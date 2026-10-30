#!/usr/bin/env python3
"""Validate Phase 7B Review admission, authority, inventory, and handoff evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any

from build_review_change_inventory import (
    PROTECTED_CLASSES,
    SUPPORTED_REVIEW_TYPES,
    artifact_identity,
    build_citation_anchor_inventory,
    build_inventory,
    canonical_sha256,
    citation_occurrences,
    payload_sha256,
    read_json,
    validate_document,
    validate_lineage_map,
    write_json,
)


HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
DEFAULT_PHASE7A_VALIDATOR = HERE / "validate_review_package.py"
DEFAULT_PHASE7A_SCHEMAS = SKILL_ROOT / "schemas"
DEFAULT_SHARED_VALIDATOR = SKILL_ROOT / "shared-core" / "scripts" / "validate_artifact.py"
DEFAULT_SCHEMAS = SKILL_ROOT / "schemas"
PACKAGE_ROOT = SKILL_ROOT
PACKAGE_INVENTORY = PACKAGE_ROOT / "package-inventory.json"
IMPLEMENTATION_VERSION = "0.1.6"
PACKAGE_VERSION = "0.1.7"

LIGHT_MEDIUM_OPERATION = "replace_unit_text"
DEEP_OPERATIONS = {
    "paragraph_split", "paragraph_merge", "paragraph_move", "section_move",
    "theme_reorganization", "draft_authorized_unit",
}
STRUCTURAL_OPERATIONS = DEEP_OPERATIONS - {"draft_authorized_unit"}
ALL_OPERATIONS = DEEP_OPERATIONS | {LIGHT_MEDIUM_OPERATION}
STRUCTURAL_SUBJECT_TYPES = {"paragraph_plan", "section_plan", "source_unit"}
CLOSURE_FIELDS = (
    "claim_ids", "citation_relation_ids", "source_ids", "extraction_record_ids",
    "conflict_ids", "limitation_ids", "gap_ids", "author_position_ids",
    "future_direction_ids",
)


class ReviewRevisionValidationError(RuntimeError):
    """Raised when validation cannot be completed deterministically."""


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_package_runtime_trust_root(
    *,
    schemas_dir: Path,
    phase7a_validator_path: Path,
    phase7a_schemas_dir: Path,
    shared_validator_path: Path,
) -> None:
    """Fail closed unless runtime dependencies are the pinned package-local bytes."""
    expected_paths = {
        "schemas_dir": DEFAULT_SCHEMAS.resolve(),
        "phase7a_validator": DEFAULT_PHASE7A_VALIDATOR.resolve(),
        "phase7a_schemas_dir": DEFAULT_PHASE7A_SCHEMAS.resolve(),
        "shared_validator": DEFAULT_SHARED_VALIDATOR.resolve(),
    }
    supplied_paths = {
        "schemas_dir": schemas_dir.resolve(),
        "phase7a_validator": phase7a_validator_path.resolve(),
        "phase7a_schemas_dir": phase7a_schemas_dir.resolve(),
        "shared_validator": shared_validator_path.resolve(),
    }
    mismatched = sorted(name for name in expected_paths if supplied_paths[name] != expected_paths[name])
    if mismatched:
        raise ReviewRevisionValidationError(
            f"runtime validator/schema overrides are prohibited: {mismatched}"
        )

    # Development-source tests do not have a package inventory.  The formal
    # package does, and must verify it before any validator module is loaded.
    if not PACKAGE_INVENTORY.is_file():
        return
    inventory = read_json(PACKAGE_INVENTORY)
    if inventory.get("schema_name") != "skill_package_inventory":
        raise ReviewRevisionValidationError("package inventory identity mismatch")
    if payload_sha256(inventory, "package_manifest_sha256") != inventory.get("package_manifest_sha256"):
        raise ReviewRevisionValidationError("package inventory self-hash mismatch")
    if inventory.get("skill_name") != "review-architect-polisher" or inventory.get("skill_package_version") != PACKAGE_VERSION:
        raise ReviewRevisionValidationError("package inventory version mismatch")

    rows = {
        row.get("path"): row
        for row in inventory.get("files", [])
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }
    required_relatives = {
        "scripts/validate_review_revision_package.py",
        "scripts/validate_review_package.py",
        "shared-core/scripts/validate_artifact.py",
        "shared-core/shared-core-vendor-inventory.json",
    }
    required_relatives.update(
        path.relative_to(PACKAGE_ROOT).as_posix()
        for path in DEFAULT_SCHEMAS.glob("*.json")
    )
    for relative in sorted(required_relatives):
        row = rows.get(relative)
        path = PACKAGE_ROOT / relative
        if row is None or not path.is_file():
            raise ReviewRevisionValidationError(f"pinned runtime file missing: {relative}")
        if path.stat().st_size != row.get("size_bytes") or _file_sha256(path) != row.get("sha256"):
            raise ReviewRevisionValidationError(f"pinned runtime file hash/size mismatch: {relative}")

    vendor = read_json(PACKAGE_ROOT / "shared-core" / "shared-core-vendor-inventory.json")
    if payload_sha256(vendor, "inventory_sha256") != vendor.get("inventory_sha256"):
        raise ReviewRevisionValidationError("vendored shared-core inventory self-hash mismatch")
    if inventory.get("vendored_shared_core", {}).get("inventory_sha256") != vendor.get("inventory_sha256"):
        raise ReviewRevisionValidationError("package/vendor inventory binding mismatch")
    for row in vendor.get("files", []):
        relative = row.get("vendored_relative_path")
        path = PACKAGE_ROOT / "shared-core" / str(relative)
        if not path.is_file() or path.stat().st_size != row.get("size_bytes") or _file_sha256(path) != row.get("sha256"):
            raise ReviewRevisionValidationError(f"vendored shared-core file mismatch: {relative}")


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ReviewRevisionValidationError(f"cannot load validator: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _artifact_ref(value: dict[str, Any], *, version_field: str = "schema_version", hash_field: str = "artifact_sha256") -> dict[str, Any]:
    return {
        "artifact_id": value.get("artifact_id"),
        "artifact_version": value.get(version_field),
        "artifact_sha256": value.get(hash_field),
    }


def _proposal_ref(proposal: dict[str, Any]) -> dict[str, Any]:
    return {
        "proposal_id": proposal.get("proposal_id"),
        "proposal_version": proposal.get("schema_version"),
        "proposal_sha256": proposal.get("proposal_sha256"),
    }


def _permission_ref(permission: dict[str, Any]) -> dict[str, Any]:
    return {
        "permission_id": permission.get("permission_id"),
        "permission_version": permission.get("schema_version"),
        "permission_sha256": permission.get("permission_sha256"),
    }


def permission_payload_sha256(permission: dict[str, Any]) -> str:
    """Frozen contract 0.1.2 algorithm: omit only the top-level self-hash."""
    return canonical_sha256({key: value for key, value in permission.items() if key != "permission_sha256"})


def _governed_projection(value: Any) -> Any:
    if isinstance(value, list):
        return [_governed_projection(item) for item in value]
    if not isinstance(value, dict):
        return value
    omitted = {
        "artifact_sha256", "source_record_sha256", "record_sha256", "decision_ref",
        "decision_refs", "unresolved_decision_refs", "access_verification_ref",
    }
    return {
        key: _governed_projection(item)
        for key, item in value.items()
        if key not in omitted and not key.endswith("_decision_ref")
    }


def governed_subject_sha256(value: Any) -> str:
    return canonical_sha256(_governed_projection(value))


def _phase7a_refs(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "scope": _artifact_ref(package["scope"]),
        "source_registry": _artifact_ref(package["registry"]),
        "synthesis_matrix": _artifact_ref(package["synthesis"]),
        "outline": _artifact_ref(package["outline"]),
        "extraction_records": sorted(({
            "artifact_id": item.get("extraction_record_id"),
            "artifact_version": item.get("interface_version"),
            "artifact_sha256": item.get("record_sha256"),
        } for item in package["extractions"]), key=lambda item: str(item["artifact_id"])),
        "authority_manifest_sha256": package.get("authority_manifest_sha256"),
    }


def _validate_phase7a(
    package: dict[str, Any],
    *,
    phase7a_validator_path: Path = DEFAULT_PHASE7A_VALIDATOR,
    phase7a_schemas_dir: Path = DEFAULT_PHASE7A_SCHEMAS,
    shared_validator_path: Path = DEFAULT_SHARED_VALIDATOR,
) -> list[dict[str, str]]:
    required = {"scope", "registry", "extractions", "authority_bundle", "authority_manifest_sha256", "synthesis", "outline", "trusted_inputs"}
    missing = sorted(required - set(package))
    if missing:
        return [{"code": "phase7a:shape", "message": f"Phase 7A package missing {missing}"}]
    module = _load_module(phase7a_validator_path, "phase7a_frozen_validator")
    trusted_inputs: dict[str, dict[str, Any]] = {}
    for input_id, record in package.get("trusted_inputs", {}).items():
        if not isinstance(record, dict):
            return [{"code": "phase7a:trusted_input", "message": f"invalid trusted input record: {input_id}"}]
        path = record.get("path")
        trusted_inputs[input_id] = {"path": Path(path).resolve(), "sha256": record.get("sha256")}
    issues = module.validate_schema_layer(
        package["scope"], package["registry"], package["extractions"],
        package["authority_bundle"], package["synthesis"], package["outline"],
        phase7a_schemas_dir, shared_validator_path,
    )
    issues.extend(module.validate_review_package(
        package["scope"], package["registry"], package["extractions"],
        package["authority_bundle"], package["authority_manifest_sha256"],
        package["synthesis"], package["outline"], trusted_inputs,
    ))
    return [
        {"code": f"phase7a:{issue.get('code', 'invalid')}", "message": issue.get("message", "invalid Phase 7A closure")}
        for issue in issues
    ]


def _validate_value_schema(value: dict[str, Any], schema_name: str, shared_validator_path: Path) -> list[dict[str, str]]:
    validator = _load_module(shared_validator_path, f"phase7b_schema_{schema_name.replace('-', '_')}")
    schema_path = DEFAULT_SCHEMAS / schema_name
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    store = validator.SchemaStore()
    return [
        {"code": f"schema:{issue.keyword}", "message": f"{schema_name}:{issue.path}: {issue.message}"}
        for issue in validator.validate_instance(value, schema, schema_path, schema, store)
    ]


def _phase7a_indexes(package: dict[str, Any]) -> dict[str, dict[str, Any]]:
    synthesis = package["synthesis"]
    outline = package["outline"]
    result: dict[str, dict[str, Any]] = {
        "claim_ids": {item["claim_id"]: item for item in synthesis.get("claims", [])},
        "citation_relation_ids": {item["relation_id"]: item for item in synthesis.get("citation_relations", [])},
        "source_ids": {item["source_id"]: item for item in package["registry"].get("source_records", [])},
        "extraction_record_ids": {item["extraction_record_id"]: item for item in package.get("extractions", [])},
        "conflict_ids": {item["conflict_id"]: item for item in synthesis.get("conflicts", [])},
        "limitation_ids": {item["limitation_id"]: item for item in synthesis.get("limitations", [])},
        "gap_ids": {item["gap_id"]: item for item in synthesis.get("gaps", [])},
        "author_position_ids": {item["position_id"]: item for item in synthesis.get("author_positions", []) if "position_id" in item},
        "future_direction_ids": {item["direction_id"]: item for item in synthesis.get("future_directions", []) if "direction_id" in item},
        "paragraph_plan": {},
        "section_plan": {},
    }
    for section in outline.get("section_plans", []):
        result["section_plan"][section.get("section_id")] = section
        for paragraph in section.get("paragraph_plans", []):
            result["paragraph_plan"][paragraph.get("paragraph_id")] = paragraph
    return result


def _unit_closure(units: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        field: sorted({identifier for unit in units for identifier in unit.get(field, [])})
        for field in CLOSURE_FIELDS
    }


def _replacement_closure(specs: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        field: sorted({identifier for spec in specs for identifier in spec.get(field, [])})
        for field in CLOSURE_FIELDS
    }


def _validate_exact_closure(closure: Any, indexes: dict[str, dict[str, Any]], path: str, add: Any) -> None:
    if not isinstance(closure, dict) or set(closure) != set(CLOSURE_FIELDS):
        add("phase7a:closure_shape", f"{path} must contain exactly {list(CLOSURE_FIELDS)}")
        return
    for field in CLOSURE_FIELDS:
        values = closure.get(field)
        if not isinstance(values, list) or len(values) != len(set(values)) or values != sorted(values):
            add("phase7a:closure_shape", f"{path}.{field} must be a unique sorted identifier array")
            continue
        unknown = sorted(set(values) - set(indexes[field]))
        if unknown:
            add("phase7a:unknown_closure", f"{path}.{field} contains unknown IDs: {unknown}")


def _subject_for_decision(
    decision: dict[str, Any],
    source: dict[str, Any],
    phase7a: dict[str, Any],
) -> tuple[str, Any] | None:
    subject_type = decision.get("governed_subject_type")
    subject_id = decision.get("governed_subject_id")
    indexes = _phase7a_indexes(phase7a)
    if subject_type in {"paragraph_plan", "section_plan"}:
        subject = indexes[subject_type].get(subject_id)
        return (phase7a["outline"].get("schema_version"), subject) if subject is not None else None
    if subject_type == "source_unit":
        subject = next((unit for unit in source.get("units", []) if unit.get("unit_id") == subject_id), None)
        return (source.get("artifact_version"), subject) if subject is not None else None
    if subject_type == "authorized_empty_draft_slot":
        subject = next((slot for slot in source.get("authorized_empty_draft_slots", []) if slot.get("slot_id") == subject_id), None)
        return (subject.get("slot_version"), subject) if subject is not None else None
    return None


def _decision_is_internally_authorized(decision: dict[str, Any]) -> bool:
    if decision.get("authorization_origin") != "author" or decision.get("authorization_state") != "author_approved":
        return False
    decision_type = decision.get("decision_type")
    subject_type = decision.get("governed_subject_type")
    operation = decision.get("allowed_operation")
    if decision_type == "review_draft_slot_materialization":
        return subject_type == "authorized_empty_draft_slot" and operation == "draft_authorized_unit"
    if decision_type == "review_structural_revision":
        return subject_type in STRUCTURAL_SUBJECT_TYPES and operation in STRUCTURAL_OPERATIONS
    return False


def _operation_target_units(source: dict[str, Any], operation: dict[str, Any]) -> list[dict[str, Any]]:
    index = {unit["unit_id"]: unit for unit in source.get("units", [])}
    return [index[unit_id] for unit_id in operation.get("target_unit_ids", []) if unit_id in index]


def _actual_affected_ids(
    target_units: list[dict[str, Any]],
    operation: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    replacements = operation.get("replacement_units", [])
    expected_slot = operation.get("expected_slot")
    paragraph_ids = {unit.get("paragraph_plan_id") for unit in target_units}
    paragraph_ids.update(spec.get("paragraph_plan_id") for spec in replacements if isinstance(spec, dict))
    section_ids = {unit.get("section_id") for unit in target_units}
    section_ids.update(spec.get("section_id") for spec in replacements if isinstance(spec, dict))
    for field in ("target_section_id", "destination_section_id"):
        if isinstance(operation.get(field), str):
            section_ids.add(operation[field])
    slot_ids: set[str] = set()
    if isinstance(expected_slot, dict):
        slot_ids.add(expected_slot.get("slot_id"))
        paragraph_ids.add(expected_slot.get("outline_paragraph_id"))
        section_ids.add(expected_slot.get("section_id"))
    return (
        sorted(value for value in paragraph_ids if isinstance(value, str)),
        sorted(value for value in section_ids if isinstance(value, str)),
        sorted(value for value in slot_ids if isinstance(value, str)),
    )


def _profile_feature_locators(profile: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    if profile.get("schema_name") == "style_profile":
        for section_id, section in profile.get("sections", {}).items():
            for feature_id in section.get("feature_support", {}):
                result[feature_id] = f"sections.{section_id}.feature_support.{feature_id}"
    elif profile.get("schema_name") == "structure_profile":
        for feature_id in profile.get("feature_support", {}):
            result[feature_id] = f"feature_support.{feature_id}"
    return result


def _validate_profile_alignment(
    profile_ref: Any,
    supplied_profile: dict[str, Any] | None,
    add: Any,
) -> None:
    if profile_ref is None:
        if supplied_profile is not None:
            add("profile:unused_artifact", "a Review profile was supplied but no profile alignment was proposed")
        return
    if not isinstance(profile_ref, dict):
        add("profile:binding", "profile alignment must be an object")
        return
    if supplied_profile is None:
        add("profile:missing_artifact", "profile alignment requires the exact supplied M01 profile artifact")
        return
    if supplied_profile.get("schema_name") not in {"style_profile", "structure_profile"}:
        add("profile:type", "supplied profile is not an M01 style/structure profile")
    common_fields = {
        "schema_name", "schema_version", "artifact_id", "created_at", "created_by",
        "source_artifact_ids", "source_files", "status", "warnings", "corpus_id",
        "corpus_type", "document_count",
    }
    style_fields = common_fields | {
        "feature_method_version", "aggregation_contract", "sections", "prohibited_content_audit",
    }
    structure_fields = common_fields | {
        "section_presence", "common_canonical_sequences", "section_instances_per_document",
        "paragraphs_per_document_section", "heading_depth_per_document",
        "child_edge_count_per_document_canonical_section",
        "mean_direct_children_per_root_section_instance_by_document",
        "figure_references_per_document_section", "feature_support", "deterministic_only",
        "semantic_annotation_status", "semantic_role_labels_present",
    }
    required_fields = style_fields if supplied_profile.get("schema_name") == "style_profile" else structure_fields
    if set(supplied_profile) != required_fields or supplied_profile.get("schema_version") != "0.2.2":
        add("profile:m01_shape", "supplied profile does not have the exact M01 0.2.2 artifact surface")
    if supplied_profile.get("corpus_type") != "review_article" or supplied_profile.get("status") != "author_approved":
        add("profile:route", "supplied profile must be author-reviewed and Review-only")
    exact_hash = canonical_sha256(supplied_profile)
    if (
        profile_ref.get("profile_id") != supplied_profile.get("artifact_id")
        or profile_ref.get("profile_version") != supplied_profile.get("schema_version")
        or profile_ref.get("profile_sha256") != exact_hash
    ):
        add("profile:artifact_binding", "profile identity/version/hash does not match the supplied artifact")
    if (
        profile_ref.get("document_type") != "review_article"
        or profile_ref.get("corpus_type") != "review_only"
        or profile_ref.get("review_state") != "reviewed"
        or profile_ref.get("stale") is not False
    ):
        add("profile:route", "profile reference must declare a current reviewed Review-only route")
    feature_id = profile_ref.get("feature_id")
    locators = _profile_feature_locators(supplied_profile)
    if feature_id not in locators or profile_ref.get("support_locator") != locators.get(feature_id):
        add("profile:feature_binding", "profile feature/support locator does not resolve in the supplied artifact")
    else:
        if supplied_profile.get("schema_name") == "style_profile":
            support = next(
                section.get("feature_support", {}).get(feature_id)
                for section in supplied_profile.get("sections", {}).values()
                if feature_id in section.get("feature_support", {})
            )
        else:
            support = supplied_profile.get("feature_support", {}).get(feature_id)
        if not isinstance(support, dict) or support.get("feature_id") != feature_id:
            add("profile:feature_binding", "resolved M01 feature support does not bind its feature_id")


def validate_admission(
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
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    def add(code: str, message: str) -> None:
        issues.append({"code": code, "message": message})

    for message in validate_document(source, "source"):
        add("source:invalid", message)
    try:
        issues.extend(_validate_value_schema(permission, "review-revision-permission.schema.json", shared_validator_path))
        issues.extend(_validate_value_schema(proposal, "review-revision-proposal.schema.json", shared_validator_path))
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        add("schema:validator_error", str(exc))
    try:
        issues.extend(_validate_phase7a(
            phase7a,
            phase7a_validator_path=phase7a_validator_path,
            phase7a_schemas_dir=phase7a_schemas_dir,
            shared_validator_path=shared_validator_path,
        ))
    except (OSError, RuntimeError, KeyError, TypeError, ValueError) as exc:
        add("phase7a:validator_error", str(exc))

    if permission.get("schema_name") != "review_revision_permission" or permission.get("schema_version") != "0.1.0":
        add("permission:identity", "permission schema identity is unsupported")
    recomputed_permission_hash = permission_payload_sha256(permission)
    if permission.get("permission_sha256") != recomputed_permission_hash:
        add("permission:hash", "embedded permission_sha256 does not match the canonical payload")
    if expected_permission_sha256 != recomputed_permission_hash:
        add("permission:expected_hash", "caller-held expected_permission_sha256 mismatch")
    if permission.get("creator_role") in {"module04", "model"}:
        add("permission:self_produced", "Module 04 or model output cannot create the permission trust root")
    if permission.get("authorization_state") not in {"caller_accepted", "author_approved"}:
        add("permission:state", "machine-proposed or rejected permission cannot authorize application")
    if permission.get("authorization_state") == "author_approved" and permission.get("authorization_origin") != "author":
        add("permission:origin", "author_approved requires author origin")
    if permission.get("authorization_origin") not in {"author", "calling_workflow"}:
        add("permission:origin", "permission authorization origin is unsupported")

    if permission.get("document_type") != "review_article" or permission.get("review_type") not in SUPPORTED_REVIEW_TYPES:
        add("routing:review_only", "only narrative_review or mini_review Review Articles are executable")
    if permission.get("review_type") != source.get("review_type"):
        add("routing:review_type", "permission review_type does not match source")
    if permission.get("source_artifact") != artifact_identity(source):
        add("permission:source_binding", "permission does not bind the exact source Review")
    try:
        if permission.get("phase7a_closure") != _phase7a_refs(phase7a):
            add("permission:phase7a_binding", "permission does not bind the exact Phase 7A closure")
    except (KeyError, TypeError):
        add("permission:phase7a_binding", "Phase 7A closure is incomplete")
    scope = phase7a.get("scope", {})
    if scope.get("document_type") != "review_article" or scope.get("review_type") != source.get("review_type") or scope.get("execution_mode") != "executable":
        add("routing:phase7a_scope", "Phase 7A scope is not an executable matching Review route")

    source_unit_ids = {unit["unit_id"] for unit in source.get("units", []) if isinstance(unit, dict) and "unit_id" in unit}
    allowed_source_ids = permission.get("authorized_source_unit_ids")
    if not isinstance(allowed_source_ids, list) or len(allowed_source_ids) != len(set(allowed_source_ids)):
        add("permission:source_units", "authorized_source_unit_ids must be unique")
        allowed_source_ids = []
    unknown_authorized = sorted(set(allowed_source_ids) - source_unit_ids)
    if unknown_authorized:
        add("permission:widened_source_scope", f"permission authorizes unknown source units: {unknown_authorized}")
    source_slots = {slot["slot_id"]: slot for slot in source.get("authorized_empty_draft_slots", [])}
    permission_slots = permission.get("authorized_empty_draft_slots")
    if not isinstance(permission_slots, list):
        add("permission:slots", "authorized_empty_draft_slots must be an array")
        permission_slots = []
    permission_slot_ids: set[str] = set()
    for record in permission_slots:
        if not isinstance(record, dict) or record.get("slot_id") in permission_slot_ids:
            add("permission:slots", "permission slot records must be unique objects")
            continue
        slot_id = record.get("slot_id")
        permission_slot_ids.add(slot_id)
        if source_slots.get(slot_id) != record:
            add("permission:slot_binding", f"permission slot does not equal exact source slot: {slot_id}")

    if proposal.get("schema_name") != "review_revision_proposal" or proposal.get("schema_version") != "0.1.0":
        add("proposal:identity", "proposal schema identity is unsupported")
    if proposal.get("proposal_sha256") != payload_sha256(proposal, "proposal_sha256"):
        add("proposal:hash", "proposal_sha256 mismatch")
    if proposal.get("proposal_origin") != "model_proposed" or proposal.get("status") != "machine_proposed":
        add("proposal:authority", "revision proposal must remain machine_proposed")
    if proposal.get("document_type") != "review_article" or proposal.get("review_type") != source.get("review_type"):
        add("routing:proposal", "proposal does not match the source Review route")
    if proposal.get("source_artifact") != artifact_identity(source):
        add("proposal:source_binding", "proposal does not bind the exact source")
    if proposal.get("permission_ref") != _permission_ref(permission):
        add("proposal:permission_binding", "proposal does not bind the exact permission")
    mode = proposal.get("revision_mode")
    if mode not in {"light", "medium", "deep"} or mode != permission.get("revision_mode"):
        add("mode:binding", "proposal and permission revision modes must match")

    allowed_operations = permission.get("allowed_operations")
    prohibited_operations = permission.get("prohibited_operations")
    if not isinstance(allowed_operations, list) or len(allowed_operations) != len(set(allowed_operations)) or set(allowed_operations) - ALL_OPERATIONS:
        add("permission:allowed_operations", "allowed_operations contains duplicates or unsupported values")
        allowed_operations = []
    if not isinstance(prohibited_operations, list) or len(prohibited_operations) != len(set(prohibited_operations)) or set(prohibited_operations) - ALL_OPERATIONS:
        add("permission:prohibited_operations", "prohibited_operations contains duplicates or unsupported values")
        prohibited_operations = []
    if set(allowed_operations) & set(prohibited_operations):
        add("permission:operation_conflict", "an operation cannot be both allowed and prohibited")

    decisions_raw = permission.get("authorized_decisions")
    decisions: dict[str, dict[str, Any]] = {}
    if not isinstance(decisions_raw, list):
        add("permission:decisions", "authorized_decisions must be an array")
        decisions_raw = []
    indexes = _phase7a_indexes(phase7a) if all(key in phase7a for key in ("synthesis", "outline", "registry", "extractions")) else {field: {} for field in CLOSURE_FIELDS}
    for index, decision in enumerate(decisions_raw):
        path = f"permission.authorized_decisions[{index}]"
        if not isinstance(decision, dict) or not isinstance(decision.get("decision_id"), str):
            add("permission:decision_shape", f"{path} must contain a decision_id")
            continue
        decision_id = decision["decision_id"]
        if decision_id in decisions:
            add("permission:decision_duplicate", f"duplicate decision ID: {decision_id}")
            continue
        decisions[decision_id] = decision
        if not _decision_is_internally_authorized(decision):
            add("permission:decision_compatibility", f"unauthorized or incompatible decision: {decision_id}")
        subject = _subject_for_decision(decision, source, phase7a)
        if subject is None or subject[1] is None:
            add("permission:governed_subject", f"governed subject does not resolve: {decision_id}")
        else:
            expected_version, value = subject
            if decision.get("governed_subject_version") != expected_version or decision.get("governed_subject_sha256") != governed_subject_sha256(value):
                add("permission:governed_subject", f"governed subject version/hash mismatch: {decision_id}")
        _validate_exact_closure(decision.get("phase7a_closure"), indexes, f"{path}.phase7a_closure", add)
        allowlist = decision.get("materialization_allowlist", [])
        required_materializations = decision.get("required_materialization_ids", [])
        if decision.get("decision_type") == "review_draft_slot_materialization":
            if not isinstance(allowlist, list) or not allowlist:
                add("permission:materialization_allowlist", f"draft decision requires a non-empty allowlist: {decision_id}")
            allow_ids = [item.get("materialization_id") for item in allowlist if isinstance(item, dict)]
            if len(allow_ids) != len(set(allow_ids)) or any(not isinstance(item, str) for item in allow_ids):
                add("permission:materialization_allowlist", f"materialization IDs must be unique: {decision_id}")
            if not isinstance(required_materializations, list) or set(required_materializations) - set(allow_ids):
                add("permission:required_materializations", f"required materializations are not a subset of the allowlist: {decision_id}")
            for item in allowlist:
                if not isinstance(item, dict) or item.get("protected_class") not in {"citation", "terminology", "numeric", "statistic", "unit"}:
                    add("permission:materialization_allowlist", f"unsupported draft materialization: {decision_id}")
                elif not isinstance(item.get("identity"), str) or not isinstance(item.get("candidate_token"), str):
                    add("permission:materialization_allowlist", f"materialization must bind exact identity/token: {decision_id}")
        elif allowlist or required_materializations:
            add("permission:materialization_scope", f"structural decision cannot carry draft materializations: {decision_id}")

    operations = proposal.get("operations")
    if not isinstance(operations, list) or not operations:
        add("proposal:operations", "proposal operations must be a non-empty array")
        operations = []
    operation_ids: set[str] = set()
    orders: list[int] = []
    touched_source_units: set[str] = set()
    touched_slots: set[str] = set()
    touched_protected_anchors: set[str] = set()
    permission_protected_anchors = permission.get("protected_anchor_ids", [])
    if not isinstance(permission_protected_anchors, list) or len(permission_protected_anchors) != len(set(permission_protected_anchors)):
        add("permission:protected_anchors", "protected_anchor_ids must be a unique identifier array")
        permission_protected_anchors = []
    for index, operation in enumerate(operations):
        path = f"proposal.operations[{index}]"
        if not isinstance(operation, dict):
            add("proposal:operation_shape", f"{path} must be an object")
            continue
        operation_id = operation.get("operation_id")
        operation_type = operation.get("operation_type")
        if not isinstance(operation_id, str) or operation_id in operation_ids:
            add("proposal:operation_id", f"{path}.operation_id must be unique")
        else:
            operation_ids.add(operation_id)
        order = operation.get("operation_order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 1:
            add("proposal:operation_order", f"{path}.operation_order must be positive")
        else:
            orders.append(order)
        if operation_type not in ALL_OPERATIONS or operation_type not in allowed_operations or operation_type in prohibited_operations:
            add("proposal:operation_scope", f"operation is unsupported or not authorized: {operation_type}")
        if mode in {"light", "medium"} and operation_type != LIGHT_MEDIUM_OPERATION:
            add("mode:operation", f"{mode} mode may only use replace_unit_text")
        target_ids = operation.get("target_unit_ids")
        if not isinstance(target_ids, list) or len(target_ids) != len(set(target_ids)):
            add("proposal:targets", f"{path}.target_unit_ids must be unique")
            target_ids = []
        target_units = _operation_target_units(source, operation)
        if len(target_units) != len(target_ids):
            add("proposal:targets", f"{path} references unknown source units")
        if set(target_ids) - set(allowed_source_ids):
            add("proposal:unauthorized_target", f"{path} targets source units outside the permission")
        overlap = touched_source_units & set(target_ids)
        if overlap:
            add("proposal:overlap", f"source units are targeted by multiple operations: {sorted(overlap)}")
        touched_source_units.update(target_ids)
        expected_targets = operation.get("expected_targets")
        actual_expected = [
            {"unit_id": unit["unit_id"], "unit_sha256": canonical_sha256(unit), "locator": unit["locator"]}
            for unit in target_units
        ]
        if expected_targets != actual_expected:
            add("proposal:stale_target", f"{path}.expected_targets do not bind exact source units")
        replacements = operation.get("replacement_units")
        if not isinstance(replacements, list):
            add("proposal:replacements", f"{path}.replacement_units must be an array")
            replacements = []
        if operation_type == "replace_unit_text" and (len(target_ids) != 1 or len(replacements) != 1):
            add("proposal:operation_shape", "replace_unit_text requires one target and one replacement")
        if operation_type == "paragraph_split" and (len(target_ids) != 1 or len(replacements) < 2):
            add("proposal:operation_shape", "paragraph_split requires one target and at least two replacements")
        if operation_type == "paragraph_merge" and (len(target_ids) < 2 or len(replacements) != 1):
            add("proposal:operation_shape", "paragraph_merge requires at least two targets and one replacement")
        if operation_type in {"paragraph_move", "section_move", "theme_reorganization"} and replacements:
            add("proposal:operation_shape", f"{operation_type} must move exact source units without replacement prose")
        if operation_type == "section_move":
            section_id = operation.get("target_section_id")
            exact_section_ids = [unit["unit_id"] for unit in source.get("units", []) if unit.get("section_id") == section_id]
            if target_ids != exact_section_ids or not exact_section_ids:
                add("proposal:section_closure", "section_move targets must equal the complete exact source section")
        if operation_type == "draft_authorized_unit":
            if target_ids or len(replacements) != 1:
                add("proposal:draft_shape", "draft_authorized_unit requires no source-unit target and exactly one replacement")
            expected_slot = operation.get("expected_slot")
            slot_id = expected_slot.get("slot_id") if isinstance(expected_slot, dict) else None
            if slot_id in touched_slots:
                add("proposal:overlap", f"draft slot targeted more than once: {slot_id}")
            touched_slots.add(slot_id)
            if source_slots.get(slot_id) != expected_slot or slot_id not in permission_slot_ids:
                add("proposal:stale_slot", "draft operation does not bind an exact authorized source slot")
        elif operation.get("expected_slot") is not None:
            add("proposal:slot_scope", "only draft_authorized_unit may carry expected_slot")

        replacement_source_ids = [source_id for spec in replacements for source_id in spec.get("source_unit_ids", [])] if replacements else []
        replacement_slot_ids = [slot_id for spec in replacements for slot_id in spec.get("authorized_draft_slot_ids", [])] if replacements else []
        if operation_type in {"replace_unit_text", "paragraph_split", "paragraph_merge"}:
            if set(replacement_source_ids) != set(target_ids) or replacement_slot_ids:
                add("proposal:replacement_lineage", f"{operation_type} replacement provenance must exactly cover its source targets")
        if operation_type == "draft_authorized_unit":
            expected_slot_id = operation.get("expected_slot", {}).get("slot_id") if isinstance(operation.get("expected_slot"), dict) else None
            if replacement_source_ids or replacement_slot_ids != [expected_slot_id]:
                add("proposal:replacement_lineage", "draft replacement must bind only its exact authorized slot")
        expected_closure = _unit_closure(target_units) if target_units else _replacement_closure(replacements)
        if operation.get("phase7a_closure") != expected_closure:
            add("phase7a:operation_closure", f"{path}.phase7a_closure must equal the affected exact unit closure")
        _validate_exact_closure(operation.get("phase7a_closure"), indexes, f"{path}.phase7a_closure", add)
        if replacements and _replacement_closure(replacements) != expected_closure:
            add("phase7a:replacement_closure", f"{path} replacement changes Phase 7A provenance closure")

        operation_anchors = operation.get("affected_protected_anchor_ids")
        if not isinstance(operation_anchors, list) or len(operation_anchors) != len(set(operation_anchors)):
            add("proposal:protected_anchors", f"{path}.affected_protected_anchor_ids must be unique")
            operation_anchors = []
        unknown_anchors = sorted(set(operation_anchors) - set(permission_protected_anchors))
        if unknown_anchors:
            add("proposal:protected_anchor_scope", f"{path} references unauthorized protected anchors: {unknown_anchors}")
        duplicate_anchors = sorted(touched_protected_anchors & set(operation_anchors))
        if duplicate_anchors:
            add("proposal:protected_anchor_overlap", f"protected anchors map to multiple operations: {duplicate_anchors}")
        touched_protected_anchors.update(operation_anchors)

        decision_id = operation.get("permission_decision_id")
        if operation_type in DEEP_OPERATIONS:
            decision = decisions.get(decision_id)
            if decision is None:
                add("permission:missing_decision", f"Deep/draft operation lacks an exact permission decision: {operation_id}")
            else:
                if decision.get("allowed_operation") != operation_type:
                    add("permission:decision_operation", f"decision does not authorize exact operation: {operation_id}")
                if decision.get("phase7a_closure") != operation.get("phase7a_closure"):
                    add("permission:decision_closure", f"decision and operation Phase 7A closure differ: {operation_id}")
                if sorted(decision.get("affected_source_unit_ids", [])) != sorted(target_ids):
                    add("permission:decision_targets", f"decision and operation source targets differ: {operation_id}")
                operation_paragraph_ids, operation_section_ids, operation_slot_ids = _actual_affected_ids(target_units, operation)
                if sorted(decision.get("affected_paragraph_ids", [])) != operation_paragraph_ids:
                    add("permission:decision_paragraphs", f"decision and operation paragraph targets differ: {operation_id}")
                if sorted(decision.get("affected_section_ids", [])) != operation_section_ids:
                    add("permission:decision_sections", f"decision and operation section targets differ: {operation_id}")
                if sorted(decision.get("affected_draft_slot_ids", [])) != operation_slot_ids:
                    add("permission:decision_slots", f"decision and operation slot targets differ: {operation_id}")
                governed_type = decision.get("governed_subject_type")
                governed_id = decision.get("governed_subject_id")
                exact_governed_ids = {
                    "source_unit": set(target_ids),
                    "paragraph_plan": {unit.get("paragraph_plan_id") for unit in target_units},
                    "section_plan": {unit.get("section_id") for unit in target_units},
                    "authorized_empty_draft_slot": set(operation_slot_ids),
                }.get(governed_type, set())
                if governed_id not in exact_governed_ids:
                    add("permission:decision_subject_scope", f"decision governed subject is unrelated to operation targets: {operation_id}")
        elif decision_id is not None:
            add("permission:decision_scope", "replace_unit_text must not claim a structural/drafting decision")

    if orders != list(range(1, len(orders) + 1)):
        add("proposal:operation_order", "operation_order values must be unique, contiguous, and already sorted")

    if touched_protected_anchors != set(permission_protected_anchors):
        add(
            "proposal:protected_anchor_coverage",
            "proposal affected_protected_anchor_ids must exactly cover the permission protected_anchor_ids",
        )

    profile = proposal.get("profile_alignment")
    _validate_profile_alignment(profile, review_profile, add)

    blocking_queries = {
        unit_id
        for query in proposal.get("unresolved_queries", [])
        if isinstance(query, dict) and query.get("blocks_revision") is True
        for unit_id in query.get("affected_unit_ids", [])
    }
    blocked_targets = sorted(blocking_queries & (touched_source_units | touched_slots))
    if blocked_targets:
        add("query:blocking", f"unresolved blocking queries prevent changes to units: {blocked_targets}")
    return issues


def _mode_issues(mode: str, inventory: dict[str, Any]) -> list[dict[str, str]]:
    footprint = inventory.get("structural_footprint", {})
    issues: list[dict[str, str]] = []
    if mode == "light":
        forbidden = {
            "paragraph_count_changed", "paragraph_order_changed", "sentence_count_changed",
            "sentence_order_changed", "section_membership_changed", "unit_split", "unit_merge",
            "unit_move", "unit_added", "authorized_draft_slot_materialized", "unit_removed",
        }
    elif mode == "medium":
        forbidden = {
            "paragraph_count_changed", "paragraph_order_changed", "section_membership_changed",
            "unit_split", "unit_merge", "unit_move", "unit_added",
            "authorized_draft_slot_materialized", "unit_removed",
        }
    else:
        forbidden = {"unit_removed"}
    observed = sorted(field for field in forbidden if footprint.get(field) is True)
    if observed:
        issues.append({"code": "mode:observed_footprint", "message": f"{mode} mode forbids observed effects: {observed}"})
    if mode == "light" and footprint.get("citation_placement_changed") is True:
        issues.append({
            "code": "mode:citation_placement",
            "message": "light mode forbids citation placement or syntactic-role changes",
        })
    return issues


def _protected_change_issues(
    inventory: dict[str, Any],
    permission: dict[str, Any],
    proposal: dict[str, Any],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    operations = {item.get("operation_id"): item for item in proposal.get("operations", []) if isinstance(item, dict)}
    decisions = {item.get("decision_id"): item for item in permission.get("authorized_decisions", []) if isinstance(item, dict)}
    inventory_to_operation: dict[str, dict[str, Any]] = {}
    for change in inventory.get("changed_units", []):
        change_sources = set(change.get("source_unit_ids", []))
        change_slots = set(change.get("authorized_draft_slot_ids", []))
        matches = []
        for operation in operations.values():
            operation_sources = set(operation.get("target_unit_ids", []))
            expected_slot = operation.get("expected_slot")
            operation_slots = {expected_slot.get("slot_id")} if isinstance(expected_slot, dict) else set()
            if (change_sources and change_sources & operation_sources) or (change_slots and change_slots == operation_slots):
                matches.append(operation)
        if len(matches) == 1:
            inventory_to_operation[change["inventory_change_id"]] = matches[0]

    used_materializations: dict[str, set[str]] = defaultdict(set)
    for change in inventory.get("protected_changes", []):
        protected_class = change.get("protected_class")
        if protected_class not in PROTECTED_CLASSES:
            issues.append({"code": "protected:class", "message": f"unsupported protected class: {protected_class}"})
            continue
        if change.get("delta_type") == "formatting_only":
            source_token = change.get("source_token")
            candidate_token = change.get("candidate_token")
            source_rows = citation_occurrences(source_token) if isinstance(source_token, str) else []
            candidate_rows = citation_occurrences(candidate_token) if isinstance(candidate_token, str) else []
            exact_identity_preserved = (
                protected_class == "citation"
                and isinstance(source_token, str)
                and isinstance(candidate_token, str)
                and source_token != candidate_token
                and len(source_rows) == 1
                and len(candidate_rows) == 1
                and source_rows[0]["start"] == candidate_rows[0]["start"] == 0
                and source_rows[0]["end"] == len(source_token)
                and candidate_rows[0]["end"] == len(candidate_token)
                and source_rows[0]["identity"] == candidate_rows[0]["identity"] == change.get("identity")
            )
            if not exact_identity_preserved:
                issues.append({
                    "code": "protected:formatting_identity",
                    "message": f"formatting-only change does not preserve one exact citation identity: {change.get('protected_change_id')}",
                })
            continue
        if change.get("delta_type") == "placement_changed":
            source_token = change.get("source_token")
            candidate_token = change.get("candidate_token")
            source_rows = citation_occurrences(source_token) if isinstance(source_token, str) else []
            candidate_rows = citation_occurrences(candidate_token) if isinstance(candidate_token, str) else []
            source_placement = change.get("source_placement")
            candidate_placement = change.get("candidate_placement")
            exact_identity_preserved = (
                protected_class == "citation"
                and isinstance(source_token, str)
                and isinstance(candidate_token, str)
                and len(source_rows) == 1
                and len(candidate_rows) == 1
                and source_rows[0]["start"] == candidate_rows[0]["start"] == 0
                and source_rows[0]["end"] == len(source_token)
                and candidate_rows[0]["end"] == len(candidate_token)
                and source_rows[0]["identity"] == candidate_rows[0]["identity"] == change.get("identity")
            )
            same_paragraph = (
                isinstance(source_placement, dict)
                and isinstance(candidate_placement, dict)
                and source_placement.get("section_id") == candidate_placement.get("section_id")
                and source_placement.get("paragraph_plan_id") == candidate_placement.get("paragraph_plan_id")
            )
            placement_differs = source_placement != candidate_placement
            source_alignment = source_placement.get("lexical_boundary", {}) if isinstance(source_placement, dict) else {}
            candidate_alignment = candidate_placement.get("lexical_boundary", {}) if isinstance(candidate_placement, dict) else {}
            alignment_resolved = (
                source_alignment.get("alignment_status") in {"aligned", "not_applicable"}
                and candidate_alignment.get("alignment_status") in {"aligned", "not_applicable"}
            )
            if not exact_identity_preserved or not same_paragraph or not placement_differs or not alignment_resolved:
                issues.append({
                    "code": "protected:citation_placement",
                    "message": f"citation placement record is unresolved or is not an exact same-paragraph identity-preserving move: {change.get('protected_change_id')}",
                })
            continue
        operation = inventory_to_operation.get(change.get("inventory_change_id"))
        if operation is None or operation.get("operation_type") != "draft_authorized_unit":
            issues.append({"code": "protected:ordinary_delta", "message": f"protected change is not allowed in existing prose: {change.get('protected_change_id')}"})
            continue
        decision = decisions.get(operation.get("permission_decision_id"), {})
        if change.get("delta_type") != "added":
            issues.append({"code": "protected:draft_delta", "message": "draft-slot materialization may only add exact allowlisted tokens"})
            continue
        matching = [
            item for item in decision.get("materialization_allowlist", [])
            if item.get("protected_class") == protected_class and item.get("identity") == change.get("identity")
        ]
        if len(matching) != 1:
            issues.append({"code": "protected:not_allowlisted", "message": f"draft protected token is not exactly allowlisted: {protected_class}/{change.get('identity')}"})
            continue
        used_materializations[decision.get("decision_id")].add(matching[0]["materialization_id"])
    for decision_id, decision in decisions.items():
        if decision.get("decision_type") != "review_draft_slot_materialization":
            continue
        required = set(decision.get("required_materialization_ids", []))
        missing = sorted(required - used_materializations.get(decision_id, set()))
        if missing:
            issues.append({"code": "protected:required_materialization", "message": f"required draft materializations missing for {decision_id}: {missing}"})
    return issues


def _operation_for_inventory_change(
    change: dict[str, Any],
    operations: list[dict[str, Any]],
) -> dict[str, Any] | None:
    source_ids = set(change.get("source_unit_ids", []))
    slot_ids = set(change.get("authorized_draft_slot_ids", []))
    matches: list[dict[str, Any]] = []
    for operation in operations:
        targets = set(operation.get("target_unit_ids", []))
        expected_slot = operation.get("expected_slot")
        operation_slots = {expected_slot.get("slot_id")} if isinstance(expected_slot, dict) else set()
        if (source_ids and source_ids & targets) or (slot_ids and slot_ids == operation_slots):
            matches.append(operation)
    if len(matches) == 1:
        return matches[0]
    if not matches and "paragraph_move" in change.get("observed_effects", []):
        moves = [
            operation for operation in operations
            if operation.get("operation_type") in {"paragraph_move", "section_move", "theme_reorganization"}
        ]
        if len(moves) == 1:
            return moves[0]
    return None


def expected_change_records(
    inventory: dict[str, Any],
    permission: dict[str, Any],
    proposal: dict[str, Any],
) -> list[dict[str, Any]]:
    operations = proposal.get("operations", [])
    protected_by_change: dict[str, list[str]] = defaultdict(list)
    for protected in inventory.get("protected_changes", []):
        protected_by_change[protected.get("inventory_change_id")].append(protected.get("protected_change_id"))
    records: list[dict[str, Any]] = []
    for item in inventory.get("changed_units", []):
        operation = _operation_for_inventory_change(item, operations)
        if operation is None:
            continue
        payload = {"proposal": proposal.get("proposal_id"), "inventory": item.get("inventory_change_id")}
        decision_id = operation.get("permission_decision_id")
        records.append({
            "change_id": f"review-change:{canonical_sha256(payload)[:24]}",
            "operation_id": operation.get("operation_id"),
            "operation_type": operation.get("operation_type"),
            "inventory_change_id": item.get("inventory_change_id"),
            "source_unit_ids": list(item.get("source_unit_ids", [])),
            "candidate_unit_ids": list(item.get("candidate_unit_ids", [])),
            "authorized_draft_slot_ids": list(item.get("authorized_draft_slot_ids", [])),
            "source_locators": list(item.get("source_locators", [])),
            "candidate_locators": list(item.get("candidate_locators", [])),
            "source_representation_sha256": item.get("source_representation_sha256"),
            "candidate_representation_sha256": item.get("candidate_representation_sha256"),
            "revision_mode": proposal.get("revision_mode"),
            "permission_ref": _permission_ref(permission),
            "permission_authorization_state": permission.get("authorization_state"),
            "protected_change_ids": sorted(protected_by_change.get(item.get("inventory_change_id"), [])),
            "phase7a_closure": operation.get("phase7a_closure"),
            "permission_decision_ids": [decision_id] if isinstance(decision_id, str) else [],
            "affected_protected_anchor_ids": sorted(operation.get("affected_protected_anchor_ids", [])),
            "rationale": operation.get("rationale"),
            "risk_class": operation.get("risk_class"),
            "observed_effects": list(item.get("observed_effects", [])),
            "author_review_required": True,
        })
    return records


def expected_upstream_closure_refs(
    phase7a: dict[str, Any],
    proposal: dict[str, Any],
) -> dict[str, Any]:
    return {
        "phase7a_artifacts": _phase7a_refs(phase7a),
        "operation_closures": [
            {
                "operation_id": operation.get("operation_id"),
                "phase7a_closure": operation.get("phase7a_closure"),
            }
            for operation in proposal.get("operations", [])
        ],
        "profile_ref": proposal.get("profile_alignment"),
    }


def expected_citation_support_warnings(
    source: dict[str, Any],
    candidate: dict[str, Any],
    proposal: dict[str, Any],
    phase7a: dict[str, Any],
) -> list[dict[str, Any]]:
    """Warn for every changed cited sentence or moved citation placement."""
    source_units = {unit["unit_id"]: unit for unit in source.get("units", [])}
    source_sentences = {
        sentence["sentence_id"]: (unit, sentence)
        for unit in source.get("units", [])
        for sentence in unit.get("sentences", [])
    }
    candidate_units = {unit["unit_id"]: unit for unit in candidate.get("units", [])}
    relations = {
        relation.get("relation_id"): relation
        for relation in phase7a.get("synthesis", {}).get("citation_relations", [])
    }
    operation_by_candidate: dict[str, dict[str, Any]] = {}
    for operation in proposal.get("operations", []):
        replacements = operation.get("replacement_units", [])
        if replacements:
            for replacement in replacements:
                operation_by_candidate[replacement.get("candidate_unit_id")] = operation
        else:
            for unit_id in operation.get("target_unit_ids", []):
                operation_by_candidate[unit_id] = operation

    warnings: list[dict[str, Any]] = []
    for candidate_unit_id, operation in operation_by_candidate.items():
        unit = candidate_units.get(candidate_unit_id)
        if unit is None:
            continue
        source_unit_ids = unit.get("source_unit_ids", [])
        placement_changed = any(
            source_units.get(source_id, {}).get("section_id") != unit.get("section_id")
            or source_units.get(source_id, {}).get("ordinal") != unit.get("ordinal")
            for source_id in source_unit_ids
        )
        for sentence in unit.get("sentences", []):
            relation_ids = sorted(sentence.get("citation_relation_ids", []))
            citations = [
                anchor for anchor in build_citation_anchor_inventory({
                    **candidate,
                    "units": [{**unit, "sentences": [sentence]}],
                })
            ]
            if not relation_ids and not citations:
                continue
            original_texts = [
                source_sentences[source_id][1].get("text", "")
                for source_id in sentence.get("source_sentence_ids", [])
                if source_id in source_sentences
            ]
            text_changed = " ".join(original_texts).strip() != sentence.get("text", "").strip()
            if not (text_changed or placement_changed or sentence.get("authorized_draft_slot_ids")):
                continue
            for relation_id in relation_ids:
                relation = relations.get(relation_id, {})
                relation_citations = citations or [{
                    "token": "UNRESOLVED_STRUCTURED_CITATION_TOKEN",
                    "identity": "unresolved",
                    "locator": unit.get("locator"),
                }]
                for citation in relation_citations:
                    source_locators = [
                        source_units[source_id]["locator"]
                        for source_id in source_unit_ids
                        if source_id in source_units
                    ]
                    payload = {
                        "operation_id": operation.get("operation_id"),
                        "candidate_sentence_id": sentence.get("sentence_id"),
                        "citation_identity": citation.get("identity"),
                        "synthesis_relation_id": relation_id,
                    }
                    warnings.append({
                        "warning_id": f"review-citation-support-warning:{canonical_sha256(payload)[:24]}",
                        "operation_id": operation.get("operation_id"),
                        "candidate_sentence_id": sentence.get("sentence_id"),
                        "citation_token": citation.get("token"),
                        "citation_identity": citation.get("identity"),
                        "source_ids": sorted(relation.get("source_ids", unit.get("source_ids", []))),
                        "synthesis_relation_id": relation_id,
                        "extraction_record_ids": sorted(relation.get("extraction_record_ids", unit.get("extraction_record_ids", []))),
                        "source_locators": source_locators,
                        "candidate_locator": unit.get("locator"),
                        "access_ceiling": relation.get("actual_access_level") or relation.get("access_constraint") or "unknown",
                        "reason": "changed cited sentence or citation placement requires independent support review",
                        "author_review_required": True,
                    })
    return sorted(warnings, key=lambda row: row["warning_id"])


def build_application_receipt(
    source: dict[str, Any],
    candidate: dict[str, Any],
    permission: dict[str, Any],
    proposal: dict[str, Any],
    lineage: dict[str, Any],
    inventory: dict[str, Any],
    queries: dict[str, Any],
) -> dict[str, Any]:
    payload = {"proposal": _proposal_ref(proposal), "candidate": artifact_identity(candidate)}
    receipt: dict[str, Any] = {
        "schema_name": "review_patch_application_receipt",
        "schema_version": "0.1.0",
        "artifact_id": f"review-patch-receipt:{canonical_sha256(payload)[:24]}",
        "artifact_sha256": "0" * 64,
        "source_artifact": artifact_identity(source),
        "candidate_artifact": artifact_identity(candidate),
        "permission_ref": _permission_ref(permission),
        "proposal_ref": _proposal_ref(proposal),
        "lineage_ref": _artifact_ref(lineage),
        "protected_inventory_ref": _artifact_ref(inventory),
        "author_query_list_ref": _artifact_ref(queries),
        "applied_operation_ids": [operation.get("operation_id") for operation in proposal.get("operations", [])],
        "application_engine": {"name": "phase7b_deterministic_patch_layer", "version": IMPLEMENTATION_VERSION},
        "status": "applied",
        "author_review_required": True,
    }
    receipt["artifact_sha256"] = payload_sha256(receipt, "artifact_sha256")
    return receipt


def build_package_validation_result(
    source: dict[str, Any],
    candidate: dict[str, Any],
    permission: dict[str, Any],
    proposal: dict[str, Any],
    manifest: dict[str, Any],
    application_receipt: dict[str, Any],
) -> dict[str, Any]:
    payload = {"manifest": _artifact_ref(manifest), "application_receipt": _artifact_ref(application_receipt)}
    result: dict[str, Any] = {
        "schema_name": "review_package_validation_result",
        "schema_version": "0.1.0",
        "artifact_id": f"review-validation-result:{canonical_sha256(payload)[:24]}",
        "artifact_sha256": "0" * 64,
        "source_artifact": artifact_identity(source),
        "candidate_artifact": artifact_identity(candidate),
        "permission_ref": _permission_ref(permission),
        "proposal_ref": _proposal_ref(proposal),
        "change_manifest_ref": _artifact_ref(manifest),
        "application_receipt_ref": _artifact_ref(application_receipt),
        "validator_engine": {"name": "phase7b_revision_package_validator", "version": IMPLEMENTATION_VERSION},
        "valid": True,
        "producer_state": "ready_for_independent_qc",
        "issue_count": 0,
        "issues": [],
        "author_review_required": True,
        "module06_handoff_state": "blocked_pending_module06_integration_contract",
    }
    result["artifact_sha256"] = payload_sha256(result, "artifact_sha256")
    return result


def validate_revision_evidence(
    source: dict[str, Any],
    candidate: dict[str, Any],
    permission: dict[str, Any],
    proposal: dict[str, Any],
    manifest: dict[str, Any],
    lineage: dict[str, Any],
    inventory: dict[str, Any],
    queries: dict[str, Any],
    application_receipt: dict[str, Any],
    validation_result: dict[str, Any],
    *,
    shared_validator_path: Path = DEFAULT_SHARED_VALIDATOR,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    try:
        issues.extend(_validate_value_schema(application_receipt, "review-patch-application-receipt.schema.json", shared_validator_path))
        issues.extend(_validate_value_schema(validation_result, "review-package-validation-result.schema.json", shared_validator_path))
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        issues.append({"code": "schema:validator_error", "message": str(exc)})
    expected_receipt = build_application_receipt(source, candidate, permission, proposal, lineage, inventory, queries)
    if application_receipt != expected_receipt:
        issues.append({"code": "receipt:application", "message": "application receipt is not the deterministic hash-bound record"})
    if manifest.get("application_receipt_ref") != _artifact_ref(application_receipt):
        issues.append({"code": "manifest:application_receipt", "message": "manifest does not bind the exact application receipt"})
    expected_result = build_package_validation_result(source, candidate, permission, proposal, manifest, application_receipt)
    if validation_result != expected_result:
        issues.append({"code": "receipt:validation", "message": "package validation result is not the deterministic hash-bound record"})
    return issues


def validate_revision_package(
    source: dict[str, Any],
    candidate: dict[str, Any],
    permission: dict[str, Any],
    expected_permission_sha256: str,
    proposal: dict[str, Any],
    manifest: dict[str, Any],
    queries: dict[str, Any],
    lineage: dict[str, Any],
    inventory: dict[str, Any],
    phase7a: dict[str, Any],
    review_profile: dict[str, Any] | None = None,
    *,
    phase7a_validator_path: Path = DEFAULT_PHASE7A_VALIDATOR,
    phase7a_schemas_dir: Path = DEFAULT_PHASE7A_SCHEMAS,
    shared_validator_path: Path = DEFAULT_SHARED_VALIDATOR,
) -> list[dict[str, str]]:
    issues = validate_admission(
        source, permission, expected_permission_sha256, proposal, phase7a, review_profile,
        phase7a_validator_path=phase7a_validator_path,
        phase7a_schemas_dir=phase7a_schemas_dir,
        shared_validator_path=shared_validator_path,
    )

    def add(code: str, message: str) -> None:
        issues.append({"code": code, "message": message})

    for message in validate_document(candidate, "candidate"):
        add("candidate:invalid", message)
    try:
        for value, schema_name in (
            (manifest, "review-change-manifest.schema.json"),
            (queries, "review-author-query-list.schema.json"),
            (lineage, "review-revision-lineage-map.schema.json"),
            (inventory, "review-protected-change-inventory.schema.json"),
        ):
            issues.extend(_validate_value_schema(value, schema_name, shared_validator_path))
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        add("schema:validator_error", str(exc))
    if candidate.get("manuscript_id") != source.get("manuscript_id") or candidate.get("review_type") != source.get("review_type"):
        add("candidate:identity", "candidate manuscript/review route differs from source")
    if candidate.get("authorized_empty_draft_slots") != source.get("authorized_empty_draft_slots"):
        add("candidate:slot_registry", "candidate must retain the exact source-bound authorized slot registry")
    lineage_issues = validate_lineage_map(source, candidate, lineage)
    issues.extend(lineage_issues)
    if lineage_issues:
        return issues
    expected_inventory = build_inventory(source, candidate, lineage)
    if inventory != expected_inventory:
        add("inventory:mismatch", "supplied protected-change inventory is not the deterministic source/candidate inventory")
    if inventory.get("artifact_sha256") != payload_sha256(inventory, "artifact_sha256"):
        add("inventory:hash", "inventory artifact hash mismatch")
    issues.extend(_mode_issues(proposal.get("revision_mode"), expected_inventory))
    issues.extend(_protected_change_issues(expected_inventory, permission, proposal))

    if queries.get("schema_name") != "review_author_query_list" or queries.get("schema_version") != "0.1.0":
        add("queries:identity", "author query artifact identity is unsupported")
    if queries.get("artifact_sha256") != payload_sha256(queries, "artifact_sha256"):
        add("queries:hash", "author query artifact hash mismatch")
    if queries.get("source_artifact") != artifact_identity(source) or queries.get("candidate_artifact") != artifact_identity(candidate):
        add("queries:binding", "author query list does not bind exact source/candidate")
    if queries.get("proposal_ref") != _proposal_ref(proposal):
        add("queries:proposal_binding", "author query list does not bind exact proposal")
    if queries.get("queries") != proposal.get("unresolved_queries"):
        add("queries:content", "author query list differs from proposal unresolved queries")
    changed_source_units = {
        source_id
        for change in expected_inventory.get("changed_units", [])
        for source_id in change.get("source_unit_ids", [])
    }
    changed_draft_slots = {
        slot_id
        for change in expected_inventory.get("changed_units", [])
        for slot_id in change.get("authorized_draft_slot_ids", [])
    }
    blocking_changed = sorted({
        unit_id
        for query in queries.get("queries", [])
        if query.get("blocks_revision") is True
        for unit_id in query.get("affected_unit_ids", [])
        if unit_id in changed_source_units | changed_draft_slots
    })
    if blocking_changed:
        add("queries:blocking", f"blocking queries affect changed units: {blocking_changed}")

    if manifest.get("schema_name") != "review_change_manifest" or manifest.get("schema_version") != "0.1.0":
        add("manifest:identity", "change manifest identity is unsupported")
    if manifest.get("artifact_sha256") != payload_sha256(manifest, "artifact_sha256"):
        add("manifest:hash", "change manifest hash mismatch")
    exact_bindings = {
        "source_artifact": artifact_identity(source),
        "candidate_artifact": artifact_identity(candidate),
        "permission_ref": _permission_ref(permission),
        "proposal_ref": _proposal_ref(proposal),
        "lineage_ref": _artifact_ref(lineage),
        "protected_inventory_ref": _artifact_ref(inventory),
        "author_query_list_ref": _artifact_ref(queries),
    }
    for field, expected in exact_bindings.items():
        if manifest.get(field) != expected:
            add("manifest:binding", f"manifest {field} does not match exact artifact identity")
    manifest_changes = manifest.get("changes")
    if not isinstance(manifest_changes, list):
        add("manifest:changes", "manifest changes must be an array")
        manifest_changes = []
    inventory_ids = {item["inventory_change_id"] for item in expected_inventory.get("changed_units", [])}
    declared_inventory_ids = [item.get("inventory_change_id") for item in manifest_changes if isinstance(item, dict)]
    if len(declared_inventory_ids) != len(set(declared_inventory_ids)) or set(declared_inventory_ids) != inventory_ids:
        add("manifest:coverage", "manifest must cover every deterministic changed unit exactly once")
    expected_changes = expected_change_records(expected_inventory, permission, proposal)
    if manifest_changes != expected_changes:
        add("manifest:change_evidence", "manifest change records do not equal the deterministic contract-complete evidence")
    operation_ids = {item.get("operation_id") for item in proposal.get("operations", [])}
    if any(item.get("operation_id") not in operation_ids for item in manifest_changes if isinstance(item, dict)):
        add("manifest:operation_binding", "manifest change references an unknown operation")
    expected_protected_ids = {item["protected_change_id"] for item in expected_inventory.get("protected_changes", [])}
    if set(manifest.get("protected_change_ids", [])) != expected_protected_ids or len(manifest.get("protected_change_ids", [])) != len(expected_protected_ids):
        add("manifest:protected_coverage", "manifest must enumerate every protected change exactly once")
    if manifest.get("revision_mode") != proposal.get("revision_mode"):
        add("manifest:mode", "manifest revision mode differs from proposal")
    if manifest.get("upstream_closure_refs") != expected_upstream_closure_refs(phase7a, proposal):
        add("manifest:upstream_closure", "manifest does not bind the exact upstream closure used by operations")
    expected_warnings = expected_citation_support_warnings(source, candidate, proposal, phase7a)
    if manifest.get("citation_support_warnings") != expected_warnings:
        add("manifest:citation_support", "manifest citation-support warnings are incomplete or non-deterministic")
    if manifest.get("producer_state") != "ready_for_independent_qc":
        add("manifest:terminal_state", "valid producer state must be ready_for_independent_qc")
    if manifest.get("author_review_required") is not True:
        add("manifest:author_review", "author review must remain required")
    expected_handoff = {
        "interface_name": "module06_review_revision_admission",
        "interface_version": None,
        "state": "blocked_pending_module06_integration_contract",
    }
    if manifest.get("module06_handoff") != expected_handoff:
        add("manifest:h04", "H04 must remain blocked pending the Module 06 integration contract")
    if manifest.get("scientific_correctness_claimed") is not False or manifest.get("qc_pass_claimed") is not False:
        add("manifest:overclaim", "Phase 7B cannot claim scientific correctness or QC pass")
    return issues


def _schema_issues(validator: ModuleType, schema_path: Path, data_path: Path) -> list[dict[str, str]]:
    return [
        {"code": f"schema:{issue.keyword}", "message": f"{data_path.name}:{issue.path}: {issue.message}"}
        for issue in validator.validate_files(schema_path, data_path)
    ]


def _normalize_phase7a_paths(package: dict[str, Any], wrapper_path: Path) -> dict[str, Any]:
    for record in package.get("trusted_inputs", {}).values():
        if isinstance(record, dict) and isinstance(record.get("path"), str):
            raw = Path(record["path"])
            record["path"] = str(raw if raw.is_absolute() else (wrapper_path.parent / raw).resolve())
    return package


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-document", type=Path, required=True)
    parser.add_argument("--candidate-document", type=Path, required=True)
    parser.add_argument("--permission", type=Path, required=True)
    parser.add_argument("--expected-permission-sha256", required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--change-manifest", type=Path, required=True)
    parser.add_argument("--author-query-list", type=Path, required=True)
    parser.add_argument("--lineage-map", type=Path, required=True)
    parser.add_argument("--protected-inventory", type=Path, required=True)
    parser.add_argument("--phase7a-package", type=Path, required=True)
    parser.add_argument("--review-profile", type=Path)
    parser.add_argument("--application-receipt", type=Path, required=True)
    parser.add_argument("--package-validation-result", type=Path, required=True)
    parser.add_argument("--schemas-dir", type=Path, default=DEFAULT_SCHEMAS)
    parser.add_argument("--phase7a-validator", type=Path, default=DEFAULT_PHASE7A_VALIDATOR)
    parser.add_argument("--phase7a-schemas-dir", type=Path, default=DEFAULT_PHASE7A_SCHEMAS)
    parser.add_argument("--shared-validator", type=Path, default=DEFAULT_SHARED_VALIDATOR)
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args()
    try:
        verify_package_runtime_trust_root(
            schemas_dir=args.schemas_dir,
            phase7a_validator_path=args.phase7a_validator,
            phase7a_schemas_dir=args.phase7a_schemas_dir,
            shared_validator_path=args.shared_validator,
        )
        source = read_json(args.source_document)
        candidate = read_json(args.candidate_document)
        permission = read_json(args.permission)
        proposal = read_json(args.proposal)
        manifest = read_json(args.change_manifest)
        queries = read_json(args.author_query_list)
        lineage = read_json(args.lineage_map)
        inventory = read_json(args.protected_inventory)
        application_receipt = read_json(args.application_receipt)
        validation_result = read_json(args.package_validation_result)
        review_profile = read_json(args.review_profile) if args.review_profile else None
        phase7a = _normalize_phase7a_paths(read_json(args.phase7a_package), args.phase7a_package)
        validator = _load_module(args.shared_validator, "phase7b_shared_validator")
        schema_inputs = (
            ("review-revision-permission.schema.json", args.permission),
            ("review-revision-proposal.schema.json", args.proposal),
            ("review-change-manifest.schema.json", args.change_manifest),
            ("review-author-query-list.schema.json", args.author_query_list),
            ("review-revision-lineage-map.schema.json", args.lineage_map),
            ("review-protected-change-inventory.schema.json", args.protected_inventory),
            ("review-patch-application-receipt.schema.json", args.application_receipt),
            ("review-package-validation-result.schema.json", args.package_validation_result),
        )
        issues: list[dict[str, str]] = []
        for schema_name, data_path in schema_inputs:
            issues.extend(_schema_issues(validator, args.schemas_dir / schema_name, data_path))
        issues.extend(validate_revision_package(
            source, candidate, permission, args.expected_permission_sha256, proposal,
            manifest, queries, lineage, inventory, phase7a, review_profile,
            phase7a_validator_path=args.phase7a_validator,
            phase7a_schemas_dir=args.phase7a_schemas_dir,
            shared_validator_path=args.shared_validator,
        ))
        issues.extend(validate_revision_evidence(
            source, candidate, permission, proposal, manifest, lineage, inventory,
            queries, application_receipt, validation_result,
            shared_validator_path=args.shared_validator,
        ))
    except (OSError, json.JSONDecodeError, ReviewRevisionValidationError, KeyError, TypeError, ValueError) as exc:
        print(f"review revision validation error: {exc}", file=sys.stderr)
        return 2
    result = {
        "valid": not issues,
        "producer_state": "ready_for_independent_qc" if not issues else "blocked",
        "author_review_required": True,
        "module06_handoff_state": "blocked_pending_module06_integration_contract",
        "issue_count": len(issues),
        "issues": issues,
    }
    if args.json_report:
        write_json(args.json_report, result)
    if issues:
        for issue in issues:
            print(f"[{issue['code']}] {issue['message']}")
        return 1
    print("Phase 7B revision package valid; producer_state=ready_for_independent_qc; H04=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
