#!/usr/bin/env python3
"""Apply exact source-bound Article revision operations and emit trusted lineage.

This additive Phase 9 layer applies an untrusted prose proposal only after
checking the frozen revision contract. It derives candidate lineage from the
operation semantics; proposal authors cannot supply or relabel lineage.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from build_change_inventory import (
    artifact_identity,
    build_inventory,
    canonical_sha256,
    declared_lineage_map,
    document_sha256,
    read_json,
    text_sha256,
    validate_document,
    write_json,
)
from validate_revision_package import provenance_gate_issues


PATCH_LAYER_VERSION = "0.1.6"
PROPOSAL_SCHEMA_VERSION = "0.1.1"
LIGHT_OPERATIONS = {
    "grammar", "punctuation", "syntax", "clarity", "lexical_tightening",
    "redundancy_removal", "transition",
}
MEDIUM_ADDITIONAL_TEXT_OPERATIONS = {"information_reorder", "topic_sentence_repair"}
NONSTRUCTURAL_OPERATIONS = LIGHT_OPERATIONS | MEDIUM_ADDITIONAL_TEXT_OPERATIONS
MEDIUM_STRUCTURAL_OPERATIONS = {"sentence_split", "sentence_merge", "sentence_reorder"}
SUPPORTED_OPERATIONS = NONSTRUCTURAL_OPERATIONS | MEDIUM_STRUCTURAL_OPERATIONS | {"paragraph_move"}
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]+$")


class PatchApplicationError(RuntimeError):
    """Fail-closed proposal admission or application error with a stable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _fail(code: str, message: str) -> None:
    raise PatchApplicationError(code, message)


def _require_identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        _fail("proposal:shape", f"{field} must be a supported identifier")
    return value


def _contract_ref(contract: dict[str, Any]) -> dict[str, str]:
    return {
        "revision_contract_id": contract.get("revision_contract_id"),
        "revision_contract_version": contract.get("revision_contract_version"),
        "contract_sha256": contract.get("contract_sha256"),
    }


def _contract_payload_hash(contract: dict[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in contract.items() if key != "contract_sha256"})


def _index_source(source: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, tuple[dict[str, Any], dict[str, Any]]]]:
    paragraphs = {item["unit_id"]: item for item in source["paragraphs"]}
    sentences = {
        sentence["unit_id"]: (paragraph, sentence)
        for paragraph in source["paragraphs"]
        for sentence in paragraph["sentences"]
    }
    return paragraphs, sentences


def _candidate_from_source(source: dict[str, Any], candidate_ref: dict[str, Any]) -> dict[str, Any]:
    candidate = {
        "document_id": source["document_id"],
        "artifact_id": candidate_ref["artifact_id"],
        "artifact_version": candidate_ref["artifact_version"],
        "side": "candidate",
        "document_type": "original_article",
        "paragraphs": [],
    }
    for source_paragraph in source["paragraphs"]:
        paragraph = {
            "unit_id": source_paragraph["unit_id"],
            "source_unit_ids": [source_paragraph["unit_id"]],
            "section": source_paragraph["section"],
            "paragraph_function": copy.deepcopy(source_paragraph["paragraph_function"]),
            "experiment_labels": list(source_paragraph["experiment_labels"]),
            "sentences": [],
        }
        for source_sentence in source_paragraph["sentences"]:
            paragraph["sentences"].append({
                "unit_id": f"candidate:{source_sentence['unit_id']}",
                "source_unit_ids": [source_sentence["unit_id"]],
                "text": source_sentence["text"],
            })
        candidate["paragraphs"].append(paragraph)
    _refresh_candidate(candidate)
    return candidate


def _refresh_candidate(candidate: dict[str, Any]) -> None:
    for paragraph_ordinal, paragraph in enumerate(candidate["paragraphs"], start=1):
        paragraph["ordinal"] = paragraph_ordinal
        for sentence_ordinal, sentence in enumerate(paragraph["sentences"], start=1):
            sentence["ordinal"] = sentence_ordinal
        paragraph["text"] = " ".join(item["text"] for item in paragraph["sentences"])
        paragraph["locator"] = {
            "locator_type": "structured_unit",
            "side": "candidate",
            "artifact_id": candidate["artifact_id"],
            "unit_id": paragraph["unit_id"],
            "local_identifier": f"{paragraph['section']}/paragraph/{paragraph_ordinal}",
            "span_sha256": text_sha256(paragraph["text"]),
        }
    candidate["artifact_sha256"] = document_sha256(candidate)


