# Phase 8 — `05_scientific-figure-designer` Development Contract

Contract version: `0.1.1`  
Status: final frozen development contract; Phase 8A not yet implemented  
First implementation boundary: Phase 8A deterministic artifact package and validator only  
Installation status: uninstalled  

## Purpose

`05_scientific-figure-designer` converts an author-bounded scientific claim/evidence plan and real source-data description into a traceable Figure story. It designs Figure Cards, Figure Contracts, source-data manifests, backend-independent Plot Recipes, panel order, visual encodings, statistical-annotation requirements, and integrity/QC records.

The Skill may propose how supplied evidence should be displayed. It has no authority to create evidence, alter data, choose a scientifically favorable subset, invent statistical results, or declare its own prototype submission-ready.

The minimum operating chain is:

```text
approved or reviewable upstream claim/evidence or Review-figure brief
+ exact real-data/source identities
→ source-data manifest
→ panel-level Figure Cards
→ figure-level Figure Contract
→ backend-independent Plot Recipe
→ deterministic Figure QC package
→ author review / optional later rendering / Module 06 integrity review
```

## Trigger and routing boundary

This Skill applies when the requested deliverable is one or more scientific figures, panel plans, Figure stories, data-visualization recipes, figure legends as structured content requirements, or a traceable prototype plan for an Original Article or Review Article.

It must not activate as the primary Skill for:

- Original Article claim/evidence architecture, which belongs to `02_manuscript-story-architect`;
- prose polishing, which belongs to `03_article-polisher` or the later prose layer of `04_review-architect-polisher`;
- Review taxonomy or synthesis, which belongs to `04_review-architect-polisher`;
- final scientific, statistical, image-integrity, citation, or submission approval, which remains with the author and an appropriately expanded `06_scientific-integrity-qc`;
- literature retrieval, data acquisition, image generation, statistical analysis, or experimental interpretation not separately authorized;
- copying or cosmetically recreating a published figure;
- a table-only brief. A Module 04 brief with `output_type: table` remains an unresolved table-design handoff and must not be silently converted into a figure.

An illustrative biological schematic is admissible only as an explicitly labelled `conceptual_schematic`. It must remain distinguishable from a data-bearing panel and must not imply observations absent from supplied evidence.

## Phase boundary

This contract separates three stages:

### Phase 8 — contract

Defines identities, artifacts, scientific boundaries, validation duties, maturity states, and required tests. It creates no schemas, executable validator, plot, or full `SKILL.md`.

### Phase 8A — deterministic minimum implementation

May create only:

- the five candidate business schemas defined by this contract;
- shared schema definitions required by those five artifacts;
- validator-facing `trusted_source_inputs`, `analysis_output_record`, `figure_authority_decision`, and non-circular design-package manifest interfaces defined by this contract;
- a deterministic package validator;
- fixture factories, positive fixtures, negative fixtures, and tests;
- concise implementation/review/test records.

Phase 8A does not generate plotting code or render a figure. It validates declared structure, identity, provenance, and cross-artifact closure; it does not determine scientific truth, semantic support, statistical validity, or visual quality.

### Phase 8B — optional prototype execution

May be designed only after this contract and Phase 8A are reviewed. It may translate a validated Plot Recipe into selected R or Python code and an explicitly non-final prototype. Backend execution, statistical computation, and rendered-image inspection are separate capabilities and must not be smuggled into Phase 8A.

No phase may use `schema_valid`, `validator_passed`, or a successful render as a synonym for `scientifically_valid`, `author_approved`, `journal_compliant`, or `final`.

## Scientific, data, and decision authority

The Skill has no independent scientific, statistical, data-curation, bibliographic, or author-approval authority. It may use only:

1. author-supplied or externally authorized upstream claim/evidence artifacts;
2. author-supplied source data or data produced by a separately authorized workflow;
3. author-supplied statistical results or outputs from a separately authorized analysis workflow;
4. externally supplied decisions whose exact subject, version, and hash bindings are resolvable;
5. reference figures used only for source-grounded functional abstraction under the copyright boundary below.

It must not invent, infer as fact, repair, silently normalize, or change:

- observations, values, sample sizes, units, groups, controls, exclusions, missingness, labels, or file identities;
- the biological, technical, observational, feature, or experimental unit;
- pairing, repeated-measure, nesting, batch, time-course, or independence structure;
- statistical tests, adjustment methods, effect sizes, uncertainty values, or significance annotations;
- causal, mechanistic, translational, clinical, or generalization strength;
- a “representative” image selection decision;
- an author decision, author approval, journal rule, or backend verification state.

Author approval may accept a design decision, but it cannot repair missing source data, a broken hash, an unsupported claim/evidence relation, an impossible variable mapping, or an undeclared transformation.

## Required inputs

Every run requires:

1. `document_type`: `original_article` or `review_article`.
2. Exact upstream artifact identity, version, and SHA-256 binding.
3. A bounded Figure request with intended use and target output count.
4. Stable claim and evidence identities admissible for the declared document type.
5. A real-data/source inventory or an explicit declaration that the run is architecture-only.
6. Experiment labels for every data-bearing panel or an explicit `unresolved` label.
7. Authorization state for any frozen scientific or layout decision.

For `original_article`, the preferred upstream source is the Module 02 `figure_sequence` together with the referenced claim–evidence records and interpretation boundaries. A Figure-sequence item is a plan, not proof that the underlying data exist or support the claim.

For `review_article`, the preferred upstream source is a Module 04 `candidate_figure_table_brief` whose `output_type` is `figure`, together with referenced Review claims, themes, synthesis records, and source identities. A Review Figure brief is not source data and cannot authorize a data plot by itself.

Conditional inputs include:

- data dictionary, table schema, variable types, units, and exact source locators;
- raw and processed image identities and processing history;
- author-supplied summary statistics or authorized analysis outputs;
- existing Figure files and their provenance;
- reference-figure functional analyses;
- current target-journal profile;
- project-level terminology and color contracts;
- selected optional plotting backend and verified capability profile;
- externally supplied author or workflow decision records.

