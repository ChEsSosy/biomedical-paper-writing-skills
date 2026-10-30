#!/usr/bin/env python3
"""Focused end-to-end tests for Module 06 integration candidate 0.1.1."""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_SCRIPTS = PACKAGE_ROOT / "integration" / "scripts"
if not INTEGRATION_SCRIPTS.is_dir():
    INTEGRATION_SCRIPTS = PACKAGE_ROOT / "scripts"
sys.path.insert(0, str(INTEGRATION_SCRIPTS))

from integration_runtime import (  # noqa: E402
    canonical_sha256,
    describe_artifact,
    file_sha256,
    payload_sha256,
    process_request,
    read_json,
    write_json,
)
from validate_integrity_bundle import validate as validate_bundle  # noqa: E402


VENDOR = PACKAGE_ROOT / "vendor"
STAMP = "2026-09-06T00:00:00Z"

PRODUCERS = {
    "article_revision": {
        "skill_name": "article-polisher", "skill_package_version": "0.1.7",
        "package_manifest_sha256": "c517643b4c9ea3bb5765314b4d07e927c4a29ddebff0dcd5d1c1584f508e7074",
        "expected_inventory_file_sha256": "32dbca7d3ab4ad49f613a5973458e3bb1be7f69e82ae4bb9cb86866941f3d61c",
        "producer_interface": "module03_revision_qc_bundle", "producer_interface_version": "0.1.2",
    },
    "review_revision": {
        "skill_name": "review-architect-polisher", "skill_package_version": "0.1.7",
        "package_manifest_sha256": "60a734ee8e7f32f543210e40fac72ee797a781499eb8997342eaaf5e6dd04f08",
        "expected_inventory_file_sha256": "bc851bc3ef180dab72598ddbe23c90b643496c37fb0b2231892fb20edf0ee14d",
        "producer_interface": "phase7b_revision_bundle", "producer_interface_version": "0.1.0",
    },
    "figure_qc": {
        "skill_name": "scientific-figure-designer", "skill_package_version": "0.1.0", "build_generation": "0.1.2",
        "package_manifest_sha256": "897e31b93d8c6a997d3308b0dcf5cb5c4d4d3d7f3a351cc04f15ec6cee6a2429",
        "expected_inventory_file_sha256": "e5a6eed0848d6c27447120893c99fbc0cd9fc54c10366bd091c7865efd4f1476",
        "producer_interface": "module05_figure_qc_bundle", "producer_interface_version": "0.1.0",
    },
}