def _candidate_paragraph(candidate: dict[str, Any], source_paragraph_id: str) -> dict[str, Any]:
    for paragraph in candidate["paragraphs"]:
        if paragraph["source_unit_ids"] == [source_paragraph_id]:
            return paragraph
    _fail("application:lineage", f"candidate paragraph for {source_paragraph_id} is unavailable")


def _candidate_sentence(paragraph: dict[str, Any], source_sentence_id: str) -> tuple[int, dict[str, Any]]:
    matches = [
        (index, sentence)
        for index, sentence in enumerate(paragraph["sentences"])
        if sentence.get("source_unit_ids") == [source_sentence_id]
    ]
    if len(matches) != 1:
        _fail("application:lineage", f"expected one candidate sentence for {source_sentence_id}")
    return matches[0]


def _validate_exact_texts(operation: dict[str, Any], actual_texts: list[str]) -> None:
    expected = operation.get("expected_source_texts")
    hashes = operation.get("expected_source_sha256s")
    if expected != actual_texts:
        _fail("proposal:stale_source_text", f"operation {operation.get('operation_id')} does not match exact source text")
    expected_hashes = [text_sha256(value) for value in actual_texts]
    if hashes != expected_hashes:
        _fail("proposal:stale_source_hash", f"operation {operation.get('operation_id')} does not match exact source hashes")


def _operation_parent_ids(
    operation: dict[str, Any],
    paragraph_index: dict[str, dict[str, Any]],
    sentence_index: dict[str, tuple[dict[str, Any], dict[str, Any]]],
) -> set[str]:
    operation_type = operation["operation_type"]
    targets = operation.get("target_unit_ids", [])
    if operation_type == "paragraph_move":
        unknown = sorted(set(targets) - set(paragraph_index))
        if unknown:
            _fail("proposal:unknown_target", f"unknown paragraph targets: {unknown}")
        return set(targets)
    unknown = sorted(set(targets) - set(sentence_index))
    if unknown:
        _fail("proposal:unknown_target", f"unknown sentence targets: {unknown}")
    return {sentence_index[item][0]["unit_id"] for item in targets}


def _validate_operation_admission(
    operation: dict[str, Any],
    source: dict[str, Any],
    contract: dict[str, Any],
    paragraph_index: dict[str, dict[str, Any]],
    sentence_index: dict[str, tuple[dict[str, Any], dict[str, Any]]],
    upstream_artifacts: dict[str, dict[str, Any]],
) -> set[str]:
    operation_id = _require_identifier(operation.get("operation_id"), "operation_id")
    operation_type = operation.get("operation_type")
    if operation_type not in SUPPORTED_OPERATIONS:
        _fail("operation:unsupported", f"operation {operation_id} is not implemented by patch layer {PATCH_LAYER_VERSION}")
    if operation_type not in set(contract.get("allowed_operations", [])):
        _fail("operation:not_allowed", f"operation {operation_id} is not authorized by the exact revision contract")
    targets = operation.get("target_unit_ids")
    if not isinstance(targets, list) or not targets or len(targets) != len(set(targets)):
        _fail("proposal:shape", f"operation {operation_id} target_unit_ids must be a non-empty unique array")
    parent_ids = _operation_parent_ids(operation, paragraph_index, sentence_index)
    if not parent_ids.issubset(set(contract.get("authorized_scope", {}).get("unit_ids", []))):
        _fail("scope:outside_authorized", f"operation {operation_id} targets a paragraph outside authorized_scope")
    mode = contract.get("revision_mode")
    if mode == "light" and operation_type not in LIGHT_OPERATIONS:
        _fail("mode:light_structural_effect", f"Light mode cannot apply {operation_type}")
    if mode == "medium" and operation_type == "paragraph_move":
        _fail("mode:medium_structural_effect", "Medium mode cannot move paragraphs")
    if operation_type == "paragraph_move" and mode != "deep":
        _fail("mode:deep_required", "paragraph_move requires Deep mode")
    sections = {
        paragraph_index[parent_id]["section"]
        for parent_id in parent_ids
    }
    section = next(iter(sections)) if len(sections) == 1 else None
    provenance_issues = provenance_gate_issues(
        operation, source["document_id"], parent_ids, section, upstream_artifacts
    )
    if provenance_issues:
        code, message = provenance_issues[0]
        _fail(code, message)
    return parent_ids


