"""Deterministic schema, trust, authority, hash, and negative tests for Phase 8A."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable


TEST_ROOT = Path(__file__).resolve().parent
CANDIDATE_ROOT = TEST_ROOT.parent
VALIDATOR_PATH = CANDIDATE_ROOT / "scripts" / "validate_figure_package.py"
sys.path.insert(0, str(TEST_ROOT))
sys.path.insert(0, str(CANDIDATE_ROOT / "scripts"))

from fixture_factory import (  # noqa: E402
    MANIFEST_FILE,
    TRUST_FILES,
    build_valid_package,
    canonical_sha256,
    load_package,
    make_decision,
    payload_sha256,
    save_package,
    set_maturity,
    write_external_trust_root,
)


def _load_validator() -> Any:
    spec = importlib.util.spec_from_file_location("phase8a_validator_under_test", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load validator: {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()
REQUIRED_NEGATIVE_CASE_IDS = {
    "design-package-hash-mismatch", "qc-cycle-in-design-manifest",
    "component-file-hash-mismatch", "artifact-self-hash-mismatch", "package-path-escape",
    "trusted-collection-hash-mismatch", "source-without-trusted-binding",
    "trusted-source-missing", "trusted-source-hash-mismatch", "manifest-self-certification",
    "unsupported-content-inspected", "trusted-header-missing", "recipe-variable-missing",
    "n-inference-unit-mismatch", "technical-replicate-counted-as-n",
    "card-source-unit-mismatch", "design-flag-dropped", "upstream-relation-map-mismatch",
    "unknown-upstream-claim", "structured-claim-ceiling-exceeded",
    "required-evidence-unplaced", "linked-publications-double-counted",
    "source-claim-multiple-sources", "workflow-author-only-decision",
    "stale-authority-subject-hash", "authority-decision-type-mismatch",
    "analysis-record-hash-mismatch", "model-proposed-analysis-result",
    "analysis-source-binding-mismatch", "analysis-input-hash-mismatch", "analysis-n-mismatch",
    "annotation-missing-analysis-binding", "unavailable-annotation-filled",
    "orphan-plot-recipe", "panel-coverage-mismatch", "decorative-evidence-bearing",
    "schematic-labelled-data", "unknown-palette-key", "published-reference-asset-embedded",
    "declared-copied-layout", "prohibited-image-processing",
    "representative-image-without-authority", "prototype-finality-overreach",
    "phase8a-execution-claim", "review-table-brief-converted",
    "maturity-component-mismatch", "image-region-reuse-undeclared",
}


class Phase8AContractTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="phase8a-test-")
        workspace = Path(self.temp.name)
        self.root = build_valid_package(workspace / "package")
        self.trust_root_path = workspace / "trusted-inputs-root.json"
        self.trust_root_sha256 = write_external_trust_root(self.root, self.trust_root_path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def result(self) -> dict[str, Any]:
        return VALIDATOR.validate_figure_package(
            self.root,
            trust_root_path=self.trust_root_path,
            expected_trust_root_sha256=self.trust_root_sha256,
        )

    def codes(self) -> set[str]:
        return {item["code"] for item in self.result()["issues"]}

    def assertCode(
        self,
        expected: str,
        mutate: Callable[[dict[str, Any]], None],
        *,
        rehash: bool = True,
        refresh_decision_subjects: bool = True,
        refresh_external_trust_root: bool = False,
    ) -> None:
        documents = load_package(self.root)
        mutate(documents)
        save_package(
            self.root,
            documents,
            rehash=rehash,
            refresh_decision_subjects=refresh_decision_subjects,
        )
        if refresh_external_trust_root:
            self.trust_root_sha256 = write_external_trust_root(self.root, self.trust_root_path)
        codes = self.codes()
        self.assertIn(expected, codes, f"issues were: {sorted(codes)}")

    @staticmethod
    def add_author_representative_decision(
        documents: dict[str, Any],
        *,
        decision_value: str = "approve",
        asserted_state: str = "approved",
    ) -> None:
        representative = {
            "representative_image_id": "representative-author-1",
            "source_data_id": "source-data-1",
            "selection_status": "approved",
            "quantified_source_data_id": "source-data-1",
        }
        decision = make_decision(
            "author-representative-1",
            "representative_image_selection",
            "representative_image",
            representative["representative_image_id"],
            "0.1.0",
            representative,
            role="author",
        )
        decision["decision_value"] = decision_value
        decision["subject_refs"][0]["asserted_state"] = asserted_state
        representative["decision_ref"] = {
            "decision_id": decision["decision_id"],
            "interface_version": decision["interface_version"],
            "decision_sha256": decision["decision_sha256"],
        }
        documents["cards"][0]["representative_image"] = representative
        documents["authority_collection"]["records"].append(decision)

    def test_01_valid_fixture_passes(self) -> None:
        result = self.result()
        self.assertTrue(result["valid"], result["issues"])
        self.assertEqual([], result["issues"])
        self.assertEqual("author_review_required", result["qc"]["readiness_gate"])

    def test_02_all_eleven_schemas_are_present_and_parseable(self) -> None:
        paths = sorted((CANDIDATE_ROOT / "schemas").glob("*.schema.json"))
        self.assertEqual(11, len(paths))
        ids = []
        for path in paths:
            value = json.loads(path.read_text(encoding="utf-8"))
            ids.append(value["$id"])
        self.assertEqual(len(ids), len(set(ids)))

    def test_03_negative_matrix_is_exact_and_executable(self) -> None:
        value = json.loads((TEST_ROOT / "fixtures" / "negative-cases.json").read_text(encoding="utf-8"))
        cases = value["cases"]
        self.assertEqual(REQUIRED_NEGATIVE_CASE_IDS, {item["case_id"] for item in cases})
        self.assertEqual(len(cases), len({item["case_id"] for item in cases}))
        self.assertEqual(len(cases), len({item["test_binding"] for item in cases}))
        for item in cases:
            self.assertTrue(callable(getattr(self, item["test_binding"], None)), item)
            self.assertTrue(item["expected_code"], item)

    def test_04_qc_hash_is_non_circular_and_recomputable(self) -> None:
        result = self.result()
        qc = result["qc"]
        self.assertNotIn("figure_qc", load_package(self.root)["manifest"])
        self.assertEqual(qc["figure_qc_sha256"], payload_sha256(qc, "figure_qc_sha256"))
        self.assertEqual(qc["design_package_hash"], load_package(self.root)["manifest"]["design_package_hash"])

    def test_05_cli_generates_qc_without_plotting(self) -> None:
        output = self.root / "generated-figure-qc.json"
        completed = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR_PATH),
                str(self.root),
                "--trust-root",
                str(self.trust_root_path),
                "--trust-root-sha256",
                self.trust_root_sha256,
                "--output",
                str(output),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
        self.assertTrue(output.is_file())
        qc = json.loads(output.read_text(encoding="utf-8"))
        self.assertFalse(qc["render_inspected"])
        self.assertEqual("deterministic_phase8a", qc["check_level"])

    def test_06_design_package_hash_is_recomputed(self) -> None:
        self.assertCode(
            "identity:design_package_hash",
            lambda p: p["manifest"].update(created_at="2026-09-01T00:00:00Z"),
            rehash=False,
        )

    def test_07_design_manifest_cannot_include_figure_qc(self) -> None:
        self.assertCode(
            "identity:qc_cycle",
            lambda p: p["manifest"].update(figure_qc={"design_package_hash": p["manifest"]["design_package_hash"]}),
            rehash=False,
        )

    def test_08_component_file_hash_is_recomputed(self) -> None:
        self.assertCode(
            "identity:file_hash",
            lambda p: p["recipes"][0].update(review_status="approved"),
            rehash=False,
        )

    def test_09_artifact_self_hash_is_recomputed(self) -> None:
        self.assertCode(
            "identity:artifact_hash",
            lambda p: p["source_manifest"].update(created_by="tampered-after-hash"),
            rehash=False,
        )

    def test_10_component_path_cannot_escape_package(self) -> None:
        self.assertCode(
            "package:path_scope",
            lambda p: p["manifest"]["components"]["plot_recipes"][0].update(path="../outside.json"),
            rehash=False,
        )

    def test_11_trusted_collection_hash_is_external_boundary(self) -> None:
        self.assertCode(
            "trust:collection_hash",
            lambda p: p["source_collection"].update(supplied_by="tampered-caller"),
            rehash=False,
        )

    def test_12_source_manifest_cannot_self_certify_binding(self) -> None:
        self.assertCode(
            "trust:source_binding",
            lambda p: p["source_manifest"]["source_records"][0].update(trusted_input_id=None),
        )

    def test_13_missing_trusted_source_is_rejected(self) -> None:
        self.assertCode(
            "trust:source_missing",
            lambda p: p["source_collection"]["records"][0].update(path="data/missing.csv"),
        )

    def test_14_trusted_source_hash_is_recomputed(self) -> None:
        self.assertCode(
            "trust:source_hash",
            lambda p: p["source_collection"]["records"][0].update(expected_sha256="f" * 64),
        )

    def test_15_manifest_verified_string_is_not_trusted(self) -> None:
        self.assertCode(
            "trust:self_certification",
            lambda p: p["source_manifest"]["source_records"][0].update(verification_status="verified"),
        )

    def test_16_unsupported_binary_cannot_claim_content_inspection(self) -> None:
        def mutate(p: dict[str, Any]) -> None:
            set_maturity(p, "ready_for_prototype")
            p["source_collection"]["records"][0]["format"] = "xlsx"
            p["source_manifest"]["source_records"][0]["file_identity"]["format"] = "xlsx"

        self.assertCode("trust:content_not_performed", mutate)

    def test_17_actual_header_must_contain_expected_variable(self) -> None:
        self.assertCode(
            "trust:locator_missing",
            lambda p: p["source_collection"]["records"][0]["expected_locators"].append(
                {"locator_type": "header", "value": "missing_column"}
            ),
        )

    def test_18_recipe_variable_must_resolve(self) -> None:
        self.assertCode(
            "recipe:variable_mapping",
            lambda p: p["recipes"][0]["variable_mappings"][1].update(variable_id="missing_variable"),
        )

    def test_19_n_unit_must_match_inference_unit(self) -> None:
        self.assertCode(
            "units:n_inference_mismatch",
            lambda p: p["source_manifest"]["source_records"][0]["replicates"].update(n_unit="cell"),
        )

    def test_20_technical_replicate_cannot_be_independent_n(self) -> None:
        def mutate(p: dict[str, Any]) -> None:
            source = p["source_manifest"]["source_records"][0]
            source["units"]["inference_unit"] = "assay_read"
            source["replicates"]["n_unit"] = "assay_read"
            for card in p["cards"]:
                card["units"]["inference_unit"] = "assay_read"
                card["replicates"]["n_unit"] = "assay_read"
            analysis = p["analysis_collection"]["records"][0]
            analysis["unit_context"]["inference_unit"] = "assay_read"
            analysis["n_unit"] = "assay_read"

        self.assertCode("units:technical_as_n", mutate)

    def test_21_card_units_must_match_source(self) -> None:
        self.assertCode(
            "units:card_source",
            lambda p: p["cards"][0]["units"].update(inference_unit="cell"),
        )

    def test_22_card_cannot_drop_repeated_measure_state(self) -> None:
        self.assertCode(
            "units:design_flag",
            lambda p: p["source_manifest"]["source_records"][0]["design_context"].update(repeated=True),
        )

    def test_23_evidence_binding_must_resolve_through_relation_map(self) -> None:
        self.assertCode(
            "upstream:relation_map",
            lambda p: p["cards"][0]["evidence_bindings"][0].update(relation_type="conflict"),
        )

    def test_24_panel_claim_must_exist_upstream(self) -> None:
        def mutate(p: dict[str, Any]) -> None:
            p["cards"][0]["claim_ids"] = ["claim-missing"]
            p["cards"][0]["evidence_bindings"][0]["claim_id"] = "claim-missing"

        self.assertCode("upstream:claim", mutate)

    def test_25_structured_claim_ceiling_is_enforced(self) -> None:
        self.assertCode(
            "claim:structured_ceiling",
            lambda p: p["contracts"][0]["conclusion"]["structured_ceiling"].update(causality="causal"),
        )

    def test_26_required_evidence_cannot_disappear(self) -> None:
        self.assertCode(
            "figure:required_visibility",
            lambda p: p["contracts"][0].update(required_visibility_ids=[]),
        )

    def test_27_linked_evidence_units_cannot_be_double_counted(self) -> None:
        def mutate(p: dict[str, Any]) -> None:
            upstream = p["manifest"]["upstream_context"]
            upstream["evidence"].append({
                "evidence_id": "evidence-2", "evidence_unit_id": "evidence-unit-1",
                "linked_source_ids": ["source-publication-2"], "relation_status": "support",
            })
            upstream["claim_evidence_relations"].append({
                "claim_id": "claim-1", "evidence_id": "evidence-2", "relation_type": "support"
            })
            upstream["figure_sequence"][0]["evidence_ids"].append("evidence-2")
            p["cards"][0]["evidence_bindings"].append({
                "claim_id": "claim-1", "evidence_id": "evidence-2", "relation_type": "support"
            })
            p["contracts"][0]["evidence_ids"].append("evidence-2")
            p["contracts"][0]["independent_evidence_unit_count"] = 2

        self.assertCode("independence:linked_double_count", mutate)

    def test_28_source_claim_cannot_bind_multiple_sources(self) -> None:
        self.assertCode(
            "upstream:source_claim_provenance",
            lambda p: p["manifest"]["upstream_context"]["claims"][0]["source_ids"].append("source-publication-2"),
        )

    def test_29_workflow_cannot_approve_representative_image(self) -> None:
        def mutate(p: dict[str, Any]) -> None:
            representative = {
                "representative_image_id": "representative-1", "source_data_id": "source-data-1",
                "selection_status": "approved", "quantified_source_data_id": "source-data-1",
            }
            decision = make_decision(
                "workflow-representative", "representative_image_selection", "representative_image",
                "representative-1", "0.1.0", representative, role="authorized_figure_workflow"
            )
            representative["decision_ref"] = {
                "decision_id": decision["decision_id"], "interface_version": "0.1.0",
                "decision_sha256": decision["decision_sha256"],
            }
            p["cards"][0]["representative_image"] = representative
            p["authority_collection"]["records"].append(decision)

        self.assertCode("authority:role_policy", mutate)

    def test_30_stale_decision_cannot_govern_changed_analysis(self) -> None:
        self.assertCode(
            "authority:subject_hash",
            lambda p: p["analysis_collection"]["records"][0].update(estimate=9.9),
            refresh_decision_subjects=False,
        )

    def test_31_analysis_review_requires_analysis_decision_type(self) -> None:
        def mutate(p: dict[str, Any]) -> None:
            decision = p["authority_collection"]["records"][0]
            decision.update(
                decision_type="layout_decision", decision_value="approve",
                authorization_origin="author", authorization_state="author_approved",
                decision_producer_role="author",
            )

        self.assertCode("authority:decision_type", mutate)

    def test_32_analysis_record_hash_is_recomputed(self) -> None:
        self.assertCode(
            "analysis:record_hash",
            lambda p: p["analysis_collection"]["records"][0].update(estimate=8.8),
            rehash=False,
        )

    def test_33_model_proposal_cannot_supply_statistical_result(self) -> None:
        self.assertCode(
            "analysis:model_result",
            lambda p: p["analysis_collection"]["records"][0].update(analysis_origin="model_proposed"),
        )

    def test_34_analysis_must_bind_exact_source_record(self) -> None:
        self.assertCode(
            "analysis:source_binding",
            lambda p: p["analysis_collection"]["records"][0]["source_data_refs"][0].update(source_data_sha256="f" * 64),
        )

    def test_35_analysis_input_hash_must_resolve(self) -> None:
        self.assertCode(
            "analysis:input_hash",
            lambda p: p["analysis_collection"]["records"][0].update(input_data_hashes=["f" * 64]),
        )

    def test_36_analysis_n_must_match_source(self) -> None:
        self.assertCode(
            "analysis:n_binding",
            lambda p: p["analysis_collection"]["records"][0]["n_by_group"].update(control=99),
        )

    def test_37_supplied_annotation_requires_analysis_record(self) -> None:
        self.assertCode(
            "analysis:annotation_binding",
            lambda p: p["recipes"][0]["statistical_annotations"][0].pop("analysis_output_ref"),
        )

    def test_38_unavailable_annotation_cannot_carry_symbol(self) -> None:
        self.assertCode(
            "analysis:unavailable_filled",
            lambda p: p["recipes"][0]["statistical_annotations"][0].update(status="required_but_unavailable"),
        )

    def test_39_recipe_must_resolve_to_panel(self) -> None:
        self.assertCode(
            "figure:orphan_recipe",
            lambda p: p["recipes"][0].update(panel_id="panel-missing"),
        )

    def test_40_contract_panel_coverage_is_exact(self) -> None:
        self.assertCode(
            "figure:panel_coverage",
            lambda p: p["contracts"][0].update(ordered_panel_ids=["panel-a"]),
        )

    def test_41_decorative_is_evidence_role_not_panel_kind(self) -> None:
        self.assertCode(
            "figure:decorative_evidence",
            lambda p: p["cards"][0].update(evidence_role="decorative"),
        )

    def test_42_conceptual_schematic_cannot_be_measured_data(self) -> None:
        self.assertCode(
            "figure:schematic_as_data",
            lambda p: p["cards"][0].update(panel_kind="conceptual_schematic"),
        )

    def test_43_recipe_palette_key_must_resolve(self) -> None:
        self.assertCode(
            "palette:unknown_key",
            lambda p: p["recipes"][0]["palette_keys"].append("unknown-group"),
        )

    def test_44_reference_asset_cannot_be_embedded(self) -> None:
        self.assertCode(
            "copyright:embedded_asset",
            lambda p: p["cards"][0]["reference_abstractions"].append({
                "reference_id": "reference-1", "source_locator": "doi:10.0000/example#figure-1",
                "feature_type": "panel_sequence", "observation_status": "observed",
                "usage_purpose": "functional_abstraction", "asset_embedded": True,
                "layout_origin": "functional_abstraction",
            }),
        )

    def test_45_explicit_copied_layout_is_rejected(self) -> None:
        self.assertCode(
            "copyright:copied_declared",
            lambda p: p["cards"][0]["reference_abstractions"].append({
                "reference_id": "reference-1", "source_locator": "doi:10.0000/example#figure-1",
                "feature_type": "layout", "observation_status": "observed",
                "usage_purpose": "functional_abstraction", "asset_embedded": False,
                "layout_origin": "copied_reference",
            }),
        )

    def test_46_prohibited_processing_cannot_be_acceptable(self) -> None:
        self.assertCode(
            "image:prohibited_processing",
            lambda p: p["source_manifest"]["source_records"][0]["processing_history"].append({
                "processing_id": "processing-1", "operation": "generative_fill",
                "scope": "synthetic region", "declared_acceptable": True,
                "divider_policy": None, "calibration_ref": None,
            }),
        )

    def test_47_representative_image_requires_external_authority(self) -> None:
        self.assertCode(
            "authority:missing_ref",
            lambda p: p["cards"][0].update(representative_image={
                "representative_image_id": "representative-1", "source_data_id": "source-data-1",
                "selection_status": "approved", "quantified_source_data_id": "source-data-1",
            }),
        )

    def test_48_phase8a_cannot_emit_submission_finality(self) -> None:
        self.assertCode(
            "finality:phase8a_state",
            lambda p: p["contracts"][0].update(finality_state="submission_candidate"),
        )

    def test_49_phase8a_recipe_cannot_claim_execution(self) -> None:
        self.assertCode(
            "phase8a:execution_claim",
            lambda p: p["recipes"][0].update(implementation_status="prototype_generated_unverified"),
        )

    def test_50_review_table_brief_cannot_become_figure(self) -> None:
        def mutate(p: dict[str, Any]) -> None:
            p["manifest"]["document_type"] = "review_article"
            p["source_manifest"]["document_type"] = "review_article"
            for artifact in [*p["cards"], *p["contracts"], *p["recipes"]]:
                artifact["document_type"] = "review_article"
            p["manifest"]["upstream_context"]["figure_sequence"] = []
            p["manifest"]["upstream_context"]["review_figure_briefs"] = [{
                "brief_id": "brief-table-1", "output_type": "table",
                "claim_ids": ["claim-1"], "source_ids": ["source-publication-1"],
            }]
            p["contracts"][0]["upstream_figure_or_brief_id"] = "brief-table-1"

        self.assertCode("routing:table_brief", mutate)

    def test_51_maturity_state_cannot_promote_incomplete_components(self) -> None:
        self.assertCode(
            "maturity:component_mismatch",
            lambda p: p["manifest"].update(maturity="ready_for_prototype"),
        )

    def test_52_identical_region_reuse_requires_group(self) -> None:
        def mutate(p: dict[str, Any]) -> None:
            for card in p["cards"]:
                card["data_locators"].append({
                    "source_data_id": "source-data-1", "locator_type": "region", "value": "region-1"
                })

        self.assertCode("image:reuse_relationship", mutate)

    def test_53_interval_level_must_be_positive(self) -> None:
        def mutate(p: dict[str, Any]) -> None:
            p["analysis_collection"]["records"][0]["interval"]["level"] = 0

        self.assertCode("analysis:interval_level", mutate)

    def test_54_external_trust_root_is_required(self) -> None:
        result = VALIDATOR.validate_figure_package(self.root)
        self.assertIn("trust:external_root_required", {item["code"] for item in result["issues"]})

    def test_55_fully_resigned_authority_collection_cannot_self_authorize(self) -> None:
        def mutate(p: dict[str, Any]) -> None:
            p["authority_collection"]["records"][0]["conditions"].append(
                "forged condition added by the package producer"
            )

        self.assertCode("trust:external_collection_identity", mutate)

    def test_56_fully_resigned_source_collection_cannot_self_authorize(self) -> None:
        self.assertCode(
            "trust:external_collection_identity",
            lambda p: p["source_collection"].update(supplied_by="forged-package-signer"),
        )

    def test_57_caller_held_trust_root_hash_is_enforced(self) -> None:
        trust_root = json.loads(self.trust_root_path.read_text(encoding="utf-8"))
        trust_root["supplied_by"] = "tampered-after-caller-pinning"
        self.trust_root_path.write_text(
            json.dumps(trust_root, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self.assertIn("trust:external_root_hash", self.codes())

    def test_58_reject_cannot_satisfy_representative_image_approval(self) -> None:
        self.assertCode(
            "authority:decision_value",
            lambda p: self.add_author_representative_decision(p, decision_value="reject"),
            refresh_external_trust_root=True,
        )

    def test_59_incompatible_asserted_state_cannot_satisfy_approval(self) -> None:
        self.assertCode(
            "authority:asserted_state",
            lambda p: self.add_author_representative_decision(p, asserted_state="rejected"),
            refresh_external_trust_root=True,
        )

    def test_60_positive_author_approval_remains_admissible(self) -> None:
        documents = load_package(self.root)
        self.add_author_representative_decision(documents)
        save_package(self.root, documents)
        self.trust_root_sha256 = write_external_trust_root(self.root, self.trust_root_path)
        result = self.result()
        self.assertTrue(result["valid"], result["issues"])


if __name__ == "__main__":
    unittest.main()
