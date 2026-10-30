---
name: scientific-figure-designer
description: Design, validate, or generate a tightly bounded biomedical Figure prototype from exact Original Article or Review evidence artifacts. Use for auditable Figure cards, Figure contracts, plot recipes, design-only review, or the admitted restricted Python/Pillow prototype chain. Do not use for arbitrary code, statistical recomputation, scientific approval, or final publication figures.
metadata:
  short-description: Design auditable biomedical Figure prototypes
---

# Scientific Figure Designer

Build or inspect a Figure package without inventing data, statistics, claims, authority, or scientific validity. The public entrypoint exposes exactly two modes.

## Public mode: `design_review_only`

Use this mode to create or validate the five frozen Phase 8A business artifacts—Source Data Manifest, Figure Cards, Figure Contract, Plot Recipe, and Figure QC—or to validate a standalone presentation-only design-revision proposal. Do not render or execute code in this mode.

Route `original_article` only from an exact admitted `module02_figure_story_bundle`; route `review_article` only from an exact admitted `module04_review_architecture_bundle`. The Phase 9 runtime handoff must bind the exact upstream IDs, versions, hashes, and required closure before their content is normalized into the Phase 8A `upstream_context`. A Review table brief must stay a table and cannot be converted to a Figure.

Run the frozen Phase 8A validator:

```text
python candidate/scripts/validate_figure_package.py <design-package-root> --trust-root <trusted-inputs-root.json> --trust-root-sha256 <caller-held-sha256> --output <new-figure-qc.json>
```

Validate a standalone design-revision proposal with:

```text
python scripts/validate_design_revision_proposal.py <proposal.json>
```

Read [mode-routing.md](references/mode-routing.md) before constructing or reviewing a package.

## Public mode: `prototype_execution_and_inspection`

Use this mode only after the exact Phase 8A package freshly validates at `ready_for_prototype`. The internal code-generation stage is not a third public mode: it is one required, hash-bound step within this execution chain.

The only admitted backend is generator-owned restricted Python with the pre-existing Pillow runtime. It is not a general sandbox and does not accept arbitrary Python or R. Use the package-local Phase 8B probe, admission, generator, program validator, runner, metadata inspector, and final validator in the order defined by [phase8b-development-contract.md](references/phase8b-development-contract.md). Every run requires an exact external execution authorization and a new output directory.

Do not install dependencies, use the network, overwrite source data or prior output, compute inferential statistics, fit models, select favorable results, or change Figure scientific meaning. Unsupported behavior blocks execution.

## Authority and completion boundary

- `prototype_generated_unverified` is not visually or scientifically verified and cannot be promoted by the model.
- A schema-valid inspection record proves only structural record validity, not that cognitive inspection occurred or that the Figure is scientifically correct.
- Model inspection cannot establish raw-image integrity, statistical appropriateness, copyright clearance, journal compliance, author acceptance, or publication readiness.
- Emit `module05_figure_qc_bundle` version `0.1.0` only with the exact Phase 8A manifest and Figure QC; when prototype mode runs, also retain the exact Phase 8A admission receipt, execution result, render manifest, inspection records, and Phase 8B Figure QC.
- Module 06 admission remains blocked until the separate Item 6 integration contract and consumer package are frozen.
- Never install or activate this candidate, overwrite an admitted source package, or run an automatic rewrite/rerender loop.
