"""Synthetic, hash-bound Phase 7B fixtures built on the frozen Phase 7A factory."""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent.parent
for path in (SKILL_ROOT / "scripts",):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from build_review_change_inventory import (  # noqa: E402
    PROTECTED_CLASSES,
    artifact_identity,
    canonical_sha256,
    payload_sha256,
    refresh_document,
    text_sha256,
)
from validate_review_revision_package import (  # noqa: E402
    CLOSURE_FIELDS,
    _phase7a_refs,
    governed_subject_sha256,
    permission_payload_sha256,
)


STAMP = "2026-09-05T00:00:00Z"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load fixture dependency: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PHASE7A_FACTORY = _load(HERE.parent / "phase7a" / "fixture_factory.py", "frozen_phase7a_fixture_factory")


def clone(value: Any) -> Any:
    return copy.deepcopy(value)


def phase7a_package() -> dict[str, Any]:
    package = PHASE7A_FACTORY.build_valid_package()
    package["outline"]["section_plans"].append({
        "section_id": "section-limitations",
        "title": "Limitations of the admitted source set",
        "theme_ids": ["theme-response"],
        "paragraph_plans": [{
            "paragraph_id": "paragraph-limitations",
            "role": "limitation",
            "theme_id": "theme-response",
            "claim_ids": ["claim-response"],
            "evidence_cluster_ids": ["cluster-response"],
            "source_ids": ["source-1", "source-2"],
            "conflict_ids": ["conflict-1"],
            "limitation_ids": ["limitation-1"],
            "gap_ids": ["gap-1"],
        }],
    })
    return PHASE7A_FACTORY.rehash_package(package)


def exact_closure() -> dict[str, list[str]]:
    return {
        "claim_ids": ["claim-response"],
        "citation_relation_ids": ["relation-response"],
        "source_ids": ["source-1", "source-2"],
        "extraction_record_ids": ["extract-1", "extract-2"],
        "conflict_ids": ["conflict-1"],
        "limitation_ids": ["limitation-1"],
        "gap_ids": ["gap-1"],
        "author_position_ids": [],
        "future_direction_ids": [],
    }


def _sentence(sentence_id: str, text: str, *, claim: bool = True, relation: bool = True) -> dict[str, Any]:
    return {
        "sentence_id": sentence_id,
        "source_sentence_ids": [sentence_id],
        "authorized_draft_slot_ids": [],
        "ordinal": 0,
        "text": text,
        "claim_ids": ["claim-response"] if claim else [],
        "citation_relation_ids": ["relation-response"] if relation else [],
    }


def _source_unit(
    unit_id: str,
    section_id: str,
    section_ordinal: int,
    paragraph_plan_id: str,
    sentences: list[dict[str, Any]],
) -> dict[str, Any]:
    unit = {
        "unit_id": unit_id,
        "source_unit_ids": [unit_id],
        "authorized_draft_slot_ids": [],
        "ordinal": 0,
        "section_id": section_id,
        "section_ordinal": section_ordinal,
        "paragraph_plan_id": paragraph_plan_id,
        "text": " ".join(sentence["text"] for sentence in sentences),
        "locator": {},
        "sentences": sentences,
        **exact_closure(),
    }
    return unit