Missing conditional inputs must produce an explicit degraded or blocked state. They do not permit model completion from memory.

Any source file, supplied statistic, or trusted decision used above must cross the applicable validator-facing trust interface below. A path, hash, inspection state, statistical value, or approval string emitted only inside the model-produced Figure package is a claim to validate, not trusted evidence that validates itself.

## Accepted upstream identity closure

Every upstream reference must bind the exact artifact ID, artifact version, SHA-256 hash, object type, and local object ID. Name-only or ID-only references are insufficient when the referenced object can change independently.

The admissible chain is:

```text
upstream claim/evidence/theme/source
→ source-data record
→ Figure Card panel
→ Figure Contract panel sequence
→ Plot Recipe layer
→ optional rendered output
→ Figure QC finding/report
```

The package validator must reject a missing reference, version mismatch, hash mismatch, wrong object type, duplicate stable ID, cyclic identity binding, or a child that silently changes the scientific identity of its parent.

An artifact cannot mint trusted approval for itself. Any `author_approved` or equivalent trusted state must resolve to a separately supplied authority decision or upstream artifact whose producer role, authorization origin/state, governed subject, version, and hash are admissible. `calling_workflow` may authorize bounded execution or record `caller_accepted`; it cannot mint author approval.

## Validator-facing trust interfaces

The following interfaces make the data, analysis, and authority boundaries executable. They are supplied separately from the model-produced five-artifact Figure package and are not additional Figure business artifacts. Phase 8A may define schemas and resolver support for them without changing the five-artifact architecture.

### `trusted_source_inputs`

`trusted_source_inputs` is a caller-supplied collection that binds each claimed `source_data_id` to an actual scoped input or a separately authorized resolver reference. The collection carries its own stable collection ID, version, canonical SHA-256 hash, and one or more entries containing:

- stable trusted-input ID and the exact `source_data_id` it is permitted to support;
- input class, supplied path or resolver reference, format, and expected identity when available;
- caller-supplied scope and access mode;
- expected file size and SHA-256 when those are part of the supplied identity;
- externally supplied dataset/sheet/table/layer/assay/image locators where applicable;
- resolver or adapter identity/version when content is not a directly readable local file.

The validator must not trust a model-produced path, hash, locator, variable list, or inspection label merely because it is schema-valid. When an input is locally or otherwise resolvably available, it must:

1. resolve the exact trusted entry authorized for the `source_data_id`;
2. check existence and recompute file size and SHA-256;
3. compare the recomputed identity with both the trusted entry and `source_data_manifest`;
4. use an explicitly supported reader/adapter to inspect the requested dataset, sheet, table, header, variable, channel, or other supported content identity;
5. record the performed verification level and any failure without upgrading unperformed checks.

Validator-produced verification dimensions remain separate:

- `existence_verification`: `verified`, `failed`, or `not_performed`;
- `hash_verification`: `verified`, `failed`, or `not_performed`;
- `content_inspection`: `inspected`, `failed`, or `not_performed`;
- `content_scope`: the exact sheet/table/dataset/header/variable/channel identities actually inspected;
- `inspection_adapter`: reader name and version when content was inspected.

For an unsupported binary format, existence and hash may be verified while content inspection remains `not_performed`. A manifest declaration cannot promote that state. A remotely resolvable input may use an authorized adapter, but an inaccessible URI or narrative assurance is not equivalent to direct inspection.

### `analysis_output_record`

`analysis_output_record` is a versioned validator-facing representation of a supplied statistic or derived analysis output. It is not a sixth Figure business artifact. Each record binds:

- stable `analysis_output_id`, version, canonical record SHA-256, and result status;
- exact source-data IDs, source-data versions/hashes, trusted-input IDs, and input-data hashes;
- `analysis_origin`: `author_supplied`, `authorized_analysis_workflow`, or `model_proposed`;
- analysis workflow/software identity and version when applicable;
- comparison IDs, contrast definition, and group IDs;
- observation, experimental, and inference-unit context;
- `n` by group and the exact `n` definition;
- statistic or estimate type and value when supplied;
- center and spread/interval definitions when supplied;
- test/model name and model specification when supplied;
- paired, repeated, nested, clustered, batch, or longitudinal state where applicable;
- sidedness and multiplicity-correction method when supplied;
- p-value, adjusted p-value, effect size, interval, and other annotation values when supplied;
- review status, authorization state, and exact `decision_ref` when a trusted reviewed state is asserted.

Author-supplied or workflow-produced records used as statistical authority must enter through a separately supplied `trusted_analysis_outputs` collection whose collection identity/hash is bound by the design-package manifest. The validator checks record identity, hash, source-input closure, unit/contrast compatibility, and authorization provenance; it does not decide whether the analysis method is scientifically appropriate.

A `model_proposed` record may express only that an analysis is required, with result status `required_but_unavailable` or equivalent. It cannot supply a trusted estimate, p-value, adjusted p-value, interval, effect size, significance symbol, or completed-test state. Every Figure Card and Plot Recipe statistical annotation must resolve to an admissible supplied record or remain explicitly `required_but_unavailable`.

### `figure_authority_decision`

`figure_authority_decision` reuses the established shared authorization meanings and Phase 7A trust pattern; it must not create incompatible approval semantics. It is a validator-facing decision interface, not a Figure business artifact. Every decision record binds:

- stable decision ID, version, decision type, and canonical decision-record SHA-256;
- governed subject type and stable subject ID;
- exact governed subject version and non-circular governed-content SHA-256;
- decision value such as `approve`, `reject`, `confirm`, or `resolve`;
- authorization origin and authorization state;
- producer role and reviewer/author identity as supplied by the trusted caller;
- exact upstream artifact/input identities and hashes on which the decision was based;
- creation/review timestamp and any bounded conditions.

Figure decision types include, at minimum, `representative_image_selection`, `material_evidence_omission`, `panel_freeze`, `figure_conclusion_freeze`, `layout_decision`, `design_acceptance`, and `finality_decision`.

