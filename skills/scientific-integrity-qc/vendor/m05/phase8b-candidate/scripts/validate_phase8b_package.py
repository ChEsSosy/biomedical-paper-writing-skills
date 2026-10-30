#!/usr/bin/env python3
"""End-to-end deterministic validator for the Phase 8B minimum package."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Iterable

from generate_restricted_python import SCRIPT_PATH as GENERATOR_PATH, validate_plan
from inspect_render_metadata import inspect_render
from phase8b_runtime import (
    CONTRACT_VERSION,
    PHASE8A_VALIDATOR,
    execution_package_hash,
    file_sha256,
    payload_sha256,
    read_json,
    utc_now,
    validate_schema,
)
from probe_backend_environment import verify_profile
from run_prototype import validate_execution_inputs
from validate_generated_program import validate_program
from validate_phase8b_admission import admit_phase8a


PRESENTATION_FIELDS = {
    "layout.panel_spacing", "layout.panel_width", "legend.position",
    "typography.font_size", "label.position",
}
FORBIDDEN_MODEL_AUTHORITY_DOMAINS = {
    "scientific_validity", "raw_image_integrity", "copyright_clearance",
    "journal_compliance", "author_approval",
}
VALIDATOR_VERSION = "0.1.1"


def add_issue(issues: list[dict[str, str]], code: str, message: str, path: str = "$", severity: str = "error") -> None:
    issues.append({"layer": "deterministic", "path": path, "code": code, "message": message, "review_route": "deterministic", "severity": severity})


def _dedupe_issues(issues: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in issues:
        key = (str(item.get("code")), str(item.get("path")), str(item.get("message")))
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def _blocked_result(
    issues: list[dict[str, str]], fresh_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic failure envelope without inventing a Figure QC.

    A Phase 8B Figure QC requires exact upstream, execution, render, and
    inspection identities.  If their minimum structure is unavailable, a
    schema-valid QC cannot be emitted honestly; the validator returns an
    explicit blocked envelope and a null QC instead.
    """
    phase8a_hash = None
    if isinstance(fresh_receipt, dict):
        qc_ref = fresh_receipt.get("phase8a_qc_ref")
        if isinstance(qc_ref, dict):
            phase8a_hash = qc_ref.get("phase8a_figure_qc_sha256")
    return {
        "valid": False,
        "validation_state": "blocked",
        "validator_version": VALIDATOR_VERSION,
        "issues": _dedupe_issues(issues),
        "phase8a_figure_qc_sha256": phase8a_hash,
        "phase8b_figure_qc_sha256": None,
        "qc": None,
    }


def _read_object(path: Path, label: str, issues: list[dict[str, str]]) -> dict[str, Any] | None:
    try:
        value = read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        add_issue(
            issues, "input:unreadable_json",
            f"could not read {label}: {type(exc).__name__}: {exc}",
            f"$.inputs.{label}",
        )
        return None
    if not isinstance(value, dict):
        add_issue(
            issues, "input:object_required", f"{label} must be a JSON object",
            f"$.inputs.{label}",
        )
        return None
    return value


def _dict_has_strings(value: Any, keys: tuple[str, ...]) -> bool:
    return isinstance(value, dict) and all(isinstance(value.get(key), str) and value.get(key) for key in keys)


def _receipt_dependencies_available(receipt: dict[str, Any]) -> bool:
    return (
        _dict_has_strings(receipt, ("receipt_id", "schema_version", "receipt_sha256"))
        and _dict_has_strings(
            receipt.get("design_package_ref"),
            ("design_package_id", "design_package_version", "design_package_hash"),
        )
        and _dict_has_strings(
            receipt.get("phase8a_qc_ref"),
            ("artifact_id", "schema_version", "design_package_hash", "phase8a_figure_qc_sha256"),
        )
        and _dict_has_strings(receipt.get("validator"), ("file_sha256",))
    )


def _list_of_objects(value: Any, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(isinstance(item, dict) for item in value)
    )


