#!/usr/bin/env python3
"""Read-only prerequisite checks for an Xcode/App Store Connect release."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from discover_xcode_project import candidates, parse_schemes


def run_command(args: list[str], cwd: Path) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, str(exc)
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def add_result(results: list[dict[str, Any]], name: str, status: str, detail: str) -> None:
    results.append({"name": name, "status": status, "detail": detail})


def display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def select_container(root: Path, explicit: str | None, suffix: str) -> tuple[Path | None, list[Path]]:
    if explicit:
        path = Path(explicit).expanduser()
        return ((root / path).resolve() if not path.is_absolute() else path.resolve()), []
    found = candidates(root, suffix)
    if len(found) == 1:
        return found[0], found
    top_level = [path for path in found if path.parent == root]
    return (top_level[0] if len(top_level) == 1 else None), found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".", help="Xcode project root")
    parser.add_argument("--scheme", help="Expected scheme name")
    parser.add_argument("--workspace", help="Workspace path relative to project root")
    parser.add_argument("--project", help="Project path relative to project root")
    parser.add_argument("--platform", help="Target platform, for example macOS or iOS")
    parser.add_argument("--require-api", action="store_true", help="Require API credentials")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()

    root = Path(args.project_root).expanduser().resolve()
    results: list[dict[str, Any]] = []
    errors = 0

    if not root.is_dir():
        add_result(results, "project_root", "FAIL", f"Directory does not exist: {root}")
        errors += 1
    else:
        add_result(results, "project_root", "PASS", str(root))

    xcodebuild = shutil.which("xcodebuild")
    if xcodebuild:
        add_result(results, "xcodebuild", "PASS", xcodebuild)
    else:
        add_result(results, "xcodebuild", "FAIL", "xcodebuild is not available on PATH")
        errors += 1

    xcrun = shutil.which("xcrun")
    if xcrun:
        add_result(results, "xcrun", "PASS", xcrun)
    else:
        add_result(results, "xcrun", "WARN", "xcrun is not available; upload tools cannot run here")

    workspace, workspaces = select_container(root, args.workspace, ".xcworkspace") if root.is_dir() else (None, [])
    project, projects = select_container(root, args.project, ".xcodeproj") if root.is_dir() else (None, [])

    if workspace and workspace.exists():
        add_result(results, "workspace", "PASS", display_path(workspace, root))
    elif args.workspace:
        add_result(results, "workspace", "FAIL", f"Not found: {workspace}")
        errors += 1
    elif len(workspaces) > 1:
        add_result(results, "workspace", "INFO", f"Multiple workspaces discovered ({len(workspaces)}); pass --workspace to select one")
    else:
        add_result(results, "workspace", "INFO", "No single workspace discovered")

    if project and project.exists():
        add_result(results, "project", "PASS", display_path(project, root))
    elif args.project:
        add_result(results, "project", "FAIL", f"Not found: {project}")
        errors += 1
    elif len(projects) > 1:
        add_result(results, "project", "INFO", f"Multiple projects discovered ({len(projects)}); pass --project to select one")
    else:
        add_result(results, "project", "INFO", "No single project discovered")

    if args.scheme:
        container = workspace or project
        if container and xcodebuild:
            flag = "-workspace" if container.suffix == ".xcworkspace" else "-project"
            command = [xcodebuild, flag, str(container), "-list"]
            code, output = run_command(command, root)
            available_schemes = parse_schemes(output) if code == 0 else []
            if code == 0 and args.scheme in available_schemes:
                add_result(results, "scheme", "PASS", args.scheme)
            elif code == 0:
                add_result(results, "scheme", "FAIL", f"Scheme was not found: {args.scheme}")
                errors += 1
            else:
                add_result(results, "scheme", "WARN", f"Could not inspect schemes: {output[-400:]}")
        else:
            add_result(results, "scheme", "WARN", "Cannot inspect scheme without a project/workspace and xcodebuild")

    api_names = ("ASC_API_KEY_ID", "ASC_API_ISSUER_ID", "ASC_API_KEY_PATH")
    api_values = {name: os.environ.get(name, "") for name in api_names}
    missing = [name for name, value in api_values.items() if not value]
    key_path = Path(api_values["ASC_API_KEY_PATH"]).expanduser() if api_values["ASC_API_KEY_PATH"] else None
    if args.require_api and missing:
        add_result(results, "app_store_connect_api", "FAIL", "Missing: " + ", ".join(missing))
        errors += 1
    elif args.require_api and key_path and not key_path.is_file():
        add_result(results, "app_store_connect_api", "FAIL", f"API key file not found: {key_path}")
        errors += 1
    elif args.require_api:
        add_result(results, "app_store_connect_api", "PASS", "Required variables set and key file exists")
    else:
        add_result(results, "app_store_connect_api", "INFO", "Not required for this check")

    if args.platform:
        add_result(results, "platform", "INFO", args.platform)

    if args.json:
        print(json.dumps({"ok": errors == 0, "results": results}, indent=2))
    else:
        for result in results:
            print(f"{result['status']:<5} {result['name']}: {result['detail']}")
        message = "Prerequisite check passed." if errors == 0 else f"Prerequisite check failed with {errors} error(s)."
        print(f"\n{message}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
