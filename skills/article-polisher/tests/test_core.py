#!/usr/bin/env python3
"""Synthetic and adversarial tests for Article Polisher core 0.1.6."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCHEMAS = ROOT / "schemas"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
RESULT_ROOT = ROOT
PHASE4_PLAN = FIXTURES / "valid-manuscript-plan.json"
CLAIM_EVIDENCE_MAP = FIXTURES / "valid-claim-evidence-map.json"
sys.path.insert(0, str(SCRIPTS))

from build_change_inventory import (  # noqa: E402
    build_inventory,
    canonical_sha256,
    declared_lineage_map,
    document_sha256,
    text_sha256,
    write_json,
)
from validate_revision_package import (  # noqa: E402
    DEFAULT_VALIDATOR,
    PHASE4_SCHEMAS,
    _load_validator,
    _revision_contract_schema_issues,
    _schema_issues,
    validate_revision_package,
)


def read_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def materialize_document(spec: dict[str, Any], side: str) -> dict[str, Any]:
    document = copy.deepcopy(spec)
    document["side"] = side
    document["document_type"] = "original_article"
    for paragraph_ordinal, paragraph in enumerate(document["paragraphs"], start=1):
        paragraph["ordinal"] = paragraph_ordinal
        if side == "source":
            paragraph["source_unit_ids"] = [paragraph["unit_id"]]
        for sentence_ordinal, sentence in enumerate(paragraph["sentences"], start=1):
            sentence["ordinal"] = sentence_ordinal
            if side == "source":
                sentence["source_unit_ids"] = [sentence["unit_id"]]
        paragraph["text"] = " ".join(item["text"] for item in paragraph["sentences"])
        paragraph["locator"] = {
            "locator_type": "structured_unit",
            "side": side,
            "artifact_id": document["artifact_id"],
            "unit_id": paragraph["unit_id"],
            "local_identifier": f"{paragraph['section']}/paragraph/{paragraph_ordinal}",
            "span_sha256": text_sha256(paragraph["text"]),
        }
    document["artifact_sha256"] = document_sha256(document)
    return document


def refresh_document(document: dict[str, Any]) -> None:
    for paragraph_ordinal, paragraph in enumerate(document["paragraphs"], start=1):
        paragraph["ordinal"] = paragraph_ordinal
        for sentence_ordinal, sentence in enumerate(paragraph["sentences"], start=1):
            sentence["ordinal"] = sentence_ordinal
        paragraph["text"] = " ".join(item["text"] for item in paragraph["sentences"])
        paragraph["locator"]["local_identifier"] = f"{paragraph['section']}/paragraph/{paragraph_ordinal}"
        paragraph["locator"]["span_sha256"] = text_sha256(paragraph["text"])
    document["artifact_sha256"] = document_sha256(document)


def unchanged_candidate(source: dict[str, Any]) -> dict[str, Any]:
    spec = {
        "document_id": source["document_id"],
        "artifact_id": "article-candidate:synthetic:unchanged",
        "artifact_version": "1.0.0",
        "paragraphs": [],
    }
    for paragraph in source["paragraphs"]:
        spec["paragraphs"].append({
            "unit_id": paragraph["unit_id"],
            "source_unit_ids": [paragraph["unit_id"]],
            "section": paragraph["section"],
            "paragraph_function": copy.deepcopy(paragraph["paragraph_function"]),
            "experiment_labels": list(paragraph["experiment_labels"]),
            "sentences": [
                {
                    "unit_id": f"candidate:{sentence['unit_id']}",
                    "source_unit_ids": [sentence["unit_id"]],
                    "text": sentence["text"],
                }
                for sentence in paragraph["sentences"]
            ],
        })
    return materialize_document(spec, "candidate")


def make_contract(
    source: dict[str, Any],
    mode: str = "light",
    allowed: list[str] | None = None,
    scope: list[str] | None = None,
    origin: str = "calling_workflow",
    state: str = "caller_accepted",
    structural_authorizations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    author_approval = "approved" if state == "author_approved" else "pending"
    structural_authorizations = structural_authorizations or []
    contract = {
        "revision_contract_id": f"revision-contract:{mode}:synthetic",
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
        "allowed_operations": allowed or ["grammar", "syntax", "clarity"],
        "prohibited_operations": [
            "change_numeric_anchor", "change_claim_scope", "change_claim_evidence_relation",
            "unapproved_paragraph_restructure",
        ],
        "frozen_anchor_ids": [],
        "approved_structural_change_ids": [
            item["structural_change_id"] for item in structural_authorizations
        ],
        "structural_change_authorizations": structural_authorizations,
        "comparison_scope": "Explicit synthetic paragraph units",
        "authorization_origin": origin,
        "authorization_state": state,
        "author_approval": author_approval,
    }
    contract["contract_sha256"] = canonical_sha256({
        key: value for key, value in contract.items() if key != "contract_sha256"
    })
    return contract


def artifact_identity(document: dict[str, Any]) -> dict[str, str]:
    return {
        "document_id": document["document_id"],
        "artifact_id": document["artifact_id"],
        "artifact_version": document["artifact_version"],
        "artifact_sha256": document["artifact_sha256"],
    }


def make_upstream_ref(artifact: dict[str, Any]) -> dict[str, str]:
    return {
        "artifact_id": artifact["artifact_id"],
        "artifact_type": artifact["schema_name"],
        "artifact_version": artifact["schema_version"],
        "artifact_sha256": canonical_sha256(artifact),
    }


def make_manifest(
    source: dict[str, Any],
    candidate: dict[str, Any],
    contract: dict[str, Any],
    inventory: dict[str, Any],
    operation: str = "grammar",
    rationale: str = "grammar",
    structural_change_ids: list[str] | None = None,
    upstream_refs: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    records = []
    for index, item in enumerate(inventory["changed_units"], start=1):
        records.append({
            "change_id": f"change:synthetic:{index}",
            "inventory_change_id": item["inventory_change_id"],
            "source_unit_ids": item["source_unit_ids"],
            "candidate_unit_ids": item["candidate_unit_ids"],
            "source_locators": item["source_locators"],
            "candidate_locators": item["candidate_locators"],
            "source_representation_sha256": item["source_representation_sha256"],
            "candidate_representation_sha256": item["candidate_representation_sha256"],
            "section": item["section"],
            "paragraph_function": item["paragraph_function"],
            "experiment_labels": item["experiment_labels"],
            "revision_mode": contract["revision_mode"],
            "operation_type": operation,
            "authorization_origin": contract["authorization_origin"],
            "authorization_state": contract["authorization_state"],
            "affected_protected_anchor_ids": [],
            "rationale": rationale,
            "risk_class": "low",
            "author_review_required": True,
            "structural_change_ids": list(structural_change_ids or []),
            "upstream_artifact_refs": copy.deepcopy(upstream_refs or []),
        })
    return {
        "schema_name": "change_manifest",
        "schema_version": "0.1.1",
        "artifact_id": "change-manifest:synthetic:1",
        "created_at": "2026-08-31T12:00:00+00:00",
        "created_by": "article-polisher-minimum/0.1.0",
        "status": "author_review_required",
        "source_artifact": artifact_identity(source),
        "candidate_artifact": artifact_identity(candidate),
        "revision_contract_ref": {
            "revision_contract_id": contract["revision_contract_id"],
            "revision_contract_version": contract["revision_contract_version"],
            "contract_sha256": contract["contract_sha256"],
        },
        "changes": records,
    }


def make_queries(source: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "author_query_list",
        "schema_version": "0.1.0",
        "artifact_id": "author-query-list:synthetic:1",
        "created_at": "2026-08-31T12:00:00+00:00",
        "created_by": "article-polisher-minimum/0.1.0",
        "status": "author_review_required",
        "source_artifact": artifact_identity(source),
        "candidate_artifact": artifact_identity(candidate),
        "queries": [],
    }


def trusted_lineage_map(
    source: dict[str, Any],
    candidate: dict[str, Any],
    origin: str = "deterministic_patch_layer",
) -> dict[str, Any]:
    """Simulate the separate lineage evidence supplied by the deterministic caller."""
    return declared_lineage_map(source, candidate, origin=origin)


def approved_phase4_plan(
    source_document_id: str = "article:synthetic:1",
) -> dict[str, Any]:
    plan = json.loads(PHASE4_PLAN.read_text(encoding="utf-8"))
    plan["status"] = "author_approved"
    plan["manuscript_id"] = source_document_id

    def approve_fields(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "author_approval":
                    value[key] = "approved"
                else:
                    approve_fields(child)
        elif isinstance(value, list):
            for child in value:
                approve_fields(child)

    approve_fields(plan)
    for decision in plan["author_decisions"]:
        decision["status"] = "approved"
        decision["decision"] = "approve candidate A"
        decision["rationale"] = "Synthetic approved position-only move."
    for gap in plan["gaps_and_risks"]:
        gap["status"] = "resolved"
    source_ids_by_section = {
        "results": ["paragraph:results:1"],
        "discussion": ["paragraph:discussion:1"],
    }
    for section in plan["section_plans"]:
        source_ids = source_ids_by_section.get(section["canonical_section"])
        if source_ids:
            for paragraph in section["paragraph_plans"]:
                paragraph["source_paragraph_ids"] = source_ids
    plan["approval_summary"]["overall_status"] = "approved"
    plan["approval_summary"]["pending_decision_count"] = 0
    plan["approval_summary"]["open_blocker_count"] = 0
    return plan


def upstream_index(*artifacts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        artifact["artifact_id"]: {
            "value": artifact,
            "path": PHASE4_PLAN.parent / f"{artifact['schema_name']}.json",
            "artifact_type": artifact["schema_name"],
            "artifact_version": artifact["schema_version"],
            "artifact_sha256": canonical_sha256(artifact),
        }
        for artifact in artifacts
    }


def resolve_all_author_states(value: Any) -> None:
    """Create a fully approved synthetic upstream closure for positive controls."""
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


def approved_claim_evidence_map(
    source_document_id: str = "article:synthetic:1",
) -> dict[str, Any]:
    value = json.loads(CLAIM_EVIDENCE_MAP.read_text(encoding="utf-8"))
    resolve_all_author_states(value)
    value["status"] = "author_approved"
    value["manuscript_id"] = source_document_id
    for claim in value["claim_records"]:
        for locator in claim.get("source_locators", []):
            locator["document_id"] = source_document_id
            if claim["claim_id"] == "claim:result-1":
                locator["paragraph_id"] = "paragraph:results:1"
    return value


def approved_interpretation_card(
    source_document_id: str = "article:synthetic:1",
) -> dict[str, Any]:
    value = json.loads(PHASE4_PLAN.with_name("valid-interpretation-card.json").read_text(encoding="utf-8"))
    resolve_all_author_states(value)
    value["status"] = "author_approved"
    value["manuscript_id"] = source_document_id
    return value


def second_approved_interpretation_card(
    source_document_id: str = "article:synthetic:1",
) -> dict[str, Any]:
    """Create a valid planned card whose boundary is deliberately non-key."""
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


class ArticlePolisherMinimumTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = materialize_document(read_fixture("base-source-spec.json"), "source")
        self.candidate = materialize_document(read_fixture("base-candidate-spec.json"), "candidate")

    def package(self, **contract_kwargs: Any):
        contract = make_contract(self.source, **contract_kwargs)
        inventory = build_inventory(self.source, self.candidate)
        manifest = make_manifest(self.source, self.candidate, contract, inventory)
        queries = make_queries(self.source, self.candidate)
        return contract, inventory, manifest, queries

    def semantic_issues(
        self,
        source: dict[str, Any],
        candidate: dict[str, Any],
        contract: dict[str, Any],
        manifest: dict[str, Any],
        queries: dict[str, Any],
        upstream: dict[str, dict[str, Any]] | None = None,
        lineage: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        issues, _ = validate_revision_package(
            source, candidate, contract, manifest, queries, upstream or {},
            lineage or trusted_lineage_map(source, candidate),
        )
        return issues

    def assert_code(self, issues: list[dict[str, str]], code: str) -> None:
        self.assertIn(code, {item["code"] for item in issues})

    def test_valid_light_package(self):
        contract, _, manifest, queries = self.package()
        self.assertEqual([], self.semantic_issues(self.source, self.candidate, contract, manifest, queries))

    def test_artifact_and_revision_contract_schemas(self):
        contract, _, manifest, queries = self.package()
        validator = _load_validator(DEFAULT_VALIDATOR)
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            manifest_path = directory / "change-manifest.json"
            queries_path = directory / "author-queries.json"
            write_json(manifest_path, manifest)
            write_json(queries_path, queries)
            self.assertEqual([], _schema_issues(validator, SCHEMAS / "change-manifest.schema.json", manifest_path))
            self.assertEqual([], _schema_issues(validator, SCHEMAS / "author-query-list.schema.json", queries_path))
            self.assertEqual([], _revision_contract_schema_issues(validator, contract))

    def test_schema_negatives_reject_missing_contract_fields(self):
        contract, _, manifest, queries = self.package()
        validator = _load_validator(DEFAULT_VALIDATOR)
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            del manifest["changes"][0]["inventory_change_id"]
            manifest_path = directory / "bad-manifest.json"
            write_json(manifest_path, manifest)
            manifest_issues = _schema_issues(
                validator, SCHEMAS / "change-manifest.schema.json", manifest_path,
            )
            self.assertTrue(any(item["code"] == "schema:required" for item in manifest_issues))

            queries["queries"] = [{
                "query_id": "query:missing-block-field",
                "query_class": "ambiguity",
                "question": "Which interpretation is intended?",
                "affected_unit_ids": ["paragraph:results:1"],
                "affected_locators": [self.source["paragraphs"][0]["locator"]],
                "resolution_status": "unresolved",
            }]
            queries_path = directory / "bad-queries.json"
            write_json(queries_path, queries)
            query_issues = _schema_issues(
                validator, SCHEMAS / "author-query-list.schema.json", queries_path,
            )
            self.assertTrue(any(item["code"] == "schema:required" for item in query_issues))

            del contract["source_artifact_sha256"]
            self.assertTrue(any(
                item["code"] == "schema:required"
                for item in _revision_contract_schema_issues(validator, contract)
            ))

    def test_inventory_detects_mislabelled_sentence_reorder(self):
        candidate = unchanged_candidate(self.source)
        paragraph = candidate["paragraphs"][0]
        paragraph["sentences"].reverse()
        # Deliberately falsify lineage by position; exact source text still reveals the reorder.
        paragraph["sentences"][0]["source_unit_ids"] = ["sentence:results:1"]
        paragraph["sentences"][1]["source_unit_ids"] = ["sentence:results:2"]
        refresh_document(candidate)
        contract = make_contract(self.source, mode="light", allowed=["grammar"])
        inventory = build_inventory(self.source, candidate)
        manifest = make_manifest(self.source, candidate, contract, inventory, operation="grammar")
        issues = self.semantic_issues(self.source, candidate, contract, manifest, make_queries(self.source, candidate))
        self.assert_code(issues, "operation:mislabelled_structural_change")
        self.assert_code(issues, "mode:light_structural_effect")
        self.assertTrue(inventory["structural_footprint"]["sentence_order_changed"])

    def test_changed_reorder_with_model_declared_lineage_is_unassessable(self):
        candidate = unchanged_candidate(self.source)
        paragraph = candidate["paragraphs"][0]
        paragraph["sentences"].reverse()
        paragraph["sentences"][0]["text"] = "Replicate-level effects were detected."
        paragraph["sentences"][1]["text"] = "Viability declined by twenty percent."
        # Falsify by position after rewriting, so exact-text recovery cannot help.
        paragraph["sentences"][0]["source_unit_ids"] = ["sentence:results:1"]
        paragraph["sentences"][1]["source_unit_ids"] = ["sentence:results:2"]
        refresh_document(candidate)
        contract = make_contract(self.source, mode="light", allowed=["grammar"])
        inventory = build_inventory(self.source, candidate)
        self.assertFalse(inventory["structural_footprint"]["sentence_order_changed"])
        manifest = make_manifest(self.source, candidate, contract, inventory, operation="grammar")
        issues = self.semantic_issues(
            self.source, candidate, contract, manifest, make_queries(self.source, candidate),
            lineage=trusted_lineage_map(self.source, candidate, origin="model_declared"),
        )
        self.assert_code(issues, "lineage:untrusted")

    def test_unknown_and_cross_paragraph_sentence_lineage_fail(self):
        candidate = unchanged_candidate(self.source)
        candidate["paragraphs"][0]["sentences"][0]["source_unit_ids"] = ["sentence:not-real"]
        refresh_document(candidate)
        contract = make_contract(self.source)
        inventory = build_inventory(self.source, candidate)
        manifest = make_manifest(self.source, candidate, contract, inventory)
        issues = self.semantic_issues(self.source, candidate, contract, manifest, make_queries(self.source, candidate))
        self.assert_code(issues, "lineage:unknown_sentence")

        candidate = unchanged_candidate(self.source)
        candidate["paragraphs"][0]["sentences"][0]["source_unit_ids"] = ["sentence:discussion:1"]
        refresh_document(candidate)
        inventory = build_inventory(self.source, candidate)
        manifest = make_manifest(self.source, candidate, contract, inventory)
        issues = self.semantic_issues(self.source, candidate, contract, manifest, make_queries(self.source, candidate))
        self.assert_code(issues, "lineage:paragraph_closure")

    def test_locator_identity_and_span_hash_mismatch_fail(self):
        candidate = unchanged_candidate(self.source)
        locator = candidate["paragraphs"][0]["locator"]
        locator.update({
            "side": "source", "artifact_id": "wrong-artifact",
            "unit_id": "wrong-unit", "span_sha256": "0" * 64,
        })
        candidate["artifact_sha256"] = document_sha256(candidate)
        contract = make_contract(self.source)
        inventory = build_inventory(self.source, candidate)
        manifest = make_manifest(self.source, candidate, contract, inventory)
        issues = self.semantic_issues(self.source, candidate, contract, manifest, make_queries(self.source, candidate))
        self.assert_code(issues, "document:invalid")

    def test_light_sentence_split_fails(self):
        candidate = unchanged_candidate(self.source)
        paragraph = candidate["paragraphs"][0]
        paragraph["sentences"] = [
            {"unit_id": "candidate:split:1", "source_unit_ids": ["sentence:results:1"], "ordinal": 1, "text": "The treatment reduced viability."},
            {"unit_id": "candidate:split:2", "source_unit_ids": ["sentence:results:1"], "ordinal": 2, "text": "The reduction was 20%."},
            paragraph["sentences"][1],
        ]
        refresh_document(candidate)
        contract = make_contract(self.source, mode="light", allowed=["grammar"])
        inventory = build_inventory(self.source, candidate)
        manifest = make_manifest(self.source, candidate, contract, inventory, operation="grammar")
        issues = self.semantic_issues(self.source, candidate, contract, manifest, make_queries(self.source, candidate))
        self.assert_code(issues, "mode:light_structural_effect")

    def test_medium_paragraph_move_fails(self):
        candidate = unchanged_candidate(self.source)
        candidate["paragraphs"].reverse()
        refresh_document(candidate)
        contract = make_contract(self.source, mode="medium", allowed=["paragraph_move"])
        inventory = build_inventory(self.source, candidate)
        manifest = make_manifest(self.source, candidate, contract, inventory, operation="paragraph_move")
        issues = self.semantic_issues(self.source, candidate, contract, manifest, make_queries(self.source, candidate))
        self.assert_code(issues, "mode:medium_structural_effect")

    def test_caller_workflow_cannot_mint_author_approval(self):
        contract, _, manifest, queries = self.package(origin="calling_workflow", state="author_approved")
        issues = self.semantic_issues(self.source, self.candidate, contract, manifest, queries)
        self.assert_code(issues, "authorization:origin_state")
        self.assert_code(issues, "authorization:caller_mint")

    def test_unresolved_blocking_query_rejects_changed_unit(self):
        contract, _, manifest, queries = self.package()
        queries["queries"] = [{
            "query_id": "query:blocking:1",
            "query_class": "missing_reporting",
            "question": "What dose was used?",
            "affected_unit_ids": ["paragraph:results:1"],
            "affected_locators": [self.source["paragraphs"][0]["locator"]],
            "blocks_revision": True,
            "resolution_status": "unresolved",
        }]
        issues = self.semantic_issues(self.source, self.candidate, contract, manifest, queries)
        self.assert_code(issues, "query:blocking_unit_changed")

    def test_unrelated_blocking_query_allows_other_unit(self):
        contract, _, manifest, queries = self.package()
        queries["queries"] = [{
            "query_id": "query:blocking:unrelated",
            "query_class": "author_judgment",
            "question": "Retain the Discussion wording?",
            "affected_unit_ids": ["paragraph:discussion:1"],
            "affected_locators": [self.source["paragraphs"][1]["locator"]],
            "blocks_revision": True,
            "resolution_status": "unresolved",
        }]
        self.assertEqual([], self.semantic_issues(self.source, self.candidate, contract, manifest, queries))

    def test_unmanifested_actual_change_fails(self):
        contract, _, manifest, queries = self.package()
        manifest["changes"] = []
        issues = self.semantic_issues(self.source, self.candidate, contract, manifest, queries)
        self.assert_code(issues, "manifest:unmanifested_change")

    def test_manifest_record_without_actual_diff_fails(self):
        contract, inventory, manifest, _ = self.package()
        candidate = unchanged_candidate(self.source)
        manifest["candidate_artifact"] = artifact_identity(candidate)
        manifest["changes"][0]["inventory_change_id"] = inventory["changed_units"][0]["inventory_change_id"]
        queries = make_queries(self.source, candidate)
        issues = self.semantic_issues(self.source, candidate, contract, manifest, queries)
        self.assert_code(issues, "manifest:no_actual_diff")

    def test_unauthorized_operation_fails(self):
        contract, inventory, _, queries = self.package(allowed=["syntax"])
        manifest = make_manifest(self.source, self.candidate, contract, inventory, operation="grammar")
        self.assert_code(
            self.semantic_issues(self.source, self.candidate, contract, manifest, queries),
            "operation:not_allowed",
        )

    def test_out_of_scope_change_fails(self):
        contract, inventory, _, queries = self.package(scope=["paragraph:discussion:1"])
        manifest = make_manifest(self.source, self.candidate, contract, inventory)
        self.assert_code(
            self.semantic_issues(self.source, self.candidate, contract, manifest, queries),
            "scope:outside_authorized",
        )

    def test_profile_alignment_requires_feature_reference(self):
        contract, inventory, _, queries = self.package()
        manifest = make_manifest(self.source, self.candidate, contract, inventory, rationale="profile_alignment")
        self.assert_code(
            self.semantic_issues(self.source, self.candidate, contract, manifest, queries),
            "profile:missing_feature_ref",
        )
        manifest["changes"][0]["profile_feature_ref"] = {
            "profile_id": "structure-profile:invented",
            "profile_version": "0.2.2",
            "profile_sha256": "a" * 64,
            "feature_id": "feature:invented",
            "feature_support_ref": "/feature_support/feature:invented",
        }
        self.assert_code(
            self.semantic_issues(self.source, self.candidate, contract, manifest, queries),
            "profile:unbound_feature",
        )

        profile = minimal_approved_structure_profile()
        reference = make_upstream_ref(profile)
        manifest = make_manifest(
            self.source,
            self.candidate,
            contract,
            inventory,
            rationale="profile_alignment",
            upstream_refs=[reference],
        )
        feature_id = "results.marker_rate.figure_reference"
        manifest["changes"][0]["profile_feature_ref"] = {
            "profile_id": profile["artifact_id"],
            "profile_version": profile["schema_version"],
            "profile_sha256": canonical_sha256(profile),
            "feature_id": feature_id,
            "feature_support_ref": f"/feature_support/{feature_id}",
        }
        self.assertEqual([], self.semantic_issues(
            self.source,
            self.candidate,
            contract,
            manifest,
            queries,
            upstream_index(profile),
        ))

        manifest["changes"][0]["profile_feature_ref"]["profile_sha256"] = "b" * 64
        self.assert_code(
            self.semantic_issues(
                self.source,
                self.candidate,
                contract,
                manifest,
                queries,
                upstream_index(profile),
            ),
            "profile:unbound_feature",
        )

        manifest["changes"][0]["profile_feature_ref"]["profile_sha256"] = canonical_sha256(profile)
        manifest["changes"][0]["upstream_artifact_refs"][0]["artifact_sha256"] = "c" * 64
        mismatched = self.semantic_issues(
            self.source,
            self.candidate,
            contract,
            manifest,
            queries,
            upstream_index(profile),
        )
        self.assert_code(mismatched, "upstream:identity_mismatch")
        self.assert_code(mismatched, "profile:unbound_feature")

    def test_topic_sentence_repair_requires_proposition(self):
        contract, inventory, _, queries = self.package(
            mode="medium", allowed=["topic_sentence_repair"]
        )
        manifest = make_manifest(self.source, self.candidate, contract, inventory, operation="topic_sentence_repair")
        issues = self.semantic_issues(self.source, self.candidate, contract, manifest, queries)
        self.assert_code(issues, "topic_sentence:missing_proposition")
        manifest["changes"][0]["source_proposition_ids"] = ["claim:invented"]
        self.assert_code(
            self.semantic_issues(self.source, self.candidate, contract, manifest, queries),
            "topic_sentence:unresolved_proposition",
        )

        claim_map = approved_claim_evidence_map(self.source["document_id"])
        manifest = make_manifest(
            self.source,
            self.candidate,
            contract,
            inventory,
            operation="topic_sentence_repair",
            upstream_refs=[make_upstream_ref(claim_map)],
        )
        manifest["changes"][0]["source_proposition_ids"] = ["claim:result-1"]
        self.assertEqual([], self.semantic_issues(
            self.source,
            self.candidate,
            contract,
            manifest,
            queries,
            upstream_index(claim_map),
        ))

        claim_map["claim_records"][0]["source_locators"][0]["paragraph_id"] = "paragraph:discussion:1"
        manifest["changes"][0]["upstream_artifact_refs"] = [make_upstream_ref(claim_map)]
        self.assert_code(
            self.semantic_issues(
                self.source,
                self.candidate,
                contract,
                manifest,
                queries,
                upstream_index(claim_map),
            ),
            "topic_sentence:unresolved_proposition",
        )

    def test_contract_hash_mismatch_fails(self):
        contract, _, manifest, queries = self.package()
        contract["contract_sha256"] = "f" * 64
        issues = self.semantic_issues(self.source, self.candidate, contract, manifest, queries)
        self.assert_code(issues, "contract:hash")

    def test_medium_results_reorder_requires_approved_plan(self):
        candidate = unchanged_candidate(self.source)
        paragraph = candidate["paragraphs"][0]
        paragraph["sentences"].reverse()
        refresh_document(candidate)
        contract = make_contract(self.source, mode="medium", allowed=["sentence_reorder"])
        inventory = build_inventory(self.source, candidate)
        manifest = make_manifest(self.source, candidate, contract, inventory, operation="sentence_reorder")
        manifest["changes"][0]["source_proposition_ids"] = ["claim:result-1"]
        queries = make_queries(self.source, candidate)
        issues = self.semantic_issues(self.source, candidate, contract, manifest, queries)
        self.assert_code(issues, "medium:missing_approved_baseline")

    def test_information_reorder_requires_exact_approved_relation_closure(self):
        contract, inventory, _, queries = self.package(
            mode="medium", allowed=["information_reorder"]
        )
        manifest = make_manifest(
            self.source,
            self.candidate,
            contract,
            inventory,
            operation="information_reorder",
        )
        manifest["changes"][0]["source_proposition_ids"] = ["claim:result-1"]
        self.assert_code(
            self.semantic_issues(self.source, self.candidate, contract, manifest, queries),
            "medium:missing_approved_baseline",
        )

        plan = approved_phase4_plan(self.source["document_id"])
        claim_map = approved_claim_evidence_map(self.source["document_id"])
        refs = [make_upstream_ref(plan), make_upstream_ref(claim_map)]
        manifest["changes"][0]["upstream_artifact_refs"] = refs
        self.assertEqual([], self.semantic_issues(
            self.source,
            self.candidate,
            contract,
            manifest,
            queries,
            upstream_index(plan, claim_map),
        ))

        claim_map["claim_evidence_links"][0]["author_approval"] = "pending"
        manifest["changes"][0]["upstream_artifact_refs"] = [
            make_upstream_ref(plan), make_upstream_ref(claim_map)
        ]
        self.assert_code(
            self.semantic_issues(
                self.source,
                self.candidate,
                contract,
                manifest,
                queries,
                upstream_index(plan, claim_map),
            ),
            "medium:missing_approved_baseline",
        )

    def test_information_reorder_rejects_pending_target_claim(self):
        contract, inventory, _, queries = self.package(
            mode="medium", allowed=["information_reorder"]
        )
        plan = approved_phase4_plan(self.source["document_id"])
        claim_map = approved_claim_evidence_map(self.source["document_id"])
        target = next(
            item for item in claim_map["claim_records"]
            if item["claim_id"] == "claim:result-1"
        )
        target["author_approval"] = "pending"
        manifest = make_manifest(
            self.source,
            self.candidate,
            contract,
            inventory,
            operation="information_reorder",
            upstream_refs=[make_upstream_ref(plan), make_upstream_ref(claim_map)],
        )
        manifest["changes"][0]["source_proposition_ids"] = ["claim:result-1"]
        self.assert_code(
            self.semantic_issues(
                self.source,
                self.candidate,
                contract,
                manifest,
                queries,
                upstream_index(plan, claim_map),
            ),
            "medium:missing_approved_baseline",
        )

    def test_information_reorder_rejects_inconsistent_plan_approval_summary(self):
        contract, inventory, _, queries = self.package(
            mode="medium", allowed=["information_reorder"]
        )
        plan = approved_phase4_plan(self.source["document_id"])
        plan["approval_summary"].update({
            "overall_status": "pending",
            "pending_decision_count": 1,
        })
        claim_map = approved_claim_evidence_map(self.source["document_id"])
        manifest = make_manifest(
            self.source,
            self.candidate,
            contract,
            inventory,
            operation="information_reorder",
            upstream_refs=[make_upstream_ref(plan), make_upstream_ref(claim_map)],
        )
        manifest["changes"][0]["source_proposition_ids"] = ["claim:result-1"]
        self.assert_code(
            self.semantic_issues(
                self.source,
                self.candidate,
                contract,
                manifest,
                queries,
                upstream_index(plan, claim_map),
            ),
            "medium:missing_approved_baseline",
        )

    def assert_information_reorder_rejects_authority_mutation(
        self,
        artifact: str,
        mutate: Any,
    ) -> None:
        contract, inventory, _, queries = self.package(
            mode="medium", allowed=["information_reorder"]
        )
        plan = approved_phase4_plan(self.source["document_id"])
        claim_map = approved_claim_evidence_map(self.source["document_id"])
        mutate(plan if artifact == "plan" else claim_map)
        manifest = make_manifest(
            self.source,
            self.candidate,
            contract,
            inventory,
            operation="information_reorder",
            upstream_refs=[make_upstream_ref(plan), make_upstream_ref(claim_map)],
        )
        manifest["changes"][0]["source_proposition_ids"] = ["claim:result-1"]
        self.assert_code(
            self.semantic_issues(
                self.source,
                self.candidate,
                contract,
                manifest,
                queries,
                upstream_index(plan, claim_map),
            ),
            "medium:missing_approved_baseline",
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

    def test_light_declared_medium_operations_fail_independent_core_validation(self):
        for operation in ("information_reorder", "topic_sentence_repair"):
            with self.subTest(operation=operation):
                contract, inventory, _, queries = self.package(
                    mode="light", allowed=[operation]
                )
                manifest = make_manifest(
                    self.source,
                    self.candidate,
                    contract,
                    inventory,
                    operation=operation,
                )
                if operation == "topic_sentence_repair":
                    manifest["changes"][0]["source_proposition_ids"] = ["claim:invented"]
                self.assert_code(
                    self.semantic_issues(
                        self.source, self.candidate, contract, manifest, queries
                    ),
                    "mode:light_structural_effect",
                )

    def test_medium_proposition_must_belong_to_affected_paragraph_plan(self):
        candidate = unchanged_candidate(self.source)
        candidate["paragraphs"][0]["sentences"].reverse()
        refresh_document(candidate)
        contract = make_contract(self.source, mode="medium", allowed=["sentence_reorder"])
        inventory = build_inventory(self.source, candidate)
        queries = make_queries(self.source, candidate)
        plan = approved_phase4_plan(self.source["document_id"])
        claim_map = approved_claim_evidence_map(self.source["document_id"])
        for section in plan["section_plans"]:
            if section["canonical_section"] == "discussion":
                section["paragraph_plans"][0]["claim_ids"] = ["claim:unrelated-2"]
                section["paragraph_plans"][0]["evidence_ids"] = ["evidence:unrelated-2"]
        manifest = make_manifest(
            self.source, candidate, contract, inventory,
            operation="sentence_reorder",
            upstream_refs=[make_upstream_ref(plan), make_upstream_ref(claim_map)],
        )
        manifest["changes"][0]["source_proposition_ids"] = ["claim:unrelated-2"]
        issues = self.semantic_issues(
            self.source, candidate, contract, manifest, make_queries(self.source, candidate),
            upstream_index(plan, claim_map),
        )
        self.assert_code(issues, "medium:missing_approved_baseline")

        plan = approved_phase4_plan(self.source["document_id"])
        claim_map = approved_claim_evidence_map(self.source["document_id"])
        manifest = make_manifest(
            self.source, candidate, contract, inventory,
            operation="sentence_reorder",
            upstream_refs=[make_upstream_ref(plan), make_upstream_ref(claim_map)],
        )
        manifest["changes"][0]["source_proposition_ids"] = ["claim:result-1"]
        self.assertEqual([], self.semantic_issues(
            self.source, candidate, contract, manifest, queries,
            upstream_index(plan, claim_map),
        ))

        for section in plan["section_plans"]:
            if section["canonical_section"] == "results":
                section["paragraph_plans"][0]["claim_ids"] = []
                section["paragraph_plans"][0]["evidence_ids"] = []
        manifest = make_manifest(
            self.source, candidate, contract, inventory,
            operation="sentence_reorder",
            upstream_refs=[make_upstream_ref(plan), make_upstream_ref(claim_map)],
        )
        manifest["changes"][0]["source_proposition_ids"] = ["claim:result-1"]
        issues = self.semantic_issues(
            self.source, candidate, contract, manifest, queries,
            upstream_index(plan, claim_map),
        )
        self.assert_code(issues, "medium:missing_approved_baseline")

    def test_deep_move_requires_exact_artifact_closure(self):
        candidate = unchanged_candidate(self.source)
        candidate["paragraphs"].reverse()
        refresh_document(candidate)
        plan = approved_phase4_plan()
        structural_id = plan["author_decisions"][0]["decision_id"]
        authorization = {
            "structural_change_id": structural_id,
            "allowed_effects": ["paragraph_move"],
            "source_unit_ids": [item["unit_id"] for item in self.source["paragraphs"]],
            "candidate_unit_ids": [item["unit_id"] for item in candidate["paragraphs"]],
            "required_upstream_artifact_ids": [plan["artifact_id"]],
            "author_approval": "approved",
        }
        contract = make_contract(
            self.source,
            mode="deep",
            allowed=["paragraph_move"],
            origin="author",
            state="author_approved",
            structural_authorizations=[authorization],
        )
        inventory = build_inventory(self.source, candidate)
        queries = make_queries(self.source, candidate)
        manifest = make_manifest(
            self.source, candidate, contract, inventory,
            operation="paragraph_move", structural_change_ids=[structural_id],
        )
        issues = self.semantic_issues(self.source, candidate, contract, manifest, queries)
        self.assert_code(issues, "deep:authorization_closure")

        reference = make_upstream_ref(plan)
        manifest = make_manifest(
            self.source, candidate, contract, inventory,
            operation="paragraph_move", structural_change_ids=[structural_id],
            upstream_refs=[reference],
        )
        self.assertEqual([], self.semantic_issues(
            self.source, candidate, contract, manifest, queries, upstream_index(plan),
        ))

    def test_deep_rejects_structural_id_not_present_in_plan(self):
        candidate = unchanged_candidate(self.source)
        candidate["paragraphs"].reverse()
        refresh_document(candidate)
        plan = approved_phase4_plan()
        false_id = "decision:not-present-in-plan"
        authorization = {
            "structural_change_id": false_id,
            "allowed_effects": ["paragraph_move"],
            "source_unit_ids": [item["unit_id"] for item in self.source["paragraphs"]],
            "candidate_unit_ids": [item["unit_id"] for item in candidate["paragraphs"]],
            "required_upstream_artifact_ids": [plan["artifact_id"]],
            "author_approval": "approved",
        }
        contract = make_contract(
            self.source, mode="deep", allowed=["paragraph_move"], origin="author",
            state="author_approved", structural_authorizations=[authorization],
        )
        inventory = build_inventory(self.source, candidate)
        manifest = make_manifest(
            self.source, candidate, contract, inventory, operation="paragraph_move",
            structural_change_ids=[false_id], upstream_refs=[make_upstream_ref(plan)],
        )
        issues = self.semantic_issues(
            self.source, candidate, contract, manifest, make_queries(self.source, candidate),
            upstream_index(plan),
        )
        self.assert_code(issues, "deep:authorization_closure")

    def test_deep_claim_and_boundary_references_require_richer_artifacts(self):
        candidate = unchanged_candidate(self.source)
        candidate["paragraphs"].reverse()
        refresh_document(candidate)
        for referenced_id in ("claim:result-1", "boundary:interpretation-1"):
            with self.subTest(referenced_id=referenced_id):
                plan = approved_phase4_plan()
                plan["author_decisions"][0]["related_ids"].append(referenced_id)
                structural_id = plan["author_decisions"][0]["decision_id"]
                authorization = {
                    "structural_change_id": structural_id,
                    "allowed_effects": ["paragraph_move"],
                    "source_unit_ids": [item["unit_id"] for item in self.source["paragraphs"]],
                    "candidate_unit_ids": [item["unit_id"] for item in candidate["paragraphs"]],
                    "required_upstream_artifact_ids": [plan["artifact_id"]],
                    "author_approval": "approved",
                }
                contract = make_contract(
                    self.source, mode="deep", allowed=["paragraph_move"], origin="author",
                    state="author_approved", structural_authorizations=[authorization],
                )
                inventory = build_inventory(self.source, candidate)
                manifest = make_manifest(
                    self.source, candidate, contract, inventory, operation="paragraph_move",
                    structural_change_ids=[structural_id], upstream_refs=[make_upstream_ref(plan)],
                )
                issues = self.semantic_issues(
                    self.source, candidate, contract, manifest, make_queries(self.source, candidate),
                    upstream_index(plan),
                )
                self.assert_code(issues, "deep:authorization_closure")

    def deep_reference_issues(
        self,
        referenced_id: str,
        cards: list[dict[str, Any]],
        tamper_card_hash: bool = False,
        plan_override: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        candidate = unchanged_candidate(self.source)
        candidate["paragraphs"].reverse()
        refresh_document(candidate)
        plan = (
            copy.deepcopy(plan_override)
            if plan_override is not None
            else approved_phase4_plan(self.source["document_id"])
        )
        plan["author_decisions"][0]["related_ids"].append(referenced_id)
        structural_id = plan["author_decisions"][0]["decision_id"]
        authorization = {
            "structural_change_id": structural_id,
            "allowed_effects": ["paragraph_move"],
            "source_unit_ids": [item["unit_id"] for item in self.source["paragraphs"]],
            "candidate_unit_ids": [item["unit_id"] for item in candidate["paragraphs"]],
            "required_upstream_artifact_ids": [plan["artifact_id"]],
            "author_approval": "approved",
        }
        contract = make_contract(
            self.source,
            mode="deep",
            allowed=["paragraph_move"],
            origin="author",
            state="author_approved",
            structural_authorizations=[authorization],
        )
        inventory = build_inventory(self.source, candidate)
        artifacts = [plan, *cards]
        manifest = make_manifest(
            self.source,
            candidate,
            contract,
            inventory,
            operation="paragraph_move",
            structural_change_ids=[structural_id],
            upstream_refs=[make_upstream_ref(item) for item in artifacts],
        )
        if tamper_card_hash:
            manifest["changes"][0]["upstream_artifact_refs"][-1]["artifact_sha256"] = "0" * 64
        return self.semantic_issues(
            self.source,
            candidate,
            contract,
            manifest,
            make_queries(self.source, candidate),
            upstream_index(*artifacts),
        )

    def test_deep_direct_card_rejects_pending_boundary_approval(self):
        card = approved_interpretation_card(self.source["document_id"])
        card["boundary"]["author_approval"] = "pending"
        self.assert_code(
            self.deep_reference_issues(card["artifact_id"], [card]),
            "deep:authorization_closure",
        )

    def test_deep_direct_card_rejects_pending_author_decision(self):
        card = approved_interpretation_card(self.source["document_id"])
        card["author_decisions"][0]["status"] = "pending"
        self.assert_code(
            self.deep_reference_issues(card["artifact_id"], [card]),
            "deep:authorization_closure",
        )

    def test_deep_boundary_rejects_rogue_unreferenced_card(self):
        card = approved_interpretation_card("other-manuscript")
        card["artifact_id"] = "interpretation-card:rogue"
        card["card_id"] = "card:rogue"
        self.assert_code(
            self.deep_reference_issues(card["boundary"]["boundary_id"], [card]),
            "deep:authorization_closure",
        )

    def test_deep_boundary_rejects_plan_card_for_wrong_manuscript(self):
        card = approved_interpretation_card("other-manuscript")
        self.assert_code(
            self.deep_reference_issues(card["boundary"]["boundary_id"], [card]),
            "deep:authorization_closure",
        )

    def test_deep_boundary_accepts_exact_consistent_plan_card(self):
        card = approved_interpretation_card(self.source["document_id"])
        self.assertEqual(
            [],
            self.deep_reference_issues(card["boundary"]["boundary_id"], [card]),
        )

    def test_deep_non_key_boundary_rejects_missing_planned_card(self):
        plan = approved_phase4_plan(self.source["document_id"])
        card = second_approved_interpretation_card(self.source["document_id"])
        plan["interpretation_card_ids"].append(card["artifact_id"])
        plan["source_artifact_ids"].append(card["artifact_id"])
        self.assertNotIn(
            card["boundary"]["boundary_id"],
            plan["story_anchors"]["key_boundary_ids"],
        )
        self.assert_code(
            self.deep_reference_issues(
                card["boundary"]["boundary_id"], [], plan_override=plan
            ),
            "deep:authorization_closure",
        )

    def test_deep_non_key_boundary_accepts_exact_planned_card(self):
        plan = approved_phase4_plan(self.source["document_id"])
        card = second_approved_interpretation_card(self.source["document_id"])
        plan["interpretation_card_ids"].append(card["artifact_id"])
        plan["source_artifact_ids"].append(card["artifact_id"])
        self.assertNotIn(
            card["boundary"]["boundary_id"],
            plan["story_anchors"]["key_boundary_ids"],
        )
        self.assertEqual(
            [],
            self.deep_reference_issues(
                card["boundary"]["boundary_id"], [card], plan_override=plan
            ),
        )

    def test_deep_boundary_rejects_card_reference_hash_mismatch(self):
        card = approved_interpretation_card(self.source["document_id"])
        self.assert_code(
            self.deep_reference_issues(
                card["boundary"]["boundary_id"], [card], tamper_card_hash=True
            ),
            "upstream:identity_mismatch",
        )
        self.assert_code(
            self.deep_reference_issues(
                card["boundary"]["boundary_id"], [card], tamper_card_hash=True
            ),
            "deep:authorization_closure",
        )

    def test_deep_section_membership_change_is_unsupported(self):
        candidate = unchanged_candidate(self.source)
        candidate["paragraphs"][0]["section"] = "discussion"
        refresh_document(candidate)
        contract = make_contract(
            self.source, mode="deep", allowed=["paragraph_move"], origin="author",
            state="author_approved",
        )
        inventory = build_inventory(self.source, candidate)
        manifest = make_manifest(self.source, candidate, contract, inventory, operation="paragraph_move")
        issues = self.semantic_issues(
            self.source, candidate, contract, manifest, make_queries(self.source, candidate),
        )
        self.assert_code(issues, "mode:deep_section_move_unsupported")

    def test_approved_phase4_plan_remains_schema_valid(self):
        validator = _load_validator(DEFAULT_VALIDATOR)
        plan = approved_phase4_plan()
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "plan.json"
            write_json(path, plan)
            self.assertEqual([], _schema_issues(validator, PHASE4_SCHEMAS["manuscript_plan"], path))

    def test_declarative_negative_fixture_matrix_is_covered(self):
        cases = read_fixture("negative-cases.json")
        required = {
            "mislabelled_sentence_reorder_as_grammar", "light_sentence_reorder",
            "medium_paragraph_move", "calling_workflow_mints_author_approval",
            "unresolved_blocking_query_changed", "unmanifested_actual_change",
            "manifest_without_actual_diff", "deep_missing_artifact_closure",
            "deep_structural_id_absent_from_plan", "deep_section_membership_change",
        }
        self.assertEqual(required, {item["case"] for item in cases})
        self.assertTrue(all(item["expected_code"] for item in cases))

    def test_cli_smoke_valid_and_mislabelled_negative(self):
        contract, _, manifest, queries = self.package()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            paths = {
                "source": directory / "source.json",
                "candidate": directory / "candidate.json",
                "lineage": directory / "lineage.json",
                "contract": directory / "contract.json",
                "manifest": directory / "manifest.json",
                "queries": directory / "queries.json",
                "inventory": directory / "inventory.json",
            }
            for key, value in (
                ("source", self.source), ("candidate", self.candidate),
                ("lineage", trusted_lineage_map(self.source, self.candidate)), ("contract", contract),
                ("manifest", manifest), ("queries", queries),
            ):
                write_json(paths[key], value)
            command = [
                sys.executable, "-B", str(SCRIPTS / "validate_revision_package.py"),
                "--source-document", str(paths["source"]),
                "--candidate-document", str(paths["candidate"]),
                "--lineage-map", str(paths["lineage"]),
                "--revision-contract", str(paths["contract"]),
                "--change-manifest", str(paths["manifest"]),
                "--author-queries", str(paths["queries"]),
                "--write-inventory", str(paths["inventory"]),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertTrue(paths["inventory"].is_file())

            bad_candidate = unchanged_candidate(self.source)
            paragraph = bad_candidate["paragraphs"][0]
            paragraph["sentences"].reverse()
            paragraph["sentences"][0]["source_unit_ids"] = ["sentence:results:1"]
            paragraph["sentences"][1]["source_unit_ids"] = ["sentence:results:2"]
            refresh_document(bad_candidate)
            bad_contract = make_contract(self.source, mode="light", allowed=["grammar"])
            bad_inventory = build_inventory(self.source, bad_candidate)
            bad_manifest = make_manifest(self.source, bad_candidate, bad_contract, bad_inventory, operation="grammar")
            bad_queries = make_queries(self.source, bad_candidate)
            for key, value in (
                ("candidate", bad_candidate),
                ("lineage", trusted_lineage_map(self.source, bad_candidate)),
                ("contract", bad_contract),
                ("manifest", bad_manifest), ("queries", bad_queries),
            ):
                write_json(paths[key], value)
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(1, completed.returncode)
            self.assertIn("operation:mislabelled_structural_change", completed.stdout)

    def test_change_inventory_cli_smoke(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            source_path = directory / "source.json"
            candidate_path = directory / "candidate.json"
            lineage_path = directory / "lineage.json"
            output_path = directory / "inventory.json"
            write_json(source_path, self.source)
            write_json(candidate_path, self.candidate)
            write_json(lineage_path, trusted_lineage_map(self.source, self.candidate))
            completed = subprocess.run(
                [
                    sys.executable, "-B", str(SCRIPTS / "build_change_inventory.py"),
                    "--source-document", str(source_path),
                    "--candidate-document", str(candidate_path),
                    "--lineage-map", str(lineage_path),
                    "--output", str(output_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            inventory = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(1, len(inventory["changed_units"]))


if __name__ == "__main__":
    unittest.main()
