"""Positive and negative contract tests for manuscript-story-architect artifacts."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
FIXTURES = ROOT / "tests" / "fixtures"
VALIDATOR_PATH = ROOT / "shared-core" / "scripts" / "validate_artifact.py"

SCHEMA_BY_FIXTURE = {
    "valid-claim-evidence-map.json": "claim-evidence-map.schema.json",
    "valid-interpretation-card.json": "interpretation-card.schema.json",
    "valid-manuscript-plan.json": "manuscript-plan.schema.json",
}


def load_validator_module():
    """Load the frozen dependency-free validator without installing the candidate."""
    spec = importlib.util.spec_from_file_location("story_contract_validator", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load shared validator: {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def apply_mutation(payload: object, case: dict) -> object:
    """Apply one explicit fixture mutation so each negative case stays reviewable."""
    mutated = copy.deepcopy(payload)
    target = mutated
    path = case["path"]
    for token in path[:-1]:
        target = target[token]
    final = path[-1]
    if case["operation"] in {"add", "replace"}:
        target[final] = case["value"]
    elif case["operation"] == "remove":
        del target[final]
    else:
        raise RuntimeError(f"Unsupported negative-fixture operation: {case['operation']}")
    return mutated


def validate_payload(validator: object, schema_path: Path, payload: object) -> list:
    """Validate an in-memory variant without adding another persistent fixture."""
    with tempfile.TemporaryDirectory() as temp_dir:
        data_path = Path(temp_dir) / "payload.json"
        data_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return validator.validate_files(schema_path, data_path)


class StoryArtifactSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_validator_module()

    def test_positive_claim_evidence_map(self) -> None:
        issues = self.validator.validate_files(
            SCHEMAS / "claim-evidence-map.schema.json",
            FIXTURES / "valid-claim-evidence-map.json",
        )
        self.assertEqual([], issues)

    def test_positive_interpretation_card(self) -> None:
        issues = self.validator.validate_files(
            SCHEMAS / "interpretation-card.schema.json",
            FIXTURES / "valid-interpretation-card.json",
        )
        self.assertEqual([], issues)

    def test_positive_manuscript_plan(self) -> None:
        issues = self.validator.validate_files(
            SCHEMAS / "manuscript-plan.schema.json",
            FIXTURES / "valid-manuscript-plan.json",
        )
        self.assertEqual([], issues)

    def test_notes_only_plan_declares_reverse_outline_skip(self) -> None:
        payload = json.loads(
            (FIXTURES / "valid-manuscript-plan.json").read_text(encoding="utf-8")
        )
        payload["current_structure_assessment"] = {
            "input_mode": "structured_notes",
            "skipped_reason": "no_existing_manuscript_structure_to_reverse_outline",
        }
        issues = validate_payload(
            self.validator,
            SCHEMAS / "manuscript-plan.schema.json",
            payload,
        )
        self.assertEqual([], issues)

    def test_optional_profile_and_journal_inputs_may_be_absent(self) -> None:
        payload = json.loads(
            (FIXTURES / "valid-manuscript-plan.json").read_text(encoding="utf-8")
        )
        del payload["upstream_profiles"]
        del payload["journal_adaptation"]
        issues = validate_payload(
            self.validator,
            SCHEMAS / "manuscript-plan.schema.json",
            payload,
        )
        self.assertEqual([], issues)

    def test_explicitly_approved_novelty_branch(self) -> None:
        payload = json.loads(
            (FIXTURES / "valid-manuscript-plan.json").read_text(encoding="utf-8")
        )
        novelty = payload["story_anchors"]["novelty_scope"]
        novelty["provenance"] = "explicitly_approved_by_author"
        novelty["author_approval"] = "approved"
        issues = validate_payload(
            self.validator,
            SCHEMAS / "manuscript-plan.schema.json",
            payload,
        )
        self.assertEqual([], issues)

    def test_source_located_central_question_candidate(self) -> None:
        payload = json.loads(
            (FIXTURES / "valid-manuscript-plan.json").read_text(encoding="utf-8")
        )
        central_question = payload["story_anchors"]["central_question"]
        central_question["provenance"] = "explicitly_stated_in_author_source"
        central_question["author_approval"] = "pending"
        issues = validate_payload(
            self.validator,
            SCHEMAS / "manuscript-plan.schema.json",
            payload,
        )
        self.assertEqual([], issues)

    def test_negative_cases_fail_on_declared_boundary(self) -> None:
        cases = json.loads((FIXTURES / "negative-cases.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            for case in cases:
                with self.subTest(case=case["case_id"]):
                    source_path = FIXTURES / case["fixture"]
                    payload = json.loads(source_path.read_text(encoding="utf-8"))
                    mutated = apply_mutation(payload, case)
                    data_path = temp_root / f"{case['case_id']}.json"
                    data_path.write_text(json.dumps(mutated, ensure_ascii=False), encoding="utf-8")
                    issues = self.validator.validate_files(
                        SCHEMAS / SCHEMA_BY_FIXTURE[case["fixture"]],
                        data_path,
                    )
                    self.assertIn(case["expected_keyword"], {item.keyword for item in issues})


if __name__ == "__main__":
    unittest.main()
