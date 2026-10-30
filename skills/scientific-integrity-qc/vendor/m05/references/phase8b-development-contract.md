# Phase 8B — `05_scientific-figure-designer` Model Design and Prototype Execution Contract

Contract version: `0.1.1`  
Status: final frozen development contract  
Upstream contract: Phase 8 Development Contract `0.1.1` — frozen  
Required upstream implementation: Phase 8A deterministic implementation `0.1.2` — externally reviewed, final pass, frozen  
Implementation status: not implemented; minimum candidate boundary defined  
Installation status: uninstalled  

## Purpose

Phase 8B defines how a model may refine a bounded Figure design, translate a Phase 8A-validated Plot Recipe through a bounded program representation into reproducible restricted Python code for the minimum implementation, execute that code when an independently probed backend is available and separately authorized, and inspect an explicitly non-final rendered prototype. R and other backends remain later extensions under the same provenance boundary.

It does not reopen Phase 8A. It consumes the five frozen Figure business-artifact types and their deterministic trust boundary. Any model-proposed change to Figure content, panel mapping, source use, transformation, or layout must be represented as a new artifact version and pass Phase 8A again before prototype execution.

The intended chain is:

```text
Phase 8A-validated design package
→ bounded model design review
→ author/caller resolution of material decisions
→ revised package revalidated by Phase 8A when needed
→ validated ready_for_prototype Plot Recipe
→ backend-specific code generation
→ static execution-package validation
→ optional prototype execution
→ non-final rendered prototype
→ deterministic metadata/file inspection
→ model/human render inspection
→ Phase 8B Figure QC
→ later Figure-capable Module 06 QC
→ author manual validation/final recreation or acceptance
```

## Non-goals and authority boundary

Phase 8B must not:

- modify or weaken the frozen Phase 8 or Phase 8A contracts, schemas, validators, tests, or trust-root chain;
- create, impute, repair, smooth, selectively exclude, relabel, or fabricate source data;
- choose or recompute an inferential analysis, statistical test, effect, interval, p-value, adjusted p-value, significance symbol, or representative field as scientific authority;
- change observation, feature, experimental, or inference units, replicate semantics, `n`, pairing, nesting, batch, time, contrast, group order, or comparison direction;
- add a data transformation, filter, exclusion, aggregation, crop, contrast operation, annotation, or source that is absent from the validated Plot Recipe;
- treat successful code generation, zero exit status, a non-empty image, visual appeal, or clean model review as scientific validation;
- silently install packages, switch backend, fetch modules/data, use network resources, or execute an unavailable FigureYa module;
- overwrite source data, upstream artifacts, existing author figures, or prior prototype runs;
- claim `submission_candidate`, `author_approved_final`, journal compliance, copyright clearance, image integrity, or author approval;
- use generative image synthesis, content-aware fill, cloning, masking, object relocation, or other synthetic editing on measured scientific images;
- make the current minimum Module 06 prose QC appear Figure-capable before a separate Figure QC extension exists.

Author approval of a layout or design does not repair an invalid source binding, undeclared transformation, incompatible analysis record, failed execution, or render mismatch.

## Operating modes

Phase 8B has three explicit modes. A run declares exactly one primary mode.

### 1. `model_design_review`

Consumes a Phase 8A-valid `architecture_only`, `ready_for_author_review`, or `ready_for_prototype` package and proposes bounded improvements to panel role, evidence hierarchy, visual grammar, layout, labels, palette use, accessibility, and reviewer-risk visibility.

This mode produces a reviewable `design_revision_proposal`; it does not mutate the admitted design package. A material proposal must be accepted through the applicable external authority route, applied as a new version of the existing five business artifacts, and revalidated by Phase 8A.

### 2. `prototype_code_generation`

Requires a Phase 8A-valid `ready_for_prototype` package. It translates the exact validated Plot Recipe into one selected backend program and creates a pre-execution manifest. It may run syntax/static checks but does not imply that plotting succeeded.

### 3. `prototype_execution_and_inspection`

Requires a valid code-generation package, an available matching backend/environment, caller authorization for the scoped execution, and a new output directory. It executes the declared program, records actual runtime evidence, hashes outputs, and performs declared metadata and render inspections.

Code generation and execution may occur in one user-requested workflow, but their states and evidence remain separate.

## Admission gates

Every mode requires exact bindings to:

- `design_package_hash` and the admitted design-package manifest identity/version;
- Phase 8A `figure_qc` identity/version and `figure_qc_sha256`;
- the externally supplied trusted-inputs root file identity and caller-held SHA-256 used by Phase 8A;
- all five business-artifact IDs, versions, and hashes;
- the relevant source, analysis-output, and authority collection IDs, versions, and hashes;
- the Phase 8A validator/ruleset versions that produced the admission result.

