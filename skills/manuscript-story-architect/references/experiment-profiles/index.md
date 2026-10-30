# Experiment Profile Router

Read every profile matching an evidence record's labels. Evidence can be multi-label; for example, a cell-based molecular assay uses both `cell.md` and `molecular.md`.

Profiles are question sets and claim ceilings, not automatic verdicts. When applicable profiles impose different ceilings, combine them conservatively per claim dimension rather than assigning one global evidence ceiling. A dimension that is not assessed stays `not_assessed` even when another dimension is strongly supported.

Keep these dimensions distinct when applicable:

- causality;
- mechanistic specificity;
- biological scope;
- generalizability;
- in-vivo relevance;
- clinical relevance.

For example, molecular evidence may directly support target engagement while the same cell-based evidence leaves in-vivo and clinical relevance not assessed. Do not downgrade the supported molecular dimension merely because broader relevance is absent, and do not use that molecular support to fill the absent dimensions.

For every evidence record identify:

- biological or technical unit;
- independence and replicate structure;
- controls and comparison direction;
- endpoint or feature measured;
- statistics locator and `n` definition;
- model or assay limitations;
- which claim dimensions are directly supported, indirect, or not assessed.

Never infer missing metadata. Record `not_reported`, `not_assessed`, or an author decision instead.