Trusted decision records must enter through a separately supplied `trusted_authority_inputs` collection with an external collection ID/version/hash. A generated record, an embedded approval summary, or a self-declared author role is not trusted unless its exact record identity and hash resolve to that collection. `calling_workflow` may produce only the bounded execution state permitted by the shared model; it cannot mint `author_approved` or an author-only finality/selection/omission decision.

The governed-content hash must use a schema-defined canonical representation that excludes self-hash fields and the external decision reference/decision-derived state that would otherwise create a cycle. The decision record hash likewise excludes its own hash field. The external decision is not allowed to rewrite the governed scientific content it approves.

## Core business artifacts

Phase 8 defines exactly five business artifacts. Shared definitions, trusted source-input collections, analysis-output records/collections, authority-decision inputs, design-package manifests, backend/profile inputs, and upstream reference records are validator-facing interfaces, not additional Figure business artifacts.

### 1. `source_data_manifest`

The manifest records the real scientific material available to the Figure package. Each source-data record must include, where applicable:

- stable `source_data_id`, version, source class, and origin;
- exact file or external dataset identity, format, size, SHA-256 hash, and locator;
- dataset/table/sheet/layer/assay/image/region locator;
- raw, processed, normalized, summary, derived, or external-reference status;
- variable/column/channel identities, types, units, allowed values, and missingness status;
- entity identifiers and row/observation identities;
- observation unit, feature unit, experimental unit, and inference unit;
- biological and technical replicate hierarchy;
- pairing, repeated measures, nested structure, batch, time point, and longitudinal subject identity;
- groups, controls, comparators, conditions, and declared contrasts;
- exclusions, filters, missing values, transformations, normalization, aggregation, and their author/workflow provenance;
- analysis-output identity when a statistic or derived value is supplied;
- processing history and unresolved provenance gaps;
- inspection level and verification status.

The manifest must distinguish:

- file existence from file-content inspection;
- hash identity from scientific validity;
- raw data from processed or derived data;
- a supplied transformation from a model-proposed transformation;
- an image file from its quantified source table;
- a bibliographic/source record from primary data.

Large source data remain external. The artifact stores identities, locators, metadata, and bounded inspection results, not copied datasets.

For tabular sources, content-level verification requires a supported reader and records the exact header/dataset version inspected. For unsupported binary formats, the validator may verify existence, size, and hash only and must declare content inspection `not_performed`; it must not pretend that columns, channels, or statistical units were verified.

The manifest describes source material; it does not certify its own source. Any trusted existence, hash, or content-inspection state must be produced by the validator from `trusted_source_inputs` and must identify the exact trusted entry and inspection scope. A model-produced manifest may declare an expected identity or unresolved inventory, but its declaration cannot serve as verification evidence.

### 2. `figure_card`

One Figure Card represents one target panel, not a whole paper and not a reusable copy of a published panel. Every card must carry the following fields or an explicit maturity-permitted unresolved/not-assessed state for them:

- stable `figure_id` and `panel_id`;
- panel kind and data-bearing status;
- scientific question and bounded panel role;
- upstream claim IDs, evidence IDs, theme/synthesis IDs where applicable;
- relation type for each claim/evidence binding;
- source-data IDs and exact data locators;
- experiment labels and profile versions when available;
- observation, feature, experimental, and inference units;
- biological/technical replicate definitions and `n` definition;
- group, control, comparator, contrast, time, batch, and pairing structure;
- intended visual encoding and proposed plot archetype;
- supplied or required statistical summary/annotation status;
- uncertainty, limitations, negative/conflicting evidence, and unresolved fields;
- origin and review status for every model-proposed scientific or design abstraction;
- author decision references for frozen panel content or representative-image choice;
- copyright/reuse state when a reference figure informed the abstraction.

Each extracted or abstracted field uses an origin state appropriate to its source, including `observed`, `author_supplied`, `workflow_supplied`, `model_proposed`, or `missing`. A model proposal is not silently relabelled as observed. `missing` remains missing until resolved by an external input.

Panel kinds recognized by the base contract include:

- `quantitative_plot`;
- `image_or_micrograph`;
- `gel_or_blot`;
- `spatial_or_map`;
- `sequence_or_structure_view`;
- `conceptual_schematic`;
- `workflow_or_study_design`;
- `mixed_panel`.

The later implementation may refine panel subtypes without weakening their provenance, unit, or integrity requirements.

### 3. `figure_contract`

One Figure Contract defines one target Figure and freezes the relationship among its panels. It includes:

- stable contract, figure, and version identities;
- document type and intended manuscript/review location;
- one-sentence Figure conclusion or question with origin and review state;
- upstream Figure-sequence item or Review-brief identity;
- ordered panel IDs and permitted layout relationships;
- role of each panel in the evidence hierarchy;
- claim, evidence, source-data, and interpretation-boundary coverage;
- controls, negative/null/conflicting evidence, limitations, and unresolved findings that must remain visible;
- shared axes, ordering, scales, annotations, terminology, and palette semantics;
- planned legend content requirements;
- accessibility and grayscale/distinguishability requirements;
- requested output formats and intended use;
- design decisions requiring author review;
- contract maturity and finality state.

The one-sentence conclusion may copy or bound an admissible author/upstream claim. A model may propose a formulation for review, but it may not raise the claim ceiling, convert association to causation, suppress conflicting evidence, or create a new mechanism. Phase 8A may enforce a ceiling only when the upstream artifact exposes comparable structured strength, causality, mechanism, or generalization fields; natural-language strength comparison remains model/human review.

Every data-bearing panel must serve an explicit admissible relation. Decorative redundancy is reviewable; evidence-free strengthening is prohibited. A negative, null, or conflicting panel may not be omitted merely because it weakens visual narrative. Omission requires a bounded author decision and cannot erase the underlying record.

### 4. `plot_recipe`

The Plot Recipe is backend-independent first. It defines a reproducible display transformation without embedding invented values. Each layer or panel recipe must include:

