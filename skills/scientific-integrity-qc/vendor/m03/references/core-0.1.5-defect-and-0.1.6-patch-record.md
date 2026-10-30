# Article Polisher deterministic core 0.1.6 patch record

Status: candidate; not frozen, installed, or activated.

## Preserved predecessor disposition

Core candidate 0.1.5 is preserved as exact-source review-rejected evidence. It correctly enforced interpretation-card internal approval, plan membership, same-manuscript identity, and exact hash binding, but detected referenced boundaries only through `story_anchors.key_boundary_ids`. An approved Deep decision could therefore reference a planned card's non-key boundary while omitting that card and still pass closure.

## Authorized 0.1.6 patch

Core 0.1.6 changes only Deep boundary-reference detection. Explicit `boundary:` identifiers in the approved decision's `related_ids` are treated as boundary references regardless of whether they are story-anchor key boundaries. Each must resolve through an exact hash-bound, internally consistent, same-manuscript interpretation card listed in `plan.interpretation_card_ids`.

The patch does not treat every `related_id` as a boundary, change schemas or namespaces, copy the M02 semantic checker, or alter any non-Deep rule.