Phase 8B admission must recompute, not inherit, the Phase 8A result. `validate_phase8b_admission.py` must invoke the frozen Phase 8A `0.1.2` validator at `candidate/scripts/validate_figure_package.py` against the exact design package, exact external trusted-inputs root, and caller-held expected trust-root SHA-256. It must not copy, fork, or reimplement the Phase 8A validation rules.

The recomputed result must be `valid`. Its recomputed `design_package_hash`, Phase 8A Figure-QC identity/version, and `figure_qc_sha256` must exactly match the Phase 8B admission bindings. A supplied old QC record, embedded `valid` field, or supplied receipt cannot admit a package whose current recomputation fails or differs.

The admission process may emit a validator-produced `phase8a_admission_receipt`, but the receipt is evidence of the just-completed invocation rather than a substitute for that invocation. A model-produced or caller-supplied receipt is never trusted as admission evidence.

`prototype_code_generation` and `prototype_execution_and_inspection` additionally require:

- package maturity `ready_for_prototype`;
- a fresh validator-produced `phase8a_admission_receipt` recording a recomputed valid Phase 8A result for the exact admitted hashes;
- no unresolved Phase 8A blocker affecting a rendered layer;
- complete panel-to-recipe coverage for every requested output;
- exact source variables, units, transformations, group/facet order, and annotation inputs;
- all execution-critical author-only decisions resolved through trusted authority inputs;
- a deterministic-probe-produced backend/environment profile whose verified capabilities match the Plot Recipe.

An old QC pass cannot admit a mutated artifact, source, trusted collection, Plot Recipe, or authority decision. Admission must be recomputed when any bound identity changes.

## Inputs

Required inputs are:

1. The exact Phase 8A design package and its external trust-root inputs.
2. A primary operating mode.
3. The requested Figure IDs and panel IDs.
4. A scoped output location that does not overwrite existing work.
5. For the minimum implementation, the restricted `python` backend. R or a named optional module backend requires a later reviewed backend extension.
6. A `backend_environment_profile` produced by the deterministic Phase 8B environment probe, not by model assertion.
7. Requested prototype output formats and review dimensions.
8. A separately supplied `prototype_execution_authorization` when code will actually run.

Conditional inputs include a current journal/reporting profile, project style tokens, font availability, palette profile, reference-figure functional abstractions, image-processing instructions, and author authority decisions. Missing conditional input yields `not_assessed`, `author_review_required`, `unsupported`, or `blocked` as appropriate; memory-based completion is prohibited.

## Artifact boundary

The five Figure business artifacts remain exactly:

1. `source_data_manifest`;
2. `figure_card`;
3. `figure_contract`;
4. `plot_recipe`;
5. `figure_qc`.

Phase 8B may create the following execution-support records without treating them as additional Figure business artifacts:

- `phase8a_admission_receipt`;
- `backend_environment_profile`;
- `prototype_execution_authorization`;
- `design_revision_proposal`;
- `bounded_program_plan`;
- `prototype_execution_manifest`;
- generated backend program files;
- `render_output_manifest`;
- `render_inspection_record`;
- runtime logs and session/environment records.

Phase 8B may emit a distinct record of the existing `figure_qc` artifact type that binds execution and render evidence. It uses the same schema name/business-artifact type but a new Phase 8B QC artifact ID, version, and hash, plus an exact `upstream_phase8a_qc_ref`. It must not reuse, overwrite, or ambiguously replace the Phase 8A QC record or schema.

## `phase8a_admission_receipt`

The receipt is generated only by `validate_phase8b_admission.py` after it directly invokes the frozen Phase 8A validator. It binds:

- receipt ID/version and canonical receipt hash;
- exact design-package manifest identity and recomputed `design_package_hash`;
- exact Phase 8A Figure-QC identity/version and recomputed `figure_qc_sha256`;
- frozen Phase 8A validator and ruleset versions;
- exact external trusted-inputs-root file identity and caller-held expected SHA-256;
- validation command/invocation identity, completion time, result, and issue count;
- exact admitted component, trusted-collection, and authority hashes returned by the validation run.

The receipt cannot be accepted as an input assertion. Phase 8B admission creates it anew for each admitted package state. Any package, trust-root, collection, validator, ruleset, or QC identity change requires another invocation and a new receipt.

## `backend_environment_profile`

This validator-facing support interface is produced by a deterministic environment probe and binds:

- profile ID/version and canonical profile hash;
- backend kind and capability-surface version;
- exact executable absolute path and executable file identity/hash where feasible;
- runtime version and platform identity;
- relevant installed package/module names and exact versions;
- supported input/output formats, fonts discovered within the scoped probe, and supported bounded program operations;
- unavailable capabilities and known limitations;
- probe script identity/version/hash, probe command, timestamp, and result.

The probe reports only what it actually checked. Admission/code generation obtains the profile by directly invoking the probe, and the runner reruns or narrowly refreshes the probe immediately before execution to confirm that the executable and required package capabilities still match. A supplied profile file alone, model recollection, an intended environment, or fields copied into an execution manifest cannot establish backend availability. The minimum implementation requires only one actually available restricted Python profile.

## `prototype_execution_authorization`

This validator-facing interface is supplied outside the model-produced execution package through the caller/orchestration channel. Its expected file/record hash is caller-held or carried by an independently trusted orchestration envelope. The validator recomputes that hash before use. The interface binds:

- authorization ID/version and canonical authorization hash;
- exact `execution_package_hash` and generated program hash;
- exact backend-environment-profile ID/version/hash;
- exact admitted input IDs/hashes and Phase 8A admission-receipt hash;
- exact output directory and permitted read/write scope;
- exact permitted command/run identity and bounded parameters;
- caller authorization origin/state and authorization time;
- expiration or bounded conditions when supplied.

The execution manifest references this external authorization by exact identity/hash. It cannot self-certify `caller_accepted`, embed its own trusted authorization, or derive the caller-held expected authorization hash. Any change to the program, execution package, backend profile, inputs, command, parameters, or output scope invalidates the authorization and requires a new one.

## `design_revision_proposal`

A design proposal records:

- proposal ID/version and canonical hash;
- exact admitted design-package and component hashes;
- affected Figure/panel/recipe IDs;
- proposal entries typed as either `bounded_design_operation` or `authoritative_input_query`;
- proposal rationale and expected visual benefit;
- whether each operation is scientific, statistical, source/data, layout, label, palette, accessibility, or presentation-only;
- required authority decision type;
- deterministic revalidation requirements;
- unresolved risks and rejected alternatives.

The model may provide concrete before/after values only for bounded presentation fields: layout realization, content-preserving label wording, palette presentation consistent with admitted semantic keys, accessibility, and other presentation-only properties. Those operations still require any applicable design/layout authority and Phase 8A revalidation when they change a business artifact.

For source data, scientific values or meaning, `n`, units, replicates, statistical or inferential content, p-values, effect sizes, transformations, filters/exclusions, representative fields, new evidence, material omissions, Figure conclusions, or finality, the model may emit only a blocker, query, or required-authoritative-input record. It must not emit an executable replacement value. Author approval alone cannot convert model-invented scientific, source/data, or statistical content into authoritative content; the replacement must come from an admissible source, analysis, or author input and then pass Phase 8A.

The proposal may not directly carry an approved/frozen state. Accepted bounded proposals become new versions of the existing business artifacts when applicable and must return through Phase 8A.

## `realization_correction`

A realization correction changes generated code solely to conform to the already admitted Plot Recipe. Permitted examples include restoring a declared layer omitted by the generator, correcting an implementation of an existing content-preserving label, fixing a font/backend defect, or correcting panel spacing without changing the admitted layout relationship.

A realization correction creates a new bounded-program/program hash and therefore a new execution, authorization, render, inspection, and QC chain. It does not change the Phase 8A design-package hash.

Changing semantic palette identity, panel membership/order or mapping, axis/data mapping, label meaning, source variable, filter, exclusion, transformation, aggregation, summary intent, statistical annotation, Figure Card, Figure Contract, Source Data Manifest, Plot Recipe, analysis output, authority decision, or trusted collection is a `design_change`, not a realization correction. Every design change must return through Phase 8A before code generation or execution.

## `bounded_program_plan`

The minimum executable surface is a generator-owned, versioned intermediate representation rather than arbitrary handwritten code. Each operation binds:

- exact Figure, panel, Plot Recipe, and recipe-layer IDs;
- exact source-data, trusted-input, variable, and admissible analysis-output IDs/hashes;
- one operation from a versioned allowlist of reads, bounded table selection, declared display transformation, mapping, mark, annotation, layout, and export operations;
- declared parameters, order, expected input/output type, and deterministic seed where applicable;
- generated-code block identity and expected output membership.

The deterministic generator converts this plan into restricted Python. A program not produced by the declared generator from the exact plan, or a plan operation outside the allowlist, is unsupported and must fail closed.

## `prototype_execution_manifest`

The pre-execution manifest binds:

- execution-manifest ID/version and canonical `execution_package_hash`;
- exact Phase 8A design-package and QC hashes;
- Phase 8A admission-receipt identity/hash;
- operating mode, requested Figure/panels, selected backend, and deterministic backend-environment-profile identity/hash;
- runtime executable identity/version and dependency inventory;
- bounded-program-plan identity/hash and generator identity/version/hash;
- generated program paths, sizes, and SHA-256 hashes;
- exact read-only input paths/resolver identities and expected hashes;
- exact new output directory and permitted output filenames;
- Plot Recipe layer-to-code mapping;
- declared parameters, deterministic visual seeds, locale, and relevant environment settings;
- allowed display transformations and explicit prohibited operations;
- syntax/static-check state;
- exact external prototype-execution-authorization identity/hash and caller-held expected authorization hash;
- generation status and unresolved blockers.

`execution_package_hash` is the hash of a schema-defined pre-authorization subject: the canonical execution manifest and bound plan/program/configuration fields excluding its own hash, the external prototype-execution-authorization reference/hash/state, and all runtime/render outputs. The separately supplied authorization binds this pre-authorization hash. After authorization is attached, the validator verifies the authorization reference and caller-held expected authorization hash without feeding either back into `execution_package_hash`; this prevents an authorization/package hash cycle.

## Restricted generated-code contract

The minimum implementation executes only restricted Python produced by the Phase 8B generator from the admitted `bounded_program_plan`. It does not accept arbitrary handwritten Python or R and does not claim general-purpose program safety.

`validate_generated_program.py` must parse the Python AST and allow only the versioned imports, calls, assignments, literals, control constructs, and plotting/export operations required by the bounded surface. It must reject unsupported syntax or constructs, including:

- `eval`, `exec`, `compile`, dynamic import, reflective/dynamic attribute dispatch, or undeclared helper code;
- subprocess, shell, process-launch, socket, HTTP/network, downloader, or package-installer calls;
- arbitrary filesystem enumeration, globbing, traversal, environment-secret access, or undeclared path construction;
- undeclared aggregation, transformation, statistical/inferential computation, data-driven thresholding, feature selection, representative-field selection, or preferred-result search;
- writes outside the declared output scope or mutation of admitted input/source files.

Restricted generated Python must:

- read only the exact admitted source identities and keep source files read-only;
- map every displayed layer to an exact Plot Recipe ID/layer and source field;
- preserve group, factor, facet, panel, comparison, axis, unit, palette-semantic, and annotation order;
- implement only declared filters, exclusions, transformations, normalizations, aggregations, crop/contrast operations, and display summaries;
- display supplied statistical results through their admitted analysis-output bindings rather than silently recomputing them;
- fail clearly on missing columns, unexpected types, incompatible units, empty post-filter data, missing fonts/packages, or unsupported geometry;
- use deterministic seeds for stochastic layout, label placement, sampling, or rasterization when the backend exposes such behavior;
- save the exact plotting table or image-region manifest actually consumed by each data-bearing layer;
- save package/session versions and runtime metadata;
- write only inside the declared new run directory;
- create editable source plus requested vector/raster prototype outputs when supported;
- mark outputs and manifests as prototype/non-final through filenames and machine-readable state;
- avoid network access, package installation, shell-driven download, hidden data discovery, or fallback paths not declared in the manifest.

Generated code may perform deterministic display transformations already specified in the validated Plot Recipe. A new inferential computation, model fit, data-driven threshold, feature selection, representative-field selection, or preferred-result search requires a separately authorized analysis/design workflow and a new Phase 8A-admitted analysis output or decision.

Every rendered layer must close through `Plot Recipe layer → bounded program operation → generated code block → exact source/analysis IDs`. AST validation is necessary but not sufficient: runtime enforcement must verify exact input hashes before execution, bound all writes to the authorized output directory, record actual output membership, and verify admitted source identities again after execution. Unsupported behavior blocks execution rather than being approximated by source-text regexes.

## Backend and environment routing

Backend selection follows the requested Plot Recipe and verified capability profile, not visual resemblance.

- The minimum implementation supports only the restricted Python backend produced by the generator. R, FigureYa, cross-backend comparison, and arbitrary user-supplied programs require later reviewed extensions.
- Do not silently switch from R to Python, Python to R, or a named module to handwritten code because a dependency is missing.
- Do not run dependency installers. Missing packages produce a bounded blocker and installation instructions or an approval request outside this contract.
- A FigureYa-like module is admissible only after its actual module code, example input schema, data shape, statistical behavior, dependency requirements, and output path are inspected and matched.
- Original FigureYa or other reference modules remain read-only; adaptation occurs in a task-specific run directory.
- Backend profile provenance comes only from the deterministic probe and records the environment actually checked, not a recalled or intended environment.

