#!/usr/bin/env python3
"""CLI/orchestrator for Phase 3.1 observable structure and statistics."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from aggregation import (
    make_corpus_balance,
    make_document_record,
    make_figure_reference_map,
    make_section_map,
    make_structure_profile,
    make_style_profile,
)
from confidence_qc import audit_prohibited_content
from features import extract_figure_references
from manifest import (
    ARTICLE_TYPES,
    build_draft_manifest,
    enforce_manifest_governance,
    load_shared_validator,
    resolve_source_path,
    sha256_file,
    source_type_from_suffix,
    validate_payload_file,
    warning,
    write_json_new,
)
from parsers import parse_document


def command_init_manifest(args: argparse.Namespace) -> int:
    input_dir = args.input_dir.resolve()
    if not input_dir.is_dir():
        raise RuntimeError(f"Input directory does not exist: {input_dir}")
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError(f"Refusing to overwrite existing manifest: {output}")
    payload = build_draft_manifest(
        input_dir,
        args.article_type,
        args.corpus_id,
        args.minimum_document_count,
        output.parent,
    )
    write_json_new(output, payload)
    print(f"DRAFT MANIFEST: {output}")
    print("Author review is required; the draft is intentionally not schema-valid yet.")
    return 0


def command_run(args: argparse.Namespace) -> int:
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    skill_root = Path(__file__).resolve().parents[1]
    candidate_root = skill_root
    validator = load_shared_validator(candidate_root)
    manifest_issues = validator.validate_files(skill_root / "schemas" / "corpus-manifest.schema.json", manifest_path)
    if manifest_issues:
        summary = "; ".join(f"{item.path} [{item.keyword}] {item.message}" for item in manifest_issues[:12])
        raise RuntimeError(f"Manifest validation failed: {summary}")
    draft = getattr(args, "draft", False)
    included, excluded_count = enforce_manifest_governance(manifest, draft=draft)

    parsed = []
    failures: list[dict[str, str]] = []
    for record in included:
        source_path = resolve_source_path(manifest_path, record)
        try:
            if not source_path.is_file():
                raise RuntimeError(f"Source file does not exist: {source_path}")
            actual_source_type = source_type_from_suffix(source_path)
            if actual_source_type != record["source_type"]:
                raise RuntimeError(
                    f"Approved source_type '{record['source_type']}' does not match file suffix-derived type '{actual_source_type}'"
                )
            actual_hash = sha256_file(source_path)
            expected_hash = record.get("expected_sha256")
            if expected_hash and actual_hash.lower() != expected_hash.lower():
                raise RuntimeError("Source SHA-256 does not match the approved manifest")
            parsed.append(parse_document(source_path, record["document_id"], record["article_type"]))
        except (OSError, ET.ParseError, RuntimeError, subprocess.SubprocessError) as exc:
            failures.append({"document_id": record["document_id"], "error": str(exc)})
    if not parsed:
        raise RuntimeError(f"All included documents failed parsing: {failures}")

    hashes: dict[str, list[str]] = defaultdict(list)
    for document in parsed:
        hashes[document.source_sha256].append(document.document_id)
    duplicates = {digest: ids for digest, ids in hashes.items() if len(ids) > 1}
    if duplicates:
        raise RuntimeError(f"Duplicate included source documents detected by SHA-256: {duplicates}")

    run_warnings: list[dict[str, str]] = []
    if draft:
        run_warnings.append(warning("draft_corpus_not_approved", "Diagnostic extraction from an unapproved projection; author review is required before downstream use."))
    if len(parsed) < manifest["minimum_document_count"]:
        run_warnings.append(
            warning(
                "low_sample_size",
                f"Only {len(parsed)} documents were profiled; configured minimum is {manifest['minimum_document_count']}",
            )
        )
    if failures:
        run_warnings.append(warning("document_parse_failures", f"{len(failures)} included document(s) failed", "error"))

    out_dir = args.out_dir.resolve()
    if out_dir.exists() and any(out_dir.iterdir()):
        raise RuntimeError(f"Refusing to write into non-empty output directory: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    figure_references_by_document = {
        document.document_id: extract_figure_references(document) for document in parsed
    }
    artifact_payloads: list[tuple[str, Path, dict]] = []
    documents_dir = out_dir / "documents"
    for document in parsed:
        references = figure_references_by_document[document.document_id]
        artifacts = [
            (
                "document-record.schema.json",
                documents_dir / f"{document.document_id}.document-record.json",
                make_document_record(document, manifest, references),
            ),
            (
                "section-map.schema.json",
                documents_dir / f"{document.document_id}.section-map.json",
                make_section_map(document, manifest),
            ),
            (
                "figure-reference-map.schema.json",
                documents_dir / f"{document.document_id}.figure-reference-map.json",
                make_figure_reference_map(document, manifest, references),
            ),
        ]
        artifact_payloads.extend(artifacts)

    style_profile = make_style_profile(parsed, manifest, run_warnings)
    corpus_artifacts: list[tuple[str, Path, dict]] = [
        ("style-profile.schema.json", out_dir / "style-profile.json", style_profile),
        (
            "structure-profile.schema.json",
            out_dir / "structure-profile.json",
            make_structure_profile(parsed, manifest, figure_references_by_document, run_warnings),
        ),
        ("corpus-balance.schema.json", out_dir / "corpus-balance.json", make_corpus_balance(parsed, manifest, run_warnings)),
    ]
    artifact_payloads.extend(corpus_artifacts)
    if draft:
        for _, _, payload in artifact_payloads:
            if not any(w["code"] == "draft_corpus_not_approved" for w in payload["warnings"]):
                payload["warnings"].append(warning("draft_corpus_not_approved", "Draft diagnostic corpus; not approved for downstream use."))
    style_profile["prohibited_content_audit"] = audit_prohibited_content(
        [payload for _, _, payload in artifact_payloads]
    )

    generated: list[tuple[Path, Path]] = []
    for schema_name, output_path, payload in artifact_payloads:
        write_json_new(output_path, payload)
        generated.append((skill_root / "schemas" / schema_name, output_path))
    for schema_path, data_path in generated:
        validate_payload_file(validator, schema_path, data_path)

    summary_lines = [
        "# Phase 3.1 Distillation Run Summary",
        "",
        f"- Corpus ID: `{manifest['corpus_id']}`",
        f"- Corpus type: `{manifest['corpus_type']}`",
        f"- Included and parsed: {len(parsed)}",
        f"- Excluded by manifest: {excluded_count}",
        f"- Parse failures: {len(failures)}",
        f"- Run mode: {'draft diagnostic; corpus not approved' if draft else 'approved corpus'}",
        "- Artifact status: `author_review_required`",
        "- Semantic role classification: `not performed`",
        "",
        "## Generated artifacts",
        "",
        "- `style-profile.json`",
        "- `structure-profile.json`",
        "- `corpus-balance.json`",
        "- `documents/*.document-record.json`",
        "- `documents/*.section-map.json`",
        "- `documents/*.figure-reference-map.json`",
    ]
    if failures:
        summary_lines.extend(["", "## Parse failures", ""])
        summary_lines.extend(f"- `{item['document_id']}`: {item['error']}" for item in failures)
    summary_path = out_dir / "run-summary.md"
    if summary_path.exists():
        raise RuntimeError(f"Refusing to overwrite existing output: {summary_path}")
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(f"STYLE: {out_dir / 'style-profile.json'}")
    print(f"STRUCTURE: {out_dir / 'structure-profile.json'}")
    print(f"BALANCE: {out_dir / 'corpus-balance.json'}")
    print(f"SUMMARY: {summary_path}")
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract observable biomedical corpus structure and statistics.")
    commands = parser.add_subparsers(dest="command", required=True)
    init_parser = commands.add_parser("init-manifest", help="Create an intentionally incomplete draft manifest")
    init_parser.add_argument("--input-dir", type=Path, required=True)
    init_parser.add_argument("--article-type", choices=sorted(ARTICLE_TYPES), required=True)
    init_parser.add_argument("--corpus-id", required=True)
    init_parser.add_argument("--minimum-document-count", type=int, default=5)
    init_parser.add_argument("--output", type=Path, required=True)
    init_parser.set_defaults(func=command_init_manifest)
    run_parser = commands.add_parser("run", help="Validate and distill an author-approved manifest")
    run_parser.add_argument("--manifest", type=Path, required=True)
    run_parser.add_argument("--out-dir", type=Path, required=True)
    run_parser.add_argument("--draft", action="store_true", help="Diagnose a schema-valid author_review_required manifest without granting approval")
    run_parser.set_defaults(func=command_run)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (OSError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"distiller error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
