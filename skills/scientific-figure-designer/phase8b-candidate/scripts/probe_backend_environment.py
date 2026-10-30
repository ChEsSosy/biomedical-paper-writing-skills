#!/usr/bin/env python3
"""Deterministically probe the single Phase 8B minimum backend."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from PIL import __version__ as PILLOW_VERSION

from phase8b_runtime import (
    Phase8BError,
    file_sha256,
    payload_sha256,
    read_json,
    stable_profile_subject,
    utc_now,
    validate_schema,
    write_json,
)


PROBE_VERSION = "0.1.0"
SCRIPT_PATH = Path(__file__).resolve()


def probe_current(*, created_at: str | None = None) -> dict[str, Any]:
    executable = Path(sys.executable).resolve()
    profile: dict[str, Any] = {
        "schema_name": "backend_environment_profile",
        "schema_version": "0.1.0",
        "profile_id": "restricted-python-pillow-local",
        "profile_sha256": "0" * 64,
        "backend": "restricted_python",
        "executable_path": str(executable),
        "executable_sha256": file_sha256(executable),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "packages": [
            {"name": "python-stdlib", "version": platform.python_version()},
            {"name": "Pillow", "version": PILLOW_VERSION},
        ],
        "capabilities": {
            "formats": ["json", "png", "svg", "tsv"],
            "fonts": ["Pillow-default-bitmap"],
            "operations": [
                "draw_axes", "draw_legend", "draw_raw_points", "draw_supplied_annotation",
                "export_plot_data", "export_png", "export_session_metadata", "export_svg",
            ],
        },
        "limitations": [
            "synthetic quantitative point plots only",
            "no inferential statistics or aggregation",
            "no arbitrary user Python",
            "font coverage limited to Pillow default bitmap font",
        ],
        "probe": {
            "script_version": PROBE_VERSION,
            "script_sha256": file_sha256(SCRIPT_PATH),
            "command": [str(executable), "-B", str(SCRIPT_PATH)],
            "created_at": created_at or utc_now(),
            "result": "available",
        },
    }
    profile["profile_sha256"] = payload_sha256(profile, "profile_sha256")
    schema_issues = validate_schema(profile, "backend-environment-profile.schema.json", "$.backend_environment_profile")
    if schema_issues:
        raise Phase8BError(f"internal backend profile schema failure: {schema_issues}")
    return profile


def probe_executable(executable: Path) -> dict[str, Any]:
    resolved = executable.resolve()
    if resolved == Path(sys.executable).resolve():
        return probe_current()
    completed = subprocess.run(
        [str(resolved), "-B", str(SCRIPT_PATH), "--stdout-json"],
        check=False, capture_output=True, text=True,
    )
    if completed.returncode != 0:
        raise Phase8BError(f"backend probe failed ({completed.returncode}): {completed.stderr.strip()}")
    return json.loads(completed.stdout)


def verify_profile(profile: dict[str, Any]) -> list[dict[str, str]]:
    issues = validate_schema(profile, "backend-environment-profile.schema.json", "$.backend_environment_profile")
    if profile.get("backend") != "restricted_python":
        issues.append({"layer": "deterministic", "path": "$.backend_environment_profile.backend", "code": "backend:unsupported", "message": "Phase 8B minimum does not substitute or admit another backend", "review_route": "deterministic", "severity": "error"})
    if profile.get("profile_sha256") != payload_sha256(profile, "profile_sha256"):
        issues.append({"layer": "deterministic", "path": "$.backend_environment_profile.profile_sha256", "code": "backend:profile_hash", "message": "backend profile self-hash mismatch", "review_route": "deterministic", "severity": "error"})
    try:
        fresh = probe_executable(Path(profile.get("executable_path", "")))
        if stable_profile_subject(profile) != stable_profile_subject(fresh):
            issues.append({"layer": "deterministic", "path": "$.backend_environment_profile", "code": "backend:fresh_probe_mismatch", "message": "fresh deterministic probe differs from supplied profile", "review_route": "deterministic", "severity": "error"})
    except Exception as exc:
        issues.append({"layer": "deterministic", "path": "$.backend_environment_profile", "code": "backend:probe_failed", "message": str(exc), "review_route": "deterministic", "severity": "error"})
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--stdout-json", action="store_true")
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        issues = verify_profile(read_json(args.verify))
        print(json.dumps({"valid": not issues, "issues": issues}, ensure_ascii=False, indent=2))
        return 0 if not issues else 1
    profile = probe_current()
    if args.output:
        write_json(args.output, profile)
    print(json.dumps(profile if args.stdout_json else {"valid": True, "profile_sha256": profile["profile_sha256"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
