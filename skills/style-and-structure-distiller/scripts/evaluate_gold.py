#!/usr/bin/env python3
"""Evaluate observable parser output against a manually approved gold standard."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from manifest import envelope, load_shared_validator, safe_identifier, validate_payload_file, write_json_new


def _precision_recall(predicted: Counter[Any], expected: Counter[Any]) -> dict[str, int | float]:
    true_positive = sum((predicted & expected).values())
    false_positive = sum((predicted - expected).values())
    false_negative = sum((expected - predicted).values())
    return _precision_recall_counts(true_positive, false_positive, false_negative)


def _precision_recall_counts(true_positive: int, false_positive: int, false_negative: int) -> dict[str, int | float]:
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = round(true_positive / precision_denominator, 6) if precision_denominator else 1.0
    recall = round(true_positive / recall_denominator, 6) if recall_denominator else 1.0
    f1 = round(2 * precision * recall / (precision + recall), 6) if precision + recall else 0.0
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _accuracy(correct: int, evaluated: int) -> dict[str, int | float]:
    return {"correct": correct, "evaluated": evaluated, "accuracy": round(correct / evaluated, 6) if evaluated else 1.0}


def _exact_match(correct: int, evaluated: int) -> dict[str, int | float]:
    return {
        "correct": correct,
        "evaluated": evaluated,
        "exact_match_rate": round(correct / evaluated, 6) if evaluated else 1.0,
    }


def _locator_identity(locator: dict[str, Any]) -> tuple[Any, ...]:
    try:
        locator_type = locator["locator_type"]
        if locator_type == "line_char_range":
            position = (locator["start_char"], locator["end_char"])
        elif locator_type == "xml_path":
            position = (locator["xml_path"],)
        elif locator_type == "html_dom_path":
            position = (locator["dom_path"], locator["source_anchor_order"])
        elif locator_type == "pdf_page_line_range":
            position = (
                locator["page_start"],
                locator["page_end"],
                locator["extracted_start_line"],
                locator["extracted_end_line"],
            )
        else:
            raise RuntimeError(f"Unsupported source locator type: {locator_type}")
        return (locator_type, *position, locator["source_span_sha256"])
    except KeyError as exc:
        raise RuntimeError(f"Incomplete {locator.get('locator_type', 'unknown')} source locator: missing {exc.args[0]}") from exc


def _comparable_interval(locator: dict[str, Any]) -> tuple[str, tuple[int, ...], tuple[int, ...]] | None:
    """Return a source-order interval when the locator exposes comparable coordinates."""
    locator_type = locator["locator_type"]
    if locator_type == "line_char_range":
        return locator_type, (locator["start_char"],), (locator["end_char"],)
    if locator_type == "html_dom_path":
        return (
            locator_type,
            (locator["start_line"], locator["start_column"]),
            (locator["end_line"], locator["end_column"]),
        )
    if locator_type == "pdf_page_line_range":
        return (
            locator_type,
            (locator["extracted_start_line"],),
            (locator["extracted_end_line"] + 1,),
        )
    return None


def _intervals_overlap(
    first: tuple[str, tuple[int, ...], tuple[int, ...]],
    second: tuple[str, tuple[int, ...], tuple[int, ...]],
) -> bool:
    return first[0] == second[0] and first[1] < second[2] and second[1] < first[2]


def _boundary_topology(
    expected_items: list[dict[str, Any]],
    predicted_items: list[dict[str, Any]],
) -> dict[str, int | float]:
    """Separate ordered boundary shifts from true one-to-many splits and many-to-one merges."""
    expected = [
        (index, item["source_locator"], _comparable_interval(item["source_locator"]))
        for index, item in enumerate(expected_items)
    ]
    predicted = [
        (index, item["source_locator"], _comparable_interval(item["source_locator"]))
        for index, item in enumerate(predicted_items)
    ]
    topology_expected_count = sum(interval is not None for _, _, interval in expected)
    classified_expected: set[int] = set()
    classified_predicted: set[int] = set()
    fragmented_expected: set[int] = set()
    merged_expected: set[int] = set()
    shifted_pairs = 0

    locator_types = sorted({interval[0] for _, _, interval in expected + predicted if interval is not None})
    for locator_type in locator_types:
        expected_group = sorted(
            [item for item in expected if item[2] is not None and item[2][0] == locator_type],
            key=lambda item: item[2][1],
        )
        predicted_group = sorted(
            [item for item in predicted if item[2] is not None and item[2][0] == locator_type],
            key=lambda item: item[2][1],
        )

        # Equal-length, source-ordered, one-to-one overlaps are boundary shifts,
        # not simultaneous fragmentation and merge events.
        if len(expected_group) == len(predicted_group) and all(
            _intervals_overlap(expected_item[2], predicted_item[2])
            for expected_item, predicted_item in zip(expected_group, predicted_group)
        ):
            for expected_item, predicted_item in zip(expected_group, predicted_group):
                if expected_item[2][1:] != predicted_item[2][1:]:
                    shifted_pairs += 1
                    classified_expected.add(expected_item[0])
                    classified_predicted.add(predicted_item[0])
            continue

        overlaps_by_expected: dict[int, list[int]] = {}
        overlaps_by_predicted: dict[int, list[int]] = {}
        for expected_item in expected_group:
            for predicted_item in predicted_group:
                if _intervals_overlap(expected_item[2], predicted_item[2]):
                    overlaps_by_expected.setdefault(expected_item[0], []).append(predicted_item[0])
                    overlaps_by_predicted.setdefault(predicted_item[0], []).append(expected_item[0])
        for expected_index, predicted_indexes in overlaps_by_expected.items():
            if len(predicted_indexes) >= 2:
                fragmented_expected.add(expected_index)
                classified_expected.add(expected_index)
                classified_predicted.update(predicted_indexes)
        for predicted_index, expected_indexes in overlaps_by_predicted.items():
            if len(expected_indexes) >= 2:
                merged_expected.update(expected_indexes)
                classified_expected.update(expected_indexes)
                classified_predicted.add(predicted_index)

    expected_identities = {_locator_identity(locator) for _, locator, _ in expected}
    predicted_identities = {_locator_identity(locator) for _, locator, _ in predicted}
    unclassifiable = sum(
        1
        for index, locator, _ in expected
        if _locator_identity(locator) not in predicted_identities and index not in classified_expected
    ) + sum(
        1
        for index, locator, _ in predicted
        if _locator_identity(locator) not in expected_identities and index not in classified_predicted
    )
    denominator = topology_expected_count
    return {
        "topology_evaluable_expected_count": topology_expected_count,
        "fragmented_gold_paragraph_count": len(fragmented_expected),
        "fragmentation_rate": round(len(fragmented_expected) / denominator, 6) if denominator else 0.0,
        "merged_gold_paragraph_count": len(merged_expected),
        "erroneous_merge_rate": round(len(merged_expected) / denominator, 6) if denominator else 0.0,
        "shifted_boundary_pair_count": shifted_pairs,
        "shifted_boundary_rate": round(shifted_pairs / denominator, 6) if denominator else 0.0,
        "unclassifiable_boundary_error_count": unclassifiable,
    }


def _index_unique(items: list[dict[str, Any]], id_field: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        item_id = item[id_field]
        if item_id in result:
            raise RuntimeError(f"Duplicate {label} id: {item_id}")
        result[item_id] = item
    return result


def _by_unique_locator(items: list[dict[str, Any]], label: str) -> dict[tuple[Any, ...], dict[str, Any]]:
    result: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in items:
        key = _locator_identity(item["source_locator"])
        if key in result:
            raise RuntimeError(f"Duplicate {label} source locator: {key}")
        result[key] = item
    return result


def _artifact_source_sha256(artifact: dict[str, Any], document_id: str) -> str:
    matches = [
        item.get("sha256")
        for item in artifact.get("source_files", [])
        if item.get("role") == "corpus_document" and item.get("document_id") == document_id
    ]
    if len(matches) != 1 or not matches[0]:
        raise RuntimeError(f"Artifact {artifact.get('artifact_id', '<unknown>')} lacks one source SHA-256 for {document_id}")
    return str(matches[0]).lower()


def _evaluate_document(gold: dict[str, Any], section_map: dict[str, Any], figure_map: dict[str, Any]) -> dict[str, Any]:
    gold_sections_by_id = _index_unique(gold["sections"], "gold_section_id", "gold section")
    actual_sections_by_id = _index_unique(section_map["sections"], "section_id", "actual section")
    for section in gold["sections"]:
        parent_id = section["parent_gold_section_id"]
        if parent_id is not None and parent_id not in gold_sections_by_id:
            raise RuntimeError(f"Gold section {section['gold_section_id']} has unknown parent {parent_id}")
    gold_sections_by_locator = _by_unique_locator(gold["sections"], "gold section")
    actual_sections_by_locator = _by_unique_locator(section_map["sections"], "actual section")

    expected_headings = Counter(
        _locator_identity(item["source_locator"]) for item in gold["sections"] if item["source_heading"]
    )
    actual_headings = Counter(
        _locator_identity(item["source_locator"]) for item in section_map["sections"] if item["source_heading"]
    )
    heading_detection = _precision_recall(actual_headings, expected_headings)

    heading_level_correct = heading_level_evaluated = 0
    for key in set(expected_headings) & set(actual_headings):
        heading_level_evaluated += 1
        heading_level_correct += (
            gold_sections_by_locator[key]["source_heading_level"]
            == actual_sections_by_locator[key]["source_heading_level"]
        )

    parent_correct = canonical_correct = matched = 0
    for key in set(gold_sections_by_locator) & set(actual_sections_by_locator):
        expected = gold_sections_by_locator[key]
        actual = actual_sections_by_locator[key]
        matched += 1
        expected_parent_id = expected["parent_gold_section_id"]
        actual_parent_id = actual["parent_section_id"]
        expected_parent_key = (
            _locator_identity(gold_sections_by_id[expected_parent_id]["source_locator"])
            if expected_parent_id is not None else None
        )
        if actual_parent_id is None:
            actual_parent_key = None
        elif actual_parent_id in actual_sections_by_id:
            actual_parent_key = _locator_identity(actual_sections_by_id[actual_parent_id]["source_locator"])
        else:
            actual_parent_key = ("unresolved_actual_parent", actual_parent_id)
        parent_correct += expected_parent_key == actual_parent_key
        canonical_correct += expected["canonical_section"] == actual["canonical_section"]

    gold_paragraphs_by_id = _index_unique(gold["paragraphs"], "gold_paragraph_id", "gold paragraph")
    for paragraph in gold["paragraphs"]:
        if paragraph["gold_section_id"] not in gold_sections_by_id:
            raise RuntimeError(
                f"Gold paragraph {paragraph['gold_paragraph_id']} has unknown section {paragraph['gold_section_id']}"
            )
    expected_paragraphs = Counter(_locator_identity(item["source_locator"]) for item in gold["paragraphs"])
    actual_paragraphs = Counter(_locator_identity(item["source_locator"]) for item in section_map["paragraphs"])
    paragraph_boundary = _precision_recall(actual_paragraphs, expected_paragraphs)
    paragraph_boundary.update(_boundary_topology(gold["paragraphs"], section_map["paragraphs"]))

    actual_figure_ids: Counter[Any] = Counter()
    actual_panel_tokens: Counter[Any] = Counter()
    actual_full_references: Counter[Any] = Counter()
    for item in figure_map["figure_references"]:
        paragraph_key = _locator_identity(item["source_locator"])
        actual_figure_ids[(paragraph_key, item["figure_id"])] += 1
        actual_full_references[(paragraph_key, item["figure_id"], tuple(sorted(item["panel_tokens"])))] += 1
        actual_panel_tokens.update((paragraph_key, item["figure_id"], token) for token in item["panel_tokens"])

    expected_figure_ids: Counter[Any] = Counter()
    expected_panel_tokens: Counter[Any] = Counter()
    expected_full_references: Counter[Any] = Counter()
    for item in gold["figure_references"]:
        if item["gold_paragraph_id"] not in gold_paragraphs_by_id:
            raise RuntimeError(
                f"Gold Figure reference {item['gold_reference_id']} has unknown paragraph {item['gold_paragraph_id']}"
            )
        paragraph = gold_paragraphs_by_id[item["gold_paragraph_id"]]
        paragraph_key = _locator_identity(paragraph["source_locator"])
        expected_figure_ids[(paragraph_key, item["figure_id"])] += 1
        expected_full_references[(paragraph_key, item["figure_id"], tuple(sorted(item["panel_tokens"])))] += 1
        expected_panel_tokens.update((paragraph_key, item["figure_id"], token) for token in item["panel_tokens"])

    exact_correct = sum((actual_full_references & expected_full_references).values())
    return {
        "heading_detection": heading_detection,
        "heading_level": _accuracy(heading_level_correct, heading_level_evaluated),
        "parent_hierarchy": _accuracy(parent_correct, matched),
        "canonical_section": _accuracy(canonical_correct, matched),
        "paragraph_boundary": paragraph_boundary,
        "figure_id": _precision_recall(actual_figure_ids, expected_figure_ids),
        "panel_token": _precision_recall(actual_panel_tokens, expected_panel_tokens),
        "full_reference_exact_match": _exact_match(exact_correct, sum(expected_full_references.values())),
    }


def _aggregate_metric_bundles(bundles: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate: dict[str, Any] = {}
    for name in ["heading_detection", "paragraph_boundary", "figure_id", "panel_token"]:
        true_positive = sum(bundle[name]["true_positive"] for bundle in bundles)
        false_positive = sum(bundle[name]["false_positive"] for bundle in bundles)
        false_negative = sum(bundle[name]["false_negative"] for bundle in bundles)
        metric = _precision_recall_counts(true_positive, false_positive, false_negative)
        if name == "paragraph_boundary":
            topology_expected = sum(bundle[name]["topology_evaluable_expected_count"] for bundle in bundles)
            fragmented = sum(bundle[name]["fragmented_gold_paragraph_count"] for bundle in bundles)
            merged = sum(bundle[name]["merged_gold_paragraph_count"] for bundle in bundles)
            shifted = sum(bundle[name]["shifted_boundary_pair_count"] for bundle in bundles)
            metric.update(
                {
                    "topology_evaluable_expected_count": topology_expected,
                    "fragmented_gold_paragraph_count": fragmented,
                    "fragmentation_rate": round(fragmented / topology_expected, 6) if topology_expected else 0.0,
                    "merged_gold_paragraph_count": merged,
                    "erroneous_merge_rate": round(merged / topology_expected, 6) if topology_expected else 0.0,
                    "shifted_boundary_pair_count": shifted,
                    "shifted_boundary_rate": round(shifted / topology_expected, 6) if topology_expected else 0.0,
                    "unclassifiable_boundary_error_count": sum(
                        bundle[name]["unclassifiable_boundary_error_count"] for bundle in bundles
                    ),
                }
            )
        aggregate[name] = metric
    for name in ["heading_level", "parent_hierarchy", "canonical_section"]:
        correct = sum(bundle[name]["correct"] for bundle in bundles)
        evaluated = sum(bundle[name]["evaluated"] for bundle in bundles)
        aggregate[name] = _accuracy(correct, evaluated)
    exact_correct = sum(bundle["full_reference_exact_match"]["correct"] for bundle in bundles)
    exact_evaluated = sum(bundle["full_reference_exact_match"]["evaluated"] for bundle in bundles)
    aggregate["full_reference_exact_match"] = _exact_match(exact_correct, exact_evaluated)
    return aggregate


def build_evaluation(gold: dict[str, Any], actual_dir: Path, gold_path: Path) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    source_artifact_ids = [gold["artifact_id"]]
    source_files = [{"path": str(gold_path.resolve()), "role": "gold_standard", "access_status": "author_owned"}]
    for gold_document in gold["documents"]:
        document_id = gold_document["document_id"]
        section_path = actual_dir / "documents" / f"{document_id}.section-map.json"
        figure_path = actual_dir / "documents" / f"{document_id}.figure-reference-map.json"
        if not section_path.is_file() or not figure_path.is_file():
            raise RuntimeError(f"Missing actual artifacts for gold document {document_id}")
        section_map = json.loads(section_path.read_text(encoding="utf-8"))
        figure_map = json.loads(figure_path.read_text(encoding="utf-8"))
        expected_source_sha256 = gold_document["source_sha256"].lower()
        section_source_sha256 = _artifact_source_sha256(section_map, document_id)
        figure_source_sha256 = _artifact_source_sha256(figure_map, document_id)
        if section_source_sha256 != expected_source_sha256 or figure_source_sha256 != expected_source_sha256:
            raise RuntimeError(
                f"Source SHA-256 mismatch for gold document {document_id}: "
                f"gold={expected_source_sha256}, section-map={section_source_sha256}, "
                f"figure-reference-map={figure_source_sha256}"
            )
        source_artifact_ids.extend([section_map["artifact_id"], figure_map["artifact_id"]])
        documents.append({"document_id": document_id, "metrics": _evaluate_document(gold_document, section_map, figure_map)})
        source_files.extend(
            [
                {"path": str(section_path.resolve()), "role": "derived_artifact", "document_id": document_id},
                {"path": str(figure_path.resolve()), "role": "derived_artifact", "document_id": document_id},
            ]
        )
    payload = envelope(
        "observable_structure_gold_evaluation",
        f"gold-evaluation:{safe_identifier(gold['artifact_id'])}",
        source_artifact_ids,
        source_files,
        [],
    )
    payload.update(
        {
            "evaluation_scope": "parser_observable_structure_not_scientific_validity",
            "document_count": len(documents),
            "aggregate": _aggregate_metric_bundles([item["metrics"] for item in documents]),
            "documents": documents,
        }
    )
    return payload


def _perfect(payload: dict[str, Any]) -> bool:
    metrics = payload["aggregate"]
    return all(
        metrics[name]["precision"] == 1.0 and metrics[name]["recall"] == 1.0
        for name in ["heading_detection", "paragraph_boundary", "figure_id", "panel_token"]
    ) and all(
        metrics[name]["accuracy"] == 1.0
        for name in ["heading_level", "parent_hierarchy", "canonical_section"]
    ) and metrics["full_reference_exact_match"]["exact_match_rate"] == 1.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Phase 3.1 parser output against observable-structure gold.")
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--actual-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-perfect", action="store_true")
    args = parser.parse_args()
    try:
        skill_root = Path(__file__).resolve().parents[1]
        candidate_root = skill_root
        validator = load_shared_validator(candidate_root)
        gold_issues = validator.validate_files(skill_root / "schemas" / "gold-standard.schema.json", args.gold.resolve())
        if gold_issues:
            summary = "; ".join(f"{item.path} [{item.keyword}] {item.message}" for item in gold_issues[:12])
            raise RuntimeError(f"Gold standard validation failed: {summary}")
        gold = json.loads(args.gold.resolve().read_text(encoding="utf-8"))
        payload = build_evaluation(gold, args.actual_dir.resolve(), args.gold.resolve())
        write_json_new(args.output.resolve(), payload)
        validate_payload_file(validator, skill_root / "schemas" / "gold-evaluation.schema.json", args.output.resolve())
        print(f"GOLD EVALUATION: {args.output.resolve()}")
        if args.require_perfect and not _perfect(payload):
            print("gold evaluator: output is not a perfect match", file=sys.stderr)
            return 1
        return 0
    except (OSError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"gold evaluator error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
