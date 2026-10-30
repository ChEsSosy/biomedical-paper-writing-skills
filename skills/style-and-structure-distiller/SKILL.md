---
name: style-and-structure-distiller
description: Extract traceable observable structure and deterministic section-aware statistics from a curated corpus of authorized biomedical Original Articles or Review Articles. Use for corpus parsing, structure maps, Figure-reference maps, style distributions, parser QC, or corpus-balance analysis; do not use for scientific-content synthesis, semantic manuscript-role classification, author imitation, drafting, or polishing.
metadata:
  short-description: Measure biomedical corpus style and structure
---

# Style and Structure Distiller

Build Phase 3.1 artifacts that answer only: **what source-derived structure and deterministic measurements are observably present?** Keep Original Article and Review corpora separate. Never treat the corpus as a source of reusable scientific claims.

## Non-negotiable boundary

Do not infer whether a section is establishment, primary evidence, validation, mechanistic support, in-vivo relevance, controversy, translation, or another manuscript-story role. Those are Phase 3.2 model-assisted annotations and require a fixed taxonomy, located context, classification evidence, contamination review, and author review.

Do not extract or reuse hypotheses, mechanisms, conclusions, novelty claims, favored pathways, author positions, research priorities, personality, values, worldview, distinctive phrases, captions, or published Figure layouts. Store locators and aggregate measurements, not reusable prose.

## Required inputs

- An authorized local corpus containing only `original_article` or only `review_article` documents.
- A `corpus_manifest` with stable document IDs, source paths, corpus metadata, access/use status, inclusion decisions, and provenance. Production extraction requires author approval; an explicit diagnostic `run --draft` accepts `author_review_required` without granting approval.
- An explicit inclusion/exclusion rule and intended aggregate profile use.

Read [references/corpus-governance.md](references/corpus-governance.md) before accepting a corpus. Read [references/section-taxonomy.md](references/section-taxonomy.md) when reviewing hierarchy or canonical mappings. Read [references/feature-catalog.md](references/feature-catalog.md) before interpreting statistics. Read [references/confidence-and-qc.md](references/confidence-and-qc.md) before interpreting support evidence or parser quality. Apply [references/prohibited-content-boundary.md](references/prohibited-content-boundary.md) to every proposed reusable output.

## Workflow

1. Inventory supported files with `scripts/distill_corpus.py init-manifest`. The draft remains intentionally incomplete and `author_review_required`.
2. Have the author review bibliographic metadata, scientific-domain and experiment labels, corpus/lab grouping, access notes, inclusion status, and corpus type. Group metadata is for bias control, never imitation.
3. Validate the approved manifest against `schemas/corpus-manifest.schema.json`.
   For PDF-derived Markdown needing prose selection, read [references/markdown-projection.md](references/markdown-projection.md) and use `scripts/project_markdown.py` with exact source-bound exclusions. Box/Table headings never authorize dropping all following paragraphs. Retain real body Summary sections. Changing source bytes or selection creates a review-required manifest; do not inherit approval automatically.
4. Run `scripts/distill_corpus.py run` to generate source-derived document artifacts plus deterministic corpus aggregates.
5. Inspect section trees, real source locators, paragraph boundaries, Figure-reference links, observed parser QC, parser invariants, failures, and `other` mappings before interpreting distributions.
6. Prefer document-weighted summaries. Use token-weighted summaries only when the intended question explicitly concerns pooled text rather than a typical document.
7. Inspect per-feature support evidence and `corpus-balance.json`; do not convert provisional support evidence into unsupported high/medium/low labels.
8. Validate all artifacts. Keep outputs `author_review_required` until the author reviews their intended use.

## Phase 3.1 outputs

- per document: `document-record`, `section-map`, and `figure-reference-map`;
- per corpus: `style-profile`, `structure-profile`, and `corpus-balance`;
- run summary with included, excluded, failed, and warning counts.
- optional `observable_structure_gold_evaluation` against an author-approved, source-located gold standard.

The epistemic classes remain separate:

- section and Figure-reference maps are source-derived structure;
- style, structure, and balance profiles are deterministic measurements and aggregation;
- future `architecture-annotations` are bounded model-assisted classifications requiring human review;
- future `architecture-profile` artifacts aggregate reviewed annotations across documents.

Never overload `structure-profile` with semantic annotations or final manuscript-architecture patterns.

## Input support and failure behavior

- Prefer JATS/XML when available; nested JATS sections and structured abstracts retain parent IDs and heading levels.
- Markdown and HTML retain heading hierarchy when encoded in the source. Plain text and PDF use conservative heading heuristics and require closer review.
- `parser_locator` is an internal stable ordinal only. Use the format-specific `source_locator` plus `source_span_sha256` for provenance and gold matching.
- PDF requires an existing `pdftotext`; absence or extraction failure is explicit.
- Reject mixed Article/Review manifests, duplicate IDs or source hashes, missing files, hash mismatches, and excluded documents without reasons. Ordinary runs reject unapproved manifests; explicit draft diagnostics accept only `author_review_required`.
- Never overwrite an existing manifest or a non-empty output directory.

## Local maintenance version

Implementation 0.2.9 adds hash-bound paragraph relocation for PDF reading-order displacement to the 0.2.8 projection workflow. It resolves the hash-bound vendored `shared-core` inside this package. Diagnostic success establishes execution and provenance, not corpus completeness or author approval. Keep real-paper plans and outputs in the user's project, outside this reusable Skill.

See [maintenance provenance](references/maintenance-0.2.9.md) when reviewing this update against the prior local maintenance version.
