#!/usr/bin/env python3
"""Validate an Article Polisher revision package before independent Phase 5 QC.

This validator rebuilds the change inventory itself. It does not trust the
model-declared operation type, change coverage, authorization state, or Deep
artifact closure.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from build_change_inventory import (
    InventoryError,
    build_inventory,
    canonical_sha256,
    document_sha256,
    read_json,
    validate_document,
    validate_lineage_map,
    write_json,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMAS = PACKAGE_ROOT / "schemas"
DEFAULT_VALIDATOR = PACKAGE_ROOT / "shared-core" / "scripts" / "validate_artifact.py"
PHASE5_SHARED_SCHEMA = DEFAULT_SCHEMAS / "qc-shared-definitions.schema.json"
PHASE4_SCHEMAS = {
    "manuscript_plan": PACKAGE_ROOT / "upstream-schemas" / "manuscript-plan.schema.json",
    "claim_evidence_map": PACKAGE_ROOT / "upstream-schemas" / "claim-evidence-map.schema.json",
    "interpretation_card": PACKAGE_ROOT / "upstream-schemas" / "interpretation-card.schema.json",
    "style_profile": PACKAGE_ROOT / "upstream-schemas" / "style-profile.schema.json",
    "structure_profile": PACKAGE_ROOT / "upstream-schemas" / "structure-profile.schema.json",
}

STRUCTURAL_EFFECT_TO_OPERATION = {
    "sentence_order_changed": "sentence_reorder",
    "sentence_split": "sentence_split",
    "sentence_merge": "sentence_merge",
    "paragraph_split": "paragraph_split",
    "paragraph_merge": "paragraph_merge",
    "paragraph_move": "paragraph_move",
}
PARAGRAPH_EFFECTS = {"paragraph_split", "paragraph_merge", "paragraph_move"}
LIGHT_FORBIDDEN_EFFECTS = {
    "sentence_order_changed", "sentence_count_changed", "sentence_split", "sentence_merge",
    "paragraph_split", "paragraph_merge", "paragraph_move", "section_membership_changed",
    "unit_added", "unit_removed",
}
LIGHT_DECLARED_OPERATIONS = {
    "grammar", "punctuation", "syntax", "clarity", "lexical_tightening",
    "redundancy_removal", "transition",
}
MEDIUM_FORBIDDEN_EFFECTS = {
    "paragraph_split", "paragraph_merge", "paragraph_move", "section_membership_changed",
    "unit_added", "unit_removed",
}


class PackageValidationError(RuntimeError):
    """Raised when the package cannot be read or its validator cannot load."""


def _load_validator(path: Path | None) -> ModuleType:
    from schema_runtime import discover_validator, load_validator
    return load_validator(discover_validator(path))


def _schema_issues(module: ModuleType, schema_path: Path, data_path: Path) -> list[dict[str, str]]:
    return [
        {"layer": "schema", "path": issue.path, "code": f"schema:{issue.keyword}", "message": issue.message}
        for issue in module.validate_files(schema_path.resolve(), data_path.resolve())
    ]


def _revision_contract_schema_issues(module: ModuleType, contract: dict[str, Any]) -> list[dict[str, str]]:
    root = json.loads(PHASE5_SHARED_SCHEMA.read_text(encoding="utf-8"))
    store = module.SchemaStore()
    raw = module.validate_instance(
        contract,
        root["$defs"]["revisionContract"],
        PHASE5_SHARED_SCHEMA.resolve(),
        root,
        store,
        "$.revision_contract",
    )
    return [
        {"layer": "schema", "path": issue.path, "code": f"schema:{issue.keyword}", "message": issue.message}
        for issue in raw
    ]


def _artifact_identity(document: dict[str, Any]) -> dict[str, str]:
    return {
        "document_id": document["document_id"],
        "artifact_id": document["artifact_id"],
        "artifact_version": document["artifact_version"],
        "artifact_sha256": document["artifact_sha256"],
    }


def _contract_payload_hash(contract: dict[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in contract.items() if key != "contract_sha256"})


def _artifact_type(value: dict[str, Any]) -> str | None:
    schema_name = value.get("schema_name")
    return schema_name if schema_name in PHASE4_SCHEMAS else None


def _artifact_reference(actual: dict[str, Any]) -> dict[str, str]:
    """Build the only upstream identity accepted by provenance gates."""
    value = actual["value"]
    return {
        "artifact_id": value["artifact_id"],
        "artifact_type": actual["artifact_type"],
        "artifact_version": actual["artifact_version"],
        "artifact_sha256": actual["artifact_sha256"],
    }


def _bound_upstream_artifacts(
    record_refs: dict[str, dict[str, Any]],
    upstream_artifacts: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Exclude absent or identity-mismatched artifacts from authority decisions."""
    return {
        artifact_id: actual
        for artifact_id, actual in upstream_artifacts.items()
        if record_refs.get(artifact_id) == _artifact_reference(actual)
    }


