#!/usr/bin/env python3
"""Discover an Xcode container, schemes, and release-relevant build settings."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SKIP_DIRS = {".git", "build", "DerivedData", "Pods", "node_modules", ".build"}
SETTING_KEYS = (
    "PRODUCT_BUNDLE_IDENTIFIER",
    "DEVELOPMENT_TEAM",
    "MARKETING_VERSION",
    "CURRENT_PROJECT_VERSION",
    "PRODUCT_NAME",
    "SDKROOT",
    "CODE_SIGN_STYLE",
    "CODE_SIGN_IDENTITY",
    "MACOSX_DEPLOYMENT_TARGET",
    "IPHONEOS_DEPLOYMENT_TARGET",
)


def run(command: list[str], cwd: Path) -> tuple[int, str]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def candidates(root: Path, suffix: str) -> list[Path]:
    results: list[Path] = []
    for path in root.rglob(f"*{suffix}"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if suffix == ".xcworkspace" and any(part.endswith(".xcodeproj") for part in path.parts):
            continue
        results.append(path)
    return sorted(results)


def choose_container(root: Path, explicit: str, suffix: str) -> Path | None:
    if explicit:
        path = (root / explicit).resolve() if not Path(explicit).is_absolute() else Path(explicit)
        if not path.exists():
            raise SystemExit(f"Xcode container does not exist: {path}")
        return path
    found = candidates(root, suffix)
    if len(found) == 1:
        return found[0]
    top_level = [path for path in found if path.parent == root]
    if len(top_level) == 1:
        return top_level[0]
    return None


def container_args(container: Path) -> list[str]:
    return ["-workspace", str(container)] if container.suffix == ".xcworkspace" else ["-project", str(container)]


def parse_schemes(output: str) -> list[str]:
    schemes: list[str] = []
    in_schemes = False
    for line in output.splitlines():
        stripped = line.strip()
        if stripped == "Schemes:":
            in_schemes = True
            continue
        if in_schemes:
            if not stripped:
                continue
            if stripped.endswith(":") and not line.startswith(" "):
                break
            if line.startswith(" ") or line.startswith("\t"):
                schemes.append(stripped)
    return schemes


def parse_settings(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in output.splitlines():
        match = re.match(r"^\s*([A-Z][A-Z0-9_]+)\s*=\s*(.*)\s*$", line)
        if match and match.group(1) in SETTING_KEYS:
            values[match.group(1)] = match.group(2)
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Directory containing the Xcode project")
    parser.add_argument("--workspace", help="Workspace path")
    parser.add_argument("--project", help="Project path")
    parser.add_argument("--scheme", help="Scheme to inspect")
    parser.add_argument("--configuration", default="Release")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"Project root does not exist: {root}")
    container = choose_container(root, args.workspace, ".xcworkspace")
    if container is None:
        container = choose_container(root, args.project, ".xcodeproj")
    if container is None:
        raise SystemExit("Could not uniquely discover an .xcworkspace or .xcodeproj; pass --workspace or --project.")

    list_code, list_output = run(["xcodebuild", *container_args(container), "-list"], root)
    if list_code != 0:
        raise SystemExit(f"xcodebuild -list failed:\n{list_output[-2000:]}")
    schemes = parse_schemes(list_output)
    selected_scheme = args.scheme or (schemes[0] if len(schemes) == 1 else "")
    result: dict[str, Any] = {
        "root": str(root),
        "container": str(container),
        "container_type": "workspace" if container.suffix == ".xcworkspace" else "project",
        "schemes": schemes,
        "scheme": selected_scheme or None,
        "configuration": args.configuration,
        "build_settings": {},
    }

    if selected_scheme:
        settings_code, settings_output = run(
            ["xcodebuild", *container_args(container), "-scheme", selected_scheme, "-configuration", args.configuration, "-showBuildSettings"],
            root,
        )
        if settings_code != 0:
            raise SystemExit(f"xcodebuild -showBuildSettings failed:\n{settings_output[-2000:]}")
        result["build_settings"] = parse_settings(settings_output)
    elif args.scheme:
        raise SystemExit(f"Scheme was not found or could not be selected: {args.scheme}")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"container: {result['container']}")
        print(f"schemes: {', '.join(schemes) or '(none discovered)'}")
        print(f"scheme: {selected_scheme or '(not selected)'}")
        for key, value in result["build_settings"].items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
