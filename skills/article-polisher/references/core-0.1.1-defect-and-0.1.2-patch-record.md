# Article Polisher deterministic core 0.1.2 patch record

Status: candidate; not installed or activated.

## Preserved predecessor disposition

Core 0.1.1 is preserved byte-for-byte as historical evidence. The Item 3 0.1.1 exact-source review rejected it because three Medium operations could trust identifiers declared only inside a proposal or change manifest:

- Results/Discussion `information_reorder` could pass without an author-approved paragraph baseline and approved claim/evidence relation closure.
- `topic_sentence_repair` could pass with proposal-minted proposition identifiers that were not resolved in a supplied, hash-bound upstream artifact.
- `profile_alignment` could pass with a proposal-minted profile/feature reference when no matching M01 profile artifact was supplied.

## Authorized 0.1.2 patch surface

Core 0.1.2 is derived without modifying 0.1.1 in place. The patch is limited to deterministic provenance admission and version identity:

- bind upstream artifacts by exact artifact ID, artifact type, schema version, and canonical SHA-256;
- require an `author_approved` M02 manuscript plan for the exact manuscript and exact affected paragraph baseline;
- require an `author_approved` M02 claim/evidence map whose propositions, evidence links, scope, and paragraph locators close over the requested Results/Discussion reorder;
- resolve topic-sentence proposition IDs in the supplied claim/evidence map and require paragraph-scope agreement;
- resolve profile-alignment support through a strict JSON Pointer into a supplied `author_approved` Original Article M01 style or structure profile;
- reject Light contracts that declare Medium-only operations, independently of observed structural effects.

No scientific content is inferred and no proposal-supplied identifier is treated as authority.

## Regression scope

The candidate must pass the complete inherited core suite plus adversarial absent, invented, wrong-paragraph, and hash-mismatch controls for all three provenance gates. Exact supplied-and-approved positive controls are retained so fail-closed behavior does not disable contract-authorized operations.