def _nested_author_approvals_are_approved(value: Any) -> bool:
    """Reject any nested approval state that contradicts author-approved authority."""
    if isinstance(value, dict):
        if "author_approval" in value and value.get("author_approval") != "approved":
            return False
        return all(_nested_author_approvals_are_approved(child) for child in value.values())
    if isinstance(value, list):
        return all(_nested_author_approvals_are_approved(child) for child in value)
    return True


def _author_decisions_are_terminal(value: Any) -> bool:
    """Require every declared author decision to be explicitly approved or rejected."""
    return isinstance(value, list) and all(
        isinstance(item, dict) and item.get("status") in {"approved", "rejected"}
        for item in value
    )


def _plan_gaps_are_terminal(value: Any) -> bool:
    """Require every declared plan gap to be resolved or accepted as a risk."""
    return isinstance(value, list) and all(
        isinstance(item, dict) and item.get("status") in {"resolved", "accepted_risk"}
        for item in value
    )


def _author_approved_plan_is_consistent(plan: dict[str, Any]) -> bool:
    """Fresh-check the approval-state invariants M03 relies on for plan authority."""
    summary = plan.get("approval_summary")
    return (
        plan.get("status") == "author_approved"
        and isinstance(summary, dict)
        and summary.get("overall_status") == "approved"
        and type(summary.get("pending_decision_count")) is int
        and summary["pending_decision_count"] == 0
        and type(summary.get("open_blocker_count")) is int
        and summary["open_blocker_count"] == 0
        and _nested_author_approvals_are_approved(plan)
        and _author_decisions_are_terminal(plan.get("author_decisions"))
        and _plan_gaps_are_terminal(plan.get("gaps_and_risks"))
    )


def _author_approved_claim_map_is_consistent(claim_map: dict[str, Any]) -> bool:
    """Fresh-check approval state before a claim map can act as M03 authority."""
    return (
        claim_map.get("status") == "author_approved"
        and _nested_author_approvals_are_approved(claim_map)
        and _author_decisions_are_terminal(claim_map.get("author_decisions"))
    )


def _author_approved_interpretation_card_is_consistent(
    card: dict[str, Any],
    manuscript_id: str,
) -> bool:
    """Fresh-check approval and manuscript identity before card authority is used."""
    return (
        card.get("status") == "author_approved"
        and card.get("document_type") == "original_article"
        and card.get("manuscript_id") == manuscript_id
        and _nested_author_approvals_are_approved(card)
        and _author_decisions_are_terminal(card.get("author_decisions"))
    )


def _approved_paragraph_baselines(
    source_document_id: str,
    source_unit_ids: set[str],
    bound_artifacts: dict[str, dict[str, Any]],
) -> list[dict[str, set[str]]]:
    """Return exact, author-approved paragraph bindings and their claim/evidence IDs."""
    baselines: list[dict[str, set[str]]] = []
    for actual in bound_artifacts.values():
        if (
            actual.get("artifact_type") != "manuscript_plan"
            or not _author_approved_plan_is_consistent(actual["value"])
            or actual["value"].get("document_type") != "original_article"
            or actual["value"].get("manuscript_id") != source_document_id
        ):
            continue
        for section in actual["value"].get("section_plans", []):
            for paragraph in section.get("paragraph_plans", []):
                paragraph_sources = set(paragraph.get("source_paragraph_ids", []))
                claims = set(paragraph.get("claim_ids", []))
                evidence = set(paragraph.get("evidence_ids", []))
                if (
                    paragraph_sources == source_unit_ids
                    and paragraph.get("author_approval") == "approved"
                    and claims
                    and evidence
                ):
                    baselines.append({"claim_ids": claims, "evidence_ids": evidence})
    return baselines


