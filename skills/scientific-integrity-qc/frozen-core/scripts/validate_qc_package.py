#!/usr/bin/env python3
"""Validate the four-artifact QC package at schema and cross-artifact levels."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qc_gate_core import read_json, validate_package_semantics, write_json
from schema_runtime import ValidatorLoadError, validate_file


def _finding_paths(directory: Path) -> list[Path]:
    return sorted(directory.glob("finding-*.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-snapshot", type=Path, required=True)
    parser.add_argument("--candidate-snapshot", type=Path, required=True)
    parser.add_argument("--findings-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--schemas-dir", type=Path, default=Path(__file__).resolve().parents[1] / "schemas")
    parser.add_argument("--validator", type=Path)
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args()
    issues: list[dict[str, str]] = []
    try:
        schema_jobs = [
            (args.schemas_dir / "comparison-manifest.schema.json", args.manifest),
            (args.schemas_dir / "preservation-snapshot.schema.json", args.source_snapshot),
            (args.schemas_dir / "preservation-snapshot.schema.json", args.candidate_snapshot),
            (args.schemas_dir / "qc-report.schema.json", args.report),
        ]
        finding_paths = _finding_paths(args.findings_dir)
        schema_jobs.extend((args.schemas_dir / "qc-finding.schema.json", item) for item in finding_paths)
        for schema_path, data_path in schema_jobs:
            for issue in validate_file(schema_path, data_path, args.validator):
                issues.append({"layer": "schema", "artifact": str(data_path.resolve()), **issue})
        manifest = read_json(args.manifest)
        source_snapshot = read_json(args.source_snapshot)
        candidate_snapshot = read_json(args.candidate_snapshot)
        findings = [read_json(item) for item in finding_paths]
        report = read_json(args.report)
        for message in validate_package_semantics(manifest, source_snapshot, candidate_snapshot, findings, report):
            issues.append({"layer": "semantic", "artifact": "package", "path": "$", "keyword": "cross-artifact", "message": message})
    except (OSError, json.JSONDecodeError, ValidatorLoadError, RuntimeError) as exc:
        print(f"package validation error: {exc}", file=sys.stderr)
        return 2
    result = {"valid": not issues, "issue_count": len(issues), "issues": issues}
    if args.json_report:
        write_json(args.json_report, result)
    if issues:
        for issue in issues:
            print(f"{issue['layer']} {issue['artifact']} {issue['path']} [{issue['keyword']}] {issue['message']}")
        return 1
    print("QC package valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
