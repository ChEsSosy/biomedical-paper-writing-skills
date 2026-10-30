#!/usr/bin/env python3
"""Authorize and run one exact restricted-Python synthetic prototype."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from phase8b_runtime import (
    PHASE8A_VALIDATOR,
    Phase8BError,
    execution_package_hash,
    file_sha256,
    payload_sha256,
    read_json,
    resolved_within,
    utc_now,
    validate_schema,
    write_json,
)
from generate_restricted_python import SCRIPT_PATH as GENERATOR_PATH
from probe_backend_environment import verify_profile
from validate_generated_program import validate_program
from validate_phase8b_admission import admit_phase8a


def hash_ref_matches(reference: dict[str, Any], identity: str, version: str, sha256: str) -> bool:
    return reference == {"id": identity, "version": version, "sha256": sha256}


def validate_execution_inputs(
    manifest: dict[str, Any], manifest_path: Path,
    receipt: dict[str, Any], profile: dict[str, Any], plan: dict[str, Any],
    authorization: dict[str, Any], authorization_path: Path,
    expected_authorization_file_sha256: str,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    execution_root = manifest_path.resolve().parent
    issues.extend(validate_schema(manifest, "prototype-execution-manifest.schema.json", "$.execution_manifest"))
    issues.extend(validate_schema(authorization, "prototype-execution-authorization.schema.json", "$.execution_authorization"))
    if manifest.get("execution_manifest_sha256") != payload_sha256(manifest, "execution_manifest_sha256"):
        issues.append({"layer": "deterministic", "path": "$.execution_manifest.execution_manifest_sha256", "code": "execution:manifest_hash", "message": "execution manifest self-hash mismatch", "review_route": "deterministic", "severity": "error"})
    issues.extend(validate_schema(receipt, "phase8a-admission-receipt.schema.json", "$.phase8a_admission_receipt"))
    if receipt.get("receipt_sha256") != payload_sha256(receipt, "receipt_sha256"):
        issues.append({"layer": "deterministic", "path": "$.phase8a_admission_receipt.receipt_sha256", "code": "admission:receipt_hash", "message": "admission receipt self-hash mismatch", "review_route": "deterministic", "severity": "error"})
    if receipt.get("validator", {}).get("file_sha256") != file_sha256(PHASE8A_VALIDATOR):
        issues.append({"layer": "deterministic", "path": "$.phase8a_admission_receipt.validator.file_sha256", "code": "admission:validator_file_hash", "message": "receipt validator file hash differs from the frozen validator", "review_route": "deterministic", "severity": "error"})
    expected_package_hash = execution_package_hash(manifest)
    if manifest.get("execution_package_hash") != expected_package_hash:
        issues.append({"layer": "deterministic", "path": "$.execution_manifest.execution_package_hash", "code": "execution:package_hash", "message": "pre-authorization execution package hash mismatch", "review_route": "deterministic", "severity": "error"})
    if authorization.get("authorization_sha256") != payload_sha256(authorization, "authorization_sha256"):
        issues.append({"layer": "deterministic", "path": "$.execution_authorization.authorization_sha256", "code": "authorization:self_hash", "message": "execution authorization self-hash mismatch", "review_route": "deterministic", "severity": "error"})
    if resolved_within(authorization_path, execution_root):
        issues.append({"layer": "deterministic", "path": "$.execution_authorization", "code": "authorization:not_external", "message": "execution authorization must be outside the execution package", "review_route": "deterministic", "severity": "error"})
    if file_sha256(authorization_path) != expected_authorization_file_sha256:
        issues.append({"layer": "deterministic", "path": "$.execution_authorization", "code": "authorization:caller_held_hash", "message": "caller-held authorization file hash mismatch", "review_route": "deterministic", "severity": "error"})
    auth_ref = manifest.get("authorization_ref", {})
    if not hash_ref_matches(auth_ref, authorization.get("authorization_id"), authorization.get("schema_version"), authorization.get("authorization_sha256")):
        issues.append({"layer": "deterministic", "path": "$.execution_manifest.authorization_ref", "code": "authorization:reference_mismatch", "message": "execution manifest does not bind the external authorization", "review_route": "deterministic", "severity": "error"})
    if authorization.get("execution_package_hash") != expected_package_hash:
        issues.append({"layer": "deterministic", "path": "$.execution_authorization.execution_package_hash", "code": "authorization:execution_package_mismatch", "message": "authorization binds another execution package", "review_route": "deterministic", "severity": "error"})
    for value, record, name, id_key, hash_key in (
        (manifest.get("admission_receipt_ref", {}), receipt, "admission", "receipt_id", "receipt_sha256"),
        (manifest.get("backend_profile_ref", {}), profile, "backend", "profile_id", "profile_sha256"),
        (manifest.get("plan_ref", {}), plan, "plan", "plan_id", "plan_sha256"),
    ):
        if not hash_ref_matches(value, record.get(id_key), record.get("schema_version"), record.get(hash_key)):
            issues.append({"layer": "deterministic", "path": f"$.execution_manifest.{name}_ref", "code": f"execution:{name}_binding", "message": f"execution manifest {name} reference mismatch", "review_route": "deterministic", "severity": "error"})
    expected_auth_refs = {
        "backend_profile_ref": {"id": profile.get("profile_id"), "version": profile.get("schema_version"), "sha256": profile.get("profile_sha256")},
        "admission_receipt_ref": {"id": receipt.get("receipt_id"), "version": receipt.get("schema_version"), "sha256": receipt.get("receipt_sha256")},
    }
    for key, expected in expected_auth_refs.items():
        if authorization.get(key) != expected:
            issues.append({"layer": "deterministic", "path": f"$.execution_authorization.{key}", "code": "authorization:bound_record_mismatch", "message": f"authorization {key} mismatch", "review_route": "deterministic", "severity": "error"})
    program_path = Path(manifest.get("program", {}).get("path", ""))
    if not resolved_within(program_path, execution_root):
        issues.append({"layer": "deterministic", "path": "$.execution_manifest.program.path", "code": "execution:program_path_escape", "message": "program must reside inside execution package", "review_route": "deterministic", "severity": "error"})
    elif program_path.is_file():
        issues.extend(validate_program(plan, program_path, manifest.get("program", {}).get("sha256")))
    else:
        issues.append({"layer": "deterministic", "path": "$.execution_manifest.program.path", "code": "execution:program_missing", "message": "declared program is absent", "review_route": "deterministic", "severity": "error"})
    if authorization.get("program_sha256") != manifest.get("program", {}).get("sha256"):
        issues.append({"layer": "deterministic", "path": "$.execution_authorization.program_sha256", "code": "authorization:program_mismatch", "message": "authorization binds another program", "review_route": "deterministic", "severity": "error"})
    if manifest.get("program", {}).get("generator_sha256") != file_sha256(GENERATOR_PATH):
        issues.append({"layer": "deterministic", "path": "$.execution_manifest.program.generator_sha256", "code": "code:generator_hash", "message": "execution manifest does not bind the current reviewed generator", "review_route": "deterministic", "severity": "error"})
    if manifest.get("command") != authorization.get("command"):
        issues.append({"layer": "deterministic", "path": "$.execution_manifest.command", "code": "authorization:command_mismatch", "message": "manifest command differs from authorization", "review_route": "deterministic", "severity": "error"})
    expected_command = [profile.get("executable_path"), "-B", str(program_path.resolve())]
    if manifest.get("command") != expected_command:
        issues.append({"layer": "deterministic", "path": "$.execution_manifest.command", "code": "execution:command_mismatch", "message": "command is not the exact profiled interpreter and generated program", "review_route": "deterministic", "severity": "error"})
    if manifest.get("parameters") != authorization.get("parameters"):
        issues.append({"layer": "deterministic", "path": "$.execution_manifest.parameters", "code": "authorization:parameters_mismatch", "message": "manifest parameters differ from authorization", "review_route": "deterministic", "severity": "error"})
    if manifest.get("input_bindings") != authorization.get("input_bindings"):
        issues.append({"layer": "deterministic", "path": "$.execution_manifest.input_bindings", "code": "authorization:inputs_mismatch", "message": "manifest inputs differ from authorization", "review_route": "deterministic", "severity": "error"})
    writes = sorted([manifest.get("output_directory"), manifest.get("record_directory")])
    if sorted(authorization.get("authorized_write_roots", [])) != writes:
        issues.append({"layer": "deterministic", "path": "$.execution_authorization.authorized_write_roots", "code": "authorization:output_scope_mismatch", "message": "authorization write scope differs from manifest", "review_route": "deterministic", "severity": "error"})
    for path_text in writes:
        candidate = Path(path_text or "")
        if not resolved_within(candidate, execution_root):
            issues.append({"layer": "deterministic", "path": "$.execution_manifest.output_scope", "code": "execution:write_scope_escape", "message": "write scope escapes execution package", "review_route": "deterministic", "severity": "error"})
    issues.extend(verify_profile(profile))
    return issues


def run_prototype(
    manifest_path: Path, receipt_path: Path, profile_path: Path, plan_path: Path,
    authorization_path: Path, expected_authorization_file_sha256: str,
    phase8a_package_root: Path, trust_root_path: Path,
    expected_trust_root_sha256: str, expected_design_package_hash: str,
    expected_phase8a_qc_artifact_id: str, expected_phase8a_qc_schema_version: str,
    expected_phase8a_figure_qc_sha256: str,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    manifest = read_json(manifest_path)
    receipt, profile, plan = read_json(receipt_path), read_json(profile_path), read_json(plan_path)
    authorization = read_json(authorization_path)
    fresh_receipt, admission_issues = admit_phase8a(
        phase8a_package_root, trust_root_path, expected_trust_root_sha256,
        expected_design_package_hash, expected_phase8a_qc_artifact_id,
        expected_phase8a_qc_schema_version, expected_phase8a_figure_qc_sha256,
        mode="prototype_execution_and_inspection",
    )
    issues = list(admission_issues)
    if fresh_receipt is not None:
        stable_saved = {key: value for key, value in receipt.items() if key not in {"receipt_id", "receipt_sha256", "created_at"}}
        stable_fresh = {key: value for key, value in fresh_receipt.items() if key not in {"receipt_id", "receipt_sha256", "created_at"}}
        if stable_saved != stable_fresh:
            issues.append({"layer": "deterministic", "path": "$.phase8a_admission_receipt", "code": "admission:stale_or_self_declared_receipt", "message": "saved receipt differs from the fresh pre-execution Phase 8A invocation", "review_route": "deterministic", "severity": "error"})
    issues.extend(validate_execution_inputs(
        manifest, manifest_path, receipt, profile, plan, authorization,
        authorization_path, expected_authorization_file_sha256,
    ))
    if issues:
        return None, issues
    before: list[dict[str, str]] = []
    for binding in manifest["input_bindings"]:
        path = Path(binding["path"])
        if not path.is_file() or file_sha256(path) != binding["sha256"]:
            issues.append({"layer": "deterministic", "path": "$.execution_manifest.input_bindings", "code": "execution:input_hash", "message": f"input hash mismatch: {binding['input_id']}", "review_route": "deterministic", "severity": "error"})
        else:
            before.append({"input_id": binding["input_id"], "sha256": binding["sha256"]})
    output_directory = Path(manifest["output_directory"])
    record_directory = Path(manifest["record_directory"])
    for path in (output_directory, record_directory):
        if path.exists():
            issues.append({"layer": "deterministic", "path": "$.execution_manifest.output_scope", "code": "execution:output_not_new", "message": f"authorized write directory already exists: {path}", "review_route": "deterministic", "severity": "error"})
    if issues:
        return None, issues
    output_directory.mkdir(parents=True)
    record_directory.mkdir(parents=True)
    started = utc_now()
    completed = subprocess.run(manifest["command"], check=False, capture_output=True, text=True)
    finished = utc_now()
    stdout_path, stderr_path = record_directory / "stdout.log", record_directory / "stderr.log"
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    actual_outputs: list[dict[str, Any]] = []
    declared_names = {item["path"] for item in manifest["expected_outputs"]}
    actual_names = {item.name for item in output_directory.iterdir() if item.is_file()}
    if completed.returncode != 0:
        issues.append({"layer": "deterministic", "path": "$.execution_result.exit_code", "code": "execution:nonzero_exit", "message": f"restricted program exited {completed.returncode}", "review_route": "deterministic", "severity": "error"})
    if actual_names != declared_names:
        issues.append({"layer": "deterministic", "path": "$.execution_result.outputs", "code": "execution:output_set_mismatch", "message": f"declared={sorted(declared_names)} actual={sorted(actual_names)}", "review_route": "deterministic", "severity": "error"})
    for expected in manifest["expected_outputs"]:
        path = output_directory / expected["path"]
        if not path.is_file() or path.stat().st_size == 0:
            issues.append({"layer": "deterministic", "path": "$.execution_result.outputs", "code": "execution:missing_or_empty_output", "message": f"missing or empty output: {expected['path']}", "review_route": "deterministic", "severity": "error"})
        else:
            actual_outputs.append({"role": expected["role"], "path": str(path.resolve()), "format": expected["format"], "size": path.stat().st_size, "sha256": file_sha256(path), "panel_ids": expected["panel_ids"]})
    after = [{"input_id": binding["input_id"], "sha256": file_sha256(Path(binding["path"]))} for binding in manifest["input_bindings"]]
    if after != before:
        issues.append({"layer": "deterministic", "path": "$.execution_result.inputs_after", "code": "execution:input_mutated", "message": "an admitted input changed during execution", "review_route": "deterministic", "severity": "error"})
    result: dict[str, Any] = {
        "schema_name": "prototype_execution_result", "schema_version": "0.1.0",
        "execution_result_id": f"result-{manifest['execution_id']}", "execution_result_sha256": "0" * 64,
        "execution_id": manifest["execution_id"], "execution_manifest_sha256": manifest["execution_manifest_sha256"],
        "execution_package_hash": manifest["execution_package_hash"], "authorization_ref": manifest["authorization_ref"],
        "program_sha256": manifest["program"]["sha256"], "backend_profile_sha256": profile["profile_sha256"],
        "command": manifest["command"], "status": "succeeded" if not issues else "failed", "exit_code": completed.returncode,
        "started_at": started, "finished_at": finished, "inputs_before": before, "inputs_after": after,
        "outputs": actual_outputs,
        "stdout": {"path": str(stdout_path.resolve()), "sha256": file_sha256(stdout_path)},
        "stderr": {"path": str(stderr_path.resolve()), "sha256": file_sha256(stderr_path)},
        "issues": issues,
    }
    result["execution_result_sha256"] = payload_sha256(result, "execution_result_sha256")
    write_json(record_directory / "execution-result.json", result)
    return result, issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--authorization-file-sha256", required=True)
    parser.add_argument("--phase8a-package-root", type=Path, required=True)
    parser.add_argument("--trust-root", type=Path, required=True)
    parser.add_argument("--trust-root-sha256", required=True)
    parser.add_argument("--design-package-hash", required=True)
    parser.add_argument("--phase8a-qc-artifact-id", required=True)
    parser.add_argument("--phase8a-qc-schema-version", required=True)
    parser.add_argument("--phase8a-qc-sha256", required=True)
    args = parser.parse_args()
    result, issues = run_prototype(
        args.manifest, args.receipt, args.profile, args.plan, args.authorization,
        args.authorization_file_sha256, args.phase8a_package_root, args.trust_root,
        args.trust_root_sha256, args.design_package_hash, args.phase8a_qc_artifact_id,
        args.phase8a_qc_schema_version, args.phase8a_qc_sha256,
    )
    print(json.dumps({"valid": result is not None and not issues, "issues": issues, "result": result}, ensure_ascii=False, indent=2))
    return 0 if result is not None and not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
