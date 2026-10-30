# Phase 7 — `04_review-architect-polisher` Development Contract

Contract version: `0.1.3`  
Status: final frozen development contract; first implementation boundary limited to Phase 7A  
Installation status: uninstalled  

## Purpose

`04_review-architect-polisher` plans, synthesizes, and revises biomedical Review Articles from an explicitly bounded and source-verified evidence set. It freezes review scope, proposes a theme-based taxonomy, builds a provenance-bearing synthesis matrix, organizes consensus, conflict, limitations, knowledge gaps, and bounded future directions, and may then revise Review prose under an approved plan.

The Skill does not reuse the Original Article story model. It does not treat citation presence as evidence support, infer missing literature from memory, or present model-generated synthesis as a source-authored claim.

## Trigger boundary

This Skill applies when the requested deliverable is a narrative Review, mini-review, scoping-style Review, or an explicitly bounded review-like synthesis. It may plan, restructure, synthesize, or polish such a document.

It must not activate for:

- Original Article story architecture, which belongs to `02_manuscript-story-architect`;
- Original Article language revision, which belongs to `03_article-polisher`;
- a grant background, Discussion section, or literature summary unless the user explicitly asks to treat it as a Review deliverable;
- primary literature retrieval, database search execution, reference-manager mutation, or copyright acquisition;
- a formal systematic review or meta-analysis unless the required external protocol, search, screening, extraction, risk-of-bias, and statistical artifacts are supplied and the requested operation is within separately validated capability;
- Figure rendering, which belongs to `05_scientific-figure-designer`;
- final scientific, citation, or integrity approval, which remains with the author and `06_scientific-integrity-qc`.

## Review-type declaration

Every run declares exactly one `review_type`:

- `narrative_review`;
- `mini_review`;
- `scoping_style_review`;
- `systematic_style_draft`.

`systematic_style_draft` describes organizational style only. It must not be labelled a completed systematic review without a registered or author-supplied protocol, reproducible search records, screening decisions, extraction records, and all method-specific checks required by that protocol.

The declared review type controls required inputs, permitted claims, section expectations, and the wording used to describe methods. Missing method artifacts cause a declared limitation or refusal to make the formal-method claim; they are never reconstructed from prose.

The first Phase 7A implementation may execute `narrative_review` and `mini_review`. `scoping_style_review` and `systematic_style_draft` remain contract-recognized types, but they must fail closed or produce an explicitly `architecture_only_degraded` package unless the required protocol, search, screening, and other method artifacts are supplied through separately defined interfaces and pass validation. A degraded package cannot claim completion of a formal scoping or systematic review and cannot be promoted to `ready_for_qc` as one.

## Scientific and bibliographic authority

The Skill has no independent scientific or bibliographic authority. It may operate only on:

1. source records supplied by the author; or
2. records produced by a separately authorized retrieval workflow and handed off with stable identities and locators.

It must not:

- invent a source, DOI, PMID, author, year, title, journal, quotation, sample size, result, method, or citation locator;
- use model memory as a bibliographic record;
- silently replace an unresolved or retracted source with a different publication;
- promote an abstract-only or bibliographic-only record to full-text evidence;
- infer that a citation supports a sentence merely because it appears near that sentence;
- convert the Skill's synthesis into a claim attributed to one cited source.

Author approval may approve scope, taxonomy, synthesis, or wording, but it does not alter source identity or turn missing evidence into support.

## Required inputs

Minimum architecture input:

1. `document_type: review_article`.
2. Review question or objective.
3. Declared `review_type`, target audience, and intended use.
4. Population/system, disease or biological context, intervention/exposure or method class where applicable.
5. Time window and explicit inclusion/exclusion boundaries, including language or publication-type limits when relevant.
6. Source registry containing stable source IDs and at least one resolvable bibliographic identity per included record.
7. Versioned `review_extraction_record` inputs, or author notes normalized into that interface without changing their origin, that distinguish directly extracted content from later synthesis.
8. Exact authorization state for scope decisions and any requested revision.

Conditional inputs:

