# M01 local maintenance 0.2.7

User-authorized source update and local replacement, 2026-10-03.

Baseline: Phase 9 package 0.1.0, implementation 0.2.6; package manifest SHA-256 `4ad33e15db3dc00a717a88d2fc8808e48124f3d1ad43d5209aa682fafe42f90a`.

Current: package 0.1.1, implementation 0.2.7. This maintenance release adds exact-span Markdown projection and explicit draft diagnostics, and corrects nested Review Summary mapping. Shared schemas, Figure parsing and other Skills retain their prior implementations. `package-adaptation-receipt.json` describes the historical 0.1.0 baseline only; it does not certify this maintenance change.

Tests exercise prose after Boxes/Tables, short prose, page continuations, changed hashes, invalid spans/joins, top-level versus body Summary, and draft output authority. Real-paper selection plans and results remain outside the distributable Skill. Successful checks do not imply independent review or a newly frozen six-Skill system.
