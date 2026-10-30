#!/usr/bin/env python3
"""Deterministic core for the Phase 5 minimum scientific-integrity QC gate."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


RULESET_VERSION = "0.1.1"
VALIDATOR_VERSION = "0.1.0"
SUPPORTED_CATEGORIES = {
    "numeric", "citation", "reference", "terminology", "placeholder", "semantic_signal"
}
CHECK_IDS = (
    "manifest_semantics",
    "hash_identity",
    "alignment_coverage",
    "protected_anchor_comparison",
    "semantic_risk_localization",
    "exception_validation",
    "upstream_baseline_semantics",
)


class QCError(RuntimeError):
    """Raised for malformed inputs that prevent deterministic execution."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _metadata(schema_name: str, version: str, artifact_id: str, source_ids: Iterable[str]) -> dict[str, Any]:
    return {
        "schema_name": schema_name,
        "schema_version": version,
        "artifact_id": artifact_id,
        "created_at": utc_now(),
        "created_by": "06_scientific-integrity-qc-candidate",
        "source_artifact_ids": list(source_ids),
        "status": "draft",
        "warnings": [],
    }


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def make_locator(
    text: str,
    side: str,
    file_id: str,
    unit_id: str,
    start: int,
    end: int,
) -> dict[str, Any]:
    if not (0 <= start <= end <= len(text)):
        raise QCError(f"Invalid locator range {start}:{end} for {unit_id}")
    end_probe = start if end == start else end - 1
    return {
        "locator_type": "line_char_range",
        "side": side,
        "file_id": file_id,
        "unit_id": unit_id,
        "start_line": _line_number(text, start),
        "end_line": _line_number(text, end_probe),
        "start_char": start,
        "end_char": end,
        "span_sha256": sha256_text(text[start:end]),
    }


UNIT_BOUNDARY_RE = re.compile(r"\r?\n[ \t]*\r?\n+")


def split_units(text: str, side: str, file_id: str) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    raw_ranges: list[tuple[int, int]] = []
    cursor = 0
    for boundary in UNIT_BOUNDARY_RE.finditer(text):
        raw_ranges.append((cursor, boundary.start()))
        cursor = boundary.end()
    raw_ranges.append((cursor, len(text)))
    for raw_start, raw_end in raw_ranges:
        start, end = raw_start, raw_end
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start == end:
            continue
        ordinal = len(units) + 1
        unit_id = f"{side}:unit:{ordinal}"
        units.append({
            "unit_id": unit_id,
            "ordinal": ordinal,
            "text": text[start:end],
            "start": start,
            "end": end,
            "locator": make_locator(text, side, file_id, unit_id, start, end),
        })
    if not units:
        raise QCError("Input contains no non-whitespace comparison units")
    return units


