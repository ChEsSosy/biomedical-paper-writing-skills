#!/usr/bin/env python3
"""Run one frozen-contract Module 06 Article, Review, or Figure admission and QC route."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from integration_runtime import IntegrationError, process_request, read_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--invocation-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        request = read_json(args.request)
        bundle, exit_code = process_request(request, args.invocation_root, args.output_dir)
    except (OSError, json.JSONDecodeError, IntegrationError) as exc:
        print(f"Module 06 integration error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "valid_invocation": exit_code == 0,
        "terminal_state": bundle["terminal_state"],
        "bundle": str((args.output_dir / "module06-integrity-qc-bundle.json").resolve()),
    }, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