def _runtime_dependencies_available(
    profile: dict[str, Any], plan: dict[str, Any], execution_manifest: dict[str, Any],
    authorization: dict[str, Any], execution_result: dict[str, Any], render: dict[str, Any],
    inspections: list[dict[str, Any]],
) -> bool:
    """Check only fields that later code dereferences structurally."""
    return all((
        _dict_has_strings(profile, ("profile_id", "schema_version", "profile_sha256", "executable_path")),
        isinstance(profile.get("probe"), dict),
        _dict_has_strings(plan, ("plan_id", "schema_version", "plan_sha256", "figure_id")),
        _list_of_objects(plan.get("input_bindings")),
        _list_of_objects(plan.get("operations")),
        _list_of_objects(plan.get("outputs")),
        _dict_has_strings(execution_manifest, ("execution_id", "schema_version", "execution_manifest_sha256", "execution_package_hash")),
        isinstance(execution_manifest.get("program"), dict),
        _list_of_objects(execution_manifest.get("input_bindings")),
        _list_of_objects(execution_manifest.get("expected_outputs")),
        isinstance(execution_manifest.get("authorization_ref"), dict),
        _dict_has_strings(authorization, ("authorization_id", "schema_version", "authorization_sha256")),
        isinstance(authorization.get("backend_profile_ref"), dict),
        isinstance(authorization.get("admission_receipt_ref"), dict),
        _list_of_objects(authorization.get("input_bindings")),
        _dict_has_strings(execution_result, ("execution_result_id", "schema_version", "execution_result_sha256", "execution_id")),
        _list_of_objects(execution_result.get("outputs")),
        isinstance(execution_result.get("stdout"), dict),
        isinstance(execution_result.get("stderr"), dict),
        _dict_has_strings(render, ("render_manifest_id", "schema_version", "render_manifest_sha256")),
        _list_of_objects(render.get("outputs")),
        bool(inspections),
        all(
            _dict_has_strings(item, ("inspection_id", "schema_version", "inspection_sha256"))
            and isinstance(item.get("render_manifest_ref"), dict)
            and _list_of_objects(item.get("inspected_outputs"))
            and _list_of_objects(item.get("findings"), allow_empty=True)
            and isinstance(item.get("assessed_domains"), list)
            and isinstance(item.get("unassessed_domains"), list)
            for item in inspections
        ),
    ))


def _stable_receipt_subject(receipt: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(value) for key, value in receipt.items() if key not in {"receipt_id", "receipt_sha256", "created_at"}}


def _walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def validate_design_revision_proposal(proposal: dict[str, Any]) -> list[dict[str, str]]:
    issues = validate_schema(proposal, "design-revision-proposal.schema.json", "$.design_revision_proposal")
    if proposal.get("proposal_sha256") != payload_sha256(proposal, "proposal_sha256"):
        add_issue(issues, "proposal:self_hash", "design-revision proposal self-hash mismatch", "$.design_revision_proposal.proposal_sha256")
    kind = proposal.get("proposal_kind")
    for index, change in enumerate(proposal.get("requested_changes", [])):
        field = change.get("field")
        if kind == "presentation_only" and field not in PRESENTATION_FIELDS:
            add_issue(issues, "proposal:field_outside_presentation_scope", f"field is not a bounded presentation field: {field}", f"$.design_revision_proposal.requested_changes[{index}].field")
        if kind == "scientific_change_request" and change.get("after") is not None:
            add_issue(issues, "proposal:scientific_after_value_forbidden", "scientific/source/statistical change requests cannot carry a model-generated replacement value", f"$.design_revision_proposal.requested_changes[{index}].after")
    if kind == "scientific_change_request" and proposal.get("authority_route") != "phase8a_revalidation_required":
        add_issue(issues, "proposal:phase8a_route_required", "scientific change request must route through Phase 8A revalidation", "$.design_revision_proposal.authority_route")
    return issues


def _load_bound_documents(package_root: Path) -> dict[str, Any]:
    manifest = read_json(package_root / "design-package-manifest.json")
    values: dict[str, Any] = {"manifest": manifest}
    components = manifest["components"]
    for key, target in (("source_manifest", components["source_data_manifest"]),):
        values[key] = read_json(package_root / target["path"])
    for key, component_key in (("cards", "figure_cards"), ("contracts", "figure_contracts"), ("recipes", "plot_recipes")):
        values[key] = [read_json(package_root / item["path"]) for item in components[component_key]]
    for key, binding_key in (("source_collection", "trusted_source_inputs"), ("analysis_collection", "trusted_analysis_outputs"), ("authority_collection", "trusted_authority_inputs")):
        values[key] = read_json(package_root / manifest["trust_bindings"][binding_key]["path"])
    return values


