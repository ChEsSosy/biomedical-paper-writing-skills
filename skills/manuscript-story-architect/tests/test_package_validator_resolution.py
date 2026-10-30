"""Package-only regressions for M02 validator resolution and trust binding."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPTS))
import schema_runtime


def synthetic_package(temp_root: Path) -> Path:
    package = temp_root / "02_manuscript-story-architect" / "package-candidate" / ROOT.name
    package.mkdir(parents=True)
    shutil.copytree(ROOT / "shared-core", package / "shared-core")
    return package


class PackageValidatorResolutionTests(unittest.TestCase):
    def test_legacy_sibling_cannot_shadow_package_local_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = synthetic_package(Path(temp_dir))
            legacy = (
                package.parents[1]
                / "01_style-and-structure-distiller"
                / "shared-core"
                / "scripts"
                / "validate_artifact.py"
            )
            legacy.parent.mkdir(parents=True)
            legacy.write_text("def validate_files(*args): return []\n", encoding="utf-8")
            with mock.patch.object(schema_runtime, "PACKAGE_ROOT", package):
                selected = schema_runtime.discover_validator()
            self.assertEqual(
                (package / schema_runtime.VENDORED_VALIDATOR_RELATIVE).resolve(),
                selected,
            )

    def test_explicit_arbitrary_validator_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake = Path(temp_dir) / "fake_validator.py"
            fake.write_text("def validate_files(*args): return []\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
                schema_runtime.discover_validator(fake)

    def test_vendored_validator_hash_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = synthetic_package(Path(temp_dir))
            validator = package / schema_runtime.VENDORED_VALIDATOR_RELATIVE
            validator.write_bytes(validator.read_bytes() + b"\n# tampered\n")
            with mock.patch.object(schema_runtime, "PACKAGE_ROOT", package):
                with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
                    schema_runtime.discover_validator()

    def test_vendored_inventory_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = synthetic_package(Path(temp_dir))
            inventory_path = package / schema_runtime.VENDOR_INVENTORY_RELATIVE
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["authoritative_core"]["version"] = "9.9.9"
            inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
            with mock.patch.object(schema_runtime, "PACKAGE_ROOT", package):
                with self.assertRaisesRegex(RuntimeError, "self-hash mismatch"):
                    schema_runtime.discover_validator()

    def test_explicit_byte_identical_validator_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            candidate = Path(temp_dir) / "validate_artifact.py"
            shutil.copyfile(
                ROOT / schema_runtime.VENDORED_VALIDATOR_RELATIVE,
                candidate,
            )
            self.assertEqual(candidate.resolve(), schema_runtime.discover_validator(candidate))

    def test_fake_validator_cannot_create_cli_false_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            fake = temp_root / "fake_validator.py"
            fake.write_text("def validate_files(*args): return []\n", encoding="utf-8")
            payload = json.loads(
                (FIXTURES / "valid-claim-evidence-map.json").read_text(encoding="utf-8")
            )
            payload["unexpected_packaging_probe"] = 123
            invalid = temp_root / "invalid.json"
            invalid.write_text(json.dumps(payload), encoding="utf-8")
            environment = dict(os.environ)
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPTS / "validate_claim_evidence_map.py"),
                    "--claim-map",
                    str(invalid),
                    "--validator",
                    str(fake),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
                check=False,
            )
            self.assertEqual(2, completed.returncode)
            self.assertIn("validator error", completed.stderr)
            self.assertNotIn("VALID:", completed.stdout)


if __name__ == "__main__":
    unittest.main()
