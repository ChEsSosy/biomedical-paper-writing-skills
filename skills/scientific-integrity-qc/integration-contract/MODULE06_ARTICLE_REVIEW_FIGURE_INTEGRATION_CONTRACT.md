# Module 06 — Article, Review, and Figure Integration Contract

## 1. Candidate status and purpose

- Phase: `9 Item 6 — Module 06 integration contract`
- Contract version: `0.1.2`
- State: `CANDIDATE / REVIEW REQUIRED / NOT FROZEN`
- Derived integration/package candidate: **source review required**
- Installed or activated: **no**

This derived contract rebinds the exact Module 03 and 04 package identities after the accepted A/B/C1 guidance update. It preserves the existing Article, Review, and Figure admission routes and the frozen Phase 5a.1 minimum text-comparison core. The updated integration package is a separate candidate requiring independent source review before installation.

The machine-readable `module06-integration-interface-registry.json` is authoritative for exact interface, version, package, artifact-class, and state names. This prose contract defines their semantics and stop rules.

## 2. Historical baselines and current producer candidates

| Component | Exact admitted identity |
|---|---|
| Phase 9 packaging/integration contract | `0.1.1`; SHA-256 `7fc12671b129475d12de69915272f0a5da4180468180043b804d9acc5ab6f7ff` |
| Module 06 minimum-gate contract | `0.1.3`; SHA-256 `f7c8360ccc11e4cbcd5d906bbb1ae9b37ab9367d160467685aaa650afa8f3a3e` |
| Module 06 minimum deterministic core | ruleset `0.1.1`; validator `0.1.0`; 46-file tree SHA-256 `cb03850ca3e8ff3c70f9d95c658aa53aaf34e43adcdd704bce750c08e43ed685` |
| Module 03 guidance package candidate | `article-polisher` package `0.1.7`; manifest SHA-256 `c517643b4c9ea3bb5765314b4d07e927c4a29ddebff0dcd5d1c1584f508e7074` |
| Module 04 guidance package candidate | `review-architect-polisher` package `0.1.7`; manifest SHA-256 `60a734ee8e7f32f543210e40fac72ee797a781499eb8997342eaaf5e6dd04f08` |
| Module 05 package | `scientific-figure-designer` package `0.1.0`, build `0.1.2`; manifest SHA-256 `897e31b93d8c6a997d3308b0dcf5cb5c4d4d3d7f3a351cc04f15ec6cee6a2429` |
| Historical Item 5 integration manifest | schema `0.1.1`; canonical SHA-256 `94eb7f42598a352f708b6a7c6a4771d0a66f686e8235b33ea4ad8849de24333b` |

No frozen baseline file may be edited or relabelled to implement this contract. The derived integration layer and complete Module 06 Skill package are separate review candidates with their own versions and identities.

## 3. Exact interfaces

The three consumer admission interfaces are independent and cannot substitute for one another:

| Route | Frozen producer interface | Module 06 consumer admission |
|---|---|---|
| Original Article revision | `module03_revision_qc_bundle` `0.1.2` | `module06_article_revision_admission` `0.1.0` |
| Review revision | `phase7b_revision_bundle` `0.1.0` | `module06_review_revision_admission` `0.1.0` |
| Figure design/prototype QC | `module05_figure_qc_bundle` `0.1.0` | `module06_figure_qc_admission` `0.1.0` |

The future common output interface is `module06_integrity_qc_bundle` `0.1.0`. It contains one route-specific admission receipt, one exact gate report, all findings, and the route-dependent evidence listed below. It is not a seventh orchestration artifact and grants no authority.

Ambiguous or mixed document/package type is rejected. Article content cannot enter the Review route, Review content cannot enter the Article route, and text revision evidence cannot masquerade as Figure evidence.

## 4. Common admission envelope

Every call must provide an external, caller-controlled admission request containing:

- exactly one route name and consumer interface/version;
- the exact producer Skill name, package version, package-manifest canonical SHA-256, producer interface, and interface version;
- local package-relative paths for every supplied artifact;
- artifact class, ID, version, canonical SHA-256, status, and document/manuscript identity where applicable;
- a separate caller-held expected SHA-256 for every package inventory, trust root, permission/authorization file, and artifact presented as external authority;
- the requested QC scope and required domains;
- no embedded assertion that admission, QC, author review, or scientific validity has already passed.

The future consumer must recompute file and canonical artifact hashes, package-inventory self-hashes, path containment, interface/version equality, cross-artifact identity equality, and the producer validation result. A supplied old validation result, copied `valid` field, filename, top-level `approved` string, or caller description cannot replace recomputation.

Paths must resolve inside the declared package or invocation root. Missing, stale, duplicate, extra, mismatched, path-escaping, or unsupported artifacts fail closed. The consumer must not search sibling development directories to repair a missing package dependency.

## 5. Article revision admission

`module06_article_revision_admission` `0.1.0` accepts only:

- producer package and interface exactly matching Section 3;
- `document_type: original_article` on the exact source and candidate manuscripts;
- exact source/candidate IDs, versions, and SHA-256 values consistently repeated by all supplied artifacts;
- `change_manifest` `0.1.1`;
- `author_query_list` `0.1.0`;
- `revision_lineage_map` `0.1.0` with origin `deterministic_patch_layer`;
- `article_polisher_change_inventory` `0.1.1`;
- `article_polisher_patch_application_receipt` `0.1.0`;
- the exact referenced Module 03 `revision_contract` and caller-held expected contract hash required by the frozen minimum gate;
- a fresh Module 03 package validation with no issue and `ready_for_independent_qc: true`.

The handoff artifact classes remain those frozen for H03: change manifest, author-query list, lineage map, and exact source/candidate identities. The revision contract, inventory, application receipt, and fresh validator output are required consumer dependency/provenance closure; they are not new producer business outputs.

`machine_proposed`, `blocked`, incomplete, stale, hash-mismatched, Review-routed, non-deterministic-lineage, or not-ready producer states are rejected. `author_review_required` on the author-owned candidate is preserved; it is not a reason to mint approval or skip QC.

After admission, a deterministic Article adapter may project the exact ordered paragraph/sentence text and stable unit locators into the existing UTF-8/Markdown comparison interface. The projection receipt must bind every source/candidate unit and projected byte hash; omitted, duplicated, reordered, joined, split, or normalized text not declared by the frozen lineage is a blocker. The frozen Phase 5a.1 comparison gate then runs without semantic rule changes.

## 6. Review revision admission

`module06_review_revision_admission` `0.1.0` accepts only:

- producer package and interface exactly matching Section 3;
- `document_type: review_article` on the exact source and candidate manuscripts;
- exact manuscript/source/candidate identities consistently bound across the closure;
- `review_revision_permission` `0.1.0` and separate caller-held expected permission SHA-256;
- `review_revision_proposal` `0.1.0`;
- `review_change_manifest` `0.1.0`;
- `review_author_query_list` `0.1.0`;
- deterministic `review_revision_lineage_map` `0.1.0`;
- `review_protected_change_inventory` `0.1.0`;
- `review_patch_application_receipt` `0.1.0`;
- `review_package_validation_result` `0.1.0`;
- the exact Phase 7A closure actually referenced by changed units;
- a fresh Module 04 package validation with no issue and producer state `ready_for_independent_qc`.

The permission/proposal and Phase 7A records are dependency/authority closure for independent consumer verification; Module 06 does not become their producer or scientific judge. Internally pending or unresolved authority cannot be promoted by a top-level status.

An exact deterministic Review adapter must create the same kind of complete text/unit projection receipt required for Article. The frozen Phase 5a.1 text-preservation rules may then run on the projected Review source/candidate. Review-specific evidence sufficiency, synthesis balance, retrieval completeness, bibliographic truth, consensus adjudication, formal systematic-review compliance, and meta-analysis remain unimplemented. They must be recorded as `not_assessed` or `unassessable`, never `passed`.

## 7. Figure admission