def _claim_map_resolves_propositions(
    source_document_id: str,
    source_unit_ids: set[str],
    source_proposition_ids: set[str],
    baselines: list[dict[str, set[str]]],
    bound_artifacts: dict[str, dict[str, Any]],
) -> bool:
    """Resolve every proposition to the affected paragraph in an approved claim map."""
    if not source_proposition_ids:
        return False
    baseline_claims = set().union(*(item["claim_ids"] for item in baselines)) if baselines else set()
    for actual in bound_artifacts.values():
        if (
            actual.get("artifact_type") != "claim_evidence_map"
            or not _author_approved_claim_map_is_consistent(actual["value"])
            or actual["value"].get("document_type") != "original_article"
            or actual["value"].get("manuscript_id") != source_document_id
        ):
            continue
        claims = {
            item.get("claim_id"): item
            for item in actual["value"].get("claim_records", [])
            if isinstance(item, dict)
        }
        if not source_proposition_ids.issubset(claims):
            continue
        covered: set[str] = set()
        valid = True
        for proposition_id in source_proposition_ids:
            claim = claims[proposition_id]
            if claim.get("author_approval") != "approved":
                valid = False
                break
            located = {
                locator.get("paragraph_id")
                for locator in claim.get("source_locators", [])
                if isinstance(locator, dict)
                and locator.get("document_id") == source_document_id
            }
            direct = located & source_unit_ids
            approved_plan_binding = proposition_id in baseline_claims
            if direct:
                covered.update(direct)
            elif approved_plan_binding:
                covered.update(source_unit_ids)
            else:
                valid = False
                break
        if valid and source_unit_ids.issubset(covered):
            return True
    return False


def _approved_claim_evidence_relations(
    source_document_id: str,
    source_unit_ids: set[str],
    source_proposition_ids: set[str],
    baselines: list[dict[str, set[str]]],
    bound_artifacts: dict[str, dict[str, Any]],
) -> bool:
    """Require the Results/Discussion baseline to close through approved claim/evidence links."""
    if not baselines or not source_proposition_ids:
        return False
    for baseline in baselines:
        if not source_proposition_ids.issubset(baseline["claim_ids"]):
            continue
        for actual in bound_artifacts.values():
            if (
                actual.get("artifact_type") != "claim_evidence_map"
                or not _author_approved_claim_map_is_consistent(actual["value"])
                or actual["value"].get("document_type") != "original_article"
                or actual["value"].get("manuscript_id") != source_document_id
            ):
                continue
            value = actual["value"]
            claims = {item.get("claim_id"): item for item in value.get("claim_records", [])}
            evidence = {item.get("evidence_id"): item for item in value.get("evidence_records", [])}
            links = value.get("claim_evidence_links", [])
            if not source_proposition_ids.issubset(claims):
                continue
            valid = True
            for proposition_id in source_proposition_ids:
                claim = claims[proposition_id]
                if claim.get("author_approval") != "approved":
                    valid = False
                    break
                relevant_evidence = set(claim.get("evidence_ids", [])) & baseline["evidence_ids"]
                approved_evidence = {
                    evidence_id
                    for evidence_id in relevant_evidence
                    if evidence.get(evidence_id, {}).get("author_approval") == "approved"
                }
                if not approved_evidence or not any(
                    link.get("claim_id") == proposition_id
                    and link.get("evidence_id") in approved_evidence
                    and link.get("scope_match") is True
                    and link.get("author_approval") == "approved"
                    for link in links
                    if isinstance(link, dict)
                ):
                    valid = False
                    break
            if valid and _claim_map_resolves_propositions(
                source_document_id,
                source_unit_ids,
                source_proposition_ids,
                [baseline],
                bound_artifacts,
            ):
                return True
    return False


def _resolve_json_pointer(value: Any, pointer: str) -> Any:
    """Resolve a strict JSON Pointer; malformed or absent paths return None."""
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return None
    current = value
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            return None
        current = current[token]
    return current


def _reviewed_profile_supports_feature(
    profile_feature_ref: dict[str, Any],
    bound_artifacts: dict[str, dict[str, Any]],
) -> bool:
    """Bind a profile rationale to an actual approved M01 feature-support record."""
    if not isinstance(profile_feature_ref, dict):
        return False
    actual = bound_artifacts.get(profile_feature_ref.get("profile_id"))
    if actual is None or actual.get("artifact_type") not in {"style_profile", "structure_profile"}:
        return False
    value = actual["value"]
    if value.get("status") != "author_approved" or value.get("corpus_type") != "original_article":
        return False
    if (
        value.get("artifact_id") != profile_feature_ref.get("profile_id")
        or value.get("schema_version") != profile_feature_ref.get("profile_version")
        or actual.get("artifact_sha256") != profile_feature_ref.get("profile_sha256")
    ):
        return False
    support = _resolve_json_pointer(value, profile_feature_ref.get("feature_support_ref"))
    return (
        isinstance(support, dict)
        and support.get("feature_id") == profile_feature_ref.get("feature_id")
        and isinstance(support.get("document_count"), int)
        and support["document_count"] > 0
        and isinstance(support.get("document_coverage"), (int, float))
        and support["document_coverage"] > 0
    )


