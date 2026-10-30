# Module 05 mode routing

## Admission

- `original_article`: require a validated Phase 9 `H02-STORY-TO-05` handoff carrying the exact manuscript plan, claim/evidence map, and every Figure-referenced interpretation card. Normalize only their admitted Figure sequence, claims, evidence, relations, visibility requirements, identities, versions, and hashes into Phase 8A.
- `review_article`: require a validated Phase 9 `H04-ARCHITECTURE-TO-05` handoff carrying the exact Review scope, source registry, synthesis matrix, outline, referenced extraction records, and authority records. Only `output_type: figure` briefs are admissible.
- With no runtime handoff instance, remain blocked. Presence of a path, embedded approval string, or fluent summary is not admission.

## Public modes

1. `design_review_only`: validate or review Phase 8A design artifacts and a standalone design-revision proposal. No execution.
2. `prototype_execution_and_inspection`: freshly revalidate Phase 8A, generate the exact allowlisted program, verify external authorization, execute in a new bounded directory, record outputs, and validate the Phase 8B chain.

The Phase 8B code-generation operation is internal to mode 2 and is not exposed as a separate public mode.

## Stop conditions

Stop on an unresolved identity/hash, missing source or authority, unsupported backend, arbitrary code, requested statistical recomputation, missing execution authorization, existing output collision, or any attempt to promote prototype or inspection maturity beyond the frozen contracts.