- stable recipe, figure, panel, and version IDs;
- exact source-data records and variables;
- declared filters, exclusions, transformations, normalization, aggregation, and ordering;
- mappings for x, y, color, fill, shape, size, alpha, labels, facets, and panel position;
- mark/geometry and statistical-summary intent;
- raw-observation display policy;
- uncertainty representation and its supplied source;
- statistical annotation source, comparison identity, correction method, and unresolved requirements;
- axis scale, limits, breaks, units, and transformation provenance;
- palette-semantic keys and accessibility requirements;
- image-channel, scale-bar, crop, contrast, pseudocolor, stitching, and overlay instructions where applicable;
- legend, caption-content, and export intent;
- optional backend route and backend-profile version;
- implementation and verification status.

A Plot Recipe may propose a visual grammar or identify an analysis requirement. It may not invent the numerical result of a summary/test, select a test to manufacture significance, or silently execute an undeclared transformation. If a needed statistic is unavailable, the recipe records `required_but_unavailable` or blocks rendering rather than filling the field.

Backend choice is an implementation detail, not scientific authority. The package must never silently switch backend when a requested backend is unavailable or substitute a visually similar module whose required data shape or statistical assumptions do not match.

### 5. `figure_qc`

The Figure QC artifact records deterministic checks, unresolved scientific review items, and later visual/integrity checks without conflating them. It includes:

- exact validated design-package manifest identity and `design_package_hash`;
- exact component and trusted-interface identities/hashes evaluated by that manifest;
- a separately calculated `figure_qc_sha256`;
- validator, ruleset, profile, and backend versions;
- check level and whether a render was actually inspected;
- findings with stable IDs, severity, rule ID, artifact/field locator, evidence, and remediation route;
- pass/fail/not-assessed status by domain;
- unresolved author, statistics, image-integrity, copyright, accessibility, journal-profile, and backend questions;
- readiness gate and the reasons for it;
- handoff targets, including Module 06 when supported.

A clean deterministic Figure QC report means only that implemented deterministic rules passed on the supplied representations. It cannot certify scientific support, statistical correctness, visual effectiveness, accessibility by human inspection, image integrity, copyright clearance, or journal compliance.

## Non-circular design-package and Figure-QC hashing

Phase 8A must use the following lifecycle:

```text
source_data_manifest + Figure Cards + Figure Contract + Plot Recipes
+ exact trusted-source, analysis-output, authority, rule, and profile bindings
→ canonical design-package manifest
→ recomputed design_package_hash
→ deterministic validation
→ figure_qc bound to that design_package_hash
→ separately computed figure_qc_sha256
```

The validator-facing design-package manifest records exact component IDs, versions, relative/authorized locations, and SHA-256 hashes, plus the exact trusted-input collection, analysis-output record/collection, authority-decision collection, ruleset, journal/reporting profile, experiment profile, and backend-profile identities actually evaluated. Optional components remain explicitly absent or not assessed; they are not omitted ambiguously.

`design_package_hash` is calculated from the schema-defined canonical representation of that pre-QC manifest and its bound design inputs. It excludes `figure_qc`, `figure_qc_sha256`, and any final bundle field that would depend on them. The design-package manifest's own self-hash field, if present, is excluded by the canonicalization rule.

`figure_qc` then records the exact validated `design_package_hash`. Its `figure_qc_sha256` is computed independently over the canonical QC record excluding only its own self-hash field. A final QC bundle may bind both hashes, but neither hash may contain itself directly or indirectly. Any change to a design component or trusted binding invalidates the prior design-package hash and QC result.

## Figure and package maturity states

Maturity and finality are distinct.

Permitted package maturity states are:

- `architecture_only`: claim/evidence and Figure logic may be planned, but source data are incomplete or not content-verified;
- `ready_for_author_review`: a bounded design package is internally closed but retains author decisions;
- `ready_for_prototype`: required data identities, mappings, units, and supplied analysis outputs are sufficiently bound for a later backend attempt;
- `prototype_generated_unverified`: reserved for Phase 8B or later; a render/code artifact exists but has not completed all checks;
- `prototype_verified`: deterministic execution and declared visual checks passed, but the output is not final;
- `ready_for_qc`: required upstream, data, design, implementation, and declared inspection gates are closed for Module 06/human review;
- `blocked`: one or more required identities, decisions, data relations, statistics, or integrity conditions prevent progression.

Finality states are:

- `design_candidate`;
- `author_review_required`;
- `submission_candidate`;
- `author_approved_final`.

Phase 8A may emit only `design_candidate` or `author_review_required`. Phase 8B may not self-assert `submission_candidate` or `author_approved_final`. Those states require externally supplied author decisions and the declared integrity, journal, and output inspections. A Figure may be mature enough for prototype execution while still requiring author review.

### Maturity-dependent obligation matrix

Schema obligations are conditional on maturity but provenance is never waived. A lower-maturity package must preserve field identity, origin, and an explicit unresolved/not-assessed reason rather than inventing or silently omitting content.

