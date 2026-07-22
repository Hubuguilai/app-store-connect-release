#!/usr/bin/env python3
"""Shared helpers for App Store Connect metadata, screenshot, and IAP workflows."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from asc_api_client import AppStoreConnectClient, attributes, data_list, first_data


PLATFORM_CODES = {
    "IOS": "IOS",
    "IPHONEOS": "IOS",
    "IPADOS": "IPADOS",
    "MACOS": "MAC_OS",
    "MAC_OS": "MAC_OS",
    "TVOS": "TVOS",
    "WATCHOS": "WATCHOS",
    "VISIONOS": "VISIONOS",
}
NON_LOCALE_DIRS = {"review_information", "reviewInformation"}


def platform_code(value: str) -> str:
    normalized = value.strip().upper().replace("-", "_")
    return PLATFORM_CODES.get(normalized, normalized)


def resource_id(resource: dict[str, Any] | None) -> str:
    return str(resource.get("id", "")) if resource else ""


def resource_type(resource: dict[str, Any] | None) -> str:
    return str(resource.get("type", "")) if resource else ""


def resource_body(
    resource_type_value: str,
    *,
    resource_id_value: str | None = None,
    resource_attributes: dict[str, Any] | None = None,
    relationships: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {"type": resource_type_value}
    if resource_id_value:
        data["id"] = resource_id_value
    if resource_attributes:
        data["attributes"] = resource_attributes
    if relationships:
        data["relationships"] = relationships
    return {"data": data}


def relationship_data(resource: dict[str, Any] | None, name: str) -> dict[str, Any] | None:
    if not resource:
        return None
    relationship = resource.get("relationships", {}).get(name, {})
    value = relationship.get("data") if isinstance(relationship, dict) else None
    return value if isinstance(value, dict) else None


def relationship_id(resource: dict[str, Any] | None, name: str) -> str:
    value = relationship_data(resource, name)
    return resource_id(value)


def resolve_app(client: AppStoreConnectClient, *, app_id: str = "", bundle_id: str = "") -> dict[str, Any]:
    if app_id:
        app = first_data(client.get(f"/apps/{app_id}"))
    elif bundle_id:
        app = first_data(client.get("/apps", {"filter[bundleId]": bundle_id, "limit": 1}))
    else:
        raise SystemExit("Provide --app-id or --bundle-id.")
    if not app or not resource_id(app):
        label = app_id or bundle_id
        raise SystemExit(f"No App Store Connect app found for {label}.")
    return app


def resolve_app_info(client: AppStoreConnectClient, app_id: str) -> dict[str, Any]:
    payload = client.get(f"/apps/{app_id}/appInfos", {"include": "appInfoLocalizations", "limit": 50})
    info = first_data(payload)
    if not info:
        raise SystemExit(f"No App Store Connect appInfo found for app {app_id}.")
    return info


def resolve_version(
    client: AppStoreConnectClient,
    app_id: str,
    *,
    version: str = "",
    version_id: str = "",
    platform: str = "",
) -> dict[str, Any]:
    if version_id:
        found = first_data(client.get(f"/appStoreVersions/{version_id}"))
        if not found:
            raise SystemExit(f"No App Store Connect app store version found for {version_id}.")
        return found

    params: dict[str, Any] = {"limit": 200}
    if version:
        params["filter[versionString]"] = version
    if platform:
        params["filter[platform]"] = platform_code(platform)
    # Apple exposes collection reads through the app relationship endpoint;
    # the top-level collection may be instance-only for some API roles.
    payload = client.get(f"/apps/{app_id}/appStoreVersions", params)
    versions = data_list(payload)
    if version:
        versions = [item for item in versions if str(attributes(item).get("versionString", "")) == str(version)]
    if platform:
        versions = [item for item in versions if str(attributes(item).get("platform", "")) == platform_code(platform)]
    if not versions:
        target = version or "the requested version"
        raise SystemExit(f"No App Store Connect app store version found for {target}.")
    return versions[0]


def list_localizations(
    client: AppStoreConnectClient,
    parent_type: str,
    parent_id: str,
    relationship_name: str,
) -> list[dict[str, Any]]:
    endpoint = {
        "appInfos": f"/appInfos/{parent_id}/appInfoLocalizations",
        "appStoreVersions": f"/appStoreVersions/{parent_id}/appStoreVersionLocalizations",
        "appStoreVersionLocalizations": f"/appStoreVersionLocalizations/{parent_id}/appScreenshotSets",
        "inAppPurchases": f"/inAppPurchases/{parent_id}/inAppPurchaseLocalizations",
    }.get(parent_type)
    if not endpoint:
        raise ValueError(f"Unsupported localization parent type: {parent_type}")
    return data_list(client.get(endpoint, {"limit": 200}))


def index_by_locale(resources: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(attributes(resource).get("locale")): resource
        for resource in resources
        if attributes(resource).get("locale")
    }


def read_json(path: str | Path) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Unable to read JSON manifest {resolved}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"JSON manifest must contain an object: {resolved}")
    return value


def read_metadata_locales(root: str | Path) -> dict[str, dict[str, str]]:
    resolved = Path(root).expanduser().resolve()
    if not resolved.is_dir():
        raise SystemExit(f"Metadata root does not exist: {resolved}")
    result: dict[str, dict[str, str]] = {}
    for locale_dir in sorted(
        path
        for path in resolved.iterdir()
        if path.is_dir() and not path.name.startswith(".") and path.name not in NON_LOCALE_DIRS
    ):
        values: dict[str, str] = {}
        for path in sorted(locale_dir.glob("*.txt")):
            values[path.stem] = path.read_text(encoding="utf-8").strip()
        if values:
            result[locale_dir.name] = values
    return result


def manifest_locales(manifest: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Accept {localizations: {...}}, {locales: {...}}, or a list of locale objects."""

    value = manifest.get("localizations", manifest.get("locales", {}))
    if isinstance(value, dict):
        result = {}
        for locale, fields in value.items():
            if isinstance(fields, dict):
                result[str(locale)] = {str(key): str(item) for key, item in fields.items() if item is not None}
        return result
    if isinstance(value, list):
        result = {}
        for item in value:
            if not isinstance(item, dict) or not item.get("locale"):
                continue
            result[str(item["locale"])] = {
                str(key): str(field)
                for key, field in item.items()
                if key != "locale" and field is not None
            }
        return result
    raise SystemExit("Manifest localizations/locales must be an object or list.")


