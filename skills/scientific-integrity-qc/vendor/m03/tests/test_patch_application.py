#!/usr/bin/env python3
"""Contract and adversarial tests for Article Polisher patch layer 0.1.6."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any


PATCH_ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = PATCH_ROOT
CORE_SCRIPTS = PATCH_ROOT / "scripts"
PATCH_SCRIPTS = PATCH_ROOT / "scripts"
M02_PACKAGE = PATCH_ROOT
M01_PACKAGE = PATCH_ROOT
for path in (PATCH_SCRIPTS, CORE_SCRIPTS):
    sys.path.insert(0, str(path))

from apply_revision_proposal import PatchApplicationError, apply_revision_proposal  # noqa: E402
from build_change_inventory import canonical_sha256, document_sha256, text_sha256  # noqa: E402
from validate_revision_package import validate_revision_package  # noqa: E402


def materialize_source() -> dict[str, Any]:
    spec = json.loads(
        (MODULE_ROOT / "tests" / "fixtures" / "base-source-spec.json").read_text(encoding="utf-8")
    )
    source = copy.deepcopy(spec)
    source["side"] = "source"
    source["document_type"] = "original_article"
    for paragraph_ordinal, paragraph in enumerate(source["paragraphs"], start=1):
        paragraph["ordinal"] = paragraph_ordinal
        paragraph["source_unit_ids"] = [paragraph["unit_id"]]
        for sentence_ordinal, sentence in enumerate(paragraph["sentences"], start=1):
            sentence["ordinal"] = sentence_ordinal
            sentence["source_unit_ids"] = [sentence["unit_id"]]
        paragraph["text"] = " ".join(item["text"] for item in paragraph["sentences"])
        paragraph["locator"] = {
            "locator_type": "structured_unit",
            "side": "source",
            "artifact_id": source["artifact_id"],
            "unit_id": paragraph["unit_id"],
            "local_identifier": f"{paragraph['section']}/paragraph/{paragraph_ordinal}",
            "span_sha256": text_sha256(paragraph["text"]),
        }
    source["artifact_sha256"] = document_sha256(source)
    return source


def identity(document: dict[str, Any]) -> dict[str, str]:
    return {
        "document_id": document["document_id"],
        "artifact_id": document["artifact_id"],
        "artifact_version": document["artifact_version"],
        "artifact_sha256": document["artifact_sha256"],
    }


def contract(
    source: dict[str, Any],
    *,
    mode: str = "light",
    allowed: list[str] | None = None,
    scope: list[str] | None = None,
    origin: str = "calling_workflow",
    state: str = "caller_accepted",
    structural: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    structural = structural or []
    value = {
        "revision_contract_id": f"revision-contract:patch-test:{mode}",
        "revision_contract_version": "0.1.0",
        "contract_sha256": "0" * 64,
        "source_document_id": source["document_id"],
        "source_artifact_id": source["artifact_id"],
        "source_artifact_version": source["artifact_version"],
        "source_artifact_sha256": source["artifact_sha256"],
        "revision_mode": mode,
        "authorized_scope": {
            "document_id": source["document_id"],
            "unit_ids": scope or [item["unit_id"] for item in source["paragraphs"]],
        },
        "allowed_operations": allowed or ["grammar", "clarity"],
        "prohibited_operations": [
            "change_numeric_anchor", "change_citation_identity", "change_terminology_identity",
            "change_claim_scope", "change_claim_evidence_relation", "change_approval_state",
            "unapproved_paragraph_restructure",
        ],
        "frozen_anchor_ids": [],
        "approved_structural_change_ids": [item["structural_change_id"] for item in structural],
        "structural_change_authorizations": structural,
        "comparison_scope": "Exact synthetic paragraph units",
        "authorization_origin": origin,
        "authorization_state": state,
        "author_approval": "approved" if state == "author_approved" else "pending",
    }
    value["contract_sha256"] = canonical_sha256({key: item for key, item in value.items() if key != "contract_sha256"})
    return value


def operation(
    source: dict[str, Any],
    *,
    operation_type: str = "grammar",
    targets: list[str] | None = None,
    replacements: list[str] | None = None,
) -> dict[str, Any]:
    sentences = {
        sentence["unit_id"]: sentence
        for paragraph in source["paragraphs"]
        for sentence in paragraph["sentences"]
    }
    targets = targets or ["sentence:results:1"]
    texts = [sentences[item]["text"] for item in targets]
    return {
        "operation_id": f"operation:test:{operation_type}",
        "operation_type": operation_type,
        "target_unit_ids": targets,
        "expected_source_texts": texts,
        "expected_source_sha256s": [text_sha256(item) for item in texts],
        "replacement_texts": replacements if replacements is not None else ["Treatment reduced viability by 20%."],
        "rationale": "grammar" if operation_type == "grammar" else "clarity",
        "risk_class": "low",
        "affected_protected_anchor_ids": [],
        "structural_change_ids": [],
        "upstream_artifact_refs": [],
    }


def proposal(source: dict[str, Any], revision_contract: dict[str, Any], operations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_name": "article_polisher_revision_proposal",
        "schema_version": "0.1.1",
        "proposal_id": "revision-proposal:patch-test:1",
        "created_at": "2026-09-04T12:00:00+00:00",
        "created_by": "model-assisted-proposer",
        "status": "machine_proposed",
        "source_artifact": identity(source),
        "candidate_artifact": {
            "document_id": source["document_id"],
            "artifact_id": "article-candidate:patch-test:1",
            "artifact_version": "1.0.1",
        },
        "revision_contract_ref": {
            "revision_contract_id": revision_contract["revision_contract_id"],
            "revision_contract_version": revision_contract["revision_contract_version"],
            "contract_sha256": revision_contract["contract_sha256"],
        },
        "operations": operations,
        "author_queries": [],
    }


def upstream_reference(value: dict[str, Any]) -> dict[str, str]:
    return {
        "artifact_id": value["artifact_id"],
        "artifact_type": value["schema_name"],
        "artifact_version": value["schema_version"],
        "artifact_sha256": canonical_sha256(value),
    }


def upstream_index(*values: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        value["artifact_id"]: {
            "value": value,
            "path": M02_PACKAGE / "tests" / "fixtures" / f"{value['schema_name']}.json",
            "artifact_type": value["schema_name"],
            "artifact_version": value["schema_version"],
            "artifact_sha256": canonical_sha256(value),
        }
        for value in values
    }


def resolve_all_author_states(value: Any) -> None:
    if isinstance(value, dict):
        if "author_approval" in value:
            value["author_approval"] = "approved"
        if "decision_id" in value:
            value["status"] = "approved"
            value.setdefault("decision", "approve synthetic fixture")
            value.setdefault("rationale", "Approved for deterministic provenance testing.")
        if "gap_id" in value:
            value["status"] = "resolved"
        for child in value.values():
            resolve_all_author_states(child)
    elif isinstance(value, list):
        for child in value:
            resolve_all_author_states(child)


def approved_provenance_closure(source: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = json.loads((M02_PACKAGE / "tests" / "fixtures" / "valid-manuscript-plan.json").read_text(encoding="utf-8"))
    claim_map = json.loads((M02_PACKAGE / "tests" / "fixtures" / "valid-claim-evidence-map.json").read_text(encoding="utf-8"))
    for value in (plan, claim_map):
        resolve_all_author_states(value)
        value["status"] = "author_approved"
        value["manuscript_id"] = source["document_id"]
    for section in plan["section_plans"]:
        for paragraph in section["paragraph_plans"]:
            if section["canonical_section"] == "results":
                paragraph["source_paragraph_ids"] = ["paragraph:results:1"]
            elif section["canonical_section"] == "discussion":
                paragraph["source_paragraph_ids"] = ["paragraph:discussion:1"]
    plan["approval_summary"].update({
        "overall_status": "approved",
        "pending_decision_count": 0,
        "open_blocker_count": 0,
    })
    for claim in claim_map["claim_records"]:
        for locator in claim.get("source_locators", []):
            locator["document_id"] = source["document_id"]
            if claim["claim_id"] == "claim:result-1":
                locator["paragraph_id"] = "paragraph:results:1"
    return plan, claim_map


def approved_interpretation_card(
    source_document_id: str = "article:synthetic:1",
) -> dict[str, Any]:
    value = json.loads((M02_PACKAGE / "tests" / "fixtures" / "valid-interpretation-card.json").read_text(encoding="utf-8"))
    resolve_all_author_states(value)
    value["status"] = "author_approved"
    value["manuscript_id"] = source_document_id
    return value


def second_approved_interpretation_card(
    source_document_id: str = "article:synthetic:1",
) -> dict[str, Any]:
    value = approved_interpretation_card(source_document_id)
    value["artifact_id"] = "interpretation-card:synthetic-2"
    value["card_id"] = "card:interpretation-2"
    value["boundary"]["boundary_id"] = "boundary:interpretation-2"
    value["author_decisions"][0]["decision_id"] = "decision:interpretation-2"
    value["author_decisions"][0]["related_ids"] = [
        value["card_id"],
        value["claim_id"],
    ]
    return value


def minimal_approved_structure_profile() -> dict[str, Any]:
    distribution = {
        "count": 1, "mean": 1.0, "median": 1.0, "p25": 1.0,
        "p75": 1.0, "minimum": 1.0, "maximum": 1.0,
    }
    feature_id = "results.marker_rate.figure_reference"
    support = {
        "feature_id": feature_id,
        "document_count": 1,
        "document_coverage": 1.0,
        "value_summary": copy.deepcopy(distribution),
        "bootstrap_95": {"low": 1.0, "high": 1.0, "method": "synthetic"},
        "between_document_dispersion": {"method": "synthetic", "value": 0.0},
        "leave_one_document_out_median_sensitivity": {"method": "synthetic", "value": 0.0},
        "parser_support": {
            "format_prior": copy.deepcopy(distribution),
            "observed_parse_qc": {
                "heading_recognition_rate": copy.deepcopy(distribution),
                "fragment_paragraph_rate": copy.deepcopy(distribution),
                "reference_contamination_rate": copy.deepcopy(distribution),
            },
        },
        "stratum_coverage": {},
    }
    return {
        "schema_name": "structure_profile",
        "schema_version": "0.2.2",
        "artifact_id": "structure-profile:approved-article-test",
        "created_at": "2026-09-04T12:00:00+00:00",
        "created_by": "style-and-structure-distiller/0.2.6",
        "source_artifact_ids": [],
        "source_files": [],
        "status": "author_approved",
        "warnings": [],
        "corpus_id": "corpus:approved-article-test",
        "corpus_type": "original_article",
        "document_count": 1,
        "section_presence": {},
        "common_canonical_sequences": [],
        "section_instances_per_document": {},
        "paragraphs_per_document_section": {},
        "heading_depth_per_document": copy.deepcopy(distribution),
        "child_edge_count_per_document_canonical_section": {},
        "mean_direct_children_per_root_section_instance_by_document": {},
        "figure_references_per_document_section": {},
        "feature_support": {feature_id: support},
        "deterministic_only": True,
        "semantic_annotation_status": "not_performed_phase3_1",
        "semantic_role_labels_present": False,
    }


def approved_plan(source_document_id: str = "article:synthetic:1") -> dict[str, Any]:
    value = json.loads((M02_PACKAGE / "tests" / "fixtures" / "valid-manuscript-plan.json").read_text(encoding="utf-8"))
    resolve_all_author_states(value)
    value["status"] = "author_approved"
    value["manuscript_id"] = source_document_id
    decision = value["author_decisions"][0]
    decision["status"] = "approved"
    decision["decision"] = "approve candidate A"
    decision["rationale"] = "Approved position-only move."
    decision["related_ids"] = [value["plan_id"]]
    value["approval_summary"].update({"overall_status": "approved", "pending_decision_count": 0, "open_blocker_count": 0})
    for gap in value.get("gaps_and_risks", []):
        gap["status"] = "resolved"
    return value


class PatchLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = materialize_source()

    def assert_error(
        self,
        expected: str,
        revision_contract: dict[str, Any],
        revision_proposal: dict[str, Any],
        upstream: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        with self.assertRaises(PatchApplicationError) as context:
            apply_revision_proposal(
                self.source, revision_contract, revision_proposal, upstream or {}
            )
        self.assertEqual(expected, context.exception.code)

    def core_issues(
        self,
        source: dict[str, Any],
        revision_contract: dict[str, Any],
        outputs: dict[str, dict[str, Any]],
        upstream: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict[str, str]]:
        issues, rebuilt = validate_revision_package(
            source,
            outputs["candidate-document.json"],
            revision_contract,
            outputs["change-manifest.json"],
            outputs["author-query-list.json"],
            upstream or {},
            outputs["revision-lineage-map.json"],
        )
        self.assertEqual(outputs["change-inventory.json"], rebuilt)
        return issues

    def test_light_exact_replacement_builds_trusted_package(self):
        revision_contract = contract(self.source)
        outputs = apply_revision_proposal(self.source, revision_contract, proposal(
            self.source, revision_contract, [operation(self.source)],
        ))
        self.assertEqual("deterministic_patch_layer", outputs["revision-lineage-map.json"]["origin"])
        self.assertEqual("author_review_required", outputs["change-manifest.json"]["status"])
        self.assertFalse(outputs["patch-application-receipt.json"]["scientific_safety_claimed"])
        self.assertEqual([], self.core_issues(self.source, revision_contract, outputs))

    def test_stale_exact_text_and_hash_fail_closed(self):
        revision_contract = contract(self.source)
        item = operation(self.source)
        item["expected_source_texts"][0] = "Stale source."
        self.assert_error("proposal:stale_source_text", revision_contract, proposal(self.source, revision_contract, [item]))
        item = operation(self.source)
        item["expected_source_sha256s"][0] = "0" * 64
        self.assert_error("proposal:stale_source_hash", revision_contract, proposal(self.source, revision_contract, [item]))

    def test_source_contract_and_proposal_bindings_are_exact(self):
        revision_contract = contract(self.source)
        stale = proposal(self.source, revision_contract, [operation(self.source)])
        stale["source_artifact"]["artifact_sha256"] = "0" * 64
        self.assert_error("proposal:source_binding", revision_contract, stale)
        stale = proposal(self.source, revision_contract, [operation(self.source)])
        stale["revision_contract_ref"]["contract_sha256"] = "0" * 64
        self.assert_error("proposal:contract_binding", revision_contract, stale)

    def test_machine_proposed_contract_cannot_execute(self):
        revision_contract = contract(self.source, state="machine_proposed")
        self.assert_error("authorization:execution", revision_contract, proposal(
            self.source, revision_contract, [operation(self.source)],
        ))

    def test_unauthorized_and_out_of_scope_operations_fail(self):
        revision_contract = contract(self.source, allowed=["clarity"])
        self.assert_error("operation:not_allowed", revision_contract, proposal(
            self.source, revision_contract, [operation(self.source)],
        ))
        revision_contract = contract(self.source, scope=["paragraph:discussion:1"])
        self.assert_error("scope:outside_authorized", revision_contract, proposal(
            self.source, revision_contract, [operation(self.source)],
        ))

    def test_unresolved_blocking_query_prevents_affected_change(self):
        revision_contract = contract(self.source)
        value = proposal(self.source, revision_contract, [operation(self.source)])
        value["author_queries"] = [{
            "query_id": "query:test:blocking",
            "query_class": "scientific_judgment",
            "question": "Does the source support this interpretation?",
            "affected_unit_ids": ["paragraph:results:1"],
            "blocks_revision": True,
            "resolution_status": "unresolved",
        }]
        self.assert_error("query:blocking_unit_changed", revision_contract, value)

    def test_one_operation_per_paragraph_prevents_ambiguous_manifest_attribution(self):
        revision_contract = contract(self.source)
        first = operation(self.source)
        second = operation(
            self.source,
            operation_type="clarity",
            targets=["sentence:results:2"],
            replacements=["This effect was observed across three biological replicates."],
        )
        self.assert_error("operation:paragraph_conflict", revision_contract, proposal(
            self.source, revision_contract, [first, second],
        ))

    def test_medium_sentence_split_is_deterministically_lineaged(self):
        revision_contract = contract(self.source, mode="medium", allowed=["sentence_split"])
        item = operation(
            self.source,
            operation_type="sentence_split",
            replacements=["The treatment reduced viability.", "The reduction was 20%."],
        )
        outputs = apply_revision_proposal(self.source, revision_contract, proposal(self.source, revision_contract, [item]))
        lineages = outputs["revision-lineage-map.json"]["sentence_lineage"]
        split = [row for row in lineages if row["source_unit_ids"] == ["sentence:results:1"]]
        self.assertEqual(2, len(split))
        self.assertEqual([], self.core_issues(self.source, revision_contract, outputs))

    def test_medium_sentence_reorder_requires_exact_full_paragraph_permutation(self):
        source = copy.deepcopy(self.source)
        source["paragraphs"][0]["section"] = "methods"
        source["paragraphs"][0]["locator"]["local_identifier"] = "methods/paragraph/1"
        source["artifact_sha256"] = document_sha256(source)
        revision_contract = contract(source, mode="medium", allowed=["sentence_reorder"])
        item = operation(
            source,
            operation_type="sentence_reorder",
            targets=["sentence:results:1", "sentence:results:2"],
            replacements=[],
        )
        item["candidate_source_order"] = ["sentence:results:2", "sentence:results:1"]
        outputs = apply_revision_proposal(source, revision_contract, proposal(source, revision_contract, [item]))
        self.assertEqual([], self.core_issues(source, revision_contract, outputs))

    def test_light_rejects_sentence_split(self):
        revision_contract = contract(self.source, allowed=["sentence_split"])
        item = operation(
            self.source,
            operation_type="sentence_split",
            replacements=["The treatment reduced viability.", "The reduction was 20%."],
        )
        self.assert_error("mode:light_structural_effect", revision_contract, proposal(self.source, revision_contract, [item]))

    def test_light_rejects_medium_only_text_operations(self):
        for operation_type in ("information_reorder", "topic_sentence_repair"):
            with self.subTest(operation_type=operation_type):
                revision_contract = contract(self.source, mode="light", allowed=[operation_type])
                item = operation(
                    self.source,
                    operation_type=operation_type,
                    replacements=["Viability was reduced by 20% by the treatment."],
                )
                if operation_type == "topic_sentence_repair":
                    item["source_proposition_ids"] = ["claim:result-1"]
                self.assert_error(
                    "mode:light_structural_effect",
                    revision_contract,
                    proposal(self.source, revision_contract, [item]),
                )

    def test_medium_rejects_unbound_information_and_topic_provenance(self):
        cases = {
            "information_reorder": "medium:missing_approved_baseline",
            "topic_sentence_repair": "topic_sentence:unresolved_proposition",
        }
        for operation_type, expected in cases.items():
            with self.subTest(operation_type=operation_type):
                revision_contract = contract(self.source, mode="medium", allowed=[operation_type])
                item = operation(
                    self.source,
                    operation_type=operation_type,
                    replacements=["Viability was reduced by 20% by the treatment."],
                )
                item["source_proposition_ids"] = ["claim:invented-never-supplied"]
                self.assert_error(
                    expected,
                    revision_contract,
                    proposal(self.source, revision_contract, [item]),
                )

    def test_medium_accepts_exact_information_and_topic_provenance(self):
        plan, claim_map = approved_provenance_closure(self.source)
        cases = {
            "information_reorder": (plan, claim_map),
            "topic_sentence_repair": (claim_map,),
        }
        for operation_type, artifacts in cases.items():
            with self.subTest(operation_type=operation_type):
                revision_contract = contract(self.source, mode="medium", allowed=[operation_type])
                item = operation(
                    self.source,
                    operation_type=operation_type,
                    replacements=["Viability was reduced by 20% by the treatment."],
                )
                item["source_proposition_ids"] = ["claim:result-1"]
                item["upstream_artifact_refs"] = [
                    upstream_reference(value) for value in artifacts
                ]
                upstream = upstream_index(*artifacts)
                outputs = apply_revision_proposal(
                    self.source,
                    revision_contract,
                    proposal(self.source, revision_contract, [item]),
                    upstream,
                )
                self.assertEqual(
                    [],
                    self.core_issues(
                        self.source, revision_contract, outputs, upstream
                    ),
                )

    def test_information_reorder_rejects_pending_target_claim(self):
        plan, claim_map = approved_provenance_closure(self.source)
        target = next(
            item for item in claim_map["claim_records"]
            if item["claim_id"] == "claim:result-1"
        )
        target["author_approval"] = "pending"
        revision_contract = contract(
            self.source, mode="medium", allowed=["information_reorder"]
        )
        item = operation(
            self.source,
            operation_type="information_reorder",
            replacements=["Viability was reduced by 20% by the treatment."],
        )
        item["source_proposition_ids"] = ["claim:result-1"]
        item["upstream_artifact_refs"] = [
            upstream_reference(plan), upstream_reference(claim_map)
        ]
        self.assert_error(
            "medium:missing_approved_baseline",
            revision_contract,
            proposal(self.source, revision_contract, [item]),
            upstream_index(plan, claim_map),
        )

    def test_information_reorder_rejects_inconsistent_plan_approval_summary(self):
        plan, claim_map = approved_provenance_closure(self.source)
        plan["approval_summary"].update({
            "overall_status": "pending",
            "pending_decision_count": 1,
        })
        revision_contract = contract(
            self.source, mode="medium", allowed=["information_reorder"]
        )
        item = operation(
            self.source,
            operation_type="information_reorder",
            replacements=["Viability was reduced by 20% by the treatment."],
        )
        item["source_proposition_ids"] = ["claim:result-1"]
        item["upstream_artifact_refs"] = [
            upstream_reference(plan), upstream_reference(claim_map)
        ]
        self.assert_error(
            "medium:missing_approved_baseline",
            revision_contract,
            proposal(self.source, revision_contract, [item]),
            upstream_index(plan, claim_map),
        )

    def assert_information_reorder_rejects_authority_mutation(
        self,
        artifact: str,
        mutate: Any,
    ) -> None:
        plan, claim_map = approved_provenance_closure(self.source)
        mutate(plan if artifact == "plan" else claim_map)
        revision_contract = contract(
            self.source, mode="medium", allowed=["information_reorder"]
        )
        item = operation(
            self.source,
            operation_type="information_reorder",
            replacements=["Viability was reduced by 20% by the treatment."],
        )
        item["source_proposition_ids"] = ["claim:result-1"]
        item["upstream_artifact_refs"] = [
            upstream_reference(plan), upstream_reference(claim_map)
        ]
        self.assert_error(
            "medium:missing_approved_baseline",
            revision_contract,
            proposal(self.source, revision_contract, [item]),
            upstream_index(plan, claim_map),
        )

    def test_information_reorder_rejects_pending_plan_anchor(self):
        self.assert_information_reorder_rejects_authority_mutation(
            "plan",
            lambda plan: plan["story_anchors"]["novelty_scope"].update(
                {"author_approval": "pending"}
            ),
        )

    def test_information_reorder_rejects_pending_plan_author_decision(self):
        self.assert_information_reorder_rejects_authority_mutation(
            "plan",
            lambda plan: plan["author_decisions"][0].update({"status": "pending"}),
        )

    def test_information_reorder_rejects_open_plan_gap(self):
        self.assert_information_reorder_rejects_authority_mutation(
            "plan",
            lambda plan: plan["gaps_and_risks"][0].update({"status": "open"}),
        )

    def test_information_reorder_rejects_unrelated_pending_plan_section(self):
        self.assert_information_reorder_rejects_authority_mutation(
            "plan",
            lambda plan: next(
                section for section in plan["section_plans"]
                if section["canonical_section"] == "discussion"
            ).update({"author_approval": "pending"}),
        )

    def test_information_reorder_rejects_pending_claim_map_central_question(self):
        self.assert_information_reorder_rejects_authority_mutation(
            "claim_map",
            lambda claim_map: claim_map["central_question"].update(
                {"author_approval": "pending"}
            ),
        )

    def test_information_reorder_rejects_unrelated_pending_claim_map_child(self):
        self.assert_information_reorder_rejects_authority_mutation(
            "claim_map",
            lambda claim_map: claim_map["frozen_elements"][0].update(
                {"author_approval": "pending"}
            ),
        )

    def test_topic_sentence_repair_rejects_wrong_paragraph_claim(self):
        _, claim_map = approved_provenance_closure(self.source)
        claim_map["claim_records"][0]["source_locators"][0]["paragraph_id"] = "paragraph:discussion:1"
        revision_contract = contract(
            self.source, mode="medium", allowed=["topic_sentence_repair"]
        )
        item = operation(
            self.source,
            operation_type="topic_sentence_repair",
            replacements=["Viability was reduced by 20% by the treatment."],
        )
        item["source_proposition_ids"] = ["claim:result-1"]
        item["upstream_artifact_refs"] = [upstream_reference(claim_map)]
        self.assert_error(
            "topic_sentence:unresolved_proposition",
            revision_contract,
            proposal(self.source, revision_contract, [item]),
            upstream_index(claim_map),
        )

    def test_profile_alignment_requires_exact_supplied_profile_feature(self):
        revision_contract = contract(self.source, allowed=["grammar"])
        item = operation(self.source)
        item["rationale"] = "profile_alignment"
        self.assert_error(
            "profile:missing_feature_ref",
            revision_contract,
            proposal(self.source, revision_contract, [item]),
        )

        item["profile_feature_ref"] = {
            "profile_id": "structure-profile:invented",
            "profile_version": "9.9.9",
            "profile_sha256": "a" * 64,
            "feature_id": "feature:invented",
            "feature_support_ref": "/feature_support/feature:invented",
        }
        self.assert_error(
            "profile:unbound_feature",
            revision_contract,
            proposal(self.source, revision_contract, [item]),
        )

        profile = minimal_approved_structure_profile()
        feature_id = "results.marker_rate.figure_reference"
        item["profile_feature_ref"] = {
            "profile_id": profile["artifact_id"],
            "profile_version": profile["schema_version"],
            "profile_sha256": canonical_sha256(profile),
            "feature_id": feature_id,
            "feature_support_ref": f"/feature_support/{feature_id}",
        }
        item["upstream_artifact_refs"] = [upstream_reference(profile)]
        upstream = upstream_index(profile)
        outputs = apply_revision_proposal(
            self.source,
            revision_contract,
            proposal(self.source, revision_contract, [item]),
            upstream,
        )
        self.assertEqual([], self.core_issues(
            self.source, revision_contract, outputs, upstream
        ))

        item["upstream_artifact_refs"][0]["artifact_sha256"] = "b" * 64
        self.assert_error(
            "profile:unbound_feature",
            revision_contract,
            proposal(self.source, revision_contract, [item]),
            upstream,
        )

    def test_deep_paragraph_move_requires_and_preserves_authorized_plan_closure(self):
        plan = approved_plan()
        structural_id = plan["author_decisions"][0]["decision_id"]
        paragraph_ids = [item["unit_id"] for item in self.source["paragraphs"]]
        candidate_order = list(reversed(paragraph_ids))
        authorization = {
            "structural_change_id": structural_id,
            "allowed_effects": ["paragraph_move"],
            "source_unit_ids": paragraph_ids,
            "candidate_unit_ids": candidate_order,
            "required_upstream_artifact_ids": [plan["artifact_id"]],
            "author_approval": "approved",
        }
        revision_contract = contract(
            self.source,
            mode="deep",
            allowed=["paragraph_move"],
            origin="author",
            state="author_approved",
            structural=[authorization],
        )
        item = {
            "operation_id": "operation:test:paragraph-move",
            "operation_type": "paragraph_move",
            "target_unit_ids": paragraph_ids,
            "expected_source_texts": [row["text"] for row in self.source["paragraphs"]],
            "expected_source_sha256s": [text_sha256(row["text"]) for row in self.source["paragraphs"]],
            "replacement_texts": [],
            "candidate_source_order": candidate_order,
            "rationale": "approved_structure",
            "risk_class": "high",
            "affected_protected_anchor_ids": [],
            "structural_change_ids": [structural_id],
            "upstream_artifact_refs": [upstream_reference(plan)],
        }
        outputs = apply_revision_proposal(self.source, revision_contract, proposal(self.source, revision_contract, [item]))
        self.assertEqual(candidate_order, [row["source_unit_ids"][0] for row in outputs["candidate-document.json"]["paragraphs"]])
        self.assertEqual([], self.core_issues(self.source, revision_contract, outputs, upstream_index(plan)))

    def deep_reference_case(
        self,
        referenced_id: str,
        cards: list[dict[str, Any]],
        tamper_card_hash: bool = False,
        plan_override: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
        plan = (
            copy.deepcopy(plan_override)
            if plan_override is not None
            else approved_plan(self.source["document_id"])
        )
        plan["author_decisions"][0]["related_ids"].append(referenced_id)
        structural_id = plan["author_decisions"][0]["decision_id"]
        paragraph_ids = [item["unit_id"] for item in self.source["paragraphs"]]
        candidate_order = list(reversed(paragraph_ids))
        authorization = {
            "structural_change_id": structural_id,
            "allowed_effects": ["paragraph_move"],
            "source_unit_ids": paragraph_ids,
            "candidate_unit_ids": candidate_order,
            "required_upstream_artifact_ids": [plan["artifact_id"]],
            "author_approval": "approved",
        }
        revision_contract = contract(
            self.source,
            mode="deep",
            allowed=["paragraph_move"],
            origin="author",
            state="author_approved",
            structural=[authorization],
        )
        artifacts = [plan, *cards]
        item = {
            "operation_id": "operation:test:deep-card-closure",
            "operation_type": "paragraph_move",
            "target_unit_ids": paragraph_ids,
            "expected_source_texts": [row["text"] for row in self.source["paragraphs"]],
            "expected_source_sha256s": [text_sha256(row["text"]) for row in self.source["paragraphs"]],
            "replacement_texts": [],
            "candidate_source_order": candidate_order,
            "rationale": "approved_structure",
            "risk_class": "high",
            "affected_protected_anchor_ids": [],
            "structural_change_ids": [structural_id],
            "upstream_artifact_refs": [upstream_reference(value) for value in artifacts],
        }
        if tamper_card_hash:
            item["upstream_artifact_refs"][-1]["artifact_sha256"] = "0" * 64
        return (
            revision_contract,
            proposal(self.source, revision_contract, [item]),
            upstream_index(*artifacts),
        )

    def test_deep_direct_card_rejects_pending_boundary_approval(self):
        card = approved_interpretation_card(self.source["document_id"])
        card["boundary"]["author_approval"] = "pending"
        revision_contract, revision_proposal, upstream = self.deep_reference_case(
            card["artifact_id"], [card]
        )
        outputs = apply_revision_proposal(
            self.source, revision_contract, revision_proposal, upstream
        )
        self.assertIn(
            "deep:authorization_closure",
            {item["code"] for item in self.core_issues(self.source, revision_contract, outputs, upstream)},
        )

    def test_deep_direct_card_rejects_pending_author_decision(self):
        card = approved_interpretation_card(self.source["document_id"])
        card["author_decisions"][0]["status"] = "pending"
        revision_contract, revision_proposal, upstream = self.deep_reference_case(
            card["artifact_id"], [card]
        )
        outputs = apply_revision_proposal(
            self.source, revision_contract, revision_proposal, upstream
        )
        self.assertIn(
            "deep:authorization_closure",
            {item["code"] for item in self.core_issues(self.source, revision_contract, outputs, upstream)},
        )

    def test_deep_boundary_rejects_rogue_unreferenced_card(self):
        card = approved_interpretation_card("other-manuscript")
        card["artifact_id"] = "interpretation-card:rogue"
        card["card_id"] = "card:rogue"
        revision_contract, revision_proposal, upstream = self.deep_reference_case(
            card["boundary"]["boundary_id"], [card]
        )
        outputs = apply_revision_proposal(
            self.source, revision_contract, revision_proposal, upstream
        )
        self.assertIn(
            "deep:authorization_closure",
            {item["code"] for item in self.core_issues(self.source, revision_contract, outputs, upstream)},
        )

    def test_deep_boundary_rejects_plan_card_for_wrong_manuscript(self):
        card = approved_interpretation_card("other-manuscript")
        revision_contract, revision_proposal, upstream = self.deep_reference_case(
            card["boundary"]["boundary_id"], [card]
        )
        outputs = apply_revision_proposal(
            self.source, revision_contract, revision_proposal, upstream
        )
        self.assertIn(
            "deep:authorization_closure",
            {item["code"] for item in self.core_issues(self.source, revision_contract, outputs, upstream)},
        )

    def test_deep_boundary_accepts_exact_consistent_plan_card(self):
        card = approved_interpretation_card(self.source["document_id"])
        revision_contract, revision_proposal, upstream = self.deep_reference_case(
            card["boundary"]["boundary_id"], [card]
        )
        outputs = apply_revision_proposal(
            self.source, revision_contract, revision_proposal, upstream
        )
        self.assertEqual([], self.core_issues(self.source, revision_contract, outputs, upstream))

    def test_deep_non_key_boundary_rejects_missing_planned_card(self):
        plan = approved_plan(self.source["document_id"])
        card = second_approved_interpretation_card(self.source["document_id"])
        plan["interpretation_card_ids"].append(card["artifact_id"])
        plan["source_artifact_ids"].append(card["artifact_id"])
        self.assertNotIn(
            card["boundary"]["boundary_id"],
            plan["story_anchors"]["key_boundary_ids"],
        )
        revision_contract, revision_proposal, upstream = self.deep_reference_case(
            card["boundary"]["boundary_id"], [], plan_override=plan
        )
        outputs = apply_revision_proposal(
            self.source, revision_contract, revision_proposal, upstream
        )
        self.assertIn(
            "deep:authorization_closure",
            {item["code"] for item in self.core_issues(self.source, revision_contract, outputs, upstream)},
        )

    def test_deep_non_key_boundary_accepts_exact_planned_card(self):
        plan = approved_plan(self.source["document_id"])
        card = second_approved_interpretation_card(self.source["document_id"])
        plan["interpretation_card_ids"].append(card["artifact_id"])
        plan["source_artifact_ids"].append(card["artifact_id"])
        self.assertNotIn(
            card["boundary"]["boundary_id"],
            plan["story_anchors"]["key_boundary_ids"],
        )
        revision_contract, revision_proposal, upstream = self.deep_reference_case(
            card["boundary"]["boundary_id"], [card], plan_override=plan
        )
        outputs = apply_revision_proposal(
            self.source, revision_contract, revision_proposal, upstream
        )
        self.assertEqual([], self.core_issues(self.source, revision_contract, outputs, upstream))

    def test_deep_boundary_rejects_card_reference_hash_mismatch(self):
        card = approved_interpretation_card(self.source["document_id"])
        revision_contract, revision_proposal, upstream = self.deep_reference_case(
            card["boundary"]["boundary_id"], [card], tamper_card_hash=True
        )
        outputs = apply_revision_proposal(
            self.source, revision_contract, revision_proposal, upstream
        )
        codes = {
            item["code"]
            for item in self.core_issues(self.source, revision_contract, outputs, upstream)
        }
        self.assertIn("upstream:identity_mismatch", codes)
        self.assertIn("deep:authorization_closure", codes)

    def test_deep_paragraph_move_without_exact_authorization_fails(self):
        paragraph_ids = [item["unit_id"] for item in self.source["paragraphs"]]
        revision_contract = contract(
            self.source, mode="deep", allowed=["paragraph_move"], origin="author", state="author_approved",
        )
        item = {
            "operation_id": "operation:test:paragraph-move",
            "operation_type": "paragraph_move",
            "target_unit_ids": paragraph_ids,
            "expected_source_texts": [row["text"] for row in self.source["paragraphs"]],
            "expected_source_sha256s": [text_sha256(row["text"]) for row in self.source["paragraphs"]],
            "replacement_texts": [],
            "candidate_source_order": list(reversed(paragraph_ids)),
            "rationale": "approved_structure",
            "risk_class": "high",
            "affected_protected_anchor_ids": [],
            "structural_change_ids": ["decision:not-authorized"],
            "upstream_artifact_refs": [],
        }
        self.assert_error("deep:authorization_scope", revision_contract, proposal(self.source, revision_contract, [item]))

    def test_paragraph_split_and_merge_remain_explicitly_unsupported(self):
        for operation_type in ("paragraph_split", "paragraph_merge"):
            with self.subTest(operation_type=operation_type):
                revision_contract = contract(self.source, mode="deep", allowed=[operation_type], origin="author", state="author_approved")
                item = operation(self.source)
                item["operation_type"] = operation_type
                self.assert_error("operation:unsupported", revision_contract, proposal(self.source, revision_contract, [item]))

    def test_model_cannot_supply_lineage_or_approval_fields(self):
        revision_contract = contract(self.source)
        value = proposal(self.source, revision_contract, [operation(self.source)])
        value["lineage_origin"] = "deterministic_patch_layer"
        value["status"] = "author_approved"
        self.assert_error("proposal:authority", revision_contract, value)


if __name__ == "__main__":
    unittest.main()
