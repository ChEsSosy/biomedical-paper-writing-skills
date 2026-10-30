#!/usr/bin/env python3
"""Render a human-readable Markdown view without changing QC decisions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qc_gate_core import read_json, render_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--findings-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        findings = [read_json(path) for path in sorted(args.findings_dir.glob("finding-*.json"))]
        output = render_report(read_json(args.report), findings)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"report rendering error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
