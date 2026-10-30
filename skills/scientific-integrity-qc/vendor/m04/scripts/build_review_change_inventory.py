#!/usr/bin/env python3
"""Build deterministic Review structural, lineage, and protected-change evidence.

This module never judges scientific correctness.  It validates a structured
Review locator map, derives observable structure from exact source/candidate
bytes, and inventories protected lexical tokens for later fail-closed gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable


DOCUMENT_SIDES = {"source", "candidate"}
SUPPORTED_REVIEW_TYPES = {"narrative_review", "mini_review"}
TRUSTED_LINEAGE_ORIGINS = {"deterministic_patch_layer", "author_supplied", "reviewed_upstream_locator_map"}
ALL_LINEAGE_ORIGINS = TRUSTED_LINEAGE_ORIGINS | {"model_declared"}
PROTECTED_CLASSES = {
    "citation", "numeric", "statistic", "unit", "terminology",
    "figure_table_reference", "negation", "comparison_direction",
    "causal_mechanistic", "certainty_hedging", "consensus_conflict",
}

NUMERIC_BRACKET_CITATION_RE = re.compile(r"\[(?:\s*\d+\s*)(?:[,;\-–]\s*\d+\s*)*\]")
# Citation identity is normalized into typed anchors before comparison.  These
# deliberately bounded patterns cover the three frozen interface families:
# numeric brackets, author-year citations, and superscript/structured markers.
_SIMPLE_SURNAME = r"[^\W\d_][\w'’.-]*"
_SURNAME_PARTICLE = r"(?:(?:de|del|da|di|du|van|von)(?:\s+der)?\s+)?"
_SURNAME = rf"{_SURNAME_PARTICLE}{_SIMPLE_SURNAME}"
_AUTHOR = rf"(?:{_SURNAME}\s+(?:&|and)\s+{_SURNAME}|{_SURNAME}\s+et\s+al\.?|{_SURNAME})"
_AUTHOR_YEAR_ITEM = rf"{_AUTHOR}\s*,?\s*(?:19|20)\d{{2}}[a-z]?"
AUTHOR_YEAR_PAREN_CITATION_RE = re.compile(
    rf"\((?:{_AUTHOR_YEAR_ITEM})(?:\s*;\s*{_AUTHOR_YEAR_ITEM})*\)",
    re.UNICODE | re.IGNORECASE,
)
AUTHOR_YEAR_NARRATIVE_CITATION_RE = re.compile(
    rf"\b{_AUTHOR}\s*\(\s*(?:19|20)\d{{2}}[a-z]?\s*\)",
    re.UNICODE | re.IGNORECASE,
)
# These deliberately broader sentinels do not create citation identities. They
# identify author-year-like syntax that the bounded parser could not resolve,
# so validation can fail closed instead of silently treating it as prose.
AUTHOR_YEAR_PAREN_LIKE_RE = re.compile(
    rf"\(\s*(?={_AUTHOR}\s*,)(?=[^()\n]{{1,240}},\s*(?:19|20)\d{{2}})[^()\n]{{1,240}}\)",
    re.UNICODE | re.IGNORECASE,
)
AUTHOR_YEAR_NARRATIVE_LIKE_RE = re.compile(
    rf"\b{_AUTHOR}\s*\(\s*(?:19|20)\d{{2}}[a-z]?[^()\n]*\)",
    re.UNICODE | re.IGNORECASE,
)
AUTHOR_YEAR_MULTI_AUTHOR_LIKE_RE = re.compile(
    rf"\b{_SURNAME}(?:(?:\s*,\s*(?:and\s+)?|\s+(?:&|and)\s+){_SURNAME}){{2,}}"
    rf"\s*\(\s*(?:19|20)\d{{2}}[a-z]?\s*\)",
    re.UNICODE | re.IGNORECASE,
)
HTML_SUPERSCRIPT_CITATION_RE = re.compile(
    r"<sup>\s*\d+(?:\s*[,;\-–]\s*\d+)*\s*</sup>",
    re.IGNORECASE,
)
UNICODE_SUPERSCRIPT_CITATION_RE = re.compile(
    r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+(?:\s*[,\-–]\s*[⁰¹²³⁴⁵⁶⁷⁸⁹]+)*"
)
CARET_SUPERSCRIPT_CITATION_RE = re.compile(
    r"\^(?:\s*\d+\s*)(?:[,;\-–]\s*\d+\s*)*\^"
)
FIGURE_TABLE_RE = re.compile(
    r"\b(?:(?:Extended\s+Data|Supplementary)\s+)?(?:Fig(?:ure)?|Table)s?\.?\s*\d+[A-Za-z]?(?:\s*[,–-]\s*[A-Za-z0-9]+)*",
    re.IGNORECASE,
)
UNIT_RE = re.compile(
    r"(?<![\w.])(?:\d+(?:\.\d+)?|\.\d+)\s*(?:%|mg/kg|µg/kg|ug/kg|mg|µg|ug|ng|g|kg|mL|ml|µL|uL|L|mm|cm|µm|um|nm|h|min|s|°C)\b",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"(?<![\w.])(?:\d+(?:\.\d+)?|\.\d+)(?:%|\b)")
STATISTIC_RE = re.compile(
    r"\b(?:p\s*[<=>]\s*(?:\d+(?:\.\d+)?|\.\d+)|(?:OR|HR|RR|CI)\s*[=:]?\s*(?:\d+(?:\.\d+)?|\.\d+))",
    re.IGNORECASE,
)
LEXICAL_PATTERNS = {
    "negation": re.compile(r"\b(?:no|not|none|neither|without|lack(?:s|ed|ing)?)\b", re.IGNORECASE),
    "comparison_direction": re.compile(r"\b(?:increase(?:s|d)?|decrease(?:s|d)?|higher|lower|greater|less|worse|better)\b", re.IGNORECASE),
    "causal_mechanistic": re.compile(r"\b(?:cause(?:s|d)?|drive(?:s|n)?|lead(?:s|ing)?\s+to|mediate(?:s|d)?|mechanism)\b", re.IGNORECASE),
    "certainty_hedging": re.compile(r"\b(?:may|might|could|possibly|suggest(?:s|ed)?|associate(?:s|d)?|appears?)\b", re.IGNORECASE),
    "consensus_conflict": re.compile(r"\b(?:consensus|agreement|consistent|conflict(?:s|ing)?|contradict(?:s|ed|ory)?|disagreement|heterogeneous)\b", re.IGNORECASE),
}
LEXICAL_TOKEN_RE = re.compile(r"[^\W_]+(?:['’.-][^\W_]+)*", re.UNICODE)


class InventoryError(RuntimeError):
    """Raised when exact deterministic inventory cannot be constructed."""


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def payload_sha256(value: dict[str, Any], hash_field: str) -> str:
    return canonical_sha256({key: item for key, item in value.items() if key != hash_field})


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise InventoryError(f"expected a JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def document_payload(document: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if key != "artifact_sha256"}


def document_sha256(document: dict[str, Any]) -> str:
    return canonical_sha256(document_payload(document))


def artifact_identity(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "manuscript_id": document.get("manuscript_id"),
        "artifact_id": document.get("artifact_id"),
        "artifact_version": document.get("artifact_version"),
        "artifact_sha256": document.get("artifact_sha256"),
    }


def _is_identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _duplicates(values: Iterable[str]) -> set[str]:
    counts = Counter(values)
    return {value for value, count in counts.items() if count > 1}


def _validate_id_array(value: Any, path: str, issues: list[str], *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or not all(_is_identifier(item) for item in value):
        issues.append(f"{path} must be an identifier array")
        return []
    if not allow_empty and not value:
        issues.append(f"{path} must not be empty")
    duplicates = _duplicates(value)
    if duplicates:
        issues.append(f"{path} contains duplicate identifiers: {sorted(duplicates)}")
    return list(value)


def _expected_locator(document: dict[str, Any], unit_id: str, text: str) -> dict[str, Any]:
    return {
        "locator_type": "structured_unit",
        "side": document["side"],
        "artifact_id": document["artifact_id"],
        "unit_id": unit_id,
        "span_sha256": text_sha256(text),
    }


def validate_document(document: dict[str, Any], expected_side: str | None = None) -> list[str]:
    """Validate the exact normalized Review unit map used by Phase 7B."""
    issues: list[str] = []
    required = {
        "schema_name", "schema_version", "artifact_id", "artifact_version",
        "artifact_sha256", "manuscript_id", "document_type", "review_type",
        "side", "units", "authorized_empty_draft_slots", "protected_terms",
    }
    missing = sorted(required - set(document))
    if missing:
        return [f"document missing required fields: {missing}"]
    if document.get("schema_name") != "review_revision_document" or document.get("schema_version") != "0.1.0":
        issues.append("document schema identity must be review_revision_document 0.1.0")
    if document.get("document_type") != "review_article":
        issues.append("document_type must be review_article")
    if document.get("review_type") not in SUPPORTED_REVIEW_TYPES:
        issues.append("review_type must be narrative_review or mini_review")
    side = document.get("side")
    if side not in DOCUMENT_SIDES:
        issues.append("side must be source or candidate")
    if expected_side is not None and side != expected_side:
        issues.append(f"expected side {expected_side}; got {side}")
    for field in ("artifact_id", "artifact_version", "artifact_sha256", "manuscript_id"):
        if not _is_identifier(document.get(field)):
            issues.append(f"document {field} must be a non-empty string")
    if isinstance(document.get("artifact_sha256"), str) and document["artifact_sha256"] != document_sha256(document):
        issues.append("artifact_sha256 does not match the canonical document payload")

    protected_terms = document.get("protected_terms")
    if not isinstance(protected_terms, list) or not all(_is_identifier(term) for term in protected_terms):
        issues.append("protected_terms must be an array of non-empty exact terms")
    elif _duplicates(protected_terms):
        issues.append("protected_terms must not contain duplicates")

    slots = document.get("authorized_empty_draft_slots")
    slot_ids: set[str] = set()
    if not isinstance(slots, list):
        issues.append("authorized_empty_draft_slots must be an array")
        slots = []
    for index, slot in enumerate(slots):
        path = f"authorized_empty_draft_slots[{index}]"
        if not isinstance(slot, dict):
            issues.append(f"{path} must be an object")
            continue
        required_slot = {"slot_id", "slot_version", "placeholder_token", "placeholder_sha256", "outline_paragraph_id", "section_id", "locator"}
        if set(slot) != required_slot:
            issues.append(f"{path} fields must equal {sorted(required_slot)}")
            continue
        slot_id = slot.get("slot_id")
        if not _is_identifier(slot_id) or slot_id in slot_ids:
            issues.append(f"{path}.slot_id must be unique and non-empty")
            continue
        slot_ids.add(slot_id)
        expected_token = f"[[AUTHORIZED_DRAFT_SLOT:{slot_id}]]"
        if slot.get("placeholder_token") != expected_token:
            issues.append(f"{path}.placeholder_token must be the exact slot token")
        if slot.get("placeholder_sha256") != text_sha256(expected_token):
            issues.append(f"{path}.placeholder_sha256 mismatch")
        if not all(_is_identifier(slot.get(field)) for field in ("slot_version", "outline_paragraph_id", "section_id")):
            issues.append(f"{path} identity fields must be non-empty")
        locator = slot.get("locator")
        expected = {
            "locator_type": "authorized_empty_draft_slot",
            "side": "source",
            "artifact_id": document.get("artifact_id") if side == "source" else locator.get("artifact_id") if isinstance(locator, dict) else None,
            "unit_id": slot_id,
            "span_sha256": text_sha256(expected_token),
        }
        if locator != expected:
            issues.append(f"{path}.locator does not bind the exact source slot")
        if side == "candidate" and (not isinstance(locator, dict) or not _is_identifier(locator.get("artifact_id"))):
            issues.append(f"{path}.locator must retain a non-empty source artifact ID")
    if side == "candidate" and slots:
        # Candidate keeps the exact source slot registry for lineage, never a relabelled candidate slot.
        for index, slot in enumerate(slots):
            if isinstance(slot, dict) and slot.get("locator", {}).get("side") != "source":
                issues.append(f"authorized_empty_draft_slots[{index}] locator must remain source-bound")

    units = document.get("units")
    if not isinstance(units, list) or not units:
        issues.append("units must be a non-empty array")
        return issues
    unit_ids: set[str] = set()
    sentence_ids: set[str] = set()
    ordinals: list[int] = []
    required_closure = (
        "claim_ids", "citation_relation_ids", "source_ids", "extraction_record_ids",
        "conflict_ids", "limitation_ids", "gap_ids", "author_position_ids",
        "future_direction_ids",
    )
    for index, unit in enumerate(units):
        path = f"units[{index}]"
        if not isinstance(unit, dict):
            issues.append(f"{path} must be an object")
            continue
        required_unit = {
            "unit_id", "source_unit_ids", "authorized_draft_slot_ids", "ordinal",
            "section_id", "section_ordinal", "paragraph_plan_id", "text", "locator",
            "sentences", *required_closure,
        }
        missing_unit = sorted(required_unit - set(unit))
        if missing_unit:
            issues.append(f"{path} missing required fields: {missing_unit}")
            continue
        unit_id = unit.get("unit_id")
        if not _is_identifier(unit_id) or unit_id in unit_ids:
            issues.append(f"{path}.unit_id must be unique and non-empty")
        else:
            unit_ids.add(unit_id)
        ordinal = unit.get("ordinal")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 1:
            issues.append(f"{path}.ordinal must be a positive integer")
        else:
            ordinals.append(ordinal)
        if not isinstance(unit.get("section_ordinal"), int) or isinstance(unit.get("section_ordinal"), bool) or unit["section_ordinal"] < 1:
            issues.append(f"{path}.section_ordinal must be a positive integer")
        if not all(_is_identifier(unit.get(field)) for field in ("section_id", "paragraph_plan_id")):
            issues.append(f"{path} section/paragraph-plan IDs must be non-empty")
        source_ids = _validate_id_array(unit.get("source_unit_ids"), f"{path}.source_unit_ids", issues)
        draft_ids = _validate_id_array(unit.get("authorized_draft_slot_ids"), f"{path}.authorized_draft_slot_ids", issues)
        if side == "source":
            if source_ids != [unit_id] or draft_ids:
                issues.append(f"{path} source provenance must bind only itself")
        elif side == "candidate":
            if bool(source_ids) == bool(draft_ids):
                issues.append(f"{path} candidate provenance must use source units xor one authorized draft slot")
            if draft_ids and (len(draft_ids) != 1 or draft_ids[0] not in slot_ids):
                issues.append(f"{path} candidate draft-slot provenance is invalid")
        for field in required_closure:
            _validate_id_array(unit.get(field), f"{path}.{field}", issues)
        text = unit.get("text")
        if not isinstance(text, str):
            issues.append(f"{path}.text must be a string")
            text = ""
        if unit.get("locator") != _expected_locator(document, unit_id, text):
            issues.append(f"{path}.locator does not bind exact unit text and identity")
        sentences = unit.get("sentences")
        if not isinstance(sentences, list) or not sentences:
            issues.append(f"{path}.sentences must be a non-empty array")
            continue
        sentence_ordinals: list[int] = []
        combined: list[str] = []
        for sentence_index, sentence in enumerate(sentences):
            sentence_path = f"{path}.sentences[{sentence_index}]"
            if not isinstance(sentence, dict):
                issues.append(f"{sentence_path} must be an object")
                continue
            required_sentence = {
                "sentence_id", "source_sentence_ids", "authorized_draft_slot_ids",
                "ordinal", "text", "claim_ids", "citation_relation_ids",
            }
            if set(sentence) != required_sentence:
                issues.append(f"{sentence_path} fields must equal {sorted(required_sentence)}")
                continue
            sentence_id = sentence.get("sentence_id")
            if not _is_identifier(sentence_id) or sentence_id in sentence_ids:
                issues.append(f"{sentence_path}.sentence_id must be unique and non-empty")
            else:
                sentence_ids.add(sentence_id)
            sentence_ordinal = sentence.get("ordinal")
            if not isinstance(sentence_ordinal, int) or isinstance(sentence_ordinal, bool) or sentence_ordinal < 1:
                issues.append(f"{sentence_path}.ordinal must be a positive integer")
            else:
                sentence_ordinals.append(sentence_ordinal)
            sentence_sources = _validate_id_array(sentence.get("source_sentence_ids"), f"{sentence_path}.source_sentence_ids", issues)
            sentence_slots = _validate_id_array(sentence.get("authorized_draft_slot_ids"), f"{sentence_path}.authorized_draft_slot_ids", issues)
            if side == "source" and (sentence_sources != [sentence_id] or sentence_slots):
                issues.append(f"{sentence_path} source provenance must bind only itself")
            elif side == "candidate":
                if bool(sentence_sources) == bool(sentence_slots):
                    issues.append(f"{sentence_path} candidate provenance must use source sentences xor one authorized draft slot")
                if sentence_slots and (len(sentence_slots) != 1 or sentence_slots[0] not in slot_ids):
                    issues.append(f"{sentence_path} candidate draft-slot provenance is invalid")
            _validate_id_array(sentence.get("claim_ids"), f"{sentence_path}.claim_ids", issues)
            _validate_id_array(sentence.get("citation_relation_ids"), f"{sentence_path}.citation_relation_ids", issues)
            if not isinstance(sentence.get("text"), str):
                issues.append(f"{sentence_path}.text must be a string")
            else:
                combined.append(sentence["text"])
                for unresolved in unresolved_citation_like_occurrences(sentence["text"]):
                    issues.append(
                        f"{sentence_path}.text contains unresolved citation-like syntax "
                        f"at [{unresolved['start']},{unresolved['end']}]: {unresolved['token']}"
                    )
        if sentence_ordinals != list(range(1, len(sentence_ordinals) + 1)):
            issues.append(f"{path}.sentences ordinals must be contiguous and ordered")
        if " ".join(combined).strip() != text.strip():
            issues.append(f"{path}.text must equal ordered sentence texts joined by one space")
    if ordinals != list(range(1, len(ordinals) + 1)):
        issues.append("unit ordinals must be contiguous and ordered")
    section_order: dict[str, int] = {}
    for unit in units:
        if not isinstance(unit, dict):
            continue
        section_id = unit.get("section_id")
        section_ordinal = unit.get("section_ordinal")
        if section_id in section_order and section_order[section_id] != section_ordinal:
            issues.append(f"section {section_id} has inconsistent section_ordinal")
        elif _is_identifier(section_id) and isinstance(section_ordinal, int):
            section_order[section_id] = section_ordinal
    unique_section_ordinals = sorted(set(section_order.values()))
    if unique_section_ordinals != list(range(1, len(unique_section_ordinals) + 1)):
        issues.append("section ordinals must be contiguous")
    return issues


def refresh_document(document: dict[str, Any]) -> None:
    """Rebuild all derived unit locators and the document hash in place."""
    for ordinal, unit in enumerate(document.get("units", []), 1):
        unit["ordinal"] = ordinal
        for sentence_ordinal, sentence in enumerate(unit.get("sentences", []), 1):
            sentence["ordinal"] = sentence_ordinal
        unit["text"] = " ".join(sentence["text"] for sentence in unit.get("sentences", [])).strip()
        unit["locator"] = _expected_locator(document, unit["unit_id"], unit["text"])
    document["artifact_sha256"] = document_sha256(document)


def _lineage_relation(unit: dict[str, Any], source_index: dict[str, dict[str, Any]], reference_counts: Counter[str]) -> str:
    slot_ids = unit.get("authorized_draft_slot_ids", [])
    if slot_ids:
        return "drafted_slot"
    source_ids = unit.get("source_unit_ids", [])
    if len(source_ids) > 1:
        return "merged"
    if source_ids and reference_counts[source_ids[0]] > 1:
        return "split"
    if source_ids:
        source = source_index[source_ids[0]]
        if source.get("section_id") != unit.get("section_id") or source.get("ordinal") != unit.get("ordinal"):
            return "moved"
        if source.get("text") != unit.get("text"):
            return "replaced"
        return "unchanged"
    return "orphan"


def build_lineage_map(source: dict[str, Any], candidate: dict[str, Any], *, origin: str = "deterministic_patch_layer") -> dict[str, Any]:
    source_index = {unit["unit_id"]: unit for unit in source.get("units", [])}
    reference_counts = Counter(
        source_id
        for unit in candidate.get("units", [])
        for source_id in unit.get("source_unit_ids", [])
    )
    lineage: dict[str, Any] = {
        "schema_name": "review_revision_lineage_map",
        "schema_version": "0.1.0",
        "artifact_id": f"review-lineage:{canonical_sha256({'source': artifact_identity(source), 'candidate': artifact_identity(candidate)})[:24]}",
        "artifact_sha256": "0" * 64,
        "origin": origin,
        "source_artifact": artifact_identity(source),
        "candidate_artifact": artifact_identity(candidate),
        "unit_lineage": [],
        "sentence_lineage": [],
    }
    for unit in candidate.get("units", []):
        lineage["unit_lineage"].append({
            "candidate_unit_id": unit["unit_id"],
            "source_unit_ids": list(unit.get("source_unit_ids", [])),
            "authorized_draft_slot_ids": list(unit.get("authorized_draft_slot_ids", [])),
            "relation": _lineage_relation(unit, source_index, reference_counts),
        })
        for sentence in unit.get("sentences", []):
            lineage["sentence_lineage"].append({
                "candidate_sentence_id": sentence["sentence_id"],
                "source_sentence_ids": list(sentence.get("source_sentence_ids", [])),
                "authorized_draft_slot_ids": list(sentence.get("authorized_draft_slot_ids", [])),
            })
    lineage["artifact_sha256"] = payload_sha256(lineage, "artifact_sha256")
    return lineage


def validate_lineage_map(source: dict[str, Any], candidate: dict[str, Any], lineage: dict[str, Any] | None) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    def add(code: str, message: str) -> None:
        issues.append({"code": code, "message": message})

    if not isinstance(lineage, dict):
        return [{"code": "lineage:missing", "message": "a separate trusted lineage map is required"}]
    if lineage.get("schema_name") != "review_revision_lineage_map" or lineage.get("schema_version") != "0.1.0":
        add("lineage:identity", "lineage schema identity is unsupported")
    if lineage.get("artifact_sha256") != payload_sha256(lineage, "artifact_sha256"):
        add("lineage:hash", "lineage artifact hash mismatch")
    origin = lineage.get("origin")
    if origin not in ALL_LINEAGE_ORIGINS:
        add("lineage:origin", "lineage origin is unsupported")
    elif origin not in TRUSTED_LINEAGE_ORIGINS:
        add("lineage:untrusted", "model-declared lineage cannot establish provenance")
    if lineage.get("source_artifact") != artifact_identity(source):
        add("lineage:source_binding", "lineage does not bind the exact source artifact")
    if lineage.get("candidate_artifact") != artifact_identity(candidate):
        add("lineage:candidate_binding", "lineage does not bind the exact candidate artifact")

    source_units = {unit["unit_id"] for unit in source.get("units", [])}
    source_sentences = {
        sentence["sentence_id"]
        for unit in source.get("units", [])
        for sentence in unit.get("sentences", [])
    }
    slot_ids = {slot["slot_id"] for slot in source.get("authorized_empty_draft_slots", [])}
    candidate_units = {unit["unit_id"]: unit for unit in candidate.get("units", [])}
    candidate_sentences = {
        sentence["sentence_id"]: sentence
        for unit in candidate.get("units", [])
        for sentence in unit.get("sentences", [])
    }
    unit_rows = lineage.get("unit_lineage")
    sentence_rows = lineage.get("sentence_lineage")
    if not isinstance(unit_rows, list) or not isinstance(sentence_rows, list):
        add("lineage:shape", "unit_lineage and sentence_lineage must be arrays")
        return issues
    unit_index: dict[str, dict[str, Any]] = {}
    represented_sources: Counter[str] = Counter()
    for row in unit_rows:
        if not isinstance(row, dict) or not _is_identifier(row.get("candidate_unit_id")):
            add("lineage:shape", "unit lineage row lacks candidate_unit_id")
            continue
        candidate_id = row["candidate_unit_id"]
        if candidate_id in unit_index:
            add("lineage:duplicate", f"duplicate unit lineage: {candidate_id}")
            continue
        unit_index[candidate_id] = row
        source_ids = row.get("source_unit_ids", [])
        draft_ids = row.get("authorized_draft_slot_ids", [])
        unit = candidate_units.get(candidate_id)
        if unit is None:
            add("lineage:unknown_candidate", f"unknown candidate unit: {candidate_id}")
            continue
        if source_ids != unit.get("source_unit_ids") or draft_ids != unit.get("authorized_draft_slot_ids"):
            add("lineage:candidate_conflict", f"lineage conflicts with candidate unit: {candidate_id}")
        if bool(source_ids) == bool(draft_ids):
            add("lineage:orphan", f"candidate unit lacks an exclusive provenance channel: {candidate_id}")
        unknown_sources = sorted(set(source_ids) - source_units)
        unknown_slots = sorted(set(draft_ids) - slot_ids)
        if unknown_sources or unknown_slots:
            add("lineage:unknown_origin", f"unknown source/slot for {candidate_id}: {unknown_sources + unknown_slots}")
        represented_sources.update(source_ids)
    if set(unit_index) != set(candidate_units):
        add("lineage:unit_coverage", "lineage must cover every candidate unit exactly once")
    omitted_sources = sorted(source_units - set(represented_sources))
    if omitted_sources:
        add("lineage:source_coverage", f"source units were removed without an executable operation: {omitted_sources}")

    sentence_index: dict[str, dict[str, Any]] = {}
    represented_sentences: Counter[str] = Counter()
    for row in sentence_rows:
        if not isinstance(row, dict) or not _is_identifier(row.get("candidate_sentence_id")):
            add("lineage:shape", "sentence lineage row lacks candidate_sentence_id")
            continue
        candidate_id = row["candidate_sentence_id"]
        if candidate_id in sentence_index:
            add("lineage:duplicate", f"duplicate sentence lineage: {candidate_id}")
            continue
        sentence_index[candidate_id] = row
        sentence = candidate_sentences.get(candidate_id)
        if sentence is None:
            add("lineage:unknown_candidate", f"unknown candidate sentence: {candidate_id}")
            continue
        source_ids = row.get("source_sentence_ids", [])
        draft_ids = row.get("authorized_draft_slot_ids", [])
        if source_ids != sentence.get("source_sentence_ids") or draft_ids != sentence.get("authorized_draft_slot_ids"):
            add("lineage:candidate_conflict", f"lineage conflicts with candidate sentence: {candidate_id}")
        if bool(source_ids) == bool(draft_ids):
            add("lineage:orphan", f"candidate sentence lacks an exclusive provenance channel: {candidate_id}")
        if set(source_ids) - source_sentences or set(draft_ids) - slot_ids:
            add("lineage:unknown_origin", f"unknown sentence source/slot for {candidate_id}")
        represented_sentences.update(source_ids)
    if set(sentence_index) != set(candidate_sentences):
        add("lineage:sentence_coverage", "lineage must cover every candidate sentence exactly once")
    omitted_sentences = sorted(source_sentences - set(represented_sentences))
    if omitted_sentences:
        add("lineage:sentence_source_coverage", f"source sentences were omitted: {omitted_sentences}")
    return issues


def _covered(span: tuple[int, int], exclusions: list[tuple[int, int]]) -> bool:
    return any(start <= span[0] and span[1] <= end for start, end in exclusions)


def _normalized_number(raw: str) -> str:
    value = raw.rstrip("%")
    try:
        normalized = format(Decimal(value), "f")
        normalized = normalized.rstrip("0").rstrip(".") if "." in normalized else normalized
        if normalized.startswith("."):
            normalized = "0" + normalized
        suffix = "%" if raw.endswith("%") else ""
        return normalized + suffix
    except InvalidOperation:
        return raw.lower()


def _append_occurrence(rows: list[dict[str, Any]], kind: str, match: re.Match[str], identity: str | None = None) -> None:
    rows.append({
        "protected_class": kind,
        "token": match.group(0),
        "identity": identity if identity is not None else match.group(0).lower(),
        "start": match.start(),
        "end": match.end(),
    })


_SUPERSCRIPT_TRANSLATION = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
_RANGE_DASH_TRANSLATION = str.maketrans({dash: "-" for dash in "‐‑‒–—−"})


def _numeric_citation_body(token: str, style: str) -> str:
    compact = token.casefold()
    if style == "unicode_superscript":
        compact = compact.translate(_SUPERSCRIPT_TRANSLATION)
    elif style == "html_superscript":
        compact = re.sub(r"</?sup>", "", compact, flags=re.IGNORECASE)
    elif style == "caret_superscript":
        compact = compact.strip("^")
    elif style == "numeric_bracket":
        compact = compact[1:-1]
    return re.sub(r"\s+", "", compact.translate(_RANGE_DASH_TRANSLATION))


def _normalized_author_group(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip().casefold().replace("’", "'"))
    normalized = re.sub(r"\s+(?:and|&)\s+", "&", normalized)
    normalized = re.sub(r"\s+et\s+al\.?$", " etal", normalized)
    return normalized


def _author_year_identity(token: str) -> str:
    year = r"(?:19|20)\d{2}[a-z]?"
    items: list[tuple[str, str]] = []
    stripped = token.strip()
    fallback = "author_year:" + re.sub(r"\s+", "", stripped).casefold()
    if stripped.startswith("(") and stripped.endswith(")"):
        for item in re.split(r"\s*;\s*", stripped[1:-1]):
            match = re.fullmatch(rf"(?P<author>{_AUTHOR})\s*,?\s*(?P<year>{year})", item, re.UNICODE | re.IGNORECASE)
            if match is None:
                return fallback
            items.append((_normalized_author_group(match.group("author")), match.group("year").casefold()))
    else:
        match = re.fullmatch(
            rf"(?P<author>{_AUTHOR})\s*\(\s*(?P<year>{year})\s*\)",
            stripped,
            re.UNICODE | re.IGNORECASE,
        )
        if match is None:
            return fallback
        items.append((_normalized_author_group(match.group("author")), match.group("year").casefold()))
    return "author_year:" + ";".join(f"{author},{year_value}" for author, year_value in items)


def _citation_identity(token: str, style: str) -> str:
    if style == "author_year":
        return _author_year_identity(token)
    body = _numeric_citation_body(token, style)
    if style == "numeric_bracket":
        return f"numeric_bracket:[{body}]"
    return f"numeric_superscript:{body}"


def citation_occurrences(text: str) -> list[dict[str, Any]]:
    """Return non-overlapping typed citation anchors with normalized identity."""
    rows: list[dict[str, Any]] = []
    occupied: list[tuple[int, int]] = []
    patterns = (
        (HTML_SUPERSCRIPT_CITATION_RE, "html_superscript"),
        (AUTHOR_YEAR_NARRATIVE_CITATION_RE, "author_year"),
        (AUTHOR_YEAR_PAREN_CITATION_RE, "author_year"),
        (NUMERIC_BRACKET_CITATION_RE, "numeric_bracket"),
        (CARET_SUPERSCRIPT_CITATION_RE, "caret_superscript"),
        (UNICODE_SUPERSCRIPT_CITATION_RE, "unicode_superscript"),
    )
    for pattern, style in patterns:
        for match in pattern.finditer(text):
            span = (match.start(), match.end())
            if _covered(span, occupied):
                continue
            rows.append({
                "protected_class": "citation",
                "citation_style": style,
                "token": match.group(0),
                "identity": _citation_identity(match.group(0), style),
                "start": match.start(),
                "end": match.end(),
            })
            occupied.append(span)
    rows.sort(key=lambda row: (row["start"], row["end"], row["identity"]))
    return rows


def unresolved_citation_like_occurrences(text: str) -> list[dict[str, Any]]:
    """Return author-year-like spans not fully resolved by the bounded parser."""
    recognized = {
        (row["start"], row["end"])
        for row in citation_occurrences(text)
        if row["citation_style"] == "author_year"
    }
    unresolved: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for pattern in (
        AUTHOR_YEAR_PAREN_LIKE_RE,
        AUTHOR_YEAR_NARRATIVE_LIKE_RE,
        AUTHOR_YEAR_MULTI_AUTHOR_LIKE_RE,
    ):
        for match in pattern.finditer(text):
            span = (match.start(), match.end())
            if span in recognized or span in seen:
                continue
            seen.add(span)
            unresolved.append({"token": match.group(0), "start": match.start(), "end": match.end()})
    return sorted(unresolved, key=lambda row: (row["start"], row["end"], row["token"]))


def protected_occurrences(text: str, protected_terms: list[str]) -> list[dict[str, Any]]:
    """Extract conservative exact protected tokens without scientific inference."""
    rows: list[dict[str, Any]] = []
    exclusions: list[tuple[int, int]] = []
    for citation in citation_occurrences(text):
        rows.append(citation)
        exclusions.append((citation["start"], citation["end"]))
    for pattern, kind in ((FIGURE_TABLE_RE, "figure_table_reference"), (STATISTIC_RE, "statistic")):
        for match in pattern.finditer(text):
            if _covered((match.start(), match.end()), exclusions):
                continue
            identity = re.sub(r"\s+", "", match.group(0)).lower()
            _append_occurrence(rows, kind, match, identity)
            exclusions.append((match.start(), match.end()))
    for match in UNIT_RE.finditer(text):
        compact = re.sub(r"\s+", "", match.group(0)).replace("ug", "µg").replace("ul", "µl").lower()
        _append_occurrence(rows, "unit", match, compact)
    for match in NUMBER_RE.finditer(text):
        if _covered((match.start(), match.end()), exclusions):
            continue
        _append_occurrence(rows, "numeric", match, _normalized_number(match.group(0)))
    for term in protected_terms:
        pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE)
        for match in pattern.finditer(text):
            _append_occurrence(rows, "terminology", match, term.casefold())
    for kind, pattern in LEXICAL_PATTERNS.items():
        for match in pattern.finditer(text):
            _append_occurrence(rows, kind, match, re.sub(r"\s+", " ", match.group(0).casefold()))
    rows.sort(key=lambda row: (row["start"], row["end"], row["protected_class"], row["identity"]))
    return rows


def _citation_attachments(units: list[dict[str, Any]]) -> Counter[tuple[str, tuple[str, ...], tuple[str, ...]]]:
    rows: Counter[tuple[str, tuple[str, ...], tuple[str, ...]]] = Counter()
    for unit in units:
        for sentence in unit.get("sentences", []):
            if sentence.get("authorized_draft_slot_ids"):
                continue
            citations = citation_occurrences(sentence.get("text", ""))
            for citation in citations:
                rows[(citation["identity"], tuple(sorted(sentence.get("claim_ids", []))), tuple(sorted(sentence.get("citation_relation_ids", []))))] += 1
    return rows


def _citation_form(occurrence: dict[str, Any]) -> str:
    """Return the citation's syntactic family, not merely its visual style."""
    style = occurrence["citation_style"]
    if style == "author_year":
        return "author_year_parenthetical" if occurrence["token"].lstrip().startswith("(") else "author_year_narrative"
    if style == "numeric_bracket":
        return "numeric_bracket"
    return "numeric_superscript"


