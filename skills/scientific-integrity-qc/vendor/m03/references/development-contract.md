# Article Polisher — Development Contract Candidate

## Candidate status

- Development phase: `6 — Module 03 contract`
- Target Skill: `03_article-polisher`
- Contract version: `0.1.2` (final structural-footprint enforcement amendment)
- Contract review state: **frozen for minimum implementation**
- Scope: Original Research Article language polishing and explicitly authorized local restructuring
- Minimum candidate implementation version: `0.1.0`
- Minimum schemas, scripts, fixtures, and tests implemented: **yes**
- Full `SKILL.md` implemented: **no**
- Installed or activated: **no**
- Real manuscript or model-level test performed: **no**
- HPC, network, or external service used: **no**

This frozen contract and its minimum implementation remain in `result` for review. The contract defines the permission and artifact boundaries; implementation evidence is recorded separately and does not expand them.

## Purpose

Improve the clarity, precision, flow, and corpus-compatible scientific prose of an author-owned Original Article while preserving its scientific content and approved architecture.

The polisher may improve how an existing proposition is expressed. It must not invent data, methods, citations, mechanisms, novelty, limitations, controls, interpretations, or conclusions; silently change claim strength or evidence relationships; or treat stylistic fluency as evidence of scientific correctness.

Review Articles are outside this Skill and must route to future `04_review-architect-polisher`.

## Required operating boundary

The polisher is a transformation module, not the sole judge of its own output.

```text
identified author source
→ explicit revision contract
→ bounded section/experiment-aware revision
→ change manifest and unresolved queries
→ independent 06 scientific-integrity-qc comparison
→ author review where required
```

A generated draft, schema-valid artifact, caller-accepted alignment, or clean automated check cannot create author approval.

## Permission and approval authority

The Phase 5 `revision_contract` is an externally supplied, authoritative permission artifact. Article Polisher may consume it, but must never create, widen, reinterpret, replace, or self-approve its own transformation permissions. It may reject or decline an incomplete or insufficient contract; it may not enlarge one to accommodate a preferred edit.

The authoritative contract must bind:

- `revision_contract_id`, `revision_contract_version`, and `contract_sha256`;
- exact source document/artifact identity, version, and SHA-256 hash;
- authorized document/unit scope;
- allowed and prohibited operations;
- frozen anchors and approved structural-change IDs;
- `authorization_origin` and `authorization_state`.

Permitted authorization origins are `author` and `calling_workflow`. `article_polisher` is never an admissible authorization origin. The shared Phase 5 `revisionContract` definition must be versioned to carry these fields before Module 03 implementation references it; Module 03 must not create a divergent copy.

Authorization states have distinct meanings:

- `machine_proposed`: a proposed operation only; it does not authorize execution;
- `caller_accepted`: the caller permits execution of an otherwise authorized Light/Medium operation, while the result remains `author_review_required`;
- `author_approved`: the author has explicitly approved the relevant decision or final revision.

Caller acceptance is not scientific approval, claim approval, or final-manuscript approval. Deep structural operations additionally require exact structural-change IDs from a Phase 4 plan whose relevant decisions are author-approved (`author_approval: approved` in the Phase 4 schema). No generated candidate, caller acceptance, schema validation, or QC result may promote an authorization state or create author approval.

As a deterministic cross-field invariant, `authorization_state: author_approved` requires `authorization_origin: author`. A `calling_workflow` origin may create or carry `caller_accepted` execution permission only; the combination `calling_workflow` + `author_approved` is invalid.

## Required inputs

1. Exact source manuscript or section identity, stable version, and SHA-256 hash.
2. Document type fixed as `original_article`.
3. An externally authorized `revision_contract` with the exact identity, source binding, authorized scope, operations, anchors, structural-change IDs, origin, and state defined above.
4. Section identity and paragraph-function descriptor for every editable unit. The descriptor records `label`, `origin`, and `review_status`; permitted origins are `author_supplied`, `phase4_plan`, and `model_assisted_classification`.
5. Terminology map when protected spelling, abbreviation, or case rules are required.
6. Experiment labels for Results/Methods units when experiment-aware guidance is requested.
7. Optional `author_approved` Phase 4 manuscript plan, claim–evidence map, and interpretation cards.
8. Optional reviewed Article style/structure profile from Module 01.
9. Optional current journal profile supplied or separately verified for the actual submission target.

Missing optional inputs create a declared degraded mode. They do not authorize the model to infer the missing information.

A model-assisted paragraph-function classification may guide communication choices only. It cannot create scientific permission, authorize reordering, or serve as a hard structural baseline. Only an appropriately author-approved upstream role or plan may do so.

