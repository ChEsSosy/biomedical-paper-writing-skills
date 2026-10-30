#!/usr/bin/env python3
"""Create a reviewable comparison manifest skeleton from two snapshots."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qc_gate_core import QCError, build_manifest, read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-snapshot", type=Path, required=True)
    parser.add_argument("--candidate-snapshot", type=Path, required=True)
    parser.add_argument("--producer", choices=("arbitrary_user_comparison", "article_polisher", "other_skill"), default="arbitrary_user_comparison")
    parser.add_argument("--revision-contract", type=Path)
    parser.add_argument(
        "--accept-one-to-one-for-comparison",
        action="store_true",
        help="Record caller acceptance for comparison execution; this never creates author approval.",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        revision_contract = read_json(args.revision_contract) if args.revision_contract else None
        manifest = build_manifest(
            read_json(args.source_snapshot),
            read_json(args.candidate_snapshot),
            producer=args.producer,
            accept_one_to_one=args.accept_one_to_one_for_comparison,
            revision_contract=revision_contract,
        )
        write_json(args.output, manifest)
    except (OSError, json.JSONDecodeError, QCError, KeyError) as exc:
        print(f"manifest creation error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
