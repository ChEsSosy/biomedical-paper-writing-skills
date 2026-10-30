from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PHASE8B_SCRIPTS = ROOT / "phase8b-candidate" / "scripts"
sys.path.insert(0, str(PHASE8B_SCRIPTS))

from phase8b_runtime import payload_sha256  # noqa: E402
from validate_phase8b_package import validate_design_revision_proposal  # noqa: E402


class Item5EntrypointTests(unittest.TestCase):
    def proposal(self):
        value = {
            "schema_name": "design_revision_proposal",
            "schema_version": "0.1.0",
            "proposal_id": "proposal-package-test",
            "proposal_sha256": "0" * 64,
            "proposal_kind": "presentation_only",
            "design_package_ref": {
                "design_package_id": "design-package-test",
                "design_package_hash": "1" * 64,
            },
            "requested_changes": [{
                "field": "layout.panel_spacing",
                "before": "compact",
                "after": "moderate",
                "reason": "improve separation",
            }],
            "authority_route": "author_review_required",
            "mutates_admitted_package": False,
        }
        value["proposal_sha256"] = payload_sha256(value, "proposal_sha256")
        return value

    def test_entrypoint_exposes_exactly_two_public_modes(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        headings = [line for line in text.splitlines() if line.startswith("## Public mode:")]
        self.assertEqual(headings, [
            "## Public mode: `design_review_only`",
            "## Public mode: `prototype_execution_and_inspection`",
        ])

    def test_standalone_design_proposal_passes(self):
        self.assertEqual(validate_design_revision_proposal(self.proposal()), [])

    def test_tampered_design_proposal_rejects(self):
        value = self.proposal()
        value["requested_changes"][0]["after"] = "wide"
        codes = {issue["code"] for issue in validate_design_revision_proposal(value)}
        self.assertIn("proposal:self_hash", codes)

    def test_phase8a_uses_package_local_shared_validator(self):
        path = ROOT / "candidate" / "scripts" / "schema_runtime.py"
        spec = importlib.util.spec_from_file_location("item5_phase8a_schema_runtime", path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.DEFAULT_VALIDATOR, ROOT / "shared-core" / "scripts" / "validate_artifact.py")
        self.assertTrue(module.DEFAULT_VALIDATOR.is_file())


if __name__ == "__main__":
    unittest.main()
