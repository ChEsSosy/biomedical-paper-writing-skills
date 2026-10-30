"""Project Markdown by exact reviewed spans and literals; unlisted prose is retained.

No heading-scope, minimum-word-count or long-paragraph heuristic removes text.
Corpus-specific decisions stay outside the reusable Skill.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

PAGE = re.compile(r"^<!-- PDF PAGE (\d+) / \d+ -->$")
HEADING = re.compile(r"^#{1,6}\s+")
ANCILLARY = re.compile(r"^(?:#{1,6}\s+)?\*{0,2}(?:Box|Table|Fig(?:ure)?\.?)\s+\d+\s*\|", re.I)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class Block:
    text: str
    first: int
    last: int
    page: int | None
    kind: str


def source_blocks(text: str) -> list[Block]:
    """Keep complete nonblank blocks and line/page positions, including markers."""
    result = []
    pending = []
    first = 0
    page = None

    def flush(last):
        if pending:
            result.append(Block("\n".join(pending), first, last, page, "paragraph"))
            pending.clear()

    lines = text.splitlines()
    for n, line in enumerate(lines, 1):
        if not line.strip():
            flush(n - 1)
        elif PAGE.match(line.strip()):
            flush(n - 1)
            page = int(PAGE.match(line.strip()).group(1))
            result.append(Block(line, n, n, page, "page_marker"))
        elif line.startswith(("#", "<!--", "```")):
            flush(n - 1)
            result.append(Block(line, n, n, page, "heading" if HEADING.match(line) else "markup"))
        else:
            if not pending:
                first = n
            pending.append(line)
    flush(len(lines))
    return result


def project_bytes(data: bytes, plan: dict) -> tuple[str, dict]:
    if plan.get("source_sha256") != digest(data):
        raise ValueError("projection source hash mismatch")
    blocks = source_blocks(data.decode("utf-8"))
    by_span = {(b.first, b.last): b for b in blocks}
    exclusions = {}
    for item in plan.get("exclude", []):
        span = (item.get("start_line"), item.get("end_line"))
        if span not in by_span or span in exclusions:
            raise ValueError(f"exclusion must name a unique whole source block: {span}")
        if not item.get("reason", "").strip():
            raise ValueError("exclusion requires a reason")
        if item.get("span_sha256") != digest(by_span[span].text.encode("utf-8")):
            raise ValueError(f"exclusion span hash mismatch: {span}")
        exclusions[span] = item["reason"]
    removals = {}
    for item in plan.get("remove_literals", []):
        span = (item.get("start_line"), item.get("end_line"))
        if span not in by_span or span in exclusions or by_span[span].kind != "paragraph":
            raise ValueError(f"literal removal requires a retained paragraph block: {span}")
        source_text = by_span[span].text
        literal = item.get("literal")
        if (not isinstance(literal, str) or not literal or literal == source_text
                or source_text.count(literal) != 1):
            raise ValueError(f"literal removal must match exactly once and retain prose: {span}")
        if item.get("source_span_sha256") != digest(source_text.encode("utf-8")):
            raise ValueError(f"literal removal source hash mismatch: {span}")
        if item.get("literal_sha256") != digest(literal.encode("utf-8")):
            raise ValueError(f"literal removal hash mismatch: {span}")
        if not item.get("reason", "").strip():
            raise ValueError("literal removal requires a reason")
        start = source_text.index(literal)
        end = start + len(literal)
        if any(start < prior_end and prior_start < end for prior_start, prior_end, _ in removals.get(span, [])):
            raise ValueError(f"overlapping literal removals: {span}")
        removals.setdefault(span, []).append((start, end, item["reason"]))
    by_start = {b.first: b for b in blocks}
    moves = {}
    for item in plan.get("move_after", []):
        start = item.get("start_line")
        target = item.get("after_start_line")
        moved = by_start.get(start)
        anchor = by_start.get(target)
        if (start in moves or moved is None or anchor is None or start == target
                or moved.kind != "paragraph" or anchor.kind != "paragraph"
                or (moved.first, moved.last) in exclusions
                or (anchor.first, anchor.last) in exclusions):
            raise ValueError(f"move requires distinct retained paragraph blocks: {start}, {target}")
        if (item.get("end_line") != moved.last
                or item.get("source_span_sha256") != digest(moved.text.encode("utf-8"))
                or item.get("after_span_sha256") != digest(anchor.text.encode("utf-8"))
                or not item.get("reason", "").strip()):
            raise ValueError(f"move source, anchor or reason mismatch: {start}, {target}")
        moves[start] = (target, item["reason"])
    if any(target in moves for target, _ in moves.values()):
        raise ValueError("move anchor may not itself be moved")
    ordered_blocks = list(blocks)
    for start, (target, _) in moves.items():
        moved = by_start[start]
        ordered_blocks.remove(moved)
        ordered_blocks.insert(ordered_blocks.index(by_start[target]) + 1, moved)
    joins = {}
    for item in plan.get("joins", []):
        start = item["start_line"]
        if start in joins:
            raise ValueError("duplicate join")
        joins[start] = item["previous_start_line"]
    ledger = []
    parts = []
    line_count = 0
    previous = None
    used_joins = set()
    for b in ordered_blocks:
        row = {"source_start_line": b.first, "source_end_line": b.last,
               "pdf_page": b.page, "kind": b.kind,
               "source_span_sha256": digest(b.text.encode("utf-8"))}
        reason = exclusions.get((b.first, b.last))
        if b.kind == "page_marker":
            reason = "page_locator_metadata"
        if reason:
            row.update(action="exclude", reason=reason)
        else:
            selected = b.text
            removed = []
            for start_offset, end_offset, removal_reason in sorted(removals.get((b.first, b.last), []), reverse=True):
                literal = b.text[start_offset:end_offset]
                selected = selected[:start_offset] + selected[end_offset:]
                removed.append({"source_char_start": start_offset, "source_char_end": end_offset,
                                "source_start_line": b.first + b.text[:start_offset].count("\n"),
                                "source_end_line": b.first + b.text[:end_offset].count("\n"),
                                "literal_sha256": digest(literal.encode("utf-8")),
                                "reason": removal_reason})
            if not selected.strip():
                raise ValueError(f"literal removal emptied retained block: {b.first}")
            if ANCILLARY.match(selected.strip()):
                raise ValueError(f"unresolved ancillary boundary at line {b.first}; review an exact span")
            join = b.first in joins
            if join:
                if previous is None or previous.first != joins[b.first] or previous.kind != "paragraph" or b.kind != "paragraph":
                    raise ValueError(f"join must bind adjacent retained prose blocks: {b.first}")
                used_joins.add(b.first)
            separator = "" if not parts else ("\n" if join else "\n\n")
            start = 1 if not parts else line_count + (1 if join else 2)
            parts.append(separator + selected)
            end = start + len(selected.splitlines()) - 1
            row.update(action="include", reason="retained_source", analysis_start_line=start,
                       analysis_end_line=end, joined_to_previous=join,
                       projected_span_sha256=digest(selected.encode("utf-8")))
            if removed:
                row["removed_literals"] = sorted(removed, key=lambda x: x["source_char_start"])
            if b.first in moves:
                row["moved_after_source_start_line"] = moves[b.first][0]
                row["move_reason"] = moves[b.first][1]
            line_count = end
            previous = b
        ledger.append(row)
    if used_joins != set(joins):
        raise ValueError("join target missing or excluded")
    ledger.sort(key=lambda row: row["source_start_line"])
    output = "".join(parts) + "\n"
    if not parts:
        raise ValueError("empty projection")
    report = {"version": "0.1.0", "status": "author_review_required",
              "source_sha256": digest(data), "analysis_sha256": digest(output.encode("utf-8")),
              "included_blocks": sum(x["action"] == "include" for x in ledger),
              "excluded_blocks": sum(x["action"] == "exclude" for x in ledger),
              "joins_applied": len(used_joins), "moves_applied": len(moves), "ledger": ledger}
    return output, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.receipt.resolve() or args.output.exists() or args.receipt.exists():
        raise SystemExit("Projection outputs must be distinct new paths")
    output, report = project_bytes(args.source.read_bytes(), json.loads(args.plan.read_text(encoding="utf-8")))
    report["source_path"] = str(args.source.resolve())
    for path in (args.output, args.receipt):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8", newline="\n")
    args.receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Retained {report['included_blocks']} blocks; excluded {report['excluded_blocks']}; joins {report['joins_applied']}")


if __name__ == "__main__":
    main()
