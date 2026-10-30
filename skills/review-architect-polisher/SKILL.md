---
name: review-architect-polisher
description: Architect, synthesize, or revise a biomedical narrative Review or mini-review from an explicitly bounded source set, preserving exact provenance, Review-only style-profile routing, author authority, and deterministic revision evidence. Do not use for Original Articles, live literature retrieval, unsupported formal systematic-review claims, or final scientific approval.
metadata:
  short-description: Build and revise auditable biomedical Reviews
---

# Review Architect and Polisher

Build a source-bounded Review architecture or revise an existing structured Review without inventing literature, scientific content, citations, or author approval. Treat fluent prose and deterministic validation as reviewable artifacts—not proof of scientific truth or citation support.

## Route the request

- For an initial architecture diagnosis from the author's Review draft and supplied source notes, give a nonvalidated reverse outline, organization questions and provisional evidence needs. Attribute a scientific comparison only when the supplied source material supports it; mark unverified relations for source review. Do not label this a Phase 7A artifact or validator result.
- Use the formal architecture path for source admission, extraction closure, theme-based synthesis, conflict/gap preservation, and a validated author-reviewable outline. It requires the exact scope, source registry, extraction records and any applicable separately supplied authority inputs defined in [architecture-workflow.md](references/architecture-workflow.md).
- For ordinary wording advice, use the author's supplied Review text and sufficient immediate context. Read the writing guides below, preserve sentence/paragraph order and citation attachment for a same-sentence request, and keep all supplied propositions. Keep an uncertain sentence unchanged with a focused question; flag structural or evidence issues separately.
- Return clean suggested prose when requested; for an editing review, give the original, candidate and a brief reason. These consultation outputs remain outside the Phase 7B producer route. Do not create approval, lineage or producer-state artifacts or claim QC execution for them; never overwrite the source.
- Use the deterministic revision path only when a structured Review source, frozen Phase 7A package, and external revision permission are supplied. Read [revision-workflow.md](references/revision-workflow.md). Ordinary advice does not bypass this admission gate.
- For paragraph synthesis, argument flow, limitation presentation, or same-sentence professionalization, read [synthesis-and-expression-guidance.md](references/synthesis-and-expression-guidance.md). Choose the requested writing task before proposing changes; writing guidance does not expand runtime permission.
- For a same-sentence wording task, also read [sentence-preserving-expression.md](references/sentence-preserving-expression.md). A separately supplied project expression note can suggest Review wording only within its stated corpus and provenance; it is not a Module 01 profile or scientific evidence.
- Execute `narrative_review` and `mini_review`. Treat `scoping_style_review` and `systematic_style_draft` as degraded architecture-only requests unless separately validated method artifacts authorize more.
- Reject Original Articles and route them to the Article-specific architect or polisher.

## Formal artifact admission boundary

Require exact identities, versions, hashes, and locators for every source and trusted authority input. Never use model memory as a bibliographic record, infer an absent paper, upgrade an access class, or treat citation proximity as support.

Review-only Module 01 style or structure profiles are optional. Admit them only when their exact identity is supplied and their corpus is Review-specific. Use supported aggregate features to guide presentation; never reproduce source phrasing or derive scientific claims from the profile. Article-only, mixed, uncertain, or stale profiles cannot guide Review work.

Use only features actually present with support in the admitted profile. Deterministic marker rates and reference positions do not establish rhetorical purpose, synthesis quality, or grammatical voice percentages. Keep model-assisted writing judgments distinguishable from measured profile features.

## Architecture path

Produce and validate the frozen Phase 7A artifact family:

- `review_scope_contract`;
- `review_source_registry`;
- `review_extraction_record` inputs;
- separately supplied `review_authority_decision` inputs;
- `review_synthesis_matrix`;
- `review_outline`.

Run `scripts/validate_review_package.py`. A valid terminal state is `ready_for_author_review`; it does not authorize prose revision or claim completeness, semantic fidelity, scientific truth, or evidence sufficiency.

## Revision path

Freeze the structured source, exact Phase 7A closure, external `review_revision_permission`, caller-held expected permission SHA-256, revision mode, operations, and unresolved questions. The permission payload omits only its top-level self-hash when recomputed. Reject a changed payload, forged embedded hash, caller-held hash mismatch, self-produced authority, or incompatible decision tuple.

Create only a `machine_proposed` locator-bound `review_revision_proposal`. Then apply it with `scripts/apply_review_revision_proposal.py`; the deterministic layer creates the candidate, lineage, structured citation/protected-change inventory, author-query list, contract-complete change manifest, application receipt, and package-validation result. Validate those outputs with `scripts/validate_review_revision_package.py`.

Light permits local wording changes. Medium permits bounded within-paragraph sentence restructuring. Deep permits only the exact structural/draft operations authorized by matching author-approved permission decisions: paragraph split/merge/move, section move, theme reorganization, or one exact authorized draft-slot materialization. Section split/merge remain unsupported.

## Scientific authority boundary

- Preserve source-claim versus cross-source-synthesis identity, evidence-unit dependence, access ceilings, conflicts, negative evidence, limitations, gaps, certainty, causal level, numbers, statistics, units, terminology, and Figure/Table references.
- Ordinary existing-prose revision cannot add, delete, substitute, or reattach citation identities. Normalize supported numeric-range and superscript representations before identity comparison, but explicitly inventory identity-preserving citation surface changes as `formatting_only`. Fail closed when citation-like author-year syntax cannot be resolved safely. Detect citation placement against uniquely aligned lexical insertion boundaries rather than raw character offsets, retain distinct start/end identities for non-empty replace gaps, and fail closed when the citation lies inside an unresolved replace/insert/delete gap. Inventory resolved placement or syntactic-role changes separately as `placement_changed`. Light rejects them, while Medium permits only an exact identity-preserving move within the same paragraph and the same approved claim/relation. The only materialization exception is an exact authorized empty draft slot with an exact permission allowlist and Phase 7A closure.
- Do not hide blocking queries or fabricate missing reporting details. Return a query and block only its affected operation.
- `ready_for_independent_qc` means the producer package is internally valid. Module 06 Review admission is a separate execution with its own exact producer bindings and required inputs. Report its result only when it actually runs; static handoff records are not execution receipts. Never infer scientific correctness, author approval, or publication readiness from producer validation.
- Never overwrite the source or start an automatic rewrite–QC loop.

## Deterministic commands

Run from this Skill directory with Python 3:

```text
python scripts/validate_review_package.py --help
python scripts/apply_review_revision_proposal.py --source-document <source.json> --permission <permission.json> --expected-permission-sha256 <sha256> --proposal <proposal.json> --phase7a-package <phase7a.json> --output-dir <new-output-dir>
python scripts/validate_review_revision_package.py --help
```

The validators and schemas are package-local, inventory-pinned trust roots; runtime overrides are rejected and tampered local bytes fail closed. Missing or mismatched inputs fail closed. Outputs remain `author_review_required`. Installation and release state are recorded separately from scientific approval.

Current engineering status (2026-10-04): Batch A and B guidance is user-accepted and content-frozen for this workstream. Subsequent common-workflow entrypoint changes are a separate review candidate; Article-specific optimization is deferred. Existing inventories describe the prior packaged baseline. Complete the planned release refresh before treating this working tree as an installable or inventory-valid package.