The same validated Figure design may produce different backend programs, but each backend has a separate execution-manifest identity/hash and cannot inherit another backend's execution or inspection result.

## Execution and filesystem boundary

Prototype execution must:

- use a new run directory under the user-approved task scope;
- resolve and record absolute input and output paths before launch;
- recompute and match the external execution-authorization, program, backend-profile, admission-receipt, and input hashes immediately before launch;
- reject path escape, undeclared writes, source overwrite, or collision with an existing material output;
- record the exact command, start/end timestamps, exit code, stdout/stderr/log identities, runtime version, and program hash;
- stop after the declared bounded run; it must not retry indefinitely or mutate scientific inputs to obtain a render;
- classify execution as `not_run`, `blocked`, `failed`, or `succeeded` independently of render inspection;
- preserve failed logs and partial-output identities without presenting them as successful outputs.

The runner must recompute admitted source/input identities after execution and fail the run if a source was modified. Static AST checks and runtime path/hash enforcement complement one another; neither alone certifies arbitrary code.

Remote/HPC execution, software installation, environment modification, upload, and Slurm submission remain subject to the host project's separate approval policy and are not authorized by this contract.

## `render_output_manifest`

After execution, the render manifest records:

- render-manifest ID/version and canonical `render_output_manifest_sha256`;
- exact `execution_package_hash` and actual program/command identity;
- execution status and exit code;
- output file path, format, size, SHA-256, page/frame count, pixel or page dimensions, and available DPI/color/font metadata;
- per-Figure/panel output mapping;
- plotting-data or image-region manifest hashes;
- warnings, missing outputs, unexpected outputs, and partial artifacts;
- prototype maturity and finality state.

The render-manifest hash excludes its own self-hash. It cannot be computed until execution evidence and output hashes are fixed. Non-zero exit status, missing required output, zero-byte output, unreadable format, unexpected overwrite, or output outside the run directory prevents a successful render state.

## Render inspection contract

Inspection dimensions remain separate.

### Deterministic inspection

May verify:

- file existence, size, hash, format, page/frame count, dimensions, and declared metadata;
- output membership and absence of undeclared paths;
- execution/program/input identity closure;
- requested Figure/panel file coverage;
- exact plotting-table and recipe-layer bindings;
- declared font embedding/editability signals when technically inspectable;
- presence of required machine-readable labels or panel IDs when deterministically recoverable;
- that a schema-valid render-inspection record exists, binds the exact render/output hashes, identifies the declared inspector/model/tool, and explicitly lists assessed and unassessed domains.

The deterministic validator cannot infer from an inspection JSON that a model actually viewed or cognitively inspected the render. A self-declared `performed` field is not inspection provenance. Actual model inspection is orchestration/model evidence in the minimum implementation. A later trusted `inspection_execution_receipt` may bind an invocation ID, render hash, inspector identity, timestamp, and inspection-record hash, but that interface is deferred and is not simulated by Phase 8B `0.1.1`.

### Model visual inspection

May propose findings about:

- missing, duplicated, clipped, crowded, or apparently reordered panels;
- visible mismatch between declared mappings and rendered axes, legends, colors, labels, units, or annotations;
- readability at the declared review size;
- color consistency, color-only critical distinctions, contrast, and grayscale risk;
- excessive visual emphasis, suppressed variation, hidden negative/control evidence, or misleading scale/ordering risk;
- obvious crop, splice, scale-bar, image-overlay, or assembly concerns visible in the supplied render;
- whether the prototype appears to implement the declared Figure story.

Model inspection must record inspected file hashes and visible evidence locators. It cannot confirm raw-image integrity, scientific representativeness, statistical appropriateness, copyright clearance, journal compliance, or author acceptance.

### Human/author inspection

Required for scientific meaning, representative-image validity, final layout/design acceptance, raw-image comparison where applicable, copyright/licensing decisions, final journal interpretation, and any submission/final state.

An unavailable render or unreadable page/image yields `not_assessed`; it must not be converted into a narrative pass.

## `render_inspection_record`

Each inspection record binds:

- inspection ID/version/hash and inspector class;
- exact render-manifest and file hashes inspected;
- tools/model/profile versions and inspection time;
- dimensions/domains actually inspected;
- findings with severity, rule ID, file/panel locator, evidence, and remediation route;
- explicit unassessed domains and reasons;
- whether a rerender is required;
- no-authority declaration for model/tool inspections.

Repeated inspections after a rerender create new records. A prior clean inspection cannot be reused after code, data, layout, output, or file-hash change.

Record/hash closure permits a domain to be structurally represented as assessed; it does not independently prove inspection occurrence. `prototype_verified` therefore requires declared orchestration/model evidence in addition to deterministic record validation, and its provenance limitation must remain explicit until a trusted inspection-execution receipt exists.

