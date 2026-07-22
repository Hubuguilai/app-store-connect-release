#!/usr/bin/env python3
"""Build, export, validate, or upload an Xcode archive with explicit safety gates."""

from __future__ import annotations

import argparse
import json
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Any

from asc_api_client import AppStoreConnectClient, attributes, data_list, resolve_credentials
from discover_xcode_project import choose_container, container_args, parse_settings, parse_schemes


def run(command: list[str], cwd: Path, *, dry_run: bool = False) -> None:
    printable = " ".join(subprocess.list2cmdline([part]) for part in command)
    print(f"$ {printable}")
    if dry_run:
        return
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"Command failed with exit code {completed.returncode}: {command[0]}")


def xcode_settings(root: Path, container: Path, scheme: str, configuration: str) -> dict[str, str]:
    command = ["xcodebuild", *container_args(container), "-scheme", scheme, "-configuration", configuration, "-showBuildSettings"]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"Unable to read Xcode build settings:\n{(completed.stdout + completed.stderr)[-2000:]}")
    return parse_settings(completed.stdout + completed.stderr)


def archive_info(archive_path: Path) -> dict[str, str]:
    info_path = archive_path / "Info.plist"
    if not info_path.is_file():
        return {}
    try:
        payload = plistlib.loads(info_path.read_bytes())
    except (OSError, plistlib.InvalidFileException):
        return {}
    application = payload.get("ApplicationProperties", {})
    if not isinstance(application, dict):
        application = {}
    return {
        "bundle_id": str(application.get("CFBundleIdentifier", "")),
        "version": str(application.get("CFBundleShortVersionString", "")),
        "build_number": str(application.get("CFBundleVersion", "")),
        "team_id": str(application.get("TeamIdentifier", [""])[0] if isinstance(application.get("TeamIdentifier"), list) else application.get("TeamIdentifier", "")),
    }


def write_export_options(path: Path, team_id: str, method: str = "app-store-connect") -> None:
    payload: dict[str, Any] = {
        "method": method,
        "destination": "export",
        "signingStyle": "automatic",
        "manageAppVersionAndBuildNumber": False,
        "uploadSymbols": True,
    }
    if team_id:
        payload["teamID"] = team_id
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=False))


def package_in(export_path: Path) -> Path | None:
    packages = sorted(path for path in export_path.iterdir() if path.is_file() and path.suffix.lower() in {".ipa", ".pkg"}) if export_path.is_dir() else []
    return packages[0] if packages else None


def check_duplicate_build(
    client: AppStoreConnectClient,
    *,
    bundle_id: str,
    version: str,
    build_number: str,
) -> dict[str, Any] | None:
    app_payload = client.get("/apps", {"filter[bundleId]": bundle_id, "limit": 1})
    apps = data_list(app_payload)
    if not apps:
        return None
    app_id = apps[0]["id"]
    payload = client.get("/builds", {"filter[app]": app_id, "include": "preReleaseVersion", "limit": 200, "sort": "-uploadedDate"})
    included = {
        item.get("id"): item
        for item in payload.get("included", [])
        if isinstance(item, dict) and item.get("type") == "preReleaseVersions"
    }
    builds = data_list(payload)
    for build in builds:
        attrs_value = attributes(build)
        relationship = build.get("relationships", {}).get("preReleaseVersion", {}).get("data", {})
        pre_release = included.get(relationship.get("id"), {})
        pre_release_version = attributes(pre_release).get("version", "")
        if str(pre_release_version) == str(version) and str(attrs_value.get("version", "")) == str(build_number):
            return {"id": build.get("id"), "attributes": attrs_value}
    return None