def validate_plan_against_phase8a(plan: dict[str, Any], receipt: dict[str, Any], package_root: Path) -> list[dict[str, str]]:
    issues = validate_plan(plan)
    docs = _load_bound_documents(package_root)
    manifest = docs["manifest"]
    expected_design_ref = {"id": manifest["design_package_id"], "version": manifest["design_package_version"], "sha256": manifest["design_package_hash"]}
    expected_receipt_ref = {"id": receipt["receipt_id"], "version": receipt["schema_version"], "sha256": receipt["receipt_sha256"]}
    if plan.get("design_package_ref") != expected_design_ref:
        add_issue(issues, "mapping:design_package", "plan does not bind the admitted design package", "$.bounded_program_plan.design_package_ref")
    if plan.get("admission_receipt_ref") != expected_receipt_ref:
        add_issue(issues, "mapping:admission_receipt", "plan does not bind the saved admission receipt", "$.bounded_program_plan.admission_receipt_ref")
    contract = docs["contracts"][0]
    recipes = {item["panel_id"]: item for item in docs["recipes"]}
    if plan.get("figure_id") != contract.get("figure_id") or plan.get("panel_order") != contract.get("ordered_panel_ids"):
        add_issue(issues, "mapping:figure_panel_order", "plan Figure/panel order differs from the admitted contract", "$.bounded_program_plan.panel_order")
    palette = {item["semantic_key"]: item["value"] for item in contract.get("palette_semantics", [])}
    if plan.get("palette") != palette:
        add_issue(issues, "mapping:palette_drift", "plan palette semantics differ from the admitted contract", "$.bounded_program_plan.palette")
    trusted_inputs = {item["trusted_input_id"]: item for item in docs["source_collection"]["records"]}
    source_records = {item["source_data_id"]: item for item in docs["source_manifest"]["source_records"]}
    for index, binding in enumerate(plan.get("input_bindings", [])):
        trusted = trusted_inputs.get(binding.get("trusted_input_id"))
        source = source_records.get(binding.get("source_data_id"))
        if trusted is None or source is None:
            add_issue(issues, "mapping:source_binding", "plan input does not resolve to admitted source/trusted input", f"$.bounded_program_plan.input_bindings[{index}]")
            continue
        actual_path = (package_root / trusted["path"]).resolve()
        expected = {
            "trusted_input_id": trusted["trusted_input_id"], "source_data_id": trusted["source_data_id"],
            "path": str(actual_path), "format": trusted["format"], "sha256": trusted["expected_sha256"],
            "variables": [item["variable_id"] for item in source["variables"]], "units": source["units"],
        }
        if binding != expected:
            add_issue(issues, "mapping:source_binding", "plan input fields differ from admitted source/trust binding", f"$.bounded_program_plan.input_bindings[{index}]")
    analyses = {item["analysis_output_id"]: item for item in docs["analysis_collection"]["records"]}
    for index, operation in enumerate(plan.get("operations", [])):
        recipe = recipes.get(operation.get("panel_id"))
        path = f"$.bounded_program_plan.operations[{index}]"
        if recipe is None:
            add_issue(issues, "mapping:panel_recipe", "operation panel has no admitted Plot Recipe", path)
            continue
        layers = {item["layer_id"] for item in recipe["layers"]}
        mappings = {item["aesthetic"]: item["variable_id"] for item in recipe["variable_mappings"]}
        if operation.get("recipe_id") != recipe.get("recipe_id") or operation.get("layer_id") not in layers:
            add_issue(issues, "mapping:recipe_layer", "operation lacks exact Plot Recipe/layer binding", path)
        if operation.get("source_data_ids") != recipe.get("source_data_ids") or operation.get("variable_bindings") != mappings:
            add_issue(issues, "mapping:source_variable", "operation source-variable mapping drifts from Plot Recipe", path)
        if recipe.get("ordering") != plan.get("group_order"):
            add_issue(issues, "mapping:group_order_drift", "plan group order differs from Plot Recipe", path)
        if recipe.get("filters") or recipe.get("exclusions") or recipe.get("transformation_ids") or recipe.get("aggregation") not in {"none", "raw observations only"}:
            add_issue(issues, "mapping:undeclared_data_operation", "minimum backend accepts only raw observations without filter/transform/aggregation", path)
        if operation.get("operation") == "draw_supplied_annotation":
            supplied = [item for item in recipe["statistical_annotations"] if item.get("status") == "supplied"]
            expected_ids = [item["analysis_output_ref"]["analysis_output_id"] for item in supplied]
            expected_symbols = [item["symbol"] for item in supplied]
            if operation.get("analysis_output_ids") != expected_ids or operation.get("parameters", {}).get("symbol") not in expected_symbols or any(item not in analyses for item in expected_ids):
                add_issue(issues, "mapping:statistical_annotation_drift", "annotation does not exactly bind supplied analysis/symbol", path)
    return issues


