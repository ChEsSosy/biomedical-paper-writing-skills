"""Deterministic surface features and source-located Figure references."""

from __future__ import annotations

import re
import statistics
from collections import Counter
from typing import Any

from parsers import ParsedDocument, ParsedSection, source_span_sha256, split_sentences, words


FEATURE_METHOD_VERSION = "deterministic-biomedical-observable-v2"
EXCLUDED_METRIC_SECTIONS = {"front_matter", "references", "data_availability"}
POSITION_KEYS = ("single_sentence", "opening", "middle", "closing")

MARKER_PATTERNS: dict[str, re.Pattern[str]] = {
    "first_person_plural": re.compile(r"\b(?:we|our|ours)\b", re.IGNORECASE),
    "hedge": re.compile(
        r"\b(?:may|might|could|suggest|suggests|suggested|appears?|potentially|possibly|likely|unlikely|consistent with)\b",
        re.IGNORECASE,
    ),
    "contrast_transition": re.compile(
        r"\b(?:however|although|whereas|nevertheless|nonetheless|in contrast|by contrast)\b",
        re.IGNORECASE,
    ),
    "consequence_transition": re.compile(
        r"\b(?:therefore|thus|consequently|accordingly|as a result)\b",
        re.IGNORECASE,
    ),
    "addition_transition": re.compile(r"\b(?:additionally|furthermore|moreover|in addition)\b", re.IGNORECASE),
    "figure_reference": re.compile(
        r"\b(?:(?:Extended Data|Supplementary)\s+)?Fig(?:ure)?s?\.?\s+[A-Za-z]?\d+",
        re.IGNORECASE,
    ),
    "table_reference": re.compile(r"\bTables?\s+[A-Za-z]?\d+", re.IGNORECASE),
    "numeric_citation_shape": re.compile(r"(?:\[[0-9,;\-– ]+\]|\([0-9,;\-– ]+\))"),
    "author_year_citation_shape": re.compile(
        r"\([A-Z][A-Za-z'’-]+(?:\s+et\s+al\.)?,?\s+(?:19|20)\d{2}[a-z]?\)"
    ),
    "passive_marker": re.compile(
        r"\b(?:is|are|was|were|be|been|being)\s+(?:[A-Za-z]+ly\s+)?[A-Za-z]+(?:ed|en)\b",
        re.IGNORECASE,
    ),
}

CITATION_PATTERN = re.compile(
    rf"(?:{MARKER_PATTERNS['numeric_citation_shape'].pattern}|{MARKER_PATTERNS['author_year_citation_shape'].pattern})"
)
FIGURE_POSITION_PATTERN = MARKER_PATTERNS["figure_reference"]

# Preserve every single-letter panel token, including legitimate panels ``a``
# and ``i``.  Only the two case-sensitive forms that can also be complete
# English words (lowercase ``a`` and uppercase ``I``) need a local continuation
# check when they occur after a Figure-list connector. They remain valid panel
# tokens at a reference boundary, but are not consumed when local prose continues
# directly or through bounded punctuation. The token classes are Unicode-aware;
# no prose or scientific-term vocabulary is maintained. Opening wrappers accept
# any lexical token, while clause punctuation requires a multi-character token
# so a legitimate single-letter panel continuation such as `a, c` is preserved.
UNICODE_LEXICAL_START_PATTERN = r"[^\W_]"
UNICODE_MULTI_CHARACTER_TOKEN_PATTERN = (
    rf"{UNICODE_LEXICAL_START_PATTERN}"
    rf"(?:{UNICODE_LEXICAL_START_PATTERN}|[-‐‑‒–—'’]{UNICODE_LEXICAL_START_PATTERN})"
)
OPENING_WRAPPER_PATTERN = r"[\(\[\{\"'“‘]"
CLAUSE_PUNCTUATION_PATTERN = r"[,;:–—]"
LOCAL_PROSE_CONTINUATION_PATTERN = (
    rf"(?:\s+{UNICODE_LEXICAL_START_PATTERN}"
    rf"|\s*{OPENING_WRAPPER_PATTERN}\s*{UNICODE_LEXICAL_START_PATTERN}"
    rf"|\s*{CLAUSE_PUNCTUATION_PATTERN}\s*{UNICODE_MULTI_CHARACTER_TOKEN_PATTERN})"
)
SINGLE_PANEL_LIST_TAIL_PATTERN = (
    rf"(?:[B-HJ-Zb-hj-z]|[Ai]|[aI](?!{LOCAL_PROSE_CONTINUATION_PATTERN}))"
)
FIGURE_MENTION_PATTERN = re.compile(
    r"\b(?P<prefix>(?i:(?:Extended Data\s+|Supplementary\s+)?Fig(?:ure)?s?))\.?\s+"
    r"(?P<body>[A-Za-z]?\d+[A-Za-z]?(?:\s*[–-]\s*[A-Za-z]?[0-9]*[A-Za-z])?"
    rf"(?:\s*(?:,|(?i:and)|&)\s*(?:[A-Za-z]?\d+[A-Za-z]?|{SINGLE_PANEL_LIST_TAIL_PATTERN})){{0,6}})"
    # A panel token must end at a real token boundary. Without this guard,
    # the optional list tail can consume the first letter of prose such as
    # "and Supplementary", ", Methods", or ", depicting".
    r"(?![A-Za-z0-9])",
)


