# Phase 7B — Review Drafting and Revision Interface Contract

## Candidate status

- Contract version: `0.1.2`
- Derived from: rejected contract `0.1.1`, with only the reviewed permission-hash canonicalization and authorized-decision compatibility defects corrected
- State: `CANDIDATE / REVIEW REQUIRED / NOT FROZEN`
- Parent development contract: Phase 7 contract `0.1.3` (`FINAL PASS / FROZEN`)
- Governing packaging contract: Phase 9 contract `0.1.1` (`FINAL PASS / FROZEN`)
- Admitted architecture implementation: Phase 7A.1 candidate `0.1.1` (`FINAL PASS / FROZEN`)
- Installation or activation: prohibited
- Implementation state: not started; this contract is not an executable prose-revision implementation

This is the separate Phase 7B interface required by Phase 7 contract `0.1.3` and Phase 9 Item 4. It adds no authority to the frozen Phase 7A architecture layer and changes none of its schemas, validator, fixtures, or tests. It defines the exact boundary that a later Module 04 package must implement before Review drafting or revision can execute.

## 1. Purpose and route

Phase 7B may propose and deterministically apply bounded prose changes to an author-owned biomedical Review Article. It supports two source states:

1. revision of existing Review prose; and
2. drafting into an exact, pre-existing `authorized_empty_draft_slot` whose paragraph purpose, synthesis claims, citations, and source closure are fixed by the admitted Phase 7A outline and revision permission.

It accepts only `document_type: review_article`. Original Articles route to Modules 02/03. A grant background, Discussion section, or literature summary is not admitted unless the caller explicitly identifies the deliverable as a Review Article and supplies the complete Review artifacts required here.

Executable review types in the first Phase 7B implementation are `narrative_review` and `mini_review`. `scoping_style_review` and `systematic_style_draft` remain `architecture_only_degraded` unless separately validated protocol, search, screening, extraction, and method interfaces exist. Phase 7B must not turn them into completed formal reviews.

## 2. Non-authority boundary

Phase 7B has no independent scientific, bibliographic, retrieval, or author authority. It must not:

- invent or retrieve sources, identifiers, quotations, citation locators, methods, results, sample sizes, statistics, conclusions, or study-quality judgments;
- infer citation support from proximity or from a citation token alone;
- broaden a source claim beyond its admitted extraction record;
- collapse cross-source synthesis into a claim attributed to one publication;
- hide conflict, negative evidence, scope limitations, or unresolved access;
- convert a model proposal, caller acceptance, schema pass, hash match, or QC result into author approval;
- certify scientific truth, evidence sufficiency, bibliographic correctness, systematic-review completion, or submission readiness.

The model may propose wording. Deterministic code may establish identity, scope, operation, patch, inventory, and lineage facts. Only separately supplied trusted decisions may provide author or authorized-workflow approval, and author review remains required for every candidate.

## 3. Frozen upstream closure

Every admitted run must bind the exact current Review source and the exact Phase 7A closure used to plan or justify the change:

- `review_scope_contract`;
- `review_source_registry`;
- `review_synthesis_matrix`;
- `review_outline`;
- every affected `review_extraction_record`;
- every applicable `review_authority_decision` from a separately supplied, caller-hash-bound `trusted_authority_inputs` collection;
- any Review-only `style_profile` or `structure_profile` actually used;
- the exact source Review artifact and normalized unit/locator inventory.

Each reference binds artifact or interface type, stable ID, version, SHA-256, document/manuscript identity, and local package-relative path where applicable. The source, scope, registry, synthesis, and outline must share the same Review identity. An artifact is not trusted merely because it is present in the package or declares `approved` at its top level.

For each affected claim, citation relation, conflict, gap, author position, or future direction, the proposal must include the relevant closure actually used. Unrelated Phase 7A artifacts need not be duplicated, but omitted affected closure fails admission. If an approved outline decision refers to a non-primary or non-key theme, claim, paragraph, or source relation, that reference remains part of the closure; importance labels do not limit provenance. Frozen `review_authority_decision` records remain responsible only for the Phase 7A subject types their schema can express. They are not used to authorize Phase 7B paragraph, section, source-unit, or draft-slot operations.