def validate_execution_result(result: dict[str, Any], manifest: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = validate_schema(result, "prototype-execution-result.schema.json", "$.execution_result")
    if result.get("execution_result_sha256") != payload_sha256(result, "execution_result_sha256"):
        add_issue(issues, "execution:result_hash", "execution result self-hash mismatch", "$.execution_result.execution_result_sha256")
    expected_fields = {
        "execution_id": manifest.get("execution_id"), "execution_manifest_sha256": manifest.get("execution_manifest_sha256"),
        "execution_package_hash": manifest.get("execution_package_hash"), "program_sha256": manifest.get("program", {}).get("sha256"),
        "backend_profile_sha256": profile.get("profile_sha256"), "command": manifest.get("command"),
    }
    for key, expected in expected_fields.items():
        if result.get(key) != expected:
            add_issue(issues, "execution:result_binding", f"execution result {key} mismatch", f"$.execution_result.{key}")
    if result.get("status") != "succeeded" or result.get("exit_code") != 0 or result.get("issues"):
        add_issue(issues, "execution:not_successful", "execution result does not represent a clean successful run", "$.execution_result.status")
    expected_outputs = {item["role"]: item for item in manifest.get("expected_outputs", [])}
    output_directory = Path(manifest.get("output_directory", ""))
    if output_directory.is_dir():
        expected_names = {item.get("path") for item in manifest.get("expected_outputs", [])}
        actual_names = {item.name for item in output_directory.iterdir() if item.is_file()}
        if actual_names != expected_names:
            add_issue(issues, "execution:undeclared_or_missing_output", f"declared={sorted(expected_names)} actual={sorted(actual_names)}", "$.execution_result.outputs")
    if {item.get("role") for item in result.get("outputs", [])} != set(expected_outputs):
        add_issue(issues, "execution:output_set_mismatch", "execution result output roles differ from manifest", "$.execution_result.outputs")
    for output in result.get("outputs", []):
        path = Path(output.get("path", ""))
        expected = expected_outputs.get(output.get("role"), {})
        if not path.is_file() or path.stat().st_size != output.get("size") or file_sha256(path) != output.get("sha256"):
            add_issue(issues, "execution:output_identity", f"current output identity mismatch: {path}", "$.execution_result.outputs")
        if output.get("format") != expected.get("format") or output.get("panel_ids") != expected.get("panel_ids"):
            add_issue(issues, "execution:output_binding", f"output metadata differs from manifest: {path}", "$.execution_result.outputs")
    for stream in ("stdout", "stderr"):
        value = result.get(stream, {})
        path = Path(value.get("path", ""))
        if not path.is_file() or file_sha256(path) != value.get("sha256"):
            add_issue(issues, "execution:log_identity", f"{stream} log identity mismatch", f"$.execution_result.{stream}")
    return issues


def validate_render(render: dict[str, Any], result: dict[str, Any], receipt: dict[str, Any]) -> list[dict[str, str]]:
    issues = validate_schema(render, "render-output-manifest.schema.json", "$.render_output_manifest")
    if render.get("render_manifest_sha256") != payload_sha256(render, "render_manifest_sha256"):
        add_issue(issues, "render:self_hash", "render manifest self-hash mismatch", "$.render_output_manifest.render_manifest_sha256")
    expected_exec_ref = {"id": result.get("execution_result_id"), "version": result.get("schema_version"), "sha256": result.get("execution_result_sha256")}
    if render.get("execution_ref") != expected_exec_ref or render.get("program_sha256") != result.get("program_sha256"):
        add_issue(issues, "render:execution_binding", "render manifest binds another execution/program", "$.render_output_manifest.execution_ref")
    expected_receipt_ref = {"id": receipt.get("receipt_id"), "version": receipt.get("schema_version"), "sha256": receipt.get("receipt_sha256")}
    if render.get("admission_receipt_ref") != expected_receipt_ref:
        add_issue(issues, "render:admission_binding", "render manifest binds another admission receipt", "$.render_output_manifest.admission_receipt_ref")
    result_outputs = {item.get("role"): item for item in result.get("outputs", [])}
    for output in render.get("outputs", []):
        current = result_outputs.get(output.get("role"), {})
        for key in ("path", "format", "size", "sha256", "panel_ids"):
            if output.get(key) != current.get(key):
                add_issue(issues, "render:output_binding", f"render output {key} differs from execution result", "$.render_output_manifest.outputs")
    return issues


def validate_fresh_render_metadata(
    render: dict[str, Any], execution_manifest: dict[str, Any], result: dict[str, Any], receipt: dict[str, Any]
) -> list[dict[str, str]]:
    fresh, fresh_issues = inspect_render(
        execution_manifest, result, receipt, created_at=render.get("created_at")
    )
    issues = list(fresh_issues)
    if fresh is not None and fresh != render:
        add_issue(
            issues, "render:fresh_metadata_mismatch",
            "saved render manifest differs from fresh deterministic output inspection",
            "$.render_output_manifest",
        )
    return issues


def validate_inspections(records: list[dict[str, Any]], render: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    output_by_role = {item["role"]: item for item in render.get("outputs", [])}
    expected_render_ref = {"id": render.get("render_manifest_id"), "version": render.get("schema_version"), "sha256": render.get("render_manifest_sha256")}
    for index, record in enumerate(records):
        path = f"$.render_inspection_records[{index}]"
        issues.extend(validate_schema(record, "render-inspection-record.schema.json", path))
        if "performed" in record:
            add_issue(issues, "inspection:self_declared_not_proof", "a self-declared performed field is not deterministic proof of inspection", f"{path}.performed")
        if record.get("inspection_sha256") != payload_sha256(record, "inspection_sha256"):
            add_issue(issues, "inspection:self_hash", "inspection record self-hash mismatch", f"{path}.inspection_sha256")
        if record.get("render_manifest_ref") != expected_render_ref:
            add_issue(issues, "inspection:render_binding", "inspection record binds another render", f"{path}.render_manifest_ref")
        if set(record.get("assessed_domains", [])) & set(record.get("unassessed_domains", [])):
            add_issue(issues, "inspection:domain_overlap", "inspection domains cannot be both assessed and unassessed", path)
        for output in record.get("inspected_outputs", []):
            expected = output_by_role.get(output.get("role"), {})
            if output.get("path") != expected.get("path") or output.get("sha256") != expected.get("sha256"):
                add_issue(issues, "inspection:output_binding", "inspection output hash/path differs from render manifest", f"{path}.inspected_outputs")
        if record.get("inspector_class") in {"model", "deterministic_tool"}:
            overclaim = FORBIDDEN_MODEL_AUTHORITY_DOMAINS & set(record.get("assessed_domains", []))
            if overclaim or record.get("no_authority") is not True:
                add_issue(issues, "inspection:authority_overclaim", f"model/tool inspection claims unavailable authority domains: {sorted(overclaim)}", path)
    return issues


def _contains_inactive_finality_decision(values: Iterable[Any]) -> bool:
    return any(isinstance(item, dict) and item.get("decision_type") == "finality_decision" for value in values for item in _walk(value))


def validate_authority_and_claim_boundaries(values: Iterable[Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for value in values:
        for item in _walk(value):
            if not isinstance(item, dict):
                continue
            decision_type = item.get("decision_type")
            if decision_type == "finality_decision":
                add_issue(issues, "authority:inactive_decision_type", "finality_decision is inactive in Phase 8B", "$.phase8b_package")
            if decision_type in {"layout_decision", "design_acceptance", "figure_conclusion_freeze"}:
                if item.get("decision_producer_role") != "author":
                    add_issue(issues, "authority:wrong_role", "author-only Figure decision was not issued by an author", "$.phase8b_package")
                if item.get("decision_value") == "reject":
                    add_issue(issues, "authority:reject_cannot_advance", "a reject decision cannot advance Phase 8B state", "$.phase8b_package")
                if item.get("authorization_state") != "caller_accepted":
                    add_issue(issues, "authority:state_not_accepted", "authority decision is not caller accepted", "$.phase8b_package")
            if item.get("maturity") in {"submission_candidate", "author_approved_final"} or item.get("finality_state") in {"submission_candidate", "author_approved_final"}:
                add_issue(issues, "maturity:self_promotion", "Phase 8B cannot self-promote a prototype to submission/final", "$.phase8b_package")
            if item.get("module06_figure_qc_status") in {"passed", "executed", "complete"}:
                add_issue(issues, "qc:module06_figure_extension_absent", "Figure-capable Module 06 is not implemented", "$.phase8b_package")
    return issues


def make_phase8b_qc(
    receipt: dict[str, Any], execution_result: dict[str, Any], render: dict[str, Any],
    inspections: list[dict[str, Any]], structural_issues: list[dict[str, str]], *, generated_at: str | None = None,
) -> dict[str, Any]:
    inspection_blockers = [finding for record in inspections for finding in record.get("findings", []) if finding.get("severity") == "blocker"]
    if structural_issues or inspection_blockers:
        maturity, gate = "blocked", "blocked"
    else:
        maturity, gate = "prototype_generated_unverified", "author_review_required"
    findings = [
        {"code": item.get("code", "deterministic:unknown"), "severity": "blocker", "message": item.get("message", "unspecified")}
        for item in structural_issues
    ]
    findings.extend({"code": f"inspection:{item['finding_id']}", "severity": item["severity"], "message": item["message"]} for item in inspection_blockers)
    qc: dict[str, Any] = {
        "schema_name": "figure_qc", "schema_version": "0.2.0", "contract_version": CONTRACT_VERSION,
        "artifact_id": f"phase8b-qc-{execution_result.get('execution_id', 'unknown')}", "figure_qc_sha256": "0" * 64, "phase": "phase8b",
        "upstream_phase8a_qc_ref": receipt["phase8a_qc_ref"],
        "design_package_ref": {"id": receipt["design_package_ref"]["design_package_id"], "version": receipt["design_package_ref"]["design_package_version"], "sha256": receipt["design_package_ref"]["design_package_hash"]},
        "admission_receipt_ref": {"id": receipt["receipt_id"], "version": receipt["schema_version"], "sha256": receipt["receipt_sha256"]},
        "execution_ref": {"id": execution_result.get("execution_result_id", "missing"), "version": execution_result.get("schema_version", "0.1.0"), "sha256": execution_result.get("execution_result_sha256", "0" * 64)},
        "render_manifest_ref": {"id": render.get("render_manifest_id", "missing"), "version": render.get("schema_version", "0.1.0"), "sha256": render.get("render_manifest_sha256", "0" * 64)},
        "inspection_refs": [{"id": item["inspection_id"], "version": item["schema_version"], "sha256": item["inspection_sha256"]} for item in inspections],
        "phase8a_figure_qc_sha256": receipt["phase8a_qc_ref"]["phase8a_figure_qc_sha256"],
        "maturity": maturity, "readiness_gate": gate, "module06_figure_qc_status": "not_implemented",
        "inspection_provenance_limitation": "schema/hash closure does not prove that a model actually viewed or cognitively inspected the render; no trusted inspection-execution receipt exists in 0.1.1",
        "findings": findings, "generated_at": generated_at or utc_now(),
    }
    qc["figure_qc_sha256"] = payload_sha256(qc, "figure_qc_sha256")
    return qc


def validate_phase8b_package(
    phase8a_package_root: Path, trust_root_path: Path, expected_trust_root_sha256: str,
    expected_design_package_hash: str, expected_phase8a_figure_qc_sha256: str,
    expected_phase8a_qc_artifact_id: str, expected_phase8a_qc_schema_version: str,
    admission_receipt_path: Path, profile_path: Path, plan_path: Path,
    execution_manifest_path: Path, authorization_path: Path, expected_authorization_file_sha256: str,
    execution_result_path: Path, render_manifest_path: Path, inspection_paths: list[Path],
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []

    # Gate 1: upstream admission is the first dependency.  No Phase 8B record
    # is parsed or dereferenced until the exact Phase 8A package is freshly
    # admitted by the frozen validator.
    fresh_receipt, admission_issues = admit_phase8a(
        phase8a_package_root, trust_root_path, expected_trust_root_sha256,
        expected_design_package_hash, expected_phase8a_qc_artifact_id,
        expected_phase8a_qc_schema_version, expected_phase8a_figure_qc_sha256,
        mode="prototype_execution_and_inspection",
    )
    issues.extend(admission_issues)
    if fresh_receipt is None or admission_issues:
        add_issue(
            issues, "validation:dependency_chain_blocked",
            "fresh Phase 8A admission did not establish an upstream structure safe for Phase 8B dereferencing",
            "$.phase8a_admission",
        )
        return _blocked_result(issues, fresh_receipt)

    # Gate 2: the saved receipt must expose the exact identities required by
    # plan, execution, render, and QC validation.  Schema findings are retained,
    # but missing/wrong-type dependency fields stop the chain immediately.
    receipt = _read_object(admission_receipt_path, "phase8a_admission_receipt", issues)
    if receipt is None:
        add_issue(issues, "validation:dependency_chain_blocked", "saved admission receipt is not safely parseable", "$.phase8a_admission_receipt")
        return _blocked_result(issues, fresh_receipt)
    receipt_schema_issues = validate_schema(
        receipt, "phase8a-admission-receipt.schema.json", "$.phase8a_admission_receipt"
    )
    issues.extend(receipt_schema_issues)
    if not _receipt_dependencies_available(receipt):
        add_issue(
            issues, "validation:dependency_chain_blocked",
            "saved admission receipt lacks the minimum typed identity fields required downstream",
            "$.phase8a_admission_receipt",
        )
        return _blocked_result(issues, fresh_receipt)
    if receipt.get("receipt_sha256") != payload_sha256(receipt, "receipt_sha256"):
        add_issue(issues, "admission:receipt_hash", "saved admission receipt self-hash mismatch", "$.phase8a_admission_receipt.receipt_sha256")
    if receipt["validator"]["file_sha256"] != file_sha256(PHASE8A_VALIDATOR):
        add_issue(issues, "admission:validator_file_hash", "saved receipt does not bind the current frozen Phase 8A validator file", "$.phase8a_admission_receipt.validator.file_sha256")
    if _stable_receipt_subject(receipt) != _stable_receipt_subject(fresh_receipt):
        add_issue(issues, "admission:stale_or_self_declared_receipt", "saved receipt bindings differ from a fresh Phase 8A invocation", "$.phase8a_admission_receipt")

    # Gate 3: read all remaining support records through one object-only path,
    # record their schema findings, and stop before semantic dereferencing when
    # a minimum list/object dependency is unavailable.
    profile = _read_object(profile_path, "backend_environment_profile", issues)
    plan = _read_object(plan_path, "bounded_program_plan", issues)
    execution_manifest = _read_object(execution_manifest_path, "execution_manifest", issues)
    authorization = _read_object(authorization_path, "execution_authorization", issues)
    execution_result = _read_object(execution_result_path, "execution_result", issues)
    render = _read_object(render_manifest_path, "render_output_manifest", issues)
    inspections: list[dict[str, Any]] = []
    for index, path in enumerate(inspection_paths):
        value = _read_object(path, f"render_inspection_record_{index}", issues)
        if value is not None:
            inspections.append(value)
    if any(value is None for value in (profile, plan, execution_manifest, authorization, execution_result, render)) or len(inspections) != len(inspection_paths):
        add_issue(issues, "validation:dependency_chain_blocked", "one or more Phase 8B support records are not safely parseable objects", "$.phase8b_package")
        return _blocked_result(issues, fresh_receipt)

    assert profile is not None and plan is not None and execution_manifest is not None
    assert authorization is not None and execution_result is not None and render is not None
    schema_inputs = (
        (profile, "backend-environment-profile.schema.json", "$.backend_environment_profile"),
        (plan, "bounded-program-plan.schema.json", "$.bounded_program_plan"),
        (execution_manifest, "prototype-execution-manifest.schema.json", "$.execution_manifest"),
        (authorization, "prototype-execution-authorization.schema.json", "$.execution_authorization"),
        (execution_result, "prototype-execution-result.schema.json", "$.execution_result"),
        (render, "render-output-manifest.schema.json", "$.render_output_manifest"),
    )
    for value, schema_name, instance_path in schema_inputs:
        issues.extend(validate_schema(value, schema_name, instance_path))
    for index, inspection in enumerate(inspections):
        issues.extend(validate_schema(inspection, "render-inspection-record.schema.json", f"$.render_inspection_records[{index}]"))
    if not _runtime_dependencies_available(
        profile, plan, execution_manifest, authorization, execution_result, render, inspections
    ):
        add_issue(
            issues, "validation:dependency_chain_blocked",
            "Phase 8B support records lack minimum typed fields required for safe semantic validation or QC generation",
            "$.phase8b_package",
        )
        return _blocked_result(issues, fresh_receipt)

    # The upstream loader is intentionally called only after fresh admission.
    # Any unexpected dependency-resolution exception is converted to a stable
    # blocked result rather than a traceback.
    try:
        issues.extend(verify_profile(profile))
        issues.extend(validate_plan_against_phase8a(plan, receipt, phase8a_package_root))
        program_path = Path(execution_manifest["program"].get("path", ""))
        if program_path.is_file():
            issues.extend(validate_program(plan, program_path, execution_manifest["program"].get("sha256")))
        if execution_manifest["program"].get("generator_sha256") != file_sha256(GENERATOR_PATH):
            add_issue(issues, "code:generator_hash", "execution manifest generator hash mismatch", "$.execution_manifest.program.generator_sha256")
        issues.extend(validate_execution_inputs(
            execution_manifest, execution_manifest_path, receipt, profile, plan,
            authorization, authorization_path, expected_authorization_file_sha256,
        ))
        issues.extend(validate_execution_result(execution_result, execution_manifest, profile))
        issues.extend(validate_render(render, execution_result, receipt))
        issues.extend(validate_fresh_render_metadata(render, execution_manifest, execution_result, receipt))
        issues.extend(validate_inspections(inspections, render))
        issues.extend(validate_authority_and_claim_boundaries([plan, execution_manifest, authorization, render, inspections]))
    except Exception as exc:
        add_issue(
            issues, "validation:dependency_resolution_failed",
            f"dependent semantic validation failed closed: {type(exc).__name__}: {exc}",
            "$.phase8b_package",
        )
        add_issue(issues, "validation:dependency_chain_blocked", "dependent semantic validation could not continue safely", "$.phase8b_package")
        return _blocked_result(issues, fresh_receipt)

    deduped = _dedupe_issues(issues)
    qc = make_phase8b_qc(receipt, execution_result, render, inspections, deduped)
    qc_schema_issues = validate_schema(qc, "figure-qc-phase8b.schema.json", "$.phase8b_figure_qc")
    if qc_schema_issues:
        deduped = _dedupe_issues([*deduped, *qc_schema_issues])
        qc = make_phase8b_qc(receipt, execution_result, render, inspections, deduped)
    if qc.get("figure_qc_sha256") != payload_sha256(qc, "figure_qc_sha256"):
        raise RuntimeError("internal Phase 8B Figure-QC hash failure")
    return {
        "valid": not deduped,
        "validation_state": "validated" if not deduped else "blocked",
        "validator_version": VALIDATOR_VERSION,
        "issues": deduped,
        "phase8a_figure_qc_sha256": receipt["phase8a_qc_ref"]["phase8a_figure_qc_sha256"],
        "phase8b_figure_qc_sha256": qc["figure_qc_sha256"],
        "qc": qc,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase8a_package_root", type=Path)
    parser.add_argument("--trust-root", type=Path, required=True)
    parser.add_argument("--trust-root-sha256", required=True)
    parser.add_argument("--design-package-hash", required=True)
    parser.add_argument("--phase8a-qc-sha256", required=True)
    parser.add_argument("--phase8a-qc-artifact-id", required=True)
    parser.add_argument("--phase8a-qc-schema-version", required=True)
    parser.add_argument("--admission-receipt", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--execution-manifest", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--authorization-file-sha256", required=True)
    parser.add_argument("--execution-result", type=Path, required=True)
    parser.add_argument("--render-manifest", type=Path, required=True)
    parser.add_argument("--inspection", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_phase8b_package(
        args.phase8a_package_root, args.trust_root, args.trust_root_sha256,
        args.design_package_hash, args.phase8a_qc_sha256, args.phase8a_qc_artifact_id,
        args.phase8a_qc_schema_version, args.admission_receipt,
        args.profile, args.plan, args.execution_manifest, args.authorization,
        args.authorization_file_sha256, args.execution_result, args.render_manifest,
        args.inspection,
    )
    if args.output:
        from phase8b_runtime import write_json
        write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
