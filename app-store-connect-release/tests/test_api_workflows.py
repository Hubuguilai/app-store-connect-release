from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_iap  # noqa: E402
import sync_metadata  # noqa: E402
import sync_screenshots  # noqa: E402
import asc_api_client  # noqa: E402
from asc_api_client import REDACTED, redact_api_output  # noqa: E402


def png_header(width: int, height: int) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    chunk = struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr
    chunk += struct.pack(">I", zlib.crc32(b"IHDR" + ihdr) & 0xFFFFFFFF)
    return signature + chunk


class FakeClient:
    instances: list["FakeClient"] = []
    scenario = "metadata"

    def __init__(self, credentials: object):
        self.calls: list[tuple[str, str, dict]] = []
        self.post_calls: list[tuple[str, dict]] = []
        self.patch_calls: list[tuple[str, dict]] = []
        self.delete_calls: list[str] = []
        self.__class__.instances.append(self)

    def get(self, path: str, params: dict | None = None, **kwargs: object) -> dict:
        params = params or {}
        self.calls.append(("GET", path, params))
        if path == "/apps":
            return {"data": [{"type": "apps", "id": "app1", "attributes": {"bundleId": "com.example.app", "privacyPolicyUrl": "https://old.example/privacy"}}]}
        if path == "/apps/app1/appInfos":
            return {"data": [{"type": "appInfos", "id": "info1", "attributes": {}}]}
        if path == "/appInfos/info1/appInfoLocalizations":
            return {"data": [{"type": "appInfoLocalizations", "id": "info-en", "attributes": {"locale": "en-US", "name": "Old Name", "subtitle": "Old subtitle"}}]}
        if path == "/apps/app1/appStoreVersions":
            return {"data": [{"type": "appStoreVersions", "id": "version1", "attributes": {"versionString": "1.0.0", "platform": "MAC_OS"}}]}
        if path == "/appStoreVersions/version1/appStoreVersionLocalizations":
            return {"data": [{"type": "appStoreVersionLocalizations", "id": "version-en", "attributes": {"locale": "en-US", "description": "Old description"}}]}
        if path == "/apps/app1/inAppPurchases":
            if self.scenario == "iap_existing":
                return {"data": [{"type": "inAppPurchases", "id": "iap-existing", "attributes": {"referenceName": "Pro Unlock", "productId": "com.example.pro", "inAppPurchaseType": "NON_CONSUMABLE", "state": "APPROVED"}}]}
            return {"data": []}
        if path == "/inAppPurchases/iap-existing/inAppPurchaseLocalizations":
            return {"data": []}
        if path == "/appStoreVersionLocalizations/version-en/appScreenshotSets":
            return {"data": []}
        raise AssertionError(f"Unexpected GET {path} {params}")

    def post(self, path: str, body: dict, **kwargs: object) -> dict:
        self.post_calls.append((path, body))
        if path == "/inAppPurchases":
            return {"data": {"type": "inAppPurchases", "id": "iap1", "attributes": {"productId": "com.example.pro", "referenceName": "Pro", "inAppPurchaseType": "NON_CONSUMABLE"}}}
        if path == "/inAppPurchaseLocalizations":
            return {"data": {"type": "inAppPurchaseLocalizations", "id": "iap-loc1", "attributes": {}}}
        if path == "/appScreenshotSets":
            return {"data": {"type": "appScreenshotSets", "id": "set1", "attributes": {"screenshotDisplayType": "APP_DESKTOP"}}}
        if path == "/appScreenshots":
            return {"data": {"type": "appScreenshots", "id": "shot1", "attributes": {"uploadOperations": [{"url": "https://signed.example/upload", "method": "PUT", "length": 4, "offset": 0, "requestHeaders": []}]}}}
        if path in {"/appInfoLocalizations", "/appStoreVersionLocalizations"}:
            return {"data": {"type": path.strip("/"), "id": "created", "attributes": {}}}
        raise AssertionError(f"Unexpected POST {path}")

    def patch(self, path: str, body: dict, **kwargs: object) -> dict:
        self.patch_calls.append((path, body))
        return {"data": {"type": "resource", "id": path.rsplit("/", 1)[-1], "attributes": body.get("data", {}).get("attributes", {})}}

    def delete(self, path: str, **kwargs: object) -> dict:
        self.delete_calls.append(path)
        return {}


def fake_credentials(*args: object, **kwargs: object) -> object:
    return object()


class ApiWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeClient.instances.clear()
        FakeClient.scenario = "metadata"

    def test_metadata_preview_is_read_only_and_create_endpoint_is_correct(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            locale_dir = root / "en-US"
            locale_dir.mkdir()
            for field, value in {
                "name": "New Name",
                "subtitle": "New subtitle",
                "description": "New description",
                "keywords": "clipboard,history",
                "release_notes": "Bug fixes.",
            }.items():
                (locale_dir / f"{field}.txt").write_text(value, encoding="utf-8")
            argv = ["sync_metadata.py", "--metadata-root", str(root), "--bundle-id", "com.example.app", "--version", "1.0.0", "--platform", "macOS"]
            with patch.object(sync_metadata, "resolve_credentials", side_effect=fake_credentials), patch.object(sync_metadata, "AppStoreConnectClient", FakeClient), patch.object(sys, "argv", argv):
                self.assertEqual(sync_metadata.main(), 0)
            client = FakeClient.instances[-1]
            self.assertEqual(client.post_calls, [])
            self.assertEqual(client.patch_calls, [])
            self.assertIn(
                (
                    "GET",
                    "/apps/app1/appStoreVersions",
                    {"limit": 200, "filter[versionString]": "1.0.0", "filter[platform]": "MAC_OS"},
                ),
                client.calls,
            )

    def test_metadata_apply_writes_localizations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "metadata"
            locale_dir = root / "ja"
            locale_dir.mkdir(parents=True)
            (locale_dir / "name.txt").write_text("クリップボード履歴", encoding="utf-8")
            (locale_dir / "subtitle.txt").write_text("履歴をすばやく検索", encoding="utf-8")
            (locale_dir / "description.txt").write_text("説明", encoding="utf-8")
            (locale_dir / "keywords.txt").write_text("clipboard,history", encoding="utf-8")
            (locale_dir / "release_notes.txt").write_text("改善", encoding="utf-8")
            argv = ["sync_metadata.py", "--metadata-root", str(root), "--bundle-id", "com.example.app", "--version", "1.0.0", "--platform", "macOS", "--apply"]
            with patch.object(sync_metadata, "resolve_credentials", side_effect=fake_credentials), patch.object(sync_metadata, "AppStoreConnectClient", FakeClient), patch.object(sys, "argv", argv):
                self.assertEqual(sync_metadata.main(), 0)
            client = FakeClient.instances[-1]
            self.assertEqual([path for path, _ in client.post_calls], ["/appInfoLocalizations", "/appStoreVersionLocalizations"])
            self.assertEqual(client.post_calls[0][1]["data"]["relationships"]["appInfo"]["data"]["id"], "info1")
            self.assertEqual(client.post_calls[1][1]["data"]["relationships"]["appStoreVersion"]["data"]["id"], "version1")

    def test_screenshot_preview_does_not_expose_signed_upload_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "screenshots"
            locale_dir = root / "en-US"
            locale_dir.mkdir(parents=True)
            (locale_dir / "en-US-01.png").write_bytes(png_header(2880, 1800))
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps({"locales": ["en-US"], "scenes": [{"id": "01", "filename": "{locale}-01.png"}]}), encoding="utf-8")
            argv = ["sync_screenshots.py", "--screenshots-root", str(root), "--manifest", str(manifest), "--bundle-id", "com.example.app", "--version", "1.0.0", "--platform", "macOS"]
            with patch.object(sync_screenshots, "resolve_credentials", side_effect=fake_credentials), patch.object(sync_screenshots, "AppStoreConnectClient", FakeClient), patch.object(sys, "argv", argv):
                self.assertEqual(sync_screenshots.main(), 0)
            client = FakeClient.instances[-1]
            self.assertEqual(client.post_calls, [])

    def test_api_output_redacts_signed_upload_details_without_mutating_response(self) -> None:
        signed_url = "https://signed.example/upload?signature=temporary-secret"
        response = {
            "data": {
                "attributes": {
                    "privacyPolicyUrl": "https://example.com/privacy",
                    "uploadOperations": [{
                        "url": signed_url,
                        "method": "PUT",
                        "length": 4,
                        "offset": 0,
                        "requestHeaders": [
                            {"name": "Authorization", "value": "temporary-header-secret"},
                            {"name": "Content-Type", "value": "image/png"},
                        ],
                    }],
                },
            },
            "meta": {"token": "temporary-token"},
        }

        safe_response = redact_api_output(response)
        operation = safe_response["data"]["attributes"]["uploadOperations"][0]

        self.assertEqual(operation["url"], REDACTED)
        self.assertEqual(operation["requestHeaders"][0]["value"], REDACTED)
        self.assertEqual(operation["requestHeaders"][1]["value"], REDACTED)
        self.assertEqual(operation["method"], "PUT")
        self.assertEqual(operation["length"], 4)
        self.assertEqual(safe_response["meta"]["token"], REDACTED)
        self.assertEqual(safe_response["data"]["attributes"]["privacyPolicyUrl"], "https://example.com/privacy")
        self.assertEqual(response["data"]["attributes"]["uploadOperations"][0]["url"], signed_url)

    def test_json_get_cli_never_prints_signed_upload_url(self) -> None:
        signed_url = "https://signed.example/upload?signature=temporary-secret"

        class JsonClient:
            def __init__(self, credentials: object, **kwargs: object):
                pass

            def get(self, path: str, params: dict | None = None, **kwargs: object) -> dict:
                return {
                    "data": {
                        "attributes": {
                            "uploadOperations": [{
                                "url": signed_url,
                                "requestHeaders": [{"name": "Authorization", "value": "temporary-header-secret"}],
                            }],
                        },
                    },
                }

        argv = ["asc_api_client.py", "get", "--path", "/appScreenshots/shot1", "--json"]
        with patch.object(asc_api_client, "resolve_credentials", return_value=object()), patch.object(
            asc_api_client, "AppStoreConnectClient", JsonClient
        ), patch.object(sys, "argv", argv), patch("builtins.print") as print_mock:
            self.assertEqual(asc_api_client.cli(), 0)

        output = print_mock.call_args.args[0]
        self.assertNotIn(signed_url, output)
        self.assertNotIn("temporary-header-secret", output)
        self.assertIn(REDACTED, output)

    def test_screenshot_apply_registers_and_confirms_asset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "screenshots"
            locale_dir = root / "en-US"
            locale_dir.mkdir(parents=True)
            (locale_dir / "en-US-01.png").write_bytes(png_header(2880, 1800))
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps({"locales": ["en-US"], "scenes": [{"id": "01", "filename": "{locale}-01.png"}]}), encoding="utf-8")
            argv = ["sync_screenshots.py", "--screenshots-root", str(root), "--manifest", str(manifest), "--bundle-id", "com.example.app", "--version", "1.0.0", "--platform", "macOS", "--apply"]
            with patch.object(sync_screenshots, "resolve_credentials", side_effect=fake_credentials), patch.object(sync_screenshots, "AppStoreConnectClient", FakeClient), patch.object(sync_screenshots, "upload_file"), patch.object(sys, "argv", argv):
                self.assertEqual(sync_screenshots.main(), 0)
            client = FakeClient.instances[-1]
            self.assertEqual([path for path, _ in client.post_calls], ["/appScreenshotSets", "/appScreenshots"])
            self.assertIn("/appScreenshots/shot1", [path for path, _ in client.patch_calls])

    def test_iap_apply_creates_product_and_localization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "iap.json"
            manifest.write_text(json.dumps({
                "products": [{
                    "product_id": "com.example.pro",
                    "name": "Pro Unlock",
                    "type": "NON_CONSUMABLE",
                    "localizations": {"en-US": {"name": "Pro Unlock", "description": "Unlock all features."}},
                }],
            }), encoding="utf-8")
            argv = ["sync_iap.py", "--manifest", str(manifest), "--bundle-id", "com.example.app", "--apply"]
            with patch.object(sync_iap, "resolve_credentials", side_effect=fake_credentials), patch.object(sync_iap, "AppStoreConnectClient", FakeClient), patch.object(sys, "argv", argv):
                self.assertEqual(sync_iap.main(), 0)
            client = FakeClient.instances[-1]
            self.assertEqual([path for path, _ in client.post_calls], ["/inAppPurchases", "/inAppPurchaseLocalizations"])
            self.assertEqual(client.post_calls[0][1]["data"]["attributes"]["referenceName"], "Pro Unlock")
            self.assertNotIn("name", client.post_calls[0][1]["data"]["attributes"])
            localization_body = client.post_calls[1][1]
            self.assertEqual(localization_body["data"]["relationships"]["inAppPurchase"]["data"]["id"], "iap1")

    def test_iap_existing_reference_name_does_not_plan_product_patch(self) -> None:
        FakeClient.scenario = "iap_existing"
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "iap.json"
            manifest.write_text(json.dumps({
                "products": [{
                    "product_id": "com.example.pro",
                    "name": "Pro Unlock",
                    "type": "NON_CONSUMABLE",
                }],
            }), encoding="utf-8")
            argv = ["sync_iap.py", "--manifest", str(manifest), "--bundle-id", "com.example.app"]
            with patch.object(sync_iap, "resolve_credentials", side_effect=fake_credentials), patch.object(sync_iap, "AppStoreConnectClient", FakeClient), patch.object(sys, "argv", argv):
                self.assertEqual(sync_iap.main(), 0)
            client = FakeClient.instances[-1]
            self.assertEqual(client.post_calls, [])
            self.assertEqual(client.patch_calls, [])


if __name__ == "__main__":
    unittest.main()