| Requirement | `architecture_only` | `ready_for_author_review` | `ready_for_prototype` |
| --- | --- | --- | --- |
| Upstream artifact identity and claim/evidence relation-map closure | Required | Required | Required |
| Five business artifact types and cross-artifact IDs | Required; data/recipe fields may use explicit unresolved states | Required and internally closed for the proposed design | Required and complete |
| Actual source file/resolver binding | Optional only when availability is explicitly unresolved/unavailable | State-dependent; required for every field asserted as source-verified | Required for every data-bearing layer |
| Trusted existence and hash verification | `not_performed` allowed | Required for any source claimed verified; otherwise unresolved | Required and passed |
| Dataset/sheet/table/header/variable/channel inspection | `not_assessed` allowed | Required for any content asserted inspected; otherwise unresolved | Required and passed for every recipe mapping through a supported reader/authorized adapter |
| Observation/feature/experimental/inference units and replicate hierarchy | Explicit `unresolved` allowed | Complete or explicitly routed to author review; cannot support an inferential readiness claim while unresolved | Required, non-contradictory, and closed across artifacts |
| `n`, pairing, nesting, repeated-measure, batch, and aggregation semantics | Explicit unavailable/unresolved allowed | Complete for any proposed quantitative interpretation or explicitly unresolved | Required for every applicable layer and annotation |
| Statistical/analysis-output binding | `required_but_unavailable` allowed | Supplied record or explicit unresolved state | Admissible supplied record for every displayed result; explicit unavailability allowed only when the recipe omits the dependent statistic/annotation |
| Plot Recipe | Conceptual roles/encodings allowed; nonexistent variables may not be fabricated | Proposed mapping mostly complete with exact unresolved markers | Complete variable, filter, transformation, aggregation, unit, and annotation mappings |
| Image processing and representative-image decision | Requirements may be identified as unresolved | Required for any image design asserted reviewable; representative choice may remain pending | Complete, with raw/processed identity and trusted decision where representative selection is used |
| Trusted authority | Required only for any state already asserted approved/frozen/omitted/final | Required for every such material assertion; pending decisions remain visible | Required for all execution-critical author-only decisions |
| Prototype readiness | Prohibited | Not implied by author-review readiness | Permitted only when every applicable gate above passes |

An `architecture_only` package may therefore be valid at its declared maturity while remaining ineligible for prototype execution. `ready_for_author_review` is a design-review gate, not proof of source completeness. `ready_for_prototype` requires the exact data, variable, unit, replicate, transformation, statistical-output, and material authority bindings specified here.

## Statistical and unit contract

Every quantitative data-bearing panel must distinguish:

- observation unit: what each displayed observation represents;
- feature unit: gene, protein, cell, image object, taxon, peak, voxel, or analogous measured feature when applicable;
- experimental unit: the independently assigned or sampled unit relevant to the design;
- inference unit: the unit to which uncertainty or statistical inference applies;
- biological replicate;
- technical replicate;
- displayed `n` and the exact entity it counts.

The validator must fail closed on a missing or contradictory unit declaration when the panel claims replicate-level evidence or statistical inference. It must reject or block declarations that count cells, spots, reads, fields, technical wells, repeated measurements, or features as independent biological samples unless a separately supplied design explicitly makes them the valid experimental/inference unit.

Pairing, repeated measures, clustering, nesting, batch, longitudinal structure, and pseudoreplication risk must remain explicit. Aggregation from lower-level observations to the inference unit must be declared; neither the model nor plotting backend may silently choose it.

For every displayed summary or statistical annotation, record:

- value/statistic origin;
- exact admissible `analysis_output_record` ID, version, and hash;
- compared groups and direction;
- `n` per group and `n` definition;
- center and spread/interval definition;
- test/model name when supplied;
- sidedness, pairing/nesting, multiplicity correction, and effect-size/uncertainty details when applicable;
- unresolved fields and review status.

The Skill may recommend that a qualified analyst decide an unresolved method. It may not choose a method from the appearance of the data and then present the choice as authorized, or compute and promote whichever analysis produces a preferred result.

Every supplied value or completed statistical state above must resolve to an admissible `analysis_output_record` whose source inputs, contrast, groups, units, `n`, version, hash, and authorization are compatible with the Figure Card and Plot Recipe. Internal agreement among model-produced Figure artifacts is not statistical provenance.

## Experiment-profile routing

Experiment labels are multi-label because a panel may combine modalities. The base vocabulary is:

- `computational_dry_lab`;
- `cell_based`;
- `molecular_biochemical`;
- `animal_in_vivo`;
- `omics`;
- `imaging`;
- `clinical_human`;
- `structural_biophysical`;
- `other`;
- `unresolved`.

Phase 8A enforces generic identity, data, unit, replicate, transformation, and provenance rules. It must not hard-code incomplete discipline-specific science as universal truth.

Later profile packs may add reporting and design requirements for dry-lab/computational, cell, molecular, animal, omics, imaging, clinical, and structural/biophysical work. Each profile must be versioned and must define its applicability, required inputs, deterministic checks, semantic/human checks, and conflict resolution. A missing profile creates `not_assessed` or `author_review_required`; it does not permit false compliance.

Examples of later profile-specific issues include dataset split and seed identity, cell-line authentication and passage, biological versus technical assay replicates, animal allocation/blinding and animal-as-unit rules, multiple-testing/feature filtering, image segmentation and field selection, participant denominators, and structure-map/model provenance. These are deferred extensions, not Phase 8A promises.

## Image, gel, blot, and spatial-panel integrity

Data-bearing image panels require, as applicable:

- raw-source identity and hash;
- processed-image identity and hash;
- acquisition modality and channel identity;
- field, region, time point, specimen, section, or lane identity;
- scale and scale-bar provenance;
- crop coordinates or a reproducible crop description;
- linear/global contrast and brightness operations;
- background subtraction, denoising, deconvolution, segmentation, pseudocolor, stitching, projection, registration, and overlay history;
- lane or region rearrangement and explicit divider policy;
- reuse relationships across figures/panels;
- representative-image decision and its external authorization;
- quantified-source link when the panel represents a quantified claim.

The Skill must not perform or conceal selective deletion, cloning, generative fill, local masking, undeclared splicing, object relocation, non-global enhancement, or a crop that changes interpretation. It must not call an image representative based only on visual appeal. If the raw identity, processing log, or quantified link is required but absent, the panel is blocked or remains architecture-only.

A conceptual schematic may use illustrative assets only when their origin/licence and non-data status are explicit. It must not use a synthetic microscopy, gel, blot, structure, trace, or heatmap-like image as if it were measured evidence.

## Reference-figure and copyright boundary

Reference figures may inform functional analysis of:

- evidence hierarchy;
- panel roles and sequencing;
- visual grammar;
- information density;
- legend organization;
- encoding patterns;
- explicitly cited layout principles at an abstract level.

Each extracted feature must carry an exact source locator and `observed`, `inferred`, or `missing` status. Inference from a reference is a reviewable abstraction, not an observed fact.

