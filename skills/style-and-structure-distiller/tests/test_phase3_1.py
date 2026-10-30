"""Behavioral, regression, negative, and gold-evaluation tests for Phase 3.1."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "distill_corpus.py"
GOLD_SCRIPT = ROOT / "scripts" / "evaluate_gold.py"
FIXTURES = ROOT / "tests" / "fixtures"
ARTICLE_MANIFEST = FIXTURES / "approved-corpus-manifest.json"
REVIEW_MANIFEST = FIXTURES / "approved-review-manifest.json"
GOLD = FIXTURES / "gold" / "synthetic-original-gold.json"
VALIDATOR = ROOT / "shared-core" / "scripts" / "validate_artifact.py"
sys.path.insert(0, str(ROOT / "scripts"))
from parsers import VisibleHTMLParser, _pdf_source_lines, _text_blocks_from_lines, source_span_sha256
from confidence_qc import audit_prohibited_content
from evaluate_gold import _boundary_topology
from features import FIGURE_MENTION_PATTERN, _parse_figure_body


def run_script(script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-B", str(script), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def materialized_manifest(temp_dir: Path, source: Path) -> dict:
    payload = load(source)
    for record in payload["documents"]:
        record["source_file"] = str((source.parent / record["source_file"]).resolve())
    path = temp_dir / "manifest.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


class Phase31Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_context = tempfile.TemporaryDirectory()
        cls.temp_root = Path(cls.temp_context.name)
        cls.article_output = cls.temp_root / "article-output"
        cls.review_output = cls.temp_root / "review-output"
        article = run_script(SCRIPT, "run", "--manifest", str(ARTICLE_MANIFEST), "--out-dir", str(cls.article_output))
        review = run_script(SCRIPT, "run", "--manifest", str(REVIEW_MANIFEST), "--out-dir", str(cls.review_output))
        if article.returncode != 0:
            raise RuntimeError(article.stderr)
        if review.returncode != 0:
            raise RuntimeError(review.stderr)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_context.cleanup()

    def test_init_manifest_is_incomplete_but_records_source_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "draft.json"
            completed = run_script(
                SCRIPT,
                "init-manifest",
                "--input-dir",
                str(FIXTURES / "papers"),
                "--article-type",
                "original_article",
                "--corpus-id",
                "draft-phase31",
                "--output",
                str(output),
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            payload = load(output)
            self.assertEqual("0.2.2", payload["schema_version"])
            self.assertEqual("author_review_required", payload["status"])
            self.assertEqual("markdown", payload["documents"][0]["source_type"])
            self.assertIsNone(payload["documents"][0]["year"])

    def test_run_emits_separate_bounded_artifacts(self) -> None:
        expected = ["style-profile.json", "structure-profile.json", "corpus-balance.json"]
        self.assertTrue(all((self.article_output / name).is_file() for name in expected))
        documents = self.article_output / "documents"
        self.assertTrue((documents / "synthetic-article-1.section-map.json").is_file())
        self.assertTrue((documents / "synthetic-article-1.figure-reference-map.json").is_file())
        style = load(self.article_output / "style-profile.json")
        structure = load(self.article_output / "structure-profile.json")
        self.assertNotIn("confidence", style)
        self.assertEqual("document_weighted", style["aggregation_contract"]["primary_interpretation"])
        self.assertTrue(structure["deterministic_only"])
        self.assertFalse(structure["semantic_role_labels_present"])
        self.assertEqual("pass", style["prohibited_content_audit"]["result"])
        self.assertGreater(style["prohibited_content_audit"]["scanned_key_count"], 0)
        self.assertEqual(0, style["prohibited_content_audit"]["finding_count"])
        serialized = json.dumps([style, structure], ensure_ascii=False).lower()
        self.assertNotIn("raw_text", serialized)
        self.assertNotIn("architecture_annotations", serialized)

    def test_prohibited_content_audit_traverses_nested_payloads(self) -> None:
        audit = audit_prohibited_content([{"safe": {"raw_text": "not allowed"}}])
        self.assertEqual("author_review_required", audit["result"])
        self.assertTrue(audit["raw_passages_stored"])
        self.assertEqual(1, audit["finding_count"])
        self.assertIn("artifacts[0].safe.raw_text", audit["findings"][0]["path"])

    def test_raw_and_canonical_results_hierarchy_is_preserved(self) -> None:
        section_map = load(self.article_output / "documents" / "synthetic-article-1.section-map.json")
        sections = {item["source_heading"]: item for item in section_map["sections"]}
        results = sections["Results"]
        establishment = sections["System establishment"]
        orthogonal = sections["Orthogonal check"]
        self.assertEqual(results["section_id"], establishment["parent_section_id"])
        self.assertEqual(results["section_id"], orthogonal["parent_section_id"])
        self.assertEqual("results", establishment["canonical_section"])
        self.assertEqual("inherited_parent", establishment["canonical_mapping_basis"])
        self.assertEqual(2, establishment["source_heading_level"])
        self.assertIn(establishment["section_id"], results["child_section_ids"])
        self.assertEqual("line_char_range", establishment["source_locator"]["locator_type"])
        self.assertIn("start_char", establishment["source_locator"])
        self.assertIn("source_span_sha256", establishment["source_locator"])
        self.assertIn("parser_locator", establishment)
        raw = (FIXTURES / "papers" / "article-1.md").read_text(encoding="utf-8")
        locator = establishment["source_locator"]
        self.assertEqual(locator["source_span_sha256"], source_span_sha256(raw[locator["start_char"]:locator["end_char"]]))

    def test_html_and_pdf_locators_are_format_specific(self) -> None:
        raw_html = "<html><body>A &amp; B<h1>Results</h1>\n<p>Observed text.</p>\n</body></html>"
        parser = VisibleHTMLParser()
        parser.feed(raw_html)
        parser.close()
        self.assertEqual(["html_dom_path", "html_dom_path"], [item.source_locator["locator_type"] for item in parser.blocks])
        self.assertEqual("/html[1]/body[1]/h1[1]", parser.blocks[0].source_locator["dom_path"])
        self.assertEqual(1, parser.blocks[0].source_locator["source_anchor_order"])
        heading_offset = raw_html.index("<h1>")
        heading_prefix = raw_html[:heading_offset]
        self.assertEqual(heading_prefix.count("\n") + 1, parser.blocks[0].source_locator["start_line"])
        self.assertEqual(len(heading_prefix.rsplit("\n", 1)[-1]), parser.blocks[0].source_locator["start_column"])

        pdf_lines = _pdf_source_lines("Results\n\nObserved first page.\fMethods\n\nObserved second page.")
        blocks, _ = _text_blocks_from_lines(pdf_lines, True, "pdf_page_line_range")
        paragraph_locators = [item.source_locator for item in blocks if item.kind == "paragraph"]
        self.assertEqual([1, 2], [item["page_start"] for item in paragraph_locators])
        self.assertTrue(all(item["locator_type"] == "pdf_page_line_range" for item in paragraph_locators))

    def test_figure_references_are_many_to_many_and_panel_aware(self) -> None:
        payload = load(self.article_output / "documents" / "synthetic-article-1.figure-reference-map.json")
        self.assertEqual(3, payload["reference_count"])
        figure_two = [item for item in payload["figure_references"] if item["figure_id"] == "figure:2"]
        self.assertEqual(2, len(figure_two))
        self.assertEqual(2, len({item["source_section_id"] for item in figure_two}))
        self.assertEqual(["a", "b", "c"], figure_two[0]["panel_tokens"])
        self.assertIn("extended-data-figure:3", {item["figure_id"] for item in payload["figure_references"]})
        self.assertIsInstance(figure_two[0]["source_locator"], dict)
        self.assertGreater(figure_two[0]["reference_end_in_normalized_paragraph"], figure_two[0]["reference_start_in_normalized_paragraph"])
        self.assertEqual(64, len(figure_two[0]["reference_span_sha256"]))

    def test_figure_reference_panel_tokens_stop_before_adjacent_prose(self) -> None:
        cases = {
            "Fig. 1a and Supplementary Fig. 2": [
                ("Fig. 1a", [("1", ["a"])]),
                ("Supplementary Fig. 2", [("2", [])]),
            ],
            "Fig. 1a and Extended Data Fig. 3b": [
                ("Fig. 1a", [("1", ["a"])]),
                ("Extended Data Fig. 3b", [("3", ["b"])]),
            ],
            "Fig. 4d, Methods and Supplementary Video 3": [
                ("Fig. 4d", [("4", ["d"])]),
            ],
            "Fig. 4j and Supplementary Video 3": [
                ("Fig. 4j", [("4", ["j"])]),
            ],
            "Fig. 5b, depicting the assay": [
                ("Fig. 5b", [("5", ["b"])]),
            ],
            "Supplementary Fig. 1 and Table 1": [
                ("Supplementary Fig. 1", [("1", [])]),
            ],
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                observed = [
                    (match.group(0), _parse_figure_body(match.group("body")))
                    for match in FIGURE_MENTION_PATTERN.finditer(text)
                ]
                self.assertEqual(expected, observed)

    def test_figure_reference_list_tail_uses_local_continuation_context(self) -> None:
        cases = {
            "Fig. 1b and a model was fitted": [
                ("Fig. 1b", [("1", ["b"])]),
            ],
            "Fig. 2c, a control was included": [
                ("Fig. 2c", [("2", ["c"])]),
            ],
            "Fig. 3d and I observed a change": [
                ("Fig. 3d", [("3", ["d"])]),
            ],
            "Fig. 1b and a": [
                ("Fig. 1b and a", [("1", ["b", "a"])]),
            ],
            "Fig. 1b and a, c": [
                ("Fig. 1b and a, c", [("1", ["b", "a", "c"])]),
            ],
            "Fig. 1b and a & c": [
                ("Fig. 1b and a & c", [("1", ["b", "a", "c"])]),
            ],
            "Fig. 5h,i and Extended Data Fig. 8c": [
                ("Fig. 5h,i", [("5", ["h", "i"])]),
                ("Extended Data Fig. 8c", [("8", ["c"])]),
            ],
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                observed = [
                    (match.group(0), _parse_figure_body(match.group("body")))
                    for match in FIGURE_MENTION_PATTERN.finditer(text)
                ]
                self.assertEqual(expected, observed)

    def test_figure_reference_list_tail_stops_before_digit_leading_biomedical_token(self) -> None:
        text = "Fig. 1b and a 3D model was fitted"
        observed = [
            (match.group(0), _parse_figure_body(match.group("body")))
            for match in FIGURE_MENTION_PATTERN.finditer(text)
        ]
        self.assertEqual([("Fig. 1b", [("1", ["b"])])], observed)

    def test_figure_reference_list_tail_stops_before_alphanumeric_biomedical_token(self) -> None:
        text = "Fig. 2c, a p53 model was used"
        observed = [
            (match.group(0), _parse_figure_body(match.group("body")))
            for match in FIGURE_MENTION_PATTERN.finditer(text)
        ]
        self.assertEqual([("Fig. 2c", [("2", ["c"])])], observed)

    def test_figure_reference_list_tail_stops_before_unicode_hyphenated_biomedical_token(self) -> None:
        text = "Fig. 3d and a β-cell model was analysed"
        observed = [
            (match.group(0), _parse_figure_body(match.group("body")))
            for match in FIGURE_MENTION_PATTERN.finditer(text)
        ]
        self.assertEqual([("Fig. 3d", [("3", ["d"])])], observed)

    def test_figure_reference_list_tail_stops_before_parenthesized_biomedical_token(self) -> None:
        text = "Fig. 1b and a (3D) model was fitted"
        observed = [
            (match.group(0), _parse_figure_body(match.group("body")))
            for match in FIGURE_MENTION_PATTERN.finditer(text)
        ]
        self.assertEqual([("Fig. 1b", [("1", ["b"])])], observed)

    def test_figure_reference_list_tail_stops_before_quoted_biomedical_token(self) -> None:
        text = "Fig. 1b and a “3D” model was fitted"
        observed = [
            (match.group(0), _parse_figure_body(match.group("body")))
            for match in FIGURE_MENTION_PATTERN.finditer(text)
        ]
        self.assertEqual([("Fig. 1b", [("1", ["b"])])], observed)

    def test_figure_reference_list_tail_stops_before_comma_mediated_prose(self) -> None:
        text = "Fig. 3d and I, however, observed a change"
        observed = [
            (match.group(0), _parse_figure_body(match.group("body")))
            for match in FIGURE_MENTION_PATTERN.finditer(text)
        ]
        self.assertEqual([("Fig. 3d", [("3", ["d"])])], observed)

    def test_figure_reference_list_tail_stops_before_parenthesized_prose(self) -> None:
        text = "Fig. 3d and I (unexpectedly) observed a change"
        observed = [
            (match.group(0), _parse_figure_body(match.group("body")))
            for match in FIGURE_MENTION_PATTERN.finditer(text)
        ]
        self.assertEqual([("Fig. 3d", [("3", ["d"])])], observed)

    def test_figure_reference_panel_tokens_and_ranges_remain_supported(self) -> None:
        cases = {
            "Fig. 1a,b": [("1", ["a", "b"])],
            "Fig. 1a and b": [("1", ["a", "b"])],
            "Fig. 1m": [("1", ["m"])],
            "Fig. 2s": [("2", ["s"])],
            "Fig. 3a–d": [("3", ["a", "b", "c", "d"])],
            "Figures 1B, 2A, B, 3": [("1", ["b"]), ("2", ["a", "b"]), ("3", [])],
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                matches = list(FIGURE_MENTION_PATTERN.finditer(text))
                self.assertEqual(1, len(matches))
                self.assertEqual(expected, _parse_figure_body(matches[0].group("body")))

    def test_review_thematic_nodes_remain_distinct_and_nested(self) -> None:
        section_map = load(self.review_output / "documents" / "synthetic-review-1.section-map.json")
        themes = [item for item in section_map["sections"] if item["canonical_section"] == "review_body"]
        self.assertGreaterEqual(len(themes), 4)
        by_heading = {item["source_heading"]: item for item in themes}
        self.assertEqual(by_heading["Measurement landscape"]["section_id"], by_heading["Measurement categories"]["parent_section_id"])
        self.assertNotEqual(by_heading["Measurement landscape"]["section_id"], by_heading["Reporting outlook"]["section_id"])

    def test_nested_jats_sections_have_real_parent_ids(self) -> None:
        section_map = load(self.review_output / "documents" / "synthetic-review-2.section-map.json")
        by_heading = {item["source_heading"]: item for item in section_map["sections"]}
        parent = by_heading["Conceptual categories"]
        child = by_heading["Measurement boundaries"]
        self.assertEqual(parent["section_id"], child["parent_section_id"])
        self.assertEqual("Conceptual categories", child["source_parent_heading"])
        self.assertIn(child["section_id"], parent["child_section_ids"])
        self.assertEqual("xml_path", child["source_locator"]["locator_type"])
        self.assertIn("/sec[", child["source_locator"]["xml_path"])

    def test_document_first_and_token_weighted_views_are_distinct(self) -> None:
        style = load(self.article_output / "style-profile.json")
        results = style["sections"]["results"]
        document_marker = results["document_weighted"]["marker_rates_per_1000_words"]["figure_reference"]
        token_marker = results["token_weighted"]["marker_rates_per_1000_words"]["figure_reference"]
        self.assertEqual(2, document_marker["count"])
        self.assertIsInstance(token_marker, (int, float))
        support = results["feature_support"]["results.marker_rate.figure_reference"]
        self.assertEqual(2, support["document_count"])
        self.assertIn("bootstrap_95", support)
        self.assertIn("stratum_coverage", support)
        journal_coverage = support["stratum_coverage"]["journal"]
        self.assertIn("contributor_count_by_stratum", journal_coverage)
        self.assertIn("effective_stratum_count", journal_coverage)
        self.assertIn("leave_one_document_out_median_sensitivity", support)

    def test_format_prior_observed_qc_and_gold_are_not_conflated(self) -> None:
        record = load(self.review_output / "documents" / "synthetic-review-2.document-record.json")
        self.assertEqual(0.95, record["parser_format_prior"])
        self.assertIn("heading_recognition_rate", record["observed_parse_qc"])
        self.assertTrue(record["observed_parse_qc"]["parser_invariant_checks"]["all_passed"])
        self.assertNotIn("section_order_plausible", record["observed_parse_qc"])
        self.assertNotIn("parse_quality", record)
        self.assertNotIn("gold_evaluation", record)

    def test_corpus_balance_reports_bias_control_only(self) -> None:
        balance = load(self.article_output / "corpus-balance.json")
        self.assertEqual("bias_control_only_not_imitation", balance["group_metadata_usage"])
        self.assertEqual(1.0, balance["dimensions"]["lab_group"]["max_stratum_document_rate"])
        self.assertTrue(any(item["code"] == "dominant_lab_group_stratum" for item in balance["warnings"]))

    def test_mixed_article_types_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            payload = materialized_manifest(temp, ARTICLE_MANIFEST)
            payload["documents"][1]["article_type"] = "review_article"
            manifest = temp / "manifest.json"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            completed = run_script(SCRIPT, "run", "--manifest", str(manifest), "--out-dir", str(temp / "output"))
            self.assertEqual(2, completed.returncode)
            self.assertIn("Mixed Original Article and Review", completed.stderr)

    def test_hash_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            payload = materialized_manifest(temp, ARTICLE_MANIFEST)
            payload["documents"][0]["expected_sha256"] = "0" * 64
            manifest = temp / "manifest.json"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            completed = run_script(SCRIPT, "run", "--manifest", str(manifest), "--out-dir", str(temp / "output"))
            self.assertEqual(1, completed.returncode)
            warning_codes = {item["code"] for item in load(temp / "output" / "style-profile.json")["warnings"]}
            self.assertIn("document_parse_failures", warning_codes)

    def test_duplicate_source_content_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            payload = materialized_manifest(temp, ARTICLE_MANIFEST)
            payload["documents"][1]["source_file"] = payload["documents"][0]["source_file"]
            manifest = temp / "manifest.json"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            completed = run_script(SCRIPT, "run", "--manifest", str(manifest), "--out-dir", str(temp / "output"))
            self.assertEqual(2, completed.returncode)
            self.assertIn("Duplicate included source documents", completed.stderr)

    def test_nonempty_output_directory_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "output"
            output.mkdir()
            (output / "existing.txt").write_text("preserve", encoding="utf-8")
            completed = run_script(SCRIPT, "run", "--manifest", str(ARTICLE_MANIFEST), "--out-dir", str(output))
            self.assertEqual(2, completed.returncode)
            self.assertIn("non-empty output directory", completed.stderr)
            self.assertEqual("preserve", (output / "existing.txt").read_text(encoding="utf-8"))

    def test_schema_rejects_semantic_overload_of_structure_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid = load(self.article_output / "structure-profile.json")
            invalid["architecture_annotations"] = [{"role": "validation"}]
            invalid_path = Path(temp_dir) / "invalid-structure.json"
            invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
            completed = run_script(
                VALIDATOR,
                "--schema",
                str(ROOT / "schemas" / "structure-profile.schema.json"),
                "--data",
                str(invalid_path),
            )
            self.assertEqual(1, completed.returncode)
            self.assertIn("additionalProperties", completed.stdout)

    def test_gold_evaluator_is_perfect_for_synthetic_fixture(self) -> None:
        output = self.temp_root / "gold-evaluation.json"
        completed = run_script(
            GOLD_SCRIPT,
            "--gold",
            str(GOLD),
            "--actual-dir",
            str(self.article_output),
            "--output",
            str(output),
            "--require-perfect",
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        metrics = load(output)["aggregate"]
        self.assertEqual(1.0, metrics["heading_detection"]["recall"])
        self.assertEqual(1.0, metrics["heading_level"]["accuracy"])
        self.assertEqual(1.0, metrics["parent_hierarchy"]["accuracy"])
        self.assertEqual(1.0, metrics["canonical_section"]["accuracy"])
        self.assertEqual(1.0, metrics["paragraph_boundary"]["recall"])
        self.assertEqual(7, metrics["paragraph_boundary"]["topology_evaluable_expected_count"])
        self.assertEqual(0, metrics["paragraph_boundary"]["fragmented_gold_paragraph_count"])
        self.assertEqual(0.0, metrics["paragraph_boundary"]["fragmentation_rate"])
        self.assertEqual(0, metrics["paragraph_boundary"]["merged_gold_paragraph_count"])
        self.assertEqual(0.0, metrics["paragraph_boundary"]["erroneous_merge_rate"])
        self.assertEqual(0, metrics["paragraph_boundary"]["shifted_boundary_pair_count"])
        self.assertEqual(0.0, metrics["paragraph_boundary"]["shifted_boundary_rate"])
        self.assertEqual(0, metrics["paragraph_boundary"]["unclassifiable_boundary_error_count"])
        self.assertEqual(1.0, metrics["figure_id"]["recall"])
        self.assertEqual(1.0, metrics["panel_token"]["recall"])
        self.assertEqual(1.0, metrics["full_reference_exact_match"]["exact_match_rate"])

    def test_gold_evaluator_detects_missing_figure_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            output_dir = temp / "actual"
            completed = run_script(SCRIPT, "run", "--manifest", str(ARTICLE_MANIFEST), "--out-dir", str(output_dir))
            self.assertEqual(0, completed.returncode, completed.stderr)
            figure_path = output_dir / "documents" / "synthetic-article-1.figure-reference-map.json"
            figure_map = load(figure_path)
            figure_map["figure_references"].pop()
            figure_map["reference_count"] -= 1
            figure_map["unique_figure_count"] = len({item["figure_id"] for item in figure_map["figure_references"]})
            figure_path.write_text(json.dumps(figure_map), encoding="utf-8")
            evaluation = temp / "evaluation.json"
            checked = run_script(GOLD_SCRIPT, "--gold", str(GOLD), "--actual-dir", str(output_dir), "--output", str(evaluation))
            self.assertEqual(0, checked.returncode, checked.stderr)
            self.assertLess(load(evaluation)["aggregate"]["figure_id"]["recall"], 1.0)

    def test_gold_evaluator_rejects_source_sha256_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            mismatched_gold = load(GOLD)
            mismatched_gold["documents"][0]["source_sha256"] = "0" * 64
            gold_path = temp / "mismatched-gold.json"
            gold_path.write_text(json.dumps(mismatched_gold), encoding="utf-8")
            completed = run_script(
                GOLD_SCRIPT,
                "--gold",
                str(gold_path),
                "--actual-dir",
                str(self.article_output),
                "--output",
                str(temp / "evaluation.json"),
            )
            self.assertEqual(2, completed.returncode)
            self.assertIn("Source SHA-256 mismatch", completed.stderr)

    def test_gold_evaluator_detects_shifted_boundary_with_unchanged_paragraph_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            output_dir = temp / "actual"
            shutil.copytree(self.article_output, output_dir)
            section_path = output_dir / "documents" / "synthetic-article-1.section-map.json"
            section_map = load(section_path)
            original_count = len(section_map["paragraphs"])
            section_map["paragraphs"][0]["source_locator"]["end_char"] -= 1
            section_path.write_text(json.dumps(section_map), encoding="utf-8")
            evaluation = temp / "evaluation.json"
            checked = run_script(GOLD_SCRIPT, "--gold", str(GOLD), "--actual-dir", str(output_dir), "--output", str(evaluation))
            self.assertEqual(0, checked.returncode, checked.stderr)
            self.assertEqual(original_count, len(section_map["paragraphs"]))
            metric = load(evaluation)["aggregate"]["paragraph_boundary"]
            self.assertLess(metric["recall"], 1.0)
            self.assertGreater(metric["shifted_boundary_rate"], 0.0)
            self.assertEqual(0.0, metric["fragmentation_rate"])
            self.assertEqual(0.0, metric["erroneous_merge_rate"])

    def test_boundary_topology_separates_true_split_and_merge(self) -> None:
        def paragraph(start: int, end: int, digest: str) -> dict:
            return {
                "source_locator": {
                    "locator_type": "line_char_range",
                    "start_line": 1,
                    "end_line": 1,
                    "start_char": start,
                    "end_char": end,
                    "source_span_sha256": digest * 64,
                }
            }

        split = _boundary_topology(
            [paragraph(0, 100, "a")],
            [paragraph(0, 40, "b"), paragraph(40, 100, "c")],
        )
        self.assertEqual(1, split["fragmented_gold_paragraph_count"])
        self.assertEqual(0, split["merged_gold_paragraph_count"])
        self.assertEqual(0, split["shifted_boundary_pair_count"])

        merge = _boundary_topology(
            [paragraph(0, 40, "a"), paragraph(40, 100, "b")],
            [paragraph(0, 100, "c")],
        )
        self.assertEqual(0, merge["fragmented_gold_paragraph_count"])
        self.assertEqual(2, merge["merged_gold_paragraph_count"])
        self.assertEqual(0, merge["shifted_boundary_pair_count"])

    def test_heading_detection_and_level_accuracy_are_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            output_dir = temp / "actual"
            shutil.copytree(self.article_output, output_dir)
            section_path = output_dir / "documents" / "synthetic-article-1.section-map.json"
            section_map = load(section_path)
            section_map["sections"][4]["source_heading_level"] = 3
            section_path.write_text(json.dumps(section_map), encoding="utf-8")
            evaluation = temp / "evaluation.json"
            checked = run_script(GOLD_SCRIPT, "--gold", str(GOLD), "--actual-dir", str(output_dir), "--output", str(evaluation))
            self.assertEqual(0, checked.returncode, checked.stderr)
            metrics = load(evaluation)["aggregate"]
            self.assertEqual(1.0, metrics["heading_detection"]["recall"])
            self.assertLess(metrics["heading_level"]["accuracy"], 1.0)

    def test_parent_hierarchy_compares_source_nodes_not_heading_strings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            output_dir = temp / "actual"
            shutil.copytree(self.article_output, output_dir)
            section_path = output_dir / "documents" / "synthetic-article-1.section-map.json"
            section_map = load(section_path)
            section_map["sections"][4]["parent_section_id"] = section_map["sections"][2]["section_id"]
            section_map["sections"][4]["source_parent_heading"] = "Results"
            section_path.write_text(json.dumps(section_map), encoding="utf-8")
            evaluation = temp / "evaluation.json"
            checked = run_script(GOLD_SCRIPT, "--gold", str(GOLD), "--actual-dir", str(output_dir), "--output", str(evaluation))
            self.assertEqual(0, checked.returncode, checked.stderr)
            metrics = load(evaluation)["aggregate"]
            self.assertEqual(1.0, metrics["heading_detection"]["recall"])
            self.assertLess(metrics["parent_hierarchy"]["accuracy"], 1.0)

    def test_panel_token_error_does_not_reduce_figure_id_recall(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            output_dir = temp / "actual"
            shutil.copytree(self.article_output, output_dir)
            figure_path = output_dir / "documents" / "synthetic-article-1.figure-reference-map.json"
            figure_map = load(figure_path)
            figure_map["figure_references"][0]["panel_tokens"][-1] = "d"
            figure_path.write_text(json.dumps(figure_map), encoding="utf-8")
            evaluation = temp / "evaluation.json"
            checked = run_script(GOLD_SCRIPT, "--gold", str(GOLD), "--actual-dir", str(output_dir), "--output", str(evaluation))
            self.assertEqual(0, checked.returncode, checked.stderr)
            metrics = load(evaluation)["aggregate"]
            self.assertEqual(1.0, metrics["figure_id"]["recall"])
            self.assertLess(metrics["panel_token"]["recall"], 1.0)
            self.assertLess(metrics["full_reference_exact_match"]["exact_match_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