- existing Review draft, outline, taxonomy, or extraction table;
- study-quality or applicability assessment, with method and review status;
- author-approved terminology and citation-style map;
- Review-only `style_profile` and `structure_profile` from Module 01;
- target-journal profile whose source and verification date are recorded;
- formal protocol/search/screening artifacts for systematic or scoping claims;
- separately supplied trusted source-evidence inputs for asserted verified access classes;
- a separately supplied `trusted_authority_inputs` collection whenever any reviewed/approved state, author-origin claim, trusted evidence-unit/independence assignment, or field-wide coverage gate depends on `decision_ref`;
- candidate Figure/Table requirements for handoff to Module 05.

Missing conditional inputs create an explicit degraded or unsupported state. They do not authorize inference.

## Article/Review profile separation

This Skill may consume only a Module 01 profile whose `profile_kind` and document strata are Review-specific. An Article-only, mixed Article/Review, or uncertain profile is not an admissible input for Review profile-guided decisions. It must not justify `profile_alignment`, taxonomy, structure, citation-pattern, rhetorical, hedging, or prose-style recommendations. Such profiles may be inspected only for diagnostic comparison during development and must not influence a Review architecture package.

Review profile features may guide section architecture, synthesis density, citation placement patterns, rhetorical moves, hedging, and sentence-level presentation. They may not supply scientific claims, source content, author positions, or bibliographic records.

`02_manuscript-story-architect` plans and Article-specific `03_article-polisher` contracts are not admissible substitutes for Review architecture. Shared identities, locators, authorization vocabulary, and QC interfaces may be reused without importing the Original Article story model.

## Core artifacts

Phase 7 proposes four Review-specific business artifacts. They remain candidates until their schemas and validators are separately approved.

### `review_scope_contract`

Freezes:

- review question and `review_type`;
- intended audience and purpose;
- population/system, disease/context, method or intervention boundaries;
- date window, publication types, languages, and inclusion/exclusion rules;
- permitted source set or source-registry version;
- declared retrieval completeness, source-set coverage basis, and known blind spots;
- `coverage_origin`: `author_supplied`, `authorized_retrieval_workflow`, or `model_proposed`;
- `coverage_review_status`: `pending`, `author_review_required`, `approved`, or `rejected`, plus `coverage_decision_ref` when coverage is used beyond admitted-source-set wording;
- author-supplied objectives with stable `author_objective_id` values when they may ground an author position or future direction;
- authorized scope/taxonomy decision IDs;
- author/caller authorization state and unresolved decisions.

A broad instruction such as “cover the field comprehensively” does not authorize silent scope expansion.

### `review_source_registry`

Contains one record per source with:

- stable `source_id`;
- bibliographic identity fields and available persistent identifiers;
- source version, correction, expression-of-concern, or retraction status when supplied or verified;
- acquisition/verification origin and verification timestamp;
- evidence-access level: `full_text_verified`, `abstract_verified`, `bibliographic_only`, or `unresolved`;
- `access_verification_origin`: `author_supplied_source_evidence`, `authorized_retrieval_or_verification_workflow`, or `model_proposed`;
- `access_verification_status`: `pending`, `author_review_required`, `approved`, or `rejected`;
- `access_verification_ref` resolving to a supplied source-evidence identity or authority decision whenever `full_text_verified` or `abstract_verified` is asserted as trusted;
- document and local citation locators where available;
- inclusion status, exclusion reason, and author/reviewer decision;
- duplicate or linked-publication relationships;
- required stable `evidence_unit_id`, optional broader `study_family_id`, and an independence status: `independent`, `overlapping_population`, `secondary_analysis`, `follow_up`, `duplicate_report`, `linked_publication`, or `unresolved`;
- evidence-unit/study-family `assignment_origin`: `author_supplied`, `authorized_retrieval_or_review_workflow`, or `model_proposed`;
- `independence_review_status`: `pending`, `author_review_required`, `approved`, or `rejected`, plus a resolvable external `decision_ref` whenever a reviewed or trusted independence state is asserted;
- extraction-record IDs.

The registry records verification and publication-family state; it does not claim that the study is valid or that it supports a Review conclusion. A source record is not presumed to be an independent study merely because it has a distinct bibliographic identity. A `model_proposed` evidence-unit or study-family assignment remains reviewable and cannot serve as a hard consensus-independence baseline. If independence is not externally established, use `unresolved` or retain the proposal as `author_review_required`; the model must not split an unresolved family into apparently independent units.