## 4. Exact interfaces and artifact classes

The machine-readable companion registry is authoritative for interface names and versions.

### Admission interface

`module04_review_revision_admission` version `0.1.0` consumes:

- exact source Review identity and normalized source-unit inventory;
- exact frozen Phase 7A closure listed above;
- one external `review_revision_permission` version `0.1.0`;
- one model-produced `review_revision_proposal` version `0.1.0`;
- optional Review-only profile identities when profile alignment is proposed.

### Output interface

`phase7b_revision_bundle` version `0.1.0` contains:

- exact source and candidate Review identities and SHA-256 values;
- `review_change_manifest` version `0.1.0`;
- `review_author_query_list` version `0.1.0`;
- deterministic `review_revision_lineage_map` version `0.1.0`;
- deterministic `review_protected_change_inventory` version `0.1.0`;
- exact upstream closure references used by actual changes;
- patch/application receipt and package validation result;
- terminal producer state and explicit author-review requirement.

The proposal, permission, inventory, lineage, and receipts are validator/workflow evidence. The revised prose and change/query records remain author-owned Review outputs. None becomes a source of scientific authority merely by being packaged.

## 5. `review_revision_permission`

The permission is an externally supplied trust root and the sole carrier of Phase 7B structural/drafting authority. Module 04 may consume it but must not create, widen, replace, reinterpret, or self-approve it. It binds:

- `permission_id`, interface version, canonical `permission_sha256`, creator/origin, and authorization state;
- a separate caller-held `expected_permission_sha256` supplied at admission and equal to the recomputed canonical permission hash;
- exact source Review ID, version, SHA-256, and document type;
- exact scope, registry, synthesis, and outline IDs, versions, and SHA-256 values;
- authorized source unit IDs and any exact `authorized_empty_draft_slot` IDs;
- revision mode and allowed/prohibited operation types;
- frozen claim, citation-relation, conflict, limitation, gap, author-position, future-direction, terminology, numeric/statistic/unit, and Figure/Table anchor IDs;
- an `authorized_decisions` collection carrying every approved structural or drafting decision and its exact governed subject;
- comparison/QC scope and required author-review state.

### Canonical permission hash

Phase 7B uses the same canonical JSON algorithm already frozen by Module 03. The hash payload is the complete top-level `review_revision_permission` JSON object with only its top-level `permission_sha256` member omitted; a nested member with that spelling, if any schema later permits one, is not implicitly removed. The exact algorithm is:

```python
permission_payload = {
    key: value
    for key, value in review_revision_permission.items()
    if key != "permission_sha256"
}
canonical_permission_bytes = json.dumps(
    permission_payload,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
).encode("utf-8")
permission_payload_sha256 = hashlib.sha256(canonical_permission_bytes).hexdigest()
```

Thus all JSON object keys are sorted lexicographically, arrays preserve their declared order, insignificant whitespace is absent, Unicode characters are serialized without ASCII escaping and then encoded as UTF-8, and the digest is lowercase hexadecimal. The following equality must hold at admission:

```text
review_revision_permission.permission_sha256
= permission_payload_sha256
= caller-held expected_permission_sha256
```

The caller-held value is external admission input and is not inserted into the permission artifact merely for hashing. Any change to permission content other than replacing the omitted top-level self-hash field changes the recomputed payload hash. Changed content, a forged `permission_sha256`, or a mismatched caller-held `expected_permission_sha256` must fail closed.

Each `authorized_decisions` record must bind all of:

- `decision_id`;
- `decision_type`: `review_structural_revision` or `review_draft_slot_materialization`;
- `governed_subject_type`: `paragraph_plan`, `section_plan`, `source_unit`, or `authorized_empty_draft_slot`;
- exact `governed_subject_id`, `governed_subject_version`, and canonical `governed_subject_sha256`;
- one exact `allowed_operation` from the Deep operation vocabulary;
- exact affected source unit, paragraph, section, outline, and draft-slot IDs as applicable;
- exact Phase 7A claim/relation/extraction/source closure IDs used by the operation;
- `authorization_origin: author`, `authorization_state: author_approved`, and author-review provenance.