def _position(index: int, count: int) -> str:
    if count <= 1:
        return "single_sentence"
    if index == 0:
        return "opening"
    if index == count - 1:
        return "closing"
    return "middle"


def reference_position_counts(paragraphs: list[str], pattern: re.Pattern[str]) -> Counter[str]:
    counts: Counter[str] = Counter({key: 0 for key in POSITION_KEYS})
    for paragraph in paragraphs:
        sentences = split_sentences(paragraph)
        for index, sentence in enumerate(sentences):
            occurrences = len(pattern.findall(sentence))
            if occurrences:
                counts[_position(index, len(sentences))] += occurrences
    return counts


def section_feature(section: ParsedSection) -> dict[str, Any]:
    paragraphs = [paragraph.text for paragraph in section.paragraphs]
    text = " ".join(paragraphs)
    sentence_groups = [split_sentences(paragraph) for paragraph in paragraphs]
    sentence_lengths = [len(words(sentence)) for group in sentence_groups for sentence in group]
    paragraph_lengths = [len(words(paragraph)) for paragraph in paragraphs]
    paragraph_sentence_counts = [len(group) for group in sentence_groups]
    return {
        "word_count": len(words(text)),
        "sentence_lengths": sentence_lengths,
        "paragraph_lengths": paragraph_lengths,
        "paragraph_sentence_counts": paragraph_sentence_counts,
        "markers": Counter({name: len(pattern.findall(text)) for name, pattern in MARKER_PATTERNS.items()}),
        "citation_positions": reference_position_counts(paragraphs, CITATION_PATTERN),
        "figure_positions": reference_position_counts(paragraphs, FIGURE_POSITION_PATTERN),
        "section_count": 1,
    }


def document_feature_map(document: ParsedDocument) -> dict[str, dict[str, Any]]:
    combined: dict[str, dict[str, Any]] = {}
    for section in document.sections:
        canonical = section.canonical_section
        if canonical in EXCLUDED_METRIC_SECTIONS:
            continue
        feature = section_feature(section)
        bucket = combined.setdefault(
            canonical,
            {
                "word_count": 0,
                "sentence_lengths": [],
                "paragraph_lengths": [],
                "paragraph_sentence_counts": [],
                "markers": Counter(),
                "citation_positions": Counter({key: 0 for key in POSITION_KEYS}),
                "figure_positions": Counter({key: 0 for key in POSITION_KEYS}),
                "section_count": 0,
            },
        )
        bucket["word_count"] += feature["word_count"]
        bucket["sentence_lengths"].extend(feature["sentence_lengths"])
        bucket["paragraph_lengths"].extend(feature["paragraph_lengths"])
        bucket["paragraph_sentence_counts"].extend(feature["paragraph_sentence_counts"])
        bucket["markers"].update(feature["markers"])
        bucket["citation_positions"].update(feature["citation_positions"])
        bucket["figure_positions"].update(feature["figure_positions"])
        bucket["section_count"] += 1
    return combined


