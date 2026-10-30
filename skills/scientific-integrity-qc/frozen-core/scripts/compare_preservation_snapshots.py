#!/usr/bin/env python3
"""Compare two preservation snapshots under a reviewed comparison manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qc_gate_core import compare_snapshots, read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-snapshot", type=Path, required=True)
    parser.add_argument("--candidate-snapshot", type=Path, required=True)
    parser.add_argument("--findings-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        findings, report = compare_snapshots(
            read_json(args.manifest),
            read_json(args.source_snapshot),
            read_json(args.candidate_snapshot),
        )
        args.findings_dir.mkdir(parents=True, exist_ok=True)
        existing = list(args.findings_dir.glob("finding-*.json"))
        if existing:
            raise RuntimeError(f"findings directory already contains generated findings: {args.findings_dir}")
        for finding in findings:
            number = finding["finding_id"].rsplit(":", 1)[-1]
            write_json(args.findings_dir / f"finding-{number}.json", finding)
        write_json(args.report, report)
    except (OSError, json.JSONDecodeError, KeyError, RuntimeError) as exc:
        print(f"comparison error: {exc}", file=sys.stderr)
        return 2
    print(f"gate_outcome={report['gate_outcome']} findings={len(findings)}")
    return 0 if report["gate_outcome"] in {"pass", "pass_with_warnings"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
