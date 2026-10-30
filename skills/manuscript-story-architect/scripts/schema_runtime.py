#!/usr/bin/env python3
"""Load only a hash-bound schema validator admitted by the packaged trust root."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from story_artifact_checks import CheckIssue


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_IN_VENDOR_RELATIVE = Path("scripts/validate_artifact.py")
VENDORED_VALIDATOR_RELATIVE = Path("shared-core") / VALIDATOR_IN_VENDOR_RELATIVE
VENDOR_INVENTORY_RELATIVE = Path("shared-core/shared-core-vendor-inventory.json")
EXPECTED_SHARED_CORE_VERSION = "0.2.2"
EXPECTED_VALIDATOR_SHA256 = "898ea588b065eedeb1ca7867ee2a3631496d8a36ca5605e4fd2718725003cc49"
EXPECTED_VENDOR_INVENTORY_SHA256 = "a584b246d88e035a54eca8ab9859c7dc5e9eadf6518d9cfb8117a72d7f087590"


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _payload_sha256(value: dict[str, Any], hash_field: str) -> str:
    payload = dict(value)
    payload.pop(hash_field, None)
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_validator_hash(path: Path, *, label: str) -> Path:
    candidate = path.resolve()
    if not candidate.is_file():
        raise FileNotFoundError(f"{label} does not exist: {candidate}")
    actual = _file_sha256(candidate)
    if actual != EXPECTED_VALIDATOR_SHA256:
        raise RuntimeError(
            f"{label} SHA-256 mismatch: expected "
            f"{EXPECTED_VALIDATOR_SHA256}, got {actual}"
        )
    return candidate


def _verified_vendored_validator() -> Path:
    inventory_path = (PACKAGE_ROOT / VENDOR_INVENTORY_RELATIVE).resolve()
    if not inventory_path.is_file():
        raise FileNotFoundError(f"Vendored shared-core inventory does not exist: {inventory_path}")
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read vendored shared-core inventory: {exc}") from exc
    if not isinstance(inventory, dict):
        raise RuntimeError("Vendored shared-core inventory must be a JSON object")
    actual_payload_hash = _payload_sha256(inventory, "inventory_sha256")
    if inventory.get("inventory_sha256") != actual_payload_hash:
        raise RuntimeError("Vendored shared-core inventory self-hash mismatch")
    if actual_payload_hash != EXPECTED_VENDOR_INVENTORY_SHA256:
        raise RuntimeError(
            "Vendored shared-core inventory is not the package-pinned inventory: "
            f"expected {EXPECTED_VENDOR_INVENTORY_SHA256}, got {actual_payload_hash}"
        )
    authoritative = inventory.get("authoritative_core", {})
    if authoritative.get("version") != EXPECTED_SHARED_CORE_VERSION:
        raise RuntimeError("Vendored shared-core version mismatch")
    validator_records = [
        item
        for item in inventory.get("files", [])
        if item.get("vendored_relative_path") == VALIDATOR_IN_VENDOR_RELATIVE.as_posix()
    ]
    if len(validator_records) != 1:
        raise RuntimeError("Vendored inventory must bind exactly one schema validator")
    record = validator_records[0]
    if record.get("sha256") != EXPECTED_VALIDATOR_SHA256:
        raise RuntimeError("Vendored inventory validator hash is not the package-pinned hash")
    validator_path = _require_validator_hash(
        PACKAGE_ROOT / VENDORED_VALIDATOR_RELATIVE,
        label="Vendored shared-core validator",
    )
    if record.get("size_bytes") != validator_path.stat().st_size:
        raise RuntimeError("Vendored shared-core validator size mismatch")
    return validator_path


def discover_validator(explicit_path: Path | None = None) -> Path:
    """Resolve only the package-local validator or an explicitly byte-identical copy."""
    vendored = _verified_vendored_validator()
    if explicit_path is None:
        return vendored
    return _require_validator_hash(
        explicit_path,
        label="Explicit schema validator",
    )


def _load_validator(path: Path) -> Any:
    module_name = f"story_shared_schema_validator_{EXPECTED_VALIDATOR_SHA256[:16]}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import schema validator: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    if not callable(getattr(module, "validate_files", None)):
        raise RuntimeError("Schema validator lacks required validate_files interface")
    return module


def validate_schema(
    schema_path: Path,
    data_path: Path,
    validator_path: Path | None = None,
) -> list[CheckIssue]:
    """Validate one artifact and normalize hash-bound shared-validator findings."""
    resolved_validator = discover_validator(validator_path)
    module = _load_validator(resolved_validator)
    findings = module.validate_files(schema_path.resolve(), data_path.resolve())
    return [
        CheckIssue(
            code=f"schema:{finding.keyword}",
            path=finding.path,
            message=finding.message,
        )
        for finding in findings
    ]