def read_screenshot_manifest(root: str | Path, manifest: str | Path | None = None) -> list[dict[str, Any]]:
    """Return screenshot sets with locale, display type, and concrete files."""

    root_path = Path(root).expanduser().resolve()
    payload = read_json(manifest) if manifest else {}
    sets_value = payload.get("sets")
    result: list[dict[str, Any]] = []
    if isinstance(sets_value, list):
        for item in sets_value:
            if not isinstance(item, dict) or not item.get("locale"):
                continue
            locale = str(item["locale"])
            display_type = str(item.get("display_type", item.get("screenshot_display_type", "APP_DESKTOP")))
            files = item.get("files", [])
            if isinstance(files, str):
                files = [files]
            result.append({
                "locale": locale,
                "display_type": display_type,
                "files": [str(root_path / locale / str(file)) for file in files],
            })
        return result

    locales_value = payload.get("locales")
    scenes = payload.get("scenes", []) if isinstance(payload.get("scenes", []), list) else []
    if isinstance(locales_value, dict):
        locale_names = [str(locale) for locale in locales_value]
    elif isinstance(locales_value, list):
        locale_names = [str(locale) for locale in locales_value]
    elif root_path.is_dir():
        locale_names = sorted(path.name for path in root_path.iterdir() if path.is_dir() and not path.name.startswith("."))
    else:
        locale_names = []

    default_display_type = str(payload.get("display_type", payload.get("screenshot_display_type", "APP_DESKTOP")))
    for locale in locale_names:
        locale_config = locales_value.get(locale, {}) if isinstance(locales_value, dict) else {}
        if not isinstance(locale_config, dict):
            locale_config = {}
        display_type = str(locale_config.get("display_type", locale_config.get("screenshot_display_type", default_display_type)))
        files_value = locale_config.get("files")
        if isinstance(files_value, str):
            filenames = [files_value]
        elif isinstance(files_value, list):
            filenames = [str(file) for file in files_value]
        elif scenes:
            filenames = []
            for scene in scenes:
                if not isinstance(scene, dict):
                    continue
                template = scene.get("filename")
                if template:
                    filenames.append(str(template).format(locale=locale))
                elif scene.get("id"):
                    filenames.append(f"{locale}-{scene['id']}.png")
        else:
            filenames = sorted(
                path.name
                for path in (root_path / locale).iterdir()
                if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
            ) if (root_path / locale).is_dir() else []
        result.append({
            "locale": locale,
            "display_type": display_type,
            "files": [str(root_path / locale / filename) for filename in filenames],
        })
    return result


def file_checksum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upload_file(path: Path, operations: list[dict[str, Any]]) -> None:
    """Upload a file using Apple's signed upload operations without logging signed URLs."""

    with path.open("rb") as handle:
        for operation in operations:
            method = str(operation.get("method", "PUT")).upper()
            offset = int(operation.get("offset", 0) or 0)
            length = int(operation.get("length", path.stat().st_size - offset) or 0)
            handle.seek(offset)
            payload = handle.read(length)
            headers = {
                str(header.get("name")): str(header.get("value", ""))
                for header in operation.get("requestHeaders", [])
                if isinstance(header, dict) and header.get("name")
            }
            headers.setdefault("Content-Length", str(len(payload)))
            headers.setdefault("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
            request = urllib.request.Request(str(operation["url"]), data=payload, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    if response.status < 200 or response.status >= 300:
                        raise RuntimeError(f"Screenshot upload returned HTTP {response.status}.")
            except urllib.error.HTTPError as exc:
                raise RuntimeError(f"Screenshot upload returned HTTP {exc.code}.") from exc


def upload_operations(resource: dict[str, Any]) -> list[dict[str, Any]]:
    value = attributes(resource).get("uploadOperations", [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
