#!/usr/bin/env python3
"""Preview or synchronize localized App Store Connect screenshot sets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from asc_api_client import AppStoreConnectClient, attributes, data_list, resolve_credentials
from validate_screenshots import image_size
from asc_workflow import (
    file_checksum,
    index_by_locale,
    list_localizations,
    read_screenshot_manifest,
    resolve_app,
    resolve_version,
    resource_body,
    resource_id,
    upload_file,
    upload_operations,
)


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def screenshot_sets(client: AppStoreConnectClient, localization_id: str) -> list[dict[str, Any]]:
    return data_list(client.get(f"/appStoreVersionLocalizations/{localization_id}/appScreenshotSets", {"limit": 200}))


def screenshots_for_set(client: AppStoreConnectClient, set_id: str) -> list[dict[str, Any]]:
    return data_list(client.get(f"/appScreenshotSets/{set_id}/appScreenshots", {"limit": 200}))


def file_plan(path_value: str) -> tuple[Path, dict[str, Any]]:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"Screenshot file does not exist: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise SystemExit(f"Unsupported screenshot format {path.suffix}: {path}")
    size = path.stat().st_size
    if size <= 0:
        raise SystemExit(f"Screenshot file is empty: {path}")
    if not image_size(path):
        raise SystemExit(f"Unable to read PNG/JPEG dimensions: {path}")
    return path, {
        "fileName": path.name,
        "fileSize": size,
        "sourceFileChecksum": file_checksum(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots-root", required=True)
    parser.add_argument("--manifest", help="Manifest with locales/scenes or explicit sets")
    parser.add_argument("--bundle-id")
    parser.add_argument("--app-id")
    parser.add_argument("--version")
    parser.add_argument("--version-id")
    parser.add_argument("--platform")
    parser.add_argument("--locale", action="append", default=[], help="Only process these locale(s); repeat or comma-separate")
    parser.add_argument("--display-type", help="Override screenshot display type for every set")
    parser.add_argument("--apply", action="store_true", help="Create and upload assets; default is read-only preview")
    parser.add_argument("--replace", action="store_true", help="Delete existing screenshots in each target set before upload")
    parser.add_argument("--confirm-replace", action="store_true", help="Required with --apply --replace")
    parser.add_argument("--api-key-id", default="")
    parser.add_argument("--issuer-id", default="")
    parser.add_argument("--key-path", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.apply and args.replace and not args.confirm_replace:
        raise SystemExit("Replacement is blocked. Re-run with --confirm-replace after reviewing the target sets.")

    sets = read_screenshot_manifest(args.screenshots_root, args.manifest)
    requested_locales = {
        locale.strip()
        for value in args.locale
        for locale in value.split(",")
        if locale.strip()
    }
    if requested_locales:
        sets = [item for item in sets if item["locale"] in requested_locales]
    if args.display_type:
        for item in sets:
            item["display_type"] = args.display_type
    if not sets:
        raise SystemExit("No screenshot sets were found in the selected root or manifest.")

    credentials = resolve_credentials(key_id=args.api_key_id, issuer_id=args.issuer_id, key_path=args.key_path)
    client = AppStoreConnectClient(credentials)
    app = resolve_app(client, app_id=args.app_id or "", bundle_id=args.bundle_id or "")
    app_id = resource_id(app)
    version = resolve_version(client, app_id, version=args.version or "", version_id=args.version_id or "", platform=args.platform or "")
    version_id = resource_id(version)
    localizations = index_by_locale(list_localizations(client, "appStoreVersions", version_id, "appStoreVersionLocalizations"))

    operations: list[dict[str, Any]] = []
    execution_sets: list[dict[str, Any]] = []
    for screenshot_set in sets:
        locale = screenshot_set["locale"]
        display_type = screenshot_set["display_type"]
        localization = localizations.get(locale)
        if not localization:
            raise SystemExit(f"Version {version_id} has no App Store localization for {locale}; synchronize metadata first.")
        localization_id = resource_id(localization)
        existing_sets = screenshot_sets(client, localization_id)
        existing_set = next(
            (item for item in existing_sets if str(attributes(item).get("screenshotDisplayType", "")) == display_type),
            None,
        )
        set_id = resource_id(existing_set) if existing_set else f"DRY_RUN_SET_{locale}_{display_type}"
        existing_screenshots = screenshots_for_set(client, set_id) if existing_set else []
        existing_by_name = {str(attributes(item).get("fileName", "")): item for item in existing_screenshots}

        set_operations: list[dict[str, Any]] = []
        if not existing_set:
            set_operations.append({
                "action": "post",
                "kind": "screenshot_set",
                "locale": locale,
                "display_type": display_type,
                "endpoint": "/appScreenshotSets",
                "fields": ["screenshotDisplayType"],
                "body": resource_body(
                    "appScreenshotSets",
                    resource_attributes={"screenshotDisplayType": display_type},
                    relationships={"appStoreVersionLocalization": {"data": {"type": "appStoreVersionLocalizations", "id": localization_id}}},
                ),
            })
        if args.replace and existing_set:
            for existing in existing_screenshots:
                set_operations.append({
                    "action": "delete",
                    "kind": "screenshot",
                    "locale": locale,
                    "display_type": display_type,
                    "endpoint": f"/appScreenshots/{resource_id(existing)}",
                    "file": attributes(existing).get("fileName", ""),
                })
            existing_by_name = {}

        files_to_upload: list[tuple[Path, dict[str, Any]]] = []
        for file_value in screenshot_set["files"]:
            path, file_attrs = file_plan(file_value)
            existing = existing_by_name.get(path.name)
            if existing and str(attributes(existing).get("sourceFileChecksum", "")) == file_attrs["sourceFileChecksum"]:
                continue
            if existing and not args.replace:
                raise SystemExit(
                    f"Screenshot {locale}/{path.name} already exists with a different checksum; use --replace to replace the set safely."
                )
            files_to_upload.append((path, file_attrs))
            set_operations.append({
                "action": "upload",
                "kind": "screenshot",
                "locale": locale,
                "display_type": display_type,
                "endpoint": "/appScreenshots",
                "file": path.name,
                "file_size": file_attrs["fileSize"],
                "checksum": file_attrs["sourceFileChecksum"],
                "body": resource_body(
                    "appScreenshots",
                    resource_attributes=file_attrs,
                    relationships={"appScreenshotSet": {"data": {"type": "appScreenshotSets", "id": set_id}}},
                ),
            })
        operations.extend(set_operations)
        execution_sets.append({
            "locale": locale,
            "display_type": display_type,
            "localization_id": localization_id,
            "existing_set": existing_set,
            "set_id": set_id,
            "existing_screenshots": existing_screenshots,
            "files": files_to_upload,
        })

    applied: list[dict[str, Any]] = []
    if args.apply:
        for execution in execution_sets:
            current_set = execution["existing_set"]
            if not current_set:
                response = client.post(
                    "/appScreenshotSets",
                    resource_body(
                        "appScreenshotSets",
                        resource_attributes={"screenshotDisplayType": execution["display_type"]},
                        relationships={"appStoreVersionLocalization": {"data": {"type": "appStoreVersionLocalizations", "id": execution["localization_id"]}}},
                    ),
                )
                current_set = response.get("data") if isinstance(response, dict) else None
                if not current_set:
                    raise SystemExit(f"Apple did not return a screenshot set for {execution['locale']}.")
                execution["set_id"] = resource_id(current_set)
                applied.append({"action": "post", "kind": "screenshot_set", "locale": execution["locale"], "resource_id": execution["set_id"]})

            if args.replace:
                for existing in execution["existing_screenshots"]:
                    client.delete(f"/appScreenshots/{resource_id(existing)}")
                    applied.append({"action": "delete", "kind": "screenshot", "locale": execution["locale"], "resource_id": resource_id(existing)})

            for path, file_attrs in execution["files"]:
                response = client.post(
                    "/appScreenshots",
                    resource_body(
                        "appScreenshots",
                        resource_attributes=file_attrs,
                        relationships={"appScreenshotSet": {"data": {"type": "appScreenshotSets", "id": execution["set_id"]}}},
                    ),
                )
                resource = response.get("data") if isinstance(response, dict) else None
                if not resource or not resource_id(resource):
                    raise SystemExit(f"Apple did not return a screenshot resource for {path.name}.")
                operations_value = upload_operations(resource)
                if not operations_value:
                    raise SystemExit(f"Apple returned no upload operation for {path.name}.")
                upload_file(path, operations_value)
                client.patch(
                    f"/appScreenshots/{resource_id(resource)}",
                    resource_body("appScreenshots", resource_id_value=resource_id(resource), resource_attributes={"uploaded": True}),
                )
                applied.append({"action": "upload", "kind": "screenshot", "locale": execution["locale"], "file": path.name, "resource_id": resource_id(resource)})

    result = {
        "dry_run": not args.apply,
        "app_id": app_id,
        "version_id": version_id,
        "version": attributes(version).get("versionString", ""),
        "set_count": len(sets),
        "operation_count": len(operations),
        "operations": operations,
        "applied": applied,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        mode = "Applied" if args.apply else "Preview"
        print(f"{mode}: {len(operations)} screenshot operation(s) across {len(sets)} set(s).")
        for operation in operations:
            detail = operation.get("file") or ", ".join(operation.get("fields", []))
            print(f"{operation['action'].upper():6} {operation.get('locale', ''):<12} {operation.get('display_type', ''):<24} {detail}")
        if not operations:
            print("Screenshots are already synchronized.")
        elif not args.apply:
            print("No screenshot was changed. Re-run with --apply to create/upload assets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
