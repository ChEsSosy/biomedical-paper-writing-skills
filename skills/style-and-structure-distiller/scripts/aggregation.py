"""Artifact builders and document-first corpus aggregation."""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Any

from confidence_qc import distribution, feature_support, make_balance_dimensions
from features import (
    EXCLUDED_METRIC_SECTIONS,
    FEATURE_METHOD_VERSION,
    MARKER_PATTERNS,
    POSITION_KEYS,
    document_feature_map,
    document_section_feature_values,
    extract_figure_references,
)
from manifest import envelope, manifest_document, source_file_record, warning
from parsers import PARSER_VERSION, ParsedDocument, split_sentences, words


def _source_files(documents: list[ParsedDocument], manifest: dict[str, Any]) -> list[dict[str, str]]:
    return [
        source_file_record(document, manifest_document(manifest, document.document_id)["access_status"])
        for document in documents
    ]


def make_document_record(
    document: ParsedDocument,
    manifest: dict[str, Any],
    figure_references: list[dict[str, Any]],
) -> dict[str, Any]:
    paragraphs = [paragraph for section in document.sections for paragraph in section.paragraphs]
    payload = envelope(
        "document_record",
        f"document-record:{document.document_id}",
        [manifest["artifact_id"]],
        [source_file_record(document, manifest_document(manifest, document.document_id)["access_status"])],
        document.warnings,
    )
    payload.update(
        {
            "document_id": document.document_id,
            "article_type": document.article_type,
            "source_format": document.source_format,
            "source_sha256": document.source_sha256,
            "parser_name": "parsers.py",
            "parser_version": PARSER_VERSION,
            "parser_format_prior": document.parser_format_prior,
            "observed_parse_qc": document.observed_parse_qc,
            "word_count": sum(len(words(paragraph.text)) for paragraph in paragraphs),
            "paragraph_count": len(paragraphs),
            "sentence_count": sum(len(split_sentences(paragraph.text)) for paragraph in paragraphs),
            "section_count": len(document.sections),
            "figure_reference_count": len(figure_references),
        }
    )
    return payload


def make_section_map(document: ParsedDocument, manifest: dict[str, Any]) -> dict[str, Any]:
    payload = envelope(
        "section_map",
        f"section-map:{document.document_id}",
        [manifest["artifact_id"], f"document-record:{document.document_id}"],
        [source_file_record(document, manifest_document(manifest, document.document_id)["access_status"])],
        document.warnings,
    )
    payload.update(
        {
            "document_id": document.document_id,
            "article_type": document.article_type,
            "root_section_ids": [section.section_id for section in document.sections if section.parent_section_id is None],
            "sections": [
                {
                    "section_id": section.section_id,
                    "parent_section_id": section.parent_section_id,
                    "child_section_ids": section.child_section_ids,
                    "source_heading": section.source_heading,
                    "source_heading_level": section.source_heading_level,
                    "source_parent_heading": section.source_parent_heading,
                    "canonical_section": section.canonical_section,
                    "canonical_parent_section": section.canonical_parent_section,
                    "canonical_mapping_basis": section.canonical_mapping_basis,
                    "canonical_mapping_prior": section.canonical_mapping_prior,
                    "source_order": section.source_order,
                    "sibling_order": section.sibling_order,
                    "depth": section.depth,
                    "paragraph_ids": [paragraph.paragraph_id for paragraph in section.paragraphs],
                    "paragraph_count": len(section.paragraphs),
                    "word_count": sum(len(words(paragraph.text)) for paragraph in section.paragraphs),
                    "parser_locator": section.parser_locator,
                    "source_locator": section.source_locator,
                }
                for section in document.sections
            ],
            "paragraphs": [
                {
                    "paragraph_id": paragraph.paragraph_id,
                    "section_id": section.section_id,
                    "order_in_section": paragraph.order_in_section,
                    "global_order": paragraph.global_order,
                    "word_count": len(words(paragraph.text)),
                    "sentence_count": len(split_sentences(paragraph.text)),
                    "parser_locator": paragraph.parser_locator,
                    "source_locator": paragraph.source_locator,
                }
                for section in document.sections
                for paragraph in section.paragraphs
            ],
        }
    )
    return payload


