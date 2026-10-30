# Corpus Governance

Use this reference before accepting or modifying a corpus.

## Corpus identity

Create separate corpora for `original_article` and `review_article`. Each included document has a stable local ID, source path, verified article type, access/use status, inclusion decision, metadata provenance, and available bibliographic or grouping metadata.

Optional DOI, PMID, PMCID, language, source type, article subtype, corpus group, lab group, and journal family support provenance and bias analysis. Do not infer uncertain bibliographic facts from memory.

## Group metadata boundary

`corpus_group` and `lab_group` are bias-control metadata. They may be used for sampling, dominance warnings, balance checks, or stratified stability analysis. They must not be used to create an identifiable author/lab voice, a “writing DNA” profile, or imitation instructions.

## Access and storage

- Process only documents the user is authorized to use.
- Keep real papers and manually annotated real gold corpora outside the reusable Skill package.
- Package only synthetic fixtures.
- Do not store full papers, reusable passages, captions, figures, or layouts in artifacts.
- Preserve source hashes where available.

## Sampling and promotion

After changing source bytes or prose selection, create an `author_review_required` manifest. The diagnostic `run --draft` path validates the same metadata, access, routing and source hashes and labels outputs as unapproved. Normal `run` still requires an `author_approved` manifest. Draft success does not grant authority to downstream rewriting.

Inspect journal, year, domain, experiment, group, subtype, language, and format concentration. A large but homogeneous corpus is not representative by default. Exclusions require reasons; duplicates and parser failures remain visible.

After synthetic validation, use a small manually annotated real gold subset, then separate 5–10 Article and 5–10 Review pilots. Revise parser/schema behavior, run a second pilot, and freeze deterministic v1 before Phase 3.2.