A model-proposed access classification cannot establish or strengthen trusted access. In particular, it cannot promote `unresolved`, `bibliographic_only`, or `abstract_verified` to a class that permits stronger substantive use. The effective access ceiling remains the last externally verified class; without one, the source remains `unresolved` for substantive synthesis.

### `review_synthesis_matrix`

The matrix groups evidence by theme, claim, assumption, method, or controversy rather than by paper order. Each synthesis record includes:

- stable theme and synthesis-claim IDs;
- stable `gap_id`, `limitation_id`, and `conflict_id` values for recorded bases referenced by future directions;
- `claim_origin`: `source_claim`, `cross_source_synthesis`, `author_position`, or `future_direction`;
- origin-conditional source, extraction-record, evidence-unit, study-family, and decision/basis provenance defined below;
- citation and source locators;
- study design, population/model, method, exposure/intervention, comparator, and outcome where applicable;
- direction and type of evidence;
- evidence-access level and quality/applicability status;
- agreement, heterogeneity, conflict, negative evidence, and unresolved status;
- limitations and scope boundaries;
- support status: `supported`, `partially_supported`, `conflicting`, `unsupported`, or `not_assessed`;
- relation provenance, including `relation_origin`, relation review status, and the access-level constraint under which the relation may be used;
- author-review state.

### Claim-origin provenance invariants

Provenance requirements are conditional on `claim_origin`; the validator must not require or fabricate identical source fields for all origins.

- `source_claim` must resolve to exactly one `source_id`, one or more compatible extraction records from that source, and an access level sufficient for the represented proposition. Its scope cannot exceed the extraction boundary.
- `cross_source_synthesis` must resolve to at least two distinct `source_id` values, the underlying extraction/evidence cluster, and explicit evidence-unit identities. Multiple publications from one evidence unit may participate in a cross-publication synthesis, but they must not be described or counted as multiple independent studies.
- `author_position` may have no literature source when explicitly supplied by the author. It must carry author-origin provenance and a resolvable external author decision/reference, and it must not be represented as source-derived. Any separately claimed literature support must independently satisfy the normal extraction and claim–citation relation rules.
- `future_direction` must resolve to at least one recorded `gap_id`, `limitation_id`, `conflict_id`, or `author_objective_id`. A source-derived basis preserves its downstream extraction provenance. An author-supplied objective requires resolvable author-origin provenance but no fabricated source, and the resulting proposal must not be represented as established evidence.

`cross_source_synthesis` remains explicitly distinguishable from every `source_claim`. `future_direction` is a proposal, not an established finding.

### `review_outline`

Contains:

- taxonomy axes and their decision rationale;
- theme-based sections and paragraph plans;
- claims/evidence clusters assigned to each paragraph;
- consensus, controversy, conflict, limitation, and knowledge-gap placement;
- bounded future-direction statements;
- candidate Figure/Table briefs;
- source coverage and unassigned-evidence audit;
- material reorganization decisions and author approvals;
- unresolved author decisions and risks.

The outline plans Review synthesis. It must not contain generated prose presented as verified source content.

## Upstream source-extraction interface

`review_extraction_record` is a versioned validator-facing evidence/provenance interface, not a fifth Review business artifact. Every record must bind:

- interface version and stable `extraction_record_id`;
- exact `source_id`, required `evidence_unit_id`, and optional `study_family_id`;
- extraction type, such as `result`, `method`, `source_claim`, `limitation`, `population`, `comparator`, `outcome`, `statistic`, or `author_note`;
- source access level;
- exact source locator when the permitted use requires one;
- source-span hash or stable representation hash when applicable;
- directly extracted content and/or normalized proposition without concealing which representation is primary;
- `extraction_origin`: `direct_source_extraction`, `author_supplied_source_note`, or `model_assisted_extraction`;
- review status: `pending`, `author_review_required`, `approved`, or `rejected`;
- `review_decision_origin`: `author_supplied`, `authorized_review_workflow`, or `model_proposed`;
- resolvable external `decision_ref` and reviewer identity when `approved` or another reviewed state is asserted.

