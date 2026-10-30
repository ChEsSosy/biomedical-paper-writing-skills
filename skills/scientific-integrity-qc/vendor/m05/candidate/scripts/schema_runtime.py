#!/usr/bin/env python3
"""Dependency-free JSON Schema bridge for the Phase 8A candidate.

The project already has a deterministic Draft 2020-12 subset validator in the
frozen shared artifact core.  This module loads that implementation by exact
local path so Phase 8A does not introduce a second, incompatible schema engine
or require a package installation.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


CANDIDATE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = CANDIDATE_ROOT.parent
DEFAULT_SCHEMAS = CANDIDATE_ROOT / "schemas"
DEFAULT_VALIDATOR = PACKAGE_ROOT / "shared-core" / "scripts" / "validate_artifact.py"


class SchemaRuntimeError(RuntimeError):
    """Raised when a schema or the frozen shared validator cannot be loaded."""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_shared_validator(path: Path = DEFAULT_VALIDATOR) -> ModuleType:
    resolved = path.resolve()
    if not resolved.is_file():
        raise SchemaRuntimeError(f"shared validator not found: {resolved}")
    spec = importlib.util.spec_from_file_location("phase8a_shared_validator", resolved)
    if spec is None or spec.loader is None:
        raise SchemaRuntimeError(f"could not import shared validator: {resolved}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_document(
    value: Any,
    schema_filename: str,
    instance_path: str,
    *,
    schemas_dir: Path = DEFAULT_SCHEMAS,
    validator_path: Path = DEFAULT_VALIDATOR,
) -> list[dict[str, str]]:
    """Return stable schema-layer issues for one JSON-compatible document."""
    module = load_shared_validator(validator_path)
    schema_path = (schemas_dir / schema_filename).resolve()
    if not schema_path.is_file():
        raise SchemaRuntimeError(f"schema not found: {schema_path}")
    root = read_json(schema_path)
    store = module.SchemaStore()
    raw = module.validate_instance(value, root, schema_path, root, store, instance_path)
    return [
        {
            "layer": "schema",
            "path": issue.path,
            "code": f"schema:{issue.keyword}",
            "message": issue.message,
            "review_route": "deterministic",
        }
        for issue in raw
    ]
