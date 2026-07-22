#!/usr/bin/env python3
"""Poll App Store Connect until a build reaches a terminal processing state."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Any

from asc_api_client import AppStoreConnectClient, attributes, data_list, first_data, resolve_credentials

TERMINAL_STATES = {"VALID", "INVALID", "FAILED", "PROCESSING_EXCEPTION", "DUPLICATE"}


def find_app(client: AppStoreConnectClient, bundle_id: str) -> dict[str, Any]:
    app = first_data(client.get("/apps", {"filter[bundleId]": bundle_id, "limit": 1}))
    if not app:
        raise SystemExit(f"No App Store Connect app found for bundle ID {bundle_id}.")
    return app


def find_build(client: AppStoreConnectClient, args: argparse.Namespace) -> dict[str, Any] | None:
    if args.build_id:
        return first_data(client.get(f"/builds/{args.build_id}"))
    app_id = args.app_id or find_app(client, args.bundle_id)["id"]
    params: dict[str, Any] = {"filter[app]": app_id, "include": "preReleaseVersion", "limit": 200, "sort": "-uploadedDate"}
    payload = client.get("/builds", params)
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
        if args.version and str(pre_release_version) != str(args.version):
            continue
        if args.build_number and str(attrs_value.get("version", "")) != str(args.build_number):
            continue
        build["_asc_pre_release_version"] = pre_release_version
        return build
    return None


def snapshot(build: dict[str, Any] | None) -> dict[str, Any]:
    if not build:
        return {"found": False}
    attrs = attributes(build)
    return {
        "found": True,
        "id": build.get("id"),
        "type": build.get("type"),
        "version": build.get("_asc_pre_release_version"),
        "build_number": attrs.get("version"),
        "processing_state": attrs.get("processingState"),
        "processing_state_details": attrs.get("processingStateDetails"),
        "build_audience_type": attrs.get("buildAudienceType"),
        "uploaded_date": attrs.get("uploadedDate"),
        "min_os_version": attrs.get("minOsVersion"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-id")
    parser.add_argument("--app-id")
    parser.add_argument("--build-id")
    parser.add_argument("--version")
    parser.add_argument("--build-number")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--interval", type=int, default=20)
    parser.add_argument("--once", action="store_true", help="Query once and exit")
    parser.add_argument("--api-key-id", default="")
    parser.add_argument("--issuer-id", default="")
    parser.add_argument("--key-path", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.build_id and not (args.bundle_id or args.app_id):
        raise SystemExit("Provide --build-id, --bundle-id, or --app-id.")

    credentials = resolve_credentials(key_id=args.api_key_id, issuer_id=args.issuer_id, key_path=args.key_path)
    client = AppStoreConnectClient(credentials)
    deadline = time.monotonic() + max(0, args.timeout)
    history: list[dict[str, Any]] = []
    while True:
        build = find_build(client, args)
        current = snapshot(build)
        current["observed_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        history.append(current)
        if not build:
            if args.once or time.monotonic() >= deadline:
                break
        else:
            state = current.get("processing_state")
            if args.once or state in TERMINAL_STATES or time.monotonic() >= deadline:
                break
        time.sleep(max(1, args.interval))

    result = {"final": history[-1] if history else {"found": False}, "observations": history}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        final = result["final"]
        print(json.dumps(final, ensure_ascii=False, indent=2))
        if not final.get("found"):
            print("No matching build was found before the polling deadline.")
        elif final.get("processing_state") not in TERMINAL_STATES:
            print("Polling ended before a terminal processing state was observed.")
    return 0 if result["final"].get("found") and result["final"].get("processing_state") in TERMINAL_STATES else 1


if __name__ == "__main__":
    sys.exit(main())