Every referenced extraction record must resolve to a supplied record whose source identity, evidence-unit identity, access level, locator, and available source hash are compatible with the source registry. Deterministic validation may establish exact identity, hash, locator, enum, and cross-artifact consistency; it does not by itself prove that extracted language is a semantically faithful representation of the source.

`model_assisted_extraction` remains `author_review_required` unless a supplied external decision resolves to an author or separately authorized review workflow. A generated `approved` string, self-declared author identity, model emission, locator existence, or hash agreement alone must not convert it into a verified source claim. `model_proposed` review or assignment decisions cannot mint their own trusted approval. Approval does not repair a missing source, incompatible locator, insufficient access level, or broken identity/hash binding.

Extraction approval, evidence-unit assignment, and independence decisions reuse the shared authorization meanings. A trusted reviewed state must resolve through `decision_ref` to an external decision with an admissible authorization origin; the generator or calling workflow cannot manufacture that authority inside the Review package.

## Upstream authority-decision interface

`review_authority_decision` is a versioned validator-facing authority/provenance interface, not a fifth Review business artifact. It makes `decision_ref` executable without allowing a Review record to approve itself. Every decision record must bind:

- interface version and stable `decision_id`;
- `decision_type`: `extraction_review`, `evidence_unit_assignment`, `independence_resolution`, `author_position_origin`, `author_objective`, `source_access_verification`, `source_set_coverage`, `scope_decision`, `taxonomy_decision`, `synthesis_decision`, `support_relation_review`, or `outline_decision`;
- exact governed `subject_ids`, their subject types, and applicable artifact/file versions and SHA-256 bindings;
- `decision_value`: `approve`, `reject`, `resolve`, or `confirm`, plus the state asserted for the governed subject;
- shared `authorization_origin` and `authorization_state` meanings;
- `decision_producer_role`: `author`, `authorized_review_workflow`, or `authorized_retrieval_or_verification_workflow`;
- creation/review identity and timestamp;
- exact upstream input identities and hashes on which the decision was based, when applicable;
- deterministic decision-record SHA-256 calculated over the defined canonical representation.

Each `decision_ref` must bind the exact `decision_id`, interface version, and decision-record SHA-256. The validator must confirm record existence, hash identity, governed-subject coverage, decision type/value compatibility, upstream binding, and admissible authorization state.

Authority decisions must enter through a `trusted_authority_inputs` collection supplied separately from the model-produced Review package and bound by an external caller-supplied manifest identity/hash. A record embedded only inside a generated Review artifact, or a record that merely claims `author` identity, is not trusted. An embedded decision summary becomes authoritative only when its exact identity and hash resolve to the separately supplied trusted collection.

`author_approved` retains the shared requirement `authorization_origin: author` and `decision_producer_role: author`. An authorized workflow may supply a bounded `caller_accepted` verification or resolution within its declared role, but it cannot mint author approval. The validator checks the supplied trust boundary and deterministic bindings; it does not claim to cryptographically prove a person's real-world identity.

Author-decision material in `review_scope_contract` or `review_outline` must be an embedded reference/summary under that artifact's schema or resolve to `review_authority_decision`. Unresolved queries remain embedded records in the existing scope/outline artifacts. Neither creates an additional Review business artifact or an undefined sixth architecture output.

## Access-level permitted-use rules

| Access level | Maximum permitted use |
| --- | --- |
| `full_text_verified` | May support content explicitly present in the supplied verified full text and bound to an appropriate source locator. The label alone does not establish semantic support. |
| `abstract_verified` | May support only content explicitly present in the supplied verified abstract; it cannot support unobserved full-text detail. |
| `bibliographic_only` | May establish publication identity or existence only; it cannot provide substantive scientific support. |
| `unresolved` | Cannot support substantive extraction, synthesis, consensus, conflict resolution, or future-direction claims. |

The validator must enforce these ceilings and must not infer a stronger access level from prose, citation placement, bibliographic completeness, or model assertion.

`full_text_verified` and `abstract_verified` are trusted only when `access_verification_origin` is non-model, `access_verification_status` is approved, and `access_verification_ref` resolves either to exact author-supplied source evidence in the separately supplied trusted source inputs or to an admissible `review_authority_decision` of type `source_access_verification`. The referenced source/file identity, version, and hash must match the registry record. Authorization confirms provenance and permitted use; it does not prove semantic support for a particular claim.