`module06_figure_qc_admission` `0.1.0` accepts only the frozen Module 05 package/interface in Section 3 and has two non-interchangeable variants.

### 7.1 Phase 8A design variant

Required producer artifact classes are:

- `design_package_manifest` `0.1.0`;
- Phase 8A `figure_qc` `0.1.0`.

The exact five-artifact design package—`source_data_manifest`, all `figure_card` records, `figure_contract`, `plot_recipe`, and `figure_qc`, each at `0.1.0`—plus external trusted-input and caller-held expected hashes must be available so the consumer can freshly invoke the frozen Phase 8A `0.1.2` validator. The manifest, components, trusted bindings, design-package hash, Figure-QC identity/hash, document type, and declared maturity must match.

`readiness_gate: pass_for_declared_maturity` is admitted for identity/closure QC. `author_review_required` is admitted only as degraded and remains author-review-required. `blocked`, stale, internally inconsistent, mixed Article/Review, or trust-mismatched packages are rejected.

### 7.2 Phase 8B prototype variant

In addition to the exact Phase 8A closure, require:

- freshly generated `phase8a_admission_receipt` `0.1.0`;
- `prototype_execution_result` `0.1.0`;
- `render_output_manifest` `0.1.0`;
- one or more `render_inspection_record` `0.1.0` records;
- Phase 8B `figure_qc` `0.2.0` with an exact `upstream_phase8a_qc_ref`;
- the bound Phase 8B execution/authorization dependencies needed for a fresh frozen Phase 8B `0.1.1` package validation.

`readiness_gate: prepared_for_future_figure_qc` is admitted for identity/closure assessment. `author_review_required` is degraded. `blocked`, failed/missing execution, stale render hashes, wrong Phase 8A parent, wrong backend/authorization identity, or incomplete inspection binding is rejected.

`prototype_generated_unverified` is preserved exactly and can never be promoted by Module 06. A schema-valid or model-written inspection record does not prove that cognitive inspection occurred. A declared `ready_for_qc` maturity likewise does not prove Figure validity.

## 8. Admission, assessment, and authority are separate

The future integration layer must keep three dimensions separate:

1. `admission_state`: `accepted`, `accepted_degraded`, or `rejected`;
2. per-domain `assessment_state`: `passed`, `failed`, `unassessable`, `not_assessed`, or `not_applicable`;
3. `gate_outcome`: `pass`, `pass_with_warnings`, `fail`, or `unassessable`.

Admission success proves only exact identity, version, hash, state, path, and dependency closure. It does not imply any assessment passed.

A domain may be `passed` only when a named, versioned, actually executed deterministic or trusted external check covers that domain for the exact inputs. Missing or unimplemented checks must be `unassessable` or `not_assessed`; they cannot become `passed` from zero findings. `not_applicable` requires an explicit route/scope rule, not mere absence of data.

A route-scoped Article or Review text-preservation report may be `pass` when every domain required by that declared narrow scope actually executed and no blocker/error remains. Such a pass is not holistic scientific, bibliographic, journal, or publication validation. If the caller requests an unimplemented domain, or a route-required domain cannot run, the gate is `unassessable` or `fail` as appropriate.

The first Figure integration implementation is identity/state/handoff closure only. Because scientific meaning, raw-image integrity, statistical appropriateness, visual effectiveness, accessibility by cognitive inspection, copyright clearance, and journal compliance are unimplemented, a Figure route cannot emit clean `pass`; successful identity admission ends as `unassessable` with human review required unless a later separately frozen trusted interface implements every required domain.

## 9. Blocker propagation and terminal states

Admission and gate terminal states are:

- `blocked`: required input is missing, stale, mismatched, unsafe, or producer validation fails; no clean QC bundle is eligible for downstream promotion;
- `qc_complete_author_review_required`: all checks required by the declared implemented scope executed and the exact report was emitted; author review remains required regardless of pass/fail;
- `qc_unassessable_author_review_required`: admission may be exact, but at least one required assessment could not run or is unimplemented;
- `rejected`: route/interface/package type is unsupported or contradictory.

