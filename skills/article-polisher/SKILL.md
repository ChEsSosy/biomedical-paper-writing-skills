---
name: article-polisher
description: Revise an author-owned Original Research Article within an exact permission contract, applying locator-bound prose proposals through a deterministic patch layer with change manifests, trusted lineage, and independent-QC handoff. Use for bounded Article polishing; do not use for Review Articles, unrestricted rewriting, or unsourced scientific changes.
metadata:
  short-description: Apply auditable Original Article revisions
---

# Article Polisher

Improve the clarity, precision, and flow of an Original Research Article without changing its supplied science or silently widening its approved structure. Under this Skill, any proposed replacement prose requires the exact external revision contract below. The deterministically applied package remains `author_review_required` and needs independent scientific-integrity QC.

## Scope before revision

If the user supplies only an unstructured Article sentence or draft, identify wording problems and explain applicable meaning-preservation principles. Ask for the missing source identity and external revision contract before producing a replacement sentence, clean revised prose, or a locator-bound proposal. Do not mint a permission artifact or call the diagnostic a completed revision.

Once the contract and source are admitted, use [sentence-preserving-expression.md](references/sentence-preserving-expression.md) for same-sentence work. This common guide needs no style profile but never substitutes for the revision contract. A corpus-derived expression note must explicitly support Original Articles with source locators and applicability; the project-specific mRNA Review note cannot supply Article conventions or scientific facts. Wording intent alone cannot bypass missing contracts, hashes, scope or upstream closure. Never overwrite the source.

## Deterministic application admission

Require:

- an identified structured source with `document_type: original_article`, stable paragraph/sentence units, and exact artifact hash;
- an external `revision_contract` binding that source, the editable paragraph units, mode, allowed operations, frozen anchors, origin, and authorization state;
- a caller-accepted Light/Medium permission or an author-approved permission; Deep additionally needs exact author-approved M02 structural decisions and their referenced artifact closure;
- paragraph-function and experiment labels for editable units.

Reject Review Articles, `machine_proposed` execution permission, stale source bindings, out-of-scope operations, untraceable rewriting, and unsupported structure changes. Route Review work to `review-architect-polisher`.

Optional inputs are an M01 Article profile, an M02 plan/claim-evidence bundle, a terminology map, and a verified target-journal profile. Missing optional inputs narrow guidance; they never authorize inference.

## Deterministic application workflow

1. Freeze exact source, permission, scope, mode, protected anchors, unresolved questions, and any admitted M01/M02 identities.
2. Diagnose prose locally. Read [revision-modes.md](references/revision-modes.md) and the relevant section/experiment guidance in [section-and-experiment-guides.md](references/section-and-experiment-guides.md). For a same-sentence wording task, use [sentence-preserving-expression.md](references/sentence-preserving-expression.md) to check expression and proposition preservation.
3. Write a `machine_proposed` locator-bound revision proposal matching `schemas/revision-proposal.schema.json`. Bind every operation to exact source text and SHA-256. Do not supply lineage or approval fields.
4. If using an M01 profile, read [target-profile-usage.md](references/target-profile-usage.md). Reference only supported aggregate feature IDs; never copy phrases or infer scientific content from the corpus.
5. Apply the proposal with `scripts/apply_revision_proposal.py`. The deterministic layer—not the language model—creates the candidate, lineage map, complete change manifest, query list, and change inventory.
6. Run the frozen package validator. Read [artifact-and-qc-handoff.md](references/artifact-and-qc-handoff.md) for exact outputs and failure handling.
7. Deliver both source and candidate identities, all manifest/query artifacts, validator results, remaining limits, and explicit author decisions. Never replace the source file.

## Scientific authority boundary

- Do not invent or silently alter data, numbers, units, statistics, citations, entities, methods, controls, mechanisms, novelty, limitations, causal level, claim scope, or evidence relations.
- Do not infer missing reporting details; create an author query.
- Do not use style preference to strengthen a claim, erase a qualifier, suppress negative/conflicting evidence, or change a Figure/Table reference.
- A schema pass or deterministic lineage proves package consistency only. It does not prove semantic equivalence, scientific truth, evidence sufficiency, journal compliance, or author approval.
- Do not start an automatic rewrite–QC loop. Return failures and queries to the caller or author.

## Implemented patch surface

Patch layer `0.1.6` supports exact Light sentence-level language edits, provenance-bound Medium/Deep information reordering and topic-sentence repair, Medium/Deep sentence split or merge, exact full-paragraph sentence reordering, and Deep whole-document paragraph reordering with exact approved authorization. For Results/Discussion reordering, supply the exact M02 plan and claim/evidence map with internally consistent author-approval state; top-level approval labels cannot override nested pending/open authority states. For every explicit Deep interpretation or `boundary:` reference, including a non-key boundary, supply the exact hash-bound interpretation card named by the plan, from the same manuscript, with all nested approvals and decisions resolved. For topic-sentence repair, supply provenance that resolves each approved proposition to the affected paragraph. For `profile_alignment`, supply the exact approved M01 profile containing the referenced feature-support record. It intentionally rejects paragraph split/merge, cross-paragraph sentence operations, mixed paragraph movement plus text edits, and multiple operations in one source paragraph per application run.

## Deterministic commands

Run from this Skill directory with Python 3:

```text
python scripts/apply_revision_proposal.py --source-document <source.json> --revision-contract <contract.json> --revision-proposal <proposal.json> --output-dir <new-output-dir> [--upstream-artifact <artifact.json> ...]
python scripts/validate_revision_package.py --source-document <source.json> --candidate-document <candidate.json> --lineage-map <lineage.json> --revision-contract <contract.json> --change-manifest <manifest.json> --author-queries <queries.json> [--upstream-artifact <artifact.json> ...]
```

The schema validator is loaded only from the hash-bound package trust root or from a byte-identical explicit copy. A missing or mismatched dependency is a hard failure.

## Deterministic package delivery

Return the revised candidate as an identified, non-final artifact together with the exact source identity, revision contract, deterministic lineage, complete change manifest, author queries, inventory, and validation status. Use `ready_for_independent_qc` only to mean M03 admission succeeded. M06 is a separate consumer execution with exact bindings and required inputs; report its result only when it actually runs. Static blocked handoffs and ordinary editing suggestions are not consumer execution receipts.