A `model_proposed` access state remains reviewable and cannot raise the effective access ceiling. The validator must reject a proposed upgrade used to unlock full-text or abstract-level support.

## Taxonomy contract

Taxonomy axes are declared as either `descriptive_axis` or `evaluative_axis`. Descriptive axes may cover modality, method, biological question, mechanism level, population/model, chronology, or another non-ranking organizing principle. Evidence strength, study quality, applicability, validation ranking, translational readiness, and other value-bearing classifications are evaluative axes.

The Skill must:

- define every axis and category;
- keep axes conceptually distinguishable;
- record why a source or evidence cluster belongs to a category;
- allow multi-label assignment when scientific objects span categories;
- identify unclassified or ambiguous records;
- prevent a proposed taxonomy from silently changing the frozen review scope;
- route material taxonomy decisions to author review.

Every `evaluative_axis` must bind to an explicit author-supplied rubric or separately validated assessment method and record the review state of each classification. Without such a rubric, the model may propose the axis but classifications remain `not_assessed` or `author_review_required`; it cannot assign high/moderate/low or equivalent rankings as fact.

The taxonomy is an organizing model, not a claim that the field itself recognizes the same categories.

## Synthesis and evidence rules

### Theme-based synthesis

Default organization is by question, theme, assumption, method, evidence strength, or controversy. Paper-by-paper narration is permitted only when the section purpose is explicitly chronological, historical, or a method/source inventory.

### Consensus

The default permitted statement is agreement or consistency **within the admitted source set**, evaluated using represented evidence units rather than publication count. Linked publications, overlapping populations, follow-ups, secondary analyses, or duplicate reports from one evidence unit must not be counted as multiple independent studies.

A stronger field-wide consensus statement additionally requires a declared source-coverage basis adequate for that wording, resolved or explicitly bounded non-independence, represented scope/heterogeneity/limitations, and explicit author review. The coverage record must have a non-model `coverage_origin`, an approved review state, a resolvable `coverage_decision_ref` of type `source_set_coverage`, and exact bindings to the supporting coverage/search artifacts or author-supplied basis. Approval alone does not establish actual completeness.

`model_proposed` completeness or coverage may support only admitted-source-set wording and cannot satisfy the field-wide consensus gate. Multiple citations, source records, publications, or a self-declared `comprehensive` label never establish consensus. The Skill must not calculate a vote count or evidence grade unless an adopted and validated method defines that calculation.

### Conflict and negative evidence

Conflicting, null, negative, or scope-limited evidence must not be silently omitted to improve narrative flow. The Skill records whether disagreement may relate to population/model, design, measurement, comparator, exposure, analysis, study quality, or an unresolved cause. It may propose explanations only when grounded in supplied records or explicitly labelled as author-review hypotheses.

### Knowledge gaps

Absence from the supplied source set is not automatically a field-wide knowledge gap. Gap records distinguish:

- `evidence_gap`;
- `method_gap`;
- `validation_gap`;
- `population_or_model_gap`;
- `benchmark_gap`;
- `reporting_gap`;
- `unresolved_due_to_scope`.

Each gap records a deterministic `gap_basis_status`: `directly_observed_in_admitted_set`, `method_defined`, `scope_limited`, or `unresolved`. It also records the source-set boundary, supporting source count, independent evidence-unit count, unresolved/degraded state, and review status.

Phase 7A must not assign arbitrary numeric or high/medium/low gap-confidence scores unless a separately validated and declared method defines and calibrates them. Supporting counts and review state describe the observed basis; they do not convert absence in the admitted set into a field-wide claim.

### Future directions

Future directions must be traceable to a recorded gap, limitation, conflict, or author-supplied objective. They remain proposals and must not be written as established mechanisms, guaranteed outcomes, or universal priorities.

## Citation-scope contract

Every substantive source-grounded statement must resolve to one or more source/extraction records. For each claim–citation relation, record:

- claim ID and exact source IDs;
- citation locator or placement target;
- support relation: `direct_support`, `partial_support`, `context_only`, `contradicts`, or `not_assessed`;
- source scope and access limitation;
- whether the sentence is a source claim or cross-source synthesis;
- `relation_origin`: `extraction_backed`, `author_supplied`, or `model_proposed`;
- relation review status: `pending`, `author_review_required`, `approved`, or `rejected`;
- the relation's access constraint and the actual source access level used;
- author-review state for high-risk relations.

A citation may not be broadened beyond the population/model, method, outcome, direction, uncertainty, and conclusion boundary present in its extraction record. Citation movement during revision must preserve the claim relation or create an author-review warning.

`model_proposed` relations remain `author_review_required` and cannot become verified `direct_support` by assertion. A verified support relation must resolve through appropriately reviewed extraction or author-supplied relation evidence with a sufficient access level. Author approval cannot convert citation proximity, a missing extraction, or an access-level violation into support. `cross_source_synthesis` remains a communication construct over multiple extraction records and must never be attributed as the claim of one source.

Verbatim quotations require an exact locator and must remain within applicable copyright and quotation limits. Paraphrase does not remove the requirement for evidence fidelity.

## Architecture and revision phases

### Phase A — scope and source admission

Validate review type, scope, source identity, inclusion/exclusion state, access level, and required protocol artifacts. Stop or degrade before synthesis when the admitted source set cannot support the requested operation.

### Phase B — taxonomy and synthesis

Build candidate taxonomy axes and the synthesis matrix. Record source claims separately from cross-source synthesis, preserve conflict and negative evidence, and expose missing or unassessable relations.

### Phase C — outline and author decisions

Create a theme-based section/paragraph plan, source-coverage audit, candidate Figure/Table briefs, and explicit decision points. Material scope, taxonomy, synthesis, or structural choices remain `author_review_required` until approved.

### Phase D — bounded Review revision

Phase D is contracted but deferred to Phase 7B. It is not part of the first Phase 7A deterministic implementation. A Review-specific revision-permission contract, trusted patch/application interface, change manifest, candidate lineage, and prose-diff validation must be separately designed and reviewed before this phase becomes executable.

Only after the relevant scope, source, synthesis, and outline artifacts are available may the Skill draft or revise prose. Revision intensity may be Light, Medium, or Deep, but scientific and bibliographic protection never weakens:

- Light: grammar, syntax, local clarity, terminology, and citation-preserving transitions;
- Medium: sentence restructuring and local thematic flow within an approved paragraph plan;
- Deep: theme/paragraph reorganization only under exact author-approved outline decisions and artifact closure.

No mode authorizes new sources, new scientific conclusions, hidden source exclusion, unsupported consensus, or citation-scope expansion.

## Authorization boundary

The shared authorization meanings remain:

- `machine_proposed`: proposal only;
- `caller_accepted`: caller permits an otherwise authorized bounded operation; result remains author-review-required;
- `author_approved`: exact author approval of the relevant scope, taxonomy, synthesis, outline, or structural decision.

`author_approved` requires `authorization_origin: author`. A calling workflow cannot mint author approval. Source verification and author approval are separate states.

Material changes requiring explicit author decision include:

- scope expansion or contraction;
- inclusion/exclusion of a disputed or central source;
- primary taxonomy-axis selection when alternatives materially change the narrative;
- classification of a major conclusion as consensus or conflict;
- suppression or relocation of negative/conflicting evidence;
- strong future-direction or translational priority statements;
- Deep section or paragraph reorganization.

## Deterministic versus model responsibilities

Phase 7A deterministic code should handle:

- schema, identifier, version, hash, and exact artifact binding;
- source-registry uniqueness, required bibliographic fields, duplicate IDs, and unresolved identity states;
- claim-origin-conditional provenance and `cross_source_synthesis` source cardinality;
- external decision resolution for reviewed extraction and evidence-unit/independence assignments;
- trusted-authority collection binding and subject/hash validation for every `decision_ref`;
- source-access verification provenance and effective-access ceiling enforcement;
- source-set coverage provenance and field-wide-consensus authority checks;
- inclusion/exclusion consistency with the frozen scope contract;
- source/extraction/citation locator resolution;
- Review/Article profile separation;
- synthesis-matrix coverage, allowed enums, and unassigned-source audit;
- exact author-decision and authorization-state checks;
- package completeness and exact cross-artifact binding through the author-reviewable Review outline.