def provenance_gate_issues(
    record: dict[str, Any],
    source_document_id: str,
    source_unit_ids: set[str],
    section: str | None,
    upstream_artifacts: dict[str, dict[str, Any]],
) -> list[tuple[str, str]]:
    """Enforce provenance gates independently of proposal syntax and declared labels."""
    record_refs = {
        item.get("artifact_id"): item
        for item in record.get("upstream_artifact_refs", [])
        if isinstance(item, dict) and isinstance(item.get("artifact_id"), str)
    }
    bound = _bound_upstream_artifacts(record_refs, upstream_artifacts)
    propositions = set(record.get("source_proposition_ids", []))
    baselines = _approved_paragraph_baselines(
        source_document_id, source_unit_ids, bound
    )
    issues: list[tuple[str, str]] = []

    if (
        record.get("operation_type") == "information_reorder"
        and section in {"results", "discussion"}
        and not _approved_claim_evidence_relations(
            source_document_id, source_unit_ids, propositions, baselines, bound
        )
    ):
        issues.append((
            "medium:missing_approved_baseline",
            "Results/Discussion information_reorder requires an exact approved paragraph baseline and approved claim/evidence relation closure",
        ))

    if record.get("operation_type") == "topic_sentence_repair":
        if not propositions:
            issues.append((
                "topic_sentence:missing_proposition",
                "topic-sentence repair requires a source proposition or approved claim ID",
            ))
        elif not _claim_map_resolves_propositions(
            source_document_id, source_unit_ids, propositions, baselines, bound
        ):
            issues.append((
                "topic_sentence:unresolved_proposition",
                "topic-sentence repair proposition is not resolved to the affected paragraph by supplied, hash-bound approved upstream provenance",
            ))

    if record.get("rationale") == "profile_alignment":
        profile_ref = record.get("profile_feature_ref")
        if not isinstance(profile_ref, dict):
            issues.append((
                "profile:missing_feature_ref",
                "profile_alignment requires an exact reviewed profile-feature reference",
            ))
        elif not _reviewed_profile_supports_feature(profile_ref, bound):
            issues.append((
                "profile:unbound_feature",
                "profile_alignment feature is not resolved in a supplied, hash-bound, author-approved Original Article M01 profile",
            ))
    return issues


def _plan_contains_approved_structural_decision(actual: dict[str, Any], structural_id: str) -> bool:
    """Verify that a Deep ID is an approved Phase 4 material-reordering decision."""
    if actual.get("artifact_type") != "manuscript_plan" or not _author_approved_plan_is_consistent(actual["value"]):
        return False
    return any(
        item.get("decision_id") == structural_id
        and item.get("decision_type") == "material_reordering"
        and item.get("status") == "approved"
        for item in actual["value"].get("author_decisions", [])
    )


def _approved_structural_decision(actual: dict[str, Any], structural_id: str) -> dict[str, Any] | None:
    if actual.get("artifact_type") != "manuscript_plan" or not _author_approved_plan_is_consistent(actual["value"]):
        return None
    return next((
        item for item in actual["value"].get("author_decisions", [])
        if item.get("decision_id") == structural_id
        and item.get("decision_type") == "material_reordering"
        and item.get("status") == "approved"
    ), None)