The Skill must not:

- copy, trace, crop, embed, or redistribute a published panel, PDF image, long legend, or proprietary design asset;
- recreate a publication-specific arrangement closely enough to function as copying;
- treat a screenshot or rasterized publication panel as reusable source data;
- remove a citation or provenance record from a borrowed conceptual idea;
- claim copyright clearance.

The target Figure must be derived from the author's scientific structure and source data. A reference Figure is not a template asset.

Phase 8A may deterministically verify reference identity, source locator, feature/abstraction type, `observed`/`inferred`/`missing` provenance, declared `functional_abstraction` use, non-embedding, and explicitly declared prohibited-use states. It must not claim to detect substantial visual/layout similarity, copying from appearance, fair-use status, licence sufficiency, or copyright clearance. Those questions remain `not_assessed` or `human_review_required` unless resolved outside Phase 8A.

## Color, accessibility, and semantic consistency

Color mappings are project-level scientific semantics. The same entity or condition must not change color without an explicit scoped reason; different entities must not share an ambiguous identity color. Color must not be the only carrier of a critical distinction when shape, line, label, texture, or direct annotation can preserve accessibility.

Each palette entry binds a semantic key, value, scope, and version. The validator may check mapping closure, duplicates, contradictions, and declared accessibility status. Human or tool-assisted inspection is still required for contrast, color-vision accessibility, grayscale distinguishability, and crowded-panel legibility.

## Journal and reporting profiles

Hard journal requirements are external, time-sensitive inputs. A journal profile must record source URL or supplied rule source, target article/figure type, profile version, verification date, and applicability. The contract must not freeze current Nature or other publisher dimensions, DPI, font sizes, file types, color modes, or panel limits as universal rules.

If no current verified profile is supplied, the Skill may produce a scientifically structured design candidate using project defaults, but `journal_compliance` remains `not_assessed`. A stale, inferred, or model-recalled profile cannot support `compliant`.

Reporting profiles may request information but cannot change data or create missing methods. Their results remain separate from scientific, statistical, image-integrity, and visual-design findings.

## Optional backend routing

The core package has no hard dependency on R, Python, FigureYa, or another plotting system. A backend profile must declare:

- backend name and exact version;
- available modules/geometries;
- supported source formats;
- required data shapes;
- statistical assumptions and whether statistics are computed or merely annotated;
- deterministic parameters and seeds where relevant;
- known limitations;
- verification state and environment identity.

The router may select a backend only when the requested recipe and verified backend capabilities match. A FigureYa-like visual module is inadmissible when it merely resembles the requested panel but expects incompatible data shape, replicates, summaries, or statistical semantics. Missing capability causes an explicit unsupported/blocked result; it does not permit silent substitution.

Phase 8A stores optional routing intent only. It does not execute a backend.

## Model and deterministic responsibility split

The model may propose, subject to review:

- panel role and Figure narrative;
- evidence hierarchy and panel order;
- plot archetype and visual encoding;
- layout relationships;
- legend-content requirements;
- accessibility improvements;
- unresolved scientific, statistical, integrity, or journal questions.

The model must not assert that its proposal is an observed scientific fact, source-data property, authorized analysis, valid statistic, representative field, or final author decision.

The Phase 8A deterministic layer may verify:

- JSON Schema validity and closed/enumerated fields;
- artifact IDs, versions, hashes, manifest membership, and reference closure;
- upstream object identity and permitted document-type routing;
- uniqueness and parent/child relationships of figure/panel IDs;
- source-file existence, size, and recomputed hash through exact `trusted_source_inputs` bindings when locally or otherwise resolvably accessible;
- supported table/dataset/sheet/header/variable/channel identities through the reader/adapter actually used, while recording unsupported inspection as `not_performed`;
- required unit/replicate/`n` declarations and cross-artifact equality;
- claim/evidence/source-data mappings and closure through supplied structured upstream relation maps;
- structured claim-ceiling comparisons only when both upstream and Figure artifacts expose compatible deterministic ceiling fields;
- Plot Recipe variable mappings and transformation declarations;
- statistical annotation identities and admissible `analysis_output_record` bindings;
- external authority-decision identity, non-circular subject hash, decision type/value, producer-role, and trusted-collection resolution;
- Figure Contract panel order and coverage;
- palette-semantic consistency;
- declared image-processing/provenance fields;
- prototype/finality gates;
- journal/backend/profile provenance fields;
- exact expected issue codes for negative fixtures.

The deterministic layer cannot establish:

- whether a claim is scientifically true;
- whether evidence semantically supports a claim;
- whether natural-language Figure wording exceeds a natural-language claim when no comparable structured ceiling is supplied;
- whether a statistical method is scientifically appropriate;
- whether a Figure is persuasive, readable, unbiased, or aesthetically effective;
- whether image processing is honest merely because it is declared;
- whether a published layout is too similar for copyright purposes;
- whether an author identity is genuine;
- whether current journal requirements were exhaustively captured.

## Readiness and stop rules

Progression to `ready_for_prototype` requires, at minimum:

- exact upstream and source-data identity closure through the supplied structured relation maps and `trusted_source_inputs`;
- no claim/evidence ID outside the supplied upstream relation closure;
- all required variables present in an actually inspected supported source or an explicitly authorized adapter result;
- explicit experimental/inference unit, biological/technical replicate, and `n` semantics;
- declared filters, exclusions, transformations, and aggregation;
- statistical annotations bound to admissible `analysis_output_record` inputs, or omitted from the rendered recipe when explicitly unavailable;
- no unresolved blocking image-integrity requirement;
- complete Figure Card → Figure Contract → Plot Recipe mapping;
- no prototype/finality contradiction;
- all material model proposals still correctly marked for review;
- every execution-critical author-only decision resolved through `trusted_authority_inputs`.

The Skill must stop or remain degraded when:

- source data are absent, mismatched, or unverifiable for requested rendering;
- a panel requires invented data, labels, statistics, or scientific meaning;
- the experimental or inference unit is unresolved for a quantitative claim;
- an undeclared exclusion, crop, transformation, or summary would be needed;
- a requested design suppresses negative/conflicting evidence or hides variation;
- an upstream claim/evidence relation cannot be resolved;
- a required author decision is absent;
- copyright, image-integrity, journal, or backend constraints cannot be satisfied within the supplied scope.

The proper output is then a structured blocked/degraded package and focused author queries, not a plausible-looking Figure.

## Module handoffs

### From Module 02

Consume the exact `figure_sequence` item and only the claim/evidence/interpretation records it references. Preserve order, purpose, and approval state. Do not treat `author_approval: approved` on the sequence as proof of data existence or statistical validity.

### From Module 04

Consume only `candidate_figure_table_briefs` whose `output_type` is `figure`. Preserve theme, claim, source, support, conflict, and review status. Do not count linked publications as independent evidence or convert source synthesis into primary data.

### To Module 06

Handoff should include the complete five-artifact package, source and optional rendered-output identities, exact rule/profile versions, unresolved findings, and the declared comparison/inspection scope. The current minimum Module 06 prose gate does not by itself certify Figure packages; a Figure-capable QC extension must be separately contracted and implemented before the handoff is described as executed.

### To the author or caller

Return bounded design decisions, unresolved questions, blocked reasons, and precise source/field locators. Do not hide a missing decision inside prose.

## Phase 8A candidate directory contract

After this development contract is approved, the minimum implementation should use:

```text
05_scientific-figure-designer/
├── DEVELOPMENT_CONTRACT.md
├── IMPLEMENTATION_REVIEW.md
├── TEST_SUMMARY.md
└── candidate/
    ├── schemas/
    │   ├── figure-card.schema.json
    │   ├── figure-contract.schema.json
    │   ├── source-data-manifest.schema.json
    │   ├── plot-recipe.schema.json
    │   ├── figure-qc.schema.json
    │   ├── figure-shared-definitions.schema.json
    │   ├── trusted-source-inputs.schema.json
    │   ├── analysis-output-record.schema.json
    │   ├── figure-authority-decision.schema.json
    │   └── design-package-manifest.schema.json
    ├── scripts/
    │   ├── validate_figure_package.py
    │   └── schema_runtime.py
    └── tests/
        ├── fixtures/
        └── test_figure_package.py
```

The first five listed schemas are the five Figure business artifacts. The remaining schemas are shared or validator-facing trust/package interfaces and do not expand the business-artifact count. Names may receive a narrow review-driven amendment, but Phase 8A must not add plotting/rendering scripts or a full `SKILL.md`.

## Required positive fixtures for Phase 8A

At minimum, later implementation must include:

1. An Original Article two-panel quantitative Figure package with exact Module 02 references, recomputed trusted source-data identity, distinct biological/technical replicate semantics, an admissible supplied `analysis_output_record`, consistent palette semantics, non-circular package/QC hashes, and `ready_for_author_review` state.
2. A Review conceptual Figure package with exact Module 04 figure brief/theme/source references, no primary-data claim, explicit schematic status, and correct source/copyright provenance.
3. An image-plus-quantification Figure package whose image record, processing history, externally trusted representative-image decision, scale information, quantified-source record, and cross-panel claim relation all close.
4. An `architecture_only` package that passes only the checks appropriate to that maturity state and cannot be promoted to `ready_for_prototype`.

## Required negative matrix for Phase 8A

The implementation must use exact stable case IDs, expected issue codes, and executable test bindings. This matrix is limited to conditions the deterministic validator can establish from supplied structured records, exact identities, trusted inputs, and declared states. At minimum, it must reject or correctly block:

### Upstream and authority failures

- panel claim absent from the bound upstream package;
- panel evidence ID that does not resolve through the supplied upstream claim–evidence relation map for the referenced claim context;
- Review Figure brief used as proof of primary data;
- Module 04 table brief silently converted to a Figure;
- upstream artifact version or SHA-256 mismatch;
- self-issued or embedded-only `author_approved` design or representative-image decision that does not resolve to `trusted_authority_inputs`;
- calling workflow presented as author approval;
- authority decision type/value incompatible with its subject or asserted state;
- authority decision governed subject ID/version/non-circular hash mismatch;
- authority or trusted-collection record hash mismatch;
- an approved material omission that does not bind the exact panel/evidence/version/non-circular content hash;
- cross-source Review synthesis structurally labelled as one source-authored claim despite the supplied Review origin fields;
- linked publications counted as distinct independent evidence units despite a supplied common evidence-unit or linked-publication identity.

### Source-data and variable failures

- source-data record used as verified without an exact `trusted_source_inputs` binding;
- trusted source-data file missing, recomputed size/hash mismatched, or identity-conflicted;
- model-produced manifest inspection state used to self-certify existence, hash, or content;
- two records assign incompatible identities to the same source object;
- unsupported binary format represented as content-inspected;
- table/sheet/dataset locator not found by the recorded supported reader/adapter;
- mapped variable/column/channel absent from the actually inspected trusted input;
- variable type or unit incompatible across manifest, card, and recipe;
- raw, processed, and derived status conflated;
- filter, exclusion, missing-data handling, normalization, aggregation, or transformation omitted from the recipe;
- transformed value represented as raw;
- external bibliography/source record represented as primary data.

### Unit, replicate, and statistics failures

- observation, experimental, or inference unit missing for an inferential panel;
- technical replicates counted as biological `n`;
- cells, spots, reads, fields, features, repeated time points, or technical wells counted as independent sample/participant/animal `n` without a valid supplied design;
- paired/repeated/nested/batch structure dropped between artifacts;
- group `n` conflicts across manifest, card, recipe, and annotation;
- center or spread label does not match the bound `analysis_output_record` fields;
- a p-value, adjusted p-value, effect size, interval, test, correction, or significance symbol has no admissible `analysis_output_record` binding;
- analysis-output record version/hash, source-data inputs, contrast, groups, units, or `n` conflict with the card/recipe;
- model-proposed analysis requirement presented as a supplied, authorized, or completed result;
- unavailable statistic silently filled or a “not significant” result inferred from missing annotation;
- backend statistical assumptions conflict with structured declared data/unit fields.