Later Phase 7B deterministic code, after its interface is separately reviewed, should handle before/after citation tokens, numbers, statistics, units, terms, Figure/Table references, changed-unit inventory, change-manifest completeness, trusted candidate lineage, and exact binding to Module 06 QC inputs and candidate hashes.

The model may:

- propose taxonomy axes and theme assignments;
- cluster admitted source records;
- draft bounded cross-source synthesis;
- identify candidate conflict, limitations, gaps, and future directions;
- propose the Phase 7A Review outline;
- explain uncertainty and request author decisions.

Prose drafting or revision is a later Phase 7B model responsibility and is not executable in Phase 7A.

Model proposals remain reviewable and cannot establish source identity, evidence quality, citation support, or author approval by assertion.

## Degraded and unsupported states

The Skill fails closed or declares degraded output when:

- a source identity or citation locator is unresolved;
- full text is unavailable for a claim requiring full-text detail;
- extraction records are missing or conflict with prose;
- a trusted state depends on an absent, self-embedded, hash-mismatched, or subject-incompatible authority decision;
- a substantive claim requires an access class whose verification provenance is missing, model-proposed, or weaker than asserted;
- study quality or applicability is required but not assessed;
- scope or taxonomy decisions remain unresolved;
- the source set cannot support a requested consensus or field-wide gap statement;
- field-wide wording depends on model-proposed or otherwise untrusted source-set completeness/coverage;
- Article/Review profile kind is mixed or uncertain;
- formal review-method claims lack protocol/search/screening artifacts;
- required author approval or upstream artifact closure is absent.

Degraded output must identify affected claims, sources, sections, and prohibited downstream uses. It must not silently downgrade evidence requirements while retaining strong wording.

## Outputs and handoffs

Architecture-stage outputs:

- `review_scope_contract`;
- `review_source_registry`;
- `review_synthesis_matrix`;
- `review_outline`;
- embedded author-decision references/summaries and unresolved-query records governed by the existing scope/outline schemas.

Revision-stage outputs, only after the later Phase 7B interface is separately designed, reviewed, and authorized:

- revised Review candidate and locator map;
- change manifest;
- citation-support warnings;
- unresolved author queries;
- exact source/candidate and upstream-artifact bindings.

Handoffs:

- optional Review-only profiles from Module 01;
- optional candidate Figure/Table briefs to Module 05;
- every revised candidate and its provenance package to Module 06;
- author final review for scope, synthesis, scientific interpretation, citation support, and publication decisions.

The successful terminal state for Phase 7A is `ready_for_author_review`. It means only that deterministic architecture admission and package completeness checks passed; it does not mean bibliographic correctness, semantic extraction fidelity, scientific truth, evidence sufficiency, or author approval.

`ready_for_qc` is reserved for a later Phase 7B revised candidate with the separately required revision and lineage artifacts. Even then, it means only that deterministic admission completed, not scientific truth or final author approval.

## Frozen Phase 7A minimum implementation surface

```text
04_review-architect-polisher\
├── DEVELOPMENT_CONTRACT.md
└── candidate\
    ├── schemas\
    │   ├── review-scope.schema.json
    │   ├── review-source-registry.schema.json
    │   ├── review-extraction-record.schema.json
    │   ├── review-authority-decision.schema.json
    │   ├── review-synthesis-matrix.schema.json
    │   └── review-outline.schema.json
    ├── scripts\
    │   └── validate_review_package.py
    └── tests\
        ├── fixtures\
        └── test_review_contract.py
```

The extraction-record and authority-decision schemas formalize upstream validator evidence interfaces but do not add Review business artifacts. Phase 7A must stop at an author-reviewable `review_outline` plus a provenance-complete scope/source/extraction/synthesis package. It must not generate or revise Review prose.

The first implementation should reuse the existing shared artifact vocabulary and validator, and reuse Module 06 authorization/identity/locator definitions by reference. It must not create a full `SKILL.md`, model prose generator, Review revision contract, change-manifest or patch/application layer, retrieval engine, reference-manager connector, formal systematic-review engine, or installation package.

## Required negative tests for Phase 7A

At minimum, deterministic tests must reject:

