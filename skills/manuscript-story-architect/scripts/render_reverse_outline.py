#!/usr/bin/env python3
"""Render current and proposed manuscript structure without rewriting source prose."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from schema_runtime import validate_schema
from story_artifact_checks import load_json_object


ROOT = Path(__file__).resolve().parents[1]


def _join_ids(value: Any) -> str:
    """Render stable identifiers distinctly from narrative planning text."""
    return (
        ", ".join(f"`{item}`" for item in value if isinstance(item, str))
        if isinstance(value, list)
        else ""
    )


def render_reverse_outline(plan: dict[str, Any]) -> str:
    """Create a deterministic Markdown view containing planning fields only."""
    lines = [
        f"# Reverse Outline — {plan.get('plan_label', plan.get('plan_id', 'unnamed plan'))}",
        "",
        f"- Plan ID: `{plan.get('plan_id', '')}`",
        f"- Artifact status: `{plan.get('status', '')}`",
        f"- Document type: `{plan.get('document_type', '')}`",
        "",
        "## Current structure",
        "",
    ]
    current = plan.get("current_structure_assessment", {})
    if current.get("input_mode") == "structured_notes":
        lines.append(f"Reverse outline skipped: `{current.get('skipped_reason', '')}`.")
    else:
        for item in current.get("reverse_outline_items", []):
            lines.append(
                f"- `{item.get('source_paragraph_id', '')}` — {item.get('current_role', '')}"
            )

    lines.extend(["", "## Proposed structure", ""])
    for section in plan.get("section_plans", []):
        lines.append(
            f"### {section.get('canonical_section', 'other')} — `{section.get('section_id', '')}`"
        )
        lines.append("")
        lines.append(f"Goal: {section.get('goal', '')}")
        lines.append("")
        for paragraph in section.get("paragraph_plans", []):
            lines.append(
                f"- `{paragraph.get('paragraph_id', '')}` [{paragraph.get('role', 'other')}] "
                f"{paragraph.get('goal', '')}"
            )
            lines.append(f"  - Claims: {_join_ids(paragraph.get('claim_ids', [])) or 'none'}")
            lines.append(f"  - Evidence: {_join_ids(paragraph.get('evidence_ids', [])) or 'none'}")
            lines.append(f"  - Figures: {_join_ids(paragraph.get('figure_ids', [])) or 'none'}")
            lines.append(
                f"  - Material reordering: {str(bool(paragraph.get('material_reordering'))).lower()}"
            )
            lines.append(f"  - Approval: `{paragraph.get('author_approval', '')}`")
        lines.append("")

    lines.extend(["## Figure sequence", ""])
    for figure in sorted(plan.get("figure_sequence", []), key=lambda item: item.get("order", 0)):
        lines.append(
            f"{figure.get('order', '?')}. `{figure.get('figure_id', '')}` — {figure.get('purpose', '')}"
        )
        lines.append(f"   - Claims: {_join_ids(figure.get('claim_ids', [])) or 'none'}")
        lines.append(f"   - Evidence: {_join_ids(figure.get('evidence_ids', [])) or 'none'}")

    audit = plan.get("evidence_assignment_audit", {})
    lines.extend(["", "## Evidence assignment audit", ""])
    lines.append(f"- Assigned: {_join_ids(audit.get('assigned_evidence_ids', [])) or 'none'}")
    for item in audit.get("unassigned_evidence", []):
        lines.append(
            f"- Unassigned `{item.get('evidence_id', '')}` — `{item.get('reason', '')}`: "
            f"{item.get('rationale', '')}"
        )

    lines.extend(["", "## Author decisions", ""])
    decisions = plan.get("author_decisions", [])
    if not decisions:
        lines.append("- None declared.")
    for decision in decisions:
        lines.append(
            f"- `{decision.get('decision_id', '')}` [{decision.get('status', '')}] "
            f"{decision.get('question', '')}"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validator", type=Path)
    args = parser.parse_args()
    try:
        issues = validate_schema(
            ROOT / "schemas" / "manuscript-plan.schema.json", args.plan, args.validator
        )
        if issues:
            for item in issues:
                print(f"{item.path} [{item.code}] {item.message}", file=sys.stderr)
            return 1
        rendered = render_reverse_outline(load_json_object(args.plan))
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
            print(f"WROTE: {args.output}")
        else:
            print(rendered, end="")
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"render error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