def source_document() -> dict[str, Any]:
    source: dict[str, Any] = {
        "schema_name": "review_revision_document",
        "schema_version": "0.1.0",
        "artifact_id": "review-source-draft-1",
        "artifact_version": "1.0.0",
        "artifact_sha256": "0" * 64,
        "manuscript_id": "review-manuscript-1",
        "document_type": "review_article",
        "review_type": "narrative_review",
        "side": "source",
        "units": [
            _source_unit(
                "review-unit-1", "section-response", 1, "paragraph-response",
                [
                    _sentence("review-sentence-1", "Both admitted sources report a response in the same direction [1,2]."),
                    _sentence("review-sentence-2", "This statement is limited to the admitted source set.", relation=False),
                ],
            ),
            _source_unit(
                "review-unit-2", "section-response", 1, "paragraph-response",
                [_sentence("review-sentence-3", "The evidence base remains small.", relation=False)],
            ),
            _source_unit(
                "review-unit-3", "section-limitations", 2, "paragraph-limitations",
                [_sentence("review-sentence-4", "Interpretation remains constrained by the synthetic scope.", relation=False)],
            ),
        ],
        "authorized_empty_draft_slots": [],
        "protected_terms": ["response"],
    }
    slot_id = "review-slot-future-1"
    token = f"[[AUTHORIZED_DRAFT_SLOT:{slot_id}]]"
    source["authorized_empty_draft_slots"] = [{
        "slot_id": slot_id,
        "slot_version": "0.1.0",
        "placeholder_token": token,
        "placeholder_sha256": text_sha256(token),
        "outline_paragraph_id": "paragraph-limitations",
        "section_id": "section-limitations",
        "locator": {
            "locator_type": "authorized_empty_draft_slot",
            "side": "source",
            "artifact_id": source["artifact_id"],
            "unit_id": slot_id,
            "span_sha256": text_sha256(token),
        },
    }]
    refresh_document(source)
    return source


def _permission_decision(
    source: dict[str, Any],
    package: dict[str, Any],
    operation_type: str,
    target_unit_ids: list[str],
    *,
    slot_id: str | None = None,
) -> dict[str, Any]:
    units = {unit["unit_id"]: unit for unit in source["units"]}
    if slot_id is not None:
        subject_type = "authorized_empty_draft_slot"
        subject = next(slot for slot in source["authorized_empty_draft_slots"] if slot["slot_id"] == slot_id)
        subject_id = slot_id
        subject_version = subject["slot_version"]
        decision_type = "review_draft_slot_materialization"
        allowlist = [
            {
                "materialization_id": "materialization-citation-1",
                "protected_class": "citation",
                "candidate_token": "[1,2]",
                "identity": "numeric_bracket:[1,2]",
                "source_ids": ["source-1", "source-2"],
                "citation_relation_ids": ["relation-response"],
                "extraction_record_ids": ["extract-1", "extract-2"],
            },
            {
                "materialization_id": "materialization-term-1",
                "protected_class": "terminology",
                "candidate_token": "response",
                "identity": "response",
                "source_ids": ["source-1", "source-2"],
                "citation_relation_ids": ["relation-response"],
                "extraction_record_ids": ["extract-1", "extract-2"],
            },
        ]
        required = ["materialization-citation-1", "materialization-term-1"]
    else:
        subject_type = "source_unit"
        subject_id = target_unit_ids[0]
        subject = units[subject_id]
        subject_version = source["artifact_version"]
        decision_type = "review_structural_revision"
        allowlist = []
        required = []
    return {
        "decision_id": f"review-decision-{operation_type}-1",
        "decision_type": decision_type,
        "governed_subject_type": subject_type,
        "governed_subject_id": subject_id,
        "governed_subject_version": subject_version,
        "governed_subject_sha256": governed_subject_sha256(subject),
        "allowed_operation": operation_type,
        "affected_source_unit_ids": list(target_unit_ids),
        "affected_paragraph_ids": sorted({units[unit_id]["paragraph_plan_id"] for unit_id in target_unit_ids}) if target_unit_ids else [subject["outline_paragraph_id"]],
        "affected_section_ids": sorted({units[unit_id]["section_id"] for unit_id in target_unit_ids}) if target_unit_ids else [subject["section_id"]],
        "affected_draft_slot_ids": [slot_id] if slot_id else [],
        "phase7a_closure": exact_closure(),
        "materialization_allowlist": allowlist,
        "required_materialization_ids": required,
        "authorization_origin": "author",
        "authorization_state": "author_approved",
        "authorization_provenance": "synthetic-author-review-record-1",
    }


