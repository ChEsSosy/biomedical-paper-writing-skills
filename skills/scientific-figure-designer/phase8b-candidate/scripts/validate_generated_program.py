#!/usr/bin/env python3
"""Exact-generator and AST-whitelist validator for restricted Python output."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

from generate_restricted_python import generate_program_text
from phase8b_runtime import file_sha256, read_json


ALLOWED_IMPORTS = {"csv", "hashlib", "json", "pathlib", "PIL", "xml"}
PROHIBITED_NAMES = {
    "eval", "exec", "compile", "__import__", "getattr", "setattr", "delattr", "globals", "locals",
    "subprocess", "socket", "requests", "urllib", "pip", "conda", "os", "sys", "shutil", "tempfile",
}
ALLOWED_NODES = {
    ast.Module, ast.Expr, ast.Import, ast.ImportFrom, ast.alias, ast.Assign, ast.AnnAssign,
    ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.Raise, ast.If, ast.For, ast.With,
    ast.withitem, ast.Call, ast.Name, ast.Load, ast.Store, ast.Constant, ast.Dict, ast.List,
    ast.Tuple, ast.Set, ast.Subscript, ast.Slice, ast.Attribute, ast.BinOp, ast.UnaryOp,
    ast.BoolOp, ast.Compare, ast.ListComp, ast.comprehension, ast.JoinedStr, ast.FormattedValue,
    ast.keyword, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Pow, ast.USub, ast.Not,
    ast.And, ast.Or, ast.Eq, ast.NotEq,
    ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Is, ast.IsNot, ast.IfExp,
    ast.Lambda,
}


def validate_program(plan: dict[str, Any], program_path: Path, expected_sha256: str | None = None) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    try:
        source = program_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(program_path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        return [{"layer": "deterministic", "path": "$.program", "code": "code:syntax", "message": str(exc), "review_route": "deterministic", "severity": "error"}]
    try:
        expected = generate_program_text(plan)
    except Exception as exc:
        return [{"layer": "deterministic", "path": "$.plan", "code": "code:plan_generation_failed", "message": str(exc), "review_route": "deterministic", "severity": "error"}]
    if source != expected:
        issues.append({"layer": "deterministic", "path": "$.program", "code": "code:not_exact_generator_output", "message": "program bytes differ from the declared generator output for the exact plan", "review_route": "deterministic", "severity": "error"})
    actual_hash = file_sha256(program_path)
    if expected_sha256 is not None and actual_hash != expected_sha256:
        issues.append({"layer": "deterministic", "path": "$.program.sha256", "code": "code:program_hash", "message": "generated program hash mismatch", "review_route": "deterministic", "severity": "error"})
    for node in ast.walk(tree):
        if type(node) not in ALLOWED_NODES:
            issues.append({"layer": "deterministic", "path": f"$.program.ast.{type(node).__name__}", "code": "code:ast_node_not_allowlisted", "message": f"AST node is not allowlisted: {type(node).__name__}", "review_route": "deterministic", "severity": "error"})
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".", 1)[0] not in ALLOWED_IMPORTS:
                    issues.append({"layer": "deterministic", "path": "$.program.ast.Import", "code": "code:import_not_allowlisted", "message": f"import is not allowlisted: {alias.name}", "review_route": "deterministic", "severity": "error"})
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".", 1)[0] not in ALLOWED_IMPORTS:
            issues.append({"layer": "deterministic", "path": "$.program.ast.ImportFrom", "code": "code:import_not_allowlisted", "message": f"import is not allowlisted: {node.module}", "review_route": "deterministic", "severity": "error"})
        if isinstance(node, ast.Name) and node.id in PROHIBITED_NAMES:
            issues.append({"layer": "deterministic", "path": "$.program.ast.Name", "code": "code:prohibited_name", "message": f"prohibited name: {node.id}", "review_route": "deterministic", "severity": "error"})
        if isinstance(node, ast.Attribute) and (node.attr.startswith("__") or node.attr in PROHIBITED_NAMES):
            issues.append({"layer": "deterministic", "path": "$.program.ast.Attribute", "code": "code:reflection_or_prohibited_attribute", "message": f"prohibited attribute: {node.attr}", "review_route": "deterministic", "severity": "error"})
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in issues:
        key = (item["code"], item["path"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("program", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    issues = validate_program(read_json(args.plan), args.program, args.expected_sha256)
    print(json.dumps({"valid": not issues, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
