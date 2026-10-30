# Semantic Preservation Contract

## Executable scope

The minimum gate compares two UTF-8 plain-text or Markdown inputs. It creates paragraph-level units separated by blank lines, hashes both full inputs, and stores line/character locators for every unit and extracted anchor.

Only a `caller_accepted` or explicitly `author_approved` `one_to_one` unit alignment with `execution_support: supported` receives deterministic anchor and local semantic-risk comparison. Caller acceptance permits execution but is not author approval. Split, merge, moved, added, removed, machine-proposed, rejected, or technically unsupported alignments remain `unassessable`; their presence cannot produce a clean pass.

## Deterministic anchor classes

The current extractor implements:

- conservative structured numeric anchors;
- numeric-bracket and author–year parenthetical citations, each explicitly classified;
- Figure, Extended Data Figure, Supplementary Figure, Table, Supplementary Table, equation, section, and appendix references with namespace-preserving subtype identity;
- double-brace and double-bracket placeholders;
- exact terminology terms supplied as a JSON string array;
- local lexical signals for direction, negation, causality, mechanism, hedging, and boundary language.

`extracted_categories` records the capabilities actually applied to each snapshot. A protected category missing from either snapshot, or not supported by the minimum implementation, is `unassessable` rather than passed.

Equations, variables, frozen literals, graph identities, and raw structured-section ingestion are represented in the artifact contract but are not claimed as implemented extractors in this candidate.

## Semantic warning boundary

Semantic-risk signals are compared as an ordered local sequence only within the two spans named by one reviewed alignment. Document-wide keyword counts are never evidence. An order, class, or normalized-signal change produces a warning and `human_review_required: true`; it does not establish that scientific meaning changed.

## Approval boundary

Schema validity, a clean gate result, or a deterministic alignment proposal cannot create author approval. The manifest generator leaves ordinal alignments `machine_proposed` unless its caller explicitly supplies `--accept-one-to-one-for-comparison`, which records `caller_accepted` only. The whole manifest always remains `author_review_required` after deterministic construction. Reports remain `draft` on a clean pass and `author_review_required` otherwise.

An `article_polisher` candidate requires an approved `revision_contract`. An exception applies only when its exact anchor/locator target, source representation, candidate representation, source hash, candidate hash, and candidate-anchor hash all match.
