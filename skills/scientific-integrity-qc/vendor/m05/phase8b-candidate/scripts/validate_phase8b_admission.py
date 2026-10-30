#!/usr/bin/env python3
"""Fresh Phase 8A admission gate for Phase 8B.

This module invokes the frozen Phase 8A validator by exact local path on every
admission.  A supplied receipt or cached valid flag is never accepted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from phase8b_runtime import (
    CONTRACT_VERSION,
    PHASE8A_VALIDATOR,
    Phase8BError,
    canonical_sha256,
    file_sha256,
    load_phase8a_validator,
    payload_sha256,
    read_json,
    unique_codes,
    utc_now,
    validate_schema,
    write_json,
)


RECEIPT_VERSION = "0.1.0"
CODE_EXECUTION_MODES = {"prototype_code_generation", "prototype_execution_and_inspection"}


def admit_phase8a(
    package_root: Path,
    trust_root_path: Path,
    expected_trust_root_sha256: str,
    expected_design_package_hash: str,
    expected_phase8a_qc_artifact_id: str,
    expected_phase8a_qc_schema_version: str,
    expected_phase8a_figure_qc_sha256: str,
    *,
    mode: str,
    created_at: str | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    try:
        validator = load_phase8a_validator()
        result = validator.validate_figure_package(
            package_root.resolve(),
            trust_root_path=trust_root_path.resolve(),
            expected_trust_root_sha256=expected_trust_root_sha256,
        )
    except Exception as exc:  # frozen validator supplies the diagnostic boundary
        return None, [{
            "layer": "deterministic", "path": "$.admission", "code": "admission:phase8a_invocation_failed",
            "message": str(exc), "review_route": "deterministic", "severity": "error",
        }]

    if not result.get("valid"):
        issues.extend(result.get("issues", []))
        issues.append({
            "layer": "deterministic", "path": "$.admission", "code": "admission:phase8a_invalid",
            "message": "fresh frozen Phase 8A validation did not pass", "review_route": "deterministic", "severity": "error",
        })
        return None, issues

    qc = result["qc"]
    manifest = read_json(package_root / "design-package-manifest.json")
    if manifest.get("design_package_hash") != expected_design_package_hash:
        issues.append({
            "layer": "deterministic", "path": "$.design_package_ref.design_package_hash", "code": "admission:design_hash_mismatch",
            "message": "fresh design-package hash differs from the caller binding", "review_route": "deterministic", "severity": "error",
        })
    if qc.get("design_package_hash") != expected_design_package_hash:
        issues.append({
            "layer": "deterministic", "path": "$.phase8a_qc_ref.design_package_hash", "code": "admission:qc_design_hash_mismatch",
            "message": "fresh Phase 8A QC binds a different design package", "review_route": "deterministic", "severity": "error",
        })
    if qc.get("figure_qc_sha256") != expected_phase8a_figure_qc_sha256:
        issues.append({
            "layer": "deterministic", "path": "$.phase8a_qc_ref.phase8a_figure_qc_sha256", "code": "admission:phase8a_qc_hash_mismatch",
            "message": "fresh Phase 8A QC hash differs from the caller binding", "review_route": "deterministic", "severity": "error",
        })
    if qc.get("artifact_id") != expected_phase8a_qc_artifact_id:
        issues.append({
            "layer": "deterministic", "path": "$.phase8a_qc_ref.artifact_id", "code": "admission:phase8a_qc_identity_mismatch",
            "message": "fresh Phase 8A QC artifact identity differs from the caller binding", "review_route": "deterministic", "severity": "error",
        })
    if qc.get("schema_version") != expected_phase8a_qc_schema_version:
        issues.append({
            "layer": "deterministic", "path": "$.phase8a_qc_ref.schema_version", "code": "admission:phase8a_qc_version_mismatch",
            "message": "fresh Phase 8A QC schema version differs from the caller binding", "review_route": "deterministic", "severity": "error",
        })
    if mode in CODE_EXECUTION_MODES and manifest.get("maturity") != "ready_for_prototype":
        issues.append({
            "layer": "deterministic", "path": "$.manifest.maturity", "code": "admission:maturity_below_ready_for_prototype",
            "message": "code generation/execution requires ready_for_prototype", "review_route": "deterministic", "severity": "error",
        })
    if issues:
        return None, issues

    trust_root = read_json(trust_root_path)
    receipt_created_at = created_at or utc_now()
    receipt_identity = canonical_sha256({
        "created_at": receipt_created_at,
        "design_package_hash": manifest["design_package_hash"],
        "phase8a_figure_qc_sha256": qc["figure_qc_sha256"],
        "validator_file_sha256": file_sha256(PHASE8A_VALIDATOR),
    })[:16]
    receipt: dict[str, Any] = {
        "schema_name": "phase8a_admission_receipt",
        "schema_version": RECEIPT_VERSION,
        "contract_version": CONTRACT_VERSION,
        "receipt_id": f"phase8a-admission-{receipt_identity}",
        "receipt_sha256": "0" * 64,
        "created_at": receipt_created_at,
        "mode": mode,
        "design_package_ref": {
            "design_package_id": manifest["design_package_id"],
            "design_package_version": manifest["design_package_version"],
            "design_package_hash": manifest["design_package_hash"],
        },
        "trust_root_ref": {
            "root_id": trust_root["trust_root_id"],
            "root_version": trust_root["schema_version"],
            "root_sha256": expected_trust_root_sha256,
        },
        "phase8a_qc_ref": {
            "artifact_id": qc["artifact_id"],
            "schema_version": qc["schema_version"],
            "design_package_hash": qc["design_package_hash"],
            "phase8a_figure_qc_sha256": qc["figure_qc_sha256"],
        },
        "validator": {
            "validator_version": validator.VALIDATOR_VERSION,
            "ruleset_version": validator.RULESET_VERSION,
            "file_path": str(PHASE8A_VALIDATOR.resolve()),
            "file_sha256": file_sha256(PHASE8A_VALIDATOR),
        },
        "invocation_result": {
            "valid": True,
            "issue_codes": unique_codes(result.get("issues", [])),
            "readiness_gate": qc["readiness_gate"],
        },
    }
    receipt["receipt_sha256"] = payload_sha256(receipt, "receipt_sha256")
    schema_issues = validate_schema(receipt, "phase8a-admission-receipt.schema.json", "$.phase8a_admission_receipt")
    if schema_issues:
        raise Phase8BError(f"internal admission receipt schema failure: {schema_issues}")
    return receipt, []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", type=Path)
    parser.add_argument("--trust-root", type=Path, required=True)
    parser.add_argument("--trust-root-sha256", required=True)
    parser.add_argument("--design-package-hash", required=True)
    parser.add_argument("--phase8a-qc-sha256", required=True)
    parser.add_argument("--phase8a-qc-artifact-id", required=True)
    parser.add_argument("--phase8a-qc-schema-version", required=True)
    parser.add_argument("--mode", choices=["design_review_only", "prototype_code_generation", "prototype_execution_and_inspection"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    receipt, issues = admit_phase8a(
        args.package_root, args.trust_root, args.trust_root_sha256,
        args.design_package_hash, args.phase8a_qc_artifact_id,
        args.phase8a_qc_schema_version, args.phase8a_qc_sha256, mode=args.mode,
    )
    if receipt is None:
        print(json.dumps({"valid": False, "issues": issues}, ensure_ascii=False, indent=2))
        return 1
    write_json(args.output, receipt)
    print(json.dumps({"valid": True, "receipt_sha256": receipt["receipt_sha256"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
