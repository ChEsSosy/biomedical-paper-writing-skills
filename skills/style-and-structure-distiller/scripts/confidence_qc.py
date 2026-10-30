"""Observable support evidence, deterministic distributions, and corpus-balance QC."""

from __future__ import annotations

import math
import random
import statistics
from collections import Counter
from typing import Any, Callable

from manifest import manifest_document, warning
from parsers import ParsedDocument


STRATUM_DIMENSIONS: dict[str, tuple[str, bool]] = {
    "journal": ("journal", False),
    "year": ("year", False),
    "domain": ("domains", True),
    "experiment_label": ("experiment_labels", True),
    "corpus_group": ("corpus_group", False),
    "lab_group": ("lab_group", False),
    "article_subtype": ("article_subtype", False),
    "journal_family": ("journal_family", False),
    "language": ("language", False),
    "source_type": ("source_type", False),
}


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def distribution(values: list[int | float]) -> dict[str, int | float]:
    numeric = [float(value) for value in values]
    if not numeric:
        return {"count": 0, "mean": 0.0, "median": 0.0, "p25": 0.0, "p75": 0.0, "minimum": 0.0, "maximum": 0.0}
    return {
        "count": len(numeric),
        "mean": round(statistics.mean(numeric), 6),
        "median": round(statistics.median(numeric), 6),
        "p25": round(percentile(numeric, 0.25), 6),
        "p75": round(percentile(numeric, 0.75), 6),
        "minimum": round(min(numeric), 6),
        "maximum": round(max(numeric), 6),
    }


def bootstrap_median_interval(values: list[float], iterations: int = 1000) -> dict[str, float | str]:
    if not values:
        return {"low": 0.0, "high": 0.0, "method": "fixed_seed_document_bootstrap_median_1000"}
    if len(values) == 1:
        value = round(float(values[0]), 6)
        return {"low": value, "high": value, "method": "fixed_seed_document_bootstrap_median_1000"}
    rng = random.Random(20260830)
    medians = [statistics.median(rng.choice(values) for _ in values) for _ in range(iterations)]
    return {
        "low": round(percentile(medians, 0.025), 6),
        "high": round(percentile(medians, 0.975), 6),
        "method": "fixed_seed_document_bootstrap_median_1000",
    }


