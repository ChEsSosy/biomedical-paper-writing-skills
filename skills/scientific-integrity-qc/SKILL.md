---
name: scientific-integrity-qc
description: Validate exact Article, Review, or Figure producer packages against the frozen Module 06 admission contract and emit deterministic integrity-QC gate artifacts. Use after Module 03, 04, or 05 has produced a complete hash-bound package. Do not use to rewrite content, certify scientific truth, grant author approval, or install/activate any skill.
metadata:
  short-description: Gate Article, Review, and Figure outputs for integrity QC
---

# Scientific Integrity QC

Use this package only as the downstream consumer of one exact frozen producer route:

- `article_revision` from Article Polisher;
- `review_revision` from Review Architect Polisher;
- `figure_qc` from Scientific Figure Designer.

Do not mix artifacts across routes. Require the complete artifact closure declared by the versioned `0.1.2` integration registry, exact file hashes, caller-held hashes for authority-bearing artifacts, and a fresh validation by the vendored producer.

Run:

```text
python -B integration/scripts/run_integrated_qc.py --request REQUEST.json --invocation-root INPUT_ROOT --output-dir NEW_OUTPUT_DIR
```

The output directory must not already exist. A rejected admission is recorded as `blocked`. Article and Review assessment is limited to domains that are both declared and implemented; every requested but unimplemented domain remains `not_assessed` or `unassessable`. Figure integration cannot produce a clean pass and always preserves the producer's degraded or author-review-required state.

Never rewrite source artifacts, repair producer packages, infer scientific truth, or claim author approval. This candidate is not installed or activated.
