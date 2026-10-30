"""Behavior tests for deterministic manuscript-story-architect scripts."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "tests" / "fixtures"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from render_reverse_outline import render_reverse_outline  # noqa: E402
from materialize_figure_sequence import materialize_figure_sequence  # noqa: E402
from schema_runtime import validate_schema  # noqa: E402
from story_artifact_checks import (  # noqa: E402
    check_artifact_links,
    check_section_coverage,
    validate_claim_map,
)


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def issue_codes(issues: list) -> set[str]:
    return {item.code for item in issues}


def resolve_all_author_states(value: object) -> None:
    """Convert the synthetic fixture into a fully resolved approval state."""
    if isinstance(value, dict):
        if "author_approval" in value:
            value["author_approval"] = "approved"
        if "decision_id" in value:
            value["status"] = "approved"
        if "gap_id" in value:
            value["status"] = "resolved"
        for child in value.values():
            resolve_all_author_states(child)
    elif isinstance(value, list):
        for child in value:
            resolve_all_author_states(child)


class StoryScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.claim_map = load_fixture("valid-claim-evidence-map.json")
        self.card = load_fixture("valid-interpretation-card.json")
        self.plan = load_fixture("valid-manuscript-plan.json")

    def add_secondary_claim_evidence(self) -> tuple[str, str]:
        """Add a valid second claim/evidence pair for cross-link mismatch tests."""
        claim_id = "claim:result-2"
        evidence_id = "evidence:cell-2"

        evidence = copy.deepcopy(self.claim_map["evidence_records"][0])
        evidence["evidence_id"] = evidence_id
        self.claim_map["evidence_records"].append(evidence)

        claim = copy.deepcopy(self.claim_map["claim_records"][0])
        claim["claim_id"] = claim_id
        claim["evidence_ids"] = [evidence_id]
        claim["claim_class"] = "secondary_result"
        self.claim_map["claim_records"].append(claim)

        link = copy.deepcopy(self.claim_map["claim_evidence_links"][0])
        link["link_id"] = "link:claim-2-evidence-2"
        link["claim_id"] = claim_id
        link["evidence_id"] = evidence_id
        self.claim_map["claim_evidence_links"].append(link)
        return claim_id, evidence_id

    def test_shared_schema_runtime_validates_claim_map(self) -> None:
        issues = validate_schema(
            ROOT / "schemas" / "claim-evidence-map.schema.json",
            FIXTURES / "valid-claim-evidence-map.json",
        )
        self.assertEqual([], issues)

    def test_valid_claim_map_semantics(self) -> None:
        self.assertEqual([], validate_claim_map(self.claim_map))

    def test_duplicate_claim_id_is_rejected(self) -> None:
        self.claim_map["claim_records"].append(copy.deepcopy(self.claim_map["claim_records"][0]))
        self.assertIn("duplicate_id", issue_codes(validate_claim_map(self.claim_map)))

    def test_claim_link_set_mismatch_is_rejected(self) -> None:
        self.claim_map["claim_records"][0]["evidence_ids"] = []
        self.assertIn("claim_link_set_mismatch", issue_codes(validate_claim_map(self.claim_map)))

    def test_supported_claim_requires_supports_relation(self) -> None:
        self.claim_map["claim_records"][0]["support_status"] = "supported"
        self.assertIn(
            "supported_without_supporting_link",
            issue_codes(validate_claim_map(self.claim_map)),
        )

    def test_valid_cross_artifact_links(self) -> None:
        self.assertEqual([], check_artifact_links(self.claim_map, [self.card], self.plan))

    def test_all_declared_relation_types_are_admissible_for_cross_links(self) -> None:
        cases = (
            ("supports", "supported"),
            ("partially_supports", "partially_supported"),
            ("conflicts", "conflicting"),
            ("context_only", "unsupported"),
            ("does_not_support", "unsupported"),
        )
        for relation, support_status in cases:
            with self.subTest(relation=relation):
                self.claim_map["claim_evidence_links"][0]["relation"] = relation
                self.claim_map["claim_records"][0]["support_status"] = support_status
                self.assertEqual([], check_artifact_links(self.claim_map, [self.card], self.plan))

    def test_key_claim_without_planned_interpretation_card_is_rejected(self) -> None:
        self.plan["interpretation_card_ids"] = []
        self.assertIn(
            "key_claim_missing_interpretation_card",
            issue_codes(check_artifact_links(self.claim_map, [self.card], self.plan)),
        )

    def test_card_evidence_unrelated_to_card_claim_is_rejected(self) -> None:
        _, evidence_id = self.add_secondary_claim_evidence()
        self.card["evidence_ids"] = [evidence_id]
        self.plan["evidence_assignment_audit"]["unassigned_evidence"].append(
            {
                "evidence_id": evidence_id,
                "reason": "outside_current_scope",
                "rationale": "Synthetic evidence retained outside the current plan.",
                "author_approval": "pending",
            }
        )
        self.assertIn(
            "card_evidence_not_linked_to_claim",
            issue_codes(check_artifact_links(self.claim_map, [self.card], self.plan)),
        )

    def test_paragraph_evidence_unrelated_to_every_paragraph_claim_is_rejected(self) -> None:
        _, evidence_id = self.add_secondary_claim_evidence()
        self.plan["section_plans"][0]["paragraph_plans"][0]["evidence_ids"].append(evidence_id)
        self.plan["evidence_assignment_audit"]["assigned_evidence_ids"].append(evidence_id)
        self.assertIn(
            "paragraph_evidence_not_linked_to_claim",
            issue_codes(check_artifact_links(self.claim_map, [self.card], self.plan)),
        )

    def test_paragraph_evidence_without_a_declared_claim_is_rejected(self) -> None:
        paragraph = self.plan["section_plans"][0]["paragraph_plans"][0]
        paragraph["claim_ids"] = []
        self.assertIn(
            "paragraph_evidence_not_linked_to_claim",
            issue_codes(check_artifact_links(self.claim_map, [self.card], self.plan)),
        )

    def test_figure_evidence_unrelated_to_every_figure_claim_is_rejected(self) -> None:
        _, evidence_id = self.add_secondary_claim_evidence()
        self.plan["figure_sequence"][0]["evidence_ids"].append(evidence_id)
        self.plan["evidence_assignment_audit"]["assigned_evidence_ids"].append(evidence_id)
        self.assertIn(
            "figure_evidence_not_linked_to_claim",
            issue_codes(check_artifact_links(self.claim_map, [self.card], self.plan)),
        )

    def test_key_boundary_from_unreferenced_card_is_rejected(self) -> None:
        extra_card = copy.deepcopy(self.card)
        extra_card["artifact_id"] = "interpretation-card:synthetic-2"
        extra_card["card_id"] = "card:interpretation-2"
        extra_card["boundary"]["boundary_id"] = "boundary:interpretation-2"
        self.plan["story_anchors"]["key_boundary_ids"] = ["boundary:interpretation-2"]
        codes = issue_codes(check_artifact_links(self.claim_map, [self.card, extra_card], self.plan))
        self.assertIn("key_boundary_not_from_planned_card", codes)
        self.assertNotIn("unknown_key_boundary", codes)

    def test_unknown_key_boundary_is_rejected(self) -> None:
        self.plan["story_anchors"]["key_boundary_ids"] = ["boundary:unknown"]
        self.assertIn(
            "unknown_key_boundary",
            issue_codes(check_artifact_links(self.claim_map, [self.card], self.plan)),
        )

    def test_every_evidence_record_must_appear_in_assignment_audit(self) -> None:
        extra = copy.deepcopy(self.claim_map["evidence_records"][0])
        extra["evidence_id"] = "evidence:cell-unassigned"
        self.claim_map["evidence_records"].append(extra)
        self.assertIn(
            "evidence_missing_from_audit",
            issue_codes(check_artifact_links(self.claim_map, [self.card], self.plan)),
        )

    def test_evidence_marked_assigned_must_have_real_plan_assignment(self) -> None:
        extra = copy.deepcopy(self.claim_map["evidence_records"][0])
        extra["evidence_id"] = "evidence:cell-declared-only"
        self.claim_map["evidence_records"].append(extra)
        self.plan["evidence_assignment_audit"]["assigned_evidence_ids"].append(
            "evidence:cell-declared-only"
        )
        self.assertIn(
            "evidence_marked_assigned_but_unused",
            issue_codes(check_artifact_links(self.claim_map, [self.card], self.plan)),
        )

    def test_evidence_used_in_plan_must_be_marked_assigned(self) -> None:
        self.plan["evidence_assignment_audit"] = {
            "assigned_evidence_ids": [],
            "unassigned_evidence": [
                {
                    "evidence_id": "evidence:cell-1",
                    "reason": "unresolved",
                    "rationale": "Negative fixture: the evidence is still used in the plan.",
                    "author_approval": "pending",
                }
            ],
        }
        self.assertIn(
            "evidence_used_but_not_marked_assigned",
            issue_codes(check_artifact_links(self.claim_map, [self.card], self.plan)),
        )

    def test_unresolved_unassigned_evidence_is_allowed_before_final_approval(self) -> None:
        extra = copy.deepcopy(self.claim_map["evidence_records"][0])
        extra["evidence_id"] = "evidence:cell-unresolved"
        self.claim_map["evidence_records"].append(extra)
        self.plan["evidence_assignment_audit"]["unassigned_evidence"].append(
            {
                "evidence_id": "evidence:cell-unresolved",
                "reason": "unresolved",
                "rationale": "The author has not yet assigned or excluded this evidence.",
                "author_approval": "pending",
            }
        )
        self.assertEqual([], check_artifact_links(self.claim_map, [self.card], self.plan))

    def test_duplicate_section_and_paragraph_ids_are_rejected(self) -> None:
        duplicate_section = copy.deepcopy(self.plan["section_plans"][0])
        self.plan["section_plans"].append(duplicate_section)
        codes = issue_codes(check_artifact_links(self.claim_map, [self.card], self.plan))
        self.assertIn("duplicate_id", codes)
        self.assertIn("duplicate_paragraph_id", codes)

    def test_duplicate_figure_id_and_order_are_rejected(self) -> None:
        self.plan["figure_sequence"].append(copy.deepcopy(self.plan["figure_sequence"][0]))
        codes = issue_codes(check_artifact_links(self.claim_map, [self.card], self.plan))
        self.assertIn("duplicate_id", codes)
        self.assertIn("duplicate_figure_order", codes)

    def test_figure_materializer_groups_claim_centric_rows_without_invention(self) -> None:
        proposals = [
            {
                "figure_id": "figure:5",
                "order": 5,
                "purpose": "Purpose A",
                "claim_ids": ["claim:a"],
                "evidence_ids": ["evidence:a"],
                "author_approval": "pending",
            },
            {
                "figure_id": "figure:5",
                "order": 6,
                "purpose": "Purpose B",
                "claim_ids": ["claim:b", "claim:a"],
                "evidence_ids": ["evidence:b", "evidence:a"],
                "author_approval": "pending",
            },
        ]
        sequence, receipt = materialize_figure_sequence(
            proposals,
            allowed_figure_ids=["figure:5"],
            allowed_claim_ids=["claim:a", "claim:b", "claim:c"],
            allowed_evidence_ids=["evidence:a", "evidence:b", "evidence:c"],
        )
        self.assertEqual(1, len(sequence))
        self.assertEqual(["claim:a", "claim:b"], sequence[0]["claim_ids"])
        self.assertEqual(["evidence:a", "evidence:b"], sequence[0]["evidence_ids"])
        self.assertNotIn("claim:c", sequence[0]["claim_ids"])
        self.assertNotIn("evidence:c", sequence[0]["evidence_ids"])
        self.assertEqual("Purpose A | Purpose B", sequence[0]["purpose"])
        self.assertFalse(receipt["scientific_associations_added"])

    def test_figure_materializer_rejects_unknown_ids(self) -> None:
        proposal = [{
            "figure_id": "figure:5",
            "order": 1,
            "purpose": "Purpose",
            "claim_ids": ["claim:unknown"],
            "evidence_ids": ["evidence:a"],
            "author_approval": "pending",
        }]
        with self.assertRaisesRegex(ValueError, "unknown IDs"):
            materialize_figure_sequence(
                proposal,
                allowed_figure_ids=["figure:5"],
                allowed_claim_ids=["claim:a"],
                allowed_evidence_ids=["evidence:a"],
            )

    def test_figure_materializer_rejects_conflicting_approval_states(self) -> None:
        base = {
            "figure_id": "figure:5",
            "order": 1,
            "purpose": "Purpose",
            "claim_ids": ["claim:a"],
            "evidence_ids": ["evidence:a"],
        }
        proposals = [
            {**base, "author_approval": "pending"},
            {**base, "order": 2, "author_approval": "approved"},
        ]
        with self.assertRaisesRegex(ValueError, "conflicting author_approval"):
            materialize_figure_sequence(
                proposals,
                allowed_figure_ids=["figure:5"],
                allowed_claim_ids=["claim:a"],
                allowed_evidence_ids=["evidence:a"],
            )

    def test_author_approved_plan_cannot_retain_pending_anchors(self) -> None:
        self.plan["status"] = "author_approved"
        self.plan["approval_summary"].update(
            {"overall_status": "approved", "pending_decision_count": 0, "open_blocker_count": 0}
        )
        codes = issue_codes(check_artifact_links(self.claim_map, [self.card], self.plan))
        self.assertIn("approved_plan_has_unapproved_anchor", codes)
        self.assertIn("approved_plan_has_unapproved_sources", codes)
        self.assertIn("approved_artifact_has_unapproved_child", codes)
        self.assertIn("approved_plan_has_unresolved_decision", codes)
        self.assertIn("approved_plan_has_unresolved_gap", codes)

    def test_fully_resolved_author_approved_artifacts_pass(self) -> None:
        for artifact in (self.claim_map, self.card, self.plan):
            resolve_all_author_states(artifact)
            artifact["status"] = "author_approved"
        self.plan["approval_summary"].update(
            {"overall_status": "approved", "pending_decision_count": 0, "open_blocker_count": 0}
        )
        self.assertEqual([], check_artifact_links(self.claim_map, [self.card], self.plan))

    def test_author_approved_plan_cannot_retain_unresolved_evidence(self) -> None:
        extra = copy.deepcopy(self.claim_map["evidence_records"][0])
        extra["evidence_id"] = "evidence:cell-unresolved"
        self.claim_map["evidence_records"].append(extra)
        self.plan["evidence_assignment_audit"]["unassigned_evidence"].append(
            {
                "evidence_id": "evidence:cell-unresolved",
                "reason": "unresolved",
                "rationale": "The record remains scientifically unresolved.",
                "author_approval": "pending",
            }
        )
        for artifact in (self.claim_map, self.card, self.plan):
            resolve_all_author_states(artifact)
            artifact["status"] = "author_approved"
        self.plan["approval_summary"].update(
            {"overall_status": "approved", "pending_decision_count": 0, "open_blocker_count": 0}
        )
        self.assertEqual(
            {"approved_plan_has_unresolved_evidence"},
            issue_codes(check_artifact_links(self.claim_map, [self.card], self.plan)),
        )

    def test_valid_section_coverage(self) -> None:
        issues, summary = check_section_coverage(self.claim_map, self.plan)
        self.assertEqual([], issues)
        self.assertEqual(1, summary["key_claim_count"])
        self.assertEqual(2, summary["section_count"])

    def test_key_claim_missing_from_paragraphs_is_rejected(self) -> None:
        for section in self.plan["section_plans"]:
            section["claim_ids"] = []
            for paragraph in section["paragraph_plans"]:
                paragraph["claim_ids"] = []
        codes = issue_codes(check_section_coverage(self.claim_map, self.plan)[0])
        self.assertIn("key_claim_missing_from_sections", codes)
        self.assertIn("key_claim_missing_from_paragraphs", codes)

    def test_reverse_outline_renders_ids_without_source_prose(self) -> None:
        rendered = render_reverse_outline(self.plan)
        self.assertIn("`paragraph:results-1`", rendered)
        self.assertIn("`claim:result-1`", rendered)
        self.assertIn("## Evidence assignment audit", rendered)

    def test_notes_only_reverse_outline_declares_skip(self) -> None:
        self.plan["current_structure_assessment"] = {
            "input_mode": "structured_notes",
            "skipped_reason": "no_existing_manuscript_structure_to_reverse_outline",
        }
        rendered = render_reverse_outline(self.plan)
        self.assertIn("Reverse outline skipped", rendered)
        self.assertIn("no_existing_manuscript_structure_to_reverse_outline", rendered)


if __name__ == "__main__":
    unittest.main()
