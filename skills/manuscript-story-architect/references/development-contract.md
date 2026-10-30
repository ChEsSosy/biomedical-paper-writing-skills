# Manuscript Story Architect — Development Contract Candidate

## Candidate status

- Target module: `02_manuscript-story-architect`
- Contract version: `0.1.1`
- Skill candidate version: `0.1.2`
- Scope: Original Research Article story reconstruction
- Full Skill implemented: **yes, review candidate only**
- Installed or activated: **no**
- `01_style-and-structure-distiller` real-paper pilot: **pending**
- HPC or external services used: **no**

This package preserves the approved artifact contract and contains a full review candidate with `SKILL.md`, routed references, deterministic scripts, and synthetic tests. It remains inside `result` and does not draft or polish manuscript prose automatically.

## Purpose

Transform author-owned manuscript material into an auditable question–claim–evidence–interpretation–boundary–validation plan without creating scientific facts, selecting a scientific position, or silently strengthening a claim.

The module may reorganize already supplied material into reviewable structural proposals. Only the author can approve the central question, take-home message, interpretation, evidence relation, material reordering, or final manuscript plan.

## Required inputs

1. An Original Article manuscript or structured author notes with stable source identities.
2. Central question and principal findings that are author supplied or explicitly stated in an author-provided manuscript/notes and extractable with stable locators. Source-extracted candidates remain author-review-required and are not inferred from results or data patterns.
3. Author-supplied novelty scope and author-confirmed frozen scientific elements. Novelty is never inferred from manuscript promotion language, the corpus, literature, data, or a structure profile.
4. Results, tables, figures, data summaries, or evidence records with source locators.
5. Methods and experiment metadata with one or more experiment labels.
6. Explicit unknown, conflicting, missing, or not-reported states; absence must not be converted into invented content.
7. Optional deterministic Article `structure_profile` from `01_style-and-structure-distiller`.
8. Optional reviewed Article `architecture_profile` from `01_style-and-structure-distiller`, when that later interface exists.
9. Optional target-journal inputs: `target_journal`, `target_journal_profile`, `journal_instructions_provenance`, and `article_subtype`.

The two profiles are descriptive inputs, not scientific authority or mandatory templates. Their absence is a declared degraded mode, not a blocker. When the input is an existing manuscript, the module first records its reverse outline. For structured notes without an existing manuscript structure, it records the explicit skip reason instead.

## Outputs locked by this contract

### `claim_evidence_map`

Records author-owned, explicitly source-stated, or architect-restated claims; evidence records; explicit claim–evidence relations; support status; scientific scope; causal/mechanistic ceiling; locators; unresolved risks; and author decisions.

`claim_origin` is restricted to `author_supplied`, `explicitly_stated_in_author_source`, or `architect_proposed_restatement`. An architect-proposed restatement may only reorganize or narrow an existing proposition, remains author-review-required, and must never be represented as `model_inferred_from_data`.

Schema: `schemas/claim-evidence-map.schema.json`.

### `interpretation_card`

Separates observation, interpretation, identified boundary, alternative explanations, abstract `validation_needs`, and any separately authorized `proposed_validation_experiments`. Alternative explanations must carry provenance and remain author-review-required unless the author supplied or approved them.

The default story-planning workflow may describe what evidence category is missing, but it must not invent a concrete experiment. A concrete proposed experiment is admissible only when author supplied or explicitly requested as a separate task, with source locators and approval state.

Schema: `schemas/interpretation-card.schema.json`.

### `manuscript_plan`

Defines provenance-bearing `story_anchors`, current-structure assessment, section goals, paragraph roles, claim/evidence assignments, Figure sequence, unassigned-evidence audit, frozen elements, gaps, reviewer risks, and author-decision points. It contains planning statements, not rewritten manuscript paragraphs.

`story_anchors` contains the central question, take-home message, novelty scope, key claim IDs, and key boundary IDs. Each textual anchor carries provenance, locators, and an approval state. Novelty provenance is restricted to author supplied or explicitly author approved.

Schema: `schemas/manuscript-plan.schema.json`.

## Workflow contract

```text
author-owned source material
→ inventory and freeze scientific anchors
→ reverse-outline the current manuscript, or record the notes-only skip reason
→ claim/evidence map with source locators
→ interpretation cards with explicit boundaries
→ provenance-bearing story anchors and evidence-assignment audit
→ one or more structural plan candidates
→ deterministic structural and cross-link checks
→ author review and selection
→ author-approved manuscript plan
```

An `author_review_required` artifact must never be represented as approved. Approval of one claim, relation, interpretation, paragraph move, or plan does not imply approval of another.

## Journal adaptation boundary

A target-journal profile may influence only structure, emphasis, compression, and order. It must not change claims, evidence strength, causality or mechanistic ceilings, treatment of negative/counter evidence, or novelty scope. Journal instructions and their provenance are optional inputs; the contract records `scientific_authority: false` whenever journal adaptation is used.

## Evidence assignment audit

