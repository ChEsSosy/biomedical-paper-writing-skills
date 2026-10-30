#!/usr/bin/env python3
"""Validate a Module 06 integrated output bundle without changing any artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from integration_runtime import (
    CORE_SCHEMA_ROOT,
    INTEGRATION_SCHEMA_ROOT,
    canonical_sha256,
    contained_path,
    file_sha256,
    payload_sha256,
    read_json,
    validate_schema_value,
)


OUTPUT_SCHEMAS = {
    "module06-integration-admission-receipt.json": INTEGRATION_SCHEMA_ROOT / "module06-integration-admission-receipt.schema.json",
    "module06-gate-report.json": INTEGRATION_SCHEMA_ROOT / "module06-gate-report.schema.json",
    "structured-text-projection-receipt.json": INTEGRATION_SCHEMA_ROOT / "structured-text-projection-receipt.schema.json",
    "comparison-manifest.json": CORE_SCHEMA_ROOT / "comparison-manifest.schema.json",
    "source-preservation-snapshot.json": CORE_SCHEMA_ROOT / "preservation-snapshot.schema.json",
    "candidate-preservation-snapshot.json": CORE_SCHEMA_ROOT / "preservation-snapshot.schema.json",
    "qc-report.json": CORE_SCHEMA_ROOT / "qc-report.schema.json",
}


def validate(bundle_path: Path, root: Path) -> list[str]:
    issues: list[str] = []
    bundle = read_json(bundle_path)
    issues.extend(f"bundle schema: {item}" for item in validate_schema_value(
        bundle, INTEGRATION_SCHEMA_ROOT / "module06-integrity-qc-bundle.schema.json"
    ))
    if bundle.get("schema_name") != "module06_integrity_qc_bundle" or bundle.get("schema_version") != "0.1.0":
        issues.append("bundle identity/version mismatch")
    if payload_sha256(bundle, "bundle_sha256") != bundle.get("bundle_sha256"):
        issues.append("bundle canonical self-hash mismatch")
    if bundle.get("author_approval_claimed") is not False or bundle.get("scientific_truth_claimed") is not False or bundle.get("automatic_repair_performed") is not False:
        issues.append("bundle claims prohibited authority or repair")
    artifacts: dict[str, dict[str, Any]] = {}
    for reference in bundle.get("output_artifacts", []):
        try:
            path = contained_path(root, reference.get("path", ""))
        except Exception as exc:  # keep validator output compact and fail closed
            issues.append(str(exc))
            continue
        if reference.get("file_sha256") != file_sha256(path):
            issues.append(f"output file hash mismatch: {reference.get('path')}")
            continue
        if path.suffix == ".json":
            value = read_json(path)
            schema_path = CORE_SCHEMA_ROOT / "qc-finding.schema.json" if path.parent.name == "findings" else OUTPUT_SCHEMAS.get(reference.get("path"))
            if schema_path is not None:
                issues.extend(f"{reference.get('path')} schema: {item}" for item in validate_schema_value(value, schema_path))
            if reference.get("canonical_sha256") != canonical_sha256(value):
                issues.append(f"output canonical hash mismatch: {reference.get('path')}")
            artifacts[reference["path"]] = value
    receipt = artifacts.get("module06-integration-admission-receipt.json")
    gate = artifacts.get("module06-gate-report.json")
    if receipt is None or gate is None:
        issues.append("bundle lacks admission receipt or gate report")
        return issues
    if payload_sha256(receipt, "receipt_sha256") != receipt.get("receipt_sha256"):
        issues.append("admission receipt self-hash mismatch")
    if payload_sha256(gate, "gate_report_sha256") != gate.get("gate_report_sha256"):
        issues.append("gate report self-hash mismatch")
    if bundle.get("admission_receipt_ref", {}).get("sha256") != receipt.get("receipt_sha256"):
        issues.append("bundle/admission receipt binding mismatch")
    if bundle.get("gate_report_ref", {}).get("sha256") != gate.get("gate_report_sha256"):
        issues.append("bundle/gate report binding mismatch")
    if bundle.get("request_id") != receipt.get("request_id") or bundle.get("request_id") != gate.get("request_id"):
        issues.append("request identity mismatch across output closure")
    if bundle.get("route") != receipt.get("route") or bundle.get("route") != gate.get("route"):
        issues.append("route mismatch across output closure")
    if bundle.get("terminal_state") != gate.get("terminal_state"):
        issues.append("terminal-state mismatch")
    if gate.get("human_review_required") is not True or bundle.get("human_review_required") is not True:
        issues.append("integrated output must retain human_review_required")
    for item in gate.get("domain_coverage", []):
        if item.get("implemented") is False and item.get("assessment_state") == "passed":
            issues.append(f"unimplemented domain was promoted to pass: {item.get('domain')}")
    if bundle.get("route") == "figure_qc" and gate.get("gate_outcome") == "pass":
        issues.append("Figure route cannot emit clean pass")
    if receipt.get("admission_state") == "rejected" and gate.get("terminal_state") not in {"blocked", "rejected"}:
        issues.append("rejected admission did not propagate to a fail-closed terminal state")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args()
    try:
        issues = validate(args.bundle, args.root.resolve())
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"integrated bundle validation error: {exc}", file=sys.stderr)
        return 2
    result = {"valid": not issues, "issue_count": len(issues), "issues": issues}
    if args.json_report:
        args.json_report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
