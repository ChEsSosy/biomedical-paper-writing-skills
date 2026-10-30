# Article Polisher Patch/Application Layer 0.1.6

This additive candidate implements the deterministic application boundary required by Phase 9 Item 3. Historical Module 03 candidates remain preserved; the residual non-key referenced-boundary closure defect reproduced during Item 3 0.1.5 review is corrected only in separately versioned core candidate `0.1.6`.

## Implemented operations

- exact one-sentence replacement for the frozen non-structural operation vocabulary;
- deterministic sentence split and merge in Medium or Deep mode;
- exact full-paragraph sentence reordering in Medium or Deep mode;
- exact whole-document paragraph reordering in Deep mode with a matching author-approved structural authorization and upstream-plan reference.

Patch layer `0.1.6` enforces the frozen mode vocabulary: `information_reorder` and `topic_sentence_repair` require Medium or Deep and cannot be admitted under Light even if a malformed caller contract lists them. Results/Discussion information reordering requires an exact author-approved paragraph baseline, a fresh authority-state consistency check over the supplied plan and claim map, and approved claim/evidence relations including the target claim itself. Deep interpretation-card and boundary closure accepts only exact hash-bound cards named by the plan, from the same Original Article manuscript, with internally consistent approvals; this applies to every explicit `boundary:` reference in the approved decision, not only story-anchor key boundaries. Topic-sentence repair must resolve every approved proposition to the affected paragraph through supplied, hash-bound approved provenance. `profile_alignment` must resolve its feature in an actual supplied, hash-bound, author-approved Original Article M01 profile. The layer deliberately rejects paragraph split/merge, cross-paragraph sentence operations, mixed paragraph movement plus text operations, and more than one operation per source paragraph. These are explicit bounded implementation limits, not silent degradation.

## Authority and output boundary

The proposal remains `machine_proposed`. It cannot supply trusted lineage, approve itself, widen scope, or alter its revision contract. Candidate lineage is derived from operation semantics and emitted with origin `deterministic_patch_layer`. Every candidate remains `author_review_required` and must pass the frozen M03 package validator before independent M06 comparison/QC. Neither deterministic validation nor later QC creates scientific truth or author approval.
