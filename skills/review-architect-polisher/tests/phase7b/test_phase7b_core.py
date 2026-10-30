"""Behavioral contract tests for Phase 7B core candidate 0.1.6."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent.parent
for path in (SKILL_ROOT / "scripts",):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import fixture_factory as fixtures  # noqa: E402
from apply_review_revision_proposal import (  # noqa: E402
    PatchApplicationError,
    apply_review_revision_proposal,
)
from build_review_change_inventory import (  # noqa: E402
    artifact_identity,
    build_inventory,
    build_lineage_map,
    canonical_sha256,
    citation_occurrences,
    payload_sha256,
    refresh_document,
)
from validate_review_revision_package import (  # noqa: E402
    permission_payload_sha256,
    validate_admission,
    validate_revision_package,
)


def admission_codes(case: dict) -> set[str]:
    return {
        issue["code"]
        for issue in validate_admission(
            case["source"], case["permission"], case["expected_permission_sha256"],
            case["proposal"], case["phase7a"], case.get("review_profile"),
        )
    }


def apply_case(case: dict) -> dict:
    return apply_review_revision_proposal(
        case["source"], case["permission"], case["expected_permission_sha256"],
        case["proposal"], case["phase7a"], case.get("review_profile"),
    )


def final_codes(case: dict, artifacts: dict) -> set[str]:
    return {
        issue["code"]
        for issue in validate_revision_package(
            case["source"], artifacts["candidate-review.json"], case["permission"],
            case["expected_permission_sha256"], case["proposal"],
            artifacts["review-change-manifest.json"], artifacts["review-author-query-list.json"],
            artifacts["review-revision-lineage-map.json"], artifacts["review-protected-change-inventory.json"],
            case["phase7a"], case.get("review_profile"),
        )
    }


def cited_light_case(source_text: str, candidate_text: str) -> dict:
    case = fixtures.light_case()
    source = case["source"]
    source["units"][0]["sentences"][0]["text"] = source_text
    refresh_document(source)
    target = source["units"][0]
    operation = case["proposal"]["operations"][0]
    operation["target_unit_ids"] = [target["unit_id"]]
    operation["expected_targets"] = fixtures._expected_targets(source, [target["unit_id"]])
    operation["replacement_units"] = [fixtures.replacement_from_unit(target)]
    operation["replacement_units"][0]["sentences"][0]["text"] = candidate_text
    case["permission"]["source_artifact"] = artifact_identity(source)
    case["proposal"]["source_artifact"] = artifact_identity(source)
    fixtures.refresh_permission_and_binding(case)
    return case


def citation_relocation_case(mode: str) -> dict:
    """Move one unchanged citation between same-paragraph sentence lineages."""
    case = fixtures.light_case() if mode == "light" else fixtures.medium_case()
    source = case["source"]
    target = source["units"][0]
    target["sentences"][0]["text"] = "Evidence was reported [1,2]."
    target["sentences"][0]["claim_ids"] = ["claim-response"]
    target["sentences"][0]["citation_relation_ids"] = ["relation-response"]
    target["sentences"][1]["text"] = "This statement describes the admitted evidence."
    target["sentences"][1]["claim_ids"] = ["claim-response"]
    target["sentences"][1]["citation_relation_ids"] = []
    refresh_document(source)

    replacement = fixtures.replacement_from_unit(target)
    replacement["sentences"][0]["text"] = "Evidence was reported."
    replacement["sentences"][0]["claim_ids"] = ["claim-response"]
    replacement["sentences"][0]["citation_relation_ids"] = []
    replacement["sentences"][1]["text"] = "This statement describes the admitted evidence [1,2]."
    replacement["sentences"][1]["claim_ids"] = ["claim-response"]
    replacement["sentences"][1]["citation_relation_ids"] = ["relation-response"]

    operation = case["proposal"]["operations"][0]
    operation["target_unit_ids"] = [target["unit_id"]]
    operation["expected_targets"] = fixtures._expected_targets(source, [target["unit_id"]])
    operation["replacement_units"] = [replacement]
    case["permission"]["source_artifact"] = artifact_identity(source)
    case["permission"]["revision_mode"] = mode
    case["proposal"]["source_artifact"] = artifact_identity(source)
    case["proposal"]["revision_mode"] = mode
    fixtures.refresh_permission_and_binding(case)
    return case


class Phase7BCoreTests(unittest.TestCase):
    def test_01_light_positive(self) -> None:
        case = fixtures.light_case()
        artifacts = apply_case(case)
        self.assertEqual(final_codes(case, artifacts), set())

    def test_02_medium_positive(self) -> None:
        case = fixtures.medium_case()
        artifacts = apply_case(case)
        self.assertTrue(artifacts["review-protected-change-inventory.json"]["structural_footprint"]["sentence_order_changed"])

    def test_03_deep_positive(self) -> None:
        case = fixtures.deep_move_case()
        artifacts = apply_case(case)
        self.assertTrue(artifacts["review-protected-change-inventory.json"]["structural_footprint"]["paragraph_order_changed"])

    def test_04_authorized_draft_slot_positive(self) -> None:
        case = fixtures.draft_case()
        artifacts = apply_case(case)
        protected = {(item["protected_class"], item["identity"]) for item in artifacts["review-protected-change-inventory.json"]["protected_changes"]}
        self.assertEqual(protected, {("citation", "numeric_bracket:[1,2]"), ("terminology", "response")})

    def test_05_permission_content_change_without_rehash_rejected(self) -> None:
        case = fixtures.light_case()
        case["permission"]["created_by"] = "tampered"
        self.assertIn("permission:hash", admission_codes(case))

    def test_06_forged_embedded_permission_hash_rejected(self) -> None:
        case = fixtures.light_case()
        case["permission"]["permission_sha256"] = "0" * 64
        self.assertIn("permission:hash", admission_codes(case))

    def test_07_caller_expected_permission_hash_mismatch_rejected(self) -> None:
        case = fixtures.light_case()
        case["expected_permission_sha256"] = "f" * 64
        self.assertIn("permission:expected_hash", admission_codes(case))

    def test_08_self_produced_permission_rejected(self) -> None:
        case = fixtures.light_case()
        case["permission"]["creator_role"] = "module04"
        fixtures.refresh_permission_and_binding(case)
        self.assertIn("permission:self_produced", admission_codes(case))

    def test_09_calling_workflow_cannot_mint_author_approved(self) -> None:
        case = fixtures.light_case()
        case["permission"]["authorization_state"] = "author_approved"
        fixtures.refresh_permission_and_binding(case)
        self.assertIn("permission:origin", admission_codes(case))

    def test_10_machine_proposed_permission_rejected(self) -> None:
        case = fixtures.light_case()
        case["permission"]["authorization_state"] = "machine_proposed"
        fixtures.refresh_permission_and_binding(case)
        self.assertIn("permission:state", admission_codes(case))

    def test_11_extra_permission_field_rejected_by_schema(self) -> None:
        case = fixtures.light_case()
        case["permission"]["uncontracted_authority"] = True
        fixtures.refresh_permission_and_binding(case)
        self.assertIn("schema:additionalProperties", admission_codes(case))

    def test_12_non_review_source_rejected(self) -> None:
        case = fixtures.light_case()
        case["source"]["document_type"] = "original_article"
        refresh_document(case["source"])
        self.assertIn("source:invalid", admission_codes(case))

    def test_13_scoping_route_rejected(self) -> None:
        case = fixtures.light_case()
        case["permission"]["review_type"] = "scoping_style_review"
        fixtures.refresh_permission_and_binding(case)
        self.assertIn("routing:review_only", admission_codes(case))

    def test_14_source_identity_mismatch_rejected(self) -> None:
        case = fixtures.light_case()
        case["permission"]["source_artifact"]["artifact_sha256"] = "0" * 64
        fixtures.refresh_permission_and_binding(case)
        self.assertIn("permission:source_binding", admission_codes(case))

    def test_15_phase7a_binding_mismatch_rejected(self) -> None:
        case = fixtures.light_case()
        case["permission"]["phase7a_closure"]["outline"]["artifact_sha256"] = "0" * 64
        fixtures.refresh_permission_and_binding(case)
        self.assertIn("permission:phase7a_binding", admission_codes(case))

    def test_16_invalid_phase7a_closure_rejected(self) -> None:
        case = fixtures.light_case()
        case["phase7a"]["outline"]["terminal_state"] = "blocked"
        case["phase7a"] = fixtures.PHASE7A_FACTORY.rehash_package(case["phase7a"])
        case["permission"]["phase7a_closure"] = fixtures._phase7a_refs(case["phase7a"])
        fixtures.refresh_permission_and_binding(case)
        self.assertTrue(any(code.startswith("phase7a:") for code in admission_codes(case)))

    def test_17_stale_target_hash_rejected(self) -> None:
        case = fixtures.light_case()
        case["proposal"]["operations"][0]["expected_targets"][0]["unit_sha256"] = "0" * 64
        fixtures.refresh_proposal(case["proposal"])
        self.assertIn("proposal:stale_target", admission_codes(case))

    def test_18_duplicate_target_overlap_rejected(self) -> None:
        case = fixtures.light_case()
        second = fixtures.clone(case["proposal"]["operations"][0])
        second["operation_id"] = "review-operation-light-2"
        second["operation_order"] = 2
        case["proposal"]["operations"].append(second)
        fixtures.refresh_proposal(case["proposal"])
        self.assertIn("proposal:overlap", admission_codes(case))

    def test_19_blocking_query_prevents_affected_change(self) -> None:
        case = fixtures.light_case()
        case["proposal"]["unresolved_queries"] = [{
            "query_id": "query-1", "query_type": "citation_support", "question": "Is support adequate?",
            "affected_unit_ids": ["review-unit-2"], "blocks_revision": True, "status": "unresolved",
        }]
        fixtures.refresh_proposal(case["proposal"])
        self.assertIn("query:blocking", admission_codes(case))

    def test_20_unrelated_blocking_query_may_continue(self) -> None:
        case = fixtures.light_case()
        case["proposal"]["unresolved_queries"] = [{
            "query_id": "query-1", "query_type": "citation_support", "question": "Is support adequate?",
            "affected_unit_ids": ["review-unit-1"], "blocks_revision": True, "status": "unresolved",
        }]
        fixtures.refresh_proposal(case["proposal"])
        self.assertEqual(admission_codes(case), set())

    def test_21_deep_operation_requires_permission_decision(self) -> None:
        case = fixtures.deep_move_case()
        case["permission"]["authorized_decisions"] = []
        fixtures.refresh_permission_and_binding(case)
        self.assertIn("permission:missing_decision", admission_codes(case))

    def test_22_pending_deep_decision_rejected(self) -> None:
        case = fixtures.deep_move_case()
        case["permission"]["authorized_decisions"][0]["authorization_state"] = "pending"
        fixtures.refresh_permission_and_binding(case)
        codes = admission_codes(case)
        self.assertTrue("schema:const" in codes or "permission:decision_compatibility" in codes)

    def test_23_incompatible_decision_tuple_rejected(self) -> None:
        case = fixtures.deep_move_case()
        decision = case["permission"]["authorized_decisions"][0]
        decision["decision_type"] = "review_draft_slot_materialization"
        fixtures.refresh_permission_and_binding(case)
        self.assertIn("permission:decision_compatibility", admission_codes(case))

    def test_24_governed_subject_hash_mismatch_rejected(self) -> None:
        case = fixtures.deep_move_case()
        case["permission"]["authorized_decisions"][0]["governed_subject_sha256"] = "0" * 64
        fixtures.refresh_permission_and_binding(case)
        self.assertIn("permission:governed_subject", admission_codes(case))

    def test_25_unrelated_governed_subject_rejected(self) -> None:
        case = fixtures.deep_move_case()
        decision = case["permission"]["authorized_decisions"][0]
        other = case["source"]["units"][0]
        decision["governed_subject_id"] = other["unit_id"]
        decision["governed_subject_sha256"] = fixtures.governed_subject_sha256(other)
        fixtures.refresh_permission_and_binding(case)
        self.assertIn("permission:decision_subject_scope", admission_codes(case))

    def test_26_decision_operation_mismatch_rejected(self) -> None:
        case = fixtures.deep_move_case()
        case["permission"]["authorized_decisions"][0]["allowed_operation"] = "paragraph_split"
        fixtures.refresh_permission_and_binding(case)
        self.assertIn("permission:decision_operation", admission_codes(case))

    def test_27_operation_phase7a_closure_mismatch_rejected(self) -> None:
        case = fixtures.light_case()
        case["proposal"]["operations"][0]["phase7a_closure"]["gap_ids"] = []
        fixtures.refresh_proposal(case["proposal"])
        self.assertIn("phase7a:operation_closure", admission_codes(case))

    def test_28_article_profile_rejected(self) -> None:
        case = fixtures.light_case()
        fixtures.bind_profile(case, fixtures.review_profile_artifact(corpus_type="original_article"))
        self.assertIn("profile:route", admission_codes(case))

    def test_29_valid_review_profile_allowed(self) -> None:
        case = fixtures.light_case()
        fixtures.bind_profile(case, fixtures.review_profile_artifact())
        self.assertEqual(admission_codes(case), set())

    def test_30_light_sentence_reorder_rejected_by_observed_footprint(self) -> None:
        case = fixtures.medium_case()
        case["permission"]["revision_mode"] = "light"
        case["proposal"]["revision_mode"] = "light"
        fixtures.refresh_permission_and_binding(case)
        with self.assertRaises(PatchApplicationError):
            apply_case(case)

    def test_31_ordinary_citation_addition_rejected(self) -> None:
        case = fixtures.light_case()
        case["proposal"]["operations"][0]["replacement_units"][0]["sentences"][0]["text"] += " [3]"
        fixtures.refresh_proposal(case["proposal"])
        with self.assertRaises(PatchApplicationError):
            apply_case(case)

    def test_32_causal_strengthening_rejected(self) -> None:
        case = fixtures.light_case()
        case["proposal"]["operations"][0]["replacement_units"][0]["sentences"][0]["text"] = "The evidence base causes the response."
        fixtures.refresh_proposal(case["proposal"])
        with self.assertRaises(PatchApplicationError):
            apply_case(case)

    def test_33_citation_relation_change_rejected(self) -> None:
        case = fixtures.medium_case()
        sentence = next(item for item in case["proposal"]["operations"][0]["replacement_units"][0]["sentences"] if "[1,2]" in item["text"])
        sentence["citation_relation_ids"] = []
        fixtures.refresh_proposal(case["proposal"])
        with self.assertRaises(PatchApplicationError):
            apply_case(case)

    def test_34_unallowlisted_draft_token_rejected(self) -> None:
        case = fixtures.draft_case()
        case["proposal"]["operations"][0]["replacement_units"][0]["sentences"][0]["text"] += " 3"
        fixtures.refresh_proposal(case["proposal"])
        with self.assertRaises(PatchApplicationError):
            apply_case(case)

    def test_35_missing_required_draft_materialization_rejected(self) -> None:
        case = fixtures.draft_case()
        case["proposal"]["operations"][0]["replacement_units"][0]["sentences"][0]["text"] = "Both admitted sources describe the outcome [1,2]."
        fixtures.refresh_proposal(case["proposal"])
        with self.assertRaises(PatchApplicationError):
            apply_case(case)

    def test_36_model_declared_lineage_rejected(self) -> None:
        case = fixtures.light_case()
        artifacts = apply_case(case)
        lineage = artifacts["review-revision-lineage-map.json"]
        lineage["origin"] = "model_declared"
        lineage["artifact_sha256"] = payload_sha256(lineage, "artifact_sha256")
        self.assertIn("lineage:untrusted", final_codes(case, artifacts))

    def test_37_orphan_lineage_rejected(self) -> None:
        case = fixtures.light_case()
        artifacts = apply_case(case)
        row = artifacts["review-revision-lineage-map.json"]["unit_lineage"][0]
        row["source_unit_ids"] = []
        row["authorized_draft_slot_ids"] = []
        lineage = artifacts["review-revision-lineage-map.json"]
        lineage["artifact_sha256"] = payload_sha256(lineage, "artifact_sha256")
        self.assertIn("lineage:orphan", final_codes(case, artifacts))

    def test_38_inventory_tamper_rejected(self) -> None:
        case = fixtures.light_case()
        artifacts = apply_case(case)
        artifacts["review-protected-change-inventory.json"]["changed_units"] = []
        artifacts["review-protected-change-inventory.json"]["artifact_sha256"] = payload_sha256(artifacts["review-protected-change-inventory.json"], "artifact_sha256")
        self.assertIn("inventory:mismatch", final_codes(case, artifacts))

    def test_39_manifest_omission_rejected(self) -> None:
        case = fixtures.light_case()
        artifacts = apply_case(case)
        manifest = artifacts["review-change-manifest.json"]
        manifest["changes"] = []
        manifest["artifact_sha256"] = payload_sha256(manifest, "artifact_sha256")
        self.assertIn("manifest:coverage", final_codes(case, artifacts))

    def test_40_fake_module06_admission_rejected(self) -> None:
        case = fixtures.light_case()
        artifacts = apply_case(case)
        manifest = artifacts["review-change-manifest.json"]
        manifest["module06_handoff"] = {"interface_name": "module06_review_revision_admission", "interface_version": "0.1.0", "state": "passed"}
        manifest["artifact_sha256"] = payload_sha256(manifest, "artifact_sha256")
        self.assertIn("manifest:h04", final_codes(case, artifacts))

    def test_41_scientific_correctness_overclaim_rejected(self) -> None:
        case = fixtures.light_case()
        artifacts = apply_case(case)
        manifest = artifacts["review-change-manifest.json"]
        manifest["scientific_correctness_claimed"] = True
        manifest["artifact_sha256"] = payload_sha256(manifest, "artifact_sha256")
        self.assertIn("manifest:overclaim", final_codes(case, artifacts))

    def test_42_candidate_identity_tamper_rejected(self) -> None:
        case = fixtures.light_case()
        artifacts = apply_case(case)
        artifacts["candidate-review.json"]["artifact_sha256"] = "0" * 64
        codes = final_codes(case, artifacts)
        self.assertTrue("candidate:invalid" in codes or "lineage:candidate_binding" in codes)

    def test_43_candidate_slot_registry_tamper_rejected(self) -> None:
        case = fixtures.light_case()
        artifacts = apply_case(case)
        artifacts["candidate-review.json"]["authorized_empty_draft_slots"] = []
        refresh_document(artifacts["candidate-review.json"])
        self.assertIn("candidate:slot_registry", final_codes(case, artifacts))

    def test_44_permission_decision_cannot_use_phase7a_authority_record(self) -> None:
        case = fixtures.deep_move_case()
        decision = case["permission"]["authorized_decisions"][0]
        decision["decision_type"] = "outline_decision"
        fixtures.refresh_permission_and_binding(case)
        codes = admission_codes(case)
        self.assertTrue("schema:enum" in codes or "permission:decision_compatibility" in codes)

    def test_45_lineage_and_inventory_are_deterministic(self) -> None:
        case = fixtures.light_case()
        artifacts = apply_case(case)
        candidate = artifacts["candidate-review.json"]
        lineage = build_lineage_map(case["source"], candidate, origin="deterministic_patch_layer")
        inventory = build_inventory(case["source"], candidate, lineage)
        self.assertEqual(lineage, artifacts["review-revision-lineage-map.json"])
        self.assertEqual(inventory, artifacts["review-protected-change-inventory.json"])

    def test_46_author_year_citation_identity_substitution_rejected(self) -> None:
        case = cited_light_case(
            "Both admitted sources report a response (Smith, 2025; Jones, 2026).",
            "Both admitted sources report a response (Taylor, 2025; Jones, 2026).",
        )
        with self.assertRaises(PatchApplicationError):
            apply_case(case)

    def test_47_deep_wrong_affected_paragraph_id_rejected(self) -> None:
        case = fixtures.deep_move_case()
        case["permission"]["authorized_decisions"][0]["affected_paragraph_ids"] = ["paragraph:invented"]
        fixtures.refresh_permission_and_binding(case)
        self.assertIn("permission:decision_paragraphs", admission_codes(case))

    def test_48_deep_wrong_affected_section_id_rejected(self) -> None:
        case = fixtures.deep_move_case()
        case["permission"]["authorized_decisions"][0]["affected_section_ids"] = ["section:invented"]
        fixtures.refresh_permission_and_binding(case)
        self.assertIn("permission:decision_sections", admission_codes(case))

    def test_49_draft_slot_blocking_query_rejected(self) -> None:
        case = fixtures.draft_case()
        case["proposal"]["unresolved_queries"] = [{
            "query_id": "query-slot-1",
            "query_type": "citation_support",
            "question": "Is citation support for this draft slot resolved?",
            "affected_unit_ids": ["review-slot-future-1"],
            "blocks_revision": True,
            "status": "unresolved",
        }]
        fixtures.refresh_proposal(case["proposal"])
        self.assertIn("query:blocking", admission_codes(case))

    def test_50_changed_cited_sentence_emits_bound_warning(self) -> None:
        case = cited_light_case(
            "Both admitted sources report a response [1,2].",
            "Both admitted sources describe a response [1,2].",
        )
        warnings = apply_case(case)["review-change-manifest.json"]["citation_support_warnings"]
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["citation_identity"], "numeric_bracket:[1,2]")
        self.assertEqual(warnings[0]["synthesis_relation_id"], "relation-response")
        self.assertEqual(warnings[0]["source_ids"], ["source-1", "source-2"])

    def test_51_manifest_missing_per_change_risk_rejected(self) -> None:
        case = fixtures.light_case()
        artifacts = apply_case(case)
        del artifacts["review-change-manifest.json"]["changes"][0]["risk_class"]
        manifest = artifacts["review-change-manifest.json"]
        manifest["artifact_sha256"] = payload_sha256(manifest, "artifact_sha256")
        self.assertIn("manifest:change_evidence", final_codes(case, artifacts))

    def test_52_permission_protected_anchor_requires_operation_binding(self) -> None:
        case = fixtures.light_case()
        case["permission"]["protected_anchor_ids"] = ["protected-anchor:citation-1"]
        fixtures.refresh_permission_and_binding(case)
        self.assertIn("proposal:protected_anchor_coverage", admission_codes(case))

    def test_53_permission_protected_anchor_exact_binding_passes(self) -> None:
        case = fixtures.light_case()
        case["permission"]["protected_anchor_ids"] = ["protected-anchor:citation-1"]
        case["proposal"]["operations"][0]["affected_protected_anchor_ids"] = ["protected-anchor:citation-1"]
        fixtures.refresh_permission_and_binding(case)
        self.assertEqual(admission_codes(case), set())

    def test_54_invented_review_profile_rejected_without_exact_artifact(self) -> None:
        case = fixtures.light_case()
        case["proposal"]["profile_alignment"] = {
            "profile_id": "profile:invented", "profile_version": "9.9.9", "profile_sha256": "a" * 64,
            "document_type": "review_article", "corpus_type": "review_only", "review_state": "reviewed",
            "stale": False, "feature_id": "feature:invented", "support_locator": "support:invented",
        }
        fixtures.refresh_proposal(case["proposal"])
        self.assertIn("profile:missing_artifact", admission_codes(case))

    def test_55_superscript_citation_families_are_typed(self) -> None:
        rows = citation_occurrences("Evidence<sup>1,2</sup> and confirmation³–⁵ were reported.")
        self.assertEqual(
            {(row["citation_style"], row["identity"]) for row in rows},
            {("html_superscript", "numeric_superscript:1,2"), ("unicode_superscript", "numeric_superscript:3-5")},
        )

    def test_56_ampersand_multi_author_substitution_rejected(self) -> None:
        case = cited_light_case(
            "Both sources agree (Smith & Jones, 2025).",
            "Both sources agree (Taylor & Jones, 2025).",
        )
        with self.assertRaises(PatchApplicationError):
            apply_case(case)

    def test_57_and_multi_author_substitution_rejected(self) -> None:
        case = cited_light_case(
            "Both sources agree (Smith and Jones, 2025).",
            "Both sources agree (Taylor and Jones, 2025).",
        )
        with self.assertRaises(PatchApplicationError):
            apply_case(case)

    def test_58_narrative_multi_author_substitution_rejected(self) -> None:
        case = cited_light_case(
            "Smith and Jones (2025) reported agreement.",
            "Taylor and Jones (2025) reported agreement.",
        )
        with self.assertRaises(PatchApplicationError):
            apply_case(case)

    def test_59_range_dash_is_formatting_only(self) -> None:
        case = cited_light_case(
            "Evidence was reported [1-3].",
            "Evidence was reported [1–3].",
        )
        artifacts = apply_case(case)
        changes = artifacts["review-protected-change-inventory.json"]["protected_changes"]
        formatting = [item for item in changes if item["delta_type"] == "formatting_only"]
        self.assertEqual(len(formatting), 1)
        self.assertEqual(formatting[0]["identity"], "numeric_bracket:[1-3]")
        self.assertEqual((formatting[0]["source_token"], formatting[0]["candidate_token"]), ("[1-3]", "[1–3]"))
        self.assertEqual(final_codes(case, artifacts), set())

    def test_60_citation_whitespace_is_formatting_only(self) -> None:
        case = cited_light_case(
            "Evidence was reported [1, 2].",
            "Evidence was reported [1,2].",
        )
        artifacts = apply_case(case)
        formatting = [
            item for item in artifacts["review-protected-change-inventory.json"]["protected_changes"]
            if item["delta_type"] == "formatting_only"
        ]
        self.assertEqual(len(formatting), 1)
        self.assertEqual(formatting[0]["identity"], "numeric_bracket:[1,2]")
        self.assertEqual((formatting[0]["source_token"], formatting[0]["candidate_token"]), ("[1, 2]", "[1,2]"))

    def test_61_equivalent_superscript_representations_are_formatting_only(self) -> None:
        case = cited_light_case(
            "Evidence was reported <sup>1,2</sup>.",
            "Evidence was reported ¹,².",
        )
        artifacts = apply_case(case)
        formatting = [
            item for item in artifacts["review-protected-change-inventory.json"]["protected_changes"]
            if item["delta_type"] == "formatting_only"
        ]
        self.assertEqual(len(formatting), 1)
        self.assertEqual(formatting[0]["identity"], "numeric_superscript:1,2")

    def test_62_unresolved_author_year_like_syntax_fails_closed(self) -> None:
        case = cited_light_case(
            "Both sources agree (Smith, Jones, and Taylor, 2025).",
            "Both sources remain aligned (Smith, Jones, and Taylor, 2025).",
        )
        self.assertIn("source:invalid", admission_codes(case))
        with self.assertRaises(PatchApplicationError):
            apply_case(case)

    def test_63_supported_author_year_forms_have_complete_identity(self) -> None:
        text = (
            "(Smith, 2025); (Smith et al., 2025); (Smith & Jones, 2025); "
            "(Smith and Jones, 2025); Smith (2025); Smith et al. (2025); "
            "Smith & Jones (2025); Smith and Jones (2025); "
            "(Smith, 2025; Jones, 2026); de Vries and van der Waals (2025)."
        )
        rows = citation_occurrences(text)
        self.assertEqual(len(rows), 10)
        identities = [row["identity"] for row in rows]
        self.assertIn("author_year:smith&jones,2025", identities)
        self.assertIn("author_year:de vries&van der waals,2025", identities)

    def test_64_unsupported_page_locator_and_year_group_forms_fail_closed(self) -> None:
        forms = (
            "Both sources agree (Smith, 2025, p. 3).",
            "Both sources agree (Smith, 2025, pp. 3–5).",
            "Both sources agree (Smith, 2025: 3).",
            "Smith (2025, p. 3) reported agreement.",
            "Smith and Jones (2025, p. 3) reported agreement.",
            "Both sources agree (Smith et al., 2025a,b).",
            "Smith et al. (2025a,b) reported agreement.",
        )
        for text in forms:
            with self.subTest(text=text):
                case = cited_light_case(text, text.replace("agree", "remain aligned"))
                self.assertIn("source:invalid", admission_codes(case))

    def test_65_light_within_sentence_citation_relocation_rejected(self) -> None:
        case = cited_light_case(
            "Evidence was reported [1,2].",
            "[1,2] Evidence was reported.",
        )
        with self.assertRaisesRegex(PatchApplicationError, "mode:citation_placement"):
            apply_case(case)

    def test_66_light_cross_sentence_citation_relocation_rejected(self) -> None:
        case = citation_relocation_case("light")
        with self.assertRaisesRegex(PatchApplicationError, "mode:citation_placement"):
            apply_case(case)

    def test_67_medium_same_paragraph_citation_relocation_is_inventoried(self) -> None:
        case = citation_relocation_case("medium")
        artifacts = apply_case(case)
        inventory = artifacts["review-protected-change-inventory.json"]
        moves = [item for item in inventory["protected_changes"] if item["delta_type"] == "placement_changed"]
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves[0]["identity"], "numeric_bracket:[1,2]")
        self.assertNotEqual(moves[0]["source_placement"]["source_sentence_ids"], moves[0]["candidate_placement"]["source_sentence_ids"])
        self.assertEqual(final_codes(case, artifacts), set())

    def test_68_parenthetical_to_narrative_is_placement_not_formatting(self) -> None:
        case = cited_light_case(
            "Evidence was reported (Smith, 2025).",
            "Smith (2025) reported evidence.",
        )
        case["permission"]["revision_mode"] = "medium"
        case["proposal"]["revision_mode"] = "medium"
        fixtures.refresh_permission_and_binding(case)
        artifacts = apply_case(case)
        changes = artifacts["review-protected-change-inventory.json"]["protected_changes"]
        self.assertEqual([item["delta_type"] for item in changes], ["placement_changed"])
        self.assertEqual(changes[0]["source_placement"]["citation_form"], "author_year_parenthetical")
        self.assertEqual(changes[0]["candidate_placement"]["citation_form"], "author_year_narrative")

    def test_69_light_medial_to_medial_citation_relocation_rejected(self) -> None:
        case = cited_light_case(
            "Evidence [1,2] was clearly reported.",
            "Evidence was clearly [1,2] reported.",
        )
        with self.assertRaisesRegex(PatchApplicationError, "mode:citation_placement"):
            apply_case(case)

    def test_70_medium_medial_to_medial_citation_relocation_is_inventoried(self) -> None:
        case = cited_light_case(
            "Evidence [1,2] was clearly reported.",
            "Evidence was clearly [1,2] reported.",
        )
        case["permission"]["revision_mode"] = "medium"
        case["proposal"]["revision_mode"] = "medium"
        fixtures.refresh_permission_and_binding(case)
        artifacts = apply_case(case)
        moves = [
            item for item in artifacts["review-protected-change-inventory.json"]["protected_changes"]
            if item["delta_type"] == "placement_changed"
        ]
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves[0]["identity"], "numeric_bracket:[1,2]")
        self.assertEqual(moves[0]["claim_ids"], ["claim-response"])
        self.assertEqual(moves[0]["citation_relation_ids"], ["relation-response"])
        self.assertNotEqual(
            moves[0]["source_placement"]["lexical_boundary"],
            moves[0]["candidate_placement"]["lexical_boundary"],
        )

    def test_71_word_insertion_before_trailing_citation_is_not_relocation(self) -> None:
        case = cited_light_case(
            "Evidence was reported [1,2].",
            "Evidence was clearly reported [1,2].",
        )
        artifacts = apply_case(case)
        changes = artifacts["review-protected-change-inventory.json"]["protected_changes"]
        self.assertFalse(any(item["delta_type"] == "placement_changed" for item in changes))
        self.assertFalse(artifacts["review-protected-change-inventory.json"]["structural_footprint"]["citation_placement_changed"])
        self.assertEqual(final_codes(case, artifacts), set())

    def test_72_light_ambiguous_lexical_citation_alignment_fails_closed(self) -> None:
        case = cited_light_case(
            "Evidence alpha [1,2] beta reported.",
            "Evidence gamma delta [1,2] epsilon reported.",
        )
        with self.assertRaisesRegex(PatchApplicationError, "protected:citation_placement"):
            apply_case(case)

    def test_73_medium_ambiguous_lexical_citation_alignment_fails_closed(self) -> None:
        case = cited_light_case(
            "Evidence alpha [1,2] beta reported.",
            "Evidence gamma delta [1,2] epsilon reported.",
        )
        case["permission"]["revision_mode"] = "medium"
        case["proposal"]["revision_mode"] = "medium"
        fixtures.refresh_permission_and_binding(case)
        with self.assertRaisesRegex(PatchApplicationError, "protected:citation_placement"):
            apply_case(case)

    def test_74_light_replace_gap_start_to_end_is_relocation(self) -> None:
        case = cited_light_case(
            "Evidence [1,2] alpha beta reported.",
            "Evidence gamma delta epsilon [1,2] reported.",
        )
        with self.assertRaisesRegex(PatchApplicationError, "mode:citation_placement"):
            apply_case(case)

    def test_75_medium_replace_gap_start_to_end_is_inventoried(self) -> None:
        case = cited_light_case(
            "Evidence [1,2] alpha beta reported.",
            "Evidence gamma delta epsilon [1,2] reported.",
        )
        case["permission"]["revision_mode"] = "medium"
        case["proposal"]["revision_mode"] = "medium"
        fixtures.refresh_permission_and_binding(case)
        artifacts = apply_case(case)
        moves = [
            item for item in artifacts["review-protected-change-inventory.json"]["protected_changes"]
            if item["delta_type"] == "placement_changed"
        ]
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves[0]["identity"], "numeric_bracket:[1,2]")
        self.assertNotEqual(
            moves[0]["source_placement"]["lexical_boundary"],
            moves[0]["candidate_placement"]["lexical_boundary"],
        )

    def test_76_replace_gap_start_to_start_is_stationary(self) -> None:
        case = cited_light_case(
            "Evidence [1,2] alpha beta reported.",
            "Evidence [1,2] gamma delta epsilon reported.",
        )
        artifacts = apply_case(case)
        changes = artifacts["review-protected-change-inventory.json"]["protected_changes"]
        self.assertFalse(any(item["delta_type"] == "placement_changed" for item in changes))

    def test_77_replace_gap_end_to_end_is_stationary(self) -> None:
        case = cited_light_case(
            "Evidence alpha beta [1,2] reported.",
            "Evidence gamma delta epsilon [1,2] reported.",
        )
        artifacts = apply_case(case)
        changes = artifacts["review-protected-change-inventory.json"]["protected_changes"]
        self.assertFalse(any(item["delta_type"] == "placement_changed" for item in changes))


if __name__ == "__main__":
    unittest.main()
