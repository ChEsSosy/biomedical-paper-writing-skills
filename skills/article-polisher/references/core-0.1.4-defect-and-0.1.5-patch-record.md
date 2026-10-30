# Article Polisher deterministic core 0.1.5 patch record

Status: candidate; not frozen, installed, or activated.

## Preserved predecessor disposition

Core candidate 0.1.4 is preserved as exact-source review-rejected evidence. Its plan and claim-map authority-state gates passed review, but Deep closure still trusted an interpretation card's top-level `author_approved` label without checking nested approvals or decisions. A supplied card not named by `plan.interpretation_card_ids` could also satisfy a boundary solely by reusing the same `boundary_id`, even from another manuscript.

## Authorized 0.1.5 patch

Core 0.1.5 adds one interpretation-card authority gate and tightens Deep closure:

- require `status: author_approved`, `document_type: original_article`, and the same `manuscript_id` as the plan;
- require every nested `author_approval` to be `approved` and every card author decision to be terminal;
- resolve direct card references and boundary references only through exact hash-bound artifacts named by `plan.interpretation_card_ids`;
- preserve the existing plan, claim-map, target-relation, mode, and structural-authorization checks.

This patch does not duplicate M02 scientific/story assessment, change schemas, widen operations, or infer approval.
