# Article Polisher deterministic core 0.1.3 patch record

Status: candidate; not frozen, installed, or activated.

## Preserved predecessor disposition

Core candidate 0.1.2 is preserved as exact-source review-rejected evidence. It closed the earlier absent/invented/hash-mismatched provenance defects, but still treated a top-level `author_approved` M02 artifact as authority when the approval state used by M03 was internally contradictory.

Two exact false-passes were reproduced in review:

- Results/Discussion `information_reorder` accepted a target claim whose `author_approval` remained `pending` while evidence and link approvals were `approved`.
- It accepted a plan whose top-level status was `author_approved` while `approval_summary` declared a pending overall state and nonzero pending/open counts.

## Authorized 0.1.3 patch

Core 0.1.3 adds only the authority invariants M03 relies on:

- every proposition used by topic repair or Results/Discussion relation closure must itself have `author_approval: approved`;
- an M02 plan used as authority must have top-level `status: author_approved`, `approval_summary.overall_status: approved`, and exact zero integer values for both `pending_decision_count` and `open_blocker_count`;
- the plan invariant also applies to Deep structural decisions, because the same plan is their authority source.

This patch does not duplicate the full M02 scientific checker, change the M03 contract/schema, or infer approval.