NUMBER = r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
UNIT = (
    r"(?:%|‰|°C|°F|K|kg|mg|µg|μg|ug|ng|pg|g|mL|ml|µL|μL|uL|L|"
    r"mM|µM|μM|uM|nM|pM|M|mm|cm|µm|μm|um|nm|h|min|s|ms|days?|weeks?|months?|years?)"
)
NUMERIC_RE = re.compile(
    rf"(?<![\w.])(?P<label>[Pp]\s*)?(?P<comparator><=|>=|≤|≥|<|>|=|≈|~)?\s*"
    rf"(?P<sign>[+-])?(?P<value>{NUMBER})"
    rf"(?:(?:\s*±\s*(?P<uncertainty>{NUMBER}))|"
    rf"(?:\s*(?:–|—|\bto\b)\s*(?P<range_high>{NUMBER}))|"
    rf"(?:\s*/\s*(?P<denominator>{NUMBER})))?"
    rf"\s*(?P<unit>{UNIT})?(?![A-Za-zµμ])",
    re.IGNORECASE,
)
NUMERIC_CITATION_RE = re.compile(r"\[(?:\d+(?:\s*[-–]\s*\d+)?)(?:\s*[,;]\s*\d+(?:\s*[-–]\s*\d+)?)*\]")
AUTHOR_YEAR_ITEM = r"[A-Z][A-Za-z'’\-]+(?:\s+et\s+al\.)?(?:\s+(?:and|&)\s+[A-Z][A-Za-z'’\-]+)?,\s*(?:19|20)\d{2}[a-z]?"
AUTHOR_YEAR_CITATION_RE = re.compile(rf"\((?P<body>{AUTHOR_YEAR_ITEM}(?:\s*;\s*{AUTHOR_YEAR_ITEM})*)\)", re.IGNORECASE)
REFERENCE_RE = re.compile(
    r"\b(?P<kind>Extended\s+Data\s+Fig(?:ure)?|Supplementary\s+(?:Fig(?:ure)?|Table)|"
    r"Fig(?:ure)?|Table|Eq(?:uation)?|Sec(?:tion)?|Appendix)\.?\s*"
    r"(?P<label>(?:[A-Za-z]*\d+(?:\.\d+)*(?:[A-Za-z]*)|[A-Za-z]+))\b",
    re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(r"\{\{[^{}\n]+\}\}|\[\[[^\[\]\n]+\]\]")
SEMANTIC_PATTERNS: dict[str, tuple[str, ...]] = {
    "direction": ("increase", "increases", "increased", "decrease", "decreases", "decreased", "higher", "lower", "upregulated", "downregulated"),
    "negation": ("not", "no", "without", "failed to", "neither"),
    "causality": ("cause", "caused", "causes", "drive", "drives", "induce", "induces", "led to", "leads to", "resulted in"),
    "mechanism": ("via", "mediated by", "dependent on", "through"),
    "hedging": ("may", "might", "could", "suggest", "suggests", "suggested", "likely", "possibly", "appears"),
    "boundary": ("only", "except", "restricted to", "limited to", "at least", "at most"),
}


def _canonical_number(token: str | None) -> str | None:
    if token is None:
        return None
    lower = token.lower()
    if "e" in lower:
        lower = lower.split("e", 1)[0]
    try:
        value = format(Decimal(lower), "f")
    except InvalidOperation:
        return token
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    return value or "0"


def _numeric_components(match: re.Match[str]) -> dict[str, Any]:
    raw_value = match.group("value")
    exponent = raw_value.lower().split("e", 1)[1] if "e" in raw_value.lower() else None
    comparator = match.group("comparator") or "none"
    comparator = {"≤": "<=", "≥": ">=", "≈": "approximately", "~": "approximately"}.get(comparator, comparator)
    sign_token = match.group("sign")
    sign = "negative" if sign_token == "-" else "positive" if sign_token == "+" else "none"
    uncertainty = match.group("uncertainty")
    range_high = match.group("range_high")
    denominator = match.group("denominator")
    unit = match.group("unit")
    if unit:
        unit = unit.replace("μ", "µ")
    uncertainty_kind = (
        "plus_minus" if uncertainty else "range" if range_high else "ratio" if denominator else "none"
    )
    label = match.group("label")
    context_type = "p_value" if label else "percentage" if unit in {"%", "‰"} else "measurement" if unit else uncertainty_kind if uncertainty_kind != "none" else "number"
    value = _canonical_number(raw_value)
    return {
        "comparator": comparator,
        "sign": sign,
        "value": value,
        "exponent": exponent,
        "uncertainty_kind": uncertainty_kind,
        "uncertainty_value": _canonical_number(uncertainty),
        "range_low": value if range_high else None,
        "range_high": _canonical_number(range_high),
        "unit": unit,
        "numerator": value if denominator else None,
        "denominator": _canonical_number(denominator),
        "context_type": context_type,
    }


def _inside_citation(text: str, start: int, end: int) -> bool:
    left = text.rfind("[", 0, start + 1)
    closed = text.rfind("]", 0, start + 1)
    return left > closed and text.find("]", end) >= 0


def _reference_number(text: str, start: int) -> bool:
    return re.search(
        r"(?:extended\s+data\s+fig(?:ure)?|supplementary\s+(?:fig(?:ure)?|table)|"
        r"fig(?:ure)?|table|eq(?:uation)?|sec(?:tion)?|appendix)\.?\s*$",
        text[max(0, start - 48):start], re.IGNORECASE,
    ) is not None


def _status(raw: str, normalized: str) -> str:
    return "exact" if raw == normalized else "normalized_exact"


def _context(text: str, start: int, end: int) -> str:
    return text[max(0, start - 60):min(len(text), end + 60)]


def _term_matches(text: str, term: str, match_mode: str) -> Iterable[re.Match[str]]:
    escaped = re.escape(term)
    prefix = r"(?<!\w)" if term and term[0].isalnum() else ""
    suffix = r"(?!\w)" if term and term[-1].isalnum() else ""
    flags = 0 if match_mode == "case_sensitive" else re.IGNORECASE
    return re.finditer(prefix + escaped + suffix, text, flags)


def _terminology_entries(entries: list[dict[str, str]] | None) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for entry in entries or []:
        if not isinstance(entry, dict) or set(entry) != {"term", "match_mode"}:
            raise QCError("Each terminology entry requires only term and match_mode")
        term = entry.get("term")
        mode = entry.get("match_mode")
        if not isinstance(term, str) or not term.strip():
            raise QCError("Terminology term must be a non-empty string")
        if mode not in {"case_sensitive", "case_insensitive"}:
            raise QCError("Terminology match_mode must be case_sensitive or case_insensitive")
        normalized.append({"term": term.strip(), "match_mode": mode})
    return normalized


def extract_anchors(
    document_text: str,
    unit: dict[str, Any],
    side: str,
    file_id: str,
    terminology_terms: list[dict[str, str]],
) -> list[dict[str, Any]]:
    unit_text = unit["text"]
    drafts: list[dict[str, Any]] = []

    for match in NUMERIC_RE.finditer(unit_text):
        if _inside_citation(unit_text, match.start(), match.end()) or _reference_number(unit_text, match.start()):
            continue
        components = _numeric_components(match)
        normalized = json.dumps(components, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        drafts.append({"class": "numeric", "start": match.start(), "end": match.end(), "normalized": normalized, "numeric_components": components})

    for match in NUMERIC_CITATION_RE.finditer(unit_text):
        normalized = re.sub(r"\s+", "", match.group(0)).replace("–", "-")
        drafts.append({"class": "citation", "citation_style": "numeric_bracket", "start": match.start(), "end": match.end(), "normalized": normalized})

    for match in AUTHOR_YEAR_CITATION_RE.finditer(unit_text):
        normalized = re.sub(r"\s+", " ", match.group("body")).strip().casefold()
        drafts.append({"class": "citation", "citation_style": "author_year_parenthetical", "start": match.start(), "end": match.end(), "normalized": normalized})

    for match in REFERENCE_RE.finditer(unit_text):
        kind = re.sub(r"\s+", " ", match.group("kind").lower()).strip()
        if kind.startswith("extended data"):
            canonical_kind = "extended_data_figure"
        elif kind.startswith("supplementary") and "table" in kind:
            canonical_kind = "supplementary_table"
        elif kind.startswith("supplementary"):
            canonical_kind = "supplementary_figure"
        elif "table" in kind:
            canonical_kind = "table"
        elif "fig" in kind:
            canonical_kind = "figure"
        elif kind.startswith("sec"):
            canonical_kind = "section"
        elif kind.startswith("appendix"):
            canonical_kind = "appendix"
        else:
            canonical_kind = "equation"
        normalized = f"{canonical_kind}:{match.group('label').lower()}"
        drafts.append({"class": "reference", "reference_subtype": canonical_kind, "start": match.start(), "end": match.end(), "normalized": normalized})

    for match in PLACEHOLDER_RE.finditer(unit_text):
        normalized = re.sub(r"\s+", " ", match.group(0)).strip()
        drafts.append({"class": "placeholder", "start": match.start(), "end": match.end(), "normalized": normalized})

    unique_terms = {(item["term"], item["match_mode"]): item for item in terminology_terms}
    for term, match_mode in sorted(unique_terms, key=lambda value: (-len(value[0]), value[0].casefold(), value[1])):
        for match in _term_matches(unit_text, term, match_mode):
            normalized = re.sub(r"\s+", " ", match.group(0)).strip()
            if match_mode == "case_insensitive":
                normalized = normalized.casefold()
            drafts.append({
                "class": "terminology", "terminology_match_mode": match_mode,
                "start": match.start(), "end": match.end(), "normalized": normalized,
            })

    for signal_class, phrases in SEMANTIC_PATTERNS.items():
        for phrase in sorted(phrases, key=len, reverse=True):
            for match in re.finditer(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", unit_text, re.IGNORECASE):
                normalized = f"{signal_class}:{match.group(0).casefold()}"
                drafts.append({"class": "semantic_signal", "signal_class": signal_class, "start": match.start(), "end": match.end(), "normalized": normalized})

    drafts.sort(key=lambda item: (item["start"], item["end"], item["class"], item["normalized"]))
    class_counts: Counter[str] = Counter()
    anchors: list[dict[str, Any]] = []
    for draft in drafts:
        anchor_class = draft["class"]
        class_counts[anchor_class] += 1
        occurrence = class_counts[anchor_class]
        local_start, local_end = draft["start"], draft["end"]
        start, end = unit["start"] + local_start, unit["start"] + local_end
        raw = document_text[start:end]
        anchor_id = f"{side}:{anchor_class}:{unit['ordinal']}:{occurrence}"
        anchor = {
            "anchor_id": anchor_id,
            "anchor_class": anchor_class,
            "unit_id": unit["unit_id"],
            "raw_representation": raw,
            "normalized_representation": draft["normalized"],
            "occurrence_index": occurrence,
            "anchor_sha256": sha256_text(raw),
            "locator": make_locator(document_text, side, file_id, unit["unit_id"], start, end),
            "context_sha256": sha256_text(_context(document_text, start, end)),
            "extraction_status": _status(raw, draft["normalized"]),
            "extraction_support": {
                "method": f"deterministic_regex:{anchor_class}",
                "rule_version": RULESET_VERSION,
                "match_count": 1,
            },
            "frozen": False,
            "author_approval": "not_requested",
        }
        if "signal_class" in draft:
            anchor["signal_class"] = draft["signal_class"]
        if "citation_style" in draft:
            anchor["citation_style"] = draft["citation_style"]
        if "reference_subtype" in draft:
            anchor["reference_subtype"] = draft["reference_subtype"]
        if "terminology_match_mode" in draft:
            anchor["terminology_match_mode"] = draft["terminology_match_mode"]
        if "numeric_components" in draft:
            anchor["numeric_components"] = draft["numeric_components"]
        anchors.append(anchor)
    return anchors


def build_snapshot(
    input_path: Path,
    side: str,
    document_id: str,
    file_id: str | None = None,
    terminology_terms: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    if side not in {"source", "candidate"}:
        raise QCError("side must be source or candidate")
    raw_bytes = input_path.read_bytes()
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise QCError("Minimum extractor accepts UTF-8 plain text or Markdown only") from exc
    if input_path.suffix.lower() not in {".txt", ".md", ".markdown"}:
        raise QCError("Minimum extractor accepts only .txt, .md, or .markdown")
    file_id = file_id or f"{side}-file"
    terms = _terminology_entries(terminology_terms)
    units = split_units(text, side, file_id)
    anchors: list[dict[str, Any]] = []
    for unit in units:
        anchors.extend(extract_anchors(text, unit, side, file_id, terms))
    snapshot_id = f"snapshot:{document_id}:{side}"
    snapshot = _metadata("preservation-snapshot", "0.1.1", snapshot_id, [])
    categories = ["numeric", "citation", "reference", "placeholder", "semantic_signal"]
    if terms:
        categories.append("terminology")
    snapshot.update({
        "snapshot_id": snapshot_id,
        "side": side,
        "file_identity": {
            "file_id": file_id,
            "path": str(input_path.resolve()),
            "side": side,
            "format": "markdown" if input_path.suffix.lower() in {".md", ".markdown"} else "plain_text",
            "sha256": sha256_bytes(raw_bytes),
        },
        "document_id": document_id,
        "ruleset_version": RULESET_VERSION,
        "extracted_categories": categories,
        "citation_styles": ["numeric_bracket", "author_year_parenthetical"],
        "reference_subtypes": [
            "figure", "extended_data_figure", "supplementary_figure", "table",
            "supplementary_table", "equation", "section", "appendix",
        ],
        "units": [{"unit_id": item["unit_id"], "ordinal": item["ordinal"], "locator": item["locator"]} for item in units],
        "anchors": anchors,
    })
    return snapshot


def build_manifest(
    source_snapshot: dict[str, Any],
    candidate_snapshot: dict[str, Any],
    producer: str = "arbitrary_user_comparison",
    accept_one_to_one: bool = False,
    revision_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if source_snapshot.get("document_id") != candidate_snapshot.get("document_id"):
        raise QCError("Snapshots must use the same document_id")
    document_id = source_snapshot["document_id"]
    source_units = source_snapshot["units"]
    candidate_units = candidate_snapshot["units"]
    common = min(len(source_units), len(candidate_units))
    alignments: list[dict[str, Any]] = []
    for index in range(common):
        source_unit, candidate_unit = source_units[index], candidate_units[index]
        alignments.append({
            "alignment_id": f"alignment:{index + 1}",
            "source_unit_ids": [source_unit["unit_id"]],
            "candidate_unit_ids": [candidate_unit["unit_id"]],
            "source_locators": [source_unit["locator"]],
            "candidate_locators": [candidate_unit["locator"]],
            "alignment_type": "one_to_one",
            "alignment_origin": "deterministic_aligner",
            "review_status": "caller_accepted" if accept_one_to_one else "machine_proposed",
            "execution_support": "supported",
        })
    for source_unit in source_units[common:]:
        index = len(alignments) + 1
        alignments.append({
            "alignment_id": f"alignment:{index}",
            "source_unit_ids": [source_unit["unit_id"]],
            "candidate_unit_ids": [],
            "source_locators": [source_unit["locator"]],
            "candidate_locators": [],
            "alignment_type": "removed",
            "alignment_origin": "deterministic_aligner",
            "review_status": "machine_proposed",
            "execution_support": "unassessable",
        })
    for candidate_unit in candidate_units[common:]:
        index = len(alignments) + 1
        alignments.append({
            "alignment_id": f"alignment:{index}",
            "source_unit_ids": [],
            "candidate_unit_ids": [candidate_unit["unit_id"]],
            "source_locators": [],
            "candidate_locators": [candidate_unit["locator"]],
            "alignment_type": "added",
            "alignment_origin": "deterministic_aligner",
            "review_status": "machine_proposed",
            "execution_support": "unassessable",
        })
    manifest_id = f"manifest:{document_id}"
    manifest = _metadata(
        "comparison-manifest", "0.1.1", manifest_id,
        [source_snapshot["artifact_id"], candidate_snapshot["artifact_id"]],
    )
    # Mechanical construction and caller acceptance never create author approval for the artifact.
    manifest["status"] = "author_review_required"
    protected = sorted(set(source_snapshot["extracted_categories"]) & set(candidate_snapshot["extracted_categories"]))
    manifest.update({
        "manifest_id": manifest_id,
        "producer": producer,
        "source_file": source_snapshot["file_identity"],
        "candidate_file": candidate_snapshot["file_identity"],
        "comparison_scope": {
            "document_id": document_id,
            "unit_kind": "paragraph",
            "scope_description": "All paragraph units in both UTF-8 inputs",
        },
        "protected_categories": protected,
        "required_checks": list(CHECK_IDS),
        "optional_checks": [],
        "degraded_modes": [],
        "unit_alignments": alignments,
        "approved_exceptions": [],
        "upstream_baselines": [],
    })
    if revision_contract is not None:
        manifest["revision_contract"] = revision_contract
    return manifest


def _finding(
    manifest: dict[str, Any],
    source_snapshot: dict[str, Any],
    candidate_snapshot: dict[str, Any],
    finding_id: str,
    check_id: str,
    finding_class: str,
    severity: str,
    message: str,
    execution_state: str = "failed",
    finding_status: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    item = _metadata(
        "qc-finding", "0.3.0", finding_id,
        [manifest["artifact_id"], source_snapshot["artifact_id"], candidate_snapshot["artifact_id"]],
    )
    item["status"] = "author_review_required"
    item.update({
        "finding_id": finding_id,
        "check_id": check_id,
        "finding_class": finding_class,
        "severity": severity,
        "message": message,
        "evidence": fields.pop("evidence", []),
        "execution_state": execution_state,
        "finding_status": finding_status or ("author_review_required" if severity == "warning" else "open"),
    })
    item.update({key: value for key, value in fields.items() if value is not None})
    return item


def _alignment_shape_ok(alignment: dict[str, Any]) -> bool:
    shape = (len(alignment.get("source_unit_ids", [])), len(alignment.get("candidate_unit_ids", [])))
    kind = alignment.get("alignment_type")
    return {
        "one_to_one": shape == (1, 1),
        "split": shape[0] == 1 and shape[1] >= 2,
        "merge": shape[0] >= 2 and shape[1] == 1,
        "moved": shape == (1, 1),
        "added": shape[0] == 0 and shape[1] >= 1,
        "removed": shape[0] >= 1 and shape[1] == 0,
    }.get(kind, False)


def _exception_semantic_errors(exception: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    target_kind = exception.get("target_kind")
    if target_kind in {"anchor_id", "anchor_and_locator"} and not exception.get("anchor_id"):
        errors.append("anchor_id is required for this target_kind")
    if target_kind in {"locator", "anchor_and_locator"} and not exception.get("locator"):
        errors.append("locator is required for this target_kind")
    strings = [
        exception.get("expected_source_representation", ""),
        exception.get("approved_candidate_representation", ""),
    ]
    if any("*" in value or "?" in value for value in strings):
        errors.append("wildcard exception representations are prohibited")
    if exception.get("author_approval") != "approved":
        errors.append("exception is not author-approved")
    return errors


def _exact_exception(
    manifest: dict[str, Any],
    source_anchor: dict[str, Any],
    candidate_anchor: dict[str, Any],
) -> dict[str, Any] | None:
    for exception in manifest.get("approved_exceptions", []):
        if _exception_semantic_errors(exception):
            continue
        target_kind = exception["target_kind"]
        if target_kind in {"anchor_id", "anchor_and_locator"} and exception.get("anchor_id") != source_anchor["anchor_id"]:
            continue
        if target_kind in {"locator", "anchor_and_locator"} and exception.get("locator") != source_anchor["locator"]:
            continue
        if exception["expected_source_representation"] != source_anchor["raw_representation"]:
            continue
        if exception["approved_candidate_representation"] != candidate_anchor["raw_representation"]:
            continue
        if exception["source_sha256"].lower() != manifest["source_file"]["sha256"].lower():
            continue
        if exception["candidate_sha256"].lower() != manifest["candidate_file"]["sha256"].lower():
            continue
        if exception["candidate_anchor_sha256"].lower() != candidate_anchor["anchor_sha256"].lower():
            continue
        return exception
    return None


def _anchors_by_unit(snapshot: dict[str, Any]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for anchor in snapshot.get("anchors", []):
        grouped[anchor["unit_id"]][anchor["anchor_class"]].append(anchor)
    for unit_groups in grouped.values():
        for anchors in unit_groups.values():
            anchors.sort(key=lambda item: item["occurrence_index"])
    return grouped


def compare_snapshots(
    manifest: dict[str, Any],
    source_snapshot: dict[str, Any],
    candidate_snapshot: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(check_id: str, finding_class: str, severity: str, message: str, execution_state: str = "failed", **fields: Any) -> dict[str, Any]:
        finding_id = f"finding:{len(findings) + 1:04d}"
        item = _finding(
            manifest, source_snapshot, candidate_snapshot, finding_id,
            check_id, finding_class, severity, message, execution_state, **fields,
        )
        findings.append(item)
        return item

    if manifest.get("producer") == "article_polisher":
        contract = manifest.get("revision_contract")
        if contract is None:
            add("manifest_semantics", "execution", "blocker", "article_polisher output requires revision_contract")
        else:
            origin = contract.get("authorization_origin")
            state = contract.get("authorization_state")
            if state not in {"caller_accepted", "author_approved"}:
                add("manifest_semantics", "execution", "error", "revision_contract does not authorize comparison execution")
            if state == "author_approved" and origin != "author":
                add("manifest_semantics", "execution", "error", "author_approved requires authorization_origin author")
            if origin == "calling_workflow" and state == "author_approved":
                add("manifest_semantics", "execution", "error", "calling_workflow cannot create author_approved")
            if state == "author_approved" and contract.get("author_approval") != "approved":
                add("manifest_semantics", "execution", "error", "author_approved revision_contract lacks approved author decision")
            if state == "caller_accepted" and contract.get("author_approval") == "approved":
                add("manifest_semantics", "execution", "error", "caller_accepted cannot carry approved author decision")
            source_identity = source_snapshot.get("file_identity", {})
            if contract.get("source_artifact_id") != source_identity.get("file_id"):
                add("manifest_semantics", "execution", "error", "revision_contract source_artifact_id does not match source snapshot")
            if contract.get("source_artifact_sha256") != source_identity.get("sha256"):
                add("manifest_semantics", "execution", "error", "revision_contract source_artifact_sha256 does not match source snapshot")
            scope = contract.get("authorized_scope", {})
            if scope.get("document_id") != manifest.get("comparison_scope", {}).get("document_id"):
                add("manifest_semantics", "execution", "error", "revision_contract authorized scope does not match comparison document")

    for alignment in manifest.get("unit_alignments", []):
        if not _alignment_shape_ok(alignment):
            add("manifest_semantics", "alignment", "error", f"Invalid unit cardinality for {alignment.get('alignment_id')}")
        if len(alignment.get("source_unit_ids", [])) != len(alignment.get("source_locators", [])) or len(alignment.get("candidate_unit_ids", [])) != len(alignment.get("candidate_locators", [])):
            add("manifest_semantics", "alignment", "error", f"Unit/locator count mismatch for {alignment.get('alignment_id')}")
        for side in ("source", "candidate"):
            unit_ids = alignment.get(f"{side}_unit_ids", [])
            locators = alignment.get(f"{side}_locators", [])
            expected_file_id = manifest.get(f"{side}_file", {}).get("file_id")
            for index, locator in enumerate(locators):
                expected_unit_id = unit_ids[index] if index < len(unit_ids) else None
                if locator.get("side") != side or locator.get("unit_id") != expected_unit_id:
                    add("manifest_semantics", "alignment", "error", f"{alignment.get('alignment_id')} has a {side} locator/unit binding mismatch")
                if locator.get("locator_type") == "line_char_range" and locator.get("file_id") != expected_file_id:
                    add("manifest_semantics", "alignment", "error", f"{alignment.get('alignment_id')} has a {side} locator/file binding mismatch")

    for exception in manifest.get("approved_exceptions", []):
        for message in _exception_semantic_errors(exception):
            add("exception_validation", "exception", "error", f"{exception.get('exception_id')}: {message}")

    for baseline in manifest.get("upstream_baselines", []):
        if baseline.get("baseline_use") == "hard_constraint" and baseline.get("artifact_status") not in {"author_approved"}:
            add("upstream_baseline_semantics", "execution", "error", f"{baseline.get('artifact_id')} cannot be a hard constraint while {baseline.get('artifact_status')}")

    if source_snapshot.get("side") != "source" or source_snapshot.get("file_identity", {}).get("side") != "source":
        add("hash_identity", "identity", "error", "Source snapshot side identity is invalid")
    if candidate_snapshot.get("side") != "candidate" or candidate_snapshot.get("file_identity", {}).get("side") != "candidate":
        add("hash_identity", "identity", "error", "Candidate snapshot side identity is invalid")
    if manifest.get("source_file", {}).get("sha256", "").lower() != source_snapshot.get("file_identity", {}).get("sha256", "").lower():
        add("hash_identity", "identity", "blocker", "Manifest source hash does not match source snapshot")
    if manifest.get("candidate_file", {}).get("sha256", "").lower() != candidate_snapshot.get("file_identity", {}).get("sha256", "").lower():
        add("hash_identity", "identity", "blocker", "Manifest candidate hash does not match candidate snapshot")
    if source_snapshot.get("document_id") != candidate_snapshot.get("document_id") or manifest.get("comparison_scope", {}).get("document_id") != source_snapshot.get("document_id"):
        add("hash_identity", "identity", "error", "Document identities do not agree")

    source_units = {item["unit_id"] for item in source_snapshot.get("units", [])}
    candidate_units = {item["unit_id"] for item in candidate_snapshot.get("units", [])}
    covered_source: list[str] = []
    covered_candidate: list[str] = []
    for alignment in manifest.get("unit_alignments", []):
        covered_source.extend(alignment.get("source_unit_ids", []))
        covered_candidate.extend(alignment.get("candidate_unit_ids", []))
    for side, expected, covered in (("source", source_units, covered_source), ("candidate", candidate_units, covered_candidate)):
        duplicates = sorted(item for item, count in Counter(covered).items() if count > 1)
        missing = sorted(expected - set(covered))
        unknown = sorted(set(covered) - expected)
        if duplicates or missing or unknown:
            add("alignment_coverage", "alignment", "error", f"{side} alignment coverage invalid", evidence=[f"duplicates={duplicates}", f"missing={missing}", f"unknown={unknown}"])

    source_categories = set(source_snapshot.get("extracted_categories", []))
    candidate_categories = set(candidate_snapshot.get("extracted_categories", []))
    protected = set(manifest.get("protected_categories", []))
    unsupported = sorted(protected - source_categories | protected - candidate_categories | protected - SUPPORTED_CATEGORIES)
    if unsupported:
        add(
            "protected_anchor_comparison", "execution", "warning",
            f"Protected categories are not deterministically extractable on both sides: {unsupported}",
            execution_state="unassessable",
        )

    source_grouped = _anchors_by_unit(source_snapshot)
    candidate_grouped = _anchors_by_unit(candidate_snapshot)
    comparable_classes = sorted((protected & SUPPORTED_CATEGORIES) - {"semantic_signal"})
    comparable_alignments = []
    for alignment in manifest.get("unit_alignments", []):
        supported = alignment.get("alignment_type") == "one_to_one" and alignment.get("execution_support") == "supported"
        reviewed = alignment.get("review_status") in {"caller_accepted", "author_approved"}
        if supported and reviewed:
            comparable_alignments.append(alignment)
        else:
            add(
                "alignment_coverage", "alignment", "warning",
                f"{alignment.get('alignment_id')} is outside reviewed one_to_one execution support",
                execution_state="unassessable",
                source_locator=(alignment.get("source_locators") or [None])[0],
                candidate_locator=(alignment.get("candidate_locators") or [None])[0],
            )

    for alignment in comparable_alignments:
        source_unit = alignment["source_unit_ids"][0]
        candidate_unit = alignment["candidate_unit_ids"][0]
        for anchor_class in comparable_classes:
            source_anchors = source_grouped[source_unit].get(anchor_class, [])
            candidate_anchors = candidate_grouped[candidate_unit].get(anchor_class, [])
            pair_count = min(len(source_anchors), len(candidate_anchors))
            for index in range(pair_count):
                source_anchor, candidate_anchor = source_anchors[index], candidate_anchors[index]
                equivalent = (
                    source_anchor.get("numeric_components") == candidate_anchor.get("numeric_components")
                    if anchor_class == "numeric"
                    else source_anchor["normalized_representation"] == candidate_anchor["normalized_representation"]
                )
                if equivalent:
                    continue
                exception = _exact_exception(manifest, source_anchor, candidate_anchor)
                common = {
                    "source_locator": source_anchor["locator"],
                    "candidate_locator": candidate_anchor["locator"],
                    "expected_representation": source_anchor["raw_representation"],
                    "observed_representation": candidate_anchor["raw_representation"],
                }
                if exception:
                    add(
                        "exception_validation", "exception", "info",
                        f"Exact approved exception applied to {source_anchor['anchor_id']}",
                        execution_state="passed", finding_status="accepted",
                        exception_id=exception["exception_id"], **common,
                    )
                else:
                    add(
                        "protected_anchor_comparison", anchor_class, "error",
                        f"Protected {anchor_class} anchor changed in {alignment['alignment_id']}",
                        **common,
                    )
            for source_anchor in source_anchors[pair_count:]:
                add(
                    "protected_anchor_comparison", anchor_class, "error",
                    f"Protected {anchor_class} anchor was removed in {alignment['alignment_id']}",
                    source_locator=source_anchor["locator"],
                    expected_representation=source_anchor["raw_representation"],
                    observed_representation="",
                )
            for candidate_anchor in candidate_anchors[pair_count:]:
                add(
                    "protected_anchor_comparison", anchor_class, "error",
                    f"Protected {anchor_class} anchor was added in {alignment['alignment_id']}",
                    candidate_locator=candidate_anchor["locator"],
                    expected_representation="",
                    observed_representation=candidate_anchor["raw_representation"],
                )

        if "semantic_signal" in protected and "semantic_signal" in source_categories and "semantic_signal" in candidate_categories:
            source_signals = source_grouped[source_unit].get("semantic_signal", [])
            candidate_signals = candidate_grouped[candidate_unit].get("semantic_signal", [])
            source_sequence = [(item.get("signal_class"), item["normalized_representation"]) for item in source_signals]
            candidate_sequence = [(item.get("signal_class"), item["normalized_representation"]) for item in candidate_signals]
            if source_sequence != candidate_sequence:
                add(
                    "semantic_risk_localization", "semantic_signal", "warning",
                    f"Local semantic-risk signals changed in {alignment['alignment_id']}; lexical evidence alone is not a scientific verdict",
                    execution_state="failed",
                    source_locator=alignment["source_locators"][0],
                    candidate_locator=alignment["candidate_locators"][0],
                    evidence=[
                        "source_ordered=" + json.dumps(source_sequence, ensure_ascii=False),
                        "candidate_ordered=" + json.dumps(candidate_sequence, ensure_ascii=False),
                    ],
                )

    check_results: list[dict[str, Any]] = []
    required_checks = set(manifest.get("required_checks", []))
    requested_checks = list(dict.fromkeys(manifest.get("required_checks", []) + manifest.get("optional_checks", [])))
    for check_id in requested_checks:
        check_findings = [item for item in findings if item["check_id"] == check_id]
        if any(item["execution_state"] == "failed" for item in check_findings):
            state = "failed"
        elif any(item["execution_state"] == "unassessable" for item in check_findings):
            state = "unassessable"
        else:
            state = "passed"
        result = {
            "check_id": check_id,
            "required": check_id in required_checks,
            "execution_state": state,
            "finding_ids": [item["finding_id"] for item in check_findings],
        }
        if state == "unassessable":
            result["reason"] = "One or more declared inputs or alignments are outside minimum deterministic support"
        check_results.append(result)

    counts = {severity: sum(1 for item in findings if item["severity"] == severity) for severity in ("blocker", "error", "warning", "info")}
    unresolved = [item for item in findings if item["finding_status"] in {"open", "author_review_required"}]
    required_unassessable = any(item["required"] and item["execution_state"] in {"unassessable", "skipped_with_reason"} for item in check_results)
    if any(item["severity"] in {"blocker", "error"} for item in unresolved):
        outcome = "fail"
    elif required_unassessable:
        outcome = "unassessable"
    elif any(item["severity"] == "warning" for item in unresolved):
        outcome = "pass_with_warnings"
    else:
        outcome = "pass"
    report_id = f"report:{manifest['comparison_scope']['document_id']}"
    report = _metadata(
        "qc-report", "0.1.0", report_id,
        [manifest["artifact_id"], source_snapshot["artifact_id"], candidate_snapshot["artifact_id"]],
    )
    report["status"] = "author_review_required" if outcome != "pass" else "draft"
    report.update({
        "report_id": report_id,
        "manifest_id": manifest["manifest_id"],
        "source_sha256": source_snapshot["file_identity"]["sha256"],
        "candidate_sha256": candidate_snapshot["file_identity"]["sha256"],
        "validator_version": VALIDATOR_VERSION,
        "ruleset_version": RULESET_VERSION,
        "check_results": check_results,
        "finding_ids": [item["finding_id"] for item in findings],
        "finding_counts": counts,
        "gate_outcome": outcome,
        "human_review_required": outcome != "pass",
        "degraded_modes": list(manifest.get("degraded_modes", [])),
        "limitations": [
            "Minimum gate accepts UTF-8 plain text/Markdown only.",
            "Semantic-risk signals are local lexical warnings, not scientific conclusions.",
            "Numeric comparison is conservative and performs no automatic unit conversion.",
            "Only reviewed one_to_one alignments receive deterministic semantic comparison.",
        ],
        "human_decision_queue": [item["finding_id"] for item in unresolved],
    })
    return findings, report


def validate_snapshot_semantics(snapshot: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    side = snapshot.get("side")
    file_identity = snapshot.get("file_identity", {})
    if file_identity.get("side") != side:
        errors.append("file_identity.side must match snapshot.side")
    units = snapshot.get("units", [])
    unit_ids = [item.get("unit_id") for item in units]
    if len(unit_ids) != len(set(unit_ids)):
        errors.append("unit IDs must be unique")
    ordinals = [item.get("ordinal") for item in units]
    if ordinals != list(range(1, len(units) + 1)):
        errors.append("unit ordinals must be contiguous and ordered from 1")
    unit_set = set(unit_ids)
    seen_anchor_ids: set[str] = set()
    seen_occurrences: set[tuple[str, str, int]] = set()
    for anchor in snapshot.get("anchors", []):
        anchor_id = anchor.get("anchor_id")
        if anchor_id in seen_anchor_ids:
            errors.append(f"duplicate anchor_id: {anchor_id}")
        seen_anchor_ids.add(anchor_id)
        if anchor.get("unit_id") not in unit_set:
            errors.append(f"anchor {anchor_id} references unknown unit")
        locator = anchor.get("locator", {})
        if locator.get("side") != side or locator.get("file_id") != file_identity.get("file_id"):
            errors.append(f"anchor {anchor_id} locator identity mismatch")
        if locator.get("start_line", 1) > locator.get("end_line", 1) or locator.get("start_char", 0) > locator.get("end_char", 0):
            errors.append(f"anchor {anchor_id} locator range is reversed")
        if anchor.get("anchor_sha256") != sha256_text(anchor.get("raw_representation", "")):
            errors.append(f"anchor {anchor_id} hash does not match raw representation")
        occurrence_key = (anchor.get("unit_id"), anchor.get("anchor_class"), anchor.get("occurrence_index"))
        if occurrence_key in seen_occurrences:
            errors.append(f"duplicate occurrence index for {occurrence_key[:2]}")
        seen_occurrences.add(occurrence_key)
        if anchor.get("anchor_class") == "numeric" and "numeric_components" not in anchor:
            errors.append(f"numeric anchor {anchor_id} lacks numeric_components")
        if anchor.get("anchor_class") == "semantic_signal" and "signal_class" not in anchor:
            errors.append(f"semantic anchor {anchor_id} lacks signal_class")
        if anchor.get("anchor_class") == "citation" and "citation_style" not in anchor:
            errors.append(f"citation anchor {anchor_id} lacks citation_style")
        if anchor.get("anchor_class") == "reference" and "reference_subtype" not in anchor:
            errors.append(f"reference anchor {anchor_id} lacks reference_subtype")
        if anchor.get("anchor_class") == "terminology" and "terminology_match_mode" not in anchor:
            errors.append(f"terminology anchor {anchor_id} lacks terminology_match_mode")
    return errors


def validate_package_semantics(
    manifest: dict[str, Any],
    source_snapshot: dict[str, Any],
    candidate_snapshot: dict[str, Any],
    findings: list[dict[str, Any]],
    report: dict[str, Any],
) -> list[str]:
    errors = [f"source snapshot: {item}" for item in validate_snapshot_semantics(source_snapshot)]
    errors.extend(f"candidate snapshot: {item}" for item in validate_snapshot_semantics(candidate_snapshot))
    if manifest.get("manifest_id") != report.get("manifest_id"):
        errors.append("report.manifest_id does not match manifest")
    if manifest.get("source_file", {}).get("sha256") != source_snapshot.get("file_identity", {}).get("sha256"):
        errors.append("manifest/source snapshot hash mismatch")
    if manifest.get("candidate_file", {}).get("sha256") != candidate_snapshot.get("file_identity", {}).get("sha256"):
        errors.append("manifest/candidate snapshot hash mismatch")
    if report.get("source_sha256") != source_snapshot.get("file_identity", {}).get("sha256"):
        errors.append("report/source snapshot hash mismatch")
    if report.get("candidate_sha256") != candidate_snapshot.get("file_identity", {}).get("sha256"):
        errors.append("report/candidate snapshot hash mismatch")
    finding_ids = [item.get("finding_id") for item in findings]
    if len(finding_ids) != len(set(finding_ids)):
        errors.append("finding IDs are not unique")
    if report.get("finding_ids") != finding_ids:
        errors.append("report finding_ids do not exactly match ordered findings")
    expected_counts = {severity: sum(1 for item in findings if item.get("severity") == severity) for severity in ("blocker", "error", "warning", "info")}
    if report.get("finding_counts") != expected_counts:
        errors.append("report finding_counts do not match findings")
    declared_checks = set(manifest.get("required_checks", [])) | set(manifest.get("optional_checks", []))
    report_checks = {item.get("check_id") for item in report.get("check_results", [])}
    if declared_checks != report_checks:
        errors.append("report checks do not match manifest-declared checks")
    if any(item.get("check_id") not in report_checks for item in findings):
        errors.append("a finding references a check absent from report")
    for result in report.get("check_results", []):
        expected_ids = [item["finding_id"] for item in findings if item.get("check_id") == result.get("check_id")]
        if result.get("finding_ids") != expected_ids:
            errors.append(f"check {result.get('check_id')} finding_ids do not match findings")
    if report.get("gate_outcome") == "pass_with_warnings" and report.get("human_review_required") is not True:
        errors.append("pass_with_warnings requires human_review_required=true")
    if report.get("gate_outcome") == "pass" and report.get("human_review_required") is not False:
        errors.append("clean pass requires human_review_required=false")
    if report.get("gate_outcome") != "pass" and report.get("human_review_required") is not True:
        errors.append("non-pass outcome requires human_review_required=true")
    expected_queue = [
        item["finding_id"] for item in findings
        if item.get("finding_status") in {"open", "author_review_required"}
    ]
    if report.get("human_decision_queue") != expected_queue:
        errors.append("human_decision_queue does not exactly match unresolved findings")
    try:
        expected_findings, expected_report = compare_snapshots(
            manifest, source_snapshot, candidate_snapshot
        )
        finding_keys = (
            "finding_id", "check_id", "finding_class", "severity", "message",
            "source_locator", "candidate_locator", "expected_representation",
            "observed_representation", "evidence", "execution_state", "finding_status",
            "exception_id",
        )
        actual_view = [{key: item[key] for key in finding_keys if key in item} for item in findings]
        expected_view = [{key: item[key] for key in finding_keys if key in item} for item in expected_findings]
        if actual_view != expected_view:
            errors.append("findings do not match deterministic recomputation")
        report_keys = (
            "manifest_id", "source_sha256", "candidate_sha256", "validator_version",
            "ruleset_version", "check_results", "finding_ids", "finding_counts",
            "gate_outcome", "human_review_required", "degraded_modes", "limitations",
            "human_decision_queue",
        )
        actual_report_view = {key: report.get(key) for key in report_keys}
        expected_report_view = {key: expected_report.get(key) for key in report_keys}
        if actual_report_view != expected_report_view:
            errors.append("report decision fields do not match deterministic recomputation")
    except (KeyError, TypeError, QCError) as exc:
        errors.append(f"deterministic package recomputation failed: {exc}")
    return errors


def render_report(report: dict[str, Any], findings: list[dict[str, Any]]) -> str:
    lines = [
        "# Scientific Integrity QC Report",
        "",
        f"- Gate outcome: `{report['gate_outcome']}`",
        f"- Human review required: `{str(report['human_review_required']).lower()}`",
        f"- Manifest: `{report['manifest_id']}`",
        f"- Source SHA-256: `{report['source_sha256']}`",
        f"- Candidate SHA-256: `{report['candidate_sha256']}`",
        "",
        "## Check results",
        "",
        "| Check | Required | State | Findings |",
        "|---|---:|---|---:|",
    ]
    for item in report["check_results"]:
        lines.append(f"| `{item['check_id']}` | {item['required']} | `{item['execution_state']}` | {len(item['finding_ids'])} |")
    lines.extend(["", "## Findings", ""])
    if not findings:
        lines.append("No findings.")
    for item in findings:
        lines.extend([
            f"### {item['finding_id']} — {item['severity']}",
            "",
            item["message"],
            "",
            f"Check: `{item['check_id']}` · State: `{item['execution_state']}` · Status: `{item['finding_status']}`",
            "",
        ])
        if "expected_representation" in item or "observed_representation" in item:
            lines.append(f"Expected: `{item.get('expected_representation', '')}`  ")
            lines.append(f"Observed: `{item.get('observed_representation', '')}`")
            lines.append("")
    lines.extend(["## Limitations", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.append("")
    return "\n".join(lines)