def _apply_sentence_operation(
    candidate: dict[str, Any],
    source_sentences: dict[str, tuple[dict[str, Any], dict[str, Any]]],
    operation: dict[str, Any],
) -> None:
    operation_type = operation["operation_type"]
    targets = operation["target_unit_ids"]
    source_pairs = [source_sentences[item] for item in targets]
    parent_ids = {pair[0]["unit_id"] for pair in source_pairs}
    if len(parent_ids) != 1:
        _fail("operation:cross_paragraph", "one sentence operation cannot cross paragraph boundaries")
    source_paragraph_id = next(iter(parent_ids))
    source_paragraph = source_pairs[0][0]
    source_order = [item["unit_id"] for item in source_paragraph["sentences"]]
    target_positions = [source_order.index(item) for item in targets]
    actual_texts = [pair[1]["text"] for pair in source_pairs]
    _validate_exact_texts(operation, actual_texts)
    candidate_paragraph = _candidate_paragraph(candidate, source_paragraph_id)
    replacements = operation.get("replacement_texts")
    if not isinstance(replacements, list) or not all(isinstance(item, str) and item.strip() for item in replacements):
        _fail("proposal:shape", "replacement_texts must be a non-empty-string array")

    if operation_type in NONSTRUCTURAL_OPERATIONS:
        if len(targets) != 1 or len(replacements) != 1:
            _fail("operation:cardinality", f"{operation_type} requires one source and one replacement sentence")
        if replacements[0] == actual_texts[0]:
            _fail("operation:no_change", "a replacement must differ from exact source text")
        _, sentence = _candidate_sentence(candidate_paragraph, targets[0])
        sentence["text"] = replacements[0]
        return

    if operation_type == "sentence_split":
        if len(targets) != 1 or len(replacements) < 2:
            _fail("operation:cardinality", "sentence_split requires one source and at least two replacements")
        position, _ = _candidate_sentence(candidate_paragraph, targets[0])
        digest = canonical_sha256({"operation": operation["operation_id"], "source": targets})[:16]
        generated = [
            {
                "unit_id": f"candidate-split:{digest}:{index}",
                "source_unit_ids": [targets[0]],
                "text": text,
            }
            for index, text in enumerate(replacements, start=1)
        ]
        candidate_paragraph["sentences"][position:position + 1] = generated
        return

    if operation_type == "sentence_merge":
        if len(targets) < 2 or len(replacements) != 1:
            _fail("operation:cardinality", "sentence_merge requires at least two sources and one replacement")
        if target_positions != list(range(min(target_positions), max(target_positions) + 1)):
            _fail("operation:noncontiguous", "sentence_merge targets must be contiguous and source ordered")
        digest = canonical_sha256({"operation": operation["operation_id"], "source": targets})[:16]
        generated = {
            "unit_id": f"candidate-merge:{digest}",
            "source_unit_ids": list(targets),
            "text": replacements[0],
        }
        start = min(target_positions)
        candidate_paragraph["sentences"][start:start + len(targets)] = [generated]
        return

    if operation_type == "sentence_reorder":
        if targets != source_order:
            _fail("operation:incomplete_reorder_scope", "sentence_reorder must bind every sentence in the paragraph in source order")
        order = operation.get("candidate_source_order")
        if not isinstance(order, list) or len(order) != len(targets) or set(order) != set(targets):
            _fail("operation:invalid_reorder", "candidate_source_order must be an exact permutation of target_unit_ids")
        if order == targets:
            _fail("operation:no_change", "candidate_source_order must change the order")
        if replacements:
            _fail("operation:invalid_reorder", "sentence_reorder cannot also replace sentence text")
        by_source = {item["source_unit_ids"][0]: item for item in candidate_paragraph["sentences"]}
        candidate_paragraph["sentences"] = [by_source[item] for item in order]
        return

    _fail("operation:unsupported", f"unhandled operation type: {operation_type}")