- `document_type: original_article` routed to Module 04;
- Article-only, mixed Article/Review, or uncertain profile used to justify Review `profile_alignment`, taxonomy, structure, or prose-style guidance;
- `scoping_style_review` or `systematic_style_draft` treated as executable formal-review completion without validated method artifacts;
- unresolved or duplicate source identity admitted as verified evidence;
- bibliography-only source used as full-text support;
- abstract-only extraction used for detail absent from the verified abstract;
- unresolved-access source used in substantive synthesis;
- included source outside the frozen scope without an approved decision;
- synthesis relation referring to a missing, incompatible, or insufficient-access extraction record;
- `decision_ref` resolving to a missing decision, mismatched subject/type/state, or incorrect decision-record hash;
- a generated or embedded-only decision record accepted as trusted authority without an exact match in `trusted_authority_inputs`;
- `model_assisted_extraction` or `model_proposed` support relation promoted to verified support merely by model assertion;
- `model_assisted_extraction` marked approved without a resolvable external authorized decision;
- `model_proposed` independence assignment used as verified multiple-independent-study evidence;
- citation relation referring to a missing source/extraction record;
- cross-source synthesis represented as one source's claim;
- one-source record labelled `cross_source_synthesis`;
- `author_position` forced to carry a fabricated source or represented as source-derived without a valid support relation;
- author-objective `future_direction` falsely attributed to a publication or represented as established evidence;
- a model-proposed source-access upgrade used to enable abstract- or full-text substantive support;
- unsupported consensus created from citation count alone;
- linked publications from one evidence unit represented as multiple independent studies;
- field-wide consensus asserted without adequate source-coverage basis, non-independence handling, and explicit author review;
- model-proposed `comprehensive` coverage used to satisfy the field-wide-consensus gate;
- evaluative taxonomy classification asserted without an author-supplied or validated rubric;
- conflict or negative evidence silently unassigned;
- P1 theme/paragraph satisfied by an unrelated P2 claim/evidence cluster;
- calling workflow minting `author_approved`;
- systematic-review wording without the required protocol/search/screening artifacts.

Positive tests must demonstrate a bounded narrative Review package, a legitimate theme-based synthesis with explicit source-claim versus cross-source-synthesis separation, preserved conflict, exact source/evidence-unit coverage, resolvable extraction provenance, externally supplied authority-decision resolution, and a valid `ready_for_author_review` terminal state. Phase 7A positive tests do not require a revised candidate or Module 06 QC handoff.

## Deferred negative tests for Phase 7B

Phase 7B tests are not requirements of the Phase 7A validator. When the Review revision interface is later designed, its tests must include at least:

- Deep reorganization without the exact approved Review outline decision;
- prose revision without an approved Review-specific revision permission;
- a changed citation, number, statistic, unit, term, or Figure/Table reference absent from the Review change manifest;
- a patch applied to a candidate or source hash other than the exact authorized input;
- a revised Review candidate lacking trusted lineage and a resolvable Module 06 handoff.

## Explicitly out of scope for the first implementation

- live literature retrieval or web/database browsing;
- automatic DOI/PMID correction or bibliographic guessing;
- PDF acquisition or copyright circumvention;
- systematic-review registration, search execution, deduplication, screening, PRISMA production, risk-of-bias scoring, meta-analysis, or GRADE automation;
- scientific truth checking or evidence-sufficiency certification;
- automatic journal-rule updates;
- Figure rendering;
- DOCX tracked changes and PDF layout fidelity;
- model-level prose generation and real-Review revision testing;
- Review revision permission, patch/application, change-manifest, and prose-diff implementation;
- full Skill installation or activation.

## Development stop condition

This contract is finally frozen at `0.1.3`. The next permitted development step, when requested, is Phase 7A only: the four Review business schemas, the upstream extraction-record and authority-decision interface schemas, deterministic package validator, and synthetic positive/negative fixtures described above.

Phase 7A must stop at a provenance-complete synthesis package and author-reviewable Review outline. It must not include prose generation, live literature retrieval, a Review revision patch layer, a full `SKILL.md`, installation, or activation. After Phase 7A passes deterministic review, perform model-level Review architecture/synthesis testing before designing the separate Phase 7B revision interface.
