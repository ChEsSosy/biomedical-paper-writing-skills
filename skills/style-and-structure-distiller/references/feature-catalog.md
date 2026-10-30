# Deterministic Feature Catalog

Every reported feature must have a stable definition, unit, normalization rule, and support record. Scientific nouns, propositions, and topic-specific phrase lists are excluded.

## Aggregation contract

The required observation hierarchy is:

```text
sentence or paragraph observation
→ document × canonical section summary
→ across-document distribution
→ corpus-stratum coverage
```

Document-weighted summaries are the primary interpretation. Token-weighted summaries are retained as a distinct pooled-text view. Subsections are never treated as independent corpus documents.

## Length and organization

- words per document/section;
- words per sentence;
- words and sentence count per paragraph;
- section and subsection counts;
- paragraph counts by canonical section;
- heading depth;
- child-edge count per document × canonical section;
- mean direct-child count per root section instance within each document.

Sentence segmentation is heuristic. Counts therefore travel with parser-format priors, observed QC, and empirical gold evaluation when available.

## Functional surface markers

Counts are normalized per 1,000 words within each document × canonical section before across-document aggregation:

- first-person plural;
- explicit hedges;
- contrast, consequence, and addition transitions;
- Figure and Table references;
- numeric and author-year citation shapes;
- a conservative passive-construction marker.

The passive metric is a marker rate, not a grammatical passive-voice percentage.

## Reference positioning

Citation and Figure-reference occurrences are counted by sentence position within a paragraph: `single_sentence`, `opening`, `middle`, or `closing`. Phase 3.1 records position only. It does not decide why a reference was placed there or what evidentiary role it serves.

## Observable structure

- raw and canonical section trees;
- paragraph boundaries and locators;
- canonical section presence and sequence;
- section-instance and subsection-count distributions;
- many-to-many Figure, Extended Data Figure, and Supplementary Figure references;
- Figure-reference counts by canonical section;
- corpus balance across available metadata strata.

## Per-feature support evidence

Each document-weighted feature carries document count/coverage, median and quartiles, fixed-seed bootstrap interval, robust between-document dispersion, explicitly named leave-one-document-out median sensitivity, parser-support distributions, and contributor-aware stratum coverage. These are evidence fields, not a model confidence score.

## Explicitly deferred

Paragraph roles, rhetorical moves, Results evidence roles, Review synthesis roles, evidence chains, mechanisms, novelty, and manuscript-story patterns belong to Phase 3.2 or Phase 3.3 and never appear as deterministic output here.