def _apply_paragraph_move(
    candidate: dict[str, Any],
    source: dict[str, Any],
    contract: dict[str, Any],
    operation: dict[str, Any],
) -> None:
    source_order = [item["unit_id"] for item in source["paragraphs"]]
    if operation["target_unit_ids"] != source_order:
        _fail("operation:incomplete_move_scope", "paragraph_move must bind all source paragraphs in source order")
    _validate_exact_texts(operation, [item["text"] for item in source["paragraphs"]])
    order = operation.get("candidate_source_order")
    if not isinstance(order, list) or len(order) != len(source_order) or set(order) != set(source_order):
        _fail("operation:invalid_move", "candidate_source_order must be an exact paragraph permutation")
    if order == source_order:
        _fail("operation:no_change", "candidate_source_order must change paragraph order")
    structural_ids = set(operation.get("structural_change_ids", []))
    if not structural_ids:
        _fail("deep:missing_structural_id", "paragraph_move requires an exact approved structural-change ID")
    authorizations = {
        item.get("structural_change_id"): item
        for item in contract.get("structural_change_authorizations", [])
        if isinstance(item, dict)
    }
    if not any(
        item in set(contract.get("approved_structural_change_ids", []))
        and authorizations.get(item, {}).get("author_approval") == "approved"
        and "paragraph_move" in authorizations.get(item, {}).get("allowed_effects", [])
        and set(source_order).issubset(set(authorizations.get(item, {}).get("source_unit_ids", [])))
        and set(order).issubset(set(authorizations.get(item, {}).get("candidate_unit_ids", [])))
        for item in structural_ids
    ):
        _fail("deep:authorization_scope", "paragraph_move lacks matching author-approved contract authorization")
    by_source = {item["source_unit_ids"][0]: item for item in candidate["paragraphs"]}
    candidate["paragraphs"] = [by_source[item] for item in order]


def _query_locator(source: dict[str, Any], unit_id: str) -> dict[str, Any]:
    for paragraph in source["paragraphs"]:
        if paragraph["unit_id"] == unit_id:
            return copy.deepcopy(paragraph["locator"])
        if any(sentence["unit_id"] == unit_id for sentence in paragraph["sentences"]):
            return copy.deepcopy(paragraph["locator"])
    _fail("query:unknown_unit", f"author query references unknown source unit {unit_id}")