Every evidence record is ultimately either assigned in the plan or retained in the unassigned-evidence audit. An unassigned record must carry one of these explicit reasons: `redundant_validation`, `supplement_candidate`, `outside_current_scope`, `negative_or_counter_evidence_retained`, `author_excluded`, or `unresolved`. Narrative convenience is not a valid reason to hide evidence.

## Experiment routing

Evidence labels are multi-valued. The minimum vocabulary is:

`computational`, `cell`, `molecular`, `animal`, `omics`, `imaging`, `clinical_human`, `structural_biophysical`, and `other`.

Experiment labels route later reporting and claim-ceiling checks; they do not determine scientific meaning by themselves. The future full Skill may add experiment-specific references, but those references must share the same artifact contracts.

## Scientific boundaries

The module must not:

- invent a claim, result, control, replicate, statistic, mechanism, limitation, citation, or validation experiment;
- infer novelty or a scientific proposition from the corpus, literature, data pattern, target-journal profile, or upstream structure profile;
- convert missing evidence into prose that implies the evidence exists;
- resolve conflicting evidence or choose among scientific interpretations for the author;
- raise associative evidence to causal evidence, in-vitro evidence to in-vivo relevance, or model evidence to clinical relevance;
- remove negative results, counterexamples, uncertainty, or limitations to improve narrative flow;
- use a corpus-derived language or structure profile as scientific authority;
- use a target-journal profile as authority over claims, evidence strength, causality, negative evidence, or novelty;
- turn an abstract validation need into a concrete experiment proposal during the default workflow;
- start Article polishing automatically or modify the manuscript during story planning;
- process Review Article architecture, which belongs to `04_review-architect-polisher`.

## Deterministic checks implemented in the candidate

The candidate validators check at least:

1. unique claim, evidence, link, card, boundary, section, paragraph, Figure-sequence, and decision IDs, plus resolvable artifact/claim/evidence/card/boundary references used by the plan;
2. every core claim has at least one locator and an explicit support status;
3. every evidence record has at least one locator and an experiment label;
4. every claim–evidence relation references existing IDs;
5. `supported` claims have a `supports` relation, while `partially_supported` claims have a `supports` or `partially_supports` relation;
6. every interpretation has an identified boundary and an approval state, and every evidence ID on a card has an explicit relation to that card's claim;
7. claims use only the three admitted `claim_origin` states, and architect restatements remain reviewable;
8. every story anchor has provenance, locators, and approval state; novelty is never architect inferred;
9. an existing manuscript has a reverse outline, while notes-only input has an explicit skip reason;
10. every paragraph plan links to its section goal and declares its claim/evidence IDs; each used evidence ID has an explicit relation to at least one claim declared by that paragraph;
11. every Figure sequence item links to known claims and evidence; each used evidence ID has an explicit relation to at least one claim declared by that Figure;
12. every evidence record either appears in an actual paragraph/Figure assignment and the assigned audit, or appears only in the unassigned-evidence audit with a reason;
13. journal and upstream profiles remain explicitly non-scientific inputs;
14. concrete experiment proposals have an admitted author-origin or separate-task origin;
15. unresolved blockers remain visible in the approval summary;
16. an `author_approved` plan has no pending nested anchor, section, paragraph, Figure, evidence-audit, gap, decision, claim-map, or interpretation-card approval state and no unassigned evidence whose reason remains `unresolved`;
17. every key claim is represented by at least one interpretation card referenced by the plan, and every key boundary comes from a referenced card;
18. an artifact cannot become `author_approved` through schema validation alone.

Schema validation establishes structure only. It cannot prove that a scientific claim is true, that evidence actually supports a claim, or that the author approved the content.

## Handoffs

- Optional inputs from `01`: deterministic Article `structure_profile` and, when available, reviewed Article `architecture_profile`.
- Required future output to `03`: an author-approved `manuscript_plan` for Deep restructuring; `03` must not infer approval.
- Output to `05`: Figure sequence brief linked to claim and evidence IDs.
- Output to `06`: complete claim/evidence/interpretation chain plus unresolved risks.

## Candidate acceptance criteria

This candidate is acceptable for review when:

- all four schema files parse as JSON;
- positive fixtures validate;
- negative fixtures fail on the intended schema boundaries;
- the dependency-free validator rejects unsupported schema keywords;
- cross-artifact IDs, declared support states, evidence assignment, section coverage, and approval consistency have negative tests;
- the reverse-outline renderer emits planning fields and IDs without copying source prose;
- no real paper, manuscript, scientific result, or reusable prose is packaged;
- the full Skill remains uninstalled and inactive.

## Implemented after contract approval

- final `SKILL.md` trigger and routing language;
- deterministic claim-map and cross-artifact validators;
- reverse-outline renderer and section-coverage checker;
- routed computational, cell, molecular/structural, animal, omics, imaging, clinical, and fallback experiment profiles;
- positive and negative synthetic artifact/script tests.

## Deferred until candidate review

- real manuscript pilot;
- model-level forward testing on the four `test_article` papers;
- integration with the minimal `06_scientific-integrity-qc` gate.
