---
name: manuscript-story-architect
description: Reconstruct the auditable scientific story of an Original Research Article from author-owned drafts, notes, figures, and evidence. Use for section or paragraph architecture, claim–evidence mapping, Results–Discussion boundaries, interpretation cards, and Figure sequencing; do not use for prose polishing or Review Articles.
metadata:
  short-description: Build an auditable Original Article story plan
---

# Manuscript Story Architect

Build an author-reviewable plan before manuscript rewriting. Preserve the supplied science while making the question–claim–evidence–interpretation–boundary chain explicit.

This Skill produces planning artifacts. It does not polish manuscript prose, approve scientific choices, or silently continue into another Skill.

## Non-negotiable boundaries

- Use only author-owned or explicitly supplied source material. Give every claim, evidence record, anchor, and journal instruction a stable locator.
- Never invent a result, mechanism, control, replicate, statistic, citation, limitation, novelty statement, or validation experiment.
- Novelty must be author supplied or explicitly author approved. A corpus, target-journal profile, literature pattern, or structure profile is never novelty evidence.
- Keep observation, interpretation, boundary, alternative explanation, and validation need distinct.
- Do not resolve conflicting evidence or choose a scientific interpretation for the author.
- Do not raise associative evidence to causal evidence, in-vitro evidence to in-vivo relevance, model evidence to clinical relevance, or a computational prediction to experimental validation.
- Retain negative, null, conflicting, and out-of-scope evidence in the assignment audit. Narrative convenience is not an exclusion reason.
- Treat upstream structure/architecture profiles and target-journal profiles as descriptive, non-scientific inputs.
- Do not modify the manuscript. Send prose polishing to `article-polisher` only after the user asks and, for deep restructuring, after a plan is author approved.
- Reject Review Article architecture and route it to `review-architect-polisher`.

## Input gate

Require enough source identity to create stable locators and distinguish facts from proposals:

- Original Article manuscript or structured author notes;
- central question and principal findings that are either directly author supplied or explicitly stated in the author-provided manuscript/notes and extractable with stable locators;
- author-supplied novelty scope and author-confirmed frozen elements;
- figures, tables, result summaries, data objects, or existing evidence records;
- Methods or experiment metadata with one or more experiment labels;
- explicit missing, conflicting, unknown, and not-reported states.

Extracting an explicitly stated proposition from an author source is not permission to infer it from results, Figures, or data patterns. Record a source-extracted central question or principal finding as `explicitly_stated_in_author_source` with locators and `author_review_required` status. Novelty remains author supplied or explicitly author approved even when promotional novelty language appears in the manuscript.

Optional inputs are a deterministic Article `structure_profile`, a reviewed Article `architecture_profile`, and a provenance-bearing target-journal profile. If optional profiles are absent, declare degraded mode and continue conservatively. If neither the author nor an author-provided source states the required scientific anchors, stop at an inventory plus author-decision list; do not complete a scientific plan by inference.

## Workflow

1. Inventory source files and freeze author-provided facts, numerical values, terminology, comparison direction, causal ceiling, novelty scope, and explicit exclusions.
2. If an existing manuscript is present, record its reverse outline before proposing a new order. For notes-only input, record the schema-defined skip reason.
3. Build or normalize `claim_evidence_map`. Read [claim-evidence-gate.md](references/claim-evidence-gate.md).
4. For every key claim, create an `interpretation_card`. Read [observation-interpretation-boundary-validation.md](references/observation-interpretation-boundary-validation.md).
5. Apply every experiment profile matching the evidence labels. Multi-label evidence must satisfy all applicable boundaries. Resolve the conservative ceiling separately for each claim dimension rather than collapsing the evidence into one global strength rating.
6. Construct provenance-bearing story anchors, section goals, paragraph roles, claim/evidence assignments, and Figure sequence. Read [original-article-story.md](references/original-article-story.md), [section-and-paragraph-roles.md](references/section-and-paragraph-roles.md), and [figure-story-sequencing.md](references/figure-story-sequencing.md) only when those tasks are active. Treat a model-proposed Figure assignment as a raw proposal: materialize exactly one formal sequence entry per `figure_id` with `scripts/materialize_figure_sequence.py`, preserving the raw proposal and its receipt before schema and semantic validation.
7. Audit every evidence ID as assigned or explicitly unassigned with a permitted reason.
8. Run schema and semantic checks. Validation establishes structural consistency, not scientific truth or author approval.
9. Deliver an author-review package. Keep candidate structures separate when they encode different scientific choices; ask the author to select or revise them.

## Experiment routing

Always read [experiment-profiles/index.md](references/experiment-profiles/index.md), then only the profiles matching the evidence labels:

- `computational`: [computational.md](references/experiment-profiles/computational.md)
- `cell`: [cell.md](references/experiment-profiles/cell.md)
- `molecular` or `structural_biophysical`: [molecular.md](references/experiment-profiles/molecular.md)
- `animal`: [animal.md](references/experiment-profiles/animal.md)
- `omics`, `imaging`, `clinical_human`, or `other`: [additional-modalities.md](references/experiment-profiles/additional-modalities.md)

Experiment profiles identify relevant metadata, possible confounder categories, and claim ceilings. They do not decide whether evidence supports a claim. Track at least causality, mechanistic specificity, biological scope, generalizability, in-vivo relevance, and clinical relevance separately; a strong ceiling in one dimension cannot fill a dimension that is not assessed.

## Artifact and status contract

Create artifacts matching the schemas in `schemas/`:

- `claim_evidence_map`
- one or more `interpretation_card` artifacts
- `manuscript_plan`

Use `draft` or `author_review_required` unless the author explicitly approves the exact artifact version. Never infer approval from silence, schema validity, approval of another artifact, or approval of only one decision.

An architect-proposed claim restatement may reorganize or narrow an existing proposition but must keep `claim_origin: architect_proposed_restatement`, source locators, and an approval state. Do not create `model_inferred_from_data` claims.

Concrete experiment proposals are empty by default. Populate `proposed_validation_experiments` only when the author supplied them or explicitly requested a separate experiment-design task; keep abstract missing-evidence categories in `validation_needs`.

## Deterministic checks

Run from this Skill directory with Python 3:

```text
python scripts/validate_claim_evidence_map.py --claim-map <claim-map.json>
python scripts/check_artifact_links.py --claim-map <claim-map.json> --interpretation-card <card.json> --plan <plan.json>
python scripts/check_section_coverage.py --claim-map <claim-map.json> --plan <plan.json>
python scripts/render_reverse_outline.py --plan <plan.json> --output <reverse-outline.md>
python scripts/materialize_figure_sequence.py --proposal <raw-figure-proposal.json> --sequence-output <figure-sequence.json> --receipt-output <materialization-receipt.json>
```

The scripts use the hash-bound dependency-free validator vendored at `shared-core/scripts/validate_artifact.py`. A missing or mismatched validator is an explicit failure, not permission to skip schema validation. For exact authority and permission edge cases, consult the [frozen development contract](references/development-contract.md).

## Delivery

Return:

1. artifact file paths and status;
2. current reverse outline or the declared notes-only skip;
3. proposed section/paragraph/Figure structure;
4. unresolved evidence gaps, conflicts, overclaim risks, and unassigned evidence;
5. exact author decisions required;
6. validator results and any degraded-mode warnings.

Do not include rewritten manuscript paragraphs unless the user separately requests a drafting or polishing task.
