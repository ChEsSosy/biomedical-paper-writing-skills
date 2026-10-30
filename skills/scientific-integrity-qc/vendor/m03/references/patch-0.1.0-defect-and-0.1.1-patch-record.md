# Patch-layer 0.1.0 Defect and 0.1.1 Narrow Correction

## Reproduced defect

Patch layer `0.1.0` placed `information_reorder` and `topic_sentence_repair` in the set admitted by Light mode. A Light contract that listed either operation could therefore produce a candidate that the frozen structural core accepted when no observable sentence-count/order change occurred. This contradicted frozen M03 contract `0.1.2`, which introduces both operations only in Medium mode.

Exact reproduction for `information_reorder` returned:

```text
applied: true
core_issue_count: 0
ready_for_independent_qc: true
```

## Narrow correction

Candidate `0.1.1` separates the Light operation vocabulary from Medium additional text operations. Light now rejects both operations before application; Medium and Deep retain them subject to all existing proposition, scope, authorization, lineage, manifest, and QC boundaries. Contract schema validation is also moved before patch application so malformed authority artifacts stop before candidate construction.

No frozen M03 core, schema, M01/M02 package, Item 1 source, or Phase 9 contract is modified. Patch-layer `0.1.0`, package candidate `0.1.0`, and Item 3 candidate `0.1.0` remain preserved as rejected pre-review evidence.
