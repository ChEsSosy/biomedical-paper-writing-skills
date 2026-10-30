# Support Evidence and Parser Quality

Phase 3.1 reports observable evidence. It does not assign `high`, `moderate`, or `low` support labels before real-paper pilots establish defensible thresholds.

## Three separate evidence classes

1. `parser_format_prior` is a documented pre-observation prior associated with an input format. It is not measured accuracy.
2. `observed_parse_qc` is computed from the current extraction: heading recognition, empty/fragment paragraph rates, and reference contamination. Tree consistency is reported separately as `parser_invariant_checks`; passing an invariant is not extraction accuracy.
3. `gold_evaluation` compares source-located parser output with manually approved structure annotations and produces empirical metrics.

Never rename a format prior as parse quality or merge these classes into an unexplained score.

## Per-feature support

For each document-weighted feature, report where applicable:

- contributing document count and section coverage;
- value count, median, quartiles, minimum, and maximum;
- fixed-seed document bootstrap interval for the median;
- robust IQR-to-median dispersion;
- `leave_one_document_out_median_sensitivity`, defined as the maximum leave-one-document-out median shift;
- parser-format-prior and observed-QC distributions for contributing documents;
- coverage of available journal, year, domain, experiment, group, subtype, language, and source-format strata, including contributor counts, minimum support, maximum contributor share, and effective-stratum count.

No aggregate profile confidence number is emitted.

## Required QC

- schema validation for every generated artifact;
- source existence, optional SHA-256 match, unique document IDs, and duplicate-content detection;
- exact raw-source SHA-256 binding between every gold document and the evaluated artifacts;
- strict Article/Review separation;
- included, excluded, failed, and warning counts;
- raw/canonical hierarchy checks and parent-before-child order;
- parser-format and observed-QC reporting;
- many-to-many Figure-reference extraction checks;
- prohibited-content audit;
- deterministic rerun tests;
- synthetic gold evaluator tests before real-paper pilot use.

Gold metrics keep heading detection, heading-level accuracy, parent-node hierarchy, canonical mapping, paragraph boundary shifts, fragmentation, erroneous merges, unclassifiable boundary errors, Figure IDs, panel tokens, and full-reference exact match separate. A one-to-one endpoint change is not counted as both a split and a merge. Gold performance is parser evidence, not scientific validity. All generated profiles remain `author_review_required`.
