#!/usr/bin/env python3
"""Thin loader for the frozen Phase 3.1 dependency-free schema validator."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


DEFAULT_VALIDATOR = (
    Path(__file__).resolve().parents[3]
    / "01_style-and-structure-distiller"
    / "shared-core"
    / "scripts"
    / "validate_artifact.py"
)


class ValidatorLoadError(RuntimeError):
    """Raised when the authoritative local validator cannot be loaded."""


def load_validator(path: Path | None = None) -> ModuleType:
    validator_path = (path or DEFAULT_VALIDATOR).resolve()
    if not validator_path.is_file():
        raise ValidatorLoadError(f"Validator not found: {validator_path}")
    spec = importlib.util.spec_from_file_location("phase3_1_validate_artifact", validator_path)
    if spec is None or spec.loader is None:
        raise ValidatorLoadError(f"Could not load validator: {validator_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_file(schema_path: Path, data_path: Path, validator_path: Path | None = None) -> list[dict[str, Any]]:
    module = load_validator(validator_path)
    return [
        {"path": issue.path, "keyword": issue.keyword, "message": issue.message}
        for issue in module.validate_files(schema_path.resolve(), data_path.resolve())
    ]