The three authority fields are not independent enums. Their compatibility is exactly:

<!-- phase7b-authorized-decision-compatibility:start -->
- `review_draft_slot_materialization` requires `governed_subject_type: authorized_empty_draft_slot` and `allowed_operation: draft_authorized_unit`.
- `review_structural_revision` requires `governed_subject_type` to be one of `paragraph_plan`, `section_plan`, or `source_unit`, and requires `allowed_operation` to be one of `paragraph_split`, `paragraph_merge`, `paragraph_move`, `section_move`, or `theme_reorganization`.
<!-- phase7b-authorized-decision-compatibility:end -->

Every other `decision_type × governed_subject_type × allowed_operation` combination is invalid and fails closed. In particular, a draft-slot materialization decision cannot authorize a structural operation, and a structural-revision decision cannot govern an `authorized_empty_draft_slot` or authorize `draft_authorized_unit`. This first contract does not further specialize which of the three structural governed-subject types is primary for each structural operation; exact affected IDs, governed-subject identity/hash, and Phase 7A closure remain mandatory.

For a `paragraph_plan` or `section_plan`, the governed-subject version is the exact frozen outline schema version and the governed-subject hash is recomputed from that exact nested object. For a `source_unit`, the version is the exact source artifact version and the hash is the normalized unit representation hash. For an `authorized_empty_draft_slot`, the subject binds the source artifact/version, slot ID, exact placeholder token, placeholder representation hash, and mapped outline paragraph. A whole-outline approval cannot substitute for any of these more specific bindings.

Allowed top-level permission authorization states are `machine_proposed`, `caller_accepted`, and `author_approved`, with the shared meanings already frozen by Modules 03/06. `machine_proposed` never authorizes application. `caller_accepted` may authorize otherwise valid Light/Medium prose operations but cannot approve scientific meaning or a material source/citation/outline decision. Every Deep or drafting `authorized_decisions` record requires author origin and author-approved state. Module 04 and its calling workflow cannot mint that state.

Deep reorganization and every `draft_authorized_unit` operation require an exact matching record inside the externally supplied, caller-hash-bound `review_revision_permission.authorized_decisions`. Phase 7A `review_authority_decision` must not be treated as capable of authorizing Phase 7B structural or drafting operations, and no new Phase 7A subject type is implied. A broad request such as “make the review comprehensive” or “write the missing section” is not sufficient.

## 6. Proposal and patch contract

`review_revision_proposal` is always `machine_proposed`. Each operation binds:

- operation ID and declared type;
- exact target source unit IDs and typed source locators;
- expected source text or placeholder token and its representation SHA-256;
- replacement text;
- revision permission ID/version/hash;
- revision mode;
- affected Phase 7A claim, citation-relation, conflict, limitation, gap, author-position, future-direction, and source/extraction IDs;
- affected protected-anchor IDs;
- exact Phase 7B permission `authorized_decisions` IDs when required;
- rationale, risk class, and author-review requirement;
- optional Review-profile feature identity and support locator when profile alignment is claimed.

The patch layer applies only admitted, non-overlapping, exact-source-bound operations. A missing unit, stale hash, locator mismatch, overlapping operation, duplicate target, operation-order ambiguity, or candidate identity mismatch fails closed. The model cannot supply trusted candidate lineage; the deterministic patch layer creates candidate bytes, hashes, locators, change inventory, and lineage after application.

`draft_authorized_unit` may replace only an exact placeholder such as `[[AUTHORIZED_DRAFT_SLOT:<unit_id>]]` already present in the identified source. It cannot insert a new unplanned section or paragraph. Its outline paragraph ID, synthesis-claim cluster, citation relations, extraction closure, and matching `review_draft_slot_materialization` permission decision must all be exact and supplied. Generated prose remains `author_review_required`; deterministic provenance closure does not prove semantic faithfulness.

The permission decision for a draft slot must contain an exact materialization allowlist. Each allowed entry binds a stable materialization ID, protected class, exact candidate token/identity/value, and the Phase 7A source, citation-relation, synthesis-claim, and extraction IDs that permit it. It separately lists any required materialization IDs. The candidate's materialized set must be a subset of the allowlist and must contain every required entry. Anything outside that set fails closed.

