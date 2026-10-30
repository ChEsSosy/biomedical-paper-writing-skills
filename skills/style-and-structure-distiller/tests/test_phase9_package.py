"""Package-local integrity tests copied into each Phase 9 Item 2 Skill package."""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "package-inventory.json"
RECEIPT_PATH = ROOT / "package-adaptation-receipt.json"


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def payload_sha256(value: dict, hash_field: str) -> str:
    payload = dict(value)
    payload.pop(hash_field, None)
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Phase9PackageIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
        cls.receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    def test_package_identity_and_self_hash(self) -> None:
        self.assertEqual(ROOT.name, self.inventory["skill_name"])
        self.assertEqual(
            self.inventory["package_manifest_sha256"],
            payload_sha256(self.inventory, "package_manifest_sha256"),
        )

    def test_inventory_is_the_exact_package_file_set(self) -> None:
        recorded = {item["path"]: item for item in self.inventory["files"]}
        actual = {
            path.relative_to(ROOT).as_posix()
            for path in ROOT.rglob("*")
            if path.is_file() and path != INVENTORY_PATH
        }
        self.assertEqual(actual, set(recorded))
        for relative, item in recorded.items():
            path = ROOT / Path(*relative.split("/"))
            self.assertEqual(item["sha256"], file_sha256(path), relative)
            self.assertEqual(item["size_bytes"], path.stat().st_size, relative)

    def test_vendored_shared_core_is_exact(self) -> None:
        reference = self.inventory["vendored_shared_core"]
        vendor_path = ROOT / Path(*reference["inventory_path"].split("/"))
        vendor = json.loads(vendor_path.read_text(encoding="utf-8"))
        self.assertEqual(reference["inventory_sha256"], vendor["inventory_sha256"])
        self.assertEqual(
            vendor["inventory_sha256"], payload_sha256(vendor, "inventory_sha256")
        )
        self.assertEqual(reference["version"], vendor["authoritative_core"]["version"])
        for item in vendor["files"]:
            path = ROOT / "shared-core" / Path(*item["vendored_relative_path"].split("/"))
            self.assertEqual(item["sha256"], file_sha256(path))
            self.assertEqual(item["size_bytes"], path.stat().st_size)

    def test_skill_and_ui_metadata_are_discoverable(self) -> None:
        skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        match = re.search(r"\A---\s*\nname:\s*([^\s]+)", skill_text)
        self.assertIsNotNone(match)
        self.assertEqual(ROOT.name, match.group(1))
        ui_text = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn(f"${ROOT.name}", ui_text)

    def test_skill_markdown_links_resolve_inside_package(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
        self.assertTrue(links)
        for raw in links:
            target = raw.split("#", 1)[0]
            if not target or "://" in target:
                continue
            resolved = (ROOT / Path(*target.split("/"))).resolve()
            resolved.relative_to(ROOT.resolve())
            self.assertTrue(resolved.is_file(), raw)

    def test_adaptation_receipt_is_fail_closed(self) -> None:
        self.assertEqual("phase9_item2_package_adaptation", self.receipt["schema_name"])
        self.assertFalse(self.receipt["frozen_source_modified"])
        self.assertEqual(
            self.receipt["receipt_sha256"],
            payload_sha256(self.receipt, "receipt_sha256"),
        )
        self.assertGreater(self.receipt["source_file_count"], 0)
        self.assertTrue(self.receipt["adapted_files"])


if __name__ == "__main__":
    unittest.main()
