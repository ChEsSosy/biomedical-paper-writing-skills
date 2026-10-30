# Claim–Evidence Gate

Use this reference when building or reviewing `claim_evidence_map`.

## Claim provenance

Admit only:

- `author_supplied`;
- `explicitly_stated_in_author_source`;
- `architect_proposed_restatement`.

An architect restatement must preserve or narrow the proposition, retain locators, and remain author-reviewable. Never label an inferred pattern as a claim.

## Support states

- `supported`: direct located evidence supports the full bounded claim.
- `partially_supported`: evidence supports only part of the direction, population, scope, mechanism, or generality.
- `unsupported`: supplied evidence does not support the claim.
- `conflicting`: supplied evidence points in materially different directions.
- `not_assessed`: no support judgment can be made from the supplied material.

Schema validity does not assign these states. The architect proposes a relation and the author approves the scientific judgment.

## Relation rules

Every claim–evidence relation names both IDs, relation type, rationale, scope match, and approval state. Keep counterevidence as `conflicts` or `does_not_support`; do not omit it to simplify the story.

Check at least:

- population/model identity;
- comparison direction;
- biological or technical unit;
- replicate structure and independence;
- controls;
- endpoint and assay identity;
- statistics locator;
- causal and mechanistic ceiling;
- known assay/model limitations.

`evidence_ids` and explicit relation records must agree. A supported claim needs a supporting relation. A partially supported claim must state which scope is not supported.

## Escalation boundaries

Flag for the author when evidence identity is unclear, locators disagree, comparison direction changes, support depends on an unstated exclusion, or evidence conflicts. Do not solve these cases by weakening or strengthening prose on the author's behalf.
