#!/usr/bin/env python3
"""Validate claim-map schema plus deterministic identity and link invariants."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from schema_runtime import validate_schema
from story_artifact_checks import issue_dicts, load_json_object, validate_claim_map


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim-map", type=Path, required=True)
    parser.add_argument("--validator", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        issues = validate_schema(
            ROOT / "schemas" / "claim-evidence-map.schema.json",
            args.claim_map,
            args.validator,
        )
        payload = load_json_object(args.claim_map)
        issues.extend(validate_claim_map(payload))
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"validator error: {exc}", file=sys.stderr)
        return 2

    report = {
        "valid": not issues,
        "scope": "structural_and_declared_consistency_not_scientific_truth",
        "claim_map": str(args.claim_map.resolve()),
        "issues": issue_dicts(issues),
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if issues:
        for item in issues:
            print(f"{item.path} [{item.code}] {item.message}")
        return 1
    print(f"VALID: {args.claim_map}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
