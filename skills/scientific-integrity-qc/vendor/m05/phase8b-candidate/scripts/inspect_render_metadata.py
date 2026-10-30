#!/usr/bin/env python3
"""Inspect deterministic metadata for exact Phase 8B render outputs."""

from __future__ import annotations

import argparse
import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from PIL import Image

from phase8b_runtime import Phase8BError, file_sha256, payload_sha256, read_json, utc_now, validate_schema, write_json


def inspect_render(
    execution_manifest: dict[str, Any], execution_result: dict[str, Any],
    admission_receipt: dict[str, Any], *, created_at: str | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    if execution_result.get("execution_result_sha256") != payload_sha256(execution_result, "execution_result_sha256"):
        issues.append({"layer": "deterministic", "path": "$.execution_result.execution_result_sha256", "code": "render:execution_result_hash", "message": "execution result self-hash mismatch", "review_route": "deterministic", "severity": "error"})
    if execution_result.get("status") != "succeeded" or execution_result.get("exit_code") != 0:
        issues.append({"layer": "deterministic", "path": "$.execution_result.status", "code": "render:execution_not_successful", "message": "render metadata cannot pass without successful execution", "review_route": "deterministic", "severity": "error"})
    expected_by_role = {item["role"]: item for item in execution_manifest.get("expected_outputs", [])}
    inspected_outputs: list[dict[str, Any]] = []
    for output in execution_result.get("outputs", []):
        path = Path(output["path"])
        metadata: dict[str, Any]
        if not path.is_file() or file_sha256(path) != output.get("sha256") or path.stat().st_size != output.get("size"):
            issues.append({"layer": "deterministic", "path": "$.execution_result.outputs", "code": "render:output_hash_or_size", "message": f"output identity mismatch: {path}", "review_route": "deterministic", "severity": "error"})
            continue
        fmt = output["format"]
        try:
            if fmt == "png":
                with Image.open(path) as image:
                    metadata = {"width": image.width, "height": image.height, "mode": image.mode, "detected_format": image.format}
            elif fmt == "svg":
                root = ET.parse(path).getroot()
                metadata = {"width": int(root.attrib["width"]), "height": int(root.attrib["height"]), "root_tag": root.tag}
            elif fmt == "tsv":
                with path.open("r", encoding="utf-8", newline="") as handle:
                    rows = list(csv.reader(handle, delimiter="\t"))
                metadata = {"columns": rows[0], "data_row_count": len(rows) - 1}
            elif fmt == "json":
                value = read_json(path)
                metadata = {"keys": sorted(value), "render_status": value.get("render_status")}
            else:
                raise Phase8BError(f"unsupported output format: {fmt}")
        except Exception as exc:
            issues.append({"layer": "deterministic", "path": "$.execution_result.outputs", "code": "render:metadata_unreadable", "message": f"{path}: {exc}", "review_route": "deterministic", "severity": "error"})
            continue
        expected = expected_by_role.get(output["role"])
        if expected is None or expected.get("format") != fmt or expected.get("panel_ids") != output.get("panel_ids"):
            issues.append({"layer": "deterministic", "path": "$.execution_result.outputs", "code": "render:declared_binding_mismatch", "message": f"output differs from declared role/format/panel coverage: {path}", "review_route": "deterministic", "severity": "error"})
        inspected_outputs.append({**output, "metadata": metadata})
    if issues:
        return None, issues
    manifest: dict[str, Any] = {
        "schema_name": "render_output_manifest", "schema_version": "0.1.0",
        "render_manifest_id": f"render-{execution_manifest['execution_id']}", "render_manifest_sha256": "0" * 64,
        "created_at": created_at or utc_now(),
        "execution_ref": {"id": execution_result["execution_result_id"], "version": execution_result["schema_version"], "sha256": execution_result["execution_result_sha256"]},
        "design_package_ref": {"id": admission_receipt["design_package_ref"]["design_package_id"], "version": admission_receipt["design_package_ref"]["design_package_version"], "sha256": admission_receipt["design_package_ref"]["design_package_hash"]},
        "admission_receipt_ref": {"id": admission_receipt["receipt_id"], "version": admission_receipt["schema_version"], "sha256": admission_receipt["receipt_sha256"]},
        "program_sha256": execution_result["program_sha256"],
        "input_bindings": [{"input_id": item["input_id"], "sha256": item["sha256"]} for item in execution_result["inputs_after"]],
        "outputs": inspected_outputs,
        "metadata_check": {"status": "passed", "checked_domains": ["existence", "format", "hash", "dimensions", "panel_coverage", "plotting_data_binding"], "limitations": ["metadata checks do not prove visual quality or cognitive inspection"]},
    }
    manifest["render_manifest_sha256"] = payload_sha256(manifest, "render_manifest_sha256")
    schema_issues = validate_schema(manifest, "render-output-manifest.schema.json", "$.render_output_manifest")
    if schema_issues:
        raise Phase8BError(f"internal render manifest schema failure: {schema_issues}")
    return manifest, []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("execution_manifest", type=Path)
    parser.add_argument("execution_result", type=Path)
    parser.add_argument("admission_receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value, issues = inspect_render(read_json(args.execution_manifest), read_json(args.execution_result), read_json(args.admission_receipt))
    if value is None:
        print(json.dumps({"valid": False, "issues": issues}, ensure_ascii=False, indent=2))
        return 1
    write_json(args.output, value)
    print(json.dumps({"valid": True, "render_manifest_sha256": value["render_manifest_sha256"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
