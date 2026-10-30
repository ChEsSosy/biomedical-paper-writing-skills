"""Ensure package-local schema paths declared by the adapted M02 contract resolve."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "references" / "development-contract.md"


class PackagedContractPathTests(unittest.TestCase):
    def test_declared_schema_paths_resolve_inside_package(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")
        paths = re.findall(r"Schema: `([^`]+)`", text)
        self.assertEqual(3, len(paths))
        for relative in paths:
            resolved = (ROOT / Path(*relative.split("/"))).resolve()
            resolved.relative_to(ROOT.resolve())
            self.assertTrue(resolved.is_file(), relative)

    def test_development_skill_prefix_is_not_retained(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")
        self.assertNotIn("skill/schemas/", text)


if __name__ == "__main__":
    unittest.main()
