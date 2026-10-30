#!/usr/bin/env python3
"""Build an independent unit-level text and structural difference inventory.

The inventory is validator evidence, not a third business artifact. Candidate
lineage is checked against unique exact sentence matches when possible so a
declared Light operation cannot hide an observable sentence reorder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SECTIONS = {
    "title", "abstract", "introduction", "methods", "results", "discussion",
    "conclusion", "figure_legend", "supplement", "other",
}
PARAGRAPH_ORIGINS = {"author_supplied", "phase4_plan", "model_assisted_classification"}
REVIEW_STATES = {"machine_proposed", "caller_accepted", "author_approved", "rejected"}
DOCUMENT_SIDES = {"source", "candidate"}
LINEAGE_ORIGINS = {
    "deterministic_patch_layer", "author_supplied",
    "reviewed_upstream_locator_map", "model_declared",
}
TRUSTED_LINEAGE_ORIGINS = LINEAGE_ORIGINS - {"model_declared"}


class InventoryError(RuntimeError):
    """Raised when a structured document cannot support deterministic inventory."""


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def document_payload(document: dict[str, Any]) -> dict[str, Any]:
    """Return the exact versioned document payload covered by artifact_sha256."""
    return {key: value for key, value in document.items() if key != "artifact_sha256"}


def document_sha256(document: dict[str, Any]) -> str:
    return canonical_sha256(document_payload(document))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise InventoryError(f"Expected a JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_document(document: dict[str, Any], expected_side: str | None = None) -> list[str]:
    """Validate the minimum structured locator-map input used by this candidate."""
    issues: list[str] = []
    required = {
        "document_id", "artifact_id", "artifact_version", "artifact_sha256",
        "side", "document_type", "paragraphs",
    }
    missing = sorted(required - set(document))
    if missing:
        issues.append(f"document missing required fields: {missing}")
        return issues
    if document.get("document_type") != "original_article":
        issues.append("document_type must be original_article")
    side = document.get("side")
    if side not in DOCUMENT_SIDES:
        issues.append("side must be source or candidate")
    if expected_side and side != expected_side:
        issues.append(f"expected side {expected_side}; got {side}")
    for field in ("document_id", "artifact_id", "artifact_version", "artifact_sha256"):
        if not _nonempty_string(document.get(field)):
            issues.append(f"document {field} must be a non-empty string")
    if isinstance(document.get("artifact_sha256"), str) and document["artifact_sha256"] != document_sha256(document):
        issues.append("artifact_sha256 does not match the canonical document payload")
    paragraphs = document.get("paragraphs")
    if not isinstance(paragraphs, list) or not paragraphs:
        issues.append("paragraphs must be a non-empty array")
        return issues

    paragraph_ids: set[str] = set()
    sentence_ids: set[str] = set()
    paragraph_ordinals: list[int] = []
    for index, paragraph in enumerate(paragraphs):
        path = f"paragraphs[{index}]"
        if not isinstance(paragraph, dict):
            issues.append(f"{path} must be an object")
            continue
        for field in (
            "unit_id", "source_unit_ids", "ordinal", "section", "paragraph_function",
            "experiment_labels", "text", "locator", "sentences",
        ):
            if field not in paragraph:
                issues.append(f"{path} missing {field}")
        unit_id = paragraph.get("unit_id")
        if not _nonempty_string(unit_id):
            issues.append(f"{path}.unit_id must be non-empty")
        elif unit_id in paragraph_ids:
            issues.append(f"duplicate paragraph unit_id: {unit_id}")
        else:
            paragraph_ids.add(unit_id)
        ordinal = paragraph.get("ordinal")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 1:
            issues.append(f"{path}.ordinal must be a positive integer")
        else:
            paragraph_ordinals.append(ordinal)
        if paragraph.get("section") not in SECTIONS:
            issues.append(f"{path}.section is unsupported")
        lineage = paragraph.get("source_unit_ids")
        if not isinstance(lineage, list) or not all(_nonempty_string(item) for item in lineage):
            issues.append(f"{path}.source_unit_ids must be an array of identifiers")
        elif side == "source" and lineage != [unit_id]:
            issues.append(f"{path}.source_unit_ids must bind a source paragraph to itself")
        elif side == "candidate" and not lineage:
            issues.append(f"{path}.source_unit_ids must not be empty")
        paragraph_function = paragraph.get("paragraph_function")
        if not isinstance(paragraph_function, dict):
            issues.append(f"{path}.paragraph_function must be an object")
        else:
            if not _nonempty_string(paragraph_function.get("label")):
                issues.append(f"{path}.paragraph_function.label must be non-empty")
            if paragraph_function.get("origin") not in PARAGRAPH_ORIGINS:
                issues.append(f"{path}.paragraph_function.origin is unsupported")
            if paragraph_function.get("review_status") not in REVIEW_STATES:
                issues.append(f"{path}.paragraph_function.review_status is unsupported")
        if not isinstance(paragraph.get("experiment_labels"), list):
            issues.append(f"{path}.experiment_labels must be an array")
        if not isinstance(paragraph.get("text"), str):
            issues.append(f"{path}.text must be a string")
        locator = paragraph.get("locator")
        if not isinstance(locator, dict):
            issues.append(f"{path}.locator must be an object")
        else:
            expected_locator = {
                "locator_type": "structured_unit",
                "side": side,
                "artifact_id": document.get("artifact_id"),
                "unit_id": unit_id,
            }
            for field, expected in expected_locator.items():
                if locator.get(field) != expected:
                    issues.append(f"{path}.locator.{field} does not match its document/unit identity")
            if not _nonempty_string(locator.get("local_identifier")):
                issues.append(f"{path}.locator.local_identifier must be non-empty")
            if isinstance(paragraph.get("text"), str) and locator.get("span_sha256") != text_sha256(paragraph["text"]):
                issues.append(f"{path}.locator.span_sha256 does not match paragraph text")
        sentences = paragraph.get("sentences")
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
            for field in ("unit_id", "source_unit_ids", "ordinal", "text"):
                if field not in sentence:
                    issues.append(f"{sentence_path} missing {field}")
            sentence_id = sentence.get("unit_id")
            if not _nonempty_string(sentence_id):
                issues.append(f"{sentence_path}.unit_id must be non-empty")
            elif sentence_id in sentence_ids:
                issues.append(f"duplicate sentence unit_id: {sentence_id}")
            else:
                sentence_ids.add(sentence_id)
            sentence_ordinal = sentence.get("ordinal")
            if not isinstance(sentence_ordinal, int) or isinstance(sentence_ordinal, bool) or sentence_ordinal < 1:
                issues.append(f"{sentence_path}.ordinal must be a positive integer")
            else:
                sentence_ordinals.append(sentence_ordinal)
            sentence_lineage = sentence.get("source_unit_ids")
            if not isinstance(sentence_lineage, list) or not all(_nonempty_string(item) for item in sentence_lineage):
                issues.append(f"{sentence_path}.source_unit_ids must be an array of identifiers")
            elif side == "source" and sentence_lineage != [sentence_id]:
                issues.append(f"{sentence_path}.source_unit_ids must bind a source sentence to itself")
            elif side == "candidate" and not sentence_lineage:
                issues.append(f"{sentence_path}.source_unit_ids must not be empty")
            if not isinstance(sentence.get("text"), str):
                issues.append(f"{sentence_path}.text must be a string")
            else:
                combined.append(sentence["text"])
        if sentence_ordinals and sentence_ordinals != list(range(1, len(sentence_ordinals) + 1)):
            issues.append(f"{path}.sentences ordinals must be contiguous and ordered")
        if isinstance(paragraph.get("text"), str) and " ".join(combined).strip() != paragraph["text"].strip():
            issues.append(f"{path}.text must equal the ordered sentence texts joined by one space")
    if paragraph_ordinals and paragraph_ordinals != list(range(1, len(paragraph_ordinals) + 1)):
        issues.append("paragraph ordinals must be contiguous and ordered")
    return issues


def artifact_identity(document: dict[str, Any]) -> dict[str, str]:
    """Return the exact document identity used to bind trusted lineage evidence."""
    return {
        "document_id": document.get("document_id"),
        "artifact_id": document.get("artifact_id"),
        "artifact_version": document.get("artifact_version"),
        "artifact_sha256": document.get("artifact_sha256"),
    }


def declared_lineage_map(
    source: dict[str, Any],
    candidate: dict[str, Any],
    origin: str = "model_declared",
) -> dict[str, Any]:
    """Materialize lineage as a separate, hash-bound validator input.

    Callers may use this helper only after the mapping was produced or reviewed
    outside the generative candidate. Merely changing ``origin`` does not turn
    model output into trusted provenance.
    """
    return {
        "lineage_map_name": "article_polisher_lineage_map",
        "lineage_map_version": "0.1.0",
        "origin": origin,
        "source_artifact": artifact_identity(source),
        "candidate_artifact": artifact_identity(candidate),
        "paragraph_lineage": [
            {
                "candidate_unit_id": paragraph["unit_id"],
                "source_unit_ids": list(paragraph.get("source_unit_ids", [])),
            }
            for paragraph in candidate.get("paragraphs", [])
        ],
        "sentence_lineage": [
            {
                "candidate_unit_id": sentence["unit_id"],
                "source_unit_ids": list(sentence.get("source_unit_ids", [])),
            }
            for paragraph in candidate.get("paragraphs", [])
            for sentence in paragraph.get("sentences", [])
        ],
    }


def validate_lineage_map(
    source: dict[str, Any],
    candidate: dict[str, Any],
    lineage_map: dict[str, Any] | None,
) -> list[dict[str, str]]:
    """Validate cross-document lineage and its separate trust boundary."""
    issues: list[dict[str, str]] = []

    def add(code: str, message: str) -> None:
        issues.append({"code": code, "message": message})

    source_paragraphs = {item.get("unit_id"): item for item in source.get("paragraphs", [])}
    source_sentence_parent = {
        sentence.get("unit_id"): paragraph.get("unit_id")
        for paragraph in source.get("paragraphs", [])
        for sentence in paragraph.get("sentences", [])
    }
    candidate_paragraphs = {item.get("unit_id"): item for item in candidate.get("paragraphs", [])}
    candidate_sentences = {
        sentence.get("unit_id"): (paragraph, sentence)
        for paragraph in candidate.get("paragraphs", [])
        for sentence in paragraph.get("sentences", [])
    }

    if lineage_map is None:
        add("lineage:missing_trusted_map", "a separate trusted lineage map is required for package admission")
        lineage_map = declared_lineage_map(source, candidate)
    if lineage_map.get("lineage_map_name") != "article_polisher_lineage_map":
        add("lineage:identity", "lineage_map_name is unsupported")
    if lineage_map.get("lineage_map_version") != "0.1.0":
        add("lineage:identity", "lineage_map_version is unsupported")
    origin = lineage_map.get("origin")
    if origin not in LINEAGE_ORIGINS:
        add("lineage:origin", "lineage origin is unsupported")
    elif origin not in TRUSTED_LINEAGE_ORIGINS:
        add("lineage:untrusted", "model-declared lineage cannot establish deterministic structural admission")
    if lineage_map.get("source_artifact") != artifact_identity(source):
        add("lineage:source_binding", "lineage map does not bind the exact source artifact")
    if lineage_map.get("candidate_artifact") != artifact_identity(candidate):
        add("lineage:candidate_binding", "lineage map does not bind the exact candidate artifact")

    def index_entries(field: str) -> dict[str, list[str]]:
        raw = lineage_map.get(field)
        if not isinstance(raw, list):
            add("lineage:shape", f"{field} must be an array")
            return {}
        indexed: dict[str, list[str]] = {}
        for index, item in enumerate(raw):
            if not isinstance(item, dict) or not _nonempty_string(item.get("candidate_unit_id")):
                add("lineage:shape", f"{field}[{index}] lacks candidate_unit_id")
                continue
            candidate_id = item["candidate_unit_id"]
            source_ids = item.get("source_unit_ids")
            if not isinstance(source_ids, list) or not source_ids or not all(_nonempty_string(value) for value in source_ids):
                add("lineage:shape", f"{field}[{index}].source_unit_ids must be a non-empty identifier array")
                continue
            if candidate_id in indexed:
                add("lineage:duplicate", f"duplicate lineage for candidate unit {candidate_id}")
                continue
            indexed[candidate_id] = list(source_ids)
        return indexed

    paragraph_map = index_entries("paragraph_lineage")
    sentence_map = index_entries("sentence_lineage")
    if set(paragraph_map) != set(candidate_paragraphs):
        add("lineage:paragraph_coverage", "paragraph lineage must cover every candidate paragraph exactly once")
    if set(sentence_map) != set(candidate_sentences):
        add("lineage:sentence_coverage", "sentence lineage must cover every candidate sentence exactly once")

    for candidate_id, source_ids in paragraph_map.items():
        paragraph = candidate_paragraphs.get(candidate_id)
        if paragraph is not None and source_ids != paragraph.get("source_unit_ids"):
            add("lineage:candidate_conflict", f"trusted lineage conflicts with candidate paragraph declaration: {candidate_id}")
        unknown = sorted(set(source_ids) - set(source_paragraphs))
        if unknown:
            add("lineage:unknown_paragraph", f"candidate paragraph {candidate_id} references unknown source paragraphs: {unknown}")

    for candidate_id, source_ids in sentence_map.items():
        candidate_pair = candidate_sentences.get(candidate_id)
        if candidate_pair is None:
            continue
        paragraph, sentence = candidate_pair
        if source_ids != sentence.get("source_unit_ids"):
            add("lineage:candidate_conflict", f"trusted lineage conflicts with candidate sentence declaration: {candidate_id}")
        unknown = sorted(set(source_ids) - set(source_sentence_parent))
        if unknown:
            add("lineage:unknown_sentence", f"candidate sentence {candidate_id} references unknown source sentences: {unknown}")
            continue
        paragraph_closure = set(paragraph_map.get(paragraph.get("unit_id"), []))
        outside = sorted(
            source_id for source_id in source_ids
            if source_sentence_parent.get(source_id) not in paragraph_closure
        )
        if outside:
            add("lineage:paragraph_closure", f"candidate sentence {candidate_id} escapes its source-paragraph closure: {outside}")
    return issues


def _normalized_sentence(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _source_sentence_map(source_paragraphs: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_text: dict[str, list[str]] = defaultdict(list)
    for paragraph in source_paragraphs:
        for sentence in paragraph["sentences"]:
            by_id[sentence["unit_id"]] = sentence
            by_text[_normalized_sentence(sentence["text"])].append(sentence["unit_id"])
    return by_id, by_text


def _observed_sentence_lineage(
    sentence: dict[str, Any],
    source_by_text: dict[str, list[str]],
) -> tuple[list[str], bool]:
    """Prefer independently observable unique exact matches over declared lineage."""
    exact = source_by_text.get(_normalized_sentence(sentence["text"]), [])
    declared = list(sentence.get("source_unit_ids", []))
    if len(exact) == 1:
        return exact, declared != exact
    return declared, False


def _inversion(values: list[int]) -> bool:
    return any(left > right for left, right in zip(values, values[1:]))


def _inventory_change_id(payload: dict[str, Any]) -> str:
    return f"inventory-change:{canonical_sha256(payload)[:24]}"


def build_inventory(
    source: dict[str, Any],
    candidate: dict[str, Any],
    lineage_map: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build deterministic changed-unit records and observable structural effects."""
    source_paragraphs = sorted(source["paragraphs"], key=lambda item: item["ordinal"])
    candidate_paragraphs = sorted(candidate["paragraphs"], key=lambda item: item["ordinal"])
    source_by_id = {item["unit_id"]: item for item in source_paragraphs}
    source_position = {item["unit_id"]: index for index, item in enumerate(source_paragraphs)}
    source_sentence_by_id, source_sentence_by_text = _source_sentence_map(source_paragraphs)

    paragraph_references: Counter[str] = Counter(
        source_id
        for paragraph in candidate_paragraphs
        for source_id in paragraph.get("source_unit_ids", [])
        if source_id in source_by_id
    )
    split_source_ids = {source_id for source_id, count in paragraph_references.items() if count > 1}
    removed_source_ids = {source_id for source_id in source_by_id if paragraph_references[source_id] == 0}

    one_to_one_sequence = [
        paragraph["source_unit_ids"][0]
        for paragraph in candidate_paragraphs
        if len(paragraph.get("source_unit_ids", [])) == 1
        and paragraph["source_unit_ids"][0] in source_by_id
    ]
    one_to_one_positions = [source_position[item] for item in one_to_one_sequence]
    paragraph_order_changed = _inversion(one_to_one_positions)
    moved_source_ids = set(one_to_one_sequence) if paragraph_order_changed else set()

    changed_units: list[dict[str, Any]] = []
    lineage_conflicts: list[dict[str, str]] = []
    for paragraph in candidate_paragraphs:
        source_ids = [item for item in paragraph.get("source_unit_ids", []) if item in source_by_id]
        source_group = [source_by_id[item] for item in sorted(source_ids, key=lambda item: source_position[item])]
        source_text = "\n\n".join(item["text"] for item in source_group)
        candidate_text = paragraph["text"]
        effects: set[str] = set()
        if source_text != candidate_text:
            effects.add("text_changed")
        if not source_ids:
            effects.add("unit_added")
        if len(source_ids) > 1:
            effects.add("paragraph_merge")
        if any(item in split_source_ids for item in source_ids):
            effects.add("paragraph_split")
        if any(item in moved_source_ids for item in source_ids):
            effects.add("paragraph_move")
        if any(source_by_id[item]["section"] != paragraph["section"] for item in source_ids):
            effects.add("section_membership_changed")

        source_sentence_ids = [
            sentence["unit_id"]
            for source_paragraph in source_group
            for sentence in source_paragraph["sentences"]
        ]
        source_sentence_position = {item: index for index, item in enumerate(source_sentence_ids)}
        observed_candidate_lineages: list[list[str]] = []
        for sentence in paragraph["sentences"]:
            observed, conflict = _observed_sentence_lineage(sentence, source_sentence_by_text)
            observed_candidate_lineages.append(observed)
            if conflict:
                lineage_conflicts.append({
                    "candidate_sentence_id": sentence["unit_id"],
                    "declared_source_sentence_ids": ",".join(sentence.get("source_unit_ids", [])),
                    "observed_source_sentence_ids": ",".join(observed),
                })
                effects.add("sentence_lineage_conflict")
        sentence_reference_counts = Counter(
            source_id
            for lineage in observed_candidate_lineages
            for source_id in lineage
            if source_id in source_sentence_by_id
        )
        if any(count > 1 for count in sentence_reference_counts.values()):
            effects.add("sentence_split")
        if any(len([item for item in lineage if item in source_sentence_by_id]) > 1 for lineage in observed_candidate_lineages):
            effects.add("sentence_merge")
        mapped_sentence_positions = [
            source_sentence_position[lineage[0]]
            for lineage in observed_candidate_lineages
            if len(lineage) == 1 and lineage[0] in source_sentence_position
        ]
        if _inversion(mapped_sentence_positions):
            effects.add("sentence_order_changed")
        if len(source_sentence_ids) != len(paragraph["sentences"]):
            effects.add("sentence_count_changed")

        if effects:
            source_hash = text_sha256(source_text)
            candidate_hash = text_sha256(candidate_text)
            identity_payload = {
                "source_unit_ids": source_ids,
                "candidate_unit_ids": [paragraph["unit_id"]],
                "source_representation_sha256": source_hash,
                "candidate_representation_sha256": candidate_hash,
                "observed_effects": sorted(effects),
            }
            changed_units.append({
                "inventory_change_id": _inventory_change_id(identity_payload),
                **identity_payload,
                "source_locators": [item["locator"] for item in source_group],
                "candidate_locators": [paragraph["locator"]],
                "section": paragraph["section"],
                "paragraph_function": paragraph["paragraph_function"],
                "experiment_labels": paragraph["experiment_labels"],
            })

    for source_id in sorted(removed_source_ids, key=lambda item: source_position[item]):
        paragraph = source_by_id[source_id]
        effects = ["unit_removed"]
        identity_payload = {
            "source_unit_ids": [source_id],
            "candidate_unit_ids": [],
            "source_representation_sha256": text_sha256(paragraph["text"]),
            "candidate_representation_sha256": text_sha256(""),
            "observed_effects": effects,
        }
        changed_units.append({
            "inventory_change_id": _inventory_change_id(identity_payload),
            **identity_payload,
            "source_locators": [paragraph["locator"]],
            "candidate_locators": [],
            "section": paragraph["section"],
            "paragraph_function": paragraph["paragraph_function"],
            "experiment_labels": paragraph["experiment_labels"],
        })

    observed = {effect for item in changed_units for effect in item["observed_effects"]}
    footprint = {
        "paragraph_count_changed": len(source_paragraphs) != len(candidate_paragraphs),
        "paragraph_order_changed": paragraph_order_changed,
        "sentence_count_changed": "sentence_count_changed" in observed,
        "sentence_order_changed": "sentence_order_changed" in observed,
        "section_membership_changed": "section_membership_changed" in observed,
        "unit_split": bool({"paragraph_split", "sentence_split"} & observed),
        "unit_merge": bool({"paragraph_merge", "sentence_merge"} & observed),
        "unit_move": "paragraph_move" in observed,
        "unit_added": "unit_added" in observed,
        "unit_removed": "unit_removed" in observed,
    }
    return {
        "inventory_name": "article_polisher_change_inventory",
        "inventory_version": "0.1.1",
        "lineage_provenance": {
            "origin": (lineage_map or {}).get("origin", "model_declared"),
            "source_artifact": artifact_identity(source),
            "candidate_artifact": artifact_identity(candidate),
        },
        "source_artifact": {
            "document_id": source["document_id"],
            "artifact_id": source["artifact_id"],
            "artifact_version": source["artifact_version"],
            "artifact_sha256": source["artifact_sha256"],
        },
        "candidate_artifact": {
            "document_id": candidate["document_id"],
            "artifact_id": candidate["artifact_id"],
            "artifact_version": candidate["artifact_version"],
            "artifact_sha256": candidate["artifact_sha256"],
        },
        "structural_footprint": footprint,
        "lineage_conflicts": lineage_conflicts,
        "changed_units": changed_units,
    }


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
        lineage_map = read_json(args.lineage_map)
        issues = validate_document(source, "source") + validate_document(candidate, "candidate")
        if source.get("document_id") != candidate.get("document_id"):
            issues.append("source and candidate document_id values differ")
        issues.extend(item["message"] for item in validate_lineage_map(source, candidate, lineage_map))
        if issues:
            for issue in issues:
                print(f"inventory input error: {issue}", file=sys.stderr)
            return 1
        write_json(args.output, build_inventory(source, candidate, lineage_map))
    except (OSError, json.JSONDecodeError, InventoryError) as exc:
        print(f"inventory error: {exc}", file=sys.stderr)
        return 2
    print(f"WROTE: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
