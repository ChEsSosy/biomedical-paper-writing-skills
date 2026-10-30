# QC Severity and Gate Semantics

## Independent dimensions

Each finding records a severity, an execution state, and a review status. These fields are not interchangeable.

| Dimension | Values | Meaning |
|---|---|---|
| Severity | `blocker`, `error`, `warning`, `info` | Risk and gate consequence, not scientific truth |
| Execution | `passed`, `failed`, `unassessable`, `skipped_with_reason` | Whether the declared check could execute and what it observed |
| Finding status | `open`, `author_review_required`, `accepted`, `resolved`, `dismissed` | Human-decision state |

## Gate precedence

The minimum implementation applies this order:

1. Any unresolved blocker or error → `fail`.
2. Otherwise, any required check that is unassessable or skipped → `unassessable`.
3. Otherwise, any unresolved warning → `pass_with_warnings`.
4. Otherwise → `pass`.

Every outcome except a clean `pass` requires `human_review_required: true`. `pass_with_warnings` is never interchangeable with `pass`.

The human-decision queue exactly lists unresolved findings. The package validator deterministically recomputes findings and report decision fields from the manifest and both snapshots; hand-editing an outcome or count invalidates the package.

## Severity use

- Identity/hash failure or mandatory-contract absence: blocker.
- Deterministic protected-anchor mismatch: error.
- Local lexical semantic-risk change: warning.
- Exact approved exception applied: accepted info.

Unsupported execution is reported explicitly and cannot be hidden by zero matches.