def _make_query_list(source: dict[str, Any], candidate: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    queries: list[dict[str, Any]] = []
    for raw in proposal.get("author_queries", []):
        unit_ids = raw.get("affected_unit_ids")
        if not isinstance(unit_ids, list) or not unit_ids:
            _fail("query:shape", "author query affected_unit_ids must be non-empty")
        if raw.get("resolution_status") != "unresolved" or raw.get("author_response") is not None:
            _fail("query:authority", "patch proposals may create only unanswered unresolved author queries")
        queries.append({
            "query_id": _require_identifier(raw.get("query_id"), "query_id"),
            "query_class": raw.get("query_class"),
            "question": raw.get("question"),
            "affected_unit_ids": list(unit_ids),
            "affected_locators": [_query_locator(source, item) for item in unit_ids],
            "blocks_revision": raw.get("blocks_revision"),
            "resolution_status": "unresolved",
        })
    return {
        "schema_name": "author_query_list",
        "schema_version": "0.1.0",
        "artifact_id": f"author-query-list:{canonical_sha256(proposal)[:24]}",
        "created_at": proposal["created_at"],
        "created_by": f"article-polisher-patch-layer/{PATCH_LAYER_VERSION}",
        "status": "author_review_required",
        "source_artifact": artifact_identity(source),
        "candidate_artifact": artifact_identity(candidate),
        "queries": queries,
    }


def apply_revision_proposal(
    source: dict[str, Any],
    contract: dict[str, Any],
    proposal: dict[str, Any],
    upstream_artifacts: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return a candidate package or raise a stable fail-closed error."""
    upstream_artifacts = upstream_artifacts or {}
    document_issues = validate_document(source, "source")
    if document_issues:
        _fail("source:invalid", "; ".join(document_issues))
    if source.get("document_type") != "original_article":
        _fail("route:review_article_rejected", "Article Polisher accepts only original_article")
    if contract.get("contract_sha256") != _contract_payload_hash(contract):
        _fail("contract:hash", "revision contract self-hash mismatch")
    expected_source = artifact_identity(source)
    contract_source = {
        "document_id": contract.get("source_document_id"),
        "artifact_id": contract.get("source_artifact_id"),
        "artifact_version": contract.get("source_artifact_version"),
        "artifact_sha256": contract.get("source_artifact_sha256"),
    }
    if contract_source != expected_source:
        _fail("contract:source_binding", "revision contract does not bind the exact source artifact")
    if contract.get("authorized_scope", {}).get("document_id") != source["document_id"]:
        _fail("contract:scope_document", "authorized_scope does not bind the source document")
    origin = contract.get("authorization_origin")
    state = contract.get("authorization_state")
    if state not in {"caller_accepted", "author_approved"}:
        _fail("authorization:execution", "machine_proposed contracts do not authorize patch application")
    if state == "author_approved" and (origin != "author" or contract.get("author_approval") != "approved"):
        _fail("authorization:author_decision", "author_approved requires an approved author-origin decision")
    if origin == "calling_workflow" and state == "author_approved":
        _fail("authorization:caller_mint", "calling_workflow cannot mint author approval")

    if proposal.get("schema_name") != "article_polisher_revision_proposal" or proposal.get("schema_version") != PROPOSAL_SCHEMA_VERSION:
        _fail("proposal:identity", "unsupported revision proposal identity")
    _require_identifier(proposal.get("proposal_id"), "proposal_id")
    if proposal.get("status") != "machine_proposed":
        _fail("proposal:authority", "a prose proposal cannot assert approval")
    if proposal.get("source_artifact") != expected_source:
        _fail("proposal:source_binding", "proposal does not bind the exact source artifact")
    if proposal.get("revision_contract_ref") != _contract_ref(contract):
        _fail("proposal:contract_binding", "proposal does not bind the exact revision contract")
    candidate_ref = proposal.get("candidate_artifact")
    if not isinstance(candidate_ref, dict):
        _fail("proposal:shape", "candidate_artifact must be an object")
    if candidate_ref.get("document_id") != source["document_id"]:
        _fail("proposal:candidate_document", "candidate document_id must equal source document_id")
    _require_identifier(candidate_ref.get("artifact_id"), "candidate_artifact.artifact_id")
    if candidate_ref.get("artifact_id") == source["artifact_id"]:
        _fail("proposal:candidate_identity", "candidate artifact_id must differ from source artifact_id")
    if not isinstance(candidate_ref.get("artifact_version"), str):
        _fail("proposal:candidate_identity", "candidate artifact_version is required")

    operations = proposal.get("operations")
    if not isinstance(operations, list) or not operations:
        _fail("proposal:shape", "operations must be a non-empty array")
    operation_ids = [item.get("operation_id") for item in operations if isinstance(item, dict)]
    if len(operation_ids) != len(operations) or len(operation_ids) != len(set(operation_ids)):
        _fail("proposal:duplicate_operation", "operations must have unique operation_id values")
    paragraph_index, sentence_index = _index_source(source)
    parent_bindings: dict[str, dict[str, Any]] = {}
    has_paragraph_move = any(item.get("operation_type") == "paragraph_move" for item in operations)
    if has_paragraph_move and len(operations) != 1:
        _fail("operation:conflict", f"paragraph_move cannot be combined with another operation in patch layer {PATCH_LAYER_VERSION}")
    for operation in operations:
        parents = _validate_operation_admission(
            operation,
            source,
            contract,
            paragraph_index,
            sentence_index,
            upstream_artifacts,
        )
        for parent in parents:
            if parent in parent_bindings:
                _fail("operation:paragraph_conflict", f"patch layer {PATCH_LAYER_VERSION} permits at most one operation per source paragraph")
            parent_bindings[parent] = operation

    touched_units = set(parent_bindings)
    for operation in operations:
        touched_units.update(operation.get("target_unit_ids", []))
    for query in proposal.get("author_queries", []):
        if query.get("resolution_status") == "unresolved" and query.get("blocks_revision"):
            if set(query.get("affected_unit_ids", [])) & touched_units:
                _fail("query:blocking_unit_changed", "an unresolved blocking query intersects an applied operation")

    candidate = _candidate_from_source(source, candidate_ref)
    for operation in operations:
        if operation["operation_type"] == "paragraph_move":
            _apply_paragraph_move(candidate, source, contract, operation)
        else:
            _apply_sentence_operation(candidate, sentence_index, operation)
    _refresh_candidate(candidate)
    lineage = declared_lineage_map(source, candidate, origin="deterministic_patch_layer")
    inventory = build_inventory(source, candidate, lineage)
    if not inventory["changed_units"]:
        _fail("application:no_change", "proposal produced no deterministic source/candidate difference")

    changes: list[dict[str, Any]] = []
    for item in inventory["changed_units"]:
        matched = {parent_bindings.get(unit_id, {}).get("operation_id") for unit_id in item["source_unit_ids"]}
        matched.discard(None)
        if len(matched) != 1:
            _fail("manifest:operation_binding", "each deterministic change must map to exactly one applied operation")
        operation = next(value for value in operations if value["operation_id"] == next(iter(matched)))
        record = {
            "change_id": f"change:{canonical_sha256({'proposal': proposal['proposal_id'], 'inventory': item['inventory_change_id']})[:24]}",
            "inventory_change_id": item["inventory_change_id"],
            "source_unit_ids": item["source_unit_ids"],
            "candidate_unit_ids": item["candidate_unit_ids"],
            "source_locators": item["source_locators"],
            "candidate_locators": item["candidate_locators"],
            "source_representation_sha256": item["source_representation_sha256"],
            "candidate_representation_sha256": item["candidate_representation_sha256"],
            "section": item["section"],
            "paragraph_function": item["paragraph_function"],
            "experiment_labels": item["experiment_labels"],
            "revision_mode": contract["revision_mode"],
            "operation_type": operation["operation_type"],
            "authorization_origin": contract["authorization_origin"],
            "authorization_state": contract["authorization_state"],
            "affected_protected_anchor_ids": list(operation.get("affected_protected_anchor_ids", [])),
            "rationale": operation["rationale"],
            "risk_class": operation["risk_class"],
            "author_review_required": True,
            "structural_change_ids": list(operation.get("structural_change_ids", [])),
            "upstream_artifact_refs": copy.deepcopy(operation.get("upstream_artifact_refs", [])),
        }
        if operation.get("source_proposition_ids"):
            record["source_proposition_ids"] = list(operation["source_proposition_ids"])
        if operation.get("profile_feature_ref"):
            record["profile_feature_ref"] = copy.deepcopy(operation["profile_feature_ref"])
        changes.append(record)

    manifest = {
        "schema_name": "change_manifest",
        "schema_version": "0.1.1",
        "artifact_id": f"change-manifest:{canonical_sha256(proposal)[:24]}",
        "created_at": proposal["created_at"],
        "created_by": f"article-polisher-patch-layer/{PATCH_LAYER_VERSION}",
        "status": "author_review_required",
        "source_artifact": artifact_identity(source),
        "candidate_artifact": artifact_identity(candidate),
        "revision_contract_ref": _contract_ref(contract),
        "changes": changes,
    }
    queries = _make_query_list(source, candidate, proposal)
    receipt = {
        "schema_name": "article_polisher_patch_application_receipt",
        "schema_version": "0.1.0",
        "patch_layer_version": PATCH_LAYER_VERSION,
        "proposal_id": proposal["proposal_id"],
        "source_artifact": artifact_identity(source),
        "candidate_artifact": artifact_identity(candidate),
        "revision_contract_ref": _contract_ref(contract),
        "applied_operation_ids": operation_ids,
        "lineage_origin": "deterministic_patch_layer",
        "terminal_state": "ready_for_package_validation",
        "scientific_safety_claimed": False,
        "author_approval_claimed": False,
    }
    return {
        "candidate-document.json": candidate,
        "revision-lineage-map.json": lineage,
        "change-manifest.json": manifest,
        "author-query-list.json": queries,
        "change-inventory.json": inventory,
        "patch-application-receipt.json": receipt,
    }


def _write_report(path: Path | None, value: dict[str, Any]) -> None:
    if path is not None:
        write_json(path, value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-document", type=Path, required=True)
    parser.add_argument("--revision-contract", type=Path, required=True)
    parser.add_argument("--revision-proposal", type=Path, required=True)
    parser.add_argument("--upstream-artifact", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--validator", type=Path)
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args()
    try:
        from schema_runtime import discover_validator, load_validator
        from validate_revision_package import (
            DEFAULT_SCHEMAS,
            _read_upstream_artifacts,
            _revision_contract_schema_issues,
            _schema_issues,
            validate_revision_package,
        )

        package_root = Path(__file__).resolve().parents[1]
        validator = load_validator(discover_validator(args.validator))
        proposal_schema = package_root / "schemas" / "revision-proposal.schema.json"
        schema_issues = _schema_issues(validator, proposal_schema, args.revision_proposal)
        if schema_issues:
            _fail("proposal:schema", json.dumps(schema_issues, ensure_ascii=False))
        source = read_json(args.source_document)
        contract = read_json(args.revision_contract)
        proposal = read_json(args.revision_proposal)
        contract_schema_issues = _revision_contract_schema_issues(validator, contract)
        if contract_schema_issues:
            _fail("contract:schema", json.dumps(contract_schema_issues, ensure_ascii=False))
        upstream_issues: list[dict[str, str]] = []
        upstream = _read_upstream_artifacts(args.upstream_artifact, validator, upstream_issues)
        if upstream_issues:
            _fail("upstream:invalid", json.dumps(upstream_issues, ensure_ascii=False))
        artifacts = apply_revision_proposal(source, contract, proposal, upstream)
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            write_json(temp / "change-manifest.json", artifacts["change-manifest.json"])
            write_json(temp / "author-query-list.json", artifacts["author-query-list.json"])
            issues = []
            issues.extend(_schema_issues(validator, DEFAULT_SCHEMAS / "change-manifest.schema.json", temp / "change-manifest.json"))
            issues.extend(_schema_issues(validator, DEFAULT_SCHEMAS / "author-query-list.schema.json", temp / "author-query-list.json"))
            semantic, rebuilt = validate_revision_package(
                source,
                artifacts["candidate-document.json"],
                contract,
                artifacts["change-manifest.json"],
                artifacts["author-query-list.json"],
                upstream,
                artifacts["revision-lineage-map.json"],
            )
            issues.extend(semantic)
            if rebuilt != artifacts["change-inventory.json"]:
                issues.append({"layer": "patch", "path": "$", "code": "inventory:rebuild_mismatch", "message": "frozen core rebuilt a different inventory"})
        if issues:
            _write_report(args.json_report, {"valid": False, "ready_for_independent_qc": False, "issues": issues})
            for issue in issues:
                print(f"{issue['layer']} {issue['path']} [{issue['code']}] {issue['message']}")
            return 1
        output_dir = args.output_dir.resolve()
        if output_dir.exists() and any(output_dir.iterdir()):
            _fail("output:not_empty", f"output directory is not empty: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, value in artifacts.items():
            write_json(output_dir / name, value)
        report = {
            "valid": True,
            "ready_for_independent_qc": True,
            "author_review_required": True,
            "scientific_safety_claimed": False,
            "outputs": sorted(artifacts),
            "issues": [],
        }
        _write_report(args.json_report, report)
        print("Revision proposal applied; package valid and ready for independent QC and author review")
        return 0
    except (OSError, json.JSONDecodeError, PatchApplicationError, RuntimeError) as exc:
        code = exc.code if isinstance(exc, PatchApplicationError) else "application:error"
        message = exc.message if isinstance(exc, PatchApplicationError) else str(exc)
        _write_report(args.json_report, {"valid": False, "ready_for_independent_qc": False, "issues": [{"code": code, "message": message}]})
        print(f"patch application error [{code}]: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