def make_figure_reference_map(
    document: ParsedDocument,
    manifest: dict[str, Any],
    figure_references: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = envelope(
        "figure_reference_map",
        f"figure-reference-map:{document.document_id}",
        [manifest["artifact_id"], f"section-map:{document.document_id}"],
        [source_file_record(document, manifest_document(manifest, document.document_id)["access_status"])],
        document.warnings,
    )
    payload.update(
        {
            "document_id": document.document_id,
            "reference_count": len(figure_references),
            "unique_figure_count": len({item["figure_id"] for item in figure_references}),
            "figure_references": figure_references,
        }
    )
    return payload


def _rate(count: int, denominator: int, scale: float = 1.0) -> float:
    return round(count * scale / denominator, 6) if denominator else 0.0


def make_style_profile(
    documents: list[ParsedDocument],
    manifest: dict[str, Any],
    run_warnings: list[dict[str, str]],
) -> dict[str, Any]:
    maps = {document.document_id: document_feature_map(document) for document in documents}
    by_id = {document.document_id: document for document in documents}
    all_ids = sorted(by_id)
    canonical_sections = sorted({canonical for mapping in maps.values() for canonical in mapping})
    section_profiles: dict[str, Any] = {}

    for canonical in canonical_sections:
        buckets = {document_id: mapping[canonical] for document_id, mapping in maps.items() if canonical in mapping}
        per_document = {document_id: document_section_feature_values(bucket) for document_id, bucket in buckets.items()}
        pooled_word_count = sum(bucket["word_count"] for bucket in buckets.values())
        pooled_sentence_lengths = [value for bucket in buckets.values() for value in bucket["sentence_lengths"]]
        pooled_paragraph_lengths = [value for bucket in buckets.values() for value in bucket["paragraph_lengths"]]
        pooled_paragraph_sentence_counts = [
            value for bucket in buckets.values() for value in bucket["paragraph_sentence_counts"]
        ]
        marker_totals: Counter[str] = Counter()
        citation_positions: Counter[str] = Counter({key: 0 for key in POSITION_KEYS})
        figure_positions: Counter[str] = Counter({key: 0 for key in POSITION_KEYS})
        for bucket in buckets.values():
            marker_totals.update(bucket["markers"])
            citation_positions.update(bucket["citation_positions"])
            figure_positions.update(bucket["figure_positions"])
        paragraph_total = len(pooled_paragraph_lengths)

        document_weighted_markers = {
            name: distribution([values.get(f"marker_rate.{name}", 0.0) for values in per_document.values()])
            for name in sorted(MARKER_PATTERNS)
        }
        document_weighted_citation_positions = {
            key: distribution([values[f"citation_position_rate.{key}"] for values in per_document.values()])
            for key in POSITION_KEYS
        }
        document_weighted_figure_positions = {
            key: distribution([values[f"figure_position_rate.{key}"] for values in per_document.values()])
            for key in POSITION_KEYS
        }
        supports: dict[str, Any] = {}
        feature_keys = sorted({key for values in per_document.values() for key in values})
        for key in feature_keys:
            values_by_document = {document_id: values[key] for document_id, values in per_document.items()}
            feature_id = f"{canonical}.{key}"
            supports[feature_id] = feature_support(feature_id, values_by_document, by_id, manifest, all_ids)

        section_profiles[canonical] = {
            "document_count": len(buckets),
            "document_coverage": round(len(buckets) / len(documents), 6),
            "document_weighted": {
                "word_count_per_document": distribution([bucket["word_count"] for bucket in buckets.values()]),
                "mean_sentence_words_per_document": distribution([
                    statistics.mean(bucket["sentence_lengths"]) if bucket["sentence_lengths"] else 0.0
                    for bucket in buckets.values()
                ]),
                "mean_paragraph_words_per_document": distribution([
                    statistics.mean(bucket["paragraph_lengths"]) if bucket["paragraph_lengths"] else 0.0
                    for bucket in buckets.values()
                ]),
                "mean_sentences_per_paragraph_per_document": distribution([
                    statistics.mean(bucket["paragraph_sentence_counts"]) if bucket["paragraph_sentence_counts"] else 0.0
                    for bucket in buckets.values()
                ]),
                "marker_rates_per_1000_words": document_weighted_markers,
                "citation_position_rates": document_weighted_citation_positions,
                "figure_position_rates": document_weighted_figure_positions,
            },
            "token_weighted": {
                "word_count": pooled_word_count,
                "sentence_count": len(pooled_sentence_lengths),
                "paragraph_count": paragraph_total,
                "sentence_words": distribution(pooled_sentence_lengths),
                "paragraph_words": distribution(pooled_paragraph_lengths),
                "sentences_per_paragraph": distribution(pooled_paragraph_sentence_counts),
                "marker_rates_per_1000_words": {
                    name: _rate(marker_totals[name], pooled_word_count, 1000.0) for name in sorted(MARKER_PATTERNS)
                },
                "citation_position_rates": {
                    key: _rate(citation_positions[key], paragraph_total) for key in POSITION_KEYS
                },
                "figure_position_rates": {
                    key: _rate(figure_positions[key], paragraph_total) for key in POSITION_KEYS
                },
            },
            "feature_support": supports,
        }

    payload = envelope(
        "style_profile",
        f"style-profile:{manifest['corpus_id']}",
        [manifest["artifact_id"]] + [f"section-map:{document.document_id}" for document in documents],
        _source_files(documents, manifest),
        run_warnings,
    )
    payload.update(
        {
            "corpus_id": manifest["corpus_id"],
            "corpus_type": manifest["corpus_type"],
            "document_count": len(documents),
            "feature_method_version": FEATURE_METHOD_VERSION,
            "aggregation_contract": {
                "primary_interpretation": "document_weighted",
                "observation_hierarchy": "observation_to_document_section_to_corpus_to_stratum",
                "token_weighted_retained": True,
            },
            "sections": section_profiles,
            "prohibited_content_audit": {},
        }
    )
    return payload


def _canonical_sequence(document: ParsedDocument) -> tuple[str, ...]:
    sequence: list[str] = []
    for section in document.sections:
        canonical = section.canonical_section
        if canonical in EXCLUDED_METRIC_SECTIONS:
            continue
        if not sequence or sequence[-1] != canonical:
            sequence.append(canonical)
    return tuple(sequence)


def make_structure_profile(
    documents: list[ParsedDocument],
    manifest: dict[str, Any],
    figure_references_by_document: dict[str, list[dict[str, Any]]],
    run_warnings: list[dict[str, str]],
) -> dict[str, Any]:
    by_id = {document.document_id: document for document in documents}
    all_ids = sorted(by_id)
    canonical_sections = sorted({
        section.canonical_section for document in documents for section in document.sections
        if section.canonical_section not in EXCLUDED_METRIC_SECTIONS
    })
    presence: Counter[str] = Counter()
    sequences = Counter(_canonical_sequence(document) for document in documents)
    section_instances: dict[str, dict[str, float]] = {name: {} for name in canonical_sections}
    paragraphs: dict[str, dict[str, float]] = {name: {} for name in canonical_sections}
    figure_counts: dict[str, dict[str, float]] = {name: {} for name in canonical_sections}
    child_edges: dict[str, dict[str, float]] = {name: {} for name in canonical_sections}
    root_mean_direct_children: dict[str, dict[str, float]] = {name: {} for name in canonical_sections}
    max_depth: dict[str, float] = {}

    for document in documents:
        document_id = document.document_id
        seen = {
            section.canonical_section for section in document.sections
            if section.canonical_section not in EXCLUDED_METRIC_SECTIONS
        }
        presence.update(seen)
        section_lookup = {section.section_id: section for section in document.sections}
        references = figure_references_by_document[document_id]
        reference_counter: Counter[str] = Counter(
            section_lookup[item["source_section_id"]].canonical_section for item in references
        )
        max_depth[document_id] = float(max((section.depth for section in document.sections), default=0))
        for canonical in canonical_sections:
            matching = [section for section in document.sections if section.canonical_section == canonical]
            section_instances[canonical][document_id] = float(len(matching))
            paragraphs[canonical][document_id] = float(sum(len(section.paragraphs) for section in matching))
            figure_counts[canonical][document_id] = float(reference_counter[canonical])
            child_edges[canonical][document_id] = float(sum(len(section.child_section_ids) for section in matching))
            matching_roots = [section for section in matching if section.parent_section_id is None]
            root_mean_direct_children[canonical][document_id] = (
                float(statistics.mean(len(section.child_section_ids) for section in matching_roots))
                if matching_roots else 0.0
            )

    supports: dict[str, Any] = {}
    for prefix, mapping in [
        ("section_instances", section_instances),
        ("paragraphs", paragraphs),
        ("figure_references", figure_counts),
        ("child_edges", child_edges),
        ("root_mean_direct_children", root_mean_direct_children),
    ]:
        for canonical, values in mapping.items():
            feature_id = f"{prefix}.{canonical}"
            supports[feature_id] = feature_support(feature_id, values, by_id, manifest, all_ids)
    supports["heading.max_depth"] = feature_support("heading.max_depth", max_depth, by_id, manifest, all_ids)

    payload = envelope(
        "structure_profile",
        f"structure-profile:{manifest['corpus_id']}",
        [manifest["artifact_id"]]
        + [f"section-map:{document.document_id}" for document in documents]
        + [f"figure-reference-map:{document.document_id}" for document in documents],
        _source_files(documents, manifest),
        run_warnings + [warning("semantic_annotation_not_run", "Phase 3.1 does not classify manuscript-story roles", "info")],
    )
    payload.update(
        {
            "corpus_id": manifest["corpus_id"],
            "corpus_type": manifest["corpus_type"],
            "document_count": len(documents),
            "section_presence": {
                name: {"document_count": count, "document_rate": round(count / len(documents), 6)}
                for name, count in sorted(presence.items())
            },
            "common_canonical_sequences": [
                {"sequence": list(sequence), "document_count": count, "document_rate": round(count / len(documents), 6)}
                for sequence, count in sequences.most_common() if sequence
            ],
            "section_instances_per_document": {
                name: distribution(list(values.values())) for name, values in section_instances.items()
            },
            "paragraphs_per_document_section": {
                name: distribution(list(values.values())) for name, values in paragraphs.items()
            },
            "heading_depth_per_document": distribution(list(max_depth.values())),
            "child_edge_count_per_document_canonical_section": {
                name: distribution(list(values.values())) for name, values in child_edges.items()
            },
            "mean_direct_children_per_root_section_instance_by_document": {
                name: distribution(list(values.values())) for name, values in root_mean_direct_children.items()
            },
            "figure_references_per_document_section": {
                name: distribution(list(values.values())) for name, values in figure_counts.items()
            },
            "feature_support": supports,
            "deterministic_only": True,
            "semantic_annotation_status": "not_performed_phase3_1",
            "semantic_role_labels_present": False,
        }
    )
    return payload


def make_corpus_balance(
    documents: list[ParsedDocument],
    manifest: dict[str, Any],
    run_warnings: list[dict[str, str]],
) -> dict[str, Any]:
    records = [manifest_document(manifest, document.document_id) for document in documents]
    dimensions, balance_warnings = make_balance_dimensions(records)
    payload = envelope(
        "corpus_balance",
        f"corpus-balance:{manifest['corpus_id']}",
        [manifest["artifact_id"]] + [f"document-record:{document.document_id}" for document in documents],
        _source_files(documents, manifest),
        run_warnings + balance_warnings,
    )
    payload.update(
        {
            "corpus_id": manifest["corpus_id"],
            "corpus_type": manifest["corpus_type"],
            "document_count": len(documents),
            "dominance_threshold": 0.5,
            "dimensions": dimensions,
            "group_metadata_usage": "bias_control_only_not_imitation",
        }
    )
    return payload