def document_section_feature_values(bucket: dict[str, Any]) -> dict[str, float]:
    word_count = bucket["word_count"]
    result: dict[str, float] = {
        "word_count": float(word_count),
        "mean_sentence_words": statistics.mean(bucket["sentence_lengths"]) if bucket["sentence_lengths"] else 0.0,
        "mean_paragraph_words": statistics.mean(bucket["paragraph_lengths"]) if bucket["paragraph_lengths"] else 0.0,
        "mean_sentences_per_paragraph": statistics.mean(bucket["paragraph_sentence_counts"]) if bucket["paragraph_sentence_counts"] else 0.0,
    }
    for name in sorted(MARKER_PATTERNS):
        count = bucket["markers"][name]
        result[f"marker_rate.{name}"] = count * 1000 / word_count if word_count else 0.0
    paragraph_count = len(bucket["paragraph_lengths"])
    for key in POSITION_KEYS:
        result[f"citation_position_rate.{key}"] = bucket["citation_positions"][key] / paragraph_count if paragraph_count else 0.0
        result[f"figure_position_rate.{key}"] = bucket["figure_positions"][key] / paragraph_count if paragraph_count else 0.0
    return result


def _expand_panel_range(start: str, end: str) -> list[str]:
    start = start.lower()
    end = end.lower()
    if len(start) == len(end) == 1 and start.isalpha() and end.isalpha() and ord(start) <= ord(end):
        return [chr(value) for value in range(ord(start), ord(end) + 1)]
    return [start, end]


def _parse_figure_body(body: str) -> list[tuple[str, list[str]]]:
    normalized = re.sub(r"\s+", " ", body.strip())
    range_match = re.match(r"^([A-Za-z]?\d+)([A-Za-z])\s*[–-]\s*([A-Za-z])$", normalized)
    if range_match:
        return [(range_match.group(1).lower(), _expand_panel_range(range_match.group(2), range_match.group(3)))]

    parts = [part.strip() for part in re.split(r"\s*(?:,|\band\b|&)\s*", normalized, flags=re.IGNORECASE) if part.strip()]
    parsed: list[tuple[str, list[str]]] = []
    current_number: str | None = None
    for part in parts:
        match = re.fullmatch(r"([A-Za-z]?\d+)([A-Za-z])?", part)
        if match:
            current_number = match.group(1).lower()
            panels = [match.group(2).lower()] if match.group(2) else []
            parsed.append((current_number, panels))
        elif current_number and re.fullmatch(r"[A-Za-z]", part):
            if parsed and parsed[-1][0] == current_number:
                parsed[-1][1].append(part.lower())
    deduplicated: list[tuple[str, list[str]]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for number, panels in parsed:
        key = (number, tuple(dict.fromkeys(panels)))
        if key not in seen:
            seen.add(key)
            deduplicated.append((number, list(key[1])))
    return deduplicated


def extract_figure_references(document: ParsedDocument) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for section in document.sections:
        for paragraph in section.paragraphs:
            for match in FIGURE_MENTION_PATTERN.finditer(paragraph.text):
                prefix = match.group("prefix").lower()
                if prefix.startswith("extended data"):
                    figure_type, id_prefix = "extended_data_figure", "extended-data-figure"
                elif prefix.startswith("supplementary"):
                    figure_type, id_prefix = "supplementary_figure", "supplementary-figure"
                else:
                    figure_type, id_prefix = "figure", "figure"
                for number, panels in _parse_figure_body(match.group("body")):
                    order = len(records)
                    records.append(
                        {
                            "reference_id": f"{document.document_id}-fr{order:04d}",
                            "figure_id": f"{id_prefix}:{number}",
                            "figure_type": figure_type,
                            "figure_number": number,
                            "panel_tokens": panels,
                            "source_reference_text": match.group(0),
                            "source_section_id": section.section_id,
                            "source_paragraph_id": paragraph.paragraph_id,
                            "source_parser_locator": paragraph.parser_locator,
                            "source_locator": paragraph.source_locator,
                            "reference_start_in_normalized_paragraph": match.start(),
                            "reference_end_in_normalized_paragraph": match.end(),
                            "reference_span_sha256": source_span_sha256(match.group(0)),
                            "reference_order": order,
                        }
                    )
    return records
