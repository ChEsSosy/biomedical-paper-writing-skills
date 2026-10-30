#!/usr/bin/env python3
"""Shared deterministic helpers for the isolated Phase 8B candidate."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable


PHASE8B_VERSION = "0.1.1"
CONTRACT_VERSION = "0.1.1"
PHASE8B_ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = PHASE8B_ROOT.parent
PHASE8A_ROOT = MODULE_ROOT / "candidate"
PHASE8A_VALIDATOR = PHASE8A_ROOT / "scripts" / "validate_figure_package.py"
PHASE8A_SCHEMA_RUNTIME = PHASE8A_ROOT / "scripts" / "schema_runtime.py"
SCHEMAS_DIR = PHASE8B_ROOT / "schemas"
SHA256_PATTERN = r"^[0-9a-f]{64}$"


class Phase8BError(RuntimeError):
    """Raised when a deterministic Phase 8B operation cannot continue safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def payload_sha256(value: dict[str, Any], *excluded: str) -> str:
    payload = {key: item for key, item in value.items() if key not in set(excluded)}
    return canonical_sha256(payload)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def load_module(path: Path, module_name: str) -> ModuleType:
    resolved = path.resolve()
    if not resolved.is_file():
        raise Phase8BError(f"required module not found: {resolved}")
    spec = importlib.util.spec_from_file_location(module_name, resolved)
    if spec is None or spec.loader is None:
        raise Phase8BError(f"could not load module: {resolved}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_phase8a_validator() -> ModuleType:
    """Load the frozen Phase 8A validator by exact path; never copy its rules."""
    scripts_dir = str((PHASE8A_ROOT / "scripts").resolve())
    inserted = scripts_dir not in sys.path
    if inserted:
        sys.path.insert(0, scripts_dir)
    try:
        return load_module(PHASE8A_VALIDATOR, "phase8b_frozen_phase8a_validator")
    finally:
        if inserted:
            sys.path.remove(scripts_dir)


def validate_schema(value: Any, schema_filename: str, instance_path: str) -> list[dict[str, str]]:
    runtime = load_module(PHASE8A_SCHEMA_RUNTIME, "phase8b_phase8a_schema_runtime")
    return runtime.validate_document(
        value,
        schema_filename,
        instance_path,
        schemas_dir=SCHEMAS_DIR,
    )


def issue(code: str, message: str, path: str = "$", severity: str = "error") -> dict[str, str]:
    return {
        "layer": "deterministic",
        "path": path,
        "code": code,
        "message": message,
        "review_route": "deterministic",
        "severity": severity,
    }


def resolved_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def require_relative_path(root: Path, relative: str, *, must_exist: bool = True) -> Path:
    candidate = (root / relative).resolve()
    if not resolved_within(candidate, root):
        raise Phase8BError(f"path escapes declared root: {relative}")
    if must_exist and not candidate.exists():
        raise Phase8BError(f"declared path does not exist: {candidate}")
    return candidate


def ref(identity: str, version: str, sha256: str, *, id_key: str) -> dict[str, str]:
    return {id_key: identity, "version": version, "sha256": sha256}


def execution_package_subject(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the pre-authorization subject defined by the frozen contract."""
    omitted = {
        "execution_manifest_sha256",
        "execution_package_hash",
        "authorization_ref",
        "authorization_state",
        "runtime_result_ref",
        "render_output_ref",
    }
    return {key: copy.deepcopy(value) for key, value in manifest.items() if key not in omitted}


def execution_package_hash(manifest: dict[str, Any]) -> str:
    return canonical_sha256(execution_package_subject(manifest))


def stable_profile_subject(profile: dict[str, Any]) -> dict[str, Any]:
    """Fields the runner must reproduce immediately before launch."""
    probe = profile.get("probe", {})
    return {
        "backend": profile.get("backend"),
        "executable_path": profile.get("executable_path"),
        "executable_sha256": profile.get("executable_sha256"),
        "python_version": profile.get("python_version"),
        "platform": profile.get("platform"),
        "packages": profile.get("packages"),
        "capabilities": profile.get("capabilities"),
        "limitations": profile.get("limitations"),
        "probe_script_version": probe.get("script_version"),
        "probe_script_sha256": probe.get("script_sha256"),
        "probe_result": probe.get("result"),
    }


def unique_codes(items: Iterable[dict[str, Any]]) -> list[str]:
    return sorted({str(item.get("code")) for item in items if item.get("code")})
