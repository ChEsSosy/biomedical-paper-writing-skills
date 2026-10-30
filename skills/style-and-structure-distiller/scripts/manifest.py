"""Manifest, provenance, artifact-envelope, and fail-closed I/O helpers."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKILL_VERSION = "0.2.9-bounded-markdown-projection"
SCHEMA_VERSION = "0.2.2"
SUPPORTED_SUFFIXES = {".txt", ".md", ".xml", ".nxml", ".html", ".htm", ".pdf"}
ARTICLE_TYPES = {"original_article", "review_article"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_identifier(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip()).strip("-._")
    return cleaned.lower() or "document"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def warning(code: str, message: str, severity: str = "warning", locator: str = "") -> dict[str, str]:
    item = {"code": code, "message": message, "severity": severity}
    if locator:
        item["locator"] = locator
    return item


def envelope(
    schema_name: str,
    artifact_id: str,
    source_artifact_ids: list[str],
    source_files: list[dict[str, str]],
    warnings: list[dict[str, str]],
    status: str = "author_review_required",
) -> dict[str, Any]:
    return {
        "schema_name": schema_name,
        "schema_version": SCHEMA_VERSION,
        "artifact_id": artifact_id,
        "created_at": now_iso(),
        "created_by": f"style-and-structure-distiller/{SKILL_VERSION}",
        "source_artifact_ids": source_artifact_ids,
        "source_files": source_files,
        "status": status,
        "warnings": warnings,
    }


def source_type_from_suffix(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return "markdown"
    if suffix == ".txt":
        return "plain_text"
    if suffix in {".xml", ".nxml"}:
        return "jats_xml"
    if suffix in {".html", ".htm"}:
        return "html"
    if suffix == ".pdf":
        return "pdf"
    raise RuntimeError(f"Unsupported input suffix: {suffix}")


def source_file_record(document: Any, access_status: str) -> dict[str, str]:
    return {
        "path": str(document.source_path),
        "role": "corpus_document",
        "document_id": document.document_id,
        "sha256": document.source_sha256,
        "access_status": access_status,
    }


def manifest_document(manifest: dict[str, Any], document_id: str) -> dict[str, Any]:
    try:
        return next(item for item in manifest["documents"] if item["document_id"] == document_id)
    except StopIteration as exc:
        raise RuntimeError(f"Manifest has no document record for {document_id}") from exc


def resolve_source_path(manifest_path: Path, record: dict[str, Any]) -> Path:
    source = Path(record["source_file"])
    return source.resolve() if source.is_absolute() else (manifest_path.parent / source).resolve()


def build_draft_manifest(
    input_dir: Path,
    article_type: str,
    corpus_id: str,
    minimum_document_count: int,
    output_parent: Path,
) -> dict[str, Any]:
    if article_type not in ARTICLE_TYPES:
        raise RuntimeError(f"Unsupported article type: {article_type}")
    if minimum_document_count < 2:
        raise RuntimeError("minimum-document-count must be at least 2")
    files = sorted(
        path for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    if not files:
        raise RuntimeError(f"No supported files found under {input_dir}")

    seen: set[str] = set()
    documents: list[dict[str, Any]] = []
    source_files: list[dict[str, str]] = []
    for path in files:
        digest = sha256_file(path)
        base_id = safe_identifier(path.stem)
        document_id = base_id if base_id not in seen else f"{base_id}-{digest[:8]}"
        seen.add(document_id)
        resolved = path.resolve()
        relative = resolved.relative_to(output_parent.resolve()) if resolved.is_relative_to(output_parent.resolve()) else resolved
        documents.append(
            {
                "document_id": document_id,
                "source_file": str(relative),
                "article_type": article_type,
                "title": "",
                "journal": "",
                "year": None,
                "domains": [],
                "experiment_labels": [],
                "access_status": "REVIEW_REQUIRED",
                "license_note": "",
                "inclusion_status": "REVIEW_REQUIRED",
                "metadata_provenance": "init-manifest inventory; author review required",
                "source_type": source_type_from_suffix(path),
                "expected_sha256": digest,
            }
        )
        source_files.append(
            {
                "path": str(resolved),
                "role": "corpus_document",
                "document_id": document_id,
                "sha256": digest,
                "access_status": "unknown",
            }
        )

    payload = envelope(
        "corpus_manifest",
        f"corpus-manifest:{safe_identifier(corpus_id)}",
        [],
        source_files,
        [warning("manifest_incomplete", "Review metadata, access, grouping, and inclusion fields before extraction", "blocker")],
        status="author_review_required",
    )
    payload.update(
        {
            "corpus_id": safe_identifier(corpus_id),
            "corpus_type": article_type,
            "minimum_document_count": minimum_document_count,
            "inclusion_criteria": ["REVIEW_REQUIRED: define corpus inclusion criteria"],
            "exclusion_criteria": ["REVIEW_REQUIRED: define corpus exclusion criteria"],
            "documents": documents,
        }
    )
    return payload


def enforce_manifest_governance(manifest: dict[str, Any], *, draft: bool = False) -> tuple[list[dict[str, Any]], int]:
    if draft and manifest["status"] != "author_review_required":
        raise RuntimeError("Draft extraction requires manifest status author_review_required")
    if not draft and manifest["status"] != "author_approved":
        raise RuntimeError("Manifest status must be author_approved before extraction")
    ids = [item["document_id"] for item in manifest["documents"]]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Manifest contains duplicate document_id values")
    if any(item["article_type"] != manifest["corpus_type"] for item in manifest["documents"]):
        raise RuntimeError("Mixed Original Article and Review records are not allowed")
    excluded_without_reason = [
        item["document_id"] for item in manifest["documents"]
        if item["inclusion_status"] == "excluded" and not item.get("exclusion_reason", "").strip()
    ]
    if excluded_without_reason:
        raise RuntimeError(f"Excluded documents require exclusion_reason: {excluded_without_reason}")
    included = [item for item in manifest["documents"] if item["inclusion_status"] == "included"]
    if not included:
        raise RuntimeError("Manifest has no included documents")
    return included, len(manifest["documents"]) - len(included)


def load_shared_validator(candidate_root: Path):
    path = candidate_root / "shared-core" / "scripts" / "validate_artifact.py"
    spec = importlib.util.spec_from_file_location("phase31_shared_validator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load shared validator: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_payload_file(validator: Any, schema_path: Path, data_path: Path) -> None:
    issues = validator.validate_files(schema_path, data_path)
    if issues:
        summary = "; ".join(f"{item.path} [{item.keyword}] {item.message}" for item in issues[:12])
        raise RuntimeError(f"Generated artifact failed schema validation: {data_path}: {summary}")


def write_json_new(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
