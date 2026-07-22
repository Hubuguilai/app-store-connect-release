#!/usr/bin/env python3
"""Validate a Fastlane deliver metadata directory without contacting Apple."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

LIMITS = {
    "name": 30,
    "subtitle": 30,
    "keywords": 100,
    "promotional_text": 170,
    "description": 4000,
    "release_notes": 4000,
}
DEFAULT_REQUIRED_FIELDS = ("name", "subtitle", "keywords", "description", "release_notes")
URL_FIELDS = {"support_url", "privacy_url", "marketing_url"}
NON_LOCALE_DIRS = {"review_information", "reviewInformation"}


def split_values(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        result.extend(item.strip() for item in value.split(",") if item.strip())
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-root", required=True, help="Fastlane metadata directory")
    parser.add_argument("--required-locale", action="append", default=[], help="Locale(s) required; repeat or comma-separate")
    parser.add_argument("--required-field", action="append", default=[], help="Field(s) required in every locale")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.metadata_root).expanduser().resolve()
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if not root.is_dir():
        errors.append({"code": "missing_root", "detail": str(root)})
        result = {"valid": False, "metadata_root": str(root), "locales": [], "errors": errors, "warnings": warnings}
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else f"FAIL metadata root: {root}")
        return 1

    locales = sorted(path.name for path in root.iterdir() if path.is_dir() and path.name not in NON_LOCALE_DIRS and not path.name.startswith("."))
    required_locales = split_values(args.required_locale)
    required_fields = split_values(args.required_field) or list(DEFAULT_REQUIRED_FIELDS)
    for locale in required_locales:
        if locale not in locales:
            errors.append({"code": "missing_locale", "locale": locale, "detail": "Locale directory is missing."})

    counts: dict[str, dict[str, int]] = {}
    for locale in locales:
        locale_dir = root / locale
        counts[locale] = {}
        for field in required_fields:
            path = locale_dir / f"{field}.txt"
            if not path.is_file():
                errors.append({"code": "missing_field", "locale": locale, "field": field, "detail": str(path)})
                continue
            value = path.read_text(encoding="utf-8").strip()
            counts[locale][field] = len(value)
            if not value:
                errors.append({"code": "empty_field", "locale": locale, "field": field, "detail": "Field is empty."})
            limit = LIMITS.get(field)
            if limit is not None and len(value) > limit:
                errors.append({"code": "over_limit", "locale": locale, "field": field, "detail": f"{len(value)} characters; limit is {limit}."})
        for field in URL_FIELDS:
            path = locale_dir / f"{field}.txt"
            if not path.is_file():
                continue
            value = path.read_text(encoding="utf-8").strip()
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.netloc:
                errors.append({"code": "invalid_url", "locale": locale, "field": field, "detail": value or "empty"})

        for path in locale_dir.glob("*.txt"):
            if path.stem not in LIMITS and path.stem not in URL_FIELDS and path.stem not in {"copyright"}:
                warnings.append({"code": "unrecognized_field", "locale": locale, "field": path.stem, "detail": "File will not be checked by default."})

    result = {
        "valid": not errors,
        "metadata_root": str(root),
        "locales": locales,
        "required_locales": required_locales,
        "required_fields": required_fields,
        "field_lengths": counts,
        "errors": errors,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Locales: {len(locales)}")
        print(f"Errors: {len(errors)}; warnings: {len(warnings)}")
        for error in errors:
            location = ":".join(str(error.get(key)) for key in ("locale", "field") if error.get(key))
            print(f"FAIL {location}: {error['detail']}")
        for warning in warnings:
            print(f"WARN {warning.get('locale', '')}/{warning.get('field', '')}: {warning['detail']}")
        print("Metadata validation passed." if not errors else "Metadata validation failed.")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