def permission(
    source: dict[str, Any],
    package: dict[str, Any],
    mode: str,
    *,
    operation_type: str = "replace_unit_text",
    target_unit_ids: list[str] | None = None,
    slot_id: str | None = None,
) -> dict[str, Any]:
    targets = target_unit_ids if target_unit_ids is not None else ["review-unit-2"]
    decisions = []
    if operation_type != "replace_unit_text":
        decisions.append(_permission_decision(source, package, operation_type, targets, slot_id=slot_id))
    value: dict[str, Any] = {
        "schema_name": "review_revision_permission",
        "schema_version": "0.1.0",
        "permission_id": f"review-permission-{mode}-{operation_type}-1",
        "permission_sha256": "0" * 64,
        "interface_name": "module04_review_revision_admission",
        "interface_version": "0.1.0",
        "created_at": STAMP,
        "created_by": "synthetic-authorized-workflow",
        "creator_role": "calling_workflow",
        "authorization_origin": "calling_workflow",
        "authorization_state": "caller_accepted",
        "document_type": "review_article",
        "review_type": source["review_type"],
        "source_artifact": artifact_identity(source),
        "phase7a_closure": _phase7a_refs(package),
        "authorized_source_unit_ids": [unit["unit_id"] for unit in source["units"]],
        "authorized_empty_draft_slots": clone(source["authorized_empty_draft_slots"]),
        "revision_mode": mode,
        "allowed_operations": [operation_type],
        "prohibited_operations": sorted({"replace_unit_text", "paragraph_split", "paragraph_merge", "paragraph_move", "section_move", "theme_reorganization", "draft_authorized_unit"} - {operation_type}),
        "protected_anchor_ids": [],
        "authorized_decisions": decisions,
        "comparison_qc_scope": {
            "exact_source_candidate_comparison": True,
            "protected_classes": sorted(PROTECTED_CLASSES),
            "module06_handoff_state": "blocked_pending_module06_integration_contract",
        },
        "author_review_required": True,
    }
    value["permission_sha256"] = permission_payload_sha256(value)
    return value


def _expected_targets(source: dict[str, Any], target_ids: list[str]) -> list[dict[str, Any]]:
    index = {unit["unit_id"]: unit for unit in source["units"]}
    return [
        {"unit_id": unit_id, "unit_sha256": canonical_sha256(index[unit_id]), "locator": clone(index[unit_id]["locator"])}
        for unit_id in target_ids
    ]


def replacement_from_unit(
    unit: dict[str, Any],
    *,
    candidate_unit_id: str | None = None,
    sentences: list[dict[str, Any]] | None = None,
    source_unit_ids: list[str] | None = None,
) -> dict[str, Any]:
    source_sentences = sentences if sentences is not None else [{
        "candidate_sentence_id": sentence["sentence_id"],
        "source_sentence_ids": list(sentence["source_sentence_ids"]),
        "authorized_draft_slot_ids": [],
        "text": sentence["text"],
        "claim_ids": list(sentence["claim_ids"]),
        "citation_relation_ids": list(sentence["citation_relation_ids"]),
    } for sentence in unit["sentences"]]
    return {
        "candidate_unit_id": candidate_unit_id or unit["unit_id"],
        "source_unit_ids": list(source_unit_ids if source_unit_ids is not None else unit["source_unit_ids"]),
        "authorized_draft_slot_ids": [],
        "section_id": unit["section_id"],
        "section_ordinal": unit["section_ordinal"],
        "paragraph_plan_id": unit["paragraph_plan_id"],
        "sentences": source_sentences,
        **{field: list(unit[field]) for field in CLOSURE_FIELDS},
    }


def proposal(
    source: dict[str, Any],
    permission_value: dict[str, Any],
    mode: str,
    operation: dict[str, Any],
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema_name": "review_revision_proposal",
        "schema_version": "0.1.0",
        "proposal_id": f"review-proposal-{mode}-{operation['operation_type']}-1",
        "proposal_sha256": "0" * 64,
        "created_at": STAMP,
        "created_by": "synthetic-model",
        "proposal_origin": "model_proposed",
        "status": "machine_proposed",
        "document_type": "review_article",
        "review_type": source["review_type"],
        "source_artifact": artifact_identity(source),
        "candidate_artifact": {"artifact_id": f"review-candidate-{mode}-{operation['operation_type']}-1", "artifact_version": "0.1.0"},
        "permission_ref": {
            "permission_id": permission_value["permission_id"],
            "permission_version": permission_value["schema_version"],
            "permission_sha256": permission_value["permission_sha256"],
        },
        "revision_mode": mode,
        "operations": [operation],
        "unresolved_queries": [],
        "profile_alignment": None,
        "author_review_required": True,
    }
    value["proposal_sha256"] = payload_sha256(value, "proposal_sha256")
    return value


