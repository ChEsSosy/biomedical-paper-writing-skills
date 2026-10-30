#!/usr/bin/env python3
"""Synthetic positive, negative, semantic, and CLI tests for the minimum QC gate."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCHEMAS = ROOT / "schemas"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

from qc_gate_core import (  # noqa: E402
    build_manifest,
    build_snapshot,
    compare_snapshots,
    validate_package_semantics,
    write_json,
)
from schema_runtime import validate_file  # noqa: E402


class MinimumQCGateTests(unittest.TestCase):
    def pair(
        self,
        source_name: str,
        candidate_name: str,
        protected: list[str],
        producer: str = "arbitrary_user_comparison",
    ):
        document_id = source_name.removesuffix(".txt").replace("_source", "")
        source = build_snapshot(FIXTURES / source_name, "source", document_id)
        candidate = build_snapshot(FIXTURES / candidate_name, "candidate", document_id)
        manifest = build_manifest(source, candidate, producer=producer, accept_one_to_one=True)
        manifest["protected_categories"] = protected
        return manifest, source, candidate

    def test_format_normalization_is_clean_pass_and_artifacts_validate(self):
        manifest, source, candidate = self.pair(
            "format_source.txt", "format_candidate.txt",
            ["numeric", "citation", "reference", "semantic_signal"],
        )
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("pass", report["gate_outcome"])
        self.assertFalse(report["human_review_required"])
        self.assertEqual("draft", report["status"])
        self.assertEqual([], findings)
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            jobs = [
                ("comparison-manifest.schema.json", manifest),
                ("preservation-snapshot.schema.json", source),
                ("preservation-snapshot.schema.json", candidate),
                ("qc-report.schema.json", report),
            ]
            for index, (schema_name, value) in enumerate(jobs):
                data_path = directory / f"artifact-{index}.json"
                write_json(data_path, value)
                self.assertEqual([], validate_file(SCHEMAS / schema_name, data_path))

    def test_numeric_change_is_failure(self):
        manifest, source, candidate = self.pair("numeric_source.txt", "numeric_candidate.txt", ["numeric"])
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("fail", report["gate_outcome"])
        self.assertTrue(any(item["finding_class"] == "numeric" for item in findings))

    def test_comparator_change_is_failure(self):
        manifest, source, candidate = self.pair("p_source.txt", "p_candidate.txt", ["numeric"])
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("fail", report["gate_outcome"])
        self.assertTrue(any(item.get("expected_representation") == "P < 0.05" for item in findings))

    def test_unit_conversion_is_not_automatic(self):
        manifest, source, candidate = self.pair("unit_source.txt", "unit_candidate.txt", ["numeric"])
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("fail", report["gate_outcome"])
        self.assertTrue(any(item.get("expected_representation") == "1000 ng" for item in findings))

    def test_citation_and_reference_changes_fail(self):
        manifest, source, candidate = self.pair(
            "citation_source.txt", "citation_candidate.txt", ["citation", "reference"]
        )
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("fail", report["gate_outcome"])
        self.assertEqual({"citation", "reference"}, {item["finding_class"] for item in findings})

    def test_semantic_lexical_change_is_warning_not_verdict(self):
        manifest, source, candidate = self.pair(
            "semantic_source.txt", "semantic_candidate.txt", ["semantic_signal"]
        )
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("pass_with_warnings", report["gate_outcome"])
        self.assertTrue(report["human_review_required"])
        self.assertEqual(["semantic_signal"], [item["finding_class"] for item in findings])

    def test_direction_role_swap_is_warning_not_false_pass(self):
        manifest, source, candidate = self.pair(
            "direction_swap_source.txt", "direction_swap_candidate.txt", ["semantic_signal"]
        )
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("pass_with_warnings", report["gate_outcome"])
        self.assertTrue(any("semantic-risk signals changed" in item["message"] for item in findings))

    def test_negation_scope_swap_is_warning_not_false_pass(self):
        manifest, source, candidate = self.pair(
            "negation_swap_source.txt", "negation_swap_candidate.txt", ["semantic_signal"]
        )
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("pass_with_warnings", report["gate_outcome"])
        self.assertTrue(report["human_review_required"])

    def test_reference_namespace_changes_fail(self):
        cases = [
            ("supplementary_reference_source.txt", "supplementary_reference_candidate.txt"),
            ("extended_reference_source.txt", "extended_reference_candidate.txt"),
        ]
        for source_name, candidate_name in cases:
            with self.subTest(source=source_name):
                manifest, source, candidate = self.pair(source_name, candidate_name, ["reference"])
                findings, report = compare_snapshots(manifest, source, candidate)
                self.assertEqual("fail", report["gate_outcome"])
                self.assertTrue(any(item["finding_class"] == "reference" for item in findings))

    def test_section_and_appendix_identity_changes_fail(self):
        manifest, source, candidate = self.pair(
            "section_appendix_source.txt", "section_appendix_candidate.txt", ["reference"]
        )
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("fail", report["gate_outcome"])
        self.assertEqual(2, sum(item["finding_class"] == "reference" for item in findings))

    def test_author_year_citation_change_fails(self):
        manifest, source, candidate = self.pair(
            "author_year_source.txt", "author_year_candidate.txt", ["citation"]
        )
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("fail", report["gate_outcome"])
        self.assertTrue(any(item["finding_class"] == "citation" for item in findings))

    def test_declared_terminology_case_mode_is_honored(self):
        document_id = "terminology-case"
        sensitive = [{"term": "IL1R1", "match_mode": "case_sensitive"}]
        source = build_snapshot(FIXTURES / "terminology_source.txt", "source", document_id, terminology_terms=sensitive)
        candidate = build_snapshot(FIXTURES / "terminology_candidate.txt", "candidate", document_id, terminology_terms=sensitive)
        manifest = build_manifest(source, candidate, accept_one_to_one=True)
        manifest["protected_categories"] = ["terminology"]
        _, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("fail", report["gate_outcome"])

        insensitive = [{"term": "IL1R1", "match_mode": "case_insensitive"}]
        source = build_snapshot(FIXTURES / "terminology_source.txt", "source", document_id, terminology_terms=insensitive)
        candidate = build_snapshot(FIXTURES / "terminology_candidate.txt", "candidate", document_id, terminology_terms=insensitive)
        manifest = build_manifest(source, candidate, accept_one_to_one=True)
        manifest["protected_categories"] = ["terminology"]
        _, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("pass", report["gate_outcome"])

    def test_unsupported_structural_transform_is_unassessable(self):
        manifest, source, candidate = self.pair(
            "split_source.txt", "split_candidate.txt", ["semantic_signal"]
        )
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("unassessable", report["gate_outcome"])
        self.assertTrue(any(item["execution_state"] == "unassessable" for item in findings))

    def test_pending_ordinal_alignment_is_not_auto_approved(self):
        document_id = "pending-alignment"
        source = build_snapshot(FIXTURES / "numeric_source.txt", "source", document_id)
        candidate = build_snapshot(FIXTURES / "numeric_source.txt", "candidate", document_id)
        manifest = build_manifest(source, candidate)
        self.assertEqual("machine_proposed", manifest["unit_alignments"][0]["review_status"])
        self.assertEqual("author_review_required", manifest["status"])
        _, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("unassessable", report["gate_outcome"])

    def test_caller_acceptance_never_approves_manifest(self):
        document_id = "caller-acceptance"
        source = build_snapshot(FIXTURES / "numeric_source.txt", "source", document_id)
        candidate = build_snapshot(FIXTURES / "numeric_source.txt", "candidate", document_id)
        manifest = build_manifest(source, candidate, accept_one_to_one=True)
        self.assertEqual("caller_accepted", manifest["unit_alignments"][0]["review_status"])
        self.assertEqual("author_review_required", manifest["status"])

    def test_declared_but_unimplemented_category_is_unassessable(self):
        manifest, source, candidate = self.pair(
            "numeric_source.txt", "numeric_source.txt", ["graph_identity"]
        )
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("unassessable", report["gate_outcome"])
        self.assertTrue(any("not deterministically extractable" in item["message"] for item in findings))

    def test_article_polisher_requires_revision_contract(self):
        manifest, source, candidate = self.pair(
            "numeric_source.txt", "numeric_source.txt", ["numeric"], producer="article_polisher"
        )
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("fail", report["gate_outcome"])
        self.assertTrue(any("requires revision_contract" in item["message"] for item in findings))

    def test_approved_revision_contract_allows_article_polisher_comparison(self):
        document_id = "approved-revision"
        source = build_snapshot(FIXTURES / "numeric_source.txt", "source", document_id)
        candidate = build_snapshot(FIXTURES / "numeric_source.txt", "candidate", document_id)
        revision_contract = {
            "revision_contract_id": "revision:approved:1",
            "revision_contract_version": "0.1.0",
            "contract_sha256": "a" * 64,
            "source_document_id": document_id,
            "source_artifact_id": source["file_identity"]["file_id"],
            "source_artifact_version": "1.0.0",
            "source_artifact_sha256": source["file_identity"]["sha256"],
            "revision_mode": "light",
            "authorized_scope": {
                "document_id": document_id,
                "unit_ids": [source["units"][0]["unit_id"]],
            },
            "allowed_operations": ["grammar", "syntax"],
            "prohibited_operations": ["change_numeric_anchor", "change_claim_scope"],
            "frozen_anchor_ids": [source["anchors"][0]["anchor_id"]],
            "approved_structural_change_ids": [],
            "structural_change_authorizations": [],
            "source_plan_id": "plan:approved:1",
            "comparison_scope": "All paragraph units",
            "authorization_origin": "author",
            "authorization_state": "author_approved",
            "author_approval": "approved",
        }
        manifest = build_manifest(
            source, candidate, producer="article_polisher",
            accept_one_to_one=True, revision_contract=revision_contract,
        )
        manifest["protected_categories"] = ["numeric"]
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual([], findings)
        self.assertEqual("pass", report["gate_outcome"])
        with tempfile.TemporaryDirectory() as raw:
            data_path = Path(raw) / "manifest.json"
            write_json(data_path, manifest)
            self.assertEqual([], validate_file(SCHEMAS / "comparison-manifest.schema.json", data_path))

    def test_caller_accepted_contract_allows_comparison_without_author_approval(self):
        document_id = "caller-accepted-revision"
        source = build_snapshot(FIXTURES / "numeric_source.txt", "source", document_id)
        candidate = build_snapshot(FIXTURES / "numeric_source.txt", "candidate", document_id)
        revision_contract = {
            "revision_contract_id": "revision:caller-accepted:1",
            "revision_contract_version": "0.1.0",
            "contract_sha256": "b" * 64,
            "source_document_id": document_id,
            "source_artifact_id": source["file_identity"]["file_id"],
            "source_artifact_version": "1.0.0",
            "source_artifact_sha256": source["file_identity"]["sha256"],
            "revision_mode": "light",
            "authorized_scope": {
                "document_id": document_id,
                "unit_ids": [source["units"][0]["unit_id"]],
            },
            "allowed_operations": ["grammar", "syntax"],
            "prohibited_operations": ["change_numeric_anchor", "change_claim_scope"],
            "frozen_anchor_ids": [source["anchors"][0]["anchor_id"]],
            "approved_structural_change_ids": [],
            "structural_change_authorizations": [],
            "comparison_scope": "All paragraph units",
            "authorization_origin": "calling_workflow",
            "authorization_state": "caller_accepted",
            "author_approval": "pending",
        }
        manifest = build_manifest(
            source, candidate, producer="article_polisher",
            accept_one_to_one=True, revision_contract=revision_contract,
        )
        manifest["protected_categories"] = ["numeric"]
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual([], findings)
        self.assertEqual("pass", report["gate_outcome"])
        self.assertEqual("author_review_required", manifest["status"])

    def test_exact_exception_is_version_bound(self):
        manifest, source, candidate = self.pair("numeric_source.txt", "numeric_candidate.txt", ["numeric"])
        source_anchor = next(item for item in source["anchors"] if item["anchor_class"] == "numeric")
        candidate_anchor = next(item for item in candidate["anchors"] if item["anchor_class"] == "numeric")
        exception = {
            "exception_id": "exception:10-to-20",
            "target_kind": "anchor_id",
            "anchor_id": source_anchor["anchor_id"],
            "expected_source_representation": source_anchor["raw_representation"],
            "approved_candidate_representation": candidate_anchor["raw_representation"],
            "source_sha256": source["file_identity"]["sha256"],
            "candidate_sha256": candidate["file_identity"]["sha256"],
            "candidate_anchor_sha256": candidate_anchor["anchor_sha256"],
            "reason": "Synthetic author-approved correction",
            "author_approval": "approved",
        }
        manifest["approved_exceptions"] = [exception]
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("pass", report["gate_outcome"])
        self.assertEqual("accepted", findings[0]["finding_status"])

        stale_manifest, stale_source, stale_candidate = self.pair(
            "numeric_source.txt", "numeric_unapproved_candidate.txt", ["numeric"]
        )
        stale_manifest["approved_exceptions"] = [exception]
        stale_findings, stale_report = compare_snapshots(stale_manifest, stale_source, stale_candidate)
        self.assertEqual("fail", stale_report["gate_outcome"])
        self.assertFalse(any(item.get("exception_id") == exception["exception_id"] for item in stale_findings))

    def test_review_required_upstream_cannot_be_hard_constraint(self):
        manifest, source, candidate = self.pair("numeric_source.txt", "numeric_source.txt", ["numeric"])
        manifest["upstream_baselines"] = [{
            "artifact_id": "upstream:1",
            "artifact_type": "manuscript_plan",
            "artifact_version": "0.1.0",
            "artifact_status": "author_review_required",
            "baseline_use": "hard_constraint",
        }]
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("fail", report["gate_outcome"])
        self.assertTrue(any(item["check_id"] == "upstream_baseline_semantics" for item in findings))

    def test_alignment_locator_binding_mismatch_fails(self):
        manifest, source, candidate = self.pair("numeric_source.txt", "numeric_source.txt", ["numeric"])
        manifest["unit_alignments"][0]["candidate_locators"][0]["unit_id"] = "candidate:unit:999"
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("fail", report["gate_outcome"])
        self.assertTrue(any("locator/unit binding mismatch" in item["message"] for item in findings))

    def test_wildcard_exception_is_rejected(self):
        manifest, source, candidate = self.pair("numeric_source.txt", "numeric_candidate.txt", ["numeric"])
        source_anchor = source["anchors"][0]
        candidate_anchor = candidate["anchors"][0]
        manifest["approved_exceptions"] = [{
            "exception_id": "exception:wildcard",
            "target_kind": "anchor_id",
            "anchor_id": source_anchor["anchor_id"],
            "expected_source_representation": "10*",
            "approved_candidate_representation": candidate_anchor["raw_representation"],
            "source_sha256": source["file_identity"]["sha256"],
            "candidate_sha256": candidate["file_identity"]["sha256"],
            "candidate_anchor_sha256": candidate_anchor["anchor_sha256"],
            "reason": "Must be rejected",
            "author_approval": "approved",
        }]
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual("fail", report["gate_outcome"])
        self.assertTrue(any("wildcard" in item["message"] for item in findings))

    def test_uncalibrated_confidence_is_schema_rejected(self):
        snapshot = build_snapshot(FIXTURES / "numeric_source.txt", "source", "confidence-test")
        snapshot["anchors"][0]["confidence"] = 0.9
        with tempfile.TemporaryDirectory() as raw:
            data_path = Path(raw) / "snapshot.json"
            write_json(data_path, snapshot)
            issues = validate_file(SCHEMAS / "preservation-snapshot.schema.json", data_path)
        self.assertTrue(any(item["keyword"] == "additionalProperties" for item in issues))

    def test_package_rejects_warning_without_human_review(self):
        manifest, source, candidate = self.pair(
            "semantic_source.txt", "semantic_candidate.txt", ["semantic_signal"]
        )
        findings, report = compare_snapshots(manifest, source, candidate)
        report["human_review_required"] = False
        errors = validate_package_semantics(manifest, source, candidate, findings, report)
        self.assertTrue(any("pass_with_warnings" in item for item in errors))

    def test_finding_schema_accepts_generated_failure(self):
        manifest, source, candidate = self.pair("numeric_source.txt", "numeric_candidate.txt", ["numeric"])
        findings, _ = compare_snapshots(manifest, source, candidate)
        with tempfile.TemporaryDirectory() as raw:
            data_path = Path(raw) / "finding.json"
            write_json(data_path, findings[0])
            self.assertEqual([], validate_file(SCHEMAS / "qc-finding.schema.json", data_path))

    def test_complete_warning_package_validates(self):
        manifest, source, candidate = self.pair(
            "semantic_source.txt", "semantic_candidate.txt", ["semantic_signal"]
        )
        findings, report = compare_snapshots(manifest, source, candidate)
        self.assertEqual([], validate_package_semantics(manifest, source, candidate, findings, report))
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            artifacts = [
                ("comparison-manifest.schema.json", manifest),
                ("preservation-snapshot.schema.json", source),
                ("preservation-snapshot.schema.json", candidate),
                ("qc-finding.schema.json", findings[0]),
                ("qc-report.schema.json", report),
            ]
            for index, (schema_name, value) in enumerate(artifacts):
                data_path = directory / f"artifact-{index}.json"
                write_json(data_path, value)
                self.assertEqual([], validate_file(SCHEMAS / schema_name, data_path))

    def test_cli_smoke(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            source_snapshot = directory / "source.json"
            candidate_snapshot = directory / "candidate.json"
            manifest = directory / "manifest.json"
            findings_dir = directory / "findings"
            report = directory / "report.json"
            rendered = directory / "report.md"
            commands = [
                [sys.executable, "-B", str(SCRIPTS / "extract_preservation_snapshot.py"), "--input", str(FIXTURES / "format_source.txt"), "--side", "source", "--document-id", "cli-test", "--output", str(source_snapshot)],
                [sys.executable, "-B", str(SCRIPTS / "extract_preservation_snapshot.py"), "--input", str(FIXTURES / "format_candidate.txt"), "--side", "candidate", "--document-id", "cli-test", "--output", str(candidate_snapshot)],
                [sys.executable, "-B", str(SCRIPTS / "create_comparison_manifest.py"), "--source-snapshot", str(source_snapshot), "--candidate-snapshot", str(candidate_snapshot), "--accept-one-to-one-for-comparison", "--output", str(manifest)],
                [sys.executable, "-B", str(SCRIPTS / "compare_preservation_snapshots.py"), "--manifest", str(manifest), "--source-snapshot", str(source_snapshot), "--candidate-snapshot", str(candidate_snapshot), "--findings-dir", str(findings_dir), "--report", str(report)],
                [sys.executable, "-B", str(SCRIPTS / "validate_qc_package.py"), "--manifest", str(manifest), "--source-snapshot", str(source_snapshot), "--candidate-snapshot", str(candidate_snapshot), "--findings-dir", str(findings_dir), "--report", str(report)],
                [sys.executable, "-B", str(SCRIPTS / "render_qc_report.py"), "--report", str(report), "--findings-dir", str(findings_dir), "--output", str(rendered)],
            ]
            for command in commands:
                completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertIn("Gate outcome: `pass`", rendered.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
