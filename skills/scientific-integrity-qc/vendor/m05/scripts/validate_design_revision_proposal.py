#!/usr/bin/env python3
"""Validate one standalone Phase 8B design-revision proposal."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PHASE8B_SCRIPTS = PACKAGE_ROOT / "phase8b-candidate" / "scripts"
sys.path.insert(0, str(PHASE8B_SCRIPTS))

from phase8b_runtime import read_json  # noqa: E402
from validate_phase8b_package import validate_design_revision_proposal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal", type=Path)
    args = parser.parse_args()
    issues = validate_design_revision_proposal(read_json(args.proposal))
    result = {"valid": not issues, "issues": issues}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