## 7. Revision modes and observable footprint

Declared labels do not control admission by themselves. The deterministic difference inventory records sentence/paragraph count, order, split/merge/move, section membership, source/candidate locators, and protected-token deltas. The observed footprint governs when it conflicts with the declared operation.

### Light

May perform grammar, punctuation, syntax, clarity, lexical tightening, non-substantive redundancy removal, and local transition repair inside one existing unit. It may not reorder sentences or paragraphs, change citation attachment, populate an empty draft slot, or alter any scientific/bibliographic anchor identity or value.

### Medium

May additionally split/merge/reorder sentences and repair local thematic flow within one approved paragraph. Citation placement may move only within the same paragraph when the exact unchanged citation identity remains attached to the same approved claim/relation and the move is explicitly inventoried. It may not move paragraphs/sections, suppress evidence, populate an empty draft slot, change source attribution, or modify a material outline decision.

### Deep

The executable Deep operation vocabulary is exactly:

<!-- phase7b-deep-operations:start -->
- `paragraph_split`
- `paragraph_merge`
- `paragraph_move`
- `section_move`
- `theme_reorganization`
- `draft_authorized_unit`
<!-- phase7b-deep-operations:end -->

Every observed structural effect must map to the exact matching permission decision and affected Phase 7A closure. `section_split` and `section_merge` are not supported by interface `0.1.0` and fail closed. Deep expands structural permission, not scientific or bibliographic authority.

No mode authorizes new sources, new unsupported claims, citation identity substitution, numeric/statistical value changes, unit conversion, hidden terminology-identity changes, conflict suppression, stronger consensus, causal strengthening, or unapproved changes to claim scope or evidence relations.

## 8. Protected-change inventory

The deterministic `review_protected_change_inventory` must enumerate, for both source and candidate, every changed occurrence in these classes:

```text
citation
numeric
statistic
unit
terminology
figure_table_reference
negation
comparison_direction
causal_mechanistic
certainty_hedging
consensus_conflict
```

- citation identity, token, group, order, locator, and claim/relation attachment;
- numeric tokens and values;
- statistical tokens, values, operators, intervals, and test labels;
- units and unit-bearing quantities;
- protected terminology, abbreviations, gene/protein/drug/disease/method names, and concept identity;
- Figure, Extended Data, Supplementary Figure, Table, and Supplementary Table references;
- negation, comparison direction, causal/mechanistic markers, certainty/hedging, and consensus/conflict markers.

Every actual protected delta must resolve to exactly one change record; every declared protected delta must exist in the source/candidate comparison. Formatting-only changes must preserve identity/value and be labelled as such. In ordinary existing-prose revision, numeric/statistical value changes, unit conversion, citation identity addition/deletion/substitution, source-attribution changes, or stronger claim/consensus/causal status are not Phase 7B prose operations and fail admission. They must be resolved by the author in a new source/upstream artifact before a fresh revision run.

The only citation-addition exception is `authorized_draft_slot_materialization` produced by `draft_authorized_unit`. Candidate citation identities in that slot must be pre-authorized exact citation/source/relation identities in the permission decision's materialization allowlist and must resolve through the supplied Phase 7A synthesis/extraction/source closure. The inventory records the source state as an authorized empty slot and the candidate state as `authorized_draft_slot_materialization`; it must not mislabel this as ordinary citation addition. An unlisted citation, a citation from a different source/relation, or a citation inserted anywhere outside the exact slot fails admission.

The same narrow materialization rule may copy an exact pre-authorized terminology, numeric, statistic, or unit token into the slot only when its identity/value and upstream extraction locator are frozen in the allowlist. It does not authorize conversion, recalculation, correction, or value change. Outside an authorized draft slot, the ordinary protected-change prohibitions remain unchanged.

Terminology surface-form changes are allowed only when an exact externally supplied terminology map binds the old/new form to the same concept identity and the permission explicitly allows the operation. Citation relocation never establishes support and always remains author-reviewable.

## 9. `review_change_manifest`, queries, and lineage

