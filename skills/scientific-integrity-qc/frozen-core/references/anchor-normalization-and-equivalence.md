# Anchor Normalization and Equivalence

## General rule

Normalization may remove harmless formatting differences; it may not infer scientific equivalence. Occurrence order is preserved inside each aligned unit and anchor class.

## Numeric anchors

Numeric comparison is field-by-field over:

- comparator;
- sign;
- canonical decimal value;
- explicit scientific exponent;
- uncertainty kind and uncertainty value;
- range endpoints;
- unit;
- numerator and denominator;
- local context type and occurrence position.

Leading-zero formatting such as `.05` versus `0.05`, and Unicode comparator typography such as `≤` versus `<=`, may normalize as equal. The following remain unequal:

- `P < 0.05` versus `P = 0.05`;
- `10 mg` versus `20 mg`;
- `1000 ng` versus `1 µg`;
- a ratio with a changed denominator;
- a value expressed with a different explicit exponent structure.

No unit conversion runs in the minimum gate.

## Other deterministic classes

- Numeric-bracket citations normalize internal whitespace and range-dash typography. Author–year parenthetical citations normalize whitespace and case while preserving author/year identity. Other citation grammars are outside this ruleset.
- Reference abbreviations normalize to a subtype plus label. Figure, Extended Data Figure, Supplementary Figure, Table, Supplementary Table, equation, section, and appendix namespaces remain distinct.
- Each terminology-map entry declares `case_sensitive` or `case_insensitive`. Case is preserved or folded only as declared; the gate never infers biomedical case semantics.
- Placeholder interiors are preserved except surrounding whitespace normalization.

## Semantic signals

Direction, negation, causality, mechanism, hedging, and boundary terms are lexical risk anchors. Differences create review warnings only. They are never converted into blocker/error findings without a separate structured frozen constraint.
