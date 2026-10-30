"""Synthetic Phase 8B package factory; no real scientific data are used."""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any


PHASE8B_ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = PHASE8B_ROOT.parent
SCRIPTS = PHASE8B_ROOT / "scripts"
PHASE8A_FIXTURE_FACTORY = MODULE_ROOT / "candidate" / "tests" / "fixture_factory.py"
for path in (SCRIPTS,):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from generate_restricted_python import generate_program  # noqa: E402
from inspect_render_metadata import inspect_render  # noqa: E402
from phase8b_runtime import (  # noqa: E402
    execution_package_hash, file_sha256, load_phase8a_validator, payload_sha256, read_json, write_json,
)
from probe_backend_environment import probe_current  # noqa: E402
from run_prototype import run_prototype  # noqa: E402
from validate_phase8b_admission import admit_phase8a  # noqa: E402


STAMP = "2026-09-01T00:00:00Z"


def _load_phase8a_factory():
    spec = importlib.util.spec_from_file_location("phase8b_phase8a_fixture_factory", PHASE8A_FIXTURE_FACTORY)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load frozen Phase 8A fixture factory")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_ready_phase8a_package(root: Path) -> dict[str, Any]:
    factory = _load_phase8a_factory()
    package_root = root / "phase8a-package"
    factory.build_valid_package(package_root)
    documents = factory.load_package(package_root)
    factory.set_maturity(documents, "ready_for_prototype")
    for card in documents["cards"]:
        card["visual_encoding"]["plot_archetype"] = "raw_points_only"
    for recipe in documents["recipes"]:
        recipe["aggregation"] = "raw observations only"
        for layer in recipe["layers"]:
            layer["summary_intent"] = "no summary layer; show raw observations only"
            layer["uncertainty_representation"] = "not applicable; no uncertainty layer"
    factory.save_package(package_root, documents)
    caller_root = root / "caller-authority"
    caller_root.mkdir(parents=True, exist_ok=True)
    trust_root_path = caller_root / "phase8a-trust-root.json"
    trust_root_file_sha256 = factory.write_external_trust_root(package_root, trust_root_path)
    validator = load_phase8a_validator()
    result = validator.validate_figure_package(
        package_root, trust_root_path=trust_root_path,
        expected_trust_root_sha256=trust_root_file_sha256,
    )
    if not result["valid"]:
        raise RuntimeError(f"ready_for_prototype fixture failed Phase 8A: {result['issues']}")
    documents = factory.load_package(package_root)
    return {
        "factory": factory, "package_root": package_root, "documents": documents,
        "trust_root_path": trust_root_path, "trust_root_file_sha256": trust_root_file_sha256,
        "phase8a_result": result,
    }


def _hash_ref(identity: str, version: str, sha256: str) -> dict[str, str]:
    return {"id": identity, "version": version, "sha256": sha256}