Any open producer blocker, consumer blocker, required unassessable domain, open `blocker`/`error` finding, or unresolved required author query prevents clean promotion. `pass_with_warnings` is not a clean pass and requires human review. Changing an input, decision, exception, or warning disposition requires a new exact invocation and report; old findings cannot be edited into a pass.

## 10. Output bundle and gate report

`module06_integrity_qc_bundle` `0.1.0` must bind:

- route and exact consumer interface/version;
- exact producer package/interface and all admitted artifact identities/hashes;
- `module06_integration_admission_receipt` `0.1.0`;
- `module06_gate_report` `0.1.0`;
- all `qc_finding` `0.3.0` records;
- exact validator, ruleset, adapter, schema, and package identities;
- per-domain requested, implemented, execution, and assessment states;
- blocker propagation and terminal state;
- `human_review_required` and limitations;
- explicit `author_approval_claimed: false`, `scientific_truth_claimed: false`, and `automatic_repair_performed: false`.

Article and Review bundles also retain exact `comparison_manifest` `0.1.1`, source/candidate `preservation_snapshot` `0.1.1`, projection receipt, and `qc_report` `0.1.0`. Figure bundles retain exact Phase 8A/8B producer references and coverage records; they must not fabricate text snapshots or raw-image findings.

No Module 06 output can create author approval, modify an upstream artifact, certify scientific truth, or initiate an automatic rewrite/rerender loop.

## 11. External authority boundary

Caller acceptance authorizes only the scoped validation invocation. It is not author approval, scientific approval, or evidence verification.

Trusted author decisions, revision permissions/contracts, Figure authority records, execution authorizations, and future inspection receipts must be separately supplied, hash-bound, externally expected by the caller, and internally consistent. `calling_workflow`, a model, a generated admission request, a manifest, or Module 06 cannot mint or widen them.

Module 06 may verify that an authority record exactly governs the supplied subject and state. It must not decide whether the author should approve, infer missing approval, reinterpret scientific content, or treat approval as scientific truth.

## 12. Minimum implementation authorized only after contract freeze

After independent review freezes this contract, Item 6 may create a separately versioned additive layer containing only:

- three route-specific deterministic admission validators;
- deterministic Article and Review structured-text projection plus receipts;
- one unified gate-report/output-bundle schema layer;
- the frozen Phase 5a.1 core copied or vendored byte-identically with a source inventory;
- the exact frozen producer validators/schemas needed for fresh admission;
- focused positive and fail-closed tests for routing, stale/hash/package mismatches, state propagation, authority separation, text projection completeness, and Figure unimplemented-domain handling;
- a concise `scientific-integrity-qc` Skill entrypoint and package inventory.

The implementation must not edit the Phase 5a.1 candidate, broaden semantic rules, add scientific judgment, implement raw-image/statistical/journal/copyright QC, or activate/install the Skill.

## 13. Required contract-review questions

Independent review should determine:

1. Are all three producer and consumer interface identities/versions exact and route-separated?
2. Are runtime artifact, package, trust, permission, and authority identities recomputed rather than trusted from labels?
3. Can Article/Review projection omit or normalize text without blocking?
4. Can an unimplemented or missing assessment domain become `passed` through zero findings?
5. Can Figure identity closure be confused with scientific, visual, statistical, copyright, or journal validity?
6. Do producer blockers, unresolved required queries, unassessable checks, and Module 06 blockers prevent clean promotion?
7. Can caller/model/workflow state mint author approval or trusted inspection evidence?
8. Does the contract preserve the frozen Phase 5a.1 core and defer implementation/package work until approval?

## 14. Stop condition

Contract candidate `0.1.2` derives from the frozen `0.1.1` contract and changes only the exact admitted identities of the new Module 03 and 04 packages. The `0.1.1` source and review evidence remain preserved in the Phase 9 result tree. This new contract and its matched integration/package candidate remain `NOT FROZEN / NOT INSTALLED` until independent review. Interface names and versions, closure checks, scientific assessment boundaries, the frozen core, and fail-closed behavior remain unchanged.
