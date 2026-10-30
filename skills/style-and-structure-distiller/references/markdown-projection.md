# Preparing a Markdown analysis copy

Keep the readable paper and PDF in the user's project. Use a separate analysis copy when captions, tables, boxes or references would contaminate prose statistics. Sentence readability does not establish a reliable Box/Table end boundary.

`scripts/project_markdown.py` retains all unlisted blocks. Supply a project-local JSON plan with the complete source SHA-256 and `exclude` entries identifying exact whole blocks by `start_line`, `end_line`, `span_sha256` and `reason`. The span hash is SHA-256 of the block's UTF-8 text joined with LF, without a final newline. Source file hash uses raw bytes. `source_blocks()` exposes these boundaries for a project preparation script.

Example plan structure (hashes must be computed from the actual source):

```json
{
  "source_sha256": "<source file SHA-256>",
  "exclude": [
    {"start_line": 9, "end_line": 9, "span_sha256": "<block SHA-256>", "reason": "Box heading"},
    {"start_line": 11, "end_line": 13, "span_sha256": "<block SHA-256>", "reason": "Box content"}
  ],
  "joins": [{"start_line": 15, "previous_start_line": 7}]
}
```

Use `joins` only for verified sentence continuations interrupted by a box, figure or page break. They bind adjacent retained prose blocks; headings cannot be joined. Original lines and hashes remain recoverable in the receipt. Known PDF page comments are removed from prose and retained as page locators.

When a running header or page label is embedded inside retained prose, a plan may use `remove_literals` for that exact fragment. Each entry identifies the containing paragraph by `start_line`, `end_line`, and `source_span_sha256`, and binds the exact `literal`, `literal_sha256`, and `reason`. The literal must occur once, cannot consume the whole block, and cannot overlap another removal. The receipt records the original block hash, projected block hash, source character offsets, source line range, and removed literal hash. Keep these fragments in the readable paper; this operation affects only the analysis copy. Review the prose on both sides before joining blocks. Do not use this field to silently edit scientific content.

For verified PDF reading-order displacement, `move_after` may relocate one retained paragraph block after another. Bind the moved block with `start_line`, `end_line`, and `source_span_sha256`; bind the anchor with `after_start_line` and `after_span_sha256`; give a reason. The receipt retains original source lines, page, hashes and the move target. Review both paragraphs against the PDF before using a `join`. Moves never authorize relocating headings or changing scientific wording.

```text
project_markdown.py --source paper.md --plan selection.json --output analysis.md --receipt projection.json
```

Review the surrounding source for every excluded Box/Table span, particularly same-page body resumption and cross-page continuations. Use the PDF if the MD does not resolve the boundary. Do not infer an exclusion's end from the next heading, paragraph length or sentence count. Short text may be a valid continuation; long text may be a table note. Unresolved ancillary openers stop projection for local boundary review. A successful receipt proves exact selection, not that the operator chose correct boundaries.

Keep body Summary headings and content. Under a Review body parent, M01 0.2.7 maps Summary to that body while preserving the raw heading. A standalone paper Summary retains its Abstract mapping.

For a changed analysis source, write a new `author_review_required` manifest. `distill_corpus.py run --draft --manifest ... --out-dir ...` produces explicitly unapproved diagnostic artifacts. It checks routing, source hashes and schemas; it never changes the manifest's approval state. The ordinary run path still requires author approval. Judge completeness separately from repeatability or hash agreement.