def build_plan(phase8a: dict[str, Any], receipt: dict[str, Any], execution_root: Path, *, suffix: str = "1") -> dict[str, Any]:
    docs = phase8a["documents"]
    manifest = docs["manifest"]
    source = docs["source_manifest"]["source_records"][0]
    trusted = docs["source_collection"]["records"][0]
    contract = docs["contracts"][0]
    analysis_ids = {item["analysis_output_id"] for item in docs["analysis_collection"]["records"]}
    operations: list[dict[str, Any]] = []
    for recipe in docs["recipes"]:
        layer_id = recipe["layers"][0]["layer_id"]
        variable_bindings = {item["aesthetic"]: item["variable_id"] for item in recipe["variable_mappings"]}
        common = {
            "figure_id": recipe["figure_id"], "panel_id": recipe["panel_id"], "recipe_id": recipe["recipe_id"],
            "layer_id": layer_id, "source_data_ids": recipe["source_data_ids"],
            "variable_bindings": variable_bindings,
        }
        operations.append({"operation_id": f"axes-{recipe['panel_id']}", "operation": "draw_axes", **common, "analysis_output_ids": [], "parameters": {"x_unit": "category", "y_unit": "arbitrary_unit"}})
        operations.append({"operation_id": f"points-{recipe['panel_id']}", "operation": "draw_raw_points", **common, "analysis_output_ids": [], "parameters": {"point_offset": "deterministic_index_offset"}})
        supplied = [item for item in recipe["statistical_annotations"] if item["status"] == "supplied"]
        for annotation in supplied:
            analysis_id = annotation["analysis_output_ref"]["analysis_output_id"]
            if analysis_id not in analysis_ids:
                raise RuntimeError("fixture annotation analysis binding is unresolved")
            operations.append({"operation_id": f"annotation-{recipe['panel_id']}", "operation": "draw_supplied_annotation", **common, "analysis_output_ids": [analysis_id], "parameters": {"symbol": annotation["symbol"]}})
        operations.append({"operation_id": f"legend-{recipe['panel_id']}", "operation": "draw_legend", **common, "analysis_output_ids": [], "parameters": {"intent": "define_group_colors"}})
    first_recipe = docs["recipes"][0]
    common = {
        "figure_id": first_recipe["figure_id"], "panel_id": first_recipe["panel_id"], "recipe_id": first_recipe["recipe_id"],
        "layer_id": first_recipe["layers"][0]["layer_id"], "source_data_ids": first_recipe["source_data_ids"],
        "variable_bindings": {item["aesthetic"]: item["variable_id"] for item in first_recipe["variable_mappings"]},
        "analysis_output_ids": [],
    }
    for name in ("export_svg", "export_png", "export_plot_data", "export_session_metadata"):
        operations.append({"operation_id": name, "operation": name, **common, "parameters": {"scope": "declared_outputs_only"}})
    outputs = [
        {"role": "vector_prototype", "path": "prototype.svg", "format": "svg", "panel_ids": contract["ordered_panel_ids"]},
        {"role": "raster_prototype", "path": "prototype.png", "format": "png", "panel_ids": contract["ordered_panel_ids"]},
        {"role": "plotting_data", "path": "plot_data.tsv", "format": "tsv", "panel_ids": contract["ordered_panel_ids"]},
        {"role": "session_metadata", "path": "session.json", "format": "json", "panel_ids": contract["ordered_panel_ids"]},
    ]
    plan: dict[str, Any] = {
        "schema_name": "bounded_program_plan", "schema_version": "0.1.0",
        "plan_id": f"bounded-plan-{suffix}", "plan_sha256": "0" * 64,
        "generator_id": "phase8b-restricted-python-generator", "generator_version": "0.1.0", "backend": "restricted_python",
        "design_package_ref": _hash_ref(manifest["design_package_id"], manifest["design_package_version"], manifest["design_package_hash"]),
        "admission_receipt_ref": _hash_ref(receipt["receipt_id"], receipt["schema_version"], receipt["receipt_sha256"]),
        "input_bindings": [{
            "trusted_input_id": trusted["trusted_input_id"], "source_data_id": trusted["source_data_id"],
            "path": str((phase8a["package_root"] / trusted["path"]).resolve()), "format": trusted["format"],
            "sha256": trusted["expected_sha256"], "variables": [item["variable_id"] for item in source["variables"]],
            "units": source["units"],
        }],
        "output_directory": str((execution_root / "outputs" / f"run-{suffix}").resolve()),
        "figure_id": contract["figure_id"], "panel_order": contract["ordered_panel_ids"],
        "group_order": docs["recipes"][0]["ordering"],
        "palette": {item["semantic_key"]: item["value"] for item in contract["palette_semantics"]},
        "operations": operations, "outputs": outputs,
        "seed_policy": {"stochastic_operations": False, "seed": None},
    }
    plan["plan_sha256"] = payload_sha256(plan, "plan_sha256")
    return plan


