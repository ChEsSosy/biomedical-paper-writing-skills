# Article Polisher deterministic core 0.1.4 patch record

Status: candidate; not frozen, installed, or activated.

## Preserved predecessor disposition

Core candidate 0.1.3 is preserved as exact-source review-rejected evidence. It correctly required an approved target claim and exact approved/zero-open-item plan summary, but still admitted an artifact whose top-level `author_approved` label contradicted nested approval state.

Reproduced false-passes included a pending plan story anchor, pending plan author decision, open plan gap, unrelated pending plan section/paragraph, pending claim-map central question, and unrelated pending claim-map child.

## Authorized 0.1.4 patch

Core 0.1.4 adds one unified authority-state consistency gate before a manuscript plan or claim/evidence map can act as M03 authority:

- all nested `author_approval` values must be `approved`;
- declared author decisions must be terminal (`approved` or `rejected`);
- plan gaps must be terminal (`resolved` or `accepted_risk`);
- the existing exact plan-summary and target relation checks remain mandatory.

This gate does not copy the M02 scientific/story checker, reassess scientific quality, change a schema, or infer approval.
