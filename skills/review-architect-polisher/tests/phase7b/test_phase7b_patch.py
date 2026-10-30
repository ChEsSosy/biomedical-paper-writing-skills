"""Behavioral and CLI tests for the Phase 7B patch candidate 0.1.6."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent.parent
PATCH = SKILL_ROOT
CORE = SKILL_ROOT
for path in (SKILL_ROOT / "scripts", HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import fixture_factory as fixtures  # noqa: E402
from apply_review_revision_proposal import (  # noqa: E402
    PatchApplicationError,
    _apply_operation,
    _normalize_phase7a_paths,
    apply_review_revision_proposal,
)
from build_review_change_inventory import refresh_document, write_json  # noqa: E402


SCRIPT = PATCH / "scripts" / "apply_review_revision_proposal.py"
OUTPUT_NAMES = {
    "candidate-review.json",
    "review-revision-lineage-map.json",
    "review-protected-change-inventory.json",
    "review-author-query-list.json",
    "review-change-manifest.json",
    "review-patch-application-receipt.json",
    "review-package-validation-result.json",
}


def _candidate_sentence(sentence: dict) -> dict:
    return {
        "candidate_sentence_id": sentence["sentence_id"],
        "source_sentence_ids": list(sentence["source_sentence_ids"]),
        "authorized_draft_slot_ids": [],
        "text": sentence["text"],
        "claim_ids": list(sentence["claim_ids"]),
        "citation_relation_ids": list(sentence["citation_relation_ids"]),
    }


def _deep_case(
    operation_type: str,
    target_ids: list[str],
    *,
    replacements: list[dict] | None = None,
    target_section_id: str | None = None,
    destination_section_id: str | None = None,
    destination_ordinal: int | None = None,
) -> dict:
    phase7a = fixtures.phase7a_package()
    source = fixtures.source_document()
    permission = fixtures.permission(
        source,
        phase7a,
        "deep",
        operation_type=operation_type,
        target_unit_ids=target_ids,
    )
    operation = {
        "operation_id": f"review-operation-{operation_type}-1",
        "operation_order": 1,
        "operation_type": operation_type,
        "target_unit_ids": list(target_ids),
        "target_section_id": target_section_id,
        "destination_section_id": destination_section_id,
        "destination_ordinal": destination_ordinal,
        "expected_targets": fixtures._expected_targets(source, target_ids),
        "expected_slot": None,
        "replacement_units": copy.deepcopy(replacements or []),
        "phase7a_closure": fixtures.exact_closure(),
        "affected_protected_anchor_ids": [],
        "permission_decision_id": permission["authorized_decisions"][0]["decision_id"],
        "rationale": f"Exercise exact {operation_type} application semantics.",
        "risk_class": "high",
        "author_review_required": True,
    }
    decision = permission["authorized_decisions"][0]
    source_index = {unit["unit_id"]: unit for unit in source["units"]}
    decision["affected_paragraph_ids"] = sorted({
        source_index[unit_id]["paragraph_plan_id"] for unit_id in target_ids
    } | {
        replacement["paragraph_plan_id"] for replacement in operation["replacement_units"]
    })
    decision["affected_section_ids"] = sorted({
        source_index[unit_id]["section_id"] for unit_id in target_ids
    } | {
        replacement["section_id"] for replacement in operation["replacement_units"]
    } | {
        section_id for section_id in (target_section_id, destination_section_id)
        if isinstance(section_id, str)
    })
    permission["permission_sha256"] = fixtures.permission_payload_sha256(permission)
    proposal = fixtures.proposal(source, permission, "deep", operation)
    return {
        "source": source,
        "phase7a": phase7a,
        "permission": permission,
        "expected_permission_sha256": permission["permission_sha256"],
        "proposal": proposal,
    }


def _split_case() -> dict:
    source = fixtures.source_document()
    target = source["units"][0]
    replacements = [
        fixtures.replacement_from_unit(
            target,
            candidate_unit_id=f"review-unit-1-{suffix}",
            sentences=[_candidate_sentence(sentence)],
        )
        for suffix, sentence in (("a", target["sentences"][0]), ("b", target["sentences"][1]))
    ]
    case = _deep_case("paragraph_split", ["review-unit-1"], replacements=replacements)
    # Rebuild against the exact source identity created by _deep_case.
    target = case["source"]["units"][0]
    case["proposal"]["operations"][0]["replacement_units"] = [
        fixtures.replacement_from_unit(
            target,
            candidate_unit_id=f"review-unit-1-{suffix}",
            sentences=[_candidate_sentence(sentence)],
        )
        for suffix, sentence in (("a", target["sentences"][0]), ("b", target["sentences"][1]))
    ]
    fixtures.refresh_proposal(case["proposal"])
    return case


def _merge_case() -> dict:
    case = _deep_case("paragraph_merge", ["review-unit-1", "review-unit-2"])
    units = case["source"]["units"][:2]
    replacement = fixtures.replacement_from_unit(
        units[0],
        candidate_unit_id="review-unit-merged-1",
        source_unit_ids=[unit["unit_id"] for unit in units],
        sentences=[_candidate_sentence(sentence) for unit in units for sentence in unit["sentences"]],
    )
    case["proposal"]["operations"][0]["replacement_units"] = [replacement]
    fixtures.refresh_proposal(case["proposal"])
    return case


def _apply(case: dict) -> dict[str, dict]:
    return apply_review_revision_proposal(
        case["source"],
        case["permission"],
        case["expected_permission_sha256"],
        case["proposal"],
        case["phase7a"],
    )


def _write_cli_case(case: dict, root: Path) -> dict[str, Path]:
    paths = {
        "source": root / "source.json",
        "permission": root / "permission.json",
        "proposal": root / "proposal.json",
        "phase7a": root / "phase7a.json",
    }
    for key, path in paths.items():
        # The frozen Phase 7A synthetic factory retains Path objects for direct
        # validation; a CLI fixture must serialize those paths exactly as strings.
        serializable = json.loads(json.dumps(case[key], default=str))
        write_json(path, serializable)
    return paths


def _cli_command(paths: dict[str, Path], output: Path, report: Path | None = None) -> list[str]:
    command = [
        sys.executable,
        "-B",
        str(SCRIPT),
        "--source-document",
        str(paths["source"]),
        "--permission",
        str(paths["permission"]),
        "--expected-permission-sha256",
        json.loads(paths["permission"].read_text(encoding="utf-8"))["permission_sha256"],
        "--proposal",
        str(paths["proposal"]),
        "--phase7a-package",
        str(paths["phase7a"]),
        "--output-dir",
        str(output),
    ]
    if report is not None:
        command.extend(["--json-report", str(report)])
    return command


class Phase7BPatchTests(unittest.TestCase):
    def test_01_light_application_produces_exact_artifact_set(self) -> None:
        artifacts = _apply(fixtures.light_case())
        self.assertEqual(set(artifacts), OUTPUT_NAMES)
        self.assertEqual(artifacts["candidate-review.json"]["side"], "candidate")

    def test_02_medium_application_preserves_requested_sentence_order(self) -> None:
        case = fixtures.medium_case()
        expected = [item["candidate_sentence_id"] for item in case["proposal"]["operations"][0]["replacement_units"][0]["sentences"]]
        candidate = _apply(case)["candidate-review.json"]
        actual = [item["sentence_id"] for item in candidate["units"][0]["sentences"]]
        self.assertEqual(actual, expected)

    def test_03_paragraph_move_applies_exact_destination(self) -> None:
        candidate = _apply(fixtures.deep_move_case())["candidate-review.json"]
        self.assertEqual([unit["unit_id"] for unit in candidate["units"]], ["review-unit-2", "review-unit-1", "review-unit-3"])

    def test_04_authorized_draft_slot_materializes_exact_unit(self) -> None:
        artifacts = _apply(fixtures.draft_case())
        candidate = artifacts["candidate-review.json"]
        self.assertEqual(candidate["units"][-1]["authorized_draft_slot_ids"], ["review-slot-future-1"])
        self.assertEqual(artifacts["review-change-manifest.json"]["module06_handoff"]["state"], "blocked_pending_module06_integration_contract")

    def test_05_paragraph_split_replaces_one_unit_with_two(self) -> None:
        candidate = _apply(_split_case())["candidate-review.json"]
        self.assertEqual([unit["unit_id"] for unit in candidate["units"][:2]], ["review-unit-1-a", "review-unit-1-b"])
        self.assertEqual(len(candidate["units"]), 4)

    def test_06_paragraph_merge_replaces_contiguous_units(self) -> None:
        candidate = _apply(_merge_case())["candidate-review.json"]
        self.assertEqual(candidate["units"][0]["unit_id"], "review-unit-merged-1")
        self.assertEqual(candidate["units"][0]["source_unit_ids"], ["review-unit-1", "review-unit-2"])
        self.assertEqual(len(candidate["units"]), 2)

    def test_07_section_move_moves_complete_section(self) -> None:
        case = _deep_case(
            "section_move",
            ["review-unit-1", "review-unit-2"],
            target_section_id="section-response",
            destination_ordinal=2,
        )
        candidate = _apply(case)["candidate-review.json"]
        self.assertEqual([unit["section_id"] for unit in candidate["units"]], ["section-limitations", "section-response", "section-response"])

    def test_08_theme_reorganization_moves_exact_units_and_section(self) -> None:
        case = _deep_case(
            "theme_reorganization",
            ["review-unit-2"],
            destination_section_id="section-limitations",
            destination_ordinal=3,
        )
        candidate = _apply(case)["candidate-review.json"]
        self.assertEqual(candidate["units"][-1]["unit_id"], "review-unit-2")
        self.assertEqual(candidate["units"][-1]["section_id"], "section-limitations")

    def test_09_repeated_application_is_byte_deterministic(self) -> None:
        case = fixtures.light_case()
        first = json.dumps(_apply(case), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        second = json.dumps(_apply(case), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertEqual(first, second)

    def test_10_manifest_retains_non_overclaim_boundaries(self) -> None:
        manifest = _apply(fixtures.light_case())["review-change-manifest.json"]
        self.assertFalse(manifest["scientific_correctness_claimed"])
        self.assertFalse(manifest["qc_pass_claimed"])
        self.assertTrue(manifest["author_review_required"])

    def test_11_query_list_preserves_unrelated_open_query(self) -> None:
        case = fixtures.light_case()
        case["proposal"]["unresolved_queries"] = [{
            "query_id": "query-unrelated-1",
            "query_type": "citation_support",
            "question": "Does the first unit need an additional source?",
            "affected_unit_ids": ["review-unit-1"],
            "blocks_revision": True,
            "status": "unresolved",
        }]
        fixtures.refresh_proposal(case["proposal"])
        queries = _apply(case)["review-author-query-list.json"]
        self.assertEqual(queries["queries"], case["proposal"]["unresolved_queries"])

    def test_12_application_rejects_admission_failure_before_mutation(self) -> None:
        case = fixtures.light_case()
        case["expected_permission_sha256"] = "0" * 64
        with self.assertRaisesRegex(PatchApplicationError, "admission:blocked"):
            _apply(case)

    def test_13_direct_application_rejects_invalid_destination(self) -> None:
        candidate = copy.deepcopy(fixtures.source_document())
        operation = copy.deepcopy(fixtures.deep_move_case()["proposal"]["operations"][0])
        operation["destination_ordinal"] = 99
        with self.assertRaisesRegex(PatchApplicationError, "application:destination"):
            _apply_operation(candidate, operation)

    def test_14_direct_application_rejects_unknown_destination_section(self) -> None:
        candidate = copy.deepcopy(fixtures.source_document())
        operation = copy.deepcopy(fixtures.deep_move_case()["proposal"]["operations"][0])
        operation["destination_section_id"] = "section-unknown"
        with self.assertRaisesRegex(PatchApplicationError, "application:destination_section"):
            _apply_operation(candidate, operation)

    def test_15_direct_merge_rejects_noncontiguous_targets(self) -> None:
        candidate = copy.deepcopy(fixtures.source_document())
        operation = copy.deepcopy(_merge_case()["proposal"]["operations"][0])
        operation["target_unit_ids"] = ["review-unit-1", "review-unit-3"]
        with self.assertRaisesRegex(PatchApplicationError, "application:merge_noncontiguous"):
            _apply_operation(candidate, operation)

    def test_16_direct_application_rejects_duplicate_candidate_unit_ids(self) -> None:
        candidate = copy.deepcopy(fixtures.source_document())
        candidate["units"][1]["unit_id"] = candidate["units"][0]["unit_id"]
        operation = copy.deepcopy(fixtures.deep_move_case()["proposal"]["operations"][0])
        with self.assertRaisesRegex(PatchApplicationError, "application:duplicate_unit"):
            _apply_operation(candidate, operation)

    def test_17_relative_phase7a_paths_are_resolved_from_wrapper(self) -> None:
        wrapper = Path("D:/synthetic/package/phase7a.json")
        package = {"trusted_inputs": {"one": {"path": "inputs/source.json"}}}
        normalized = _normalize_phase7a_paths(package, wrapper)
        self.assertEqual(Path(normalized["trusted_inputs"]["one"]["path"]), (wrapper.parent / "inputs/source.json").resolve())

    def test_18_cli_success_writes_exact_files_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = _write_cli_case(fixtures.light_case(), root)
            output = root / "output"
            report = root / "success.json"
            completed = subprocess.run(
                _cli_command(paths, output, report),
                text=True,
                capture_output=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual({path.name for path in output.iterdir()}, OUTPUT_NAMES)
            self.assertTrue(json.loads(report.read_text(encoding="utf-8"))["ok"])

    def test_19_cli_refuses_existing_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = _write_cli_case(fixtures.light_case(), root)
            output = root / "existing"
            output.mkdir()
            completed = subprocess.run(
                _cli_command(paths, output), text=True, capture_output=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, check=False,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertIn("refusing to overwrite", completed.stderr)
            self.assertEqual(list(output.iterdir()), [])

    def test_20_cli_admission_failure_creates_no_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = fixtures.light_case()
            paths = _write_cli_case(case, root)
            output = root / "output"
            report = root / "failure.json"
            command = _cli_command(paths, output, report)
            expected_index = command.index("--expected-permission-sha256") + 1
            command[expected_index] = "0" * 64
            completed = subprocess.run(
                command, text=True, capture_output=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, check=False,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertFalse(output.exists())
            failure = json.loads(report.read_text(encoding="utf-8"))
            self.assertFalse(failure["ok"])
            self.assertEqual(failure["producer_state"], "blocked")


if __name__ == "__main__":
    unittest.main()