def make_inspection(render: dict[str, Any], *, inspector_class: str = "deterministic_tool", blocker: bool = False) -> dict[str, Any]:
    outputs = [item for item in render["outputs"] if item["format"] in {"png", "svg"}]
    record: dict[str, Any] = {
        "schema_name": "render_inspection_record", "schema_version": "0.1.0",
        "inspection_id": "inspection-1", "inspection_sha256": "0" * 64,
        "render_manifest_ref": _hash_ref(render["render_manifest_id"], render["schema_version"], render["render_manifest_sha256"]),
        "inspector_class": inspector_class,
        "inspector_identity": "phase8b-metadata-inspector" if inspector_class == "deterministic_tool" else "declared-model-inspector",
        "tool_versions": ["phase8b-0.1.0"], "inspected_at": STAMP,
        "occurrence_evidence": "record_only_not_proof" if inspector_class == "deterministic_tool" else "orchestration_declared_not_receipted",
        "inspected_outputs": [{"role": item["role"], "path": item["path"], "sha256": item["sha256"], "visible_evidence_locators": ["two declared panel frames"]} for item in outputs],
        "assessed_domains": ["record_structure", "declared_panel_presence"] if inspector_class == "deterministic_tool" else ["visual_legibility", "panel_balance"],
        "unassessed_domains": ["scientific_validity", "raw_image_integrity", "copyright_clearance", "journal_compliance", "author_approval"],
        "findings": ([{"finding_id": "visual-1", "severity": "blocker", "domain": "panel_balance", "message": "declared visible imbalance requires revision", "route": "realization_correction"}] if blocker else []),
        "no_authority": True,
        "provenance_limitations": ["record/hash closure does not prove cognitive visual inspection", "no trusted inspection-execution receipt exists"],
    }
    record["inspection_sha256"] = payload_sha256(record, "inspection_sha256")
    return record