The change manifest records every actual change, not only changes selected by the model. Each record binds source/candidate unit IDs, typed locators, representation hashes, mode, operation, permission identity, authorization state, affected protected deltas, Phase 7A provenance closure, structural/drafting decision IDs, rationale, risk, and `author_review_required`.

It also contains citation-support warnings for any changed sentence or citation placement. A warning binds the exact citation token/source ID, synthesis relation, extraction record, source/candidate locator, access ceiling, and reason for review. A warning is not evidence that the citation supports the revised sentence.

The author-query list records unresolved ambiguity, missing extraction, insufficient access, conflicting source material, source-scope uncertainty, citation-support uncertainty, or scientific/author judgment. An unresolved `blocks_revision: true` query prevents application to its affected units; unrelated authorized units may continue.

The deterministic lineage map provides complete source-unit to candidate-unit relations, including unchanged, replaced, split, merged, moved, and drafted-slot relations. Every candidate unit must resolve to one or more source units or one exact authorized draft slot. Orphan candidate prose fails admission.

## 10. Phase 7A authority preservation

Revision may rephrase an admitted proposition but must preserve the Phase 7A distinctions among:

- `source_claim`;
- `cross_source_synthesis`;
- `author_position`;
- `future_direction`.

It must also preserve evidence-unit non-independence, access ceilings, source-set coverage limits, conflict/negative evidence, limitations, and gap basis. Author approval of wording does not repair an unresolved source identity, missing extraction, insufficient access, or invalid support relation.

The two authority channels are disjoint:

```text
Phase 7A scientific/source/synthesis/outline authority
→ trusted_authority_inputs + frozen review_authority_decision

Phase 7B paragraph/section/source-unit/draft-slot authority
→ exact external review_revision_permission.authorized_decisions
  + caller-held expected_permission_sha256
```

For Phase 7A prose provenance, the exact separately supplied `trusted_authority_inputs` record must match decision ID, interface version, canonical hash, governed subject ID/type/version/hash, decision type/value, authorization origin/state, producer role, and manuscript identity. Embedded summaries and top-level `approved` strings cannot substitute. Phase 7B structural/drafting authority is not resolved through `review_authority_decision`; it must satisfy the exact permission-decision rules in Section 5.

## 11. Profile use

Only Review-specific Module 01 profiles may guide structure or style. Article-only, mixed, uncertain, or stale profiles are rejected. Profile-guided changes must reference the exact profile identity/version/hash, reusable feature ID, and support locator. Profiles may guide presentation but cannot supply claims, sources, citations, author positions, or authority. The Skill must not imitate an individual paper or reproduce source phrasing.

## 12. Terminal states and Module 06 handoff

Phase 7B producer states are:

- `blocked`: admission, patch, closure, or unresolved-query failure prevents a valid candidate;
- `author_review_required`: a candidate exists but is not eligible for independent QC because required package evidence is incomplete;
- `ready_for_independent_qc`: deterministic Phase 7B admission, patch, manifest, inventory, and lineage checks passed for the exact candidate, while author review remains required.

`ready_for_independent_qc` does not mean scientifically correct, citation-supported, author-approved, or publication-ready. It only makes the exact `phase7b_revision_bundle` eligible for the future `module06_review_revision_admission` interface.

Until the separate Module 06 integration contract and consumer interface are frozen, `H04-REVISION-TO-06` remains `blocked` at system integration even when the producer bundle is locally `ready_for_independent_qc`. Module 04 must not fake a consumer admission result or generic QC pass.

After Module 06 runs, its report cannot create author approval. Delivery remains `author_review_required`, and QC blockers prevent clean promotion.

## 13. Minimum deterministic implementation required after freeze

Only after independent review freezes this contract may Item 4 implement:

```text
04_review-architect-polisher/
├── phase7b-core-candidate-0.1.0/
│   ├── schemas/
│   │   ├── review-revision-permission.schema.json
│   │   ├── review-revision-proposal.schema.json
│   │   ├── review-change-manifest.schema.json
│   │   ├── review-author-query-list.schema.json
│   │   ├── review-revision-lineage-map.schema.json
│   │   └── review-protected-change-inventory.schema.json
│   ├── scripts/
│   │   ├── build_review_change_inventory.py
│   │   └── validate_review_revision_package.py
│   └── tests/
├── phase7b-patch-candidate-0.1.0/
│   ├── scripts/apply_review_revision_proposal.py
│   └── tests/
└── package-candidate-0.1.0/
    └── review-architect-polisher/
```

