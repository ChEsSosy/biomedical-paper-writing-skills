#!/usr/bin/env python3
"""Validate a Phase 8A Scientific Figure Designer package.

This validator implements only deterministic contract claims: JSON structure,
exact identities and hashes, trusted source-file inspection for supported
formats, structured upstream relation closure, unit/replicate consistency,
analysis-output provenance, external authority bindings, and non-circular QC
hashing.  It does not render figures, compute statistics, judge scientific
support, inspect aesthetics, or decide copyright similarity.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from schema_runtime import SchemaRuntimeError, validate_document


VALIDATOR_VERSION = "0.1.2"
RULESET_VERSION = "0.1.2"
DEFAULT_MANIFEST = "design-package-manifest.json"
TRUST_INTERFACES = (
    "trusted_source_inputs",
    "trusted_analysis_outputs",
    "trusted_authority_inputs",
)
SCHEMAS = {
    "manifest": "design-package-manifest.schema.json",
    "source_data_manifest": "source-data-manifest.schema.json",
    "figure_card": "figure-card.schema.json",
    "figure_contract": "figure-contract.schema.json",
    "plot_recipe": "plot-recipe.schema.json",
    "figure_qc": "figure-qc.schema.json",
    "trusted_source_inputs": "trusted-source-inputs.schema.json",
    "trusted_analysis_outputs": "analysis-output-record.schema.json",
    "trusted_authority_inputs": "figure-authority-decision.schema.json",
    "trusted_inputs_root": "trusted-inputs-root.schema.json",
}
CEILING_RANKS = {
    "strength": {"descriptive": 0, "associative": 1, "comparative": 2, "explanatory": 3},
    "causality": {"none": 0, "association": 1, "causal": 2},
    "mechanism": {"none": 0, "suggestive": 1, "established": 2},
    "generalization": {"system_only": 0, "bounded_extension": 1, "broad": 2},
}
AUTHOR_ONLY_DECISIONS = {
    "representative_image_selection",
    "material_evidence_omission",
    "panel_freeze",
    "figure_conclusion_freeze",
    "layout_decision",
    "design_acceptance",
    "finality_decision",
}
DECISION_SUBJECTS = {
    "representative_image_selection": "representative_image",
    "material_evidence_omission": "evidence_omission",
    "panel_freeze": "figure_card",
    "figure_conclusion_freeze": "figure_contract",
    "layout_decision": "layout",
    "design_acceptance": "figure_contract",
    "finality_decision": "finality",
    "analysis_output_review": "analysis_output",
}
PROHIBITED_IMAGE_OPERATIONS = {
    "local_masking", "cloning", "generative_fill", "hidden_splicing", "object_relocation"
}


class FigurePackageError(RuntimeError):
    """Raised when the package cannot be loaded enough to produce a QC record."""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def payload_sha256(value: dict[str, Any], hash_field: str) -> str:
    return canonical_sha256({key: item for key, item in value.items() if key != hash_field})


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _governed_projection(value: Any) -> Any:
    """Remove only self-hashes and external decision links from a subject hash."""
    if isinstance(value, list):
        return [_governed_projection(item) for item in value]
    if not isinstance(value, dict):
        return value
    omitted = {
        "artifact_sha256", "record_sha256", "collection_sha256", "decision_sha256",
        "decision_ref", "decision_refs", "finality_decision_ref"
    }
    return {
        key: _governed_projection(item)
        for key, item in value.items()
        if key not in omitted and not key.endswith("_decision_ref")
    }


def governed_content_sha256(value: Any) -> str:
    return canonical_sha256(_governed_projection(value))


def artifact_identity(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_id": value.get("artifact_id"),
        "artifact_version": value.get("schema_version"),
        "artifact_sha256": value.get("artifact_sha256"),
    }


def decision_ref(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision_id": value.get("decision_id"),
        "interface_version": value.get("interface_version"),
        "decision_sha256": value.get("decision_sha256"),
    }


def analysis_output_ref(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "analysis_output_id": value.get("analysis_output_id"),
        "record_version": value.get("record_version"),
        "record_sha256": value.get("record_sha256"),
    }


def _contains_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def _ids(records: Iterable[dict[str, Any]], key: str) -> set[str]:
    return {item.get(key) for item in records if isinstance(item.get(key), str)}


def _index(
    records: Any,
    key: str,
    path: str,
    add: Any,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(records, list):
        add(f"identity:{key}_collection", f"{path} must be an array", path)
        return result
    for index, record in enumerate(records):
        value = record.get(key) if isinstance(record, dict) else None
        if not isinstance(value, str) or not value:
            add(f"identity:missing_{key}", f"record lacks {key}", f"{path}[{index}]")
            continue
        if value in result:
            add(f"identity:duplicate_{key}", f"duplicate {key}: {value}", f"{path}[{index}].{key}")
            continue
        result[value] = record
    return result


def _safe_package_path(root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _resolve_trusted_path(root: Path, record: dict[str, Any]) -> Path | None:
    path_value = record.get("path")
    if not isinstance(path_value, str) or not path_value:
        return None
    if record.get("access_mode") == "package_relative_file":
        return _safe_package_path(root, path_value)
    if record.get("access_mode") == "external_file":
        return Path(path_value).resolve()
    return None


def _load_bound_json(
    root: Path,
    ref: Any,
    path: str,
    add: Any,
) -> tuple[dict[str, Any] | None, Path | None]:
    if not isinstance(ref, dict):
        add("binding:file_ref", "file reference must be an object", path)
        return None, None
    resolved = _safe_package_path(root, ref.get("path"))
    if resolved is None:
        add("package:path_scope", "file path is absent or escapes the package root", f"{path}.path")
        return None, None
    if not resolved.is_file():
        add("identity:component_missing", f"bound file does not exist: {resolved}", f"{path}.path")
        return None, resolved
    actual_file_hash = file_sha256(resolved)
    if actual_file_hash != ref.get("file_sha256"):
        add("identity:file_hash", "bound file SHA-256 does not match manifest", f"{path}.file_sha256")
    try:
        value = read_json(resolved)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        add("package:json_read", f"could not read bound JSON: {exc}", f"{path}.path")
        return None, resolved
    if not isinstance(value, dict):
        add("package:json_type", "bound JSON must be an object", f"{path}.path")
        return None, resolved
    return value, resolved


def _validate_schema(
    value: dict[str, Any],
    schema_name: str,
    instance_path: str,
    issues: list[dict[str, str]],
) -> None:
    try:
        issues.extend(validate_document(value, schema_name, instance_path))
    except SchemaRuntimeError as exc:
        issues.append({
            "layer": "schema", "path": instance_path, "code": "schema:runtime",
            "message": str(exc), "review_route": "deterministic", "severity": "blocker",
        })


def _load_external_trust_root(
    package_root: Path,
    trust_root_path: Path | None,
    expected_trust_root_sha256: str | None,
    issues: list[dict[str, str]],
) -> dict[str, dict[str, str]]:
    """Load caller-pinned collection identities from outside the design package.

    The file supplies structured collection identities, while its expected SHA-256
    must arrive through the validator call/CLI rather than any package artifact.
    """
    def add(code: str, message: str, path: str = "$.external_trust_root") -> None:
        issues.append({
            "layer": "deterministic", "path": path, "code": code,
            "message": message, "review_route": "deterministic", "severity": "error",
        })

    if trust_root_path is None or expected_trust_root_sha256 is None:
        add(
            "trust:external_root_required",
            "an external trust-root file and caller-held expected SHA-256 are required",
        )
        return {}
    if len(expected_trust_root_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in expected_trust_root_sha256
    ):
        add("trust:external_root_hash_format", "expected trust-root SHA-256 must be 64 lowercase hex characters")

    resolved = Path(trust_root_path).resolve()
    try:
        resolved.relative_to(package_root.resolve())
    except ValueError:
        pass
    else:
        add("trust:external_root_scope", "trust-root file must be outside the model-produced package")
    if not resolved.is_file():
        add("trust:external_root_missing", f"external trust-root file does not exist: {resolved}")
        return {}
    if file_sha256(resolved) != expected_trust_root_sha256:
        add("trust:external_root_hash", "external trust-root file differs from the caller-held expected SHA-256")
    try:
        value = read_json(resolved)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        add("trust:external_root_read", f"could not read external trust root: {exc}")
        return {}
    if not isinstance(value, dict):
        add("trust:external_root_type", "external trust root must be a JSON object")
        return {}
    _validate_schema(value, SCHEMAS["trusted_inputs_root"], "$.external_trust_root", issues)
    collections = value.get("collections")
    if not isinstance(collections, dict):
        return {}
    return {
        name: reference
        for name, reference in collections.items()
        if name in TRUST_INTERFACES and isinstance(reference, dict)
    }


def _validate_external_collection_identities(
    trust: dict[str, dict[str, Any]],
    expected: dict[str, dict[str, str]],
    issues: list[dict[str, str]],
) -> None:
    """Bind package-loaded collections to independently supplied identities."""
    for name in TRUST_INTERFACES:
        actual = trust.get(name)
        reference = expected.get(name)
        if actual is None or reference is None:
            issues.append({
                "layer": "deterministic",
                "path": f"$.external_trust_root.collections.{name}",
                "code": "trust:external_collection_identity",
                "message": f"external trusted identity is missing or unresolved for {name}",
                "review_route": "deterministic",
                "severity": "error",
            })
            continue
        mismatched = [
            key for key in ("collection_id", "collection_version", "collection_sha256")
            if actual.get(key) != reference.get(key)
        ]
        if mismatched:
            issues.append({
                "layer": "deterministic",
                "path": f"$.external_trust_root.collections.{name}",
                "code": "trust:external_collection_identity",
                "message": f"{name} differs from the caller-pinned identity: {', '.join(mismatched)}",
                "review_route": "deterministic",
                "severity": "error",
            })


def _schema_issue_severity(issues: list[dict[str, str]]) -> None:
    for issue in issues:
        issue.setdefault("severity", "error")
        issue.setdefault("review_route", "deterministic")


def _inspect_tabular_or_json(path: Path, format_name: str) -> tuple[str, set[str], str | None]:
    """Inspect only deterministic top-level field identities for supported formats."""
    try:
        if format_name in {"csv", "tsv"}:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle, delimiter="," if format_name == "csv" else "\t")
                row = next(reader, None)
            if row is None:
                return "failed", set(), "tabular source has no header row"
            return "inspected", {str(item) for item in row}, None
        if format_name == "json":
            value = read_json(path)
            if isinstance(value, dict):
                return "inspected", set(value), None
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return "inspected", set(value[0]), None
            return "failed", set(), "JSON source has no object fields to inspect"
    except (OSError, UnicodeError, json.JSONDecodeError, csv.Error) as exc:
        return "failed", set(), str(exc)
    return "not_performed", set(), None


def _component_refs(manifest: dict[str, Any]) -> list[tuple[str, dict[str, Any], str]]:
    components = manifest.get("components", {})
    if not isinstance(components, dict):
        return []
    result: list[tuple[str, dict[str, Any], str]] = []
    single = components.get("source_data_manifest")
    if isinstance(single, dict):
        result.append(("source_data_manifest", single, "$.manifest.components.source_data_manifest"))
    for key, kind in (
        ("figure_cards", "figure_card"),
        ("figure_contracts", "figure_contract"),
        ("plot_recipes", "plot_recipe"),
    ):
        values = components.get(key, [])
        if isinstance(values, list):
            for index, ref in enumerate(values):
                if isinstance(ref, dict):
                    result.append((kind, ref, f"$.manifest.components.{key}[{index}]"))
    return result


def _load_package_documents(
    root: Path,
    manifest: dict[str, Any],
    issues: list[dict[str, str]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    def add(code: str, message: str, path: str = "$") -> None:
        issues.append({
            "layer": "deterministic", "path": path, "code": code,
            "message": message, "review_route": "deterministic", "severity": "error",
        })

    documents: dict[str, list[dict[str, Any]]] = {
        "source_data_manifest": [], "figure_card": [], "figure_contract": [], "plot_recipe": []
    }
    for kind, ref, ref_path in _component_refs(manifest):
        if ref.get("artifact_type") != kind:
            add("binding:component_type", f"expected artifact_type {kind}", f"{ref_path}.artifact_type")
        value, _ = _load_bound_json(root, ref, ref_path, add)
        if value is None:
            continue
        _validate_schema(value, SCHEMAS[kind], ref_path.replace("$.manifest.components", "$.components"), issues)
        if value.get("artifact_sha256") != payload_sha256(value, "artifact_sha256"):
            add("identity:artifact_hash", f"invalid self hash for {kind}", f"{ref_path}.artifact_sha256")
        expected = {
            "artifact_type": kind,
            "artifact_id": value.get("artifact_id"),
            "artifact_version": value.get("schema_version"),
            "artifact_sha256": value.get("artifact_sha256"),
        }
        if any(ref.get(key) != item for key, item in expected.items()):
            add("binding:component_identity", f"manifest identity does not match {kind}", ref_path)
        if value.get("document_type") != manifest.get("document_type"):
            add("binding:document_type", f"{kind} document_type differs from manifest", ref_path)
        if value.get("maturity") != manifest.get("maturity"):
            add("maturity:component_mismatch", f"{kind} maturity differs from manifest", ref_path)
        documents[kind].append(value)

    trust: dict[str, dict[str, Any]] = {}
    bindings = manifest.get("trust_bindings", {})
    if isinstance(bindings, dict):
        for name, ref in bindings.items():
            ref_path = f"$.manifest.trust_bindings.{name}"
            value, _ = _load_bound_json(root, ref, ref_path, add)
            if value is None:
                continue
            schema_name = SCHEMAS.get(name)
            if schema_name is None:
                add("binding:trust_type", f"unknown trust interface: {name}", ref_path)
                continue
            _validate_schema(value, schema_name, f"$.trust.{name}", issues)
            recomputed = payload_sha256(value, "collection_sha256")
            if value.get("collection_sha256") != recomputed:
                add("trust:collection_hash", f"invalid collection hash for {name}", ref_path)
            for key in ("interface_name", "collection_id", "collection_version", "collection_sha256"):
                if ref.get(key) != value.get(key):
                    add("trust:collection_binding", f"{name} {key} differs from manifest binding", ref_path)
            trust[name] = value
    return documents, trust


def _build_subject_index(
    cards: list[dict[str, Any]],
    contracts: list[dict[str, Any]],
    analyses: list[dict[str, Any]],
) -> dict[tuple[str, str], tuple[str, Any]]:
    subjects: dict[tuple[str, str], tuple[str, Any]] = {}
    for card in cards:
        version = card.get("schema_version", "")
        subjects[("figure_card", card.get("artifact_id"))] = (version, card)
        representative = card.get("representative_image")
        if isinstance(representative, dict):
            subjects[("representative_image", representative.get("representative_image_id"))] = (
                version, representative
            )
    for contract in contracts:
        version = contract.get("schema_version", "")
        subjects[("figure_contract", contract.get("artifact_id"))] = (version, contract)
        for omission in contract.get("omitted_evidence", []):
            subjects[("evidence_omission", omission.get("omission_id"))] = (version, omission)
        for layout in contract.get("layout_decisions", []):
            subjects[("layout", layout.get("layout_id"))] = (version, layout)
        finality_subject = {
            "figure_contract_id": contract.get("artifact_id"),
            "finality_state": contract.get("finality_state"),
        }
        subjects[("finality", contract.get("artifact_id"))] = (version, finality_subject)
    for analysis in analyses:
        subjects[("analysis_output", analysis.get("analysis_output_id"))] = (
            analysis.get("record_version", ""), analysis
        )
    return {key: value for key, value in subjects.items() if isinstance(key[1], str)}


def _validate_authority(
    authority: dict[str, Any],
    subjects: dict[tuple[str, str], tuple[str, Any]],
    input_identities: dict[str, tuple[str, str]],
    issues: list[dict[str, str]],
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    def add(code: str, message: str, path: str = "$") -> None:
        issues.append({
            "layer": "deterministic", "path": path, "code": code,
            "message": message, "review_route": "deterministic", "severity": "error",
        })

    records = authority.get("records", []) if isinstance(authority, dict) else []
    decisions = _index(records, "decision_id", "$.trust.trusted_authority_inputs.records", add)
    trusted: set[str] = set()
    for decision_id, record in decisions.items():
        path = f"$.trust.trusted_authority_inputs.records[{decision_id}]"
        if record.get("decision_sha256") != payload_sha256(record, "decision_sha256"):
            add("authority:decision_hash", f"invalid decision hash: {decision_id}", path)
            continue
        origin = record.get("authorization_origin")
        state = record.get("authorization_state")
        role = record.get("decision_producer_role")
        decision_type = record.get("decision_type")
        if role == "author":
            if origin != "author" or state != "author_approved":
                add("authority:author_state", "author role requires author/author_approved", path)
                continue
        elif origin != "calling_workflow" or state != "caller_accepted":
            add("authority:workflow_state", "workflow role requires calling_workflow/caller_accepted", path)
            continue
        if decision_type in AUTHOR_ONLY_DECISIONS and role != "author":
            add("authority:role_policy", f"{decision_type} requires author authority", path)
            continue
        if decision_type == "analysis_output_review" and role not in {"author", "authorized_analysis_workflow"}:
            add("authority:role_policy", "analysis_output_review requires author or authorized analysis workflow", path)
            continue
        failed = False
        expected_subject_type = DECISION_SUBJECTS.get(decision_type)
        for subject in record.get("subject_refs", []):
            subject_type = subject.get("subject_type")
            subject_id = subject.get("subject_id")
            if expected_subject_type != subject_type:
                add("authority:decision_type", f"{decision_type} cannot govern {subject_type}", path)
                failed = True
                continue
            governed = subjects.get((subject_type, subject_id))
            if governed is None:
                add("authority:subject", f"decision subject does not resolve: {subject_type}/{subject_id}", path)
                failed = True
                continue
            version, value = governed
            if subject.get("subject_version") != version:
                add("authority:subject_version", f"decision subject version mismatch: {subject_id}", path)
                failed = True
            if subject.get("governed_content_sha256") != governed_content_sha256(value):
                add("authority:subject_hash", f"decision governed-content hash mismatch: {subject_id}", path)
                failed = True
        for binding in record.get("upstream_input_bindings", []):
            expected = input_identities.get(binding.get("input_id"))
            if expected is None or expected != (binding.get("input_version"), binding.get("input_sha256")):
                add("authority:input_binding", f"authority input binding mismatch: {binding.get('input_id')}", path)
                failed = True
        if not failed:
            trusted.add(decision_id)
    return decisions, trusted


def _require_decision(
    ref: Any,
    expected_type: str,
    subject_type: str,
    subject_id: str,
    decisions: dict[str, dict[str, Any]],
    trusted: set[str],
    issues: list[dict[str, str]],
    path: str,
    *,
    expected_state: str,
    allowed_decision_values: set[str],
) -> bool:
    def add(code: str, message: str) -> None:
        issues.append({
            "layer": "deterministic", "path": path, "code": code,
            "message": message, "review_route": "deterministic", "severity": "error",
        })

    if not isinstance(ref, dict):
        add("authority:missing_ref", f"missing {expected_type} decision_ref")
        return False
    decision = decisions.get(ref.get("decision_id"))
    if decision is None:
        add("authority:missing_decision", f"decision does not resolve: {ref.get('decision_id')}")
        return False
    if ref != decision_ref(decision):
        add("authority:ref_hash", "decision_ref identity/hash mismatch")
        return False
    if decision.get("decision_id") not in trusted:
        add("authority:untrusted_decision", "decision did not pass external trust checks")
        return False
    if decision.get("decision_type") != expected_type:
        add("authority:decision_type", f"expected {expected_type}, got {decision.get('decision_type')}")
        return False
    if decision.get("decision_value") not in allowed_decision_values:
        add(
            "authority:decision_value",
            f"{expected_type} decision value {decision.get('decision_value')} cannot satisfy {expected_state}",
        )
        return False
    matching_subjects = [
        item for item in decision.get("subject_refs", [])
        if item.get("subject_type") == subject_type and item.get("subject_id") == subject_id
    ]
    if not matching_subjects:
        add("authority:subject", f"decision does not govern {subject_type}/{subject_id}")
        return False
    if any(item.get("asserted_state") != expected_state for item in matching_subjects):
        add(
            "authority:asserted_state",
            f"decision subject state does not match required state {expected_state}",
        )
        return False
    return True


def _validate_source_inputs(
    root: Path,
    manifest: dict[str, Any],
    source_manifest: dict[str, Any],
    trusted_collection: dict[str, Any],
    cards: list[dict[str, Any]],
    issues: list[dict[str, str]],
) -> tuple[dict[str, dict[str, Any]], dict[str, tuple[str, str]]]:
    def add(code: str, message: str, path: str = "$") -> None:
        issues.append({
            "layer": "deterministic", "path": path, "code": code,
            "message": message, "review_route": "deterministic", "severity": "error",
        })

    sources = _index(source_manifest.get("source_records", []), "source_data_id", "$.source_data_manifest.source_records", add)
    trusted_records = _index(trusted_collection.get("records", []), "trusted_input_id", "$.trust.trusted_source_inputs.records", add)
    trusted_by_source: dict[str, dict[str, Any]] = {}
    for trusted_id, record in trusted_records.items():
        source_id = record.get("source_data_id")
        if source_id in trusted_by_source:
            add("trust:duplicate_source_binding", f"multiple trusted inputs bind source_data_id {source_id}")
        else:
            trusted_by_source[source_id] = record

    used_source_ids = {source_id for card in cards if card.get("data_bearing") for source_id in card.get("source_data_ids", [])}
    inspections: dict[str, dict[str, Any]] = {}
    input_identities: dict[str, tuple[str, str]] = {}
    maturity = manifest.get("maturity")

    for source_id, source in sources.items():
        path = f"$.source_data_manifest.source_records[{source_id}]"
        if any(key in source for key in ("verification_status", "content_inspected", "hash_verified")):
            add("trust:self_certification", "source manifest cannot self-certify verification", path)
        units = source.get("units", {})
        replicates = source.get("replicates", {})
        if replicates.get("n_unit") != units.get("inference_unit"):
            add("units:n_inference_mismatch", "n_unit must match the declared inference_unit", f"{path}.replicates.n_unit")
        if (
            replicates.get("n_unit") == replicates.get("technical_replicate_unit")
            and replicates.get("n_unit") != replicates.get("biological_replicate_unit")
        ):
            add("units:technical_as_n", "technical replicate unit is counted as independent n", f"{path}.replicates.n_unit")
        if maturity == "ready_for_prototype":
            unresolved = {"", "unresolved", "not_assessed", "missing"}
            if any(str(units.get(key, "")).lower() in unresolved for key in ("observation_unit", "experimental_unit", "inference_unit")):
                add("maturity:unit_unresolved", "ready_for_prototype requires resolved units", f"{path}.units")
            if source.get("availability") != "available":
                add("maturity:source_required", "ready_for_prototype requires available source data", path)

        trusted = trusted_by_source.get(source_id)
        claimed_id = source.get("trusted_input_id")
        if trusted is None or claimed_id != trusted.get("trusted_input_id"):
            if source_id in used_source_ids or maturity == "ready_for_prototype":
                add("trust:source_binding", f"source_data_id lacks exact trusted input binding: {source_id}", path)
            inspections[source_id] = {
                "existence_verification": "not_performed",
                "hash_verification": "not_performed",
                "content_inspection": "not_performed",
                "headers": set(),
            }
            continue
        actual_path = _resolve_trusted_path(root, trusted)
        if actual_path is None:
            inspections[source_id] = {
                "existence_verification": "not_performed",
                "hash_verification": "not_performed",
                "content_inspection": "not_performed",
                "headers": set(),
            }
            if maturity == "ready_for_prototype":
                add("trust:source_unresolved", f"trusted input is not directly inspectable: {claimed_id}", path)
            continue
        if not actual_path.is_file():
            add("trust:source_missing", f"trusted source file does not exist: {actual_path}", path)
            inspections[source_id] = {
                "existence_verification": "failed", "hash_verification": "not_performed",
                "content_inspection": "not_performed", "headers": set(),
            }
            continue
        actual_size = actual_path.stat().st_size
        actual_hash = file_sha256(actual_path)
        size_ok = actual_size == trusted.get("expected_size")
        hash_ok = actual_hash == trusted.get("expected_sha256")
        if not size_ok:
            add("trust:source_size", f"trusted source size mismatch: {claimed_id}", path)
        if not hash_ok:
            add("trust:source_hash", f"trusted source hash mismatch: {claimed_id}", path)
        file_identity = source.get("file_identity")
        if not isinstance(file_identity, dict):
            add("trust:manifest_file_identity", "available source lacks file_identity", path)
        else:
            if file_identity.get("size") != actual_size or file_identity.get("sha256") != actual_hash:
                add("trust:manifest_file_identity", "source manifest identity differs from actual trusted file", path)
            if file_identity.get("format") != trusted.get("format"):
                add("trust:source_format", "source manifest format differs from trusted input", path)
        content_state, headers, inspection_error = _inspect_tabular_or_json(actual_path, trusted.get("format"))
        if inspection_error is not None:
            add("trust:content_inspection", f"content inspection failed: {inspection_error}", path)
        expected_fields = {
            item.get("value") for item in trusted.get("expected_locators", [])
            if item.get("locator_type") in {"header", "variable"}
        }
        if content_state == "inspected" and not expected_fields.issubset(headers):
            add("trust:locator_missing", "trusted source lacks an expected header/variable", path)
        if content_state == "not_performed" and source.get("declared_inspection_state") == "content_expected" and maturity == "ready_for_prototype":
            add("trust:content_not_performed", "required content inspection was not performed", path)
        inspections[source_id] = {
            "existence_verification": "verified",
            "hash_verification": "verified" if hash_ok else "failed",
            "content_inspection": content_state,
            "headers": headers,
            "actual_hash": actual_hash,
        }
        input_identities[claimed_id] = ("0.1.0", actual_hash)

    for source_id in used_source_ids - set(sources):
        add("binding:source_data", f"card references unknown source_data_id: {source_id}")
    return inspections, input_identities


def _validate_analysis_outputs(
    analyses: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    inspections: dict[str, dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    trusted_decisions: set[str],
    issues: list[dict[str, str]],
) -> None:
    def add(code: str, message: str, path: str = "$") -> None:
        issues.append({
            "layer": "deterministic", "path": path, "code": code,
            "message": message, "review_route": "deterministic", "severity": "error",
        })

    numerical_fields = {
        "estimate", "p_value", "adjusted_p_value", "effect_size", "interval",
        "test_name", "model_specification"
    }
    for analysis_id, record in analyses.items():
        path = f"$.trust.trusted_analysis_outputs.records[{analysis_id}]"
        if record.get("record_sha256") != payload_sha256(record, "record_sha256"):
            add("analysis:record_hash", f"analysis-output hash is invalid: {analysis_id}", path)
        if record.get("analysis_origin") == "model_proposed":
            if record.get("result_status") != "required_but_unavailable" or any(record.get(key) is not None for key in numerical_fields):
                add("analysis:model_result", "model_proposed analysis cannot supply a completed result", path)
        interval = record.get("interval")
        if isinstance(interval, dict) and interval.get("level", 0) <= 0:
            add("analysis:interval_level", "analysis interval level must be greater than zero", f"{path}.interval.level")
        for ref in record.get("source_data_refs", []):
            source_id = ref.get("source_data_id")
            source = sources.get(source_id)
            if source is None:
                add("analysis:source_ref", f"analysis source_data_id does not resolve: {source_id}", path)
                continue
            expected_hash = canonical_sha256(source)
            if ref.get("source_data_version") != source.get("record_version") or ref.get("source_data_sha256") != expected_hash:
                add("analysis:source_binding", f"analysis source-data version/hash mismatch: {source_id}", path)
            if ref.get("trusted_input_id") != source.get("trusted_input_id"):
                add("analysis:trusted_input_binding", f"analysis trusted-input binding mismatch: {source_id}", path)
            if record.get("unit_context") != source.get("units"):
                add("analysis:unit_binding", f"analysis unit context differs from source manifest: {source_id}", path)
            source_replicates = source.get("replicates", {})
            if record.get("n_by_group") != source_replicates.get("n_by_group"):
                add("analysis:n_binding", f"analysis n_by_group differs from source manifest: {source_id}", path)
            if record.get("n_definition") != source_replicates.get("n_definition") or record.get("n_unit") != source_replicates.get("n_unit"):
                add("analysis:n_definition", f"analysis n semantics differ from source manifest: {source_id}", path)
            source_design = source.get("design_context", {})
            for flag in ("paired", "repeated", "nested", "clustered"):
                if record.get(flag) != source_design.get(flag):
                    add("analysis:design_flag", f"analysis {flag} state differs from source manifest", path)
        actual_hashes = {
            inspection.get("actual_hash") for inspection in inspections.values()
            if isinstance(inspection.get("actual_hash"), str)
        }
        if not set(record.get("input_data_hashes", [])).issubset(actual_hashes):
            add("analysis:input_hash", "analysis input_data_hashes do not resolve to inspected trusted inputs", path)
        units = record.get("unit_context", {})
        if record.get("n_unit") != units.get("inference_unit"):
            add("analysis:n_inference_mismatch", "analysis n_unit differs from inference_unit", path)
        if record.get("review_status") == "approved" or record.get("authorization_state") in {"caller_accepted", "author_approved"}:
            _require_decision(
                record.get("decision_ref"), "analysis_output_review", "analysis_output", analysis_id,
                decisions, trusted_decisions, issues, f"{path}.decision_ref",
                expected_state="approved",
                allowed_decision_values={"approve", "confirm", "resolve"},
            )


def _validate_upstream_and_structure(
    manifest: dict[str, Any],
    cards: list[dict[str, Any]],
    contracts: list[dict[str, Any]],
    recipes: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    analyses: dict[str, dict[str, Any]],
    inspections: dict[str, dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    trusted_decisions: set[str],
    issues: list[dict[str, str]],
) -> None:
    def add(code: str, message: str, path: str = "$") -> None:
        issues.append({
            "layer": "deterministic", "path": path, "code": code,
            "message": message, "review_route": "deterministic", "severity": "error",
        })

    upstream = manifest.get("upstream_context", {})
    upstream_ref = upstream.get("artifact_ref")
    claim_records = _index(upstream.get("claims", []), "claim_id", "$.manifest.upstream_context.claims", add)
    evidence_records = _index(upstream.get("evidence", []), "evidence_id", "$.manifest.upstream_context.evidence", add)
    relations = {
        (item.get("claim_id"), item.get("evidence_id"), item.get("relation_type"))
        for item in upstream.get("claim_evidence_relations", []) if isinstance(item, dict)
    }
    cards_by_panel = _index(cards, "panel_id", "$.figure_cards", add)
    contracts_by_figure = _index(contracts, "figure_id", "$.figure_contracts", add)
    recipes_by_panel = _index(recipes, "panel_id", "$.plot_recipes", add)

    for claim_id, claim in claim_records.items():
        if claim.get("claim_origin") == "source_claim" and len(set(claim.get("source_ids", []))) != 1:
            add("upstream:source_claim_provenance", f"source_claim must bind exactly one source: {claim_id}")
        if claim.get("claim_origin") == "cross_source_synthesis" and len(set(claim.get("source_ids", []))) < 2:
            add("upstream:cross_source_cardinality", f"cross_source_synthesis requires at least two sources: {claim_id}")

    for card in cards:
        panel_id = card.get("panel_id")
        path = f"$.figure_cards[{panel_id}]"
        if card.get("upstream_ref") != upstream_ref:
            add("binding:upstream_ref", "Figure Card upstream_ref differs from manifest", f"{path}.upstream_ref")
        for claim_id in card.get("claim_ids", []):
            if claim_id not in claim_records:
                add("upstream:claim", f"Figure Card claim does not resolve: {claim_id}", path)
        for binding in card.get("evidence_bindings", []):
            triple = (binding.get("claim_id"), binding.get("evidence_id"), binding.get("relation_type"))
            if triple not in relations:
                add("upstream:relation_map", f"evidence binding does not resolve through upstream relation map: {triple}", path)
            if binding.get("evidence_id") not in evidence_records:
                add("upstream:evidence", f"Figure Card evidence does not resolve: {binding.get('evidence_id')}", path)
        if card.get("evidence_role") == "decorative" and card.get("data_bearing"):
            add("figure:decorative_evidence", "decorative evidence_role cannot be data/evidence-bearing", path)
        if card.get("panel_kind") == "conceptual_schematic" and card.get("data_bearing"):
            add("figure:schematic_as_data", "conceptual_schematic cannot be measured primary data", path)
        for reference in card.get("reference_abstractions", []):
            if reference.get("asset_embedded"):
                add("copyright:embedded_asset", "published reference asset cannot be embedded", path)
            if reference.get("usage_purpose") != "functional_abstraction":
                add("copyright:prohibited_reuse", "reference use must be functional_abstraction", path)
            if reference.get("layout_origin") == "copied_reference":
                add("copyright:copied_declared", "explicit copied_reference layout is prohibited", path)
        representative = card.get("representative_image")
        if isinstance(representative, dict):
            if representative.get("quantified_source_data_id") is None and card.get("data_bearing"):
                add("image:quantified_link", "representative image lacks quantified source-data link", path)
            if representative.get("selection_status") == "approved":
                _require_decision(
                    representative.get("decision_ref"), "representative_image_selection",
                    "representative_image", representative.get("representative_image_id"),
                    decisions, trusted_decisions, issues, f"{path}.representative_image.decision_ref",
                    expected_state="approved",
                    allowed_decision_values={"approve"},
                )

    document_type = manifest.get("document_type")
    sequence_by_id = {item.get("figure_id"): item for item in upstream.get("figure_sequence", [])}
    briefs_by_id = {item.get("brief_id"): item for item in upstream.get("review_figure_briefs", [])}
    for contract in contracts:
        figure_id = contract.get("figure_id")
        path = f"$.figure_contracts[{figure_id}]"
        if contract.get("upstream_ref") != upstream_ref:
            add("binding:upstream_ref", "Figure Contract upstream_ref differs from manifest", f"{path}.upstream_ref")
        if document_type == "original_article":
            sequence = sequence_by_id.get(contract.get("upstream_figure_or_brief_id"))
            if sequence is None or contract.get("upstream_figure_or_brief_id") != figure_id:
                add("routing:figure_sequence", "Original Article Figure Contract does not resolve to its Figure sequence item", path)
            else:
                if not set(contract.get("claim_ids", [])).issubset(set(sequence.get("claim_ids", []))):
                    add("upstream:sequence_claims", "Figure Contract claims exceed bound Figure sequence", path)
                if not set(contract.get("evidence_ids", [])).issubset(set(sequence.get("evidence_ids", []))):
                    add("upstream:sequence_evidence", "Figure Contract evidence exceeds bound Figure sequence", path)
        elif document_type == "review_article":
            brief = briefs_by_id.get(contract.get("upstream_figure_or_brief_id"))
            if brief is None:
                add("routing:review_brief", "Review Figure Contract does not resolve to a brief", path)
            elif brief.get("output_type") != "figure":
                add("routing:table_brief", "table-only brief cannot be converted to a Figure", path)

        ordered = contract.get("ordered_panel_ids", [])
        figure_cards = [card for card in cards if card.get("figure_id") == figure_id]
        if set(ordered) != _ids(figure_cards, "panel_id"):
            add("figure:panel_coverage", "ordered_panel_ids must exactly cover Figure Cards", path)
        if set(ordered) != {recipe.get("panel_id") for recipe in recipes if recipe.get("figure_id") == figure_id}:
            add("figure:recipe_coverage", "Plot Recipes must exactly cover Figure panels", path)
        role_panels = {item.get("panel_id") for item in contract.get("panel_roles", [])}
        if role_panels != set(ordered):
            add("figure:panel_roles", "panel_roles must exactly cover ordered panels", path)
        card_claims = {item for card in figure_cards for item in card.get("claim_ids", [])}
        card_evidence = {binding.get("evidence_id") for card in figure_cards for binding in card.get("evidence_bindings", [])}
        card_sources = {item for card in figure_cards for item in card.get("source_data_ids", [])}
        if set(contract.get("claim_ids", [])) != card_claims:
            add("figure:claim_coverage", "Figure Contract claim inventory differs from cards", path)
        if set(contract.get("evidence_ids", [])) != card_evidence:
            add("figure:evidence_coverage", "Figure Contract evidence inventory differs from cards", path)
        expected_units = {
            evidence_records[evidence_id].get("evidence_unit_id")
            for evidence_id in contract.get("evidence_ids", []) if evidence_id in evidence_records
        }
        if set(contract.get("evidence_unit_ids", [])) != expected_units:
            add("independence:evidence_unit_binding", "Figure Contract evidence-unit inventory differs from upstream evidence identities", path)
        if contract.get("independent_evidence_unit_count") != len(expected_units):
            add("independence:linked_double_count", "independent evidence-unit count must equal unique supplied evidence units", path)
        if set(contract.get("source_data_ids", [])) != card_sources:
            add("figure:source_coverage", "Figure Contract source inventory differs from cards", path)

        for claim_id in contract.get("claim_ids", []):
            upstream_ceiling = claim_records.get(claim_id, {}).get("structured_ceiling", {})
            target_ceiling = contract.get("conclusion", {}).get("structured_ceiling", {})
            for dimension, ranks in CEILING_RANKS.items():
                if ranks.get(target_ceiling.get(dimension), -1) > ranks.get(upstream_ceiling.get(dimension), -1):
                    add("claim:structured_ceiling", f"Figure conclusion exceeds upstream {dimension} ceiling", path)

        omissions = {item.get("evidence_id"): item for item in contract.get("omitted_evidence", [])}
        represented = set(contract.get("required_visibility_ids", []))
        for required_id in upstream.get("required_visibility_ids", []):
            if required_id in represented:
                continue
            omission = omissions.get(required_id)
            if omission is None:
                add("figure:required_visibility", f"required upstream item is neither shown nor authorized omitted: {required_id}", path)
            else:
                _require_decision(
                    omission.get("decision_ref"), "material_evidence_omission", "evidence_omission",
                    omission.get("omission_id"), decisions, trusted_decisions, issues,
                    f"{path}.omitted_evidence[{omission.get('omission_id')}].decision_ref",
                    expected_state="approved",
                    allowed_decision_values={"approve"},
                )
        if contract.get("finality_state") in {"submission_candidate", "author_approved_final"}:
            add("finality:phase8a_state", "Phase 8A cannot emit submission/final states", path)

        palette: dict[str, str] = {}
        for item in contract.get("palette_semantics", []):
            key = item.get("semantic_key")
            value = item.get("value")
            if key in palette and palette[key] != value:
                add("palette:semantic_conflict", f"semantic key has conflicting values: {key}", path)
            palette[key] = value

    for recipe in recipes:
        panel_id = recipe.get("panel_id")
        path = f"$.plot_recipes[{panel_id}]"
        card = cards_by_panel.get(panel_id)
        if card is None:
            add("figure:orphan_recipe", f"recipe panel does not resolve: {panel_id}", path)
            continue
        if recipe.get("figure_id") != card.get("figure_id"):
            add("figure:recipe_figure", "recipe and card figure_id differ", path)
        if set(recipe.get("source_data_ids", [])) != set(card.get("source_data_ids", [])):
            add("figure:recipe_sources", "recipe source IDs differ from Figure Card", path)
        source_variables = {
            source_id: _ids(sources.get(source_id, {}).get("variables", []), "variable_id")
            for source_id in recipe.get("source_data_ids", [])
        }
        for mapping in recipe.get("variable_mappings", []):
            source_id = mapping.get("source_data_id")
            variable_id = mapping.get("variable_id")
            if variable_id not in source_variables.get(source_id, set()):
                add("recipe:variable_mapping", f"mapped variable does not exist: {source_id}/{variable_id}", path)
            inspection = inspections.get(source_id, {})
            if manifest.get("maturity") == "ready_for_prototype":
                if inspection.get("content_inspection") != "inspected" or variable_id not in inspection.get("headers", set()):
                    add("maturity:variable_unverified", f"ready_for_prototype variable was not inspected: {variable_id}", path)
        valid_transformations = {
            item.get("transformation_id")
            for source_id in recipe.get("source_data_ids", [])
            for item in sources.get(source_id, {}).get("transformations", [])
        }
        if not set(recipe.get("transformation_ids", [])).issubset(valid_transformations):
            add("recipe:transformation_binding", "recipe transformation IDs do not resolve to source manifest", path)
        if recipe.get("implementation_status") != "not_executed":
            add("phase8a:execution_claim", "Phase 8A recipe cannot claim plotting execution", path)
        for annotation in recipe.get("statistical_annotations", []):
            status = annotation.get("status")
            ref = annotation.get("analysis_output_ref")
            if status == "supplied":
                analysis = analyses.get(ref.get("analysis_output_id")) if isinstance(ref, dict) else None
                if analysis is None or ref != analysis_output_ref(analysis):
                    add("analysis:annotation_binding", "supplied annotation lacks an exact analysis-output binding", path)
                elif analysis.get("result_status") != "supplied":
                    add("analysis:annotation_status", "annotation binds an unavailable analysis output", path)
                elif annotation.get("comparison_id") not in analysis.get("comparison_ids", []):
                    add("analysis:comparison_binding", "annotation comparison_id is absent from analysis output", path)
            elif status == "required_but_unavailable" and (ref is not None or annotation.get("symbol") is not None):
                add("analysis:unavailable_filled", "unavailable annotation cannot carry a result ref or symbol", path)
        if set(recipe.get("palette_keys", [])) - {
            item.get("semantic_key") for contract in contracts if contract.get("figure_id") == recipe.get("figure_id")
            for item in contract.get("palette_semantics", [])
        }:
            add("palette:unknown_key", "recipe palette key is absent from Figure Contract", path)

    for card in cards:
        path = f"$.figure_cards[{card.get('panel_id')}]"
        source_records = [sources.get(source_id) for source_id in card.get("source_data_ids", [])]
        for source in [item for item in source_records if isinstance(item, dict)]:
            if card.get("units") != source.get("units"):
                add("units:card_source", "Figure Card units differ from source manifest", path)
            if card.get("replicates") != source.get("replicates"):
                add("units:replicate_binding", "Figure Card replicate/n context differs from source manifest", path)
            source_design = source.get("design_context", {})
            card_design = card.get("design_context", {})
            for flag in ("paired", "repeated", "nested", "clustered"):
                if source_design.get(flag) != card_design.get(flag):
                    add("units:design_flag", f"Figure Card drops source {flag} state", path)
            for processing in source.get("processing_history", []):
                if processing.get("operation") in PROHIBITED_IMAGE_OPERATIONS and processing.get("declared_acceptable"):
                    add("image:prohibited_processing", f"prohibited processing marked acceptable: {processing.get('operation')}", path)
        for annotation in card.get("statistical_annotations", []):
            status = annotation.get("status")
            ref = annotation.get("analysis_output_ref")
            if status == "supplied":
                analysis = analyses.get(ref.get("analysis_output_id")) if isinstance(ref, dict) else None
                if analysis is None or ref != analysis_output_ref(analysis):
                    add("analysis:card_annotation_binding", "Figure Card annotation lacks exact analysis-output binding", path)
            elif status == "required_but_unavailable" and (ref is not None or annotation.get("symbol") is not None):
                add("analysis:unavailable_filled", "unavailable card annotation cannot carry result content", path)

    # Exact repeated source-region reuse is detectable; overlap/similarity is not.
    region_uses: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for card in cards:
        for locator in card.get("data_locators", []):
            if locator.get("locator_type") in {"image", "region"}:
                key = (locator.get("source_data_id"), locator.get("locator_type"), locator.get("value"))
                region_uses.setdefault(key, []).append(card)
    for key, used_cards in region_uses.items():
        reuse_groups = {card.get("reuse_group_id") for card in used_cards}
        if len(used_cards) > 1 and (len(reuse_groups) != 1 or None in reuse_groups):
            add("image:reuse_relationship", f"identical source region reused without one non-null reuse_group_id: {key}")


def _domain_status(issues: list[dict[str, str]], cards: list[dict[str, Any]]) -> dict[str, str]:
    mapping = {
        "schema": {"schema"},
        "identity": {"identity", "binding", "package"},
        "trust": {"trust"},
        "authority": {"authority"},
        "data": {"source", "recipe", "upstream"},
        "units_statistics": {"units", "analysis", "claim"},
        "figure_structure": {"figure", "routing", "maturity", "finality", "phase8a"},
        "image_integrity": {"image"},
        "copyright": {"copyright"},
        "visual_semantics": {"palette"},
        "journal_backend": {"journal", "backend", "profile"},
    }
    prefixes = {issue.get("code", "").split(":", 1)[0] for issue in issues}
    result = {
        domain: "fail" if prefixes & codes else "pass"
        for domain, codes in mapping.items()
    }
    result["copyright"] = "fail" if "copyright" in prefixes else "not_assessed"
    if any(card.get("panel_kind") in {"image_or_micrograph", "gel_or_blot", "spatial_or_map"} for card in cards):
        result["image_integrity"] = "fail" if "image" in prefixes else "review_required"
    else:
        result["image_integrity"] = "not_assessed"
    result["visual_semantics"] = "fail" if "palette" in prefixes else "review_required"
    result["journal_backend"] = "fail" if prefixes & mapping["journal_backend"] else "not_assessed"
    return result


def _make_qc(
    manifest: dict[str, Any],
    issues: list[dict[str, str]],
    cards: list[dict[str, Any]],
) -> dict[str, Any]:
    _schema_issue_severity(issues)
    findings = []
    for index, issue in enumerate(issues, start=1):
        findings.append({
            "finding_id": f"finding-{index:04d}",
            "severity": issue.get("severity", "error"),
            "code": issue.get("code", "deterministic:unknown"),
            "path": issue.get("path", "$"),
            "message": issue.get("message", "unspecified deterministic issue"),
            "review_route": issue.get("review_route", "deterministic"),
        })
    blocked = any(item["severity"] in {"blocker", "error"} for item in findings)
    maturity = manifest.get("maturity")
    if blocked:
        gate = "blocked"
    elif maturity in {"architecture_only", "ready_for_author_review"}:
        gate = "author_review_required"
    else:
        gate = "pass_for_declared_maturity"
    components = manifest.get("components", {}) if isinstance(manifest.get("components"), dict) else {}
    component_hashes = []
    for ref in [components.get("source_data_manifest")]:
        if isinstance(ref, dict) and isinstance(ref.get("artifact_sha256"), str):
            component_hashes.append(ref["artifact_sha256"])
    for key in ("figure_cards", "figure_contracts", "plot_recipes"):
        for ref in components.get(key, []) if isinstance(components.get(key), list) else []:
            if isinstance(ref, dict) and isinstance(ref.get("artifact_sha256"), str):
                component_hashes.append(ref["artifact_sha256"])
    trust = manifest.get("trust_bindings", {}) if isinstance(manifest.get("trust_bindings"), dict) else {}
    trusted_hashes = [
        ref.get("collection_sha256") for ref in trust.values()
        if isinstance(ref, dict) and isinstance(ref.get("collection_sha256"), str)
    ]
    qc: dict[str, Any] = {
        "schema_name": "figure_qc",
        "schema_version": "0.1.0",
        "contract_version": "0.1.1",
        "artifact_id": f"qc-{manifest.get('design_package_id', 'unknown')}",
        "design_package_id": manifest.get("design_package_id", "unknown"),
        "design_package_version": manifest.get("design_package_version", "0.1.0"),
        "design_package_hash": manifest.get("design_package_hash", "0" * 64),
        "validator_version": VALIDATOR_VERSION,
        "ruleset_version": RULESET_VERSION,
        "check_level": "deterministic_phase8a",
        "render_inspected": False,
        "component_hashes": sorted(set(component_hashes)),
        "trusted_binding_hashes": sorted(set(trusted_hashes)),
        "findings": findings,
        "domain_status": _domain_status(issues, cards),
        "readiness_gate": gate,
        "generated_at": manifest.get("created_at", "1970-01-01T00:00:00Z"),
        "figure_qc_sha256": "0" * 64,
    }
    qc["figure_qc_sha256"] = payload_sha256(qc, "figure_qc_sha256")
    return qc


def validate_figure_package(
    package_root: Path,
    manifest_filename: str = DEFAULT_MANIFEST,
    trust_root_path: Path | None = None,
    expected_trust_root_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate one package directory and return its deterministic QC result."""
    root = package_root.resolve()
    manifest_path = _safe_package_path(root, manifest_filename)
    if manifest_path is None or not manifest_path.is_file():
        raise FigurePackageError(f"design package manifest not found: {manifest_filename}")
    try:
        manifest = read_json(manifest_path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FigurePackageError(f"could not read design package manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise FigurePackageError("design package manifest must be a JSON object")

    issues: list[dict[str, str]] = []
    _validate_schema(manifest, SCHEMAS["manifest"], "$.manifest", issues)
    external_trust = _load_external_trust_root(
        root, trust_root_path, expected_trust_root_sha256, issues
    )

    def add(code: str, message: str, path: str = "$") -> None:
        issues.append({
            "layer": "deterministic", "path": path, "code": code,
            "message": message, "review_route": "deterministic", "severity": "error",
        })

    if manifest.get("design_package_hash") != payload_sha256(manifest, "design_package_hash"):
        add("identity:design_package_hash", "design_package_hash does not match canonical pre-QC manifest", "$.manifest.design_package_hash")
    if _contains_key({key: value for key, value in manifest.items() if key != "design_package_hash"}, "figure_qc"):
        add("identity:qc_cycle", "design package manifest must not include Figure QC", "$.manifest")

    documents, trust = _load_package_documents(root, manifest, issues)
    _validate_external_collection_identities(trust, external_trust, issues)
    source_manifests = documents["source_data_manifest"]
    if len(source_manifests) != 1:
        add("package:source_manifest_count", "exactly one source-data manifest is required")
        source_manifest = {"source_records": []}
    else:
        source_manifest = source_manifests[0]
    cards = documents["figure_card"]
    contracts = documents["figure_contract"]
    recipes = documents["plot_recipe"]
    trusted_sources = trust.get("trusted_source_inputs", {"records": []})
    analyses_collection = trust.get("trusted_analysis_outputs", {"records": []})
    authority_collection = trust.get("trusted_authority_inputs", {"records": []})

    inspections, input_identities = _validate_source_inputs(
        root, manifest, source_manifest, trusted_sources, cards, issues
    )
    sources = _index(source_manifest.get("source_records", []), "source_data_id", "$.source_data_manifest.source_records", add)
    analyses = _index(analyses_collection.get("records", []), "analysis_output_id", "$.trust.trusted_analysis_outputs.records", add)
    for analysis_id, record in analyses.items():
        input_identities[analysis_id] = (record.get("record_version", ""), record.get("record_sha256", ""))
    for artifact in [*cards, *contracts, *recipes, source_manifest]:
        if isinstance(artifact.get("artifact_id"), str):
            input_identities[artifact["artifact_id"]] = (
                artifact.get("schema_version", ""), artifact.get("artifact_sha256", "")
            )
    subjects = _build_subject_index(cards, contracts, list(analyses.values()))
    decisions, trusted_decisions = _validate_authority(
        authority_collection, subjects, input_identities, issues
    )
    _validate_analysis_outputs(analyses, sources, inspections, decisions, trusted_decisions, issues)
    _validate_upstream_and_structure(
        manifest, cards, contracts, recipes, sources, analyses, inspections,
        decisions, trusted_decisions, issues
    )

    _schema_issue_severity(issues)
    qc = _make_qc(manifest, issues, cards)
    qc_schema_issues: list[dict[str, str]] = []
    _validate_schema(qc, SCHEMAS["figure_qc"], "$.figure_qc", qc_schema_issues)
    if qc_schema_issues:
        _schema_issue_severity(qc_schema_issues)
        issues.extend(qc_schema_issues)
        qc = _make_qc(manifest, issues, cards)
    if qc.get("figure_qc_sha256") != payload_sha256(qc, "figure_qc_sha256"):
        raise FigurePackageError("internal non-circular Figure QC hash failure")
    return {
        "valid": not any(item.get("severity") in {"blocker", "error"} for item in issues),
        "issues": issues,
        "qc": qc,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", type=Path, help="directory containing the Phase 8A package")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, help="package-relative manifest filename")
    parser.add_argument(
        "--trust-root", type=Path, required=True,
        help="caller-supplied trust-root JSON outside the model-produced package",
    )
    parser.add_argument(
        "--trust-root-sha256", required=True,
        help="caller-held expected SHA-256 of --trust-root (not obtained from the design package)",
    )
    parser.add_argument("--output", type=Path, help="optional path for the generated figure_qc JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = validate_figure_package(
            args.package_root,
            args.manifest,
            args.trust_root,
            args.trust_root_sha256,
        )
    except FigurePackageError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    if args.output is not None:
        write_json(args.output, result["qc"])
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