## Authority matrix

Phase 8B activates only authority paths that correspond to real execution states:

| Decision type | Required producer | Positive value/state | Permitted effect |
| --- | --- | --- | --- |
| `panel_freeze` | author | `approve` / `approved` | freeze exact governed panel content/version/hash |
| `figure_conclusion_freeze` | author | `approve` / `approved` | freeze exact bounded Figure conclusion |
| `layout_decision` | author | `approve` / `approved` | accept exact governed layout proposal |
| `design_acceptance` | author | `approve` / `approved` | accept exact Figure design version for the stated stage |
| `analysis_output_review` | authorized workflow or author as defined upstream | `approve`, `confirm`, or `resolve` / `approved` | admit exact supplied analysis output; never invent a result |

Every decision must resolve through the frozen external trust-root chain and bind subject ID, version, non-circular content hash, decision type, allowed decision value, and asserted state. `reject` or an incompatible asserted state cannot satisfy a positive transition. A model or calling workflow cannot mint author-only authority.

`finality_decision` remains declared by the frozen Phase 8 authority vocabulary but is inactive in Phase 8B. Any attempt to use it for a positive Phase 8B transition must fail with `authority:inactive_decision_type`. It must not be tested as an admissible positive transition unless a later contract first defines the Figure-capable Module 06 and author gates that make the governed target state admissible.

## States and transitions

Execution state is separate from Figure maturity and finality.

Permitted execution states are:

- `design_review_only`;
- `code_generated_unchecked`;
- `code_generated_validated`;
- `execution_not_run`;
- `execution_blocked`;
- `execution_failed`;
- `render_generated_uninspected`;
- `render_inspected_with_findings`;
- `prototype_verified`.

Allowed maturity progression is:

```text
ready_for_prototype
→ prototype_generated_unverified
→ prototype_verified
→ ready_for_qc
```

`prototype_generated_unverified` requires an actual render bound to a successful execution record. `prototype_verified` requires successful deterministic execution/output validation plus all contract-required declared inspections, with no blocking mismatch. `ready_for_qc` means ready for a separately implemented Figure-capable Module 06/human review; it is not a claim that such review has passed.

Phase 8B outputs remain `design_candidate` or `author_review_required`. They cannot self-assert `submission_candidate` or `author_approved_final`.

## Iteration and stop rules

An inspection finding may lead to a bounded `realization_correction` only when the change makes code conform to the admitted design without changing any admitted business-artifact meaning. Each changed program creates a new program hash and execution manifest; each rerender creates a new render manifest and inspection record.

Any change to a Figure Card, Figure Contract, Source Data Manifest, Plot Recipe, authority decision, analysis output, source binding, or trusted collection must return through Phase 8A before execution.

Stop with a structured blocker when:

- admission hashes or trust-root bindings do not close;
- package maturity is below `ready_for_prototype` for code/execution;
- backend capability or required dependency is unavailable;
- the requested render requires undeclared data, statistics, mapping, transformation, crop, or author decision;
- generated code cannot preserve source IDs, units, ordering, or annotation provenance;
- static validation fails or execution exits unsuccessfully;
- output is missing, unreadable, path-escaping, overwritten, or hash-inconsistent;
- a render appears inconsistent with the admitted Plot Recipe;
- image-integrity, copyright, journal, or scientific questions require unavailable human/source evidence;
- the user requests a final/submission claim before the external gates exist.

The proper response is an exact blocker and focused query, not repeated aesthetic tweaking or scientific improvisation.

## Figure QC and Module 06 handoff

The Phase 8B `figure_qc` uses schema/business-artifact type `figure_qc` but has a distinct Phase 8B artifact ID, version, and non-circular `figure_qc_sha256`. It must never reuse the Phase 8A QC artifact ID. Its required `upstream_phase8a_qc_ref` binds the exact Phase 8A QC artifact ID, version, design-package hash, and `figure_qc_sha256` established by the fresh admission run.

The Phase 8B `figure_qc` must also bind:

- Phase 8A design-package and QC hashes;
- execution-manifest and program hashes;
- render-output manifest and output-file hashes;
- render-inspection record hashes;
- backend, environment, ruleset, journal/reporting profile, and style-profile identities actually assessed;
- separate deterministic, execution, visual/model, human, statistics, image-integrity, copyright, accessibility, and journal statuses;
- unresolved findings and exact handoff routes.

References named `phase8a_figure_qc_sha256` and `phase8b_figure_qc_sha256` must remain explicit; an unqualified QC hash is insufficient when both records are in scope. The Phase 8B QC hash excludes only its own self-hash field and cannot enter any upstream execution or render hash.