def _citation_boundary_role(text: str, start: int, end: int) -> str:
    """Classify placement without treating ordinary wording-length changes as moves."""
    lexical = re.compile(r"[^\W_]", re.UNICODE)
    before = lexical.search(text[:start]) is not None
    after = lexical.search(text[end:]) is not None
    if before and after:
        return "medial"
    if before:
        return "trailing"
    if after:
        return "leading"
    return "isolated"


def _citation_placement_rows(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Bind citation placement to sentence lineage, paragraph, and claim/relation IDs."""
    rows: list[dict[str, Any]] = []
    for unit in document.get("units", []):
        for sentence in unit.get("sentences", []):
            per_identity: Counter[str] = Counter()
            text = sentence.get("text", "")
            occurrences = citation_occurrences(text)
            citation_spans = [(item["start"], item["end"]) for item in occurrences]
            lexical_rows = [
                (match.start(), match.end(), match.group(0).casefold().replace("’", "'"))
                for match in LEXICAL_TOKEN_RE.finditer(text)
                if not _covered((match.start(), match.end()), citation_spans)
            ]
            for occurrence in occurrences:
                per_identity[occurrence["identity"]] += 1
                source_sentence_ids = (
                    [sentence.get("sentence_id")]
                    if document.get("side") == "source"
                    else sorted(sentence.get("source_sentence_ids", []))
                )
                placement = {
                    "unit_id": unit.get("unit_id"),
                    "sentence_id": sentence.get("sentence_id"),
                    "source_sentence_ids": source_sentence_ids,
                    "section_id": unit.get("section_id"),
                    "paragraph_plan_id": unit.get("paragraph_plan_id"),
                    "boundary_role": _citation_boundary_role(
                        sentence.get("text", ""), occurrence["start"], occurrence["end"]
                    ),
                    "citation_form": _citation_form(occurrence),
                    "occurrence_ordinal": per_identity[occurrence["identity"]],
                    "start": occurrence["start"],
                    "end": occurrence["end"],
                }
                rows.append({
                    "identity": occurrence["identity"],
                    "token": occurrence["token"],
                    "claim_ids": sorted(sentence.get("claim_ids", [])),
                    "citation_relation_ids": sorted(sentence.get("citation_relation_ids", [])),
                    "placement": placement,
                    "_lexical_tokens": [item[2] for item in lexical_rows],
                    "_lexical_insertion_index": sum(item[1] <= occurrence["start"] for item in lexical_rows),
                })
    return rows


def _placement_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    placement = row["placement"]
    return (
        tuple(placement["source_sentence_ids"]),
        placement["section_id"],
        placement["paragraph_plan_id"],
        placement["boundary_role"],
        placement["citation_form"],
        placement["occurrence_ordinal"],
    )


def _aligned_lexical_boundaries(
    source_row: dict[str, Any],
    candidate_row: dict[str, Any],
) -> tuple[dict[str, str], dict[str, str]]:
    """Map both citations to stable lexical insertion boundaries.

    Raw character offsets are intentionally excluded: adding ordinary words
    before an unchanged citation must not look like movement.  Exact matched
    lexical tokens provide shared anchors on both sides of the insertion point.
    """
    source_placement = source_row["placement"]
    candidate_placement = candidate_row["placement"]
    if source_placement["source_sentence_ids"] != candidate_placement["source_sentence_ids"]:
        boundary = {
            "alignment_status": "not_applicable",
            "left_anchor": "DIFFERENT_SENTENCE_LINEAGE",
            "right_anchor": "DIFFERENT_SENTENCE_LINEAGE",
        }
        return dict(boundary), dict(boundary)

    source_tokens = source_row["_lexical_tokens"]
    candidate_tokens = candidate_row["_lexical_tokens"]
    matcher = SequenceMatcher(a=source_tokens, b=candidate_tokens, autojunk=False)
    opcodes = matcher.get_opcodes()
    matched_pairs = [
        (block.a + offset, block.b + offset, source_tokens[block.a + offset])
        for block in matcher.get_matching_blocks()
        for offset in range(block.size)
    ]
    if not matched_pairs and (source_tokens or candidate_tokens):
        unresolved = {
            "alignment_status": "ambiguous",
            "left_anchor": "UNRESOLVED_LEXICAL_ALIGNMENT",
            "right_anchor": "UNRESOLVED_LEXICAL_ALIGNMENT",
        }
        return dict(unresolved), dict(unresolved)

    def boundary_is_inside_unresolved_gap(side: int, boundary_index: int) -> bool:
        """Return true when this exact insertion boundary has no unique alignment.

        Equal-block edges remain usable anchors.  A boundary strictly inside a
        replace/insert/delete span cannot be mapped one-to-one merely from the
        unchanged tokens outside that span.
        """
        for tag, source_start, source_end, candidate_start, candidate_end in opcodes:
            if tag == "equal":
                continue
            start, end = (
                (source_start, source_end)
                if side == 0
                else (candidate_start, candidate_end)
            )
            if start < boundary_index < end:
                return True
        return False

    def replace_gap_edge(side: int, boundary_index: int) -> tuple[str, str] | None:
        """Return a shared opcode identity for a non-empty replace-gap edge.

        Start and end edges are both deterministically aligned, but they are not
        interchangeable.  Zero-length insert/delete sides deliberately retain
        the existing anchor behavior.
        """
        for tag, source_start, source_end, candidate_start, candidate_end in opcodes:
            if tag != "replace" or source_start == source_end or candidate_start == candidate_end:
                continue
            start, end = (
                (source_start, source_end)
                if side == 0
                else (candidate_start, candidate_end)
            )
            edge = "start" if boundary_index == start else "end" if boundary_index == end else None
            if edge is not None:
                gap_id = f"replace:{source_start}:{source_end}:{candidate_start}:{candidate_end}"
                return gap_id, edge
        return None

    def describe(side: int, boundary_index: int) -> dict[str, str]:
        if boundary_is_inside_unresolved_gap(side, boundary_index):
            return {
                "alignment_status": "ambiguous",
                "left_anchor": "UNRESOLVED_LEXICAL_ALIGNMENT",
                "right_anchor": "UNRESOLVED_LEXICAL_ALIGNMENT",
            }
        left = [pair for pair in matched_pairs if pair[side] < boundary_index]
        right = [pair for pair in matched_pairs if pair[side] >= boundary_index]

        def anchor(pair: tuple[int, int, str]) -> str:
            return f"aligned:{pair[0]}:{pair[1]}:{pair[2]}"

        boundary = {
            "alignment_status": "aligned",
            "left_anchor": anchor(left[-1]) if left else "START",
            "right_anchor": anchor(right[0]) if right else "END",
        }
        gap_edge = replace_gap_edge(side, boundary_index)
        if gap_edge is not None:
            gap_id, edge = gap_edge
            marker = f"aligned-gap-edge:{gap_id}:{edge}"
            if edge == "start":
                boundary["right_anchor"] = marker
            else:
                boundary["left_anchor"] = marker
        return boundary

    return (
        describe(0, source_row["_lexical_insertion_index"]),
        describe(1, candidate_row["_lexical_insertion_index"]),
    )


def build_citation_anchor_inventory(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Bind every recognized citation token to its exact sentence and relations."""
    anchors: list[dict[str, Any]] = []
    for unit in document.get("units", []):
        for sentence in unit.get("sentences", []):
            for occurrence in citation_occurrences(sentence.get("text", "")):
                locator = {
                    "locator_type": "structured_citation_token",
                    "side": document.get("side"),
                    "artifact_id": document.get("artifact_id"),
                    "unit_id": unit.get("unit_id"),
                    "sentence_id": sentence.get("sentence_id"),
                    "start": occurrence["start"],
                    "end": occurrence["end"],
                    "span_sha256": text_sha256(occurrence["token"]),
                }
                payload = {
                    "citation_style": occurrence["citation_style"],
                    "identity": occurrence["identity"],
                    "token": occurrence["token"],
                    "locator": locator,
                    "claim_ids": sorted(sentence.get("claim_ids", [])),
                    "citation_relation_ids": sorted(sentence.get("citation_relation_ids", [])),
                }
                anchors.append({
                    "citation_anchor_id": f"review-citation-anchor:{canonical_sha256(payload)[:24]}",
                    **payload,
                })
    return sorted(anchors, key=lambda row: row["citation_anchor_id"])


def _source_positions(source: dict[str, Any]) -> dict[str, int]:
    return {unit["unit_id"]: index for index, unit in enumerate(source.get("units", []))}


def _has_inversion(values: list[int]) -> bool:
    return any(left > right for left, right in zip(values, values[1:]))


def build_inventory(source: dict[str, Any], candidate: dict[str, Any], lineage: dict[str, Any]) -> dict[str, Any]:
    source_units = {unit["unit_id"]: unit for unit in source.get("units", [])}
    source_positions = _source_positions(source)
    candidate_units = candidate.get("units", [])
    references = Counter(source_id for unit in candidate_units for source_id in unit.get("source_unit_ids", []))
    one_to_one_positions = [
        source_positions[unit["source_unit_ids"][0]]
        for unit in candidate_units
        if len(unit.get("source_unit_ids", [])) == 1 and unit["source_unit_ids"][0] in source_positions
    ]
    paragraph_order_changed = _has_inversion(one_to_one_positions)
    changed_units: list[dict[str, Any]] = []
    protected_changes: list[dict[str, Any]] = []
    split_groups: dict[tuple[str, ...], list[tuple[dict[str, Any], str]]] = defaultdict(list)
    terms = sorted(set(source.get("protected_terms", [])) | set(candidate.get("protected_terms", [])))

    def append_protected_deltas(
        inventory_change_id: str,
        source_text: str,
        candidate_text: str,
        slot_ids: list[str],
    ) -> None:
        """Compare one complete lineage group so structural splits do not invent deltas."""
        # An authorized slot placeholder is provenance evidence, not scientific prose.
        source_occurrences = protected_occurrences("" if slot_ids else source_text, terms)
        candidate_occurrences = protected_occurrences(candidate_text, terms)
        source_counter = Counter((row["protected_class"], row["identity"]) for row in source_occurrences)
        candidate_counter = Counter((row["protected_class"], row["identity"]) for row in candidate_occurrences)
        keys = sorted(set(source_counter) | set(candidate_counter))
        for protected_class, identity in keys:
            delta = candidate_counter[(protected_class, identity)] - source_counter[(protected_class, identity)]
            if delta:
                change_payload = {
                    "inventory_change_id": inventory_change_id,
                    "protected_class": protected_class,
                    "identity": identity,
                    "delta_type": "added" if delta > 0 else "deleted",
                    "occurrence_delta": abs(delta),
                    "authorized_draft_slot_ids": slot_ids,
                }
                protected_changes.append({
                    "protected_change_id": f"review-protected-change:{canonical_sha256(change_payload)[:24]}",
                    **change_payload,
                })

            # Identity-preserving citation typography is still evidence. Cancel
            # byte-identical token occurrences, pair the deterministic remainder,
            # and inventory each distinct surface transformation explicitly.
            if protected_class == "citation":
                source_tokens = Counter(
                    (_citation_form(row), row["token"]) for row in source_occurrences
                    if row["protected_class"] == protected_class and row["identity"] == identity
                )
                candidate_tokens = Counter(
                    (_citation_form(row), row["token"]) for row in candidate_occurrences
                    if row["protected_class"] == protected_class and row["identity"] == identity
                )
                for token in set(source_tokens) & set(candidate_tokens):
                    shared = min(source_tokens[token], candidate_tokens[token])
                    source_tokens[token] -= shared
                    candidate_tokens[token] -= shared
                for form in sorted({key[0] for key in source_tokens} | {key[0] for key in candidate_tokens}):
                    source_remaining = sorted(
                        token for (token_form, token), count in source_tokens.items()
                        if token_form == form
                        for _ in range(count)
                    )
                    candidate_remaining = sorted(
                        token for (token_form, token), count in candidate_tokens.items()
                        if token_form == form
                        for _ in range(count)
                    )
                    surface_pairs = Counter(zip(source_remaining, candidate_remaining))
                    for (source_token, candidate_token), count in sorted(surface_pairs.items()):
                        formatting_payload = {
                            "inventory_change_id": inventory_change_id,
                            "protected_class": "citation",
                            "identity": identity,
                            "delta_type": "formatting_only",
                            "occurrence_delta": count,
                            "source_token": source_token,
                            "candidate_token": candidate_token,
                            "authorized_draft_slot_ids": slot_ids,
                        }
                        protected_changes.append({
                            "protected_change_id": f"review-protected-change:{canonical_sha256(formatting_payload)[:24]}",
                            **formatting_payload,
                        })

    for unit in candidate_units:
        source_ids = unit.get("source_unit_ids", [])
        slot_ids = unit.get("authorized_draft_slot_ids", [])
        source_group = [source_units[source_id] for source_id in source_ids if source_id in source_units]
        source_text = "\n\n".join(item["text"] for item in source_group)
        source_locators = [item["locator"] for item in source_group]
        effects: set[str] = set()
        if slot_ids:
            slot_index = {slot["slot_id"]: slot for slot in source.get("authorized_empty_draft_slots", [])}
            source_text = "\n".join(slot_index[slot_id]["placeholder_token"] for slot_id in slot_ids if slot_id in slot_index)
            source_locators = [slot_index[slot_id]["locator"] for slot_id in slot_ids if slot_id in slot_index]
            effects.update({"unit_added", "authorized_draft_slot_materialization", "text_changed"})
        elif source_text != unit["text"]:
            effects.add("text_changed")
        if len(source_ids) > 1:
            effects.add("paragraph_merge")
        if any(references[source_id] > 1 for source_id in source_ids):
            effects.add("paragraph_split")
        if any(source_units[source_id]["section_id"] != unit["section_id"] for source_id in source_ids):
            effects.add("section_membership_changed")
        if paragraph_order_changed and source_ids:
            effects.add("paragraph_move")
        source_sentence_ids = [sentence["sentence_id"] for item in source_group for sentence in item.get("sentences", [])]
        sentence_positions = {sentence_id: index for index, sentence_id in enumerate(source_sentence_ids)}
        candidate_sentence_sources = [sentence.get("source_sentence_ids", []) for sentence in unit.get("sentences", [])]
        mapped_positions = [sentence_positions[ids[0]] for ids in candidate_sentence_sources if len(ids) == 1 and ids[0] in sentence_positions]
        if source_sentence_ids and len(source_sentence_ids) != len(unit.get("sentences", [])):
            effects.add("sentence_count_changed")
        if _has_inversion(mapped_positions):
            effects.add("sentence_order_changed")
        counts = Counter(source_id for ids in candidate_sentence_sources for source_id in ids)
        if any(count > 1 for count in counts.values()):
            effects.add("sentence_split")
        if any(len(ids) > 1 for ids in candidate_sentence_sources):
            effects.add("sentence_merge")

        if effects:
            identity_payload = {
                "source_unit_ids": source_ids,
                "authorized_draft_slot_ids": slot_ids,
                "candidate_unit_ids": [unit["unit_id"]],
                "source_representation_sha256": text_sha256(source_text),
                "candidate_representation_sha256": text_sha256(unit["text"]),
                "observed_effects": sorted(effects),
            }
            inventory_change_id = f"review-inventory-change:{canonical_sha256(identity_payload)[:24]}"
            changed_units.append({
                "inventory_change_id": inventory_change_id,
                **identity_payload,
                "source_locators": source_locators,
                "candidate_locators": [unit["locator"]],
                "section_id": unit["section_id"],
                "paragraph_plan_id": unit["paragraph_plan_id"],
            })
            if source_ids and any(references[source_id] > 1 for source_id in source_ids):
                split_groups[tuple(source_ids)].append((unit, inventory_change_id))
            else:
                append_protected_deltas(inventory_change_id, source_text, unit["text"], slot_ids)

    # A paragraph split maps one complete source group to multiple candidate units.
    # Compare the group once; per-child comparison would falsely report every token
    # absent from that child as a protected deletion.
    for source_ids, split_candidates in sorted(split_groups.items()):
        source_group = [source_units[source_id] for source_id in source_ids]
        source_text = "\n\n".join(item["text"] for item in source_group)
        candidate_text = "\n\n".join(unit["text"] for unit, _ in split_candidates)
        append_protected_deltas(split_candidates[0][1], source_text, candidate_text, [])

    # Identity and claim/relation attachment are compared separately from
    # placement. Exact unchanged placements cancel; deterministic remaining
    # pairs become explicit movement evidence rather than typography deltas.
    source_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    candidate_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    placement_key = lambda row: (
        row["identity"], tuple(row["claim_ids"]), tuple(row["citation_relation_ids"])
    )
    for row in _citation_placement_rows(source):
        source_groups[placement_key(row)].append(row)
    for row in _citation_placement_rows(candidate):
        candidate_groups[placement_key(row)].append(row)
    candidate_change_ids = {
        candidate_unit_id: change["inventory_change_id"]
        for change in changed_units
        for candidate_unit_id in change["candidate_unit_ids"]
    }
    for key in sorted(set(source_groups) & set(candidate_groups)):
        source_rows = list(source_groups[key])
        candidate_rows = list(candidate_groups[key])
        source_rows.sort(key=lambda row: (_placement_signature(row), row["token"]))
        candidate_rows.sort(key=lambda row: (_placement_signature(row), row["token"]))

        # Cancel exact stable placements before pairing remaining occurrences.
        # This prevents an authorized new citation from stealing the match for
        # an unchanged existing occurrence with the same citation identity.
        unmatched_source: list[dict[str, Any]] = []
        unmatched_candidate = list(candidate_rows)
        for source_row in source_rows:
            exact_index: int | None = None
            for index, candidate_row in enumerate(unmatched_candidate):
                if _placement_signature(source_row) != _placement_signature(candidate_row):
                    continue
                source_boundary, candidate_boundary = _aligned_lexical_boundaries(source_row, candidate_row)
                if source_boundary == candidate_boundary and source_boundary["alignment_status"] != "ambiguous":
                    exact_index = index
                    break
            if exact_index is None:
                unmatched_source.append(source_row)
            else:
                unmatched_candidate.pop(exact_index)

        source_rows = unmatched_source
        candidate_rows = unmatched_candidate
        for source_row, candidate_row in zip(source_rows, candidate_rows):
            source_placement = dict(source_row["placement"])
            candidate_placement = dict(candidate_row["placement"])
            source_boundary, candidate_boundary = _aligned_lexical_boundaries(source_row, candidate_row)
            source_placement["lexical_boundary"] = source_boundary
            candidate_placement["lexical_boundary"] = candidate_boundary
            same_coarse_placement = _placement_signature(source_row) == _placement_signature(candidate_row)
            same_lexical_boundary = source_boundary == candidate_boundary
            alignment_ambiguous = "ambiguous" in {
                source_boundary["alignment_status"], candidate_boundary["alignment_status"]
            }
            if same_coarse_placement and same_lexical_boundary and not alignment_ambiguous:
                continue
            payload = {
                "inventory_change_id": candidate_change_ids.get(
                    candidate_placement["unit_id"], "document-level-citation-placement"
                ),
                "protected_class": "citation",
                "identity": key[0],
                "delta_type": "placement_changed",
                "occurrence_delta": 1,
                "source_token": source_row["token"],
                "candidate_token": candidate_row["token"],
                "source_placement": source_placement,
                "candidate_placement": candidate_placement,
                "claim_ids": list(key[1]),
                "citation_relation_ids": list(key[2]),
                "authorized_draft_slot_ids": [],
            }
            protected_changes.append({
                "protected_change_id": f"review-protected-change:{canonical_sha256(payload)[:24]}",
                **payload,
            })

    source_attachments = _citation_attachments(source.get("units", []))
    candidate_attachments = _citation_attachments(candidate_units)
    if source_attachments != candidate_attachments:
        for identity, claims, relations in sorted(set(source_attachments) | set(candidate_attachments)):
            delta = candidate_attachments[(identity, claims, relations)] - source_attachments[(identity, claims, relations)]
            if delta:
                payload = {
                    "inventory_change_id": "document-level-citation-attachment",
                    "protected_class": "citation",
                    "identity": identity,
                    "delta_type": "relation_added" if delta > 0 else "relation_deleted",
                    "occurrence_delta": abs(delta),
                    "claim_ids": list(claims),
                    "citation_relation_ids": list(relations),
                    "authorized_draft_slot_ids": [],
                }
                protected_changes.append({
                    "protected_change_id": f"review-protected-change:{canonical_sha256(payload)[:24]}",
                    **payload,
                })

    observed_effects = {effect for row in changed_units for effect in row["observed_effects"]}
    structural_footprint = {
        "paragraph_count_changed": len(source.get("units", [])) != len(candidate_units),
        "paragraph_order_changed": paragraph_order_changed,
        "sentence_count_changed": "sentence_count_changed" in observed_effects,
        "sentence_order_changed": "sentence_order_changed" in observed_effects,
        "section_membership_changed": "section_membership_changed" in observed_effects,
        "unit_split": bool({"paragraph_split", "sentence_split"} & observed_effects),
        "unit_merge": bool({"paragraph_merge", "sentence_merge"} & observed_effects),
        "unit_move": "paragraph_move" in observed_effects,
        "unit_added": "unit_added" in observed_effects,
        "authorized_draft_slot_materialized": "authorized_draft_slot_materialization" in observed_effects,
        "citation_placement_changed": any(
            change.get("delta_type") == "placement_changed" for change in protected_changes
        ),
        "unit_removed": False,
    }
    inventory: dict[str, Any] = {
        "schema_name": "review_protected_change_inventory",
        "schema_version": "0.1.0",
        "artifact_id": f"review-protected-inventory:{canonical_sha256({'source': artifact_identity(source), 'candidate': artifact_identity(candidate)})[:24]}",
        "artifact_sha256": "0" * 64,
        "source_artifact": artifact_identity(source),
        "candidate_artifact": artifact_identity(candidate),
        "lineage_ref": {
            "artifact_id": lineage.get("artifact_id"),
            "artifact_version": lineage.get("schema_version"),
            "artifact_sha256": lineage.get("artifact_sha256"),
        },
        "structural_footprint": structural_footprint,
        "changed_units": changed_units,
        "citation_anchors": {
            "source": build_citation_anchor_inventory(source),
            "candidate": build_citation_anchor_inventory(candidate),
        },
        "protected_changes": sorted(protected_changes, key=lambda row: row["protected_change_id"]),
    }
    inventory["artifact_sha256"] = payload_sha256(inventory, "artifact_sha256")
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-document", type=Path, required=True)
    parser.add_argument("--candidate-document", type=Path, required=True)
    parser.add_argument("--lineage-map", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        source = read_json(args.source_document)
        candidate = read_json(args.candidate_document)
        lineage = read_json(args.lineage_map)
        issues = validate_document(source, "source") + validate_document(candidate, "candidate")
        issues.extend(item["message"] for item in validate_lineage_map(source, candidate, lineage))
        if source.get("manuscript_id") != candidate.get("manuscript_id"):
            issues.append("source and candidate manuscript_id values differ")
        if issues:
            for issue in issues:
                print(f"inventory input error: {issue}", file=sys.stderr)
            return 1
        write_json(args.output, build_inventory(source, candidate, lineage))
    except (OSError, json.JSONDecodeError, InventoryError, KeyError, TypeError) as exc:
        print(f"inventory error: {exc}", file=sys.stderr)
        return 2
    print(f"WROTE: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