CONSUMERS = {
    "article_revision": "module06_article_revision_admission",
    "review_revision": "module06_review_revision_admission",
    "figure_qc": "module06_figure_qc_admission",
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def dump(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def descriptor(root: Path, path: Path, artifact_class: str, *, phase: str | None = None, authority: bool = False) -> dict[str, Any]:
    record = describe_artifact(path, artifact_class, phase=phase, authority=authority)
    record["path"] = path.resolve().relative_to(root.resolve()).as_posix()
    return record


def request(route: str, artifacts: list[dict[str, Any]], producer_validation: dict[str, Any], domains: list[str]) -> dict[str, Any]:
    return {
        "schema_name": "module06_integration_admission_request", "schema_version": "0.1.0",
        "request_id": f"request:{route}", "created_at": STAMP, "route": route,
        "consumer_interface": CONSUMERS[route], "consumer_interface_version": "0.1.0",
        "producer": copy.deepcopy(PRODUCERS[route]), "artifacts": artifacts,
        "producer_validation": producer_validation, "requested_domains": domains,
        "claims": {"admission_passed": False, "scientific_truth_claimed": False, "author_approval_claimed": False},
    }


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workspace = tempfile.TemporaryDirectory(prefix="m06i-")
        cls.root = Path(cls.workspace.name)
        cls.article_root, cls.article_request = cls._article_fixture(cls.root / "article")
        cls.review_root, cls.review_request = cls._review_fixture(cls.root / "review")
        cls.figure8a_root, cls.figure8a_request = cls._figure8a_fixture(cls.root / "figure8a")
        cls.figure8b_root, cls.figure8b_request = cls._figure8b_fixture(cls.root / "figure8b")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.workspace.cleanup()

    @classmethod
    def _article_fixture(
        cls, root: Path, *, blocking_query: bool = False, referenced_upstream: bool = False,
    ) -> tuple[Path, dict[str, Any]]:
        root.mkdir(parents=True)
        package = VENDOR / "m03"
        module = load_module("m06_article_fixture", package / "tests" / "test_patch_application.py")
        source = module.materialize_source()
        upstream_values: list[dict[str, Any]] = []
        if referenced_upstream:
            plan, claim_map = module.approved_provenance_closure(source)
            upstream_values = [plan, claim_map]
            contract_value = module.contract(source, mode="medium", allowed=["information_reorder"])
            operation = module.operation(
                source,
                operation_type="information_reorder",
                replacements=["Viability was reduced by 20% by the treatment."],
            )
            operation["source_proposition_ids"] = ["claim:result-1"]
            operation["upstream_artifact_refs"] = [
                module.upstream_reference(value) for value in upstream_values
            ]
            proposal_value = module.proposal(source, contract_value, [operation])
        else:
            contract_value = module.contract(source)
            proposal_value = module.proposal(source, contract_value, [module.operation(source)])
        if blocking_query:
            proposal_value["author_queries"] = [{
                "query_id": "query:m06:article-unresolved",
                "query_class": "scientific_judgment",
                "question": "Does the author approve the unchanged discussion interpretation?",
                "affected_unit_ids": ["paragraph:discussion:1"],
                "blocks_revision": True,
                "resolution_status": "unresolved",
            }]
        outputs = module.apply_revision_proposal(
            source, contract_value, proposal_value, module.upstream_index(*upstream_values)
        )
        paths = {"source_document": dump(root / "source.json", source), "revision_contract": dump(root / "revision-contract.json", contract_value)}
        for name, value in outputs.items():
            paths[name] = dump(root / name, value)
        classes = {
            "source_document": "source_document", "candidate-document.json": "candidate_document",
            "change-manifest.json": "change_manifest", "author-query-list.json": "author_query_list",
            "revision-lineage-map.json": "revision_lineage_map", "change-inventory.json": "article_polisher_change_inventory",
            "patch-application-receipt.json": "article_polisher_patch_application_receipt", "revision_contract": "revision_contract",
        }
        for position, value in enumerate(upstream_values, start=1):
            name = f"upstream-artifact-{position}"
            paths[name] = dump(root / f"{name}.json", value)
            classes[name] = "upstream_artifact"
        artifacts = [
            descriptor(root, path, classes[name], authority=(classes[name] == "revision_contract"))
            for name, path in paths.items()
        ]
        return root, request("article_revision", artifacts, {}, ["text_preservation"])

    @classmethod
    def _review_fixture(cls, root: Path, *, blocking_query: bool = False) -> tuple[Path, dict[str, Any]]:
        root.mkdir(parents=True)
        package = VENDOR / "m04"
        sys.path.insert(0, str(package / "scripts"))
        fixtures = load_module("m06_review_fixtures", package / "tests" / "phase7b" / "fixture_factory.py")
        patch = load_module("m06_review_patch", package / "scripts" / "apply_review_revision_proposal.py")
        case = fixtures.light_case()
        if blocking_query:
            case["proposal"]["unresolved_queries"] = [{
                "query_id": "query:m06:review-unresolved",
                "query_type": "scientific_judgment",
                "question": "Does the author approve the unchanged introductory interpretation?",
                "affected_unit_ids": [case["source"]["units"][0]["unit_id"]],
                "blocks_revision": True,
                "status": "unresolved",
            }]
            fixtures.refresh_proposal(case["proposal"])
        outputs = patch.apply_review_revision_proposal(
            case["source"], case["permission"], case["expected_permission_sha256"], case["proposal"], case["phase7a"],
        )
        paths = {
            "source_document": dump(root / "source.json", case["source"]),
            "review_revision_permission": dump(root / "permission.json", case["permission"]),
            "review_revision_proposal": dump(root / "proposal.json", case["proposal"]),
            "referenced_phase7a_closure": dump(root / "phase7a.json", case["phase7a"]),
        }
        output_classes = {
            "candidate-review.json": "candidate_document", "review-revision-lineage-map.json": "review_revision_lineage_map",
            "review-protected-change-inventory.json": "review_protected_change_inventory",
            "review-author-query-list.json": "review_author_query_list", "review-change-manifest.json": "review_change_manifest",
            "review-patch-application-receipt.json": "review_patch_application_receipt",
            "review-package-validation-result.json": "review_package_validation_result",
        }
        for name, value in outputs.items():
            paths[output_classes[name]] = dump(root / name, value)
        artifacts = [
            descriptor(root, path, name, authority=name in {"review_revision_permission", "referenced_phase7a_closure"})
            for name, path in paths.items()
        ]
        return root, request(
            "review_revision", artifacts,
            {"expected_permission_sha256": case["expected_permission_sha256"]},
            ["text_preservation", "consensus_adjudication"],
        )

    @classmethod
    def _phase8a_descriptors(cls, invocation_root: Path, package_root: Path, trust_root: Path, qc_path: Path) -> list[dict[str, Any]]:
        paths: list[tuple[Path, str, str | None, bool]] = [
            (package_root / "design-package-manifest.json", "design_package_manifest", None, False),
            (package_root / "source-data-manifest.json", "source_data_manifest", None, False),
            (trust_root, "trusted_inputs_root", None, True), (qc_path, "figure_qc", "phase8a", False),
        ]
        paths.extend((path, "figure_card", None, False) for path in sorted(package_root.glob("figure-card-*.json")))
        paths.extend((path, "figure_contract", None, False) for path in sorted(package_root.glob("figure-contract-*.json")))
        paths.extend((path, "plot_recipe", None, False) for path in sorted(package_root.glob("plot-recipe-*.json")))
        return [descriptor(invocation_root, path, kind, phase=phase, authority=authority) for path, kind, phase, authority in paths]

    @classmethod
    def _figure8a_fixture(cls, root: Path) -> tuple[Path, dict[str, Any]]:
        root.mkdir(parents=True)
        package = VENDOR / "m05"
        factory = load_module("m06_phase8a_factory", package / "candidate" / "tests" / "fixture_factory.py")
        design_root = root / "design"
        factory.build_valid_package(design_root)
        trust_root = root / "trusted-inputs-root.json"
        trust_hash = factory.write_external_trust_root(design_root, trust_root)
        command = [
            sys.executable, "-B", str(package / "candidate" / "scripts" / "validate_figure_package.py"),
            str(design_root), "--trust-root", str(trust_root), "--trust-root-sha256", trust_hash,
        ]
        completed = subprocess.run(command, text=True, capture_output=True, check=True)
        result = json.loads(completed.stdout)
        qc_path = dump(root / "phase8a-figure-qc.json", result["qc"])
        artifacts = cls._phase8a_descriptors(root, design_root, trust_root, qc_path)
        return root, request(
            "figure_qc", artifacts,
            {"variant": "phase8a_design", "phase8a_package_root": "design", "expected_trust_root_sha256": trust_hash},
            ["identity_state_handoff_closure"],
        )

    @classmethod
    def _figure8b_fixture(cls, root: Path) -> tuple[Path, dict[str, Any]]:
        root.mkdir(parents=True)
        package = VENDOR / "m05"
        sys.path.insert(0, str(package / "phase8b-candidate" / "scripts"))
        factory = load_module("m06_phase8b_factory", package / "phase8b-candidate" / "tests" / "fixture_factory.py")
        validator = load_module("m06_phase8b_validator", package / "phase8b-candidate" / "scripts" / "validate_phase8b_package.py")
        context = factory.build_complete_package(root / "fixture")
        fresh = validator.validate_phase8b_package(**factory.validation_kwargs(context))
        cls.assertTrue(cls, fresh["valid"])
        phase8a_qc_path = dump(root / "phase8a-figure-qc.json", context["phase8a_result"]["qc"])
        phase8b_qc_path = dump(root / "phase8b-figure-qc.json", fresh["qc"])
        artifacts = cls._phase8a_descriptors(root, context["package_root"], context["trust_root_path"], phase8a_qc_path)
        extra = [
            (context["receipt_path"], "phase8a_admission_receipt", False),
            (context["profile_path"], "backend_environment_profile", False),
            (context["plan_path"], "bounded_program_plan", False),
            (context["execution_manifest_path"], "prototype_execution_manifest", False),
            (context["authorization_path"], "prototype_execution_authorization", True),
            (context["execution_result_path"], "prototype_execution_result", False),
            (context["render_path"], "render_output_manifest", False),
            (context["inspection_path"], "render_inspection_record", False),
        ]
        artifacts.extend(descriptor(root, path, kind, authority=authority) for path, kind, authority in extra)
        artifacts.append(descriptor(root, phase8b_qc_path, "figure_qc", phase="phase8b"))
        manifest = context["documents"]["manifest"]
        return root, request(
            "figure_qc", artifacts,
            {
                "variant": "phase8b_prototype",
                "phase8a_package_root": context["package_root"].relative_to(root).as_posix(),
                "expected_trust_root_sha256": context["trust_root_file_sha256"],
                "expected_design_package_hash": manifest["design_package_hash"],
            },
            ["identity_state_handoff_closure", "scientific_meaning"],
        )

    def run_case(self, invocation_root: Path, value: dict[str, Any], name: str) -> tuple[dict[str, Any], Path, int]:
        output = self.root / "outputs" / name
        bundle, code = process_request(copy.deepcopy(value), invocation_root, output)
        self.assertEqual([], validate_bundle(output / "module06-integrity-qc-bundle.json", output))
        return bundle, output, code

    def test_article_fresh_validation_projection_and_qc(self) -> None:
        bundle, output, code = self.run_case(self.article_root, self.article_request, "article-positive")
        self.assertEqual(0, code)
        receipt = read_json(output / "module06-integration-admission-receipt.json")
        self.assertEqual("accepted", receipt["admission_state"])
        self.assertTrue((output / "structured-text-projection-receipt.json").is_file())
        self.assertEqual("qc_complete_author_review_required", bundle["terminal_state"])

    def test_review_unimplemented_domain_is_not_passed(self) -> None:
        bundle, output, code = self.run_case(self.review_root, self.review_request, "review-positive")
        self.assertEqual(0, code)
        gate = read_json(output / "module06-gate-report.json")
        consensus = next(item for item in gate["domain_coverage"] if item["domain"] == "consensus_adjudication")
        self.assertFalse(consensus["implemented"])
        self.assertEqual("not_assessed", consensus["assessment_state"])
        self.assertEqual("unassessable", gate["gate_outcome"])
        self.assertEqual("qc_unassessable_author_review_required", bundle["terminal_state"])

    def test_unresolved_blocking_article_query_propagates_to_gate(self) -> None:
        root, value = self._article_fixture(self.root / "article-blocking-query", blocking_query=True)
        _, output, code = self.run_case(root, value, "article-blocking-query")
        self.assertEqual(0, code)
        gate = read_json(output / "module06-gate-report.json")
        self.assertEqual("fail", gate["gate_outcome"])
        findings = [read_json(path) for path in (output / "findings").glob("finding-*.json")]
        query_findings = [item for item in findings if item["check_id"] == "required_author_query_resolution"]
        self.assertEqual(1, len(query_findings))
        self.assertEqual("blocker", query_findings[0]["severity"])

    def test_unresolved_blocking_review_query_propagates_to_gate(self) -> None:
        root, value = self._review_fixture(self.root / "review-blocking-query", blocking_query=True)
        _, output, code = self.run_case(root, value, "review-blocking-query")
        self.assertEqual(0, code)
        gate = read_json(output / "module06-gate-report.json")
        self.assertEqual("fail", gate["gate_outcome"])
        self.assertEqual(1, len(gate["finding_ids"]))

    def test_phase8a_identity_closure_never_becomes_clean_pass(self) -> None:
        bundle, output, code = self.run_case(self.figure8a_root, self.figure8a_request, "figure8a-positive")
        self.assertEqual(0, code)
        gate = read_json(output / "module06-gate-report.json")
        self.assertEqual("unassessable", gate["gate_outcome"])
        self.assertNotEqual("pass", gate["gate_outcome"])
        self.assertTrue(bundle["human_review_required"])

    def test_phase8b_unverified_maturity_remains_degraded(self) -> None:
        _, output, code = self.run_case(self.figure8b_root, self.figure8b_request, "figure8b-positive")
        self.assertEqual(0, code)
        receipt = read_json(output / "module06-integration-admission-receipt.json")
        gate = read_json(output / "module06-gate-report.json")
        self.assertEqual("accepted_degraded", receipt["admission_state"])
        self.assertEqual("unassessable", gate["gate_outcome"])

    def test_artifact_hash_mismatch_blocks(self) -> None:
        value = copy.deepcopy(self.article_request)
        value["artifacts"][0]["file_sha256"] = "0" * 64
        bundle, output, code = self.run_case(self.article_root, value, "article-hash-reject")
        self.assertEqual(1, code)
        self.assertEqual("blocked", bundle["terminal_state"])
        self.assertEqual("rejected", read_json(output / "module06-integration-admission-receipt.json")["admission_state"])

    def test_missing_required_artifact_blocks(self) -> None:
        root, value = self._article_fixture(self.root / "article-missing-artifact")
        value["artifacts"] = [
            item for item in value["artifacts"] if item["artifact_class"] != "change_manifest"
        ]
        bundle, _, code = self.run_case(root, value, "article-missing-artifact")
        self.assertEqual(1, code)
        self.assertEqual("blocked", bundle["terminal_state"])

    def test_producer_validation_failure_blocks(self) -> None:
        root, value = self._article_fixture(self.root / "article-producer-failure")
        original = next(item for item in value["artifacts"] if item["artifact_class"] == "change_manifest")
        manifest = read_json(root / original["path"])
        manifest["changes"][0]["revision_mode"] = "deep"
        mutated_path = dump(root / "change-manifest-producer-invalid.json", manifest)
        replacement = descriptor(root, mutated_path, "change_manifest")
        value["artifacts"] = [replacement if item is original else item for item in value["artifacts"]]
        bundle, output, code = self.run_case(root, value, "article-producer-failure")
        self.assertEqual(1, code)
        self.assertEqual("blocked", bundle["terminal_state"])
        issue = read_json(output / "module06-integration-admission-receipt.json")["issues"][0]
        self.assertEqual("producer:validation", issue["code"])

    def test_admission_request_schema_rejects_extra_property(self) -> None:
        value = copy.deepcopy(self.article_request)
        value["undeclared_extra"] = "schema-invalid-extra"
        _, output, code = self.run_case(self.article_root, value, "request-extra-reject")
        self.assertEqual(1, code)
        receipt = read_json(output / "module06-integration-admission-receipt.json")
        self.assertEqual("request:schema", receipt["issues"][0]["code"])

    def test_admission_request_schema_rejects_invalid_timestamp_safely(self) -> None:
        value = copy.deepcopy(self.article_request)
        value["created_at"] = "not-a-date"
        _, output, code = self.run_case(self.article_root, value, "request-date-reject")
        self.assertEqual(1, code)
        receipt = read_json(output / "module06-integration-admission-receipt.json")
        self.assertEqual("1970-01-01T00:00:00Z", receipt["created_at"])
        self.assertEqual("request:schema", receipt["issues"][0]["code"])

    def test_route_crossing_rejects(self) -> None:
        value = copy.deepcopy(self.article_request)
        value["route"] = "review_revision"
        value["consumer_interface"] = CONSUMERS["review_revision"]
        value["producer_validation"] = {"expected_permission_sha256": "0" * 64}
        value["requested_domains"] = ["text_preservation"]
        bundle, output, code = self.run_case(self.article_root, value, "route-cross-reject")
        self.assertEqual(1, code)
        issue = read_json(output / "module06-integration-admission-receipt.json")["issues"][0]
        self.assertEqual("producer:identity", issue["code"])
        self.assertEqual("rejected", bundle["terminal_state"])

    def test_wrong_producer_package_type_rejects(self) -> None:
        value = copy.deepcopy(self.article_request)
        value["producer"]["skill_name"] = "review-architect-polisher"
        bundle, _, code = self.run_case(self.article_root, value, "producer-type-reject")
        self.assertEqual(1, code)
        self.assertEqual("rejected", bundle["terminal_state"])

    def test_unsupported_route_or_interface_rejects(self) -> None:
        cases = []
        unsupported_route = copy.deepcopy(self.article_request)
        unsupported_route["route"] = "unsupported_route"
        cases.append(("unsupported-route", unsupported_route))
        unsupported_interface = copy.deepcopy(self.article_request)
        unsupported_interface["consumer_interface"] = CONSUMERS["review_revision"]
        cases.append(("unsupported-interface", unsupported_interface))
        for name, value in cases:
            with self.subTest(name=name):
                bundle, _, code = self.run_case(self.article_root, value, name)
                self.assertEqual(1, code)
                self.assertEqual("rejected", bundle["terminal_state"])

    def test_unreferenced_wrong_manuscript_upstream_blocks(self) -> None:
        root, value = self._article_fixture(self.root / "article-extra-upstream")
        module = load_module(
            "m06_article_extra_fixture", VENDOR / "m03" / "tests" / "test_patch_application.py"
        )
        plan = module.approved_plan("other-manuscript")
        plan_path = dump(root / "unreferenced-wrong-manuscript-plan.json", plan)
        value["artifacts"].append(descriptor(root, plan_path, "upstream_artifact"))
        bundle, output, code = self.run_case(root, value, "article-extra-upstream")
        self.assertEqual(1, code)
        self.assertEqual("blocked", bundle["terminal_state"])
        issue = read_json(output / "module06-integration-admission-receipt.json")["issues"][0]
        self.assertEqual("closure:upstream_extra", issue["code"])

    def test_exact_referenced_upstream_closure_and_missing_case(self) -> None:
        root, value = self._article_fixture(
            self.root / "article-referenced-upstream", referenced_upstream=True
        )
        _, _, code = self.run_case(root, value, "article-referenced-upstream")
        self.assertEqual(0, code)
        missing = copy.deepcopy(value)
        first_upstream = next(
            item for item in missing["artifacts"] if item["artifact_class"] == "upstream_artifact"
        )
        missing["artifacts"].remove(first_upstream)
        bundle, output, code = self.run_case(root, missing, "article-referenced-upstream-missing")
        self.assertEqual(1, code)
        self.assertEqual("blocked", bundle["terminal_state"])
        issue = read_json(output / "module06-integration-admission-receipt.json")["issues"][0]
        self.assertEqual("closure:upstream_missing", issue["code"])

    def test_projection_omission_or_normalization_fails_closed(self) -> None:
        value = copy.deepcopy(self.article_request)
        candidate = next(item for item in value["artifacts"] if item["artifact_class"] == "candidate_document")
        path = self.article_root / candidate["path"]
        original = read_json(path)
        mutated = copy.deepcopy(original)
        mutated["paragraphs"][0]["text"] += " hidden"
        mutated_path = dump(self.article_root / "candidate-projection-invalid.json", mutated)
        replacement = descriptor(self.article_root, mutated_path, "candidate_document")
        value["artifacts"] = [replacement if item is candidate else item for item in value["artifacts"]]
        _, output, code = self.run_case(self.article_root, value, "projection-reject")
        self.assertEqual(1, code)
        self.assertEqual("blocked", read_json(output / "module06-gate-report.json")["terminal_state"])

    def test_output_validator_rejects_unimplemented_pass(self) -> None:
        _, output, code = self.run_case(self.figure8a_root, self.figure8a_request, "figure-mutation-source")
        self.assertEqual(0, code)
        gate_path = output / "module06-gate-report.json"
        gate = read_json(gate_path)
        target = next(item for item in gate["domain_coverage"] if item["implemented"] is False)
        target["assessment_state"] = "passed"
        write_json(gate_path, gate)
        issues = validate_bundle(output / "module06-integrity-qc-bundle.json", output)
        self.assertTrue(any("unimplemented domain" in item or "file hash mismatch" in item for item in issues))

    def _copy_output(self, source: Path, name: str) -> Path:
        target = self.root / "outputs" / name
        shutil.copytree(source, target)
        return target

    def _rebind_mutated_json(self, output: Path, relative: str, self_hash_field: str | None = None) -> None:
        path = output / relative
        value = read_json(path)
        if self_hash_field:
            value[self_hash_field] = payload_sha256(value, self_hash_field)
        write_json(path, value)
        bundle_path = output / "module06-integrity-qc-bundle.json"
        bundle = read_json(bundle_path)
        reference = next(item for item in bundle["output_artifacts"] if item["path"] == relative)
        reference["file_sha256"] = file_sha256(path)
        reference["canonical_sha256"] = canonical_sha256(value)
        if relative == "module06-integration-admission-receipt.json":
            bundle["admission_receipt_ref"]["sha256"] = value["receipt_sha256"]
        if relative == "module06-gate-report.json":
            bundle["gate_report_ref"]["sha256"] = value["gate_report_sha256"]
        bundle["bundle_sha256"] = payload_sha256(bundle, "bundle_sha256")
        write_json(bundle_path, bundle)

    def test_output_schemas_reject_hash_consistent_invalid_artifacts(self) -> None:
        _, article_output, code = self.run_case(self.article_root, self.article_request, "schema-source-article")
        self.assertEqual(0, code)
        mutations = [
            ("module06-gate-report.json", "gate_report_sha256", "gate_outcome", "NOT_IN_SCHEMA_ENUM"),
            ("module06-integration-admission-receipt.json", "receipt_sha256", "admission_state", "NOT_IN_SCHEMA_ENUM"),
            ("structured-text-projection-receipt.json", "projection_sha256", "encoding", "utf-16"),
        ]
        for position, (relative, self_field, field, invalid) in enumerate(mutations, start=1):
            with self.subTest(relative=relative):
                output = self._copy_output(article_output, f"schema-invalid-{position}")
                value = read_json(output / relative)
                value[field] = invalid
                write_json(output / relative, value)
                self._rebind_mutated_json(output, relative, self_field)
                issues = validate_bundle(output / "module06-integrity-qc-bundle.json", output)
                self.assertTrue(any("schema" in item for item in issues), issues)

        bundle_output = self._copy_output(article_output, "schema-invalid-bundle")
        bundle_path = bundle_output / "module06-integrity-qc-bundle.json"
        bundle = read_json(bundle_path)
        bundle["terminal_state"] = "NOT_IN_SCHEMA_ENUM"
        bundle["bundle_sha256"] = payload_sha256(bundle, "bundle_sha256")
        write_json(bundle_path, bundle)
        self.assertTrue(any("bundle schema" in item for item in validate_bundle(bundle_path, bundle_output)))

        _, figure_output, figure_code = self.run_case(self.figure8a_root, self.figure8a_request, "schema-source-figure")
        self.assertEqual(0, figure_code)
        finding_output = self._copy_output(figure_output, "schema-invalid-finding")
        finding_path = next((finding_output / "findings").glob("finding-*.json"))
        finding = read_json(finding_path)
        finding["severity"] = "NOT_IN_SCHEMA_ENUM"
        relative = finding_path.relative_to(finding_output).as_posix()
        write_json(finding_path, finding)
        self._rebind_mutated_json(finding_output, relative)
        self.assertTrue(any("schema" in item for item in validate_bundle(
            finding_output / "module06-integrity-qc-bundle.json", finding_output
        )))


if __name__ == "__main__":
    unittest.main()
