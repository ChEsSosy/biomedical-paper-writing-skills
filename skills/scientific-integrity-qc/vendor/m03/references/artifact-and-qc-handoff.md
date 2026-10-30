# Artifact and QC Handoff

## Required M03 outputs

- `candidate-document.json`: identified candidate; never a replacement for the source.
- `revision-lineage-map.json`: exact source/candidate identity binding with origin `deterministic_patch_layer`.
- `change-manifest.json`: one record for every deterministic changed paragraph/unit, with exact operation, permission, rationale, risk, locators, and upstream/profile references. Upstream references are admissible only when the separately supplied artifact has the same ID, type, version, and canonical SHA-256; a proposal cannot mint provenance by declaring these fields itself.
- `author-query-list.json`: unresolved questions with source locators; no fabricated answers.
- `change-inventory.json`: frozen-core validator evidence.
- `patch-application-receipt.json`: applied-operation and authority-boundary receipt.

The patch command validates the revision contract before application, then validates all outputs against the frozen M03 core before writing them to a new or empty output directory. `ready_for_independent_qc` means only that M03 package admission passed.

## Failure behavior

Stop on stale source text/hash, source or contract mismatch, unapproved execution, out-of-scope or unsupported operations, conflicting operations, invalid lineage, incomplete manifest coverage, unresolved blocking queries on changed units, missing Deep closure, or mismatched package dependencies. Preserve the source and proposal for review; do not auto-repair or loop.

H03 requires the change manifest, author query list, revision lineage map, and exact source/candidate identities. Until the separate M06 integration contract and consumer package are frozen, H03 remains explicitly non-executable even when the producer output is ready.
