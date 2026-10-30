# Review revision workflow

Use this path only after a valid Phase 7A package and a structured Review source exist. The exact contract and registry are in `phase7b-revision-interface-contract.md` and `phase7b-interface-registry.json`.

For writing decisions, read [synthesis-and-expression-guidance.md](synthesis-and-expression-guidance.md). Match the proposal to the user's purpose as well as the authorized mode. A request for same-sentence professionalization retains every proposition and sentence position; return structural or content changes as separate suggestions. Translation and synthesis are distinct tasks and do not follow automatically from a wording request.
For the same-sentence task, use [sentence-preserving-expression.md](sentence-preserving-expression.md) to check the sentence's evidentiary job and meaning-bearing fields. Treat any supplied project expression note as conditional editorial guidance, not a machine-approved style profile.

## Modes

- Light: grammar, punctuation, syntax, clarity, lexical tightening, and local transitions inside one existing unit; no sentence/paragraph movement or scientific-anchor delta.
- Medium: Light plus sentence split/merge/reorder and local thematic repair within one approved paragraph; citation identity and approved claim/relation attachment must remain exact.
- Deep: only exact author-approved permission decisions may authorize paragraph split/merge/move, section move, theme reorganization, or an authorized draft-slot materialization.

## Application sequence

1. Validate the Review route, source identity, Phase 7A closure, permission canonical hash, caller-held expected hash, mode, operation scope, exact targets, decisions, and blocking queries.
2. Produce a machine proposal with exact source locators/hashes, replacement units, closure IDs, and decision binding. Explain the expression or argument benefit; check retained meaning and the specific conditions needed by the reader. If consolidation would violate protected-change or citation rules, return it upstream as a query instead of applying it. Do not model-declare candidate lineage or trusted authority.
3. Apply to a new output directory. Never overwrite source or prior output.
4. Recompute candidate hashes and locators, lineage, all observed structural effects, and all protected deltas. Canonicalize supported citation identities, inventory identity-preserving surface changes as `formatting_only`, fail closed on unresolved citation-like author-year syntax or a citation boundary inside an unresolved lexical gap, retain distinct start/end identities for non-empty replace gaps, and record resolved citation placement/syntactic-role changes as `placement_changed`.
5. Require complete manifest, author-query, lineage, inventory, hash-bound application-receipt, and package-validation closure. Reject orphan candidate prose, undeclared diffs, declared-but-absent changes, or protected changes outside the exact contract.
6. Return `ready_for_independent_qc` only when deterministic producer checks pass. Keep `author_review_required: true`. Module 06 admission requires its separate, actually executed check on the exact producer package; producer success cannot change a static blocked handoff or stand in for a consumer result.

An authorized draft slot may materialize only exact allowlisted citations or protected tokens and must include every required materialization. It does not authorize new literature, conversion, recalculation, or unsupported prose.