The final package composes frozen Phase 7A.1, the reviewed Phase 7B core/patch layer, a concise `SKILL.md`, routed references, only used schemas/scripts, vendored shared-core resources, tests, and package inventory. It must not edit the frozen Phase 7A tree in place.

## 14. Required implementation tests

The first implementation must include positive Light, Medium, Deep, and authorized-draft-slot cases plus deterministic negative controls for at least:

1. Original Article or ambiguous route;
2. formal/scoping Review promoted without method artifacts;
3. missing, self-produced, stale, or widened revision permission; changed permission content after hashing; a forged embedded `permission_sha256`; or a caller-held `expected_permission_sha256` that differs from the recomputed canonical payload hash;
4. `calling_workflow + author_approved` or internally pending authority;
5. mismatched source/scope/registry/synthesis/outline/manuscript identity;
6. omitted affected extraction or Phase 7A authority closure, including non-key outline references;
7. patch target text/hash/locator mismatch, overlap, duplicate target, or operation-order ambiguity;
8. actual diff absent from the manifest or declared change absent from the diff;
9. unmanifested citation, number, statistic, unit, terminology, Figure/Table, negation, direction, causal, hedge, consensus, or conflict delta;
10. ordinary citation addition/deletion/substitution or relocation to a different claim relation;
11. a new source ID, fabricated locator, or citation not present in the frozen registry;
12. source claim converted to cross-source synthesis or cross-source synthesis attributed to one source;
13. hidden conflict/negative evidence, access-ceiling expansion, or stronger field-wide consensus;
14. Light/Medium/Deep observable footprint outside the authorized mode;
15. Deep restructuring without an exact matching permission `authorized_decisions` record, governed-subject hash, and closure, or with an incompatible `decision_type × governed_subject_type × allowed_operation` combination;
16. draft insertion outside an exact authorized placeholder, without a matching permission decision, or without approved synthesis/citation closure;
17. draft-slot citation/terminology/numeric/statistic/unit materialization absent from the exact allowlist, missing a required materialization, or presented as ordinary citation addition;
18. any `section_split` or `section_merge`, and any mismatch between the textual Deep operation list and the machine registry;
19. unresolved blocking query with an actual change to its affected unit;
20. orphan candidate unit or incomplete lineage;
21. stale/tampered candidate identity or a Module 06 handoff claiming executable consumer admission before its contract freezes;
22. Article/mixed/uncertain profile used for Review profile alignment.

Tests must validate observable artifacts and behavior, not exact explanatory prose.

## 15. Explicitly out of scope

- live literature/database/web retrieval or reference-manager mutation;
- DOI/PMID correction or bibliographic guessing;
- PDF acquisition or copyright circumvention;
- protocol registration, search execution, deduplication, screening, PRISMA, risk-of-bias, meta-analysis, GRADE, or formal systematic-review completion;
- scientific truth or evidence-sufficiency certification;
- automatic numeric/statistical correction, unit conversion, or evidence reanalysis;
- Figure rendering or arbitrary code execution;
- DOCX tracked changes or PDF layout fidelity in the first implementation;
- automatic rewrite–QC loops;
- installation or activation;
- changes to frozen Items 1–3, Phase 7A, or Module 06 minimum core.

## 16. Review and stop condition

Contract `0.1.2` is a review candidate derived from rejected `0.1.1`. It must not be labelled frozen or used to justify implementation until an independent exact-source review confirms that its interface names, artifacts, permission/authority semantics, revision modes, protected-change inventory, Phase 7A closure, terminal states, and H04 boundary are internally consistent.

If accepted, record `FINAL PASS / FROZEN` without modifying these bytes, then begin the separately versioned Phase 7B implementation and Module 04 package. If a concrete contradiction is found, preserve `0.1.2` and derive a narrow successor; do not edit this candidate in place.
