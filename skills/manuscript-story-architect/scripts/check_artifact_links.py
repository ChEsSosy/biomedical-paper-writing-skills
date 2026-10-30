#!/usr/bin/env python3
"""Validate and cross-check one claim map, its cards, and one manuscript plan."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from schema_runtime import validate_schema
from story_artifact_checks import check_artifact_links, issue_dicts, load_json_object


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim-map", type=Path, required=True)
    parser.add_argument("--interpretation-card", type=Path, action="append", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--validator", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        issues = validate_schema(
            ROOT / "schemas" / "claim-evidence-map.schema.json", args.claim_map, args.validator
        )
        for card_path in args.interpretation_card:
            issues.extend(
                validate_schema(ROOT / "schemas" / "interpretation-card.schema.json", card_path, args.validator)
            )
        issues.extend(
            validate_schema(ROOT / "schemas" / "manuscript-plan.schema.json", args.plan, args.validator)
        )
        claim_map = load_json_object(args.claim_map)
        cards = [load_json_object(path) for path in args.interpretation_card]
        plan = load_json_object(args.plan)
        issues.extend(check_artifact_links(claim_map, cards, plan))
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"link-check error: {exc}", file=sys.stderr)
        return 2

    report = {
        "valid": not issues,
        "scope": "structural_and_declared_consistency_not_scientific_truth",
        "claim_map": str(args.claim_map.resolve()),
        "interpretation_cards": [str(path.resolve()) for path in args.interpretation_card],
        "plan": str(args.plan.resolve()),
        "issues": issue_dicts(issues),
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if issues:
        for item in issues:
            print(f"{item.path} [{item.code}] {item.message}")
        return 1
    print("VALID: artifact links and declared states are consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