def _deep_referenced_artifact_closure(
    plan: dict[str, Any],
    decision: dict[str, Any],
    bound_artifacts: dict[str, dict[str, Any]],
) -> bool:
    """Derive richer closure from IDs actually referenced by an approved decision."""
    value = plan["value"]
    related = set(decision.get("related_ids", []))
    claim_ids: set[str] = set()
    evidence_ids: set[str] = set()
    for section in value.get("section_plans", []):
        claim_ids.update(section.get("claim_ids", []))
        for paragraph in section.get("paragraph_plans", []):
            claim_ids.update(paragraph.get("claim_ids", []))
            evidence_ids.update(paragraph.get("evidence_ids", []))

    referenced_claims = related & claim_ids
    referenced_evidence = related & evidence_ids
    if referenced_claims or referenced_evidence:
        map_id = value.get("claim_evidence_map_id")
        actual = bound_artifacts.get(map_id)
        if actual is None:
            return False
        if actual.get("artifact_type") != "claim_evidence_map" or not _author_approved_claim_map_is_consistent(actual["value"]):
            return False
        actual_claims = {item.get("claim_id") for item in actual["value"].get("claim_records", [])}
        actual_evidence = {item.get("evidence_id") for item in actual["value"].get("evidence_records", [])}
        if not referenced_claims.issubset(actual_claims) or not referenced_evidence.issubset(actual_evidence):
            return False

    card_ids = set(value.get("interpretation_card_ids", []))
    direct_cards = related & card_ids
    # Boundary provenance is determined by the explicit Phase 4 identifier
    # namespace used in the approved decision, not by story-anchor importance.
    # A non-key boundary is still a referenced boundary and must resolve through
    # an exact, plan-listed interpretation card below.
    referenced_boundaries = {
        reference_id
        for reference_id in related
        if isinstance(reference_id, str) and reference_id.startswith("boundary:")
    }
    for card_id in direct_cards:
        actual = bound_artifacts.get(card_id)
        if actual is None:
            return False
        if (
            actual.get("artifact_type") != "interpretation_card"
            or not _author_approved_interpretation_card_is_consistent(
                actual["value"], value.get("manuscript_id")
            )
        ):
            return False
    for boundary_id in referenced_boundaries:
        if not any(
            card_id in card_ids
            and (actual := bound_artifacts.get(card_id)) is not None
            and actual.get("artifact_type") == "interpretation_card"
            and _author_approved_interpretation_card_is_consistent(
                actual["value"], value.get("manuscript_id")
            )
            and actual["value"].get("boundary", {}).get("boundary_id") == boundary_id
            for card_id in card_ids
        ):
            return False
    return True