### Figure-story and visual-semantic failures

- Figure Contract structured strength/causality/mechanism/generalization field exceeds a compatible structured upstream ceiling;
- panel order silently changes an approved upstream Figure sequence;
- an upstream machine-identified required negative, null, conflicting, control, limitation, or uncertainty record is omitted without a compatible trusted material-omission decision;
- same semantic entity receives inconsistent colors without an explicit scoped decision;
- different entities receive an ambiguous identical semantic key;
- a critical distinction is color-only while accessibility is falsely marked verified;
- a panel explicitly typed `decorative` is simultaneously declared evidence-bearing;
- a panel explicitly typed `conceptual_schematic` is simultaneously declared measured primary data;
- panel or recipe is orphaned from the Figure Contract;
- duplicate panel IDs or impossible panel order;
- architecture-only package marked ready for prototype.

### Image-integrity and copyright failures

- representative image lacks exact raw/source locator or external decision;
- image claim lacks its required quantified-source link;
- crop, contrast, background, pseudocolor, projection, stitching, segmentation, or rearrangement operation is required but undeclared;
- local masking, cloning, generative fill, hidden splicing, or object relocation is represented as acceptable processing;
- lane rearrangement lacks identity/divider provenance;
- scale bar lacks calibration provenance;
- a known identical source file/region identity is reused across panels without a declared reuse relationship;
- published panel, screenshot, long legend, or PDF raster is embedded as a reusable target asset;
- an explicitly declared `copied_reference` layout or prohibited reference-asset use is represented as an original design;
- an asset whose supplied provenance declares synthetic/generative origin is labelled as measured evidence.

### Backend, profile, QC, and finality failures

- unavailable requested backend is silently replaced;
- visually similar backend module is used despite data-shape or statistical mismatch;
- backend or journal profile version/verification provenance is missing while compliance is asserted;
- stale journal profile is used to claim current compliance;
- file existence/hash check is represented as scientific or visual verification;
- deterministic validator pass is represented as semantic, statistical, image-integrity, or copyright approval;
- no rendered output was inspected while visual QC is marked passed;
- prototype is marked `submission_candidate` or `author_approved_final` without admissible external decisions and required gates;
- `design_package_hash` includes or depends on `figure_qc`, or Figure QC binds a different design-package hash;
- `figure_qc_sha256` includes its own self-hash field or does not match the recomputed canonical QC hash;
- Phase 8A package claims that plotting code was executed.

## Deferred model/human forward-review matrix

The following cases are important but are not Phase 8A deterministic rejection tests. They must remain `not_assessed`, `model_review_required`, or `human_review_required` until an authorized later review is performed:

- whether an evidence item is scientifically relevant to or semantically supports the Figure claim beyond the supplied structured relation map;
- whether natural-language Figure conclusions, titles, labels, or legends strengthen causality, mechanism, generalization, clinical meaning, or certainty beyond natural-language upstream claims when no comparable structured ceiling exists;
- whether a supplied statistical method, model, contrast, correction, effect-size choice, aggregation, or uncertainty representation is scientifically appropriate;
- whether the Figure is persuasive without being biased, whether variation or negative evidence is visually minimized, and whether scale/ordering choices mislead despite being declared;
- visual readability, information density, panel balance, accessibility by actual inspection, and aesthetic effectiveness;
- whether an externally approved representative image is scientifically representative or whether field/region selection is biased;
- whether declared image processing is scientifically acceptable or conceals manipulation detectable only by raw/visual/forensic review;
- whether a target layout is substantially or visually similar to a reference, constitutes copying, is licensed, qualifies for an exception, or has copyright clearance;
- whether journal/reporting rules were interpreted completely and correctly beyond their structured profile;
- whether an optional backend's output faithfully implements the intended visual/scientific design after rendering.

Forward-review fixtures may be designed later for model/human evaluation, but they must not be counted as Phase 8A deterministic passing evidence or as a prerequisite secretly implemented by heuristic text/image similarity checks.

## Implementation acceptance conditions

Phase 8A will be eligible for freeze only when:

- the five business schemas, shared definitions, and validator-facing trust/package interfaces remain within this contract without creating a sixth business artifact;
- the validator is dependency-light and deterministic;
- all positive fixtures pass for their declared maturity states;
- every required deterministic negative case has a stable ID, expected issue code, and executed binding;
- schema/runtime/CLI failure paths are tested;
- package outputs are deterministic under a defined canonicalization rule;
- trusted source, analysis-output, and authority collections cannot be manufactured inside the model-produced Figure package;
- design-package and Figure-QC hashes are recomputed under the non-circular lifecycle and mutation-tested;
- no fixture or validator mints author/scientific/statistical authority;
- no code, schema, or documentation claims a render or real-paper test occurred;
- bytecode/cache/generated clutter is absent from the candidate;
- review notes state exactly what was and was not validated;
- the candidate remains under `result` and uninstalled.

Model/human semantic review, model-level Figure design, rendered-output quality, real-paper usefulness, discipline-profile accuracy, journal compliance, and optional backend execution remain separate forward tests even after Phase 8A passes.

## Deferred work

This contract intentionally defers:

- full `SKILL.md` routing and activation;
- plot-code generation and execution;
- statistical analysis or method selection;
- visual render inspection;
- real-paper and real-data testing;
- the dry-lab, cell, molecular, animal, omics, imaging, clinical, and structural/biophysical profile implementations;
- current journal/reporting profile packs;
- a Figure-capable Module 06 QC extension;
- automated copyright-similarity judgement;
- installation in the user's active Skills directory.

These items may proceed only after their own boundaries are reviewed. This `0.1.1` contract is frozen as the Phase 8A development boundary in `result`; it is not an enabled Skill and does not claim that Phase 8A has been implemented.
