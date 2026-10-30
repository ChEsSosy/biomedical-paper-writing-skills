"""Deterministic positive, negative, and CLI tests for Phase 7A."""

from __future__ import annotations

import copy
import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable


TEST_ROOT = Path(__file__).resolve().parent
CANDIDATE_ROOT = TEST_ROOT.parent.parent
VALIDATOR_PATH = CANDIDATE_ROOT / "scripts" / "validate_review_package.py"
sys.path.insert(0, str(TEST_ROOT))

from fixture_factory import (  # noqa: E402
    FIXTURES,
    build_valid_package,
    clone_package,
    decision_ref,
    make_decision,
    payload_sha256,
    rehash_package,
)


def _load_validator() -> Any:
    spec = importlib.util.spec_from_file_location("phase7a_validator_under_test", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load validator: {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()


REQUIRED_NEGATIVE_CASE_IDS = {
    "wrong-document-type",
    "formal-review-executable",
    "non-review-profile",
    "duplicate-source-identity",
    "unresolved-source-identity",
    "bibliography-only-substantive-support",
    "abstract-detail-absent-from-trusted-input",
    "unresolved-access-substantive-synthesis",
    "source-outside-frozen-scope",
    "missing-synthesis-relation-extraction",
    "stale-decision-subject-binding",
    "untrusted-authority-bundle",
    "workflow-mints-author-approval",
    "workflow-author-position-denied",
    "workflow-field-consensus-denied",
    "model-self-approves-extraction",
    "model-proposed-direct-support",
    "model-independence-baseline",
    "missing-citation-source-extraction",
    "cross-source-represented-as-source-claim",
    "one-source-cross-source-claim",
    "author-position-without-authority",
    "author-objective-false-source-attribution",
    "model-access-upgrade",
    "access-ceiling-exceeded",
    "missing-extraction",
    "field-consensus-without-coverage-authority",
    "field-consensus-without-independence-authority",
    "linked-publications-double-counted",
    "evaluative-axis-without-rubric",
    "outline-cluster-theme-mismatch",
    "unplaced-conflict",
    "same-theme-unrelated-claim-cluster",
    "invalid-source-partition",
    "artifact-hash-mismatch",
    "extraction-hash-mismatch",
    "registry-ref-mismatch",
    "systematic-review-without-method-artifacts",
}


def semantic_issues(package: dict[str, Any]) -> list[dict[str, str]]:
    return VALIDATOR.validate_review_package(
        package["scope"],
        package["registry"],
        package["extractions"],
        package["authority_bundle"],
        package["authority_manifest_sha256"],
        package["synthesis"],
        package["outline"],
        package["trusted_inputs"],
    )


def schema_issues(package: dict[str, Any]) -> list[dict[str, str]]:
    return VALIDATOR.validate_schema_layer(
        package["scope"],
        package["registry"],
        package["extractions"],
        package["authority_bundle"],
        package["synthesis"],
        package["outline"],
    )


class Phase7AContractTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.valid = build_valid_package()

    def assertSemanticCode(
        self,
        expected: str,
        mutate: Callable[[dict[str, Any]], None],
        *,
        rehash: bool = True,
    ) -> None:
        package = clone_package(self.valid)
        mutate(package)
        if rehash:
            rehash_package(package)
        codes = {item["code"] for item in semantic_issues(package)}
        self.assertIn(expected, codes, f"issues were: {sorted(codes)}")

    def test_01_valid_fixture_passes_all_schemas_and_semantics(self) -> None:
        self.assertEqual([], schema_issues(self.valid))
        self.assertEqual([], semantic_issues(self.valid))

    def test_02_all_six_contract_schemas_are_present_and_parseable(self) -> None:
        phase7a_names = {
            "review-scope.schema.json",
            "review-source-registry.schema.json",
            "review-extraction-record.schema.json",
            "review-authority-decision.schema.json",
            "review-synthesis-matrix.schema.json",
            "review-outline.schema.json",
        }
        schema_paths = sorted(CANDIDATE_ROOT / "schemas" / name for name in phase7a_names)
        self.assertTrue(all(path.is_file() for path in schema_paths))
        ids = {json.loads(path.read_text(encoding="utf-8"))["$id"] for path in schema_paths}
        self.assertEqual(
            phase7a_names,
            ids,
        )

    def test_03_negative_fixture_matrix_is_executable_and_exact(self) -> None:
        matrix = json.loads((FIXTURES / "negative-cases.json").read_text(encoding="utf-8"))
        cases = matrix["cases"]
        self.assertEqual(len(cases), len({item["case_id"] for item in cases}))
        self.assertEqual(len(cases), len({item["test_binding"] for item in cases}))
        self.assertEqual(REQUIRED_NEGATIVE_CASE_IDS, {item["case_id"] for item in cases})
        for item in cases:
            binding = item.get("test_binding")
            self.assertIsInstance(binding, str, item)
            self.assertTrue(callable(getattr(self, binding, None)), item)
            self.assertTrue(item.get("expected_code"), item)

    def test_04_wrong_document_type_fails_schema_const(self) -> None:
        package = clone_package(self.valid)
        package["scope"]["document_type"] = "original_article"
        rehash_package(package)
        codes = {item["code"] for item in schema_issues(package)}
        self.assertIn("schema:const", codes)

    def test_05_formal_review_cannot_claim_executable_minimum_path(self) -> None:
        self.assertSemanticCode(
            "routing:formal_review",
            lambda p: p["scope"].update(review_type="systematic_style_draft", execution_mode="executable"),
        )

    def test_06_non_review_profile_is_rejected(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            package["scope"]["profile_ref"] = {
                "profile_id": "profile-original",
                "profile_kind": "original_article",
                "profile_version": "0.1.0",
                "profile_sha256": "1" * 64,
                "profile_alignment_used": False,
            }

        self.assertSemanticCode("profile:non_review", mutate)

    def test_07_duplicate_included_bibliographic_identity_is_rejected(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            first = package["registry"]["source_records"][0]["bibliographic_identity"]["identity_records"]
            package["registry"]["source_records"][1]["bibliographic_identity"]["identity_records"] = first

        self.assertSemanticCode("source:duplicate_identity", mutate)

    def test_08_model_cannot_upgrade_source_access(self) -> None:
        self.assertSemanticCode(
            "access:model_upgrade",
            lambda p: p["registry"]["source_records"][0].update(access_verification_origin="model_proposed"),
        )

    def test_09_extraction_cannot_exceed_trusted_source_access(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            package["registry"]["source_records"][0]["access_level"] = "abstract_verified"
            decision = package["authority_bundle"]["records"][0]
            decision["subject_refs"][0]["asserted_state"] = "abstract_verified"

        self.assertSemanticCode("extraction:access_ceiling", mutate)

    def test_10_missing_extraction_breaks_registry_inventory(self) -> None:
        self.assertSemanticCode("extraction:registry_inventory", lambda p: p["extractions"].pop())

    def test_11_embedded_authority_is_not_trusted_without_external_manifest_hash(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            package["authority_bundle"]["records"][0]["reviewed_by"] = "tampered-workflow"

        self.assertSemanticCode("authority:manifest_hash", mutate, rehash=False)

    def test_12_workflow_cannot_mint_author_approval(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            decision = package["authority_bundle"]["records"][0]
            decision["authorization_state"] = "author_approved"

        self.assertSemanticCode("authority:author_mint", mutate)

    def test_13_model_assisted_extraction_cannot_approve_itself(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            extraction = package["extractions"][0]
            extraction.update(review_status="approved", review_decision_origin="model_proposed")

        self.assertSemanticCode("extraction:self_approval", mutate)

    def test_14_model_proposed_independence_is_not_a_trusted_baseline(self) -> None:
        self.assertSemanticCode(
            "independence:model_baseline",
            lambda p: p["registry"]["source_records"][0].update(assignment_origin="model_proposed"),
        )

    def test_15_cross_source_synthesis_requires_two_sources(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            claim = package["synthesis"]["claims"][0]
            claim["source_ids"] = ["source-1"]
            claim["extraction_record_ids"] = ["extract-1"]
            claim["evidence_unit_ids"] = ["evidence-unit-1"]

        self.assertSemanticCode("claim:cross_source_cardinality", mutate)

    def test_16_author_position_requires_separate_authority(self) -> None:
        self.assertSemanticCode(
            "authority:missing_ref",
            lambda p: p["synthesis"]["claims"][0].update(claim_origin="author_position"),
        )

    def test_17_field_wide_consensus_requires_coverage_authority(self) -> None:
        self.assertSemanticCode(
            "consensus:coverage_authority",
            lambda p: p["synthesis"]["claims"][0].update(agreement_scope="field_wide"),
        )

    def test_18_field_wide_consensus_requires_independence_authority(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            package["synthesis"]["claims"][0]["agreement_scope"] = "field_wide"
            source = package["registry"]["source_records"][0]
            source["independence_status"] = "unresolved"
            source["independence_review_status"] = "pending"
            source.pop("independence_decision_ref")
            package["synthesis"]["gaps"][0]["independent_evidence_unit_count"] = 1

        self.assertSemanticCode("consensus:independence_authority", mutate)

    def test_19_evaluative_taxonomy_axis_requires_rubric(self) -> None:
        self.assertSemanticCode(
            "taxonomy:missing_rubric",
            lambda p: p["synthesis"]["taxonomy_axes"][0].update(axis_kind="evaluative_axis", rubric_ref=None),
        )

    def test_20_outline_cluster_must_share_paragraph_theme(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            package["synthesis"]["themes"].append(
                {
                    "theme_id": "theme-other",
                    "label": "Other theme",
                    "axis_ids": ["axis-context"],
                    "category_labels": ["related condition"],
                }
            )
            package["synthesis"]["evidence_clusters"][0]["theme_ids"] = ["theme-other"]

        self.assertSemanticCode("outline:cluster_theme_binding", mutate)

    def test_21_all_conflicts_must_be_explicitly_placed(self) -> None:
        self.assertSemanticCode(
            "outline:conflict_coverage",
            lambda p: p["outline"].update(placed_conflict_ids=[]),
        )

    def test_22_outline_source_partition_must_be_exact(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            package["outline"]["source_coverage_audit"]["unassigned_sources"] = [
                {"source_id": "source-2", "reason": "unresolved"}
            ]

        self.assertSemanticCode("coverage:outline_partition", mutate)

    def test_23_artifact_hash_is_recomputed(self) -> None:
        self.assertSemanticCode(
            "identity:artifact_hash",
            lambda p: p["scope"].update(review_question="tampered after hashing"),
            rehash=False,
        )

    def test_24_extraction_hash_is_recomputed(self) -> None:
        self.assertSemanticCode(
            "identity:extraction_hash",
            lambda p: p["extractions"][0].update(extracted_content="tampered after hashing"),
            rehash=False,
        )

    def test_25_extraction_registry_ref_is_bound_to_registry_identity(self) -> None:
        package = clone_package(self.valid)
        extraction = package["extractions"][0]
        extraction["source_registry_ref"]["artifact_sha256"] = "f" * 64
        extraction["record_sha256"] = payload_sha256(extraction, "record_sha256")
        codes = {item["code"] for item in semantic_issues(package)}
        self.assertIn("binding:extraction_registry", codes)

    def test_28_stale_decision_cannot_authorize_changed_subject_content(self) -> None:
        package = clone_package(self.valid)
        extraction = package["extractions"][0]
        extraction.update(
            review_status="approved",
            review_decision_origin="authorized_review_workflow",
            reviewer_identity="authorized-review-fixture",
        )
        decision = make_decision(
            "approve-extract-1",
            "extraction_review",
            "extraction_record",
            "extract-1",
            "approved",
        )
        package["authority_bundle"]["records"].append(decision)
        extraction["decision_ref"] = decision_ref(decision)
        rehash_package(package)
        self.assertEqual([], semantic_issues(package))

        extraction["extracted_content"] = "Changed content retaining the same stable extraction ID."
        rehash_package(package, refresh_decision_subjects=False)
        codes = {item["code"] for item in semantic_issues(package)}
        self.assertIn("authority:subject_hash", codes)

    def test_29_workflow_decision_cannot_authorize_author_position(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            claim = package["synthesis"]["claims"][0]
            claim["claim_origin"] = "author_position"
            decision = make_decision(
                "workflow-author-position",
                "author_position_origin",
                "author_position",
                claim["claim_id"],
                "approved",
            )
            package["authority_bundle"]["records"].append(decision)
            claim["decision_ref"] = decision_ref(decision)

        self.assertSemanticCode("authority:role_policy", mutate)

    def test_30_workflow_decision_cannot_authorize_field_wide_consensus(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            claim = package["synthesis"]["claims"][0]
            claim["agreement_scope"] = "field_wide"
            decision = make_decision(
                "workflow-field-consensus",
                "synthesis_decision",
                "synthesis_claim",
                claim["claim_id"],
                "approved",
            )
            package["authority_bundle"]["records"].append(decision)
            claim["decision_ref"] = decision_ref(decision)

        self.assertSemanticCode("authority:role_policy", mutate)

    def test_31_fabricated_abstract_span_is_rejected_against_trusted_input(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            source = package["registry"]["source_records"][0]
            source["access_level"] = "abstract_verified"
            package["authority_bundle"]["records"][0]["subject_refs"][0]["asserted_state"] = "abstract_verified"
            extraction = package["extractions"][0]
            extraction["source_access_level"] = "abstract_verified"
            fabricated = hashlib.sha256(b"fabricated abstract-only detail").hexdigest()
            extraction["source_locator"]["span_sha256"] = fabricated
            extraction["source_span_sha256"] = fabricated
            extraction["extracted_content"] = "fabricated abstract-only detail"
            package["synthesis"]["claims"][0]["access_constraint"] = "abstract_verified"
            relation = package["synthesis"]["citation_relations"][0]
            relation["access_constraint"] = "abstract_verified"
            relation["actual_access_level"] = "abstract_verified"

        self.assertSemanticCode("source_span:hash_mismatch", mutate)

    def test_32_bibliographic_only_source_cannot_supply_substantive_extraction(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            source = package["registry"]["source_records"][0]
            source.update(
                access_level="bibliographic_only",
                access_verification_origin="author_supplied_source_evidence",
                access_verification_status="pending",
            )
            source.pop("access_verification_ref")
            package["extractions"][0]["source_access_level"] = "bibliographic_only"
            package["synthesis"]["claims"][0]["access_constraint"] = "bibliographic_only"
            relation = package["synthesis"]["citation_relations"][0]
            relation["source_ids"] = ["source-1"]
            relation["extraction_record_ids"] = ["extract-1"]
            relation["access_constraint"] = "bibliographic_only"
            relation["actual_access_level"] = "bibliographic_only"

        self.assertSemanticCode("extraction:substantive_access", mutate)

    def test_33_unresolved_access_cannot_supply_substantive_synthesis(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            source = package["registry"]["source_records"][0]
            source.update(
                access_level="unresolved",
                access_verification_origin="model_proposed",
                access_verification_status="pending",
            )
            source.pop("access_verification_ref")
            package["extractions"][0]["source_access_level"] = "unresolved"
            package["synthesis"]["claims"][0]["access_constraint"] = "unresolved"
            relation = package["synthesis"]["citation_relations"][0]
            relation["source_ids"] = ["source-1"]
            relation["extraction_record_ids"] = ["extract-1"]
            relation["access_constraint"] = "unresolved"
            relation["actual_access_level"] = "unresolved"

        self.assertSemanticCode("extraction:substantive_access", mutate)

    def test_34_included_source_outside_frozen_scope_is_rejected(self) -> None:
        self.assertSemanticCode(
            "scope:source_set",
            lambda p: p["scope"].update(permitted_source_ids=["source-1"]),
        )

    def test_35_synthesis_relation_missing_extraction_is_rejected(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            relation = package["synthesis"]["citation_relations"][0]
            relation["source_ids"] = ["source-1"]
            relation["extraction_record_ids"] = ["missing-extraction"]

        self.assertSemanticCode("citation:extraction_ref", mutate)

    def test_36_citation_missing_source_and_extraction_is_rejected(self) -> None:
        package = clone_package(self.valid)
        relation = package["synthesis"]["citation_relations"][0]
        relation["source_ids"] = ["missing-source"]
        relation["extraction_record_ids"] = ["missing-extraction"]
        rehash_package(package)
        codes = {item["code"] for item in semantic_issues(package)}
        self.assertIn("citation:source_ref", codes)
        self.assertIn("citation:extraction_ref", codes)

    def test_37_author_objective_future_direction_cannot_fabricate_source_attribution(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            objective: dict[str, Any] = {
                "author_objective_id": "objective-1",
                "objective": "Propose a future validation experiment.",
            }
            decision = make_decision(
                "author-objective-1",
                "author_objective",
                "author_objective",
                "objective-1",
                "approved",
                role="author",
            )
            objective["decision_ref"] = decision_ref(decision)
            package["scope"]["author_objectives"].append(objective)
            package["authority_bundle"]["records"].append(decision)
            claim = package["synthesis"]["claims"][0]
            claim["claim_origin"] = "future_direction"
            claim["basis_refs"] = [{"basis_type": "author_objective", "basis_id": "objective-1"}]

        self.assertSemanticCode("claim:author_objective_attribution", mutate)

    def test_38_linked_publications_cannot_be_counted_as_distinct_independent_units(self) -> None:
        self.assertSemanticCode(
            "independence:linked_double_count",
            lambda p: p["registry"]["source_records"][0].update(linked_source_ids=["source-2"]),
        )

    def test_39_same_theme_unrelated_claim_cluster_is_rejected(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            synthesis = package["synthesis"]
            cluster = copy.deepcopy(synthesis["evidence_clusters"][0])
            cluster["cluster_id"] = "cluster-other"
            synthesis["evidence_clusters"].append(cluster)
            claim = copy.deepcopy(synthesis["claims"][0])
            claim["claim_id"] = "claim-other"
            claim["evidence_cluster_ids"] = ["cluster-other"]
            synthesis["claims"].append(claim)
            paragraph = package["outline"]["section_plans"][0]["paragraph_plans"][0]
            paragraph["claim_ids"] = ["claim-response"]
            paragraph["evidence_cluster_ids"] = ["cluster-other"]

        self.assertSemanticCode("outline:claim_cluster_binding", mutate)

    def test_40_model_proposed_relation_cannot_mint_direct_support(self) -> None:
        def mutate(package: dict[str, Any]) -> None:
            relation = package["synthesis"]["citation_relations"][0]
            relation.update(relation_origin="model_proposed", support_relation="direct_support")

        self.assertSemanticCode("citation:model_support", mutate)

    def test_41_cross_source_synthesis_cannot_be_represented_as_one_source_claim(self) -> None:
        self.assertSemanticCode(
            "claim:source_claim_provenance",
            lambda p: p["synthesis"]["claims"][0].update(claim_origin="source_claim"),
        )

    def test_42_model_proposed_identity_cannot_be_admitted_as_verified(self) -> None:
        self.assertSemanticCode(
            "source:unverified_identity",
            lambda p: p["registry"]["source_records"][0].update(verification_origin="model_proposed"),
        )

    def test_43_systematic_review_without_method_artifacts_cannot_be_executable(self) -> None:
        self.assertSemanticCode(
            "routing:formal_review",
            lambda p: p["scope"].update(review_type="systematic_style_draft", execution_mode="executable", protocol_artifact_refs=[]),
        )

    def test_26_cli_accepts_valid_package_and_writes_valid_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="phase7a-cli-") as raw_dir:
            root = Path(raw_dir)
            paths: dict[str, Path] = {}
            for key, filename in (
                ("scope", "scope.json"),
                ("registry", "registry.json"),
                ("extractions", "extractions.json"),
                ("authority_bundle", "authority.json"),
                ("synthesis", "synthesis.json"),
                ("outline", "outline.json"),
            ):
                paths[key] = root / filename
                paths[key].write_text(
                    json.dumps(self.valid[key], indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            report = root / "report.json"
            command = [
                sys.executable,
                str(VALIDATOR_PATH),
                "--scope", str(paths["scope"]),
                "--source-registry", str(paths["registry"]),
                "--extractions", str(paths["extractions"]),
                "--authority-bundle", str(paths["authority_bundle"]),
                "--authority-manifest-sha256", self.valid["authority_manifest_sha256"],
                "--synthesis-matrix", str(paths["synthesis"]),
                "--outline", str(paths["outline"]),
                "--json-report", str(report),
            ]
            for input_id, path in self.valid["trusted_input_paths"].items():
                command.extend(["--trusted-input", f"{input_id}={path}"])
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            result = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(
                {"valid": True, "terminal_state": "ready_for_author_review", "issue_count": 0, "issues": []},
                result,
            )

    def test_27_cli_rejects_tampered_artifact(self) -> None:
        package = clone_package(self.valid)
        package["scope"]["review_question"] = "tampered after hashing"
        with tempfile.TemporaryDirectory(prefix="phase7a-cli-invalid-") as raw_dir:
            root = Path(raw_dir)
            paths: dict[str, Path] = {}
            for key in ("scope", "registry", "extractions", "authority_bundle", "synthesis", "outline"):
                paths[key] = root / f"{key}.json"
                paths[key].write_text(json.dumps(package[key]), encoding="utf-8")
            command = [
                sys.executable, str(VALIDATOR_PATH),
                "--scope", str(paths["scope"]),
                "--source-registry", str(paths["registry"]),
                "--extractions", str(paths["extractions"]),
                "--authority-bundle", str(paths["authority_bundle"]),
                "--authority-manifest-sha256", package["authority_manifest_sha256"],
                "--synthesis-matrix", str(paths["synthesis"]),
                "--outline", str(paths["outline"]),
            ]
            for input_id, path in package["trusted_input_paths"].items():
                command.extend(["--trusted-input", f"{input_id}={path}"])
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(1, completed.returncode, completed.stdout + completed.stderr)
            self.assertIn("identity:artifact_hash", completed.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