def refresh_proposal(value: dict[str, Any]) -> None:
    value["proposal_sha256"] = payload_sha256(value, "proposal_sha256")


def refresh_permission_and_binding(case: dict[str, Any], *, update_expected: bool = True) -> None:
    case["permission"]["permission_sha256"] = permission_payload_sha256(case["permission"])
    case["proposal"]["permission_ref"] = {
        "permission_id": case["permission"]["permission_id"],
        "permission_version": case["permission"]["schema_version"],
        "permission_sha256": case["permission"]["permission_sha256"],
    }
    refresh_proposal(case["proposal"])
    if update_expected:
        case["expected_permission_sha256"] = case["permission"]["permission_sha256"]


def review_profile_artifact(*, corpus_type: str = "review_article") -> dict[str, Any]:
    return {
        "schema_name": "structure_profile",
        "schema_version": "0.2.2",
        "artifact_id": "structure-profile:synthetic-review",
        "created_at": STAMP,
        "created_by": "style-and-structure-distiller/0.2.6",
        "source_artifact_ids": ["corpus-manifest:synthetic-review"],
        "source_files": [],
        "status": "author_approved",
        "warnings": [],
        "corpus_id": "synthetic-review",
        "corpus_type": corpus_type,
        "document_count": 2,
        "section_presence": {},
        "common_canonical_sequences": [],
        "section_instances_per_document": {},
        "paragraphs_per_document_section": {},
        "heading_depth_per_document": {},
        "child_edge_count_per_document_canonical_section": {},
        "mean_direct_children_per_root_section_instance_by_document": {},
        "figure_references_per_document_section": {},
        "feature_support": {
            "heading.max_depth": {"feature_id": "heading.max_depth"},
        },
        "deterministic_only": True,
        "semantic_annotation_status": "not_performed_phase3_1",
        "semantic_role_labels_present": False,
    }


def bind_profile(case: dict[str, Any], profile: dict[str, Any]) -> None:
    case["review_profile"] = profile
    case["proposal"]["profile_alignment"] = {
        "profile_id": profile["artifact_id"],
        "profile_version": profile["schema_version"],
        "profile_sha256": canonical_sha256(profile),
        "document_type": "review_article",
        "corpus_type": "review_only",
        "review_state": "reviewed",
        "stale": False,
        "feature_id": "heading.max_depth",
        "support_locator": "feature_support.heading.max_depth",
    }
    refresh_proposal(case["proposal"])


def light_case() -> dict[str, Any]:
    phase7a = phase7a_package()
    source = source_document()
    target = source["units"][1]
    replacement = replacement_from_unit(target)
    replacement["sentences"][0]["text"] = "The evidence base remains limited."
    permission_value = permission(source, phase7a, "light")
    operation = {
        "operation_id": "review-operation-light-1", "operation_order": 1, "operation_type": "replace_unit_text",
        "target_unit_ids": [target["unit_id"]], "target_section_id": None, "destination_section_id": None, "destination_ordinal": None,
        "expected_targets": _expected_targets(source, [target["unit_id"]]), "expected_slot": None,
        "replacement_units": [replacement], "phase7a_closure": exact_closure(), "affected_protected_anchor_ids": [], "permission_decision_id": None,
        "rationale": "Improve local wording without changing scientific anchors.", "risk_class": "low", "author_review_required": True,
    }
    proposal_value = proposal(source, permission_value, "light", operation)
    return {"source": source, "phase7a": phase7a, "permission": permission_value, "expected_permission_sha256": permission_value["permission_sha256"], "proposal": proposal_value}


