"""Independent synthetic fixture builder for Phase 7A contract tests."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
STAMP = "2026-08-31T00:00:00Z"


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def payload_sha256(value: dict[str, Any], field: str) -> str:
    return canonical_sha256({key: item for key, item in value.items() if key != field})


def _governed_projection(value: Any) -> Any:
    if isinstance(value, list):
        return [_governed_projection(item) for item in value]
    if not isinstance(value, dict):
        return value
    omitted = {
        "artifact_sha256",
        "source_record_sha256",
        "record_sha256",
        "decision_ref",
        "decision_refs",
        "unresolved_decision_refs",
        "access_verification_ref",
    }
    return {
        key: _governed_projection(item)
        for key, item in value.items()
        if key not in omitted and not key.endswith("_decision_ref")
    }


def governed_subject_sha256(value: Any) -> str:
    return canonical_sha256(_governed_projection(value))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact_ref(value: dict[str, Any]) -> dict[str, str]:
    return {
        "artifact_id": value["artifact_id"],
        "artifact_version": value["schema_version"],
        "artifact_sha256": value["artifact_sha256"],
    }


def decision_ref(value: dict[str, Any]) -> dict[str, str]:
    return {
        "decision_id": value["decision_id"],
        "interface_version": value["interface_version"],
        "decision_sha256": value["decision_sha256"],
    }


def make_decision(
    decision_id: str,
    decision_type: str,
    subject_type: str,
    subject_id: str,
    asserted_state: str,
    *,
    role: str = "authorized_review_workflow",
    input_binding: tuple[str, str] | None = None,
    subject_version: str = "0.1.0",
    subject_sha256: str = "0" * 64,
) -> dict[str, Any]:
    is_author = role == "author"
    record: dict[str, Any] = {
        "interface_name": "review_authority_decision",
        "interface_version": "0.1.0",
        "decision_id": decision_id,
        "decision_sha256": "0" * 64,
        "decision_type": decision_type,
        "subject_refs": [
            {
                "subject_type": subject_type,
                "subject_id": subject_id,
                "asserted_state": asserted_state,
                "artifact_version": subject_version,
                "artifact_sha256": subject_sha256,
            }
        ],
        "decision_value": "approve" if is_author else ("confirm" if decision_type == "source_access_verification" else "resolve"),
        "authorization_origin": "author" if is_author else "calling_workflow",
        "authorization_state": "author_approved" if is_author else "caller_accepted",
        "decision_producer_role": role,
        "created_at": STAMP,
        "created_by": "synthetic-authority-fixture",
        "reviewed_by": "synthetic-calling-workflow",
        "upstream_input_bindings": [],
    }
    if input_binding is not None:
        record["upstream_input_bindings"].append(
            {"input_id": input_binding[0], "input_sha256": input_binding[1]}
        )
    record["decision_sha256"] = payload_sha256(record, "decision_sha256")
    return record


def _source_record(
    number: int,
    access_ref: dict[str, str],
    independence_ref: dict[str, str],
) -> dict[str, Any]:
    source_id = f"source-{number}"
    extraction_id = f"extract-{number}"
    record: dict[str, Any] = {
        "source_id": source_id,
        "source_record_sha256": "0" * 64,
        "bibliographic_identity": {
            "title": f"Synthetic study {number}",
            "authors": [f"Author {number}"],
            "year": 2024 + number,
            "journal": "Synthetic Contract Tests",
            "identity_records": [
                {"identity_type": "doi", "value": f"10.0000/synthetic.{number}"}
            ],
        },
        "publication_status": "current",
        "verification_origin": "authorized_retrieval_workflow",
        "verification_timestamp": STAMP,
        "access_level": "full_text_verified",
        "access_verification_origin": "authorized_retrieval_or_verification_workflow",
        "access_verification_status": "approved",
        "access_verification_ref": access_ref,
        "source_locators": [],
        "inclusion_status": "included",
        "exclusion_reason": None,
        "linked_source_ids": [],
        "evidence_unit_id": f"evidence-unit-{number}",
        "independence_status": "independent",
        "assignment_origin": "authorized_retrieval_or_review_workflow",
        "independence_review_status": "approved",
        "independence_decision_ref": independence_ref,
        "extraction_record_ids": [extraction_id],
    }
    record["source_record_sha256"] = payload_sha256(record, "source_record_sha256")
    return record


def _extraction(number: int, registry_ref: dict[str, str]) -> dict[str, Any]:
    content = (
        "The intervention increased the measured response in the defined model system."
        if number == 1
        else "An independent experiment reported a response in the same direction under a related condition."
    )
    span_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    record: dict[str, Any] = {
        "interface_name": "review_extraction_record",
        "interface_version": "0.1.0",
        "record_sha256": "0" * 64,
        "extraction_record_id": f"extract-{number}",
        "source_registry_ref": registry_ref,
        "source_id": f"source-{number}",
        "evidence_unit_id": f"evidence-unit-{number}",
        "extraction_type": "result",
        "source_access_level": "full_text_verified",
        "source_locator": {
            "locator_type": "line_char_range",
            "side": "source",
            "file_id": f"trusted-source-{number}",
            "unit_id": f"line-2-source-{number}",
            "start_line": 2,
            "end_line": 2,
            "start_char": 0,
            "end_char": len(content),
            "span_sha256": span_sha256,
        },
        "source_span_sha256": span_sha256,
        "extracted_content": content,
        "normalized_proposition": "The tested condition was associated with an increased response.",
        "extraction_origin": "model_assisted_extraction",
        "review_status": "author_review_required",
        "review_decision_origin": "model_proposed",
        "reviewer_identity": None,
    }
    record["record_sha256"] = payload_sha256(record, "record_sha256")
    return record


def _refresh_decision_refs(value: Any, decisions: dict[str, dict[str, Any]]) -> None:
    if isinstance(value, list):
        for item in value:
            _refresh_decision_refs(item, decisions)
        return
    if not isinstance(value, dict):
        return
    decision_id = value.get("decision_id")
    if decision_id in decisions and "interface_version" in value and "decision_sha256" in value:
        value["interface_version"] = decisions[decision_id]["interface_version"]
        value["decision_sha256"] = decisions[decision_id]["decision_sha256"]
    for item in value.values():
        _refresh_decision_refs(item, decisions)


def _governed_subject(package: dict[str, Any], subject: dict[str, Any]) -> tuple[str, Any] | None:
    subject_type = subject.get("subject_type")
    subject_id = subject.get("subject_id")
    scope = package["scope"]
    registry = package["registry"]
    synthesis = package["synthesis"]
    if subject_type == "scope" and scope.get("artifact_id") == subject_id:
        return scope.get("schema_version", ""), scope
    if subject_type == "coverage_record" and scope.get("coverage", {}).get("coverage_id") == subject_id:
        return scope.get("schema_version", ""), scope["coverage"]
    if subject_type == "author_objective":
        record = next((item for item in scope.get("author_objectives", []) if item.get("author_objective_id") == subject_id), None)
        return (scope.get("schema_version", ""), record) if record is not None else None
    if subject_type in {"source_record", "evidence_unit", "study_family"}:
        key = {"source_record": "source_id", "evidence_unit": "evidence_unit_id", "study_family": "study_family_id"}[subject_type]
        record = next((item for item in registry.get("source_records", []) if item.get(key) == subject_id), None)
        return (registry.get("schema_version", ""), record) if record is not None else None
    if subject_type == "extraction_record":
        record = next((item for item in package["extractions"] if item.get("extraction_record_id") == subject_id), None)
        return (record.get("interface_version", ""), record) if record is not None else None
    synthesis_keys = {
        "taxonomy_axis": ("taxonomy_axes", "axis_id"),
        "synthesis_claim": ("claims", "claim_id"),
        "author_position": ("claims", "claim_id"),
        "support_relation": ("citation_relations", "relation_id"),
    }
    if subject_type in synthesis_keys:
        collection, key = synthesis_keys[subject_type]
        record = next((item for item in synthesis.get(collection, []) if item.get(key) == subject_id), None)
        return (synthesis.get("schema_version", ""), record) if record is not None else None
    if subject_type == "review_outline" and package["outline"].get("artifact_id") == subject_id:
        return package["outline"].get("schema_version", ""), package["outline"]
    return None


def rehash_package(
    package: dict[str, Any],
    *,
    refresh_decision_subjects: bool = True,
) -> dict[str, Any]:
    """Refresh all intentional hashes and forward references after a test mutation."""
    records = package["authority_bundle"]["records"]
    if refresh_decision_subjects:
        for decision in records:
            for subject in decision.get("subject_refs", []):
                governed = _governed_subject(package, subject)
                if governed is not None:
                    subject["artifact_version"] = governed[0]
                    subject["artifact_sha256"] = governed_subject_sha256(governed[1])
    for decision in records:
        decision["decision_sha256"] = payload_sha256(decision, "decision_sha256")
    decisions = {item["decision_id"]: item for item in records}
    for key in ("scope", "registry", "extractions", "synthesis", "outline"):
        _refresh_decision_refs(package[key], decisions)

    scope = package["scope"]
    scope["artifact_sha256"] = payload_sha256(scope, "artifact_sha256")

    registry = package["registry"]
    registry["scope_ref"] = artifact_ref(scope)
    for source in registry["source_records"]:
        source["source_record_sha256"] = payload_sha256(source, "source_record_sha256")
    registry["artifact_sha256"] = payload_sha256(registry, "artifact_sha256")

    for extraction in package["extractions"]:
        extraction["source_registry_ref"] = artifact_ref(registry)
        extraction["record_sha256"] = payload_sha256(extraction, "record_sha256")

    synthesis = package["synthesis"]
    synthesis["scope_ref"] = artifact_ref(scope)
    synthesis["source_registry_ref"] = artifact_ref(registry)
    synthesis["artifact_sha256"] = payload_sha256(synthesis, "artifact_sha256")

    outline = package["outline"]
    outline["scope_ref"] = artifact_ref(scope)
    outline["source_registry_ref"] = artifact_ref(registry)
    outline["synthesis_ref"] = artifact_ref(synthesis)
    outline["artifact_sha256"] = payload_sha256(outline, "artifact_sha256")

    package["authority_manifest_sha256"] = canonical_sha256(package["authority_bundle"])
    return package


def build_valid_package() -> dict[str, Any]:
    input_paths = {
        "trusted-source-1": FIXTURES / "trusted-source-1.txt",
        "trusted-source-2": FIXTURES / "trusted-source-2.txt",
    }
    trusted_hashes = {key: file_sha256(path) for key, path in input_paths.items()}
    decisions = [
        make_decision(
            "access-source-1", "source_access_verification", "source_record", "source-1",
            "full_text_verified", role="authorized_retrieval_or_verification_workflow",
            input_binding=("trusted-source-1", trusted_hashes["trusted-source-1"]),
        ),
        make_decision(
            "access-source-2", "source_access_verification", "source_record", "source-2",
            "full_text_verified", role="authorized_retrieval_or_verification_workflow",
            input_binding=("trusted-source-2", trusted_hashes["trusted-source-2"]),
        ),
        make_decision(
            "independence-unit-1", "independence_resolution", "evidence_unit",
            "evidence-unit-1", "independent",
        ),
        make_decision(
            "independence-unit-2", "independence_resolution", "evidence_unit",
            "evidence-unit-2", "independent",
        ),
    ]
    decision_by_id = {item["decision_id"]: item for item in decisions}

    scope: dict[str, Any] = {
        "schema_name": "review_scope_contract",
        "schema_version": "0.1.0",
        "contract_version": "0.1.3",
        "artifact_id": "review-scope-1",
        "artifact_sha256": "0" * 64,
        "created_at": STAMP,
        "created_by": "phase7a-fixture",
        "status": "author_review_required",
        "document_type": "review_article",
        "review_type": "narrative_review",
        "execution_mode": "executable",
        "review_question": "How does the intervention affect the response in the defined system?",
        "target_audience": "researchers",
        "intended_use": "synthetic contract validation",
        "scope_boundaries": {
            "population_or_system": "defined synthetic model system",
            "biological_context": "controlled synthetic context",
            "method_or_intervention": "synthetic intervention",
            "date_window": {"start": "2020", "end": "2026"},
            "publication_types": ["primary research"],
            "languages": ["English"],
            "inclusion_rules": ["Source identity and access must be verified."],
            "exclusion_rules": ["Exclude unverifiable sources."],
        },
        "permitted_source_ids": ["source-1", "source-2"],
        "coverage": {
            "coverage_id": "coverage-1",
            "basis": "User-supplied admitted source set; no field-wide completeness claim.",
            "known_blind_spots": ["No exhaustive retrieval was performed."],
            "coverage_origin": "model_proposed",
            "coverage_review_status": "author_review_required",
        },
        "author_objectives": [],
        "protocol_artifact_refs": [],
        "authorization": {
            "authorization_origin": "calling_workflow",
            "authorization_state": "machine_proposed",
        },
        "unresolved_decision_refs": [],
        "unresolved_queries": [],
    }
    scope["artifact_sha256"] = payload_sha256(scope, "artifact_sha256")

    source_records = [
        _source_record(1, decision_ref(decision_by_id["access-source-1"]), decision_ref(decision_by_id["independence-unit-1"])),
        _source_record(2, decision_ref(decision_by_id["access-source-2"]), decision_ref(decision_by_id["independence-unit-2"])),
    ]
    registry: dict[str, Any] = {
        "schema_name": "review_source_registry",
        "schema_version": "0.1.0",
        "contract_version": "0.1.3",
        "artifact_id": "review-source-registry-1",
        "artifact_sha256": "0" * 64,
        "created_at": STAMP,
        "created_by": "phase7a-fixture",
        "status": "author_review_required",
        "scope_ref": artifact_ref(scope),
        "source_records": source_records,
    }
    registry["artifact_sha256"] = payload_sha256(registry, "artifact_sha256")
    extractions = [_extraction(1, artifact_ref(registry)), _extraction(2, artifact_ref(registry))]

    synthesis: dict[str, Any] = {
        "schema_name": "review_synthesis_matrix",
        "schema_version": "0.1.0",
        "contract_version": "0.1.3",
        "artifact_id": "review-synthesis-1",
        "artifact_sha256": "0" * 64,
        "created_at": STAMP,
        "created_by": "phase7a-fixture",
        "status": "author_review_required",
        "scope_ref": artifact_ref(scope),
        "source_registry_ref": artifact_ref(registry),
        "taxonomy_axes": [
            {
                "axis_id": "axis-context",
                "axis_kind": "descriptive_axis",
                "label": "Experimental context",
                "categories": ["related condition"],
                "classifications": [
                    {"subject_id": "source-1", "category": "related condition", "assignment_origin": "model_proposed", "review_status": "author_review_required"},
                    {"subject_id": "source-2", "category": "related condition", "assignment_origin": "model_proposed", "review_status": "author_review_required"},
                ],
                "rubric_ref": None,
                "review_status": "author_review_required",
            }
        ],
        "themes": [
            {"theme_id": "theme-response", "label": "Response direction", "axis_ids": ["axis-context"], "category_labels": ["related condition"]}
        ],
        "evidence_clusters": [
            {
                "cluster_id": "cluster-response",
                "theme_ids": ["theme-response"],
                "source_ids": ["source-1", "source-2"],
                "extraction_record_ids": ["extract-1", "extract-2"],
                "evidence_unit_ids": ["evidence-unit-1", "evidence-unit-2"],
                "agreement_status": "agreement",
                "negative_or_conflicting_evidence_present": False,
            }
        ],
        "claims": [
            {
                "claim_id": "claim-response",
                "theme_ids": ["theme-response"],
                "claim_origin": "cross_source_synthesis",
                "statement": "Both admitted sources report a response in the same direction.",
                "source_ids": ["source-1", "source-2"],
                "extraction_record_ids": ["extract-1", "extract-2"],
                "evidence_unit_ids": ["evidence-unit-1", "evidence-unit-2"],
                "study_family_ids": [],
                "evidence_cluster_ids": ["cluster-response"],
                "basis_refs": [],
                "support_status": "not_assessed",
                "agreement_scope": "admitted_source_set",
                "access_constraint": "full_text_verified",
                "relation_origin": "model_proposed",
                "review_status": "author_review_required",
                "scope_boundaries": ["Only the two admitted synthetic sources are covered."],
                "limitations": ["Scientific truth is outside this fixture."],
            }
        ],
        "citation_relations": [
            {
                "relation_id": "relation-response",
                "claim_id": "claim-response",
                "source_ids": ["source-1", "source-2"],
                "extraction_record_ids": ["extract-1", "extract-2"],
                "citation_locator": "Synthetic source records 1 and 2",
                "support_relation": "partial_support",
                "relation_origin": "extraction_backed",
                "review_status": "author_review_required",
                "access_constraint": "full_text_verified",
                "actual_access_level": "full_text_verified",
            }
        ],
        "conflicts": [
            {"conflict_id": "conflict-1", "source_ids": ["source-1", "source-2"], "extraction_record_ids": ["extract-1", "extract-2"], "evidence_unit_ids": ["evidence-unit-1", "evidence-unit-2"], "cause_status": "unresolved", "review_status": "author_review_required"}
        ],
        "limitations": [
            {"limitation_id": "limitation-1", "description": "Only a synthetic admitted set is represented.", "source_ids": ["source-1", "source-2"], "extraction_record_ids": ["extract-1", "extract-2"], "review_status": "author_review_required"}
        ],
        "gaps": [
            {"gap_id": "gap-1", "gap_type": "validation_gap", "gap_basis_status": "directly_observed_in_admitted_set", "source_set_boundary": "Two admitted synthetic sources", "source_ids": ["source-1", "source-2"], "evidence_unit_ids": ["evidence-unit-1", "evidence-unit-2"], "supporting_source_count": 2, "independent_evidence_unit_count": 2, "degraded_state": "scope_limited", "review_status": "author_review_required"}
        ],
        "source_coverage_audit": {
            "included_source_ids": ["source-1", "source-2"],
            "assigned_source_ids": ["source-1", "source-2"],
            "unassigned_sources": [],
        },
    }
    synthesis["artifact_sha256"] = payload_sha256(synthesis, "artifact_sha256")

    outline: dict[str, Any] = {
        "schema_name": "review_outline",
        "schema_version": "0.1.0",
        "contract_version": "0.1.3",
        "artifact_id": "review-outline-1",
        "artifact_sha256": "0" * 64,
        "created_at": STAMP,
        "created_by": "phase7a-fixture",
        "status": "author_review_required",
        "scope_ref": artifact_ref(scope),
        "source_registry_ref": artifact_ref(registry),
        "synthesis_ref": artifact_ref(synthesis),
        "review_type": "narrative_review",
        "profile_guidance": None,
        "taxonomy_axis_ids": ["axis-context"],
        "section_plans": [
            {
                "section_id": "section-response",
                "title": "Response across the admitted set",
                "theme_ids": ["theme-response"],
                "paragraph_plans": [
                    {
                        "paragraph_id": "paragraph-response",
                        "role": "synthesis",
                        "theme_id": "theme-response",
                        "claim_ids": ["claim-response"],
                        "evidence_cluster_ids": ["cluster-response"],
                        "source_ids": ["source-1", "source-2"],
                        "conflict_ids": ["conflict-1"],
                        "limitation_ids": ["limitation-1"],
                        "gap_ids": ["gap-1"],
                    }
                ],
            }
        ],
        "placed_conflict_ids": ["conflict-1"],
        "placed_limitation_ids": ["limitation-1"],
        "placed_gap_ids": ["gap-1"],
        "source_coverage_audit": {
            "included_source_ids": ["source-1", "source-2"],
            "assigned_source_ids": ["source-1", "source-2"],
            "unassigned_sources": [],
        },
        "candidate_figure_table_briefs": [],
        "decision_refs": [decision_ref(item) for item in decisions],
        "unresolved_queries": [],
        "terminal_state": "ready_for_author_review",
    }
    outline["artifact_sha256"] = payload_sha256(outline, "artifact_sha256")

    package = {
        "scope": scope,
        "registry": registry,
        "extractions": extractions,
        "authority_bundle": {"manifest_version": "0.1.0", "records": decisions},
        "authority_manifest_sha256": "",
        "trusted_inputs": {
            key: {"path": path, "sha256": trusted_hashes[key]}
            for key, path in input_paths.items()
        },
        "trusted_input_paths": input_paths,
        "synthesis": synthesis,
        "outline": outline,
    }
    return rehash_package(package)


def clone_package(package: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(package)