def build_complete_package(root: Path, *, inspection_class: str = "deterministic_tool", inspection_blocker: bool = False, suffix: str = "1") -> dict[str, Any]:
    phase8a = build_ready_phase8a_package(root)
    manifest = phase8a["documents"]["manifest"]
    qc = phase8a["phase8a_result"]["qc"]
    receipt, issues = admit_phase8a(
        phase8a["package_root"], phase8a["trust_root_path"], phase8a["trust_root_file_sha256"],
        manifest["design_package_hash"], qc["artifact_id"], qc["schema_version"],
        qc["figure_qc_sha256"],
        mode="prototype_execution_and_inspection", created_at=STAMP,
    )
    if receipt is None or issues:
        raise RuntimeError(f"fixture admission failed: {issues}")
    execution_root = root / "phase8b-execution"
    execution_root.mkdir(parents=True, exist_ok=True)
    receipt_path = execution_root / "phase8a-admission-receipt.json"
    write_json(receipt_path, receipt)
    profile = probe_current(created_at=STAMP)
    profile_path = execution_root / "backend-environment-profile.json"
    write_json(profile_path, profile)
    plan = build_plan(phase8a, receipt, execution_root, suffix=suffix)
    plan_path = execution_root / "bounded-program-plan.json"
    write_json(plan_path, plan)
    program_path = execution_root / "generated-prototype.py"
    program = generate_program(plan, program_path)
    record_directory = execution_root / "records" / f"run-{suffix}"
    input_bindings = [{"input_id": item["trusted_input_id"], "path": item["path"], "sha256": item["sha256"]} for item in plan["input_bindings"]]
    manifest_b: dict[str, Any] = {
        "schema_name": "prototype_execution_manifest", "schema_version": "0.1.0",
        "execution_id": f"execution-{suffix}", "execution_manifest_sha256": "0" * 64, "execution_package_hash": "0" * 64,
        "mode": "prototype_execution_and_inspection",
        "admission_receipt_ref": _hash_ref(receipt["receipt_id"], receipt["schema_version"], receipt["receipt_sha256"]),
        "backend_profile_ref": _hash_ref(profile["profile_id"], profile["schema_version"], profile["profile_sha256"]),
        "plan_ref": _hash_ref(plan["plan_id"], plan["schema_version"], plan["plan_sha256"]),
        "program": program, "input_bindings": input_bindings,
        "output_directory": plan["output_directory"], "record_directory": str(record_directory.resolve()),
        "command": [profile["executable_path"], "-B", str(program_path.resolve())],
        "parameters": {"data_scope": "synthetic_only"}, "expected_outputs": plan["outputs"],
        "authorization_ref": _hash_ref("pending", "0.1.0", "0" * 64), "authorization_state": "externally_authorized",
    }
    manifest_b["execution_package_hash"] = execution_package_hash(manifest_b)
    authorization: dict[str, Any] = {
        "schema_name": "prototype_execution_authorization", "schema_version": "0.1.0",
        "authorization_id": f"execution-authorization-{suffix}", "authorization_sha256": "0" * 64,
        "authorization_origin": "caller", "authorization_state": "caller_accepted", "authorized_at": STAMP,
        "execution_package_hash": manifest_b["execution_package_hash"], "program_sha256": program["sha256"],
        "backend_profile_ref": _hash_ref(profile["profile_id"], profile["schema_version"], profile["profile_sha256"]),
        "admission_receipt_ref": _hash_ref(receipt["receipt_id"], receipt["schema_version"], receipt["receipt_sha256"]),
        "input_bindings": input_bindings,
        "authorized_write_roots": sorted([manifest_b["output_directory"], manifest_b["record_directory"]]),
        "command": manifest_b["command"], "parameters": manifest_b["parameters"], "scope": "single_synthetic_prototype_run",
    }
    authorization["authorization_sha256"] = payload_sha256(authorization, "authorization_sha256")
    authorization_path = root / "caller-authority" / f"execution-authorization-{suffix}.json"
    write_json(authorization_path, authorization)
    authorization_file_sha256 = file_sha256(authorization_path)
    manifest_b["authorization_ref"] = _hash_ref(authorization["authorization_id"], authorization["schema_version"], authorization["authorization_sha256"])
    manifest_b["execution_manifest_sha256"] = payload_sha256(manifest_b, "execution_manifest_sha256")
    manifest_path = execution_root / "execution-manifest.json"
    write_json(manifest_path, manifest_b)
    execution_result, run_issues = run_prototype(
        manifest_path, receipt_path, profile_path, plan_path,
        authorization_path, authorization_file_sha256,
        phase8a["package_root"], phase8a["trust_root_path"],
        phase8a["trust_root_file_sha256"], manifest["design_package_hash"],
        qc["artifact_id"], qc["schema_version"], qc["figure_qc_sha256"],
    )
    if execution_result is None or run_issues:
        raise RuntimeError(f"fixture execution failed: {run_issues}")
    result_path = record_directory / "execution-result.json"
    render, render_issues = inspect_render(manifest_b, execution_result, receipt, created_at=STAMP)
    if render is None or render_issues:
        raise RuntimeError(f"fixture render inspection failed: {render_issues}")
    render_path = record_directory / "render-output-manifest.json"
    write_json(render_path, render)
    inspection = make_inspection(render, inspector_class=inspection_class, blocker=inspection_blocker)
    inspection_path = record_directory / "render-inspection-record.json"
    write_json(inspection_path, inspection)
    return {
        **phase8a,
        "receipt": receipt, "receipt_path": receipt_path,
        "profile": profile, "profile_path": profile_path,
        "plan": plan, "plan_path": plan_path, "program_path": program_path,
        "execution_manifest": manifest_b, "execution_manifest_path": manifest_path,
        "authorization": authorization, "authorization_path": authorization_path, "authorization_file_sha256": authorization_file_sha256,
        "execution_result": execution_result, "execution_result_path": result_path,
        "render": render, "render_path": render_path,
        "inspection": inspection, "inspection_path": inspection_path,
        "execution_root": execution_root,
    }


def validation_kwargs(context: dict[str, Any]) -> dict[str, Any]:
    manifest = context["documents"]["manifest"]
    return {
        "phase8a_package_root": context["package_root"], "trust_root_path": context["trust_root_path"],
        "expected_trust_root_sha256": context["trust_root_file_sha256"],
        "expected_design_package_hash": manifest["design_package_hash"],
        "expected_phase8a_figure_qc_sha256": context["phase8a_result"]["qc"]["figure_qc_sha256"],
        "expected_phase8a_qc_artifact_id": context["phase8a_result"]["qc"]["artifact_id"],
        "expected_phase8a_qc_schema_version": context["phase8a_result"]["qc"]["schema_version"],
        "admission_receipt_path": context["receipt_path"], "profile_path": context["profile_path"],
        "plan_path": context["plan_path"], "execution_manifest_path": context["execution_manifest_path"],
        "authorization_path": context["authorization_path"], "expected_authorization_file_sha256": context["authorization_file_sha256"],
        "execution_result_path": context["execution_result_path"], "render_manifest_path": context["render_path"],
        "inspection_paths": [context["inspection_path"]],
    }