Until a Figure-capable Module 06 extension is separately contracted and implemented, `ready_for_qc` means only that the package is prepared for that later handoff. Phase 8B must not report Module 06 Figure QC as executed or passed.

## Required implementation layout

A later minimum implementation should be isolated from the frozen Phase 8A candidate:

```text
05_scientific-figure-designer/
├── DEVELOPMENT_CONTRACT.md
├── PHASE8B_DEVELOPMENT_CONTRACT.md
├── IMPLEMENTATION_REVIEW.md
├── TEST_SUMMARY.md
├── candidate/                 # frozen Phase 8A; do not modify
└── phase8b-candidate/
    ├── schemas/
    │   ├── phase8a-admission-receipt.schema.json
    │   ├── backend-environment-profile.schema.json
    │   ├── prototype-execution-authorization.schema.json
    │   ├── design-revision-proposal.schema.json
    │   ├── bounded-program-plan.schema.json
    │   ├── prototype-execution-manifest.schema.json
    │   ├── render-output-manifest.schema.json
    │   ├── render-inspection-record.schema.json
    │   └── figure-qc-phase8b.schema.json
    ├── scripts/
    │   ├── validate_phase8b_admission.py
    │   ├── probe_backend_environment.py
    │   ├── generate_restricted_python.py
    │   ├── validate_generated_program.py
    │   ├── run_prototype.py
    │   ├── inspect_render_metadata.py
    │   └── validate_phase8b_package.py
    └── tests/
        ├── fixtures/
        └── test_phase8b_contract.py
```

Names may receive narrow review-driven changes. No backend package, copied FigureYa module, plotting helper collection, generated program, render, or full `SKILL.md` should be added before the contract is reviewed and an implementation task requires it.

## Required positive fixtures for a later implementation

At minimum:

1. A design-review-only fixture that proposes a presentation/layout change without mutating the admitted package and correctly routes material acceptance back through authority and Phase 8A.
2. A synthetic two-panel quantitative `ready_for_prototype` package for which the admission script reruns frozen Phase 8A, emits a fresh admission receipt, probes one actual Python environment, generates a bounded-program plan and restricted Python program, obtains an exact separate execution authorization, preserves variables/units/group order/supplied annotations, and produces hashed non-final vector and raster prototypes plus plotting-data output.
3. A successful rerender after a presentation-only code correction, with distinct program/execution/render/inspection hashes and no change to the admitted design package.
4. A prototype whose metadata checks pass but whose model visual inspection yields a routed non-blocking or blocking finding without claiming scientific or author authority.

Only one actually available backend is required for the minimum implementation. R/Python parity, FigureYa execution, real scientific data, and journal-specific export testing are separate later coverage.

## Required deterministic negative matrix for a later implementation

Each case requires a stable case ID, expected issue code, and executable test binding. The later validator must reject or block, at minimum:

### Admission and trust

- Phase 8A package below `ready_for_prototype` used for code/execution;
- supplied old/self-declared Phase 8A QC or admission receipt accepted without rerunning the frozen Phase 8A validator;
- fresh Phase 8A recomputation result, design-package hash, or QC hash differs from the Phase 8B admission binding;
- stale or mismatched design-package, Phase 8A QC, trust-root, source, analysis, or authority hash;
- unresolved execution-critical Phase 8A blocker;
- mutated five-artifact package used without Phase 8A revalidation.

### Code and mapping

- generated layer lacks exact Plot Recipe/source-variable binding;
- arbitrary handwritten Python/R, generator/hash mismatch, bounded-program operation outside the allowlist, or generated code block without a plan binding;
- AST contains `eval`/`exec`, dynamic import/reflection, undeclared helper code, subprocess/shell, socket/network, installer, arbitrary filesystem discovery, or unsupported syntax;
- hidden filter, exclusion, transformation, aggregation, crop, or contrast change;
- group/comparison/facet order, unit, palette semantic, or statistical annotation drift;
- new inferential statistic, preferred-result search, or model-selected representative field;
- code reads an undeclared input, writes outside the run directory, overwrites a source/output, downloads data, or installs packages;
- stochastic visual operation lacks a declared seed;
- syntax/static-check result falsely represented as execution success.

### Backend and execution

- unavailable requested backend silently replaced;
- model/self-declared backend profile accepted without the deterministic probe, or probe-script/profile identity mismatch;
- backend profile/version differs from the runtime used;
- execution manifest self-certifies caller acceptance, or external authorization mismatches the execution/program/backend/input/output/command hashes;
- FigureYa-like module selected despite incompatible input shape or statistical semantics;
- program hash/command differs from the admitted execution manifest;
- non-zero exit, missing output, zero-byte output, partial output, or undeclared output represented as success;
- prior execution/inspection result reused after code, configuration, input, or output mutation.

