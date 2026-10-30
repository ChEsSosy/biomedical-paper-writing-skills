"""Deterministic source parsers that preserve raw and canonical hierarchy."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

from manifest import sha256_file, warning


PARSER_VERSION = "0.2.7"
FORMAT_PRIORS = {
    "markdown": 0.86,
    "plain_text": 0.72,
    "jats_xml": 0.95,
    "html": 0.78,
    "pdf_text": 0.60,
}

SECTION_ALIASES: dict[str, set[str]] = {
    "abstract": {"abstract", "summary"},
    "introduction": {"introduction", "background"},
    "methods": {"methods", "materials and methods", "materials & methods", "experimental procedures", "methodology"},
    "results": {"results", "findings"},
    "discussion": {"discussion"},
    "results_discussion": {"results and discussion", "results & discussion"},
    "conclusion": {"conclusion", "conclusions", "concluding remarks"},
    "figure_legend": {"figure legends", "figures", "legends"},
    "data_availability": {"data availability", "code availability", "data and code availability"},
    "references": {"references", "bibliography", "literature cited"},
}

REFERENCE_ENTRY_PATTERN = re.compile(
    r"^(?:\[?\d+\]?\.?\s+|[A-Z][A-Za-z'’-]+,?\s+[A-Z].{0,60}\b(?:19|20)\d{2}\b)"
)


@dataclass
class ParsedParagraph:
    paragraph_id: str
    text: str
    order_in_section: int
    global_order: int
    parser_locator: str
    source_locator: dict[str, int | str]


@dataclass
class ParsedSection:
    section_id: str
    parent_section_id: str | None
    child_section_ids: list[str]
    source_heading: str
    source_heading_level: int
    source_parent_heading: str
    canonical_section: str
    canonical_parent_section: str | None
    canonical_mapping_basis: str
    canonical_mapping_prior: float
    source_order: int
    sibling_order: int
    depth: int
    paragraphs: list[ParsedParagraph]
    parser_locator: str
    source_locator: dict[str, int | str]


@dataclass
class ParsedDocument:
    document_id: str
    article_type: str
    source_path: Path
    source_format: str
    source_sha256: str
    sections: list[ParsedSection]
    parser_format_prior: float
    observed_parse_qc: dict[str, object]
    warnings: list[dict[str, str]]


@dataclass
class _SectionDraft:
    source_heading: str
    source_heading_level: int
    parent_index: int | None
    source_locator: dict[str, int | str] | None = None
    paragraphs: list["_LocatedText"] = field(default_factory=list)


@dataclass
class _LocatedText:
    text: str
    source_locator: dict[str, int | str]


@dataclass
class _LocatedBlock:
    kind: str
    text: str
    level: int
    source_locator: dict[str, int | str]


@dataclass
class _SourceLine:
    text: str
    line_number: int
    start_char: int | None = None
    page_number: int | None = None


def normalize_space(text: str) -> str:
    replacements = {"\u00a0": " ", "\u2009": " ", "\u202f": " ", "\ufeff": "", "\u00ad": ""}
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def source_span_sha256(text: str) -> str:
    """Hash normalized observable source content without storing the passage."""
    return hashlib.sha256(normalize_space(text).encode("utf-8")).hexdigest()


def _locator_with_span_kind(locator: dict[str, int | str], span_kind: str) -> dict[str, int | str]:
    updated = dict(locator)
    updated["span_kind"] = span_kind
    return updated


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*|\d+(?:\.\d+)?", text)


def split_sentences(text: str) -> list[str]:
    compact = normalize_space(text)
    if not compact:
        return []
    protected = compact
    for item in ["Fig.", "Figs.", "Dr.", "vs.", "et al.", "i.e.", "e.g."]:
        protected = protected.replace(item, item.replace(".", "<DOT>"))
    pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", protected)
    restored = [piece.replace("<DOT>", ".").strip() for piece in pieces]
    return [piece for piece in restored if len(words(piece)) >= 3]


def _plain_heading(heading: str) -> str:
    plain = heading.lower().strip()
    plain = re.sub(r"^\s*(?:\d+(?:\.\d+)*|[ivx]+)[.)]?\s+", "", plain)
    plain = re.sub(r"[^a-z0-9& ]+", " ", plain)
    return normalize_space(plain)


def canonicalize_heading(
    heading: str,
    article_type: str,
    parent_canonical: str | None,
    parent_is_title: bool = False,
) -> tuple[str, str, float]:
    plain = _plain_heading(heading)
    if not plain:
        return "front_matter", "front_matter", 0.5
    # Preserve the exact local Summary heading and its Review body membership.
    if article_type == "review_article" and plain == "summary" and parent_canonical == "review_body" and not parent_is_title:
        return "review_body", "inherited_parent", 0.85
    for canonical, aliases in SECTION_ALIASES.items():
        if plain in aliases:
            exact = plain == canonical.replace("_", " ")
            return canonical, "exact_heading" if exact else "heading_synonym", 1.0 if exact else 0.85
    if re.match(r"^(figure|fig|extended data figure|supplementary figure)\s+[a-z0-9]+", plain):
        return "figure_legend", "heading_synonym", 0.8
    if parent_canonical and parent_canonical not in {"front_matter", "other", "references", "data_availability"}:
        return parent_canonical, "inherited_parent", 0.75
    if article_type == "review_article":
        return "review_body", "review_thematic", 0.65
    return "other", "unrecognized", 0.5


def _finalize_sections(
    drafts: list[_SectionDraft],
    document_id: str,
    article_type: str,
) -> list[ParsedSection]:
    sections: list[ParsedSection] = []
    sibling_counts: dict[int | None, int] = {}
    paragraph_global_order = 0
    for index, draft in enumerate(drafts):
        parent = sections[draft.parent_index] if draft.parent_index is not None else None
        canonical, basis, prior = canonicalize_heading(
            draft.source_heading,
            article_type,
            parent.canonical_section if parent else None,
            bool(parent and draft.parent_index == 0 and parent.source_heading_level == 1),
        )
        section_id = f"{document_id}-s{index:03d}"
        sibling_order = sibling_counts.get(draft.parent_index, 0)
        sibling_counts[draft.parent_index] = sibling_order + 1
        located_paragraphs: list[ParsedParagraph] = []
        for raw_order, raw in enumerate(draft.paragraphs):
            text = normalize_space(raw.text)
            if not text:
                continue
            order = len(located_paragraphs)
            paragraph_id = f"{document_id}-p{paragraph_global_order:04d}"
            located_paragraphs.append(
                ParsedParagraph(
                    paragraph_id=paragraph_id,
                    text=text,
                    order_in_section=order,
                    global_order=paragraph_global_order,
                    parser_locator=f"{document_id}:section:{index}:paragraph:{raw_order}",
                    source_locator=raw.source_locator,
                )
            )
            paragraph_global_order += 1
        source_locator = draft.source_locator
        if source_locator is None and located_paragraphs:
            source_locator = _locator_with_span_kind(located_paragraphs[0].source_locator, "section_anchor")
        if source_locator is None:
            raise RuntimeError(f"Section {index} has no recoverable source anchor")
        sections.append(
            ParsedSection(
                section_id=section_id,
                parent_section_id=parent.section_id if parent else None,
                child_section_ids=[],
                source_heading=normalize_space(draft.source_heading),
                source_heading_level=max(0, draft.source_heading_level),
                source_parent_heading=parent.source_heading if parent else "",
                canonical_section=canonical,
                canonical_parent_section=parent.canonical_section if parent else None,
                canonical_mapping_basis=basis,
                canonical_mapping_prior=prior,
                source_order=index,
                sibling_order=sibling_order,
                depth=(parent.depth + 1) if parent else 0,
                paragraphs=located_paragraphs,
                parser_locator=f"{document_id}:section:{index}",
                source_locator=source_locator,
            )
        )
    by_id = {section.section_id: section for section in sections}
    for section in sections:
        if section.parent_section_id:
            by_id[section.parent_section_id].child_section_ids.append(section.section_id)
    return sections


def _sections_from_blocks(
    blocks: Iterable[_LocatedBlock],
    document_id: str,
    article_type: str,
) -> tuple[list[ParsedSection], int]:
    drafts: list[_SectionDraft] = []
    heading_stack: list[tuple[int, int]] = []
    current_index: int | None = None
    paragraph_candidates = 0
    for block in blocks:
        if block.kind == "heading":
            while heading_stack and heading_stack[-1][0] >= block.level:
                heading_stack.pop()
            parent_index = heading_stack[-1][1] if heading_stack else None
            current_index = len(drafts)
            drafts.append(
                _SectionDraft(
                    normalize_space(block.text),
                    block.level,
                    parent_index,
                    block.source_locator,
                )
            )
            heading_stack.append((block.level, current_index))
            continue
        paragraph_candidates += 1
        if current_index is None:
            current_index = len(drafts)
            drafts.append(_SectionDraft("", 0, None))
        drafts[current_index].paragraphs.append(_LocatedText(block.text, block.source_locator))
    return _finalize_sections(drafts, document_id, article_type), paragraph_candidates


def _numbered_heading_level(text: str) -> int | None:
    match = re.match(r"^\s*(\d+(?:\.\d+)*)[.)]?\s+(.+)$", text)
    if not match or len(words(match.group(2))) > 24 or re.search(r"[.!?]$", match.group(2).strip()):
        return None
    return match.group(1).count(".") + 1


def _source_line_locator(
    lines: list[_SourceLine],
    text: str,
    span_kind: str,
    locator_type: str,
) -> dict[str, int | str]:
    locator: dict[str, int | str] = {
        "locator_type": locator_type,
        "span_kind": span_kind,
        "source_span_sha256": source_span_sha256(text),
    }
    if locator_type == "pdf_page_line_range":
        locator.update(
            {
                "page_start": int(lines[0].page_number or 1),
                "page_end": int(lines[-1].page_number or lines[0].page_number or 1),
                "extracted_start_line": lines[0].line_number,
                "extracted_end_line": lines[-1].line_number,
            }
        )
    else:
        last_content = lines[-1].text.rstrip("\r\n")
        start_char = int(lines[0].start_char or 0)
        end_char = int(lines[-1].start_char or 0) + len(last_content)
        if len(lines) == 1 and span_kind == "heading":
            relative_start = last_content.find(text)
            if relative_start >= 0:
                start_char += relative_start
                end_char = start_char + len(text)
        locator.update(
            {
                "start_line": lines[0].line_number,
                "end_line": lines[-1].line_number,
                "start_char": start_char,
                "end_char": end_char,
            }
        )
    return locator


def _text_blocks_from_lines(
    source_lines: list[_SourceLine],
    allow_numbered_headings: bool,
    locator_type: str,
) -> tuple[list[_LocatedBlock], int]:
    blocks: list[_LocatedBlock] = []
    paragraph_lines: list[_SourceLine] = []
    exact = {item for aliases in SECTION_ALIASES.values() for item in aliases}
    candidate_count = 0

    def flush() -> None:
        nonlocal paragraph_lines, candidate_count
        if paragraph_lines:
            candidate_count += 1
            text = normalize_space(" ".join(line.text.strip() for line in paragraph_lines))
            blocks.append(
                _LocatedBlock(
                    "paragraph",
                    text,
                    0,
                    _source_line_locator(paragraph_lines, text, "paragraph", locator_type),
                )
            )
        paragraph_lines = []

    for source_line in source_lines:
        stripped = source_line.text.strip()
        markdown = re.match(r"^(#{1,6})\s+(.+?)\s*#*$", stripped)
        normalized = normalize_space(re.sub(r"[:.]$", "", stripped)).lower()
        numbered_level = _numbered_heading_level(stripped) if allow_numbered_headings else None
        if markdown:
            flush()
            heading = normalize_space(markdown.group(2))
            blocks.append(
                _LocatedBlock(
                    "heading",
                    heading,
                    len(markdown.group(1)),
                    _source_line_locator([source_line], heading, "heading", locator_type),
                )
            )
        elif stripped and normalized in exact:
            flush()
            blocks.append(
                _LocatedBlock(
                    "heading",
                    stripped,
                    1,
                    _source_line_locator([source_line], stripped, "heading", locator_type),
                )
            )
        elif stripped and numbered_level is not None:
            flush()
            blocks.append(
                _LocatedBlock(
                    "heading",
                    stripped,
                    numbered_level,
                    _source_line_locator([source_line], stripped, "heading", locator_type),
                )
            )
        elif not stripped:
            flush()
        else:
            paragraph_lines.append(source_line)
    flush()
    return blocks, candidate_count


def _character_source_lines(raw: str) -> list[_SourceLine]:
    lines: list[_SourceLine] = []
    offset = 0
    for line_number, line in enumerate(raw.splitlines(keepends=True), start=1):
        lines.append(_SourceLine(line, line_number, start_char=offset))
        offset += len(line)
    if not lines or (raw and not raw.splitlines(keepends=True)):
        lines.append(_SourceLine(raw, 1, start_char=0))
    return lines


def _pdf_source_lines(raw: str) -> list[_SourceLine]:
    lines: list[_SourceLine] = []
    extracted_line = 0
    for page_number, page in enumerate(raw.split("\f"), start=1):
        for line in page.splitlines(keepends=True):
            extracted_line += 1
            lines.append(_SourceLine(line, extracted_line, page_number=page_number))
    return lines


def parse_markdown_or_text(
    path: Path,
    document_id: str,
    article_type: str,
) -> tuple[list[ParsedSection], int]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    blocks, _ = _text_blocks_from_lines(
        _character_source_lines(raw),
        allow_numbered_headings=path.suffix.lower() == ".txt",
        locator_type="line_char_range",
    )
    return _sections_from_blocks(blocks, document_id, article_type)


def strip_xml_namespace(tag: str) -> str:
    return tag.split("}")[-1].lower()


def element_text(element: ET.Element | None) -> str:
    return normalize_space(" ".join(element.itertext())) if element is not None else ""


def _direct_children(element: ET.Element, tag: str) -> list[ET.Element]:
    return [child for child in element if strip_xml_namespace(child.tag) == tag]


def _xml_path_map(root: ET.Element) -> dict[int, str]:
    paths: dict[int, str] = {}

    def visit(node: ET.Element, path: str) -> None:
        paths[id(node)] = path
        counts: dict[str, int] = {}
        for child in node:
            name = strip_xml_namespace(child.tag)
            counts[name] = counts.get(name, 0) + 1
            visit(child, f"{path}/{name}[{counts[name]}]")

    visit(root, f"/{strip_xml_namespace(root.tag)}[1]")
    return paths


def _xml_locator(element: ET.Element, path: str, span_kind: str) -> dict[str, int | str]:
    return {
        "locator_type": "xml_path",
        "span_kind": span_kind,
        "source_span_sha256": source_span_sha256(element_text(element)),
        "xml_path": path,
    }


def parse_jats(
    path: Path,
    document_id: str,
    article_type: str,
) -> tuple[list[ParsedSection], int]:
    root = ET.parse(path).getroot()
    xml_paths = _xml_path_map(root)
    drafts: list[_SectionDraft] = []
    paragraph_candidates = 0

    def add_sec(node: ET.Element, level: int, parent_index: int | None) -> None:
        nonlocal paragraph_candidates
        title = next((child for child in node if strip_xml_namespace(child.tag) == "title"), None)
        heading = element_text(title)
        index = len(drafts)
        paragraph_nodes = _direct_children(node, "p")
        paragraphs = [
            _LocatedText(element_text(child), _xml_locator(child, xml_paths[id(child)], "paragraph"))
            for child in paragraph_nodes
        ]
        paragraph_candidates += len(paragraphs)
        anchor = title if title is not None else node
        span_kind = "heading" if title is not None else "section_anchor"
        drafts.append(
            _SectionDraft(
                heading,
                level,
                parent_index,
                _xml_locator(anchor, xml_paths[id(anchor)], span_kind),
                paragraphs,
            )
        )
        for child in _direct_children(node, "sec"):
            add_sec(child, level + 1, index)

    abstracts = [node for node in root.iter() if strip_xml_namespace(node.tag) == "abstract"]
    if abstracts:
        abstract = abstracts[0]
        abstract_paragraph_nodes = _direct_children(abstract, "p")
        direct_paragraphs = [
            _LocatedText(element_text(child), _xml_locator(child, xml_paths[id(child)], "paragraph"))
            for child in abstract_paragraph_nodes
        ]
        paragraph_candidates += len(direct_paragraphs)
        abstract_index = len(drafts)
        drafts.append(
            _SectionDraft(
                "Abstract",
                1,
                None,
                _xml_locator(abstract, xml_paths[id(abstract)], "section_anchor"),
                direct_paragraphs,
            )
        )
        for child in _direct_children(abstract, "sec"):
            add_sec(child, 2, abstract_index)

    bodies = [node for node in root.iter() if strip_xml_namespace(node.tag) == "body"]
    if bodies:
        body = bodies[0]
        body_paragraph_nodes = _direct_children(body, "p")
        direct_body_paragraphs = [
            _LocatedText(element_text(child), _xml_locator(child, xml_paths[id(child)], "paragraph"))
            for child in body_paragraph_nodes
        ]
        if direct_body_paragraphs:
            paragraph_candidates += len(direct_body_paragraphs)
            drafts.append(
                _SectionDraft(
                    "",
                    0,
                    None,
                    _locator_with_span_kind(direct_body_paragraphs[0].source_locator, "section_anchor"),
                    direct_body_paragraphs,
                )
            )
        for child in _direct_children(body, "sec"):
            add_sec(child, 1, None)
    return _finalize_sections(drafts, document_id, article_type), paragraph_candidates


class VisibleHTMLParser(HTMLParser):
    """Extract visible blocks with stable stream-DOM paths and source positions."""

    VOID_ELEMENTS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current_tag: str | None = None
        self.current_path: str | None = None
        self.current_start: tuple[int, int] | None = None
        self.buffer: list[str] = []
        self.blocks: list[_LocatedBlock] = []
        self.suppressed_depth = 0
        self.element_stack: list[tuple[str, str]] = []
        self.child_counts: list[dict[str, int]] = [dict()]
        self.source_anchor_order = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        counts = self.child_counts[-1]
        counts[tag] = counts.get(tag, 0) + 1
        parent_path = self.element_stack[-1][1] if self.element_stack else ""
        path = f"{parent_path}/{tag}[{counts[tag]}]"
        if tag in {"script", "style", "noscript"}:
            self.suppressed_depth += 1
        if self.suppressed_depth == 0 and tag in {"p", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._flush(*self.getpos())
            self.current_tag = tag
            self.current_path = path
            self.current_start = self.getpos()
            self.source_anchor_order += 1
        if tag not in self.VOID_ELEMENTS:
            self.element_stack.append((tag, path))
            self.child_counts.append({})

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self.suppressed_depth:
            self.suppressed_depth -= 1
        if self.suppressed_depth == 0 and tag == self.current_tag:
            self._flush(*self.getpos())
        for index in range(len(self.element_stack) - 1, -1, -1):
            if self.element_stack[index][0] == tag:
                del self.element_stack[index:]
                del self.child_counts[index + 1 :]
                break

    def handle_data(self, data: str) -> None:
        if self.suppressed_depth == 0 and self.current_tag:
            self.buffer.append(data)

    def close(self) -> None:
        super().close()
        self._flush(*self.getpos())

    def _flush(self, end_line: int, end_column: int) -> None:
        if self.current_tag and self.buffer:
            text = normalize_space(" ".join(self.buffer))
            if text:
                level = int(self.current_tag[1]) if self.current_tag.startswith("h") else 0
                start_line, start_column = self.current_start or (end_line, end_column)
                locator: dict[str, int | str] = {
                    "locator_type": "html_dom_path",
                    "span_kind": "heading" if level else "paragraph",
                    "source_span_sha256": source_span_sha256(text),
                    "dom_path": self.current_path or "/html-stream[1]",
                    "source_anchor_order": self.source_anchor_order,
                    "start_line": start_line,
                    "end_line": end_line,
                    "start_column": start_column,
                    "end_column": end_column,
                }
                self.blocks.append(_LocatedBlock("heading" if level else "paragraph", text, level, locator))
        self.current_tag = None
        self.current_path = None
        self.current_start = None
        self.buffer = []


def parse_html_file(
    path: Path,
    document_id: str,
    article_type: str,
) -> tuple[list[ParsedSection], int]:
    parser = VisibleHTMLParser()
    # Feed the original source unchanged. HTMLParser already resolves character
    # references, while getpos() must continue to describe raw-file coordinates.
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    parser.close()
    return _sections_from_blocks(parser.blocks, document_id, article_type)


def parse_pdf(
    path: Path,
    document_id: str,
    article_type: str,
) -> tuple[list[ParsedSection], int]:
    executable = shutil.which("pdftotext")
    if executable is None:
        raise RuntimeError("PDF input requires an existing pdftotext executable")
    completed = subprocess.run(
        [executable, "-layout", str(path), "-"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"pdftotext failed with exit {completed.returncode}: {completed.stderr.strip()}")
    blocks, _ = _text_blocks_from_lines(
        _pdf_source_lines(completed.stdout),
        allow_numbered_headings=True,
        locator_type="pdf_page_line_range",
    )
    return _sections_from_blocks(blocks, document_id, article_type)


def _observed_qc(sections: list[ParsedSection], paragraph_candidates: int) -> dict[str, object]:
    headings = [section for section in sections if section.source_heading]
    recognized = [section for section in headings if section.canonical_section != "other"]
    paragraphs = [paragraph for section in sections for paragraph in section.paragraphs]
    fragments = [paragraph for paragraph in paragraphs if len(words(paragraph.text)) < 5]
    body_paragraphs = [
        paragraph for section in sections if section.canonical_section != "references" for paragraph in section.paragraphs
    ]
    contaminated = [paragraph for paragraph in body_paragraphs if REFERENCE_ENTRY_PATTERN.search(paragraph.text)]
    section_by_id = {section.section_id: section for section in sections}
    parent_ids_resolve = all(
        section.parent_section_id is None or section.parent_section_id in section_by_id for section in sections
    )
    parent_precedes_child = all(
        section.parent_section_id is None
        or (
            section.parent_section_id in section_by_id
            and section_by_id[section.parent_section_id].source_order < section.source_order
        )
        for section in sections
    )
    child_backlinks_consistent = all(
        child_id in section_by_id and section_by_id[child_id].parent_section_id == section.section_id
        for section in sections
        for child_id in section.child_section_ids
    ) and all(
        section.parent_section_id is None
        or section.section_id in section_by_id[section.parent_section_id].child_section_ids
        for section in sections
        if section.parent_section_id in section_by_id
    )
    parser_invariants = {
        "parent_precedes_child": parent_precedes_child,
        "parent_ids_resolve": parent_ids_resolve,
        "child_backlinks_consistent": child_backlinks_consistent,
        "all_passed": parent_precedes_child and parent_ids_resolve and child_backlinks_consistent,
    }
    retained = len(paragraphs)
    return {
        "heading_count": len(headings),
        "recognized_heading_count": len(recognized),
        "heading_recognition_rate": round(len(recognized) / len(headings), 4) if headings else 0.0,
        "paragraph_candidate_count": paragraph_candidates,
        "retained_paragraph_count": retained,
        "empty_paragraph_rate": round(max(0, paragraph_candidates - retained) / paragraph_candidates, 4) if paragraph_candidates else 0.0,
        "fragment_paragraph_rate": round(len(fragments) / retained, 4) if retained else 0.0,
        "reference_contamination_rate": round(len(contaminated) / len(body_paragraphs), 4) if body_paragraphs else 0.0,
        "parser_invariant_checks": parser_invariants,
    }


def parse_document(path: Path, document_id: str, article_type: str) -> ParsedDocument:
    suffix = path.suffix.lower()
    if suffix == ".md":
        sections, candidates = parse_markdown_or_text(path, document_id, article_type)
        source_format = "markdown"
    elif suffix == ".txt":
        sections, candidates = parse_markdown_or_text(path, document_id, article_type)
        source_format = "plain_text"
    elif suffix in {".xml", ".nxml"}:
        sections, candidates = parse_jats(path, document_id, article_type)
        source_format = "jats_xml"
    elif suffix in {".html", ".htm"}:
        sections, candidates = parse_html_file(path, document_id, article_type)
        source_format = "html"
    elif suffix == ".pdf":
        sections, candidates = parse_pdf(path, document_id, article_type)
        source_format = "pdf_text"
    else:
        raise RuntimeError(f"Unsupported input suffix: {suffix}")
    if not sections or not any(section.paragraphs for section in sections):
        raise RuntimeError("No usable paragraphs or sections were extracted")
    observed = _observed_qc(sections, candidates)
    warnings: list[dict[str, str]] = []
    if observed["heading_recognition_rate"] < 0.5:
        warnings.append(warning("low_heading_recognition", "Fewer than half of source headings received a recognized canonical mapping"))
    if observed["fragment_paragraph_rate"] > 0.2:
        warnings.append(warning("high_fragment_paragraph_rate", "More than 20% of retained paragraphs are shorter than five tokens"))
    if observed["reference_contamination_rate"] > 0.05:
        warnings.append(warning("possible_reference_contamination", "Body paragraphs contain reference-entry-like patterns"))
    parser_invariants = observed["parser_invariant_checks"]
    if isinstance(parser_invariants, dict) and not parser_invariants["all_passed"]:
        warnings.append(warning("parser_invariant_failure", "One or more section-tree invariants failed", "error"))
    if source_format == "pdf_text":
        warnings.append(warning("pdf_layout_risk", "PDF-derived hierarchy and paragraph boundaries require gold or manual review"))
    return ParsedDocument(
        document_id=document_id,
        article_type=article_type,
        source_path=path,
        source_format=source_format,
        source_sha256=sha256_file(path),
        sections=sections,
        parser_format_prior=FORMAT_PRIORS[source_format],
        observed_parse_qc=observed,
        warnings=warnings,
    )