def medium_case() -> dict[str, Any]:
    phase7a = phase7a_package()
    source = source_document()
    target = source["units"][0]
    reversed_sentences = []
    for sentence in reversed(target["sentences"]):
        reversed_sentences.append({
            "candidate_sentence_id": sentence["sentence_id"], "source_sentence_ids": [sentence["sentence_id"]],
            "authorized_draft_slot_ids": [], "text": sentence["text"], "claim_ids": list(sentence["claim_ids"]),
            "citation_relation_ids": list(sentence["citation_relation_ids"]),
        })
    replacement = replacement_from_unit(target, sentences=reversed_sentences)
    permission_value = permission(source, phase7a, "medium")
    operation = {
        "operation_id": "review-operation-medium-1", "operation_order": 1, "operation_type": "replace_unit_text",
        "target_unit_ids": [target["unit_id"]], "target_section_id": None, "destination_section_id": None, "destination_ordinal": None,
        "expected_targets": _expected_targets(source, [target["unit_id"]]), "expected_slot": None,
        "replacement_units": [replacement], "phase7a_closure": exact_closure(), "affected_protected_anchor_ids": [], "permission_decision_id": None,
        "rationale": "Reorder sentences within one approved paragraph.", "risk_class": "moderate", "author_review_required": True,
    }
    proposal_value = proposal(source, permission_value, "medium", operation)
    return {"source": source, "phase7a": phase7a, "permission": permission_value, "expected_permission_sha256": permission_value["permission_sha256"], "proposal": proposal_value}


def deep_move_case() -> dict[str, Any]:
    phase7a = phase7a_package()
    source = source_document()
    target_ids = ["review-unit-2"]
    permission_value = permission(source, phase7a, "deep", operation_type="paragraph_move", target_unit_ids=target_ids)
    decision_id = permission_value["authorized_decisions"][0]["decision_id"]
    operation = {
        "operation_id": "review-operation-deep-move-1", "operation_order": 1, "operation_type": "paragraph_move",
        "target_unit_ids": target_ids, "target_section_id": None, "destination_section_id": "section-response", "destination_ordinal": 1,
        "expected_targets": _expected_targets(source, target_ids), "expected_slot": None, "replacement_units": [],
        "phase7a_closure": exact_closure(), "affected_protected_anchor_ids": [], "permission_decision_id": decision_id,
        "rationale": "Move one author-approved paragraph within its section.", "risk_class": "high", "author_review_required": True,
    }
    proposal_value = proposal(source, permission_value, "deep", operation)
    return {"source": source, "phase7a": phase7a, "permission": permission_value, "expected_permission_sha256": permission_value["permission_sha256"], "proposal": proposal_value}


def draft_case() -> dict[str, Any]:
    phase7a = phase7a_package()
    source = source_document()
    slot = source["authorized_empty_draft_slots"][0]
    permission_value = permission(source, phase7a, "deep", operation_type="draft_authorized_unit", target_unit_ids=[], slot_id=slot["slot_id"])
    replacement = {
        "candidate_unit_id": "review-drafted-unit-1", "source_unit_ids": [], "authorized_draft_slot_ids": [slot["slot_id"]],
        "section_id": slot["section_id"], "section_ordinal": 2, "paragraph_plan_id": slot["outline_paragraph_id"],
        "sentences": [{
            "candidate_sentence_id": "review-drafted-sentence-1", "source_sentence_ids": [], "authorized_draft_slot_ids": [slot["slot_id"]],
            "text": "Both admitted sources describe the response [1,2].", "claim_ids": ["claim-response"],
            "citation_relation_ids": ["relation-response"],
        }],
        **exact_closure(),
    }
    operation = {
        "operation_id": "review-operation-draft-1", "operation_order": 1, "operation_type": "draft_authorized_unit",
        "target_unit_ids": [], "target_section_id": None, "destination_section_id": slot["section_id"], "destination_ordinal": 4,
        "expected_targets": [], "expected_slot": clone(slot), "replacement_units": [replacement], "phase7a_closure": exact_closure(),
        "affected_protected_anchor_ids": [], "permission_decision_id": permission_value["authorized_decisions"][0]["decision_id"],
        "rationale": "Materialize one exact author-approved empty Review slot.", "risk_class": "high", "author_review_required": True,
    }
    proposal_value = proposal(source, permission_value, "deep", operation)
    return {"source": source, "phase7a": phase7a, "permission": permission_value, "expected_permission_sha256": permission_value["permission_sha256"], "proposal": proposal_value}
