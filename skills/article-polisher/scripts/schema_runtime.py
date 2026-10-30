#!/usr/bin/env python3
"""Load only the package-local, hash-bound shared schema validator."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_RELATIVE = Path("shared-core/scripts/validate_artifact.py")
VENDOR_INVENTORY_RELATIVE = Path("shared-core/shared-core-vendor-inventory.json")
EXPECTED_SHARED_CORE_VERSION = "0.2.2"
EXPECTED_VALIDATOR_SHA256 = "898ea588b065eedeb1ca7867ee2a3631496d8a36ca5605e4fd2718725003cc49"
EXPECTED_VENDOR_INVENTORY_SHA256 = "a584b246d88e035a54eca8ab9859c7dc5e9eadf6518d9cfb8117a72d7f087590"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _payload_sha256(value: dict[str, Any], field: str) -> str:
    payload = dict(value)
    payload.pop(field, None)
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_validator(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label} does not exist: {resolved}")
    actual = _file_sha256(resolved)
    if actual != EXPECTED_VALIDATOR_SHA256:
        raise RuntimeError(f"{label} SHA-256 mismatch: expected {EXPECTED_VALIDATOR_SHA256}, got {actual}")
    return resolved


def discover_validator(explicit_path: Path | None = None) -> Path:
    """Verify the local trust root before accepting an optional identical copy."""
    inventory_path = (PACKAGE_ROOT / VENDOR_INVENTORY_RELATIVE).resolve()
    if not inventory_path.is_file():
        raise FileNotFoundError(f"vendored shared-core inventory does not exist: {inventory_path}")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if not isinstance(inventory, dict):
        raise RuntimeError("vendored shared-core inventory must be an object")
    payload_hash = _payload_sha256(inventory, "inventory_sha256")
    if inventory.get("inventory_sha256") != payload_hash:
        raise RuntimeError("vendored shared-core inventory self-hash mismatch")
    if payload_hash != EXPECTED_VENDOR_INVENTORY_SHA256:
        raise RuntimeError("vendored shared-core inventory is not the package-pinned inventory")
    if inventory.get("authoritative_core", {}).get("version") != EXPECTED_SHARED_CORE_VERSION:
        raise RuntimeError("vendored shared-core version mismatch")
    records = [
        item for item in inventory.get("files", [])
        if item.get("vendored_relative_path") == "scripts/validate_artifact.py"
    ]
    if len(records) != 1 or records[0].get("sha256") != EXPECTED_VALIDATOR_SHA256:
        raise RuntimeError("vendored inventory does not bind the package-pinned validator")
    vendored = _require_validator(PACKAGE_ROOT / VALIDATOR_RELATIVE, "vendored shared-core validator")
    if records[0].get("size_bytes") != vendored.stat().st_size:
        raise RuntimeError("vendored validator size mismatch")
    if explicit_path is None:
        return vendored
    return _require_validator(explicit_path, "explicit schema validator")


def load_validator(path: Path) -> Any:
    module_name = f"article_polisher_schema_validator_{EXPECTED_VALIDATOR_SHA256[:16]}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import schema validator: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    if not callable(getattr(module, "validate_files", None)):
        raise RuntimeError("schema validator lacks validate_files")
    return module
