#!/usr/bin/env python3
"""Extract a deterministic preservation snapshot from UTF-8 text or Markdown."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qc_gate_core import QCError, build_snapshot, write_json


def _load_terms(path: Path | None) -> list[dict[str, str]]:
    if path is None:
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise QCError("--terms must be a JSON array of {term, match_mode} objects")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--side", choices=("source", "candidate"), required=True)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--file-id")
    parser.add_argument("--terms", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        snapshot = build_snapshot(args.input, args.side, args.document_id, args.file_id, _load_terms(args.terms))
        write_json(args.output, snapshot)
    except (OSError, json.JSONDecodeError, QCError) as exc:
        print(f"snapshot extraction error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