### Render, QC, and authority

- render-output hash, dimension, format, panel coverage, or plotting-data binding mismatch;
- render-inspection record lacks exact inspected hashes, inspector identity, or explicit assessed/unassessed domains;
- self-declared `performed` field treated as deterministic proof that visual inspection occurred;
- unavailable/unreadable render marked visually passed;
- model inspection represented as scientific, image-integrity, copyright, journal, or author approval;
- author-only panel/conclusion/layout/design decision self-issued, wrong-role, `reject`, stale-subject, or wrong asserted state;
- any `finality_decision` used to advance a positive Phase 8B state instead of failing with `authority:inactive_decision_type`;
- prototype self-promoted to `submission_candidate` or `author_approved_final`;
- Module 06 Figure QC claimed passed before the extension exists;
- circular execution/render/QC self-hash or downstream hash bound to a different upstream package.

## Deferred model/human forward-review matrix

The following are not deterministic pass claims and require model/human fixtures or real review evidence:

- whether the Figure story is scientifically persuasive without bias;
- whether visual prominence accurately reflects evidence strength and uncertainty;
- whether the chosen plot archetype is the best scientific communication choice among valid alternatives;
- whether labels, legends, density, whitespace, and panel balance work at the intended publication size;
- whether color accessibility and grayscale distinguishability are adequate by actual perception;
- whether an approved representative field is scientifically representative;
- whether image processing is acceptable against raw source material;
- whether a design is too similar to a published Figure or legally reusable;
- whether a journal/reporting profile was interpreted completely and remains current;
- whether the rendered prototype should be manually recreated, revised, or accepted by the author.

Model findings must cite inspected render hashes and visible evidence. Human-unavailable domains remain `not_assessed`.

## Implementation acceptance conditions

A later Phase 8B implementation is eligible for freeze only when:

- it consumes but does not modify the frozen Phase 8A candidate;
- admission directly invokes the frozen Phase 8A `0.1.2` validator with the exact package, external root, and caller-held root hash, then binds a fresh validator-produced receipt;
- backend/environment capability comes from the deterministic probe and execution authority comes from a separate exact-hash-bound interface;
- operating modes and admission gates are executable and fail closed;
- design proposals cannot bypass Phase 8A revalidation;
- scientific/source/statistical revision requests cannot carry model-generated executable after-values;
- realization corrections are mechanically separated from design changes;
- minimum code execution is restricted to generator-owned bounded-program plans and AST-whitelisted Python, without claiming arbitrary-code safety;
- code generation is traceable from every rendered layer through the bounded plan to the Plot Recipe and admitted source/analysis identities;
- backend selection is capability-checked and never silently substituted;
- generated code cannot install, fetch, overwrite, escape paths, or invent scientific/statistical content;
- execution, render, inspection, and QC hashes follow the non-circular lifecycle and are mutation-tested;
- positive fixtures pass using synthetic or explicitly authorized bounded inputs;
- every deterministic negative case has an exact executed binding;
- an actual successful prototype run is distinguished from code-only/static checks;
- render inspection records what was declared inspected and what remained unassessed without treating self-declaration as deterministic proof of cognitive inspection;
- Phase 8A and Phase 8B Figure-QC records have distinct artifact identities and explicit non-circular upstream binding;
- no output claims Figure-capable Module 06, author, journal, copyright, image-integrity, or submission approval;
- implementation/review/test records state exact runtime, backend, fixtures, skipped checks, and failures;
- the candidate remains under `result`, uninstalled, and separate from the frozen Phase 8A candidate.

## Deferred work

This contract intentionally defers:

- implementation of the Phase 8B schemas, scripts, tests, and backend adapters;
- real-paper and real-data prototype testing;
- R, arbitrary user-supplied Python, R/Python parity, and broad plot-family coverage;
- FigureYa module fetching or execution;
- package installation or environment creation;
- remote/HPC prototype execution;
- inferential/statistical analysis workflows;
- discipline-specific experiment profiles;
- current journal/reporting profile packs;
- Figure-capable Module 06 implementation;
- automated copyright or image-forensics approval;
- author final recreation/acceptance and submission packaging;
- full `SKILL.md`, installation, activation, or movement outside `result`.

This Phase 8B `0.1.1` contract is frozen after the reviewed admission/execution-provenance amendment. No further contract hardening is required unless implementation exposes a genuine internal contradiction. The next stage is the minimum Phase 8B candidate defined here; R/Python parity, FigureYa execution, real scientific data, journal packs, Figure-capable Module 06, installation, activation, and HPC execution remain outside that minimum.
