# Revision Modes

Scientific-content protection is identical in every mode. Modes change only the admitted language and structural footprint.

## Light

Use for grammar, punctuation, syntax, lexical tightening, redundancy removal, local transitions, and clarity within one existing sentence. Do not reorder or change sentence/paragraph counts. If a proposed edit changes scope attachment or a protected scientific anchor, stop and ask.

## Medium

May add sentence split/merge or full sentence reordering within one paragraph when the exact contract permits it. Results/Discussion reordering requires an author-approved M02 paragraph baseline with the affected claim/evidence bindings and source proposition IDs. Topic-sentence repair requires an existing source-located proposition or approved claim. Paragraph movement is not permitted.

## Deep

Requires `authorization_origin: author`, `authorization_state: author_approved`, `author_approval: approved`, and exact structural-change IDs from an internally consistent author-approved M02 plan. Every explicit `boundary:` reference, including a non-key boundary, must resolve through an exact hash-bound interpretation card listed by that plan, sharing its manuscript identity and consistent approved authority state. Patch layer `0.1.6` implements only whole-document paragraph reordering; paragraph split/merge remain unsupported. Deep permission does not authorize any new claim, interpretation, mechanism, evidence relationship, or section-membership change.

If a requested footprint is unsupported or its approval closure is incomplete, fail closed. Do not downgrade or reinterpret the request silently.
