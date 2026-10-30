#!/usr/bin/env python3
"""Dependency-free, fail-closed validator for the candidate schema subset."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


ANNOTATION_KEYWORDS = {"$schema", "$id", "$defs", "title", "description", "default", "examples"}
ASSERTION_KEYWORDS = {
    "$ref", "allOf", "oneOf", "type", "required", "properties", "additionalProperties", "items",
    "minItems", "maxItems", "uniqueItems", "enum", "const", "minLength", "maxLength",
    "pattern", "minimum", "maximum", "format", "x-source-locator-contract",
}


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    keyword: str
    message: str


class SchemaError(RuntimeError):
    """Raised when a schema cannot be enforced by this validator."""


class SchemaStore:
    def __init__(self) -> None:
        self.cache: dict[Path, Any] = {}

    def load(self, path: Path) -> Any:
        resolved = path.resolve()
        if resolved not in self.cache:
            self.cache[resolved] = json.loads(resolved.read_text(encoding="utf-8"))
        return self.cache[resolved]

    def resolve(self, ref: str, schema_path: Path, root: Any) -> tuple[Any, Path, Any]:
        file_part, marker, fragment = ref.partition("#")
        target_path = (schema_path.parent / file_part).resolve() if file_part else schema_path
        target_root = self.load(target_path) if file_part else root
        target = target_root
        if marker and fragment:
            if not fragment.startswith("/"):
                raise SchemaError(f"Unsupported JSON pointer: {ref}")
            for raw in fragment.lstrip("/").split("/"):
                token = raw.replace("~1", "/").replace("~0", "~")
                try:
                    target = target[token]
                except (KeyError, TypeError) as exc:
                    raise SchemaError(f"Unresolvable $ref: {ref}") from exc
        return target, target_path, target_root


def _matches_type(value: Any, expected: str) -> bool:
    checks = {
        "object": lambda: isinstance(value, dict),
        "array": lambda: isinstance(value, list),
        "string": lambda: isinstance(value, str),
        "integer": lambda: isinstance(value, int) and not isinstance(value, bool),
        "number": lambda: isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": lambda: isinstance(value, bool),
        "null": lambda: value is None,
    }
    if expected not in checks:
        raise SchemaError(f"Unsupported JSON type: {expected}")
    return checks[expected]()


def _valid_format(value: str, name: str) -> bool:
    try:
        if name == "date-time":
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return "T" in value
        if name == "date":
            date.fromisoformat(value)
            return True
    except ValueError:
        return False
    raise SchemaError(f"Unsupported format assertion: {name}")


def _issue(path: str, keyword: str, message: str) -> ValidationIssue:
    return ValidationIssue(path or "$", keyword, message)


def _validate_source_locator_contract(instance: Any, path: str) -> list[ValidationIssue]:
    """Enforce cross-field ordering and format-exclusive source-locator coordinates."""
    if not isinstance(instance, dict) or "locator_type" not in instance:
        return []
    common = {"locator_type", "span_kind", "source_span_sha256"}
    fields = {
        "line_char_range": {"start_line", "end_line", "start_char", "end_char"},
        "xml_path": {"xml_path"},
        "html_dom_path": {
            "dom_path", "source_anchor_order", "start_line", "end_line", "start_column", "end_column"
        },
        "pdf_page_line_range": {"page_start", "page_end", "extracted_start_line", "extracted_end_line"},
    }
    locator_type = instance.get("locator_type")
    if locator_type not in fields:
        return []
    issues: list[ValidationIssue] = []
    unexpected = set(instance) - common - fields[locator_type]
    if unexpected:
        issues.append(
            _issue(path, "x-source-locator-contract", f"Fields do not belong to {locator_type}: {sorted(unexpected)}")
        )

    def comparable_integers(*names: str) -> bool:
        return all(
            name in instance and isinstance(instance[name], int) and not isinstance(instance[name], bool)
            for name in names
        )

    if locator_type == "line_char_range":
        if comparable_integers("start_line", "end_line") and instance["start_line"] > instance["end_line"]:
            issues.append(_issue(path, "x-source-locator-contract", "start_line must not exceed end_line"))
        if comparable_integers("start_char", "end_char") and instance["start_char"] > instance["end_char"]:
            issues.append(_issue(path, "x-source-locator-contract", "start_char must not exceed end_char"))
    elif locator_type == "html_dom_path":
        if comparable_integers("start_line", "end_line", "start_column", "end_column"):
            start = (instance["start_line"], instance["start_column"])
            end = (instance["end_line"], instance["end_column"])
            if start > end:
                issues.append(_issue(path, "x-source-locator-contract", "HTML start position must not exceed end position"))
    elif locator_type == "pdf_page_line_range":
        if comparable_integers("page_start", "page_end") and instance["page_start"] > instance["page_end"]:
            issues.append(_issue(path, "x-source-locator-contract", "page_start must not exceed page_end"))
        if comparable_integers("extracted_start_line", "extracted_end_line") and instance["extracted_start_line"] > instance["extracted_end_line"]:
            issues.append(
                _issue(path, "x-source-locator-contract", "extracted_start_line must not exceed extracted_end_line")
            )
    return issues


def validate_instance(
    instance: Any,
    schema: Any,
    schema_path: Path,
    root: Any,
    store: SchemaStore,
    instance_path: str = "$",
) -> list[ValidationIssue]:
    if isinstance(schema, bool):
        return [] if schema else [_issue(instance_path, "falseSchema", "Schema rejects every value")]
    if not isinstance(schema, dict):
        raise SchemaError(f"Schema at {instance_path} is not an object or boolean")
    unknown = set(schema) - ANNOTATION_KEYWORDS - ASSERTION_KEYWORDS
    if unknown:
        raise SchemaError(f"Unsupported schema keyword(s) at {instance_path}: {sorted(unknown)}")

    issues: list[ValidationIssue] = []
    if "$ref" in schema:
        target, target_path, target_root = store.resolve(schema["$ref"], schema_path, root)
        issues.extend(validate_instance(instance, target, target_path, target_root, store, instance_path))
    for child in schema.get("allOf", []):
        issues.extend(validate_instance(instance, child, schema_path, root, store, instance_path))
    if "oneOf" in schema:
        branch_results = [
            validate_instance(instance, child, schema_path, root, store, instance_path)
            for child in schema["oneOf"]
        ]
        matching_count = sum(not branch_issues for branch_issues in branch_results)
        if matching_count != 1:
            issues.append(
                _issue(instance_path, "oneOf", f"Expected exactly one matching schema branch; got {matching_count}")
            )

    expected = schema.get("type")
    if expected is not None:
        options = expected if isinstance(expected, list) else [expected]
        if not any(_matches_type(instance, option) for option in options):
            issues.append(_issue(instance_path, "type", f"Expected {options}; got {type(instance).__name__}"))
            return issues

    if "enum" in schema and instance not in schema["enum"]:
        issues.append(_issue(instance_path, "enum", f"Value is not one of {schema['enum']}"))
    if "const" in schema and instance != schema["const"]:
        issues.append(_issue(instance_path, "const", f"Expected {schema['const']!r}"))

    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            issues.append(_issue(instance_path, "minLength", "String is too short"))
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            issues.append(_issue(instance_path, "maxLength", "String is too long"))
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            issues.append(_issue(instance_path, "pattern", f"String does not match {schema['pattern']}"))
        if "format" in schema and not _valid_format(instance, schema["format"]):
            issues.append(_issue(instance_path, "format", f"Invalid {schema['format']} value"))

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            issues.append(_issue(instance_path, "minimum", f"Value is below {schema['minimum']}"))
        if "maximum" in schema and instance > schema["maximum"]:
            issues.append(_issue(instance_path, "maximum", f"Value is above {schema['maximum']}"))

    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            issues.append(_issue(instance_path, "minItems", "Array has too few items"))
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            issues.append(_issue(instance_path, "maxItems", "Array has too many items"))
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True, ensure_ascii=False) for item in instance]
            if len(encoded) != len(set(encoded)):
                issues.append(_issue(instance_path, "uniqueItems", "Array items are not unique"))
        for index, item in enumerate(instance):
            if "items" in schema:
                issues.extend(validate_instance(item, schema["items"], schema_path, root, store, f"{instance_path}[{index}]"))

    if isinstance(instance, dict):
        if schema.get("x-source-locator-contract"):
            issues.extend(_validate_source_locator_contract(instance, instance_path))
        for key in schema.get("required", []):
            if key not in instance:
                issues.append(_issue(instance_path, "required", f"Missing required property: {key}"))
        properties = schema.get("properties", {})
        for key, value in instance.items():
            child_path = f"{instance_path}.{key}"
            if key in properties:
                issues.extend(validate_instance(value, properties[key], schema_path, root, store, child_path))
            elif schema.get("additionalProperties") is False:
                issues.append(_issue(child_path, "additionalProperties", "Property is not allowed"))
            elif isinstance(schema.get("additionalProperties"), dict):
                issues.extend(validate_instance(value, schema["additionalProperties"], schema_path, root, store, child_path))
    return issues


def validate_files(schema_path: Path, data_path: Path) -> list[ValidationIssue]:
    store = SchemaStore()
    schema = store.load(schema_path)
    instance = json.loads(data_path.resolve().read_text(encoding="utf-8"))
    return validate_instance(instance, schema, schema_path.resolve(), schema, store)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a biomedical-writing JSON artifact.")
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        issues = validate_files(args.schema, args.data)
    except (OSError, json.JSONDecodeError, SchemaError) as exc:
        print(f"validator error: {exc}", file=sys.stderr)
        return 2
    report = {"valid": not issues, "schema": str(args.schema.resolve()), "data": str(args.data.resolve()), "issues": [asdict(item) for item in issues]}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if issues:
        for item in issues:
            print(f"{item.path} [{item.keyword}] {item.message}")
        return 1
    print(f"VALID: {args.data}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
