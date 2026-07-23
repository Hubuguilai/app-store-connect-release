#!/usr/bin/env python3
"""Small dependency-free App Store Connect API client for macOS CI and local release tools."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

BASE_URLS = {1: "https://api.appstoreconnect.apple.com/v1", 2: "https://api.appstoreconnect.apple.com/v2"}
COMMON_KEY_DIRS = (
    Path.cwd() / "private_keys",
    Path.cwd(),
    Path.home() / "private_keys",
    Path.home() / ".private_keys",
    Path.home() / ".appstoreconnect" / "private_keys",
    Path.home() / "Downloads",
)


@dataclass(frozen=True)
class Credentials:
    key_id: str
    issuer_id: str
    key_path: Path


class ApiError(RuntimeError):
    def __init__(self, method: str, path: str, status: int, payload: Any):
        self.method = method
        self.path = path
        self.status = status
        self.payload = payload
        super().__init__(self.message())

    def message(self) -> str:
        if isinstance(self.payload, dict) and isinstance(self.payload.get("errors"), list):
            messages = []
            for error in self.payload["errors"][:5]:
                parts = [str(error.get(key, "")) for key in ("status", "code", "title", "detail")]
                messages.append(" ".join(part for part in parts if part))
            return "; ".join(messages)
        return str(self.payload)[:1000]


def _key_id_from_path(path: Path) -> str:
    prefix = "AuthKey_"
    suffix = ".p8"
    if path.name.startswith(prefix) and path.name.endswith(suffix):
        return path.name[len(prefix) : -len(suffix)]
    return ""


def discover_key_paths() -> list[Path]:
    found: set[Path] = set()
    for directory in COMMON_KEY_DIRS:
        if directory.is_dir():
            found.update(path for path in directory.glob("AuthKey_*.p8") if path.is_file() and path.stat().st_size > 0)
    return sorted(found)


def resolve_credentials(
    *, key_id: str = "", issuer_id: str = "", key_path: str = ""
) -> Credentials:
    resolved_key_id = (key_id or os.environ.get("ASC_API_KEY_ID", "")).strip()
    resolved_issuer = (issuer_id or os.environ.get("ASC_API_ISSUER_ID", "")).strip()
    path_value = (key_path or os.environ.get("ASC_API_KEY_PATH", "")).strip()
    resolved_path = Path(path_value).expanduser() if path_value else None

    if resolved_path and not resolved_key_id:
        resolved_key_id = _key_id_from_path(resolved_path)

    if resolved_key_id and not resolved_path:
        for directory in COMMON_KEY_DIRS:
            candidate = directory / f"AuthKey_{resolved_key_id}.p8"
            if candidate.is_file() and candidate.stat().st_size > 0:
                resolved_path = candidate
                break

    if not resolved_path and not resolved_key_id:
        discovered = discover_key_paths()
        if len(discovered) == 1:
            resolved_path = discovered[0]
            resolved_key_id = _key_id_from_path(resolved_path)
        elif len(discovered) > 1:
            ids = sorted({_key_id_from_path(path) for path in discovered})
            raise SystemExit("Multiple App Store Connect API keys found; set ASC_API_KEY_ID explicitly: " + ", ".join(ids))

    if not resolved_issuer:
        raise SystemExit("ASC_API_ISSUER_ID is required.")
    if not resolved_key_id:
        raise SystemExit("ASC_API_KEY_ID or ASC_API_KEY_PATH is required.")
    if not resolved_path or not resolved_path.is_file() or resolved_path.stat().st_size == 0:
        raise SystemExit(f"App Store Connect key file was not found for key ID {resolved_key_id}.")
    return Credentials(resolved_key_id, resolved_issuer, resolved_path)


def _base64url(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_jwt(credentials: Credentials, lifetime_seconds: int = 900) -> str:
    """Generate an Apple ES256 JWT without adding a Python crypto dependency."""

    ruby = r'''
require "base64"
require "json"
require "openssl"

key_path = ARGV.fetch(0)
key_id = ARGV.fetch(1)
issuer_id = ARGV.fetch(2)
lifetime = Integer(ENV.fetch("ASC_JWT_LIFETIME", "900"))

def base64url(data)
  Base64.urlsafe_encode64(data, padding: false)
end

private_key = OpenSSL::PKey.read(File.read(key_path))
now = Time.now.to_i
header = { alg: "ES256", kid: key_id, typ: "JWT" }
payload = { iss: issuer_id, iat: now, exp: now + lifetime, aud: "appstoreconnect-v1" }
signing_input = [base64url(JSON.generate(header)), base64url(JSON.generate(payload))].join(".")
signature_der = private_key.sign(OpenSSL::Digest::SHA256.new, signing_input)
signature_asn1 = OpenSSL::ASN1.decode(signature_der)
signature_raw = signature_asn1.value.map do |integer|
  hex = integer.value.to_i.to_s(16)
  hex = "0#{hex}" if hex.length.odd?
  [hex].pack("H*").rjust(32, "\0")
end.join
puts "#{signing_input}.#{base64url(signature_raw)}"
'''
    environment = dict(os.environ)
    environment["ASC_JWT_LIFETIME"] = str(max(60, min(lifetime_seconds, 1200)))
    result = subprocess.run(
        ["ruby", "-e", ruby, str(credentials.key_path), credentials.key_id, credentials.issuer_id],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Unable to generate App Store Connect JWT.")
    token = result.stdout.strip()
    if token.count(".") != 2:
        raise RuntimeError("JWT generator returned an invalid token.")
    return token


def first_data(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    value = payload.get("data")
    if isinstance(value, list):
        return value[0] if value else None
    return value if isinstance(value, dict) else None


def data_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    value = payload.get("data")
    return value if isinstance(value, list) else []


def attributes(resource: Optional[dict[str, Any]]) -> dict[str, Any]:
    value = resource.get("attributes") if resource else None
    return value if isinstance(value, dict) else {}


REDACTED = "[REDACTED]"
SENSITIVE_OUTPUT_KEYS = {
    "authorization",
    "accesstoken",
    "idtoken",
    "privatekey",
    "refreshtoken",
    "secret",
    "token",
}


def redact_api_output(
    value: Any,
    *,
    in_upload_operation: bool = False,
    in_upload_headers: bool = False,
) -> Any:
    """Return a JSON-safe copy with credentials and signed upload details removed."""

    if isinstance(value, list):
        return [
            redact_api_output(
                item,
                in_upload_operation=in_upload_operation,
                in_upload_headers=in_upload_headers,
            )
            for item in value
        ]
    if not isinstance(value, dict):
        return value

    redacted: dict[str, Any] = {}
    for key, item in value.items():
        normalized = str(key).replace("_", "").replace("-", "").lower()
        if normalized in SENSITIVE_OUTPUT_KEYS:
            redacted[key] = REDACTED
        elif in_upload_operation and normalized == "url":
            redacted[key] = REDACTED
        elif in_upload_headers and normalized != "name":
            redacted[key] = REDACTED
        else:
            child_upload_operation = in_upload_operation or normalized == "uploadoperations"
            child_upload_headers = in_upload_headers or (
                in_upload_operation and normalized in {"headers", "requestheaders"}
            )
            redacted[key] = redact_api_output(
                item,
                in_upload_operation=child_upload_operation,
                in_upload_headers=child_upload_headers,
            )
    return redacted


class AppStoreConnectClient:
    def __init__(self, credentials: Credentials, *, timeout: int = 60, retries: int = 3):
        self.credentials = credentials
        self.token = generate_jwt(credentials)
        self.timeout = timeout
        self.retries = max(1, retries)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        body: Optional[dict[str, Any]] = None,
        version: int = 1,
    ) -> dict[str, Any]:
        if not path.startswith("/"):
            raise ValueError("App Store Connect API paths must start with '/'.")
        base = BASE_URLS.get(version)
        if not base:
            raise ValueError(f"Unsupported App Store Connect API version: {version}")
        query = urllib.parse.urlencode(params or {}, doseq=True)
        url = f"{base}{path}{'?' + query if query else ''}"
        encoded_body = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        if encoded_body is not None:
            headers["Content-Type"] = "application/json"

        last_error: Optional[BaseException] = None
        for attempt in range(self.retries):
            request = urllib.request.Request(url, data=encoded_body, headers=headers, method=method.upper())
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read().decode("utf-8")
                    return json.loads(raw) if raw.strip() else {}
            except urllib.error.HTTPError as error:
                raw = error.read().decode("utf-8", errors="replace")
                try:
                    payload: Any = json.loads(raw)
                except json.JSONDecodeError:
                    payload = raw
                if error.code in {429, 500, 502, 503, 504} and attempt + 1 < self.retries:
                    retry_after = error.headers.get("Retry-After", "")
                    try:
                        delay = min(float(retry_after), 30) if retry_after else 2**attempt
                    except ValueError:
                        delay = 2**attempt
                    time.sleep(delay)
                    continue
                raise ApiError(method.upper(), path, error.code, payload) from error
            except (urllib.error.URLError, TimeoutError, socket.timeout) as error:
                last_error = error
                if attempt + 1 < self.retries:
                    time.sleep(2**attempt)
                    continue
        raise ApiError(method.upper(), path, 0, f"Network error: {last_error}") from last_error

    def get(self, path: str, params: Optional[dict[str, Any]] = None, *, version: int = 1) -> dict[str, Any]:
        return self.request("GET", path, params=params, version=version)

    def post(self, path: str, body: dict[str, Any], *, version: int = 1) -> dict[str, Any]:
        return self.request("POST", path, body=body, version=version)

    def patch(self, path: str, body: dict[str, Any], *, version: int = 1) -> dict[str, Any]:
        return self.request("PATCH", path, body=body, version=version)

    def delete(self, path: str, *, version: int = 1) -> dict[str, Any]:
        return self.request("DELETE", path, version=version)


def parse_params(values: Iterable[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"Invalid --param value; expected key=value: {value}")
        key, item = value.split("=", 1)
        params[key] = item
    return params


def cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-key-id", default="", help="Override ASC_API_KEY_ID")
    parser.add_argument("--issuer-id", default="", help="Override ASC_API_ISSUER_ID")
    parser.add_argument("--key-path", default="", help="Override ASC_API_KEY_PATH")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--json", action="store_true", help="Print the complete JSON response")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("auth", help="Perform a read-only /apps authentication probe")
    app_parser = subparsers.add_parser("app", help="Find one app by bundle ID")
    app_parser.add_argument("--bundle-id", required=True)
    builds_parser = subparsers.add_parser("builds", help="List builds for an app")
    builds_parser.add_argument("--app-id")
    builds_parser.add_argument("--bundle-id")
    builds_parser.add_argument("--version")
    builds_parser.add_argument("--build-number")
    builds_parser.add_argument("--limit", type=int, default=50)
    get_parser = subparsers.add_parser("get", help="Perform a read-only GET request")
    get_parser.add_argument("--path", required=True)
    get_parser.add_argument("--param", action="append", default=[])
    get_parser.add_argument("--api-version", type=int, choices=(1, 2), default=1)
    for command_parser in (subparsers.choices["auth"], app_parser, builds_parser, get_parser):
        command_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    args = parser.parse_args()
    credentials = resolve_credentials(key_id=args.api_key_id, issuer_id=args.issuer_id, key_path=args.key_path)
    client = AppStoreConnectClient(credentials, timeout=args.timeout)

    if args.command == "auth":
        payload = client.get("/apps", {"limit": 1})
        result: Any = {"authenticated": True, "apps_returned": len(data_list(payload))}
    elif args.command == "app":
        result = client.get("/apps", {"filter[bundleId]": args.bundle_id, "limit": 1})
    elif args.command == "builds":
        app_id = args.app_id
        if not app_id and args.bundle_id:
            app_id = first_data(client.get("/apps", {"filter[bundleId]": args.bundle_id, "limit": 1}))
            app_id = app_id.get("id") if app_id else None
        if not app_id:
            raise SystemExit("Provide --app-id or --bundle-id.")
        params: dict[str, Any] = {"filter[app]": app_id, "include": "preReleaseVersion", "limit": args.limit, "sort": "-uploadedDate"}
        result = client.get("/builds", params)
        if args.version or args.build_number:
            included = {
                item.get("id"): item
                for item in result.get("included", [])
                if isinstance(item, dict) and item.get("type") == "preReleaseVersions"
            }
            filtered = []
            for build in data_list(result):
                attrs_value = attributes(build)
                relationship = build.get("relationships", {}).get("preReleaseVersion", {}).get("data", {})
                pre_release = included.get(relationship.get("id"), {})
                pre_release_version = attributes(pre_release).get("version", "")
                if args.version and str(pre_release_version) != str(args.version):
                    continue
                if args.build_number and str(attrs_value.get("version", "")) != str(args.build_number):
                    continue
                filtered.append(build)
            result = {"data": filtered, "included": list(included.values()), "meta": result.get("meta", {})}
    else:
        result = client.get(args.path, parse_params(args.param), version=args.api_version)

    safe_result = redact_api_output(result)
    if args.json:
        print(json.dumps(safe_result, ensure_ascii=False, indent=2))
    elif isinstance(result, dict) and "data" in result:
        items = data_list(result)
        print(f"Returned resources: {len(items)}")
        for item in items[:20]:
            attrs = attributes(item)
            label = attrs.get("name") or attrs.get("versionString") or attrs.get("bundleId") or attrs.get("buildNumber") or ""
            print(f"{item.get('type', '')} {item.get('id', '')} {label}".rstrip())
    else:
        print(json.dumps(safe_result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(cli())
