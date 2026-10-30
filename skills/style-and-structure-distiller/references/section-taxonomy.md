# Observable Section Taxonomy

Use this reference to review deterministic hierarchy and canonical mappings. Phase 3.1 stores both the source hierarchy and the aggregation hierarchy; canonicalization must not erase source headings, levels, parents, order, or locators.

## Source hierarchy contract

Each located section records:

- stable `section_id` and nullable `parent_section_id`;
- `child_section_ids` and sibling/source order;
- exact short `source_heading`, heading level, source parent heading, and depth;
- canonical section and canonical parent section;
- mapping basis and an explicitly prior-like mapping score;
- paragraph IDs, counts, word count, internal parser locator, and recoverable source locator.

Paragraphs are represented by IDs, section links, order, counts, `parser_locator`, and `source_locator`. The parser locator is never evidence of a real source position. Source locators use line/character ranges for Markdown/TXT, XML paths for JATS, DOM paths plus source positions for HTML, and page/extracted-line ranges for PDF text. Each carries a normalized source-span SHA-256. Full paragraph text is not stored in the reusable artifacts.

## Original Article canonical sections

Use `abstract`, `introduction`, `methods`, `results`, `discussion`, `results_discussion`, `conclusion`, `figure_legend`, `data_availability`, `references`, `front_matter`, or `other`.

Unknown subsections under an explicit canonical parent inherit that parent for aggregate statistics while preserving their raw heading and tree position. Thus a named Results subsection remains visibly distinct in `section-map` but contributes to the `results` aggregate.

Do not infer a scientific or rhetorical role from the subsection heading.

## Review Article canonical sections

Use the shared front/back-matter labels where explicit. Unrecognized thematic body headings map to `review_body`, but each heading remains a separate tree node. Never collapse the source tree to one undifferentiated block merely because consecutive nodes share `review_body`.

## Mapping evidence

A `Summary` subsection beneath a `review_body` parent inherits `review_body`; its exact source heading is retained. A top-level `Summary` or one within an Abstract retains the Abstract mapping. Do not discard body text to work around canonical-label collisions.

`canonical_mapping_basis` is one of:

- `exact_heading`;
- `heading_synonym`;
- `inherited_parent`;
- `review_thematic`;
- `front_matter`;
- `unrecognized`.

`canonical_mapping_prior` describes deterministic rule strength, not empirical parser accuracy. Gold evaluation separately measures canonical-section accuracy.