## Revision modes

### `light`

Allowed by default:

- grammar, punctuation, syntax correction, and lexical tightening;
- removal of redundancy that does not remove a scientific qualifier;
- local transition improvement;
- clarity edits within an existing sentence or adjacent sentence pair.

Prohibited:

- sentence or paragraph reordering;
- sentence merging that changes scope attachment;
- paragraph-function, claim-order, or evidence-order changes;
- any scientific-anchor change.

### `medium`

May additionally allow, only when declared:

- sentence split or merge;
- information reordering inside one paragraph;
- explicit topic-sentence repair that restates an existing source-located paragraph proposition or approved claim while preserving paragraph function;
- local paragraph transition repair.

It does not authorize paragraph movement, section movement, claim/evidence reassignment, or new interpretation.

If no suitable source-located proposition or approved claim exists, topic-sentence repair is not permitted; the system creates an author query instead of inferring a paragraph claim from the data.

In Results or Discussion, intra-paragraph reordering must not cross claim/evidence, observation/interpretation, qualifier/scope, or conflict boundaries. Such reordering requires an approved upstream baseline that identifies the involved propositions and relations. Without that baseline, the operation is unsupported for the affected unit and must be restricted or routed to author review rather than inferred from prose.

### `deep`

Requires an exact `author_approved` Phase 4 manuscript plan and explicit approved structural-change IDs. It may allow specified paragraph split, merge, or movement within the approved scope.

Deep increases structural movement permission, not scientific-content permission. Scientific claim/evidence protection is identical across Light, Medium, and Deep. Deep mode still does not authorize:

- changing claim scope, causal/mechanistic ceiling, evidence identity, or evidence relation;
- suppressing conflict, negative results, limitations, or unresolved evidence;
- changing section function without an exact approved plan decision;
- treating a broad instruction such as “make the story stronger” as approval for scientific changes.

For each executed Deep structural-change ID, the package must include the closure of Phase 4 artifacts actually referenced by that approved decision. A referenced claim/evidence assignment requires its claim–evidence map records; a referenced interpretation or boundary requires its interpretation card; a plan-only position change need not import unrelated cards. Missing referenced provenance makes that structural operation inadmissible rather than degraded.

## Section-aware contract

Every editable unit retains its source section and its paragraph-function label, origin, and review status. A model-assisted label remains advisory and cannot authorize a scientific or structural transformation.

### Title and Abstract

- Preserve population/model, intervention/exposure, primary result, direction, uncertainty, and scope.
- Do not create novelty, clinical relevance, mechanism, or generalization absent from approved source artifacts.
- Abstract compression must not erase important boundaries or convert secondary findings into primary findings.

### Introduction

- Improve background-to-gap-to-question flow without creating a literature claim or unsupported gap.
- Preserve citation scope and distinguish established knowledge from the study objective or hypothesis.
- Do not rewrite motivation as proof of novelty.

### Methods

- Prioritize exact reproducibility language, identities, units, timing, controls, replicate definitions, software/database versions, and statistical procedures already present.
- Do not fill missing parameters from convention or another paper.
- Ambiguous or missing reporting information becomes an author query, not generated prose.

### Results

- Keep observation separate from interpretation.
- Preserve comparison groups, direction, magnitude, uncertainty, statistics, sample/replicate units, Figure/Table references, and evidence order unless an approved plan authorizes a move.
- Do not convert association to causality, prediction to mechanism, or absence of evidence to evidence of absence.

### Discussion and Conclusion

- Preserve claim ceiling, hedging, model/population boundary, limitations, conflicts, and relationship to prior work.
- Do not add mechanism, novelty, translational relevance, clinical recommendation, or future direction not supplied or approved.
- Stylistic strengthening must never strengthen the scientific claim.

### Figure legends and supplementary text

- Preserve panel identity, experimental object, treatment/comparison, statistical notation, `n` definition, units, and abbreviation definitions.
- Do not infer methods or sample definitions from the Figure image alone.

## Experiment-aware routing

Experiment profiles constrain reporting checks and prose choices; they do not supply missing science. Units may carry multiple labels.

The first implementation should limit executable routing to the four profiles already established in Phase 4:

- `computational`: cohort/split identity, leakage boundary, validation, software/database/version, prediction ceiling;
- `cell`: cell/model identity, perturbation, controls, biological versus technical replicate, in-vitro boundary;
- `molecular`: target/reagent identity, normalization, assay/control context, loading/reference controls, assay ceiling;
- `animal`: species/strain/sex/age when supplied, dose/route/schedule, randomization/blinding when supplied, experimental unit, in-vivo boundary.

