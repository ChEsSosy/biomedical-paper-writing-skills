# Figure Story Sequencing

Use this reference when mapping figures into the Article plan. This Skill plans evidence order; it does not design visual styling or generate plots.

## Figure sequence record

Each item carries:

- Figure ID and proposed order;
- purpose in the story;
- linked claim IDs;
- linked evidence IDs;
- author approval state.

The model-facing proposal and formal artifact are separate. A raw proposal may
contain multiple claim-centric rows for the same Figure. Before validation, run
the deterministic materializer to group by `figure_id`, aggregate claim and
evidence IDs as ordered-unique unions, and emit one Figure-centric row. Preserve
the raw proposal and materialization receipt. The materializer may combine only
associations already present in the proposal; it must reject unknown IDs and must
not infer a claim, evidence relation, purpose, or order from scientific content.

Panel-level details stay in evidence locators or later Figure artifacts. Do not copy a published layout as a template.

## Ordering tests

Check whether the sequence:

- introduces the model, cohort, or data source before dependent conclusions;
- places primary evidence before validation or extension evidence;
- keeps observation before broad interpretation;
- makes negative, conflicting, or boundary-setting evidence visible;
- matches the Results paragraph order;
- avoids implying causality or generality through visual order alone.

A different Figure order is a material proposal when it changes the apparent evidence hierarchy. Keep it pending until approved.

## Extended Data and Supplement

Evidence may be assigned to Extended Data or Supplement only with an explicit rationale such as redundant validation or scope. Negative or counterevidence must remain discoverable and linked to the bounded claim. `supplement_candidate` is an audit state, not permission to hide inconvenient evidence.

Hand later Figure design work to `scientific-figure-designer` with claim and evidence IDs intact.
