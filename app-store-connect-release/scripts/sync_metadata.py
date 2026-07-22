#!/usr/bin/env python3
"""Preview or synchronize localized App Store Connect store metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from asc_api_client import AppStoreConnectClient, attributes, resolve_credentials
from validate_metadata import LIMITS, URL_FIELDS
from asc_workflow import (
    index_by_locale,
    list_localizations,
    manifest_locales,
    read_json,
    read_metadata_locales,
    resolve_app,
    resolve_app_info,
    resolve_version,
    resource_body,
    resource_id,
)


INFO_FIELDS = {"name": "name", "subtitle": "subtitle"}
VERSION_FIELDS = {
    "description": "description",
    "keywords": "keywords",
    "marketing_url": "marketingUrl",
    "promotional_text": "promotionalText",
    "release_notes": "releaseNotes",
    "support_url": "supportUrl",
}


def source_values(args: argparse.Namespace) -> tuple[dict[str, dict[str, str]], str]:
    if bool(args.metadata_root) == bool(args.manifest):
        raise SystemExit("Provide exactly one of --metadata-root or --manifest.")
    if args.metadata_root:
        return read_metadata_locales(args.metadata_root), "fastlane"
    payload = read_json(args.manifest)
    return manifest_locales(payload), "manifest"


def privacy_url(args: argparse.Namespace, metadata_root: str | None, manifest: str | None, locales: dict[str, dict[str, str]]) -> str:
    if args.privacy_url:
        return args.privacy_url.strip()
    if metadata_root:
        root_value = Path(metadata_root).expanduser().resolve() / "privacy_url.txt"
        if root_value.is_file():
            return root_value.read_text(encoding="utf-8").strip()
    if manifest:
        payload = read_json(manifest)
        app = payload.get("app", {}) if isinstance(payload.get("app", {}), dict) else {}
        value = payload.get("privacy_url", app.get("privacy_url", ""))
        if value:
            return str(value).strip()
    values = {fields.get("privacy_url", "").strip() for fields in locales.values() if fields.get("privacy_url", "").strip()}
    if len(values) == 1:
        return values.pop()
    return ""


def values_for_resource(fields: dict[str, str], mapping: dict[str, str]) -> dict[str, str]:
    return {
        api_field: fields[source_field]
        for source_field, api_field in mapping.items()
        if fields.get(source_field, "").strip()
    }


def validate_source(locales: dict[str, dict[str, str]], global_privacy_url: str) -> None:
    errors: list[str] = []
    for locale, fields in locales.items():
        for field, value in fields.items():
            value = value.strip()
            if not value:
                continue
            limit = LIMITS.get(field)
            if limit is not None and len(value) > limit:
                errors.append(f"{locale}/{field} is {len(value)} characters; limit is {limit}")
            if field in URL_FIELDS:
                parsed = urlparse(value)
                if parsed.scheme != "https" or not parsed.netloc:
                    errors.append(f"{locale}/{field} must be an HTTPS URL")
    if global_privacy_url:
        parsed = urlparse(global_privacy_url)
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append("privacy_url must be an HTTPS URL")
    if errors:
        raise SystemExit("Metadata validation failed:\n" + "\n".join(f"- {error}" for error in errors))


def plan_localization(
    *,
    locale: str,
    desired: dict[str, str],
    existing: dict[str, Any] | None,
    resource_type_value: str,
    endpoint_base: str,
    relationship_name: str,
) -> dict[str, Any] | None:
    if not desired:
        return None
    existing_attrs = attributes(existing)
    changed = {key: value for key, value in desired.items() if str(existing_attrs.get(key, "")) != value}
    if not changed:
        return None
    if existing:
        body = resource_body(resource_type_value, resource_id_value=resource_id(existing), resource_attributes=changed)
        return {
            "action": "patch",
            "locale": locale,
            "endpoint": f"{endpoint_base}/{resource_id(existing)}",
            "fields": sorted(changed),
            "body": body,
        }
    attrs_value = {"locale": locale, **desired}
    body = resource_body(
        resource_type_value,
        resource_attributes=attrs_value,
        relationships={relationship_name: {"data": {"type": "appInfos" if relationship_name == "appInfo" else "appStoreVersions", "id": "PARENT_ID"}}},
    )
    return {
        "action": "post",
        "locale": locale,
            "endpoint": endpoint_base,
        "fields": sorted(desired),
        "body": body,
        "relationship_name": relationship_name,
    }


def replace_parent_id(operation: dict[str, Any], parent_type: str, parent_id: str) -> None:
    data = operation["body"]["data"]
    relationships = data.get("relationships", {})
    relationship_name = operation.get("relationship_name")
    if relationship_name and relationship_name in relationships:
        relationships[relationship_name]["data"] = {"type": parent_type, "id": parent_id}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_argument_group("metadata source")
    source.add_argument("--metadata-root", help="Fastlane deliver metadata directory")
    source.add_argument("--manifest", help="JSON manifest with localizations")
    parser.add_argument("--bundle-id")
    parser.add_argument("--app-id")
    parser.add_argument("--version", help="Marketing version, for example 1.0.3")
    parser.add_argument("--version-id")
    parser.add_argument("--platform", help="iOS, macOS, tvOS, watchOS, or visionOS")
    parser.add_argument("--privacy-url", help="App-level privacy policy URL")
    parser.add_argument("--apply", action="store_true", help="Write planned changes; default is read-only preview")
    parser.add_argument("--api-key-id", default="")
    parser.add_argument("--issuer-id", default="")
    parser.add_argument("--key-path", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    locales, source_kind = source_values(args)
    if not locales:
        raise SystemExit("No localized metadata found in the selected source.")
    source_privacy_url = privacy_url(args, args.metadata_root, args.manifest, locales)
    validate_source(locales, source_privacy_url)
    credentials = resolve_credentials(key_id=args.api_key_id, issuer_id=args.issuer_id, key_path=args.key_path)
    client = AppStoreConnectClient(credentials)
    app = resolve_app(client, app_id=args.app_id or "", bundle_id=args.bundle_id or "")
    app_id = resource_id(app)
    info = resolve_app_info(client, app_id)
    info_id = resource_id(info)
    version = resolve_version(client, app_id, version=args.version or "", version_id=args.version_id or "", platform=args.platform or "")
    version_id = resource_id(version)

    existing_info = index_by_locale(list_localizations(client, "appInfos", info_id, "appInfoLocalizations"))
    existing_version = index_by_locale(list_localizations(client, "appStoreVersions", version_id, "appStoreVersionLocalizations"))
    operations: list[dict[str, Any]] = []

    url = source_privacy_url
    if url and str(attributes(app).get("privacyPolicyUrl", "")) != url:
        operations.append({
            "action": "patch",
            "kind": "app",
            "endpoint": f"/apps/{app_id}",
            "fields": ["privacyPolicyUrl"],
            "body": resource_body("apps", resource_id_value=app_id, resource_attributes={"privacyPolicyUrl": url}),
        })

    for locale in sorted(locales):
        fields = locales[locale]
        info_desired = values_for_resource(fields, INFO_FIELDS)
        version_desired = values_for_resource(fields, VERSION_FIELDS)
        info_operation = plan_localization(
            locale=locale,
            desired=info_desired,
            existing=existing_info.get(locale),
            resource_type_value="appInfoLocalizations",
            endpoint_base="/appInfoLocalizations",
            relationship_name="appInfo",
        )
        version_operation = plan_localization(
            locale=locale,
            desired=version_desired,
            existing=existing_version.get(locale),
            resource_type_value="appStoreVersionLocalizations",
            endpoint_base="/appStoreVersionLocalizations",
            relationship_name="appStoreVersion",
        )
        if info_operation:
            if info_operation["action"] == "post":
                replace_parent_id(info_operation, "appInfos", info_id)
            info_operation["kind"] = "app_info_localization"
            operations.append(info_operation)
        if version_operation:
            if version_operation["action"] == "post":
                replace_parent_id(version_operation, "appStoreVersions", version_id)
            version_operation["kind"] = "version_localization"
            operations.append(version_operation)

    applied: list[dict[str, Any]] = []
    if args.apply:
        for operation in operations:
            if operation["action"] == "patch":
                response = client.patch(operation["endpoint"], operation["body"])
            else:
                response = client.post(operation["endpoint"], operation["body"])
            applied.append({
                "action": operation["action"],
                "kind": operation.get("kind", ""),
                "locale": operation.get("locale", ""),
                "resource_id": resource_id(response.get("data") if isinstance(response, dict) else None),
            })

    result = {
        "source": source_kind,
        "dry_run": not args.apply,
        "app_id": app_id,
        "version_id": version_id,
        "version": attributes(version).get("versionString", ""),
        "locales": sorted(locales),
        "operation_count": len(operations),
        "operations": operations,
        "applied": applied,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        mode = "Applied" if args.apply else "Preview"
        print(f"{mode}: {len(operations)} metadata operation(s) for {len(locales)} locale(s).")
        for operation in operations:
            fields = ", ".join(operation.get("fields", []))
            print(f"{operation['action'].upper():5} {operation.get('kind', 'app'):24} {operation.get('locale', ''):<12} {fields}")
        if not operations:
            print("Metadata is already synchronized.")
        elif not args.apply:
            print("No App Store Connect metadata was changed. Re-run with --apply to write these operations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