Omics, imaging, clinical/human, and structural/biophysical profiles remain future extensions unless separately contracted and tested.

## Profile-guided style boundary

An Article style profile may guide measurable communication features such as sentence-length range, clause density, voice distribution, hedging distribution, transition placement, citation placement, Figure-reference syntax, and section-specific rhetorical moves.

It must not contribute:

- paper-specific phrases or recognizable n-grams;
- scientific propositions, mechanisms, conclusions, novelty, topic priorities, or author worldview;
- an instruction to imitate an individual author;
- unsupported rules from low-coverage or unstable profile features.

Absent or weak profile evidence falls back to clear biomedical academic prose; it does not block preservation checks.

When a change uses `profile_alignment` as its rationale, the manifest must reference the reviewed Module 01 `profile_id`, profile version/hash, the specific reusable `feature_id`, and a bounded feature-support reference. The support reference points to the reviewed aggregate evidence rather than copying corpus statistics into the manifest. A profile feature is communication evidence only: it is not scientific authority and cannot justify copying paper-specific language.

## Protected scientific content

At minimum, revisions preserve:

- numbers, signs, ranges, exponents, ratios, percentages, P values, uncertainty, statistics, units, sample sizes, and replicate counts;
- gene/protein/drug/chemical/cell-line/model/method/software/dataset identities and declared case;
- citations and Figure/Table/equation/section/appendix references;
- comparison direction, negation scope, causality, mechanism level, hedging, boundary, and generalization scope;
- claim/evidence IDs and relations, paragraph function, frozen elements, and approval states when supplied;
- placeholders and unresolved author queries.

Formatting equivalence may be normalized conservatively. Unit conversion and scientific equivalence are not inferred automatically.

## Planned artifact interfaces

### Reused, not duplicated

- Phase 5 `revision_contract` is the authoritative transformation-permission interface.
- Phase 4 manuscript plan, claim–evidence map, and interpretation cards remain authoritative upstream artifacts.
- Phase 5 comparison manifest, preservation snapshots, findings, and QC report remain authoritative downstream QC artifacts.

The polisher must not maintain divergent copies of these schemas.

### `change_manifest`

The manifest records every actual source-to-candidate text change, not only changes the model elects to declare. Its records must collectively cover the deterministic changed-unit/span inventory, and every declared record must correspond to a real source/candidate difference. The inventory is validator evidence, not a third business artifact.

Each record includes:

- stable change ID and source/candidate locators;
- source/candidate unit IDs and representation hashes;
- section, paragraph-function label/origin/review status, experiment labels, and revision mode;
- operation type plus revision-contract ID, version/hash, authorization origin, and authorization state;
- affected protected-anchor IDs;
- rationale classified as clarity, grammar, flow, profile alignment, or approved structure;
- risk class and author-review requirement;
- relationship to approved structural-change or plan IDs when applicable.

For `profile_alignment`, the record additionally references the exact profile identity/version/hash, reusable feature ID, and feature-support reference described above.

The package validator deterministically rejects, at minimum:

- an actual changed unit/span absent from `change_manifest`;
- a manifest record without a corresponding source/candidate difference;
- an operation type not authorized by the exact `revision_contract`;
- a changed unit outside the contract's authorized scope.

General semantic diffing is not required in the minimum implementation. Recoverable unit/span-level difference coverage is required.

### `author_query_list`

Records unresolved ambiguity, missing reporting detail, conflicting source material, or changes that require scientific/author judgment. Each record includes a stable query ID, `query_class`, affected unit IDs and locators, `blocks_revision`, and resolution status. It must preserve the exact local source locator and must not contain a fabricated answer.

`blocks_revision: true` prevents safe revision of the affected unit until an author response is recorded; unrelated authorized units may continue. A non-blocking query may accompany a candidate but remains explicitly unresolved and author-reviewable.

### Revised manuscript and locator map

The revised text must be versioned and paired with recoverable source/candidate unit alignments. A clean rendering never replaces the identified source file.

## Deterministic versus model responsibilities

Deterministic code should handle:

- identities, hashes, schema checks, locator continuity, operation allowlists, and source/candidate changed-unit/span inventory;
- complete two-way coverage between actual differences and `change_manifest` records;
- exact revision-contract identity, source binding, authorization origin/state, scope, and operation admission;
- protected-token extraction suitable for the established Phase 5 ruleset;
- source/candidate package completeness;
- dispatch to independent QC and verification that its report matches the exact candidate hash.

### Observable structural footprint

Operation admission must not rely solely on the model-declared `operation_type`. The deterministic inventory derives observable source/candidate structural effects where applicable, including:

- paragraph count and order changes;
- sentence count and order changes;
- section-membership changes;
- unit split, merge, and move effects.

These observations are validator evidence inside the difference inventory, not a new business artifact. Mode invariants are enforced independently of the declared label:

- **Light:** no observed sentence reorder, paragraph reorder, paragraph/unit split or merge, paragraph/unit move, or section-membership change.
- **Medium:** declared sentence split/merge and sentence/information reordering may occur inside the same paragraph, subject to the existing Results/Discussion baseline rules; paragraph move, section move, unauthorized paragraph split/merge, and section-membership change remain invalid.
- **Deep:** an observed paragraph split, merge, or move must map to the exact author-approved Phase 4 structural-change ID that permits that effect and scope.

A model-declared `grammar`, `clarity`, or other allowed Light operation cannot mask a deterministically observed structural transformation. The observed footprint governs admission when it conflicts with the declared label.

The language model may:

- diagnose clarity, flow, redundancy, and rhetorical problems;
- propose bounded revisions within the explicit contract;
- explain why a change improves communication;
- identify uncertainty and generate author questions.

The model must not decide scientific truth, evidence sufficiency, missing experimental details, or author approval.

## Gate and failure semantics

- No candidate may be represented as safe before independent Phase 5 QC runs against the exact source and candidate hashes.
- `pass_with_warnings` requires human review and is not a clean pass.
- `fail` and `unassessable` stop automatic delivery as a clean revision.
- Unsupported document format, section, experiment profile, operation, or structural transformation must be declared rather than silently handled.
- An unmanifested actual change, a declared change without an actual difference, an unauthorized operation, or an out-of-scope changed unit fails package admission before scientific-integrity QC.
- A model-assisted paragraph-function label cannot satisfy a required approved structural baseline.
- A blocking unresolved author query prevents revision of its affected unit.
- More specifically, an unresolved `blocks_revision: true` query plus an actual changed affected unit in the deterministic inventory fails the package; unrelated authorized units may still proceed.
- The polisher must not enter an automatic rewrite–QC loop. A failed candidate returns findings to the author or calling workflow.

## Proposed minimum implementation surface after contract review

```text
candidate\
├── schemas\
│   ├── change-manifest.schema.json
│   └── author-query-list.schema.json
├── references\
│   ├── revision-modes.md
│   ├── article-section-guides\
│   ├── experiment-profiles\
│   └── target-profile-usage.md
├── scripts\
│   ├── build_change_inventory.py
│   └── validate_revision_package.py
└── tests\
    └── synthetic fixtures and contract-negative cases
```

The first implementation should reuse Phase 4 and Phase 5 schemas by reference. The shared Phase 5 revision-contract definition must receive the narrow versioned identity/authority extension described above rather than being copied into Module 03. The implementation should not duplicate upstream validators, create a full `SKILL.md`, or attempt model-level prose generation before the artifact boundary passes review.

## Explicitly out of scope

- Review Article writing or synthesis;
- literature retrieval, citation supplementation, or reference-manager mutation;
- new scientific reasoning, interpretation, conclusion, novelty, or experiment design;
- Figure/image generation or image-integrity analysis;
- automatic unit conversion, statistical recalculation, or truth checking;
- DOCX tracked changes or PDF layout fidelity in the first implementation;
- automatic correction after QC failure;
- full Skill installation or activation;
- real-manuscript/model-level testing before a separate approval.

## Frozen review decisions

1. Light, Medium, and Deep differ in language/structural movement permission; scientific-content protection never weakens by mode.
2. Caller acceptance may permit an otherwise authorized Light/Medium execution but never implies scientific, claim, author, or final-manuscript approval.
3. Deep structural execution requires exact author-approved Phase 4 structural decisions.
4. Deterministic difference inventory, manifest completeness, authorization, and scope admission precede independent QC.
5. Paragraph-function provenance is explicit; model-assisted classification is advisory only.
6. Medium Results/Discussion reordering and topic-sentence repair follow the approved-baseline and source-proposition constraints above.
7. Profile-guided changes are feature-traceable and cannot supply scientific authority or paper-specific language.
8. `change_manifest` and `author_query_list` remain the only two new business artifacts; query blocking is represented inside `author_query_list`.

## Stop condition

Contract version `0.1.2` is frozen. Proceed only with the minimum schemas, deterministic structural/change inventory, package validator, synthetic fixtures, and negative tests. Do not continue contract expansion unless that implementation exposes a concrete inconsistency. A full `SKILL.md`, model prose generation, real manuscripts, DOCX/PDF tracked changes, installation, and activation remain separately deferred.
