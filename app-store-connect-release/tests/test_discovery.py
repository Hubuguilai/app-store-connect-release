from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_release_prerequisites import select_container  # noqa: E402


class PrerequisiteDiscoveryTests(unittest.TestCase):
    def test_select_container_discovers_nested_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "Apps" / "Example.xcodeproj"
            nested.mkdir(parents=True)
            selected, found = select_container(root, None, ".xcodeproj")
            self.assertEqual(selected, nested)
            self.assertEqual(found, [nested])

    def test_select_container_prefers_unique_top_level_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            top = root / "Example.xcodeproj"
            nested = root / "Vendor" / "Dependency.xcodeproj"
            top.mkdir()
            nested.mkdir(parents=True)
            selected, found = select_container(root, None, ".xcodeproj")
            self.assertEqual(selected, top)
            self.assertEqual(found, [top, nested])


if __name__ == "__main__":
    unittest.main()