def altool_auth_args(credentials: Any) -> list[str]:
    return [
        "--api-key", credentials.key_id,
        "--api-issuer", credentials.issuer_id,
        "--p8-file-path", str(credentials.key_path),
        "--api-key-subject", "user",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--workspace")
    parser.add_argument("--project")
    parser.add_argument("--scheme")
    parser.add_argument("--configuration", default="Release")
    parser.add_argument("--platform", default="macOS")
    parser.add_argument("--mode", choices=("archive", "validate", "upload"), required=True)
    parser.add_argument("--archive-path", default="build/AppStoreConnectRelease/App.xcarchive")
    parser.add_argument("--export-path", default="build/AppStoreConnectRelease/export")
    parser.add_argument("--export-options-plist")
    parser.add_argument("--package", help="Use an existing .ipa or .pkg instead of exporting an archive")
    parser.add_argument("--bundle-id")
    parser.add_argument("--team-id")
    parser.add_argument("--api-key-id", default="")
    parser.add_argument("--issuer-id", default="")
    parser.add_argument("--key-path", default="")
    parser.add_argument("--confirm-upload", action="store_true", help="Required for --mode upload")
    parser.add_argument("--allow-duplicate", action="store_true", help="Allow upload when the same version/build already exists")
    parser.add_argument(
        "--allow-provisioning-updates",
        action="store_true",
        help="Allow Xcode to create or update signing assets during archive/export",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.mode == "upload" and not args.confirm_upload:
        raise SystemExit("Upload is blocked. Re-run with --confirm-upload after reviewing the package and target.")

    root = Path(args.project_root).expanduser().resolve()
    container = choose_container(root, args.workspace, ".xcworkspace")
    if container is None:
        container = choose_container(root, args.project, ".xcodeproj")
    if container is None:
        raise SystemExit("Could not uniquely discover an Xcode workspace/project; pass --workspace or --project.")

    list_completed = subprocess.run(["xcodebuild", *container_args(container), "-list"], cwd=root, capture_output=True, text=True, check=False)
    if list_completed.returncode != 0:
        raise SystemExit(f"xcodebuild -list failed:\n{(list_completed.stdout + list_completed.stderr)[-2000:]}")
    schemes = parse_schemes(list_completed.stdout + list_completed.stderr)
    scheme = args.scheme or (schemes[0] if len(schemes) == 1 else "")
    if not scheme:
        raise SystemExit("A unique scheme was not discovered; pass --scheme explicitly.")
    settings = xcode_settings(root, container, scheme, args.configuration)
    bundle_id = args.bundle_id or settings.get("PRODUCT_BUNDLE_IDENTIFIER", "")
    team_id = args.team_id or settings.get("DEVELOPMENT_TEAM", "")
    version = settings.get("MARKETING_VERSION", "")
    build_number = settings.get("CURRENT_PROJECT_VERSION", "")
    archive_path = (root / args.archive_path).resolve()
    export_path = (root / args.export_path).resolve()
    summary: dict[str, Any] = {
        "mode": args.mode,
        "container": str(container),
        "scheme": scheme,
        "platform": args.platform,
        "bundle_id": bundle_id,
        "team_id": team_id,
        "version": version,
        "build_number": build_number,
        "archive_path": str(archive_path),
        "export_path": str(export_path),
    }

    if args.mode == "archive":
        command = [
            "xcodebuild", "archive", *container_args(container), "-scheme", scheme,
            "-configuration", args.configuration,
            "-destination", f"generic/platform={args.platform}",
            "-archivePath", str(archive_path),
        ]
        if args.allow_provisioning_updates:
            command.append("-allowProvisioningUpdates")
        run(command, root, dry_run=args.dry_run)
        summary["archive_created"] = not args.dry_run
    else:
        credentials = resolve_credentials(key_id=args.api_key_id, issuer_id=args.issuer_id, key_path=args.key_path)
        if args.package:
            package_path = Path(args.package).expanduser().resolve()
        else:
            if not archive_path.is_dir() and not args.dry_run:
                raise SystemExit(f"Archive does not exist: {archive_path}. Run --mode archive first.")
            export_options = Path(args.export_options_plist).expanduser().resolve() if args.export_options_plist else export_path / "ExportOptions.plist"
            if not export_options.exists() and not args.dry_run:
                write_export_options(export_options, team_id)
            export_command = [
                "xcodebuild", "-exportArchive", "-archivePath", str(archive_path),
                "-exportPath", str(export_path), "-exportOptionsPlist", str(export_options),
                "-authenticationKeyPath", str(credentials.key_path),
                "-authenticationKeyID", credentials.key_id,
                "-authenticationKeyIssuerID", credentials.issuer_id,
            ]
            if args.allow_provisioning_updates:
                export_command.append("-allowProvisioningUpdates")
            run(export_command, root, dry_run=args.dry_run)
            package_path = package_in(export_path)
        if args.dry_run:
            package_path = package_path or export_path / "App.ipa"
        if not package_path or not package_path.is_file() and not args.dry_run:
            raise SystemExit(f"No .ipa or .pkg package found in {export_path}.")
        summary["package_path"] = str(package_path)
        summary["archive_info"] = archive_info(archive_path)
        release_info = summary["archive_info"]
        release_version = release_info.get("version") or version
        release_build_number = release_info.get("build_number") or build_number
        summary["version"] = release_version
        summary["build_number"] = release_build_number
        if args.mode in {"validate", "upload"} and not args.dry_run:
            if bundle_id and release_version and release_build_number:
                existing = check_duplicate_build(AppStoreConnectClient(credentials), bundle_id=bundle_id, version=release_version, build_number=release_build_number)
                if existing and not args.allow_duplicate:
                    action = "Validation" if args.mode == "validate" else "Upload"
                    raise SystemExit(f"{action} blocked: App Store Connect already has version {release_version} build {release_build_number} (resource {existing['id']}). Use a higher build number or --allow-duplicate only intentionally.")
                summary["duplicate_build"] = bool(existing)
        auth_args = altool_auth_args(credentials)
        validate_command = ["xcrun", "altool", "--validate-app", str(package_path), *auth_args]
        run(validate_command, root, dry_run=args.dry_run)
        summary["validation_requested"] = True
        if args.mode == "upload":
            if package_path.suffix.lower() == ".ipa":
                upload_command = ["xcrun", "altool", "--upload-app", "-f", str(package_path), "--wait", *auth_args]
            else:
                upload_command = ["xcrun", "altool", "--upload-package", str(package_path), "--wait", *auth_args]
            run(upload_command, root, dry_run=args.dry_run)
            summary["upload_requested"] = True

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