def robust_dispersion(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    median = statistics.median(values)
    iqr = percentile(values, 0.75) - percentile(values, 0.25)
    return round(abs(iqr / median) if median else abs(iqr), 6)


def leave_one_out_median_shift(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    baseline = statistics.median(values)
    shifts = [abs(statistics.median(values[:index] + values[index + 1 :]) - baseline) for index in range(len(values))]
    return round(max(shifts), 6)


def _record_values(record: dict[str, Any], field: str, multi: bool) -> list[str]:
    raw = record.get(field)
    if multi:
        return [str(value) for value in raw or [] if str(value).strip()]
    if raw is None or str(raw).strip() == "":
        return []
    return [str(raw)]


def stratum_coverage(
    manifest: dict[str, Any],
    contributor_ids: list[str],
    all_document_ids: list[str],
) -> dict[str, dict[str, Any]]:
    contributor_set = set(contributor_ids)
    result: dict[str, dict[str, Any]] = {}
    for dimension, (field, multi) in STRATUM_DIMENSIONS.items():
        available_docs = 0
        all_strata: set[str] = set()
        represented: set[str] = set()
        contributor_counts: Counter[str] = Counter()
        for document_id in all_document_ids:
            record = manifest_document(manifest, document_id)
            values = _record_values(record, field, multi)
            if values:
                available_docs += 1
                all_strata.update(values)
                if document_id in contributor_set:
                    represented.update(values)
                    contributor_counts.update(set(values))
        contributor_assignments = sum(contributor_counts.values())
        shares = [count / contributor_assignments for count in contributor_counts.values()] if contributor_assignments else []
        effective = 1 / sum(share * share for share in shares) if shares else 0.0
        result[dimension] = {
            "available_document_count": available_docs,
            "represented_stratum_count": len(represented),
            "total_stratum_count": len(all_strata),
            "coverage_rate": round(len(represented) / len(all_strata), 6) if all_strata else 0.0,
            "contributor_count_by_stratum": dict(sorted(contributor_counts.items())),
            "minimum_contributor_count": min(contributor_counts.values(), default=0),
            "maximum_contributor_share": round(max(shares), 6) if shares else 0.0,
            "effective_stratum_count": round(effective, 6),
        }
    return result


def feature_support(
    feature_id: str,
    values_by_document: dict[str, float],
    documents_by_id: dict[str, ParsedDocument],
    manifest: dict[str, Any],
    all_document_ids: list[str],
) -> dict[str, Any]:
    contributor_ids = sorted(values_by_document)
    values = [float(values_by_document[document_id]) for document_id in contributor_ids]
    parser_documents = [documents_by_id[document_id] for document_id in contributor_ids]
    return {
        "feature_id": feature_id,
        "document_count": len(values),
        "document_coverage": round(len(values) / len(all_document_ids), 6),
        "value_summary": distribution(values),
        "bootstrap_95": bootstrap_median_interval(values),
        "between_document_dispersion": {
            "method": "robust_iqr_over_absolute_median",
            "value": robust_dispersion(values),
        },
        "leave_one_document_out_median_sensitivity": {
            "method": "max_leave_one_document_out_median_shift",
            "value": leave_one_out_median_shift(values),
        },
        "parser_support": {
            "format_prior": distribution([document.parser_format_prior for document in parser_documents]),
            "observed_parse_qc": {
                "heading_recognition_rate": distribution([
                    float(document.observed_parse_qc["heading_recognition_rate"]) for document in parser_documents
                ]),
                "fragment_paragraph_rate": distribution([
                    float(document.observed_parse_qc["fragment_paragraph_rate"]) for document in parser_documents
                ]),
                "reference_contamination_rate": distribution([
                    float(document.observed_parse_qc["reference_contamination_rate"]) for document in parser_documents
                ]),
            },
        },
        "stratum_coverage": stratum_coverage(manifest, contributor_ids, all_document_ids),
    }


def make_balance_dimensions(
    records: list[dict[str, Any]],
    dominance_threshold: float = 0.5,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    total = len(records)
    dimensions: dict[str, Any] = {}
    findings: list[dict[str, str]] = []
    for dimension, (field, multi) in STRATUM_DIMENSIONS.items():
        counts: Counter[str] = Counter()
        available = 0
        for record in records:
            values = _record_values(record, field, multi)
            if values:
                available += 1
                counts.update(set(values))
        missing = total - available
        assignments = sum(counts.values())
        proportions = [count / assignments for count in counts.values()] if assignments else []
        effective = 1 / sum(value * value for value in proportions) if proportions else 0.0
        max_rate = max((count / total for count in counts.values()), default=0.0) if total else 0.0
        dimensions[dimension] = {
            "multi_valued": multi,
            "available_document_count": available,
            "missing_document_count": missing,
            "stratum_count": len(counts),
            "effective_stratum_count": round(effective, 6),
            "max_stratum_document_rate": round(max_rate, 6),
            "strata": [
                {"stratum": name, "document_count": count, "document_rate": round(count / total, 6)}
                for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
            ],
        }
        if max_rate > dominance_threshold and counts:
            dominant_name, dominant_count = counts.most_common(1)[0]
            findings.append(
                warning(
                    f"dominant_{dimension}_stratum",
                    f"{dimension} stratum '{dominant_name}' covers {dominant_count}/{total} documents; inspect profile bias",
                )
            )
        if missing:
            findings.append(
                warning(
                    f"missing_{dimension}_metadata",
                    f"{missing}/{total} documents lack {dimension} metadata",
                    "info",
                )
            )
    return dimensions, findings


PROHIBITED_CONTENT_KEYS: dict[str, set[str]] = {
    "raw_passages": {"raw_text", "full_text", "paragraph_text", "caption_text", "text_excerpt", "passage_text"},
    "topic_lexicon": {"topic_lexicon", "topic_terms", "preferred_vocabulary"},
    "author_identity_features": {"author_identity_features", "author_voice_profile", "author_fingerprint"},
    "semantic_role_labels": {
        "semantic_role_labels", "semantic_roles", "rhetorical_roles", "evidence_roles", "architecture_annotations"
    },
}


def audit_prohibited_content(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    """Traverse generated payloads and report prohibited content-bearing fields."""
    findings: list[dict[str, str]] = []
    scanned_key_count = 0
    scanned_string_count = 0

    def visit(value: Any, path: str) -> None:
        nonlocal scanned_key_count, scanned_string_count
        if isinstance(value, dict):
            for key, child in value.items():
                scanned_key_count += 1
                normalized_key = str(key).strip().lower()
                for category, prohibited_keys in PROHIBITED_CONTENT_KEYS.items():
                    if normalized_key in prohibited_keys:
                        findings.append({"category": category, "path": f"{path}.{key}", "key": str(key)})
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
        elif isinstance(value, str):
            scanned_string_count += 1

    for index, artifact in enumerate(artifacts):
        visit(artifact, f"artifacts[{index}]")

    categories = {finding["category"] for finding in findings}
    return {
        "scanned_artifact_count": len(artifacts),
        "scanned_key_count": scanned_key_count,
        "scanned_string_count": scanned_string_count,
        "finding_count": len(findings),
        "findings": findings,
        "raw_passages_stored": "raw_passages" in categories,
        "topic_lexicon_stored": "topic_lexicon" in categories,
        "author_identity_features_stored": "author_identity_features" in categories,
        "semantic_role_labels_stored": "semantic_role_labels" in categories,
        "result": "author_review_required" if findings else "pass",
    }
