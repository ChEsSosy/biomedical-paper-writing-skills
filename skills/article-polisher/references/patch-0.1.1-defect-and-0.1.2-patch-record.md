# Article Polisher patch/application layer 0.1.2 patch record

Status: candidate; not installed or activated.

## Preserved predecessor disposition

Patch layer 0.1.1 is preserved as rejected Item 3 source-review evidence. Its application entrypoint validated proposal syntax and authorization shape but could apply three Medium operations before proving that their claimed provenance existed in supplied, hash-bound upstream artifacts.

## 0.1.2 change

Patch layer 0.1.2 calls the core provenance gate before modifying the source document. Callers must supply the upstream artifact instances referenced by the proposal. The gate rejects:

- Results/Discussion information reorder without exact approved plan and claim/evidence relation closure;
- topic-sentence repair without proposition resolution and paragraph-scope agreement;
- profile alignment without an exact approved M01 profile and resolvable feature-support pointer;
- upstream identity or canonical-hash mismatches;
- Light contracts that declare Medium-only operations.

The same rules remain in the core package validator after application, providing defense in depth. The patch does not add a word list, mint provenance, change scientific claims, or expand the frozen development contract.