def _read_upstream_artifacts(
    paths: list[Path],
    validator: ModuleType,
    issues: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    artifacts: dict[str, dict[str, Any]] = {}
    for path in paths:
        value = read_json(path)
        artifact_id = value.get("artifact_id")
        artifact_type = _artifact_type(value)
        if not isinstance(artifact_id, str) or not artifact_id:
            issues.append({"layer": "upstream", "path": str(path), "code": "upstream:identity", "message": "upstream artifact lacks artifact_id"})
            continue
        if artifact_id in artifacts:
            issues.append({"layer": "upstream", "path": str(path), "code": "upstream:duplicate", "message": f"duplicate upstream artifact_id: {artifact_id}"})
            continue
        if artifact_type is None:
            issues.append({"layer": "upstream", "path": str(path), "code": "upstream:type", "message": f"unsupported upstream schema_name: {value.get('schema_name')}"})
            continue
        issues.extend(_schema_issues(validator, PHASE4_SCHEMAS[artifact_type], path))
        artifacts[artifact_id] = {
            "value": value,
            "path": path,
            "artifact_type": artifact_type,
            "artifact_version": value.get("schema_version"),
            "artifact_sha256": canonical_sha256(value),
        }
    return artifacts


def validate_revision_package(
    source: dict[str, Any],
    candidate: dict[str, Any],
    contract: dict[str, Any],
    manifest: dict[str, Any],
    queries: dict[str, Any],
    upstream_artifacts: dict[str, dict[str, Any]],
    lineage_map: dict[str, Any] | None = None,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Return semantic issues and the independently rebuilt inventory."""
    issues: list[dict[str, str]] = []

    def add(code: str, message: str, path: str = "$") -> None:
        issues.append({"layer": "semantic", "path": path, "code": code, "message": message})

    document_issues = validate_document(source, "source") + validate_document(candidate, "candidate")
    for message in document_issues:
        add("document:invalid", message)
    lineage_issues = validate_lineage_map(source, candidate, lineage_map)
    for issue in lineage_issues:
        add(issue["code"], issue["message"])
    if source.get("document_id") != candidate.get("document_id"):
        add("identity:document", "source and candidate document_id values differ")
    if document_issues or lineage_issues:
        return issues, {
            "inventory_name": "article_polisher_change_inventory",
            "inventory_version": "0.1.1",
            "structural_footprint": {},
            "lineage_conflicts": [],
            "changed_units": [],
        }

    inventory = build_inventory(source, candidate, lineage_map)
    source_identity = _artifact_identity(source)
    candidate_identity = _artifact_identity(candidate)

    if source["artifact_sha256"] != document_sha256(source):
        add("identity:source_hash", "source artifact hash is invalid")
    if candidate["artifact_sha256"] != document_sha256(candidate):
        add("identity:candidate_hash", "candidate artifact hash is invalid")
    if contract.get("contract_sha256") != _contract_payload_hash(contract):
        add("contract:hash", "contract_sha256 does not match the canonical contract payload")
    if contract.get("source_document_id") != source["document_id"]:
        add("contract:source_document", "revision contract source_document_id does not match source")
    if contract.get("source_artifact_id") != source["artifact_id"]:
        add("contract:source_artifact", "revision contract source_artifact_id does not match source")
    if contract.get("source_artifact_version") != source["artifact_version"]:
        add("contract:source_version", "revision contract source_artifact_version does not match source")
    if contract.get("source_artifact_sha256") != source["artifact_sha256"]:
        add("contract:source_hash", "revision contract source_artifact_sha256 does not match source")
    scope = contract.get("authorized_scope", {})
    if scope.get("document_id") != source["document_id"]:
        add("contract:scope_document", "authorized_scope document_id does not match source")

    origin = contract.get("authorization_origin")
    state = contract.get("authorization_state")
    author_approval = contract.get("author_approval")
    if state == "author_approved" and origin != "author":
        add("authorization:origin_state", "author_approved requires authorization_origin author")
    if origin == "calling_workflow" and state == "author_approved":
        add("authorization:caller_mint", "calling_workflow cannot create author_approved")
    if state == "author_approved" and author_approval != "approved":
        add("authorization:author_decision", "author_approved requires author_approval approved")
    if state == "caller_accepted" and author_approval == "approved":
        add("authorization:caller_approval", "caller_accepted cannot carry an approved author decision")
    if state not in {"caller_accepted", "author_approved"}:
        add("authorization:execution", "machine_proposed contract does not authorize execution")

    if manifest.get("source_artifact") != source_identity:
        add("manifest:source_identity", "change_manifest source_artifact does not match source")
    if manifest.get("candidate_artifact") != candidate_identity:
        add("manifest:candidate_identity", "change_manifest candidate_artifact does not match candidate")
    if queries.get("source_artifact") != source_identity:
        add("queries:source_identity", "author_query_list source_artifact does not match source")
    if queries.get("candidate_artifact") != candidate_identity:
        add("queries:candidate_identity", "author_query_list candidate_artifact does not match candidate")
    expected_contract_ref = {
        "revision_contract_id": contract.get("revision_contract_id"),
        "revision_contract_version": contract.get("revision_contract_version"),
        "contract_sha256": contract.get("contract_sha256"),
    }
    if manifest.get("revision_contract_ref") != expected_contract_ref:
        add("manifest:contract_binding", "change_manifest revision_contract_ref does not match the exact contract")
    if manifest.get("status") != "author_review_required":
        add("manifest:status", "a generated revision manifest must remain author_review_required")

    inventory_by_id = {item["inventory_change_id"]: item for item in inventory["changed_units"]}
    records = manifest.get("changes", []) if isinstance(manifest.get("changes"), list) else []
    declared_ids = [item.get("inventory_change_id") for item in records if isinstance(item, dict)]
    if len(declared_ids) != len(set(declared_ids)):
        add("manifest:duplicate_coverage", "multiple manifest records claim the same inventory change")
    missing = sorted(set(inventory_by_id) - set(declared_ids))
    extra = sorted(set(declared_ids) - set(inventory_by_id))
    if missing:
        add("manifest:unmanifested_change", f"actual inventory changes are absent from manifest: {missing}")
    if extra:
        add("manifest:no_actual_diff", f"manifest records lack an actual source/candidate difference: {extra}")

    allowed_operations = set(contract.get("allowed_operations", []))
    authorized_scope = set(scope.get("unit_ids", []))
    mode = contract.get("revision_mode")
    structural_authorizations = {
        item.get("structural_change_id"): item
        for item in contract.get("structural_change_authorizations", [])
        if isinstance(item, dict)
    }
    approved_structural_ids = set(contract.get("approved_structural_change_ids", []))

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        path = f"$.changes[{index}]"
        inventory_item = inventory_by_id.get(record.get("inventory_change_id"))
        if inventory_item is None:
            continue
        for field in (
            "source_unit_ids", "candidate_unit_ids", "source_locators", "candidate_locators",
            "source_representation_sha256", "candidate_representation_sha256", "section",
            "paragraph_function", "experiment_labels",
        ):
            if record.get(field) != inventory_item.get(field):
                add("manifest:inventory_binding", f"{field} does not match deterministic inventory", f"{path}.{field}")
        if record.get("revision_mode") != mode:
            add("manifest:mode", "record revision_mode differs from revision contract", f"{path}.revision_mode")
        if record.get("authorization_origin") != origin or record.get("authorization_state") != state:
            add("manifest:authorization", "record authorization differs from revision contract", path)
        operation = record.get("operation_type")
        if operation not in allowed_operations:
            add("operation:not_allowed", f"declared operation is not allowed: {operation}", f"{path}.operation_type")
        if mode == "light" and operation not in LIGHT_DECLARED_OPERATIONS:
            add(
                "mode:light_structural_effect",
                f"Light mode cannot declare operation {operation}",
                f"{path}.operation_type",
            )
        source_units = set(inventory_item.get("source_unit_ids", []))
        if not source_units or not source_units.issubset(authorized_scope):
            add("scope:outside_authorized", "changed source unit is outside authorized_scope", path)

        effects = set(inventory_item.get("observed_effects", []))
        required_operations = {
            STRUCTURAL_EFFECT_TO_OPERATION[effect]
            for effect in effects
            if effect in STRUCTURAL_EFFECT_TO_OPERATION
        }
        if required_operations and operation not in required_operations:
            add(
                "operation:mislabelled_structural_change",
                f"declared {operation} masks observed operations {sorted(required_operations)}",
                f"{path}.operation_type",
            )
        for observed_operation in sorted(required_operations - allowed_operations):
            add("operation:observed_not_allowed", f"observed operation is not authorized: {observed_operation}", path)
        if "sentence_lineage_conflict" in effects:
            add("inventory:lineage_conflict", "declared sentence lineage conflicts with an exact observed source sentence", path)
        if effects & {"unit_added", "unit_removed"}:
            add("mode:unit_add_remove_unsupported", "unit addition/removal is unsupported in the minimum implementation", path)
        if mode == "light":
            forbidden = sorted(effects & LIGHT_FORBIDDEN_EFFECTS)
            if forbidden:
                add("mode:light_structural_effect", f"Light revision contains forbidden observed effects: {forbidden}", path)
        elif mode == "medium":
            forbidden = sorted(effects & MEDIUM_FORBIDDEN_EFFECTS)
            if forbidden:
                add("mode:medium_structural_effect", f"Medium revision contains forbidden observed effects: {forbidden}", path)
            if "sentence_count_changed" in effects and not ({"sentence_split", "sentence_merge"} & effects):
                add("mode:medium_unclassified_count_change", "sentence count changed without an observable split/merge binding", path)
        elif mode == "deep" and "section_membership_changed" in effects:
            add("mode:deep_section_move_unsupported", "section-membership changes are unsupported in the minimum Deep implementation", path)

        paragraph_function = record.get("paragraph_function", {})
        if paragraph_function.get("origin") == "model_assisted_classification" and (effects & set(STRUCTURAL_EFFECT_TO_OPERATION)):
            add("paragraph_function:advisory_only", "model-assisted paragraph function cannot authorize a structural effect", path)
        record_refs = {
            item.get("artifact_id"): item
            for item in record.get("upstream_artifact_refs", [])
            if isinstance(item, dict)
        }
        for artifact_id, reference in record_refs.items():
            actual = upstream_artifacts.get(artifact_id)
            if actual is None:
                add("upstream:missing_artifact", f"referenced upstream artifact was not supplied: {artifact_id}", path)
                continue
            expected = {
                "artifact_id": artifact_id,
                "artifact_type": actual["artifact_type"],
                "artifact_version": actual["artifact_version"],
                "artifact_sha256": actual["artifact_sha256"],
            }
            if reference != expected:
                add("upstream:identity_mismatch", f"upstream reference does not match supplied artifact: {artifact_id}", path)

        bound = _bound_upstream_artifacts(record_refs, upstream_artifacts)

        for code, message in provenance_gate_issues(
            record,
            source["document_id"],
            source_units,
            record.get("section"),
            upstream_artifacts,
        ):
            add(code, message, path)

        if (
            mode in {"medium", "deep"}
            and record.get("section") in {"results", "discussion"}
            and "sentence_order_changed" in effects
        ):
            propositions = set(record.get("source_proposition_ids", []))
            baselines = _approved_paragraph_baselines(
                source["document_id"], source_units, bound
            )
            if not _approved_claim_evidence_relations(
                source["document_id"],
                source_units,
                propositions,
                baselines,
                bound,
            ):
                add(
                    "medium:missing_approved_baseline",
                    "Results/Discussion sentence reorder requires an exact approved paragraph baseline and approved claim/evidence relation closure",
                    path,
                )

        paragraph_effects = effects & PARAGRAPH_EFFECTS
        if mode == "deep" and paragraph_effects:
            declared_structural_ids = set(record.get("structural_change_ids", []))
            if not declared_structural_ids:
                add("deep:missing_structural_id", "observed paragraph structure change lacks structural-change ID", path)
            matched = False
            for structural_id in declared_structural_ids:
                authorization = structural_authorizations.get(structural_id)
                if structural_id not in approved_structural_ids or authorization is None:
                    continue
                if authorization.get("author_approval") != "approved":
                    continue
                if not paragraph_effects.issubset(set(authorization.get("allowed_effects", []))):
                    continue
                if not source_units.issubset(set(authorization.get("source_unit_ids", []))):
                    continue
                if not set(inventory_item.get("candidate_unit_ids", [])).issubset(set(authorization.get("candidate_unit_ids", []))):
                    continue
                required_artifacts = set(authorization.get("required_upstream_artifact_ids", []))
                if not required_artifacts.issubset(record_refs):
                    continue
                if not required_artifacts.issubset(bound):
                    continue
                if any(bound[item]["value"].get("status") != "author_approved" for item in required_artifacts):
                    continue
                if not any(
                    _plan_contains_approved_structural_decision(bound[item], structural_id)
                    for item in required_artifacts
                ):
                    continue
                plans = [
                    bound[item] for item in required_artifacts
                    if _approved_structural_decision(bound[item], structural_id) is not None
                ]
                if not plans:
                    continue
                if not any(
                    _deep_referenced_artifact_closure(
                        plan,
                        _approved_structural_decision(plan, structural_id) or {},
                        bound,
                    )
                    for plan in plans
                ):
                    continue
                matched = True
                break
            if not matched:
                add("deep:authorization_closure", "observed paragraph effect lacks exact approved scope and upstream artifact closure", path)

    changed_unit_ids = {
        unit_id
        for item in inventory["changed_units"]
        for unit_id in item.get("source_unit_ids", []) + item.get("candidate_unit_ids", [])
    }
    query_records = queries.get("queries", []) if isinstance(queries.get("queries"), list) else []
    for index, query in enumerate(query_records):
        if not isinstance(query, dict):
            continue
        path = f"$.queries[{index}]"
        unresolved = query.get("resolution_status") == "unresolved"
        if unresolved and query.get("author_response"):
            add("query:fabricated_answer", "unresolved query must not contain an author response", path)
        if query.get("resolution_status") == "answered_by_author" and not str(query.get("author_response", "")).strip():
            add("query:missing_author_response", "answered_by_author requires a non-empty author response", path)
        if unresolved and query.get("blocks_revision"):
            affected = set(query.get("affected_unit_ids", []))
            if affected & changed_unit_ids:
                add("query:blocking_unit_changed", "an unresolved blocking query affects a changed unit", path)

    return issues, inventory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-document", type=Path, required=True)
    parser.add_argument("--candidate-document", type=Path, required=True)
    parser.add_argument("--lineage-map", type=Path, required=True)
    parser.add_argument("--revision-contract", type=Path, required=True)
    parser.add_argument("--change-manifest", type=Path, required=True)
    parser.add_argument("--author-queries", type=Path, required=True)
    parser.add_argument("--upstream-artifact", type=Path, action="append", default=[])
    parser.add_argument("--schemas-dir", type=Path, default=DEFAULT_SCHEMAS)
    parser.add_argument("--validator", type=Path, default=DEFAULT_VALIDATOR)
    parser.add_argument("--write-inventory", type=Path)
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args()
    try:
        validator = _load_validator(args.validator)
        source = read_json(args.source_document)
        candidate = read_json(args.candidate_document)
        lineage_map = read_json(args.lineage_map)
        contract = read_json(args.revision_contract)
        manifest = read_json(args.change_manifest)
        queries = read_json(args.author_queries)
        issues = []
        issues.extend(_schema_issues(validator, args.schemas_dir / "change-manifest.schema.json", args.change_manifest))
        issues.extend(_schema_issues(validator, args.schemas_dir / "author-query-list.schema.json", args.author_queries))
        issues.extend(_revision_contract_schema_issues(validator, contract))
        upstream = _read_upstream_artifacts(args.upstream_artifact, validator, issues)
        semantic_issues, inventory = validate_revision_package(
            source, candidate, contract, manifest, queries, upstream, lineage_map,
        )
        issues.extend(semantic_issues)
        if args.write_inventory:
            write_json(args.write_inventory, inventory)
        result = {
            "valid": not issues,
            "ready_for_independent_qc": not issues,
            "issue_count": len(issues),
            "issues": issues,
        }
        if args.json_report:
            write_json(args.json_report, result)
    except (OSError, json.JSONDecodeError, InventoryError, PackageValidationError, RuntimeError) as exc:
        print(f"revision package validation error: {exc}", file=sys.stderr)
        return 2
    if issues:
        for issue in issues:
            print(f"{issue['layer']} {issue['path']} [{issue['code']}] {issue['message']}")
        return 1
    print("Revision package valid; ready for independent Phase 5 QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
