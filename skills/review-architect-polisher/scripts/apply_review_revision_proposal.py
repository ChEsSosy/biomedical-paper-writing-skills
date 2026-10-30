#!/usr/bin/env python3
"""Apply an admitted Phase 7B proposal and derive all trusted Review evidence."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
MODULE04_ROOT = HERE.parent.parent
SIBLING_CORE = MODULE04_ROOT / "phase7b-core-candidate-0.1.6" / "scripts"
CORE_SCRIPTS = HERE if (HERE / "build_review_change_inventory.py").is_file() else SIBLING_CORE
if str(CORE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(CORE_SCRIPTS))

from build_review_change_inventory import (  # noqa: E402
    artifact_identity,
    build_inventory,
    build_lineage_map,
    canonical_sha256,
    payload_sha256,
    read_json,
    refresh_document,
    write_json,
)
from validate_review_revision_package import (  # noqa: E402
    DEFAULT_PHASE7A_SCHEMAS,
    DEFAULT_PHASE7A_VALIDATOR,
    DEFAULT_SCHEMAS,
    DEFAULT_SHARED_VALIDATOR,
    _artifact_ref,
    _permission_ref,
    _proposal_ref,
    build_application_receipt,
    build_package_validation_result,
    expected_change_records,
    expected_citation_support_warnings,
    expected_upstream_closure_refs,
    validate_admission,
    validate_revision_evidence,
    validate_revision_package,
    verify_package_runtime_trust_root,
)


class PatchApplicationError(RuntimeError):
    """Raised when deterministic patch application cannot continue safely."""


def _fail(code: str, message: str) -> None:
    raise PatchApplicationError(f"[{code}] {message}")


def _candidate_unit(spec: dict[str, Any]) -> dict[str, Any]:
    sentences = [
        {
            "sentence_id": sentence["candidate_sentence_id"],
            "source_sentence_ids": list(sentence["source_sentence_ids"]),
            "authorized_draft_slot_ids": list(sentence["authorized_draft_slot_ids"]),
            "ordinal": index,
            "text": sentence["text"],
            "claim_ids": list(sentence["claim_ids"]),
            "citation_relation_ids": list(sentence["citation_relation_ids"]),
        }
        for index, sentence in enumerate(spec["sentences"], 1)
    ]
    return {
        "unit_id": spec["candidate_unit_id"],
        "source_unit_ids": list(spec["source_unit_ids"]),
        "authorized_draft_slot_ids": list(spec["authorized_draft_slot_ids"]),
        "ordinal": 0,
        "section_id": spec["section_id"],
        "section_ordinal": spec["section_ordinal"],
        "paragraph_plan_id": spec["paragraph_plan_id"],
        "text": " ".join(sentence["text"] for sentence in sentences).strip(),
        "locator": {},
        "sentences": sentences,
        **{field: list(spec[field]) for field in (
            "claim_ids", "citation_relation_ids", "source_ids", "extraction_record_ids",
            "conflict_ids", "limitation_ids", "gap_ids", "author_position_ids",
            "future_direction_ids",
        )},
    }


def _unit_index(units: list[dict[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for index, unit in enumerate(units):
        unit_id = unit.get("unit_id")
        if unit_id in result:
            _fail("application:duplicate_unit", f"duplicate candidate unit ID: {unit_id}")
        result[unit_id] = index
    return result


def _exact_positions(units: list[dict[str, Any]], target_ids: list[str]) -> list[int]:
    index = _unit_index(units)
    if any(unit_id not in index for unit_id in target_ids):
        _fail("application:stale_target", "target disappeared during ordered application")
    return [index[unit_id] for unit_id in target_ids]


def _insert_at(units: list[dict[str, Any]], values: list[dict[str, Any]], ordinal: int | None) -> None:
    if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 1 or ordinal > len(units) + 1:
        _fail("application:destination", "destination_ordinal is outside the candidate unit range")
    units[ordinal - 1:ordinal - 1] = values


def _refresh_section_ordinals(units: list[dict[str, Any]]) -> None:
    section_sequence: list[str] = []
    for unit in units:
        if unit["section_id"] not in section_sequence:
            section_sequence.append(unit["section_id"])
    section_ordinals = {section_id: index for index, section_id in enumerate(section_sequence, 1)}
    for unit in units:
        unit["section_ordinal"] = section_ordinals[unit["section_id"]]


def _apply_operation(candidate: dict[str, Any], operation: dict[str, Any]) -> None:
    units = candidate["units"]
    operation_type = operation["operation_type"]
    target_ids = operation["target_unit_ids"]
    replacements = [_candidate_unit(spec) for spec in operation["replacement_units"]]

    if operation_type == "replace_unit_text":
        position = _exact_positions(units, target_ids)[0]
        units[position:position + 1] = replacements
    elif operation_type == "paragraph_split":
        position = _exact_positions(units, target_ids)[0]
        units[position:position + 1] = replacements
    elif operation_type == "paragraph_merge":
        positions = _exact_positions(units, target_ids)
        if positions != list(range(min(positions), max(positions) + 1)):
            _fail("application:merge_noncontiguous", "paragraph_merge targets must be contiguous")
        if [units[position]["unit_id"] for position in positions] != target_ids:
            _fail("application:merge_order", "paragraph_merge target order must equal source order")
        units[min(positions):max(positions) + 1] = replacements
    elif operation_type == "paragraph_move":
        position = _exact_positions(units, target_ids)[0]
        moved = units.pop(position)
        destination_section = operation.get("destination_section_id")
        if destination_section is not None:
            known_sections = {unit["section_id"] for unit in units} | {moved["section_id"]}
            if destination_section not in known_sections:
                _fail("application:destination_section", "paragraph_move destination section is unknown")
            moved["section_id"] = destination_section
        _insert_at(units, [moved], operation.get("destination_ordinal"))
    elif operation_type == "section_move":
        section_id = operation.get("target_section_id")
        section_units = [unit for unit in units if unit["section_id"] == section_id]
        if [unit["unit_id"] for unit in section_units] != target_ids:
            _fail("application:section_closure", "section_move target set changed during application")
        units[:] = [unit for unit in units if unit["section_id"] != section_id]
        destination_section_ordinal = operation.get("destination_ordinal")
        remaining_sections: list[str] = []
        for unit in units:
            if unit["section_id"] not in remaining_sections:
                remaining_sections.append(unit["section_id"])
        if not isinstance(destination_section_ordinal, int) or destination_section_ordinal < 1 or destination_section_ordinal > len(remaining_sections) + 1:
            _fail("application:destination", "section_move destination ordinal is invalid")
        if destination_section_ordinal == len(remaining_sections) + 1:
            units.extend(section_units)
        else:
            destination_section_id = remaining_sections[destination_section_ordinal - 1]
            insert_at = next(index for index, unit in enumerate(units) if unit["section_id"] == destination_section_id)
            units[insert_at:insert_at] = section_units
    elif operation_type == "theme_reorganization":
        positions = _exact_positions(units, target_ids)
        moved = [units[position] for position in positions]
        units[:] = [unit for unit in units if unit["unit_id"] not in set(target_ids)]
        destination_section = operation.get("destination_section_id")
        if not isinstance(destination_section, str) or destination_section not in {unit["section_id"] for unit in units}:
            _fail("application:destination_section", "theme_reorganization destination section is unknown")
        for unit in moved:
            unit["section_id"] = destination_section
        _insert_at(units, moved, operation.get("destination_ordinal"))
    elif operation_type == "draft_authorized_unit":
        _insert_at(units, replacements, operation.get("destination_ordinal"))
    else:
        _fail("application:operation", f"unsupported operation: {operation_type}")
    _refresh_section_ordinals(units)


def _change_operation(change: dict[str, Any], operations: list[dict[str, Any]]) -> dict[str, Any]:
    source_ids = set(change.get("source_unit_ids", []))
    slot_ids = set(change.get("authorized_draft_slot_ids", []))
    exact = []
    for operation in operations:
        target_ids = set(operation.get("target_unit_ids", []))
        expected_slot = operation.get("expected_slot")
        operation_slots = {expected_slot.get("slot_id")} if isinstance(expected_slot, dict) else set()
        if (source_ids and source_ids & target_ids) or (slot_ids and slot_ids == operation_slots):
            exact.append(operation)
    if len(exact) == 1:
        return exact[0]
    if not exact and "paragraph_move" in change.get("observed_effects", []):
        move_operations = [operation for operation in operations if operation.get("operation_type") in {"paragraph_move", "section_move", "theme_reorganization"}]
        if len(move_operations) == 1:
            return move_operations[0]
    _fail("manifest:operation_binding", f"changed unit does not map to exactly one operation: {change.get('inventory_change_id')}")
    raise AssertionError("unreachable")


def _query_list(source: dict[str, Any], candidate: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema_name": "review_author_query_list",
        "schema_version": "0.1.0",
        "artifact_id": f"review-author-queries:{canonical_sha256(_proposal_ref(proposal))[:24]}",
        "artifact_sha256": "0" * 64,
        "source_artifact": artifact_identity(source),
        "candidate_artifact": artifact_identity(candidate),
        "proposal_ref": _proposal_ref(proposal),
        "queries": copy.deepcopy(proposal.get("unresolved_queries", [])),
        "author_review_required": True,
    }
    value["artifact_sha256"] = payload_sha256(value, "artifact_sha256")
    return value


def apply_review_revision_proposal(
    source: dict[str, Any],
    permission: dict[str, Any],
    expected_permission_sha256: str,
    proposal: dict[str, Any],
    phase7a: dict[str, Any],
    review_profile: dict[str, Any] | None = None,
    *,
    phase7a_validator_path: Path = DEFAULT_PHASE7A_VALIDATOR,
    phase7a_schemas_dir: Path = DEFAULT_PHASE7A_SCHEMAS,
    shared_validator_path: Path = DEFAULT_SHARED_VALIDATOR,
) -> dict[str, dict[str, Any]]:
    admission_issues = validate_admission(
        source, permission, expected_permission_sha256, proposal, phase7a, review_profile,
        phase7a_validator_path=phase7a_validator_path,
        phase7a_schemas_dir=phase7a_schemas_dir,
        shared_validator_path=shared_validator_path,
    )
    if admission_issues:
        _fail("admission:blocked", json.dumps(admission_issues, ensure_ascii=False))

    candidate = copy.deepcopy(source)
    candidate["side"] = "candidate"
    candidate["artifact_id"] = proposal["candidate_artifact"]["artifact_id"]
    candidate["artifact_version"] = proposal["candidate_artifact"]["artifact_version"]
    for operation in sorted(proposal["operations"], key=lambda item: item["operation_order"]):
        _apply_operation(candidate, operation)
    refresh_document(candidate)
    lineage = build_lineage_map(source, candidate, origin="deterministic_patch_layer")
    inventory = build_inventory(source, candidate, lineage)
    queries = _query_list(source, candidate, proposal)
    application_receipt = build_application_receipt(
        source, candidate, permission, proposal, lineage, inventory, queries
    )
    changes = expected_change_records(inventory, permission, proposal)
    manifest: dict[str, Any] = {
        "schema_name": "review_change_manifest",
        "schema_version": "0.1.0",
        "artifact_id": f"review-change-manifest:{canonical_sha256(_proposal_ref(proposal))[:24]}",
        "artifact_sha256": "0" * 64,
        "source_artifact": artifact_identity(source),
        "candidate_artifact": artifact_identity(candidate),
        "permission_ref": _permission_ref(permission),
        "proposal_ref": _proposal_ref(proposal),
        "lineage_ref": _artifact_ref(lineage),
        "protected_inventory_ref": _artifact_ref(inventory),
        "author_query_list_ref": _artifact_ref(queries),
        "application_receipt_ref": _artifact_ref(application_receipt),
        "revision_mode": proposal["revision_mode"],
        "upstream_closure_refs": expected_upstream_closure_refs(phase7a, proposal),
        "changes": changes,
        "protected_change_ids": [item["protected_change_id"] for item in inventory["protected_changes"]],
        "citation_support_warnings": expected_citation_support_warnings(
            source, candidate, proposal, phase7a
        ),
        "producer_state": "ready_for_independent_qc",
        "author_review_required": True,
        "module06_handoff": {
            "interface_name": "module06_review_revision_admission",
            "interface_version": None,
            "state": "blocked_pending_module06_integration_contract",
        },
        "scientific_correctness_claimed": False,
        "qc_pass_claimed": False,
    }
    manifest["artifact_sha256"] = payload_sha256(manifest, "artifact_sha256")

    final_issues = validate_revision_package(
        source, candidate, permission, expected_permission_sha256, proposal,
        manifest, queries, lineage, inventory, phase7a, review_profile,
        phase7a_validator_path=phase7a_validator_path,
        phase7a_schemas_dir=phase7a_schemas_dir,
        shared_validator_path=shared_validator_path,
    )
    if final_issues:
        _fail("application:postcondition", json.dumps(final_issues, ensure_ascii=False))
    validation_result = build_package_validation_result(
        source, candidate, permission, proposal, manifest, application_receipt
    )
    evidence_issues = validate_revision_evidence(
        source, candidate, permission, proposal, manifest, lineage, inventory,
        queries, application_receipt, validation_result,
        shared_validator_path=shared_validator_path,
    )
    if evidence_issues:
        _fail("application:evidence", json.dumps(evidence_issues, ensure_ascii=False))
    return {
        "candidate-review.json": candidate,
        "review-revision-lineage-map.json": lineage,
        "review-protected-change-inventory.json": inventory,
        "review-author-query-list.json": queries,
        "review-change-manifest.json": manifest,
        "review-patch-application-receipt.json": application_receipt,
        "review-package-validation-result.json": validation_result,
    }


def _normalize_phase7a_paths(package: dict[str, Any], wrapper_path: Path) -> dict[str, Any]:
    for record in package.get("trusted_inputs", {}).values():
        if isinstance(record, dict) and isinstance(record.get("path"), str):
            path = Path(record["path"])
            record["path"] = str(path if path.is_absolute() else (wrapper_path.parent / path).resolve())
    return package


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-document", type=Path, required=True)
    parser.add_argument("--permission", type=Path, required=True)
    parser.add_argument("--expected-permission-sha256", required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--phase7a-package", type=Path, required=True)
    parser.add_argument("--review-profile", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--phase7a-validator", type=Path, default=DEFAULT_PHASE7A_VALIDATOR)
    parser.add_argument("--phase7a-schemas-dir", type=Path, default=DEFAULT_PHASE7A_SCHEMAS)
    parser.add_argument("--shared-validator", type=Path, default=DEFAULT_SHARED_VALIDATOR)
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args()
    try:
        verify_package_runtime_trust_root(
            schemas_dir=DEFAULT_SCHEMAS,
            phase7a_validator_path=args.phase7a_validator,
            phase7a_schemas_dir=args.phase7a_schemas_dir,
            shared_validator_path=args.shared_validator,
        )
        if args.output_dir.exists():
            raise PatchApplicationError(f"refusing to overwrite existing output directory: {args.output_dir}")
        source = read_json(args.source_document)
        permission = read_json(args.permission)
        proposal = read_json(args.proposal)
        phase7a = _normalize_phase7a_paths(read_json(args.phase7a_package), args.phase7a_package)
        review_profile = read_json(args.review_profile) if args.review_profile else None
        artifacts = apply_review_revision_proposal(
            source, permission, args.expected_permission_sha256, proposal, phase7a, review_profile,
            phase7a_validator_path=args.phase7a_validator,
            phase7a_schemas_dir=args.phase7a_schemas_dir,
            shared_validator_path=args.shared_validator,
        )
        args.output_dir.mkdir(parents=True)
        for name, value in artifacts.items():
            write_json(args.output_dir / name, value)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, PatchApplicationError) as exc:
        result = {"ok": False, "producer_state": "blocked", "error": str(exc)}
        if args.json_report:
            write_json(args.json_report, result)
        print(f"review patch error: {exc}", file=sys.stderr)
        return 1
    result = {
        "ok": True,
        "producer_state": "ready_for_independent_qc",
        "author_review_required": True,
        "module06_handoff_state": "blocked_pending_module06_integration_contract",
        "output_dir": str(args.output_dir.resolve()),
        "files": sorted(artifacts),
    }
    if args.json_report:
        write_json(args.json_report, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
