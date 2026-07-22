#!/usr/bin/env python3
"""Dependency-free smoke tests for the bundled metadata and screenshot validators."""

from __future__ import annotations

import json
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "scripts" / "validate_metadata.py"
SCREENSHOTS = ROOT / "scripts" / "validate_screenshots.py"


def png_header(width: int, height: int) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    chunk = struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr
    chunk += struct.pack(">I", zlib.crc32(b"IHDR" + ihdr) & 0xFFFFFFFF)
    return signature + chunk


class ValidatorTests(unittest.TestCase):
    def test_metadata_validator_accepts_locales(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for locale in ("en-US", "ja"):
                locale_dir = root / locale
                locale_dir.mkdir()
                values = {
                    "name": "Example App",
                    "subtitle": "A useful tool",
                    "keywords": "example,productivity",
                    "description": "A local test description.",
                    "release_notes": "Bug fixes.",
                }
                for field, value in values.items():
                    (locale_dir / f"{field}.txt").write_text(value, encoding="utf-8")
            result = subprocess.run(
                ["python3", str(METADATA), "--metadata-root", str(root), "--required-locale", "en-US,ja", "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)["valid"])

    def test_metadata_validator_rejects_overlong_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            locale_dir = Path(directory) / "en-US"
            locale_dir.mkdir(parents=True)
            values = {
                "name": "x" * 31,
                "subtitle": "A useful tool",
                "keywords": "example",
                "description": "Description",
                "release_notes": "Notes",
            }
            for field, value in values.items():
                (locale_dir / f"{field}.txt").write_text(value, encoding="utf-8")
            result = subprocess.run(["python3", str(METADATA), "--metadata-root", str(Path(directory)), "--json"], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)["valid"])

    def test_screenshot_manifest_and_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "screenshots"
            (root / "en-US").mkdir(parents=True)
            (root / "en-US" / "en-US-01.png").write_bytes(png_header(2880, 1800))
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps({
                "locales": ["en-US"],
                "recommended_minimum_size": {"width": 2880, "height": 1800},
                "scenes": [{"id": "01", "filename": "{locale}-01.png"}],
            }), encoding="utf-8")
            result = subprocess.run(
                ["python3", str(SCREENSHOTS), "--screenshots-root", str(root), "--manifest", str(manifest), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["checked_files"], 1)


if __name__ == "__main__":
    unittest.main()
