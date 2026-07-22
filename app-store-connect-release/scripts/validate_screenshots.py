#!/usr/bin/env python3
"""Validate localized App Store screenshot files with only the Python standard library."""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def png_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) >= 24 and header[:8] == PNG_SIGNATURE and header[12:16] == b"IHDR":
        return struct.unpack(">II", header[16:24])
    return None


def jpeg_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as handle:
        data = handle.read()
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(data):
            break
        length = struct.unpack(">H", data[index : index + 2])[0]
        if length < 2 or index + length > len(data):
            break
        if marker in set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0)):
            if length >= 7:
                height, width = struct.unpack(">HH", data[index + 3 : index + 7])
                return width, height
        index += length
    return None


def image_size(path: Path) -> tuple[int, int] | None:
    if path.suffix.lower() == ".png":
        return png_size(path)
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        return jpeg_size(path)
    return None


def split_values(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        result.extend(item.strip() for item in value.split(",") if item.strip())
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots-root", required=True)
    parser.add_argument("--manifest", help="Optional manifest with locales, scenes, and recommended_minimum_size")
    parser.add_argument("--required-locale", action="append", default=[])
    parser.add_argument("--required-scene", action="append", default=[])
    parser.add_argument("--min-width", type=int)
    parser.add_argument("--min-height", type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.screenshots_root).expanduser().resolve()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {}
    if args.manifest:
        manifest_path = Path(args.manifest).expanduser().resolve()
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append({"code": "invalid_manifest", "detail": str(exc)})

    manifest_locales = [str(item) for item in manifest.get("locales", []) if item]
    locales = split_values(args.required_locale) or manifest_locales
    if not locales and root.is_dir():
        locales = sorted(path.name for path in root.iterdir() if path.is_dir() and not path.name.startswith("."))
    if not root.is_dir():
        errors.append({"code": "missing_root", "detail": str(root)})

    scenes = manifest.get("scenes", []) if isinstance(manifest.get("scenes", []), list) else []
    expected_scene_ids = split_values(args.required_scene)
    if expected_scene_ids:
        scenes = [scene for scene in scenes if scene.get("id") in expected_scene_ids]
    min_size = manifest.get("recommended_minimum_size", {}) if isinstance(manifest.get("recommended_minimum_size", {}), dict) else {}
    min_width = args.min_width if args.min_width is not None else int(min_size.get("width", 0) or 0)
    min_height = args.min_height if args.min_height is not None else int(min_size.get("height", 0) or 0)
    checked = 0
    dimensions: dict[str, list[int]] = {}

    for locale in locales:
        locale_dir = root / locale
        if not locale_dir.is_dir():
            errors.append({"code": "missing_locale", "locale": locale, "detail": str(locale_dir)})
            continue
        if scenes:
            expected_files = []
            for scene in scenes:
                template = scene.get("filename")
                if template:
                    expected_files.append(str(template).format(locale=locale))
                elif scene.get("id"):
                    expected_files.append(f"{locale}-{scene['id']}.png")
        else:
            expected_files = sorted(path.name for path in locale_dir.iterdir() if path.suffix.lower() in SUPPORTED_EXTENSIONS)
        for filename in expected_files:
            path = locale_dir / filename
            if not path.is_file():
                errors.append({"code": "missing_screenshot", "locale": locale, "file": filename, "detail": str(path)})
                continue
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                errors.append({"code": "unsupported_format", "locale": locale, "file": filename, "detail": path.suffix})
                continue
            size = image_size(path)
            if not size:
                errors.append({"code": "invalid_image", "locale": locale, "file": filename, "detail": "Unable to read PNG/JPEG dimensions."})
                continue
            checked += 1
            dimensions[f"{locale}/{filename}"] = [size[0], size[1]]
            if min_width and size[0] < min_width or min_height and size[1] < min_height:
                errors.append({"code": "too_small", "locale": locale, "file": filename, "detail": f"{size[0]}x{size[1]}, minimum {min_width}x{min_height}."})

        actual_files = {path.name for path in locale_dir.iterdir() if path.suffix.lower() in SUPPORTED_EXTENSIONS}
        extra = sorted(actual_files - set(expected_files)) if scenes else []
        for filename in extra:
            warnings.append({"code": "unlisted_screenshot", "locale": locale, "file": filename, "detail": "Image is not listed in the manifest."})

    result = {
        "valid": not errors,
        "screenshots_root": str(root),
        "locales": locales,
        "scene_count": len(scenes),
        "minimum_size": {"width": min_width, "height": min_height},
        "checked_files": checked,
        "dimensions": dimensions,
        "errors": errors,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Locales: {len(locales)}; files checked: {checked}")
        print(f"Errors: {len(errors)}; warnings: {len(warnings)}")
        for error in errors:
            print(f"FAIL {error.get('locale', '')}/{error.get('file', '')}: {error['detail']}")
        for warning in warnings:
            print(f"WARN {warning.get('locale', '')}/{warning.get('file', '')}: {warning['detail']}")
        print("Screenshot validation passed." if not errors else "Screenshot validation failed.")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
