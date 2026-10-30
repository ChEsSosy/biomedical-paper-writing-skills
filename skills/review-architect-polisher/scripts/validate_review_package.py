#!/usr/bin/env python3
"""Validate a Phase 7A Review architecture package.

The validator treats authority decisions and raw source inputs as separately
supplied trust inputs. It independently checks hashes, references, access
ceilings, claim-origin provenance, evidence-unit independence, synthesis
coverage, and outline bindings. It does not assess scientific truth or write
Review prose.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import unicodedata
from pathlib import Path
from types import ModuleType
from typing import Any


CANDIDATE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMAS = CANDIDATE_ROOT / "schemas"
DEFAULT_VALIDATOR = CANDIDATE_ROOT / "shared-core" / "scripts" / "validate_artifact.py"
SCHEMAS = {
    "scope": "review-scope.schema.json",
    "registry": "review-source-registry.schema.json",
    "extraction": "review-extraction-record.schema.json",
    "authority": "review-authority-decision.schema.json",
    "synthesis": "review-synthesis-matrix.schema.json",
    "outline": "review-outline.schema.json",
}
ACCESS_RANK = {
    "unresolved": 0,
    "bibliographic_only": 1,
    "abstract_verified": 2,
    "full_text_verified": 3,
}


class PackageValidationError(RuntimeError):
    """Raised when package input or the shared validator cannot be loaded."""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def payload_sha256(value: dict[str, Any], hash_field: str) -> str:
    return canonical_sha256({key: item for key, item in value.items() if key != hash_field})


def _governed_projection(value: Any) -> Any:
    """Remove self hashes and authority references from an approval subject.

    Authority references are excluded to avoid a circular identity in which a
    decision hash is needed to calculate the exact content hash governed by
    that same decision. All scientific, bibliographic, access, scope, and
    structural fields remain in the projection.
    """
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
    """Hash the exact governed content using the non-circular projection."""
    return canonical_sha256(_governed_projection(value))


def normalize_source_span(value: str) -> str:
    """Normalize only encoding-level differences, never scientific content."""
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


def _trusted_input_hash(trusted_inputs: dict[str, Any], input_id: Any) -> str | None:
    value = trusted_inputs.get(input_id)
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("sha256"), str):
        path = _trusted_input_path(trusted_inputs, input_id)
        if path is not None and path.is_file():
            try:
                actual = file_sha256(path)
            except OSError:
                return None
            return actual if actual == value["sha256"] else None
        return value["sha256"]
    return None


def _trusted_input_path(trusted_inputs: dict[str, Any], input_id: Any) -> Path | None:
    value = trusted_inputs.get(input_id)
    if isinstance(value, dict) and isinstance(value.get("path"), (str, Path)):
        return Path(value["path"])
    return None


def resolve_source_span(locator: Any, trusted_inputs: dict[str, Any]) -> tuple[str | None, str | None]:
    """Resolve a line/character locator against a separately supplied input.

    Character offsets are zero-based and end-exclusive. Multi-line spans join
    normalized source lines with a single LF, matching the canonical text used
    for hashing.
    """
    if not isinstance(locator, dict) or locator.get("locator_type") != "line_char_range":
        return None, "only line_char_range locators are resolvable in Phase 7A.1"
    if locator.get("side") != "source":
        return None, "substantive extraction locator must use side=source"
    input_id = locator.get("file_id")
    path = _trusted_input_path(trusted_inputs, input_id)
    if path is None or not path.is_file():
        return None, f"locator file_id is not a supplied trusted input: {input_id}"
    try:
        text = normalize_source_span(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        return None, f"trusted source input could not be read as UTF-8: {exc}"
    lines = text.split("\n")
    start_line = locator.get("start_line")
    end_line = locator.get("end_line")
    start_char = locator.get("start_char")
    end_char = locator.get("end_char")
    if not all(isinstance(item, int) for item in (start_line, end_line, start_char, end_char)):
        return None, "locator line and character coordinates must be integers"
    if start_line < 1 or end_line < start_line or end_line > len(lines):
        return None, "locator line range is outside the trusted input"
    first = lines[start_line - 1]
    last = lines[end_line - 1]
    if start_char < 0 or start_char > len(first) or end_char < 0 or end_char > len(last):
        return None, "locator character range is outside the trusted input"
    if start_line == end_line:
        if end_char < start_char:
            return None, "locator end_char precedes start_char"
        span = first[start_char:end_char]
    else:
        span = "\n".join([first[start_char:], *lines[start_line:end_line - 1], last[:end_char]])
    return hashlib.sha256(normalize_source_span(span).encode("utf-8")).hexdigest(), None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_identity(value: dict[str, Any]) -> dict[str, str | None]:
    return {
        "artifact_id": value.get("artifact_id"),
        "artifact_version": value.get("schema_version"),
        "artifact_sha256": value.get("artifact_sha256"),
    }


def _load_validator(path: Path) -> ModuleType:
    resolved = path.resolve()
    if not resolved.is_file():
        raise PackageValidationError(f"shared validator not found: {resolved}")
    spec = importlib.util.spec_from_file_location("phase7a_shared_validator", resolved)
    if spec is None or spec.loader is None:
        raise PackageValidationError(f"could not import shared validator: {resolved}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _schema_issues(
    module: ModuleType,
    schema_path: Path,
    value: Any,
    instance_path: str,
) -> list[dict[str, str]]:
    root = read_json(schema_path)
    store = module.SchemaStore()
    raw = module.validate_instance(value, root, schema_path.resolve(), root, store, instance_path)
    return [
        {
            "layer": "schema",
            "path": issue.path,
            "code": f"schema:{issue.keyword}",
            "message": issue.message,
        }
        for issue in raw
    ]


def validate_schema_layer(
    scope: dict[str, Any],
    registry: dict[str, Any],
    extractions: list[dict[str, Any]],
    authority_bundle: dict[str, Any],
    synthesis: dict[str, Any],
    outline: dict[str, Any],
    schemas_dir: Path = DEFAULT_SCHEMAS,
    validator_path: Path = DEFAULT_VALIDATOR,
) -> list[dict[str, str]]:
    """Validate the six contracted schemas without third-party dependencies."""
    module = _load_validator(validator_path)
    jobs = [
        (SCHEMAS["scope"], scope, "$.scope"),
        (SCHEMAS["registry"], registry, "$.source_registry"),
        (SCHEMAS["synthesis"], synthesis, "$.synthesis_matrix"),
        (SCHEMAS["outline"], outline, "$.outline"),
    ]
    issues: list[dict[str, str]] = []
    for filename, value, path in jobs:
        issues.extend(_schema_issues(module, schemas_dir / filename, value, path))
    for index, value in enumerate(extractions):
        issues.extend(_schema_issues(
            module,
            schemas_dir / SCHEMAS["extraction"],
            value,
            f"$.extractions[{index}]",
        ))
    records = authority_bundle.get("records", []) if isinstance(authority_bundle, dict) else []
    if not isinstance(records, list):
        issues.append({
            "layer": "schema", "path": "$.authority_bundle.records", "code": "schema:type",
            "message": "authority bundle records must be an array",
        })
    else:
        for index, value in enumerate(records):
            issues.extend(_schema_issues(
                module,
                schemas_dir / SCHEMAS["authority"],
                value,
                f"$.authority_bundle.records[{index}]",
            ))
    return issues


def _index_records(
    records: list[dict[str, Any]],
    key: str,
    path: str,
    add: Any,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        value = record.get(key) if isinstance(record, dict) else None
        if not isinstance(value, str) or not value:
            add(f"identity:{key}", f"record lacks {key}", f"{path}[{index}]")
            continue
        if value in result:
            add(f"identity:duplicate_{key}", f"duplicate {key}: {value}", f"{path}[{index}].{key}")
            continue
        result[value] = record
    return result


def _ref_matches(ref: Any, value: dict[str, Any]) -> bool:
    return isinstance(ref, dict) and ref == artifact_identity(value)


def _ids(records: list[dict[str, Any]], key: str) -> set[str]:
    return {item.get(key) for item in records if isinstance(item.get(key), str)}


def validate_review_package(
    scope: dict[str, Any],
    registry: dict[str, Any],
    extractions: list[dict[str, Any]],
    authority_bundle: dict[str, Any],
    expected_authority_manifest_sha256: str,
    synthesis: dict[str, Any],
    outline: dict[str, Any],
    trusted_inputs: dict[str, Any],
) -> list[dict[str, str]]:
    """Return deterministic cross-artifact issues for a Phase 7A package."""
    issues: list[dict[str, str]] = []

    def add(code: str, message: str, path: str = "$") -> None:
        issues.append({"layer": "semantic", "path": path, "code": code, "message": message})

    # Hashes and one-way artifact lineage are recomputed; self-declared hashes are not trusted.
    for name, artifact in (
        ("scope", scope), ("registry", registry), ("synthesis", synthesis), ("outline", outline),
    ):
        if artifact.get("artifact_sha256") != payload_sha256(artifact, "artifact_sha256"):
            add("identity:artifact_hash", f"{name} artifact_sha256 is invalid", f"$.{name}.artifact_sha256")
    if not _ref_matches(registry.get("scope_ref"), scope):
        add("binding:registry_scope", "source registry scope_ref does not match scope", "$.registry.scope_ref")
    for name, artifact, field, upstream in (
        ("synthesis", synthesis, "scope_ref", scope),
        ("synthesis", synthesis, "source_registry_ref", registry),
        ("outline", outline, "scope_ref", scope),
        ("outline", outline, "source_registry_ref", registry),
        ("outline", outline, "synthesis_ref", synthesis),
    ):
        if not _ref_matches(artifact.get(field), upstream):
            add("binding:artifact_ref", f"{name}.{field} does not match upstream artifact", f"$.{name}.{field}")

    # Authority records are trusted only through a separately supplied bundle hash.
    if not isinstance(authority_bundle, dict):
        add("authority:bundle", "authority bundle must be an object", "$.authority_bundle")
        authority_bundle = {}
    if authority_bundle.get("manifest_version") != "0.1.0":
        add("authority:manifest_version", "authority manifest_version must be 0.1.0", "$.authority_bundle.manifest_version")
    if canonical_sha256(authority_bundle) != expected_authority_manifest_sha256:
        add("authority:manifest_hash", "authority bundle does not match externally supplied manifest hash", "$.authority_bundle")
    decision_records = authority_bundle.get("records", [])
    if not isinstance(decision_records, list):
        decision_records = []
    decisions = _index_records(decision_records, "decision_id", "$.authority_bundle.records", add)
    trusted_decisions: set[str] = set()
    for decision_id, decision in decisions.items():
        path = f"$.authority_bundle.records[{decision_id}]"
        if decision.get("decision_sha256") != payload_sha256(decision, "decision_sha256"):
            add("authority:decision_hash", f"decision hash is invalid: {decision_id}", path)
            continue
        origin = decision.get("authorization_origin")
        state = decision.get("authorization_state")
        role = decision.get("decision_producer_role")
        if state == "author_approved" and (origin != "author" or role != "author"):
            add("authority:author_mint", "author_approved requires author origin and author producer role", path)
            continue
        if role == "author" and (origin != "author" or state != "author_approved"):
            add("authority:author_state", "author decision requires author_approved state", path)
            continue
        if role != "author" and (origin != "calling_workflow" or state != "caller_accepted"):
            add("authority:workflow_state", "authorized workflow decision requires calling_workflow/caller_accepted", path)
            continue
        missing_binding = False
        for binding in decision.get("upstream_input_bindings", []):
            input_id = binding.get("input_id")
            expected = binding.get("input_sha256")
            if _trusted_input_hash(trusted_inputs, input_id) != expected:
                add("authority:input_binding", f"trusted input binding mismatch: {input_id}", path)
                missing_binding = True
        if not missing_binding:
            trusted_decisions.add(decision_id)

    def require_decision(
        ref: Any,
        expected_type: str,
        subject_type: str,
        subject_id: str,
        asserted_state: str | None,
        path: str,
        governed_version: str,
        governed_sha256: str,
        *,
        author_only: bool = False,
    ) -> bool:
        if not isinstance(ref, dict):
            add("authority:missing_ref", f"missing decision_ref for {subject_type} {subject_id}", path)
            return False
        decision_id = ref.get("decision_id")
        decision = decisions.get(decision_id)
        if decision is None:
            add("authority:missing_decision", f"decision_ref does not resolve: {decision_id}", path)
            return False
        if ref.get("interface_version") != decision.get("interface_version") or ref.get("decision_sha256") != decision.get("decision_sha256"):
            add("authority:ref_hash", f"decision_ref version/hash mismatch: {decision_id}", path)
            return False
        if decision_id not in trusted_decisions:
            add("authority:untrusted_decision", f"decision is not trusted: {decision_id}", path)
            return False
        if author_only and (
            decision.get("decision_producer_role") != "author"
            or decision.get("authorization_origin") != "author"
            or decision.get("authorization_state") != "author_approved"
        ):
            add(
                "authority:role_policy",
                f"decision type {expected_type} requires author/author_approved authority",
                path,
            )
            return False
        if decision.get("decision_type") != expected_type:
            add("authority:decision_type", f"expected {expected_type}, got {decision.get('decision_type')}", path)
            return False
        subjects = decision.get("subject_refs", [])
        match = next((
            item for item in subjects
            if item.get("subject_type") == subject_type and item.get("subject_id") == subject_id
        ), None)
        if match is None:
            add("authority:subject", f"decision does not govern {subject_type} {subject_id}", path)
            return False
        if asserted_state is not None and match.get("asserted_state") != asserted_state:
            add("authority:asserted_state", f"decision state does not match {asserted_state}", path)
            return False
        if match.get("artifact_version") != governed_version:
            add(
                "authority:subject_version",
                f"decision subject version does not match current governed subject: {governed_version}",
                path,
            )
            return False
        if match.get("artifact_sha256") != governed_sha256:
            add(
                "authority:subject_hash",
                "decision subject hash does not match current governed subject content",
                path,
            )
            return False
        if decision.get("decision_value") not in {"approve", "resolve", "confirm"}:
            add("authority:decision_value", "decision does not positively resolve the governed subject", path)
            return False
        return True

    # Scope type, profile isolation, authorization, objectives, and coverage authority.
    review_type = scope.get("review_type")
    if scope.get("document_type") != "review_article":
        add("routing:document_type", "Phase 7A accepts review_article only", "$.scope.document_type")
    if review_type in {"scoping_style_review", "systematic_style_draft"} and scope.get("execution_mode") != "architecture_only_degraded":
        add("routing:formal_review", "formal/scoping style is architecture_only_degraded in the minimum implementation", "$.scope.execution_mode")
    profile = scope.get("profile_ref")
    if isinstance(profile, dict) and profile.get("profile_kind") != "review_article":
        add("profile:non_review", "non-Review profile is not admissible in a Review architecture package", "$.scope.profile_ref")
    authorization = scope.get("authorization", {})
    if authorization.get("authorization_state") == "author_approved":
        require_decision(
            authorization.get("decision_ref"), "scope_decision", "scope", scope.get("artifact_id", ""),
            "approved", "$.scope.authorization.decision_ref",
            scope.get("schema_version", ""), governed_subject_sha256(scope), author_only=True,
        )
    for index, objective in enumerate(scope.get("author_objectives", [])):
        require_decision(
            objective.get("decision_ref"), "author_objective", "author_objective",
            objective.get("author_objective_id", ""), "approved",
            f"$.scope.author_objectives[{index}].decision_ref",
            scope.get("schema_version", ""), governed_subject_sha256(objective), author_only=True,
        )

    coverage = scope.get("coverage", {})
    coverage_trusted = False
    if coverage.get("coverage_origin") != "model_proposed" and coverage.get("coverage_review_status") == "approved":
        coverage_trusted = require_decision(
            coverage.get("coverage_decision_ref"), "source_set_coverage", "coverage_record",
            coverage.get("coverage_id", ""), "approved", "$.scope.coverage.coverage_decision_ref",
            scope.get("schema_version", ""), governed_subject_sha256(coverage),
        )
        for input_id in coverage.get("supporting_input_ids", []):
            if _trusted_input_hash(trusted_inputs, input_id) is None:
                add("coverage:input_binding", f"coverage supporting input is absent: {input_id}", "$.scope.coverage")
                coverage_trusted = False

    # Source registry identities, access ceilings, and evidence-unit independence.
    source_records = registry.get("source_records", [])
    sources = _index_records(source_records, "source_id", "$.registry.source_records", add)
    included_sources = {sid for sid, value in sources.items() if value.get("inclusion_status") == "included"}
    permitted_sources = set(scope.get("permitted_source_ids", []))
    if included_sources != permitted_sources:
        add("scope:source_set", "included source IDs must exactly match scope permitted_source_ids", "$.registry.source_records")
    identity_owners: dict[tuple[str, str], str] = {}
    effective_access: dict[str, str] = {}
    evidence_unit_trusted: dict[str, bool] = {}
    source_trusted_input_ids: dict[str, set[str]] = {}
    for source_id, source in sources.items():
        path = f"$.registry.source_records[{source_id}]"
        if source.get("source_record_sha256") != payload_sha256(source, "source_record_sha256"):
            add("identity:source_record_hash", f"source record hash is invalid: {source_id}", path)
        for identity in source.get("bibliographic_identity", {}).get("identity_records", []):
            key = (str(identity.get("identity_type", "")).lower(), str(identity.get("value", "")).lower())
            owner = identity_owners.get(key)
            if owner is not None and source.get("inclusion_status") == "included" and sources[owner].get("inclusion_status") == "included":
                add("source:duplicate_identity", f"included sources share bibliographic identity: {owner}, {source_id}", path)
            else:
                identity_owners[key] = source_id
        if source.get("inclusion_status") == "included" and source.get("verification_origin") == "model_proposed":
            add("source:unverified_identity", "model-proposed source identity cannot be admitted as verified", path)
        for linked_id in source.get("linked_source_ids", []):
            if linked_id not in sources:
                add("source:missing_link", f"linked source does not exist: {linked_id}", path)

        level = source.get("access_level", "unresolved")
        access_trusted = level in {"bibliographic_only", "unresolved"}
        bound_input_ids: set[str] = set()
        if level in {"full_text_verified", "abstract_verified"}:
            ref = source.get("access_verification_ref")
            origin = source.get("access_verification_origin")
            if origin == "model_proposed" or source.get("access_verification_status") != "approved":
                add("access:model_upgrade", f"trusted access cannot be model-proposed: {source_id}", path)
                access_trusted = False
            elif isinstance(ref, dict) and "decision_id" in ref:
                access_trusted = require_decision(
                    ref, "source_access_verification", "source_record", source_id, level,
                    f"{path}.access_verification_ref",
                    registry.get("schema_version", ""), governed_subject_sha256(source),
                )
            elif isinstance(ref, dict) and "input_id" in ref:
                access_trusted = _trusted_input_hash(trusted_inputs, ref.get("input_id")) == ref.get("input_sha256")
                if not access_trusted:
                    add("access:source_evidence", f"source evidence binding mismatch: {source_id}", path)
            else:
                add("access:missing_verification", f"verified access lacks an admissible reference: {source_id}", path)
                access_trusted = False
            if access_trusted and isinstance(ref, dict) and "decision_id" in ref:
                decision = decisions.get(ref.get("decision_id"), {})
                bound_input_ids.update(
                    binding.get("input_id")
                    for binding in decision.get("upstream_input_bindings", [])
                    if isinstance(binding.get("input_id"), str)
                )
            elif access_trusted and isinstance(ref, dict) and isinstance(ref.get("input_id"), str):
                bound_input_ids.add(ref["input_id"])
        effective_access[source_id] = level if access_trusted else "unresolved"
        source_trusted_input_ids[source_id] = bound_input_ids

        independence_trusted = False
        if source.get("independence_status") != "unresolved":
            if source.get("assignment_origin") == "model_proposed":
                add("independence:model_baseline", f"model-proposed evidence-unit assignment cannot be trusted: {source_id}", path)
            elif source.get("independence_review_status") == "approved":
                independence_trusted = require_decision(
                    source.get("independence_decision_ref"), "independence_resolution", "evidence_unit",
                    source.get("evidence_unit_id", ""), source.get("independence_status"),
                    f"{path}.independence_decision_ref",
                    registry.get("schema_version", ""), governed_subject_sha256(source),
                )
        evidence_unit_id = source.get("evidence_unit_id")
        evidence_unit_trusted[evidence_unit_id] = evidence_unit_trusted.get(evidence_unit_id, True) and independence_trusted

    # Linked publications cannot be represented as distinct trusted independent
    # studies merely because they have different source IDs.
    checked_links: set[tuple[str, str]] = set()
    for source_id, source in sources.items():
        for linked_id in source.get("linked_source_ids", []):
            pair = tuple(sorted((source_id, linked_id)))
            if linked_id not in sources or pair in checked_links:
                continue
            checked_links.add(pair)
            linked = sources[linked_id]
            unit_id = source.get("evidence_unit_id")
            linked_unit_id = linked.get("evidence_unit_id")
            if (
                source.get("inclusion_status") == "included"
                and linked.get("inclusion_status") == "included"
                and source.get("independence_status") == "independent"
                and linked.get("independence_status") == "independent"
                and unit_id != linked_unit_id
                and evidence_unit_trusted.get(unit_id, False)
                and evidence_unit_trusted.get(linked_unit_id, False)
            ):
                add(
                    "independence:linked_double_count",
                    f"linked publications are represented as distinct independent units: {source_id}, {linked_id}",
                    f"$.registry.source_records[{source_id}].linked_source_ids",
                )

    # Extraction interface closure and access compatibility.
    extraction_index = _index_records(extractions, "extraction_record_id", "$.extractions", add)
    extraction_ids_by_source: dict[str, set[str]] = {source_id: set() for source_id in sources}
    for extraction_id, extraction in extraction_index.items():
        path = f"$.extractions[{extraction_id}]"
        if extraction.get("record_sha256") != payload_sha256(extraction, "record_sha256"):
            add("identity:extraction_hash", f"extraction hash is invalid: {extraction_id}", path)
        if not _ref_matches(extraction.get("source_registry_ref"), registry):
            add("binding:extraction_registry", "extraction source_registry_ref does not match registry", path)
        source_id = extraction.get("source_id")
        source = sources.get(source_id)
        if source is None:
            add("extraction:missing_source", f"extraction source does not exist: {source_id}", path)
            continue
        extraction_ids_by_source[source_id].add(extraction_id)
        if extraction.get("evidence_unit_id") != source.get("evidence_unit_id"):
            add("extraction:evidence_unit", "extraction evidence_unit_id does not match source registry", path)
        if extraction.get("study_family_id") != source.get("study_family_id"):
            add("extraction:study_family", "extraction study_family_id does not match source registry", path)
        level = extraction.get("source_access_level", "unresolved")
        if ACCESS_RANK.get(level, -1) > ACCESS_RANK.get(effective_access.get(source_id, "unresolved"), -1):
            add("extraction:access_ceiling", "extraction exceeds trusted source access level", path)
        if extraction.get("extraction_type") != "author_note" and level in {"bibliographic_only", "unresolved"}:
            add("extraction:substantive_access", "substantive extraction requires abstract or full-text access", path)
        locator = extraction.get("source_locator")
        if extraction.get("extraction_type") != "author_note" and not isinstance(locator, dict):
            add("extraction:locator", "substantive extraction requires a source locator", path)
        if isinstance(locator, dict) and extraction.get("source_span_sha256") != locator.get("span_sha256"):
            add("extraction:span_hash", "source_span_sha256 does not match locator span_sha256", path)
        if extraction.get("extraction_type") != "author_note" and isinstance(locator, dict):
            input_id = locator.get("file_id")
            if input_id not in source_trusted_input_ids.get(source_id, set()):
                add(
                    "source_span:source_binding",
                    "locator trusted input is not bound to this source's verified access decision",
                    path,
                )
            actual_span_sha256, resolution_error = resolve_source_span(locator, trusted_inputs)
            if resolution_error is not None:
                add("source_span:locator", resolution_error, path)
            elif (
                actual_span_sha256 != locator.get("span_sha256")
                or actual_span_sha256 != extraction.get("source_span_sha256")
            ):
                add(
                    "source_span:hash_mismatch",
                    "locator/extraction span hash does not match the actual trusted source span",
                    path,
                )
        if not any(isinstance(extraction.get(field), str) and extraction.get(field) for field in ("extracted_content", "normalized_proposition")):
            add("extraction:empty", "extraction must contain extracted content or normalized proposition", path)
        if extraction.get("review_status") == "approved":
            require_decision(
                extraction.get("decision_ref"), "extraction_review", "extraction_record", extraction_id,
                "approved", f"{path}.decision_ref",
                extraction.get("interface_version", ""), governed_subject_sha256(extraction),
            )
        if extraction.get("extraction_origin") == "model_assisted_extraction" and extraction.get("review_status") == "approved" and extraction.get("review_decision_origin") == "model_proposed":
            add("extraction:self_approval", "model-assisted extraction cannot approve itself", path)
    for source_id, source in sources.items():
        declared = set(source.get("extraction_record_ids", []))
        actual = extraction_ids_by_source.get(source_id, set())
        if declared != actual:
            add("extraction:registry_inventory", f"registry extraction IDs differ from supplied records for {source_id}", f"$.registry.source_records[{source_id}]")

    # Synthesis indexes and reference closure.
    axes = _index_records(synthesis.get("taxonomy_axes", []), "axis_id", "$.synthesis.taxonomy_axes", add)
    themes = _index_records(synthesis.get("themes", []), "theme_id", "$.synthesis.themes", add)
    clusters = _index_records(synthesis.get("evidence_clusters", []), "cluster_id", "$.synthesis.evidence_clusters", add)
    claims = _index_records(synthesis.get("claims", []), "claim_id", "$.synthesis.claims", add)
    relations = _index_records(synthesis.get("citation_relations", []), "relation_id", "$.synthesis.citation_relations", add)
    conflicts = _index_records(synthesis.get("conflicts", []), "conflict_id", "$.synthesis.conflicts", add)
    limitations = _index_records(synthesis.get("limitations", []), "limitation_id", "$.synthesis.limitations", add)
    gaps = _index_records(synthesis.get("gaps", []), "gap_id", "$.synthesis.gaps", add)
    objectives = _index_records(scope.get("author_objectives", []), "author_objective_id", "$.scope.author_objectives", add)

    for axis_id, axis in axes.items():
        path = f"$.synthesis.taxonomy_axes[{axis_id}]"
        categories = set(axis.get("categories", []))
        for classification in axis.get("classifications", []):
            if classification.get("category") not in categories:
                add("taxonomy:category", "classification category is not declared by its axis", path)
            if classification.get("assignment_origin") == "model_proposed" and classification.get("review_status") == "approved":
                add("taxonomy:self_approval", "model-proposed classification cannot be approved by assertion", path)
        if axis.get("axis_kind") == "evaluative_axis" and not axis.get("rubric_ref"):
            add("taxonomy:missing_rubric", "evaluative axis requires a rubric_ref", path)
    for theme_id, theme in themes.items():
        unknown = set(theme.get("axis_ids", [])) - set(axes)
        if unknown:
            add("theme:axis_ref", f"theme references unknown axes: {sorted(unknown)}", f"$.synthesis.themes[{theme_id}]")

    for cluster_id, cluster in clusters.items():
        path = f"$.synthesis.evidence_clusters[{cluster_id}]"
        unknown_sources = set(cluster.get("source_ids", [])) - included_sources
        unknown_extractions = set(cluster.get("extraction_record_ids", [])) - set(extraction_index)
        unknown_themes = set(cluster.get("theme_ids", [])) - set(themes)
        if unknown_sources:
            add("cluster:source_ref", f"cluster references non-admitted sources: {sorted(unknown_sources)}", path)
        if unknown_extractions:
            add("cluster:extraction_ref", f"cluster references unknown extractions: {sorted(unknown_extractions)}", path)
        if unknown_themes:
            add("cluster:theme_ref", f"cluster references unknown themes: {sorted(unknown_themes)}", path)
        derived_sources = {extraction_index[item].get("source_id") for item in cluster.get("extraction_record_ids", []) if item in extraction_index}
        derived_units = {extraction_index[item].get("evidence_unit_id") for item in cluster.get("extraction_record_ids", []) if item in extraction_index}
        if set(cluster.get("source_ids", [])) != derived_sources:
            add("cluster:source_binding", "cluster source_ids do not equal extraction-derived sources", path)
        if set(cluster.get("evidence_unit_ids", [])) != derived_units:
            add("cluster:evidence_unit_binding", "cluster evidence_unit_ids do not equal extraction-derived units", path)

    valid_basis = {
        "gap": set(gaps), "limitation": set(limitations), "conflict": set(conflicts),
        "author_objective": set(objectives),
    }
    for claim_id, claim in claims.items():
        path = f"$.synthesis.claims[{claim_id}]"
        origin = claim.get("claim_origin")
        source_ids = set(claim.get("source_ids", []))
        extraction_ids = set(claim.get("extraction_record_ids", []))
        unit_ids = set(claim.get("evidence_unit_ids", []))
        cluster_ids = set(claim.get("evidence_cluster_ids", []))
        if set(claim.get("theme_ids", [])) - set(themes):
            add("claim:theme_ref", "claim references unknown theme", path)
        if source_ids - included_sources:
            add("claim:source_ref", "claim references non-admitted source", path)
        if extraction_ids - set(extraction_index):
            add("claim:extraction_ref", "claim references unknown extraction", path)
        if cluster_ids - set(clusters):
            add("claim:cluster_ref", "claim references unknown evidence cluster", path)
        derived_sources = {extraction_index[item].get("source_id") for item in extraction_ids if item in extraction_index}
        derived_units = {extraction_index[item].get("evidence_unit_id") for item in extraction_ids if item in extraction_index}
        if extraction_ids and source_ids != derived_sources:
            add("claim:source_binding", "claim source_ids do not equal extraction-derived sources", path)
        if extraction_ids and unit_ids != derived_units:
            add("claim:evidence_unit_binding", "claim evidence_unit_ids do not equal extraction-derived units", path)
        if origin == "source_claim":
            if len(source_ids) != 1 or not extraction_ids:
                add("claim:source_claim_provenance", "source_claim requires exactly one source and at least one extraction", path)
        elif origin == "cross_source_synthesis":
            if len(source_ids) < 2 or not extraction_ids or not cluster_ids:
                add("claim:cross_source_cardinality", "cross_source_synthesis requires at least two sources, extractions, and a cluster", path)
        elif origin == "author_position":
            require_decision(
                claim.get("decision_ref"), "author_position_origin", "author_position", claim_id,
                "approved", f"{path}.decision_ref",
                synthesis.get("schema_version", ""), governed_subject_sha256(claim), author_only=True,
            )
            if source_ids and not any(rel.get("claim_id") == claim_id for rel in relations.values()):
                add("claim:author_position_source", "author_position source support requires a separate citation relation", path)
        elif origin == "future_direction":
            basis_refs = claim.get("basis_refs", [])
            if not basis_refs:
                add("claim:future_basis", "future_direction requires a gap, limitation, conflict, or author objective", path)
            for basis in basis_refs:
                if basis.get("basis_id") not in valid_basis.get(basis.get("basis_type"), set()):
                    add("claim:future_basis_ref", "future_direction basis does not resolve", path)
            only_author_objective = bool(basis_refs) and all(item.get("basis_type") == "author_objective" for item in basis_refs)
            if only_author_objective and source_ids:
                add("claim:author_objective_attribution", "author-objective future direction must not fabricate source attribution", path)
        if claim.get("relation_origin") == "model_proposed" and claim.get("review_status") == "approved":
            add("claim:self_approval", "model-proposed synthesis cannot become approved by assertion", path)
        required_access = ACCESS_RANK.get(claim.get("access_constraint"), -1)
        for source_id in source_ids:
            if ACCESS_RANK.get(effective_access.get(source_id, "unresolved"), -1) < required_access:
                add("claim:access_ceiling", f"claim requires stronger access than trusted for {source_id}", path)
        if claim.get("agreement_scope") == "field_wide":
            if not coverage_trusted:
                add("consensus:coverage_authority", "field-wide consensus lacks trusted coverage authority", path)
            require_decision(
                claim.get("decision_ref"), "synthesis_decision", "synthesis_claim", claim_id,
                "approved", f"{path}.decision_ref",
                synthesis.get("schema_version", ""), governed_subject_sha256(claim), author_only=True,
            )
            if any(not evidence_unit_trusted.get(unit_id, False) for unit_id in unit_ids):
                add("consensus:independence_authority", "field-wide consensus uses unresolved evidence-unit independence", path)

    for relation_id, relation in relations.items():
        path = f"$.synthesis.citation_relations[{relation_id}]"
        claim = claims.get(relation.get("claim_id"))
        if claim is None:
            add("citation:claim_ref", "citation relation references unknown claim", path)
            continue
        source_ids = set(relation.get("source_ids", []))
        extraction_ids = set(relation.get("extraction_record_ids", []))
        unknown_sources = source_ids - included_sources
        unknown_extractions = extraction_ids - set(extraction_index)
        if unknown_sources:
            add("citation:source_ref", f"citation relation references unknown sources: {sorted(unknown_sources)}", path)
        if unknown_extractions:
            add(
                "citation:extraction_ref",
                f"citation relation references unknown extractions: {sorted(unknown_extractions)}",
                path,
            )
        if source_ids - set(claim.get("source_ids", [])) or extraction_ids - set(claim.get("extraction_record_ids", [])):
            add("citation:claim_scope", "citation relation exceeds claim source/extraction scope", path)
        derived_sources = {extraction_index[item].get("source_id") for item in extraction_ids if item in extraction_index}
        if extraction_ids and source_ids != derived_sources:
            add("citation:extraction_binding", "citation source_ids do not match extraction records", path)
        if relation.get("relation_origin") == "model_proposed" and (
            relation.get("support_relation") == "direct_support" or relation.get("review_status") == "approved"
        ):
            add("citation:model_support", "model-proposed relation cannot establish verified direct support", path)
        if relation.get("review_status") == "approved":
            require_decision(
                relation.get("decision_ref"), "support_relation_review", "support_relation", relation_id,
                "approved", f"{path}.decision_ref",
                synthesis.get("schema_version", ""), governed_subject_sha256(relation),
            )
        actual = relation.get("actual_access_level", "unresolved")
        required = relation.get("access_constraint", "unresolved")
        if ACCESS_RANK.get(actual, -1) < ACCESS_RANK.get(required, -1):
            add("citation:access_constraint", "citation actual access is weaker than its constraint", path)
        for source_id in source_ids:
            if actual != effective_access.get(source_id):
                add("citation:access_identity", f"citation access does not match trusted registry access for {source_id}", path)

    # Conflict, limitation, and gap inventories must resolve and use deterministic counts.
    for collection_name, collection in (("conflicts", conflicts), ("limitations", limitations)):
        for record_id, record in collection.items():
            path = f"$.synthesis.{collection_name}[{record_id}]"
            if set(record.get("source_ids", [])) - included_sources:
                add(f"{collection_name}:source_ref", "record references non-admitted source", path)
            if set(record.get("extraction_record_ids", [])) - set(extraction_index):
                add(f"{collection_name}:extraction_ref", "record references unknown extraction", path)
    for gap_id, gap in gaps.items():
        path = f"$.synthesis.gaps[{gap_id}]"
        gap_sources = set(gap.get("source_ids", []))
        gap_units = set(gap.get("evidence_unit_ids", []))
        trusted_independent = {unit for unit in gap_units if evidence_unit_trusted.get(unit, False)}
        if gap.get("supporting_source_count") != len(gap_sources):
            add("gap:source_count", "supporting_source_count is not deterministic", path)
        if gap.get("independent_evidence_unit_count") != len(trusted_independent):
            add("gap:independent_count", "independent_evidence_unit_count is not deterministic", path)

    synthesis_audit = synthesis.get("source_coverage_audit", {})
    synthesis_assigned = set().union(*(set(item.get("source_ids", [])) for item in clusters.values())) if clusters else set()
    synthesis_unassigned = {item.get("source_id") for item in synthesis_audit.get("unassigned_sources", [])}
    if set(synthesis_audit.get("included_source_ids", [])) != included_sources:
        add("coverage:synthesis_included", "synthesis coverage included_source_ids do not match registry", "$.synthesis.source_coverage_audit")
    if set(synthesis_audit.get("assigned_source_ids", [])) != synthesis_assigned:
        add("coverage:synthesis_assigned", "synthesis assigned_source_ids do not match evidence clusters", "$.synthesis.source_coverage_audit")
    if synthesis_assigned & synthesis_unassigned or synthesis_assigned | synthesis_unassigned != included_sources:
        add("coverage:synthesis_partition", "synthesis assigned/unassigned sources do not exactly partition admitted sources", "$.synthesis.source_coverage_audit")

    # Outline references must preserve the synthesis theme/cluster relationships.
    if outline.get("review_type") != review_type:
        add("outline:review_type", "outline review_type does not match scope", "$.outline.review_type")
    outline_profile = outline.get("profile_guidance")
    if isinstance(outline_profile, dict) and outline_profile.get("profile_kind") != "review_article":
        add("profile:outline_non_review", "non-Review profile cannot guide Review outline decisions", "$.outline.profile_guidance")
    if set(outline.get("taxonomy_axis_ids", [])) - set(axes):
        add("outline:taxonomy_ref", "outline references unknown taxonomy axis", "$.outline.taxonomy_axis_ids")
    paragraph_ids: set[str] = set()
    outline_sources: set[str] = set()
    for section_index, section in enumerate(outline.get("section_plans", [])):
        section_themes = set(section.get("theme_ids", []))
        if section_themes - set(themes):
            add("outline:section_theme", "section references unknown theme", f"$.outline.section_plans[{section_index}]")
        for paragraph_index, paragraph in enumerate(section.get("paragraph_plans", [])):
            path = f"$.outline.section_plans[{section_index}].paragraph_plans[{paragraph_index}]"
            paragraph_id = paragraph.get("paragraph_id")
            if paragraph_id in paragraph_ids:
                add("outline:duplicate_paragraph", f"duplicate paragraph_id: {paragraph_id}", path)
            paragraph_ids.add(paragraph_id)
            theme_id = paragraph.get("theme_id")
            if theme_id not in section_themes:
                add("outline:paragraph_theme", "paragraph theme is not assigned to its section", path)
            for claim_id in paragraph.get("claim_ids", []):
                claim = claims.get(claim_id)
                if claim is None:
                    add("outline:claim_ref", f"unknown claim: {claim_id}", path)
                elif theme_id not in claim.get("theme_ids", []):
                    add("outline:claim_theme_binding", "paragraph claim belongs to a different theme", path)
            for cluster_id in paragraph.get("evidence_cluster_ids", []):
                cluster = clusters.get(cluster_id)
                if cluster is None:
                    add("outline:cluster_ref", f"unknown evidence cluster: {cluster_id}", path)
                elif theme_id not in cluster.get("theme_ids", []):
                    add("outline:cluster_theme_binding", "paragraph evidence cluster belongs to a different theme", path)
            assigned_claims = [
                claims[claim_id]
                for claim_id in paragraph.get("claim_ids", [])
                if claim_id in claims
            ]
            allowed_clusters = {
                cluster_id
                for claim in assigned_claims
                for cluster_id in claim.get("evidence_cluster_ids", [])
            }
            unrelated_clusters = set(paragraph.get("evidence_cluster_ids", [])) - allowed_clusters
            if unrelated_clusters:
                add(
                    "outline:claim_cluster_binding",
                    f"paragraph clusters are unrelated to its assigned claims: {sorted(unrelated_clusters)}",
                    path,
                )
            paragraph_sources = set(paragraph.get("source_ids", []))
            derived_paragraph_sources: set[str] = set()
            for claim_id in paragraph.get("claim_ids", []):
                if claim_id in claims:
                    derived_paragraph_sources.update(claims[claim_id].get("source_ids", []))
            if paragraph_sources != derived_paragraph_sources:
                add("outline:paragraph_sources", "paragraph source_ids do not equal assigned claim sources", path)
            outline_sources.update(paragraph_sources)
            for field, valid in (
                ("conflict_ids", set(conflicts)), ("limitation_ids", set(limitations)), ("gap_ids", set(gaps)),
            ):
                if set(paragraph.get(field, [])) - valid:
                    add("outline:record_ref", f"paragraph {field} contains unknown IDs", path)

    if set(outline.get("placed_conflict_ids", [])) != set(conflicts):
        add("outline:conflict_coverage", "all conflict records must be explicitly placed", "$.outline.placed_conflict_ids")
    if set(outline.get("placed_limitation_ids", [])) != set(limitations):
        add("outline:limitation_coverage", "all limitation records must be explicitly placed", "$.outline.placed_limitation_ids")
    if set(outline.get("placed_gap_ids", [])) != set(gaps):
        add("outline:gap_coverage", "all gap records must be explicitly placed", "$.outline.placed_gap_ids")
    outline_audit = outline.get("source_coverage_audit", {})
    outline_unassigned = {item.get("source_id") for item in outline_audit.get("unassigned_sources", [])}
    if set(outline_audit.get("included_source_ids", [])) != included_sources:
        add("coverage:outline_included", "outline coverage included_source_ids do not match registry", "$.outline.source_coverage_audit")
    if set(outline_audit.get("assigned_source_ids", [])) != outline_sources:
        add("coverage:outline_assigned", "outline assigned_source_ids do not match paragraph assignments", "$.outline.source_coverage_audit")
    if outline_sources & outline_unassigned or outline_sources | outline_unassigned != included_sources:
        add("coverage:outline_partition", "outline assigned/unassigned sources do not exactly partition admitted sources", "$.outline.source_coverage_audit")
    if outline.get("status") == "author_approved":
        outline_refs = outline.get("decision_refs", [])
        outline_ref = next((
            ref for ref in outline_refs
            if decisions.get(ref.get("decision_id"), {}).get("decision_type") == "outline_decision"
        ), None)
        require_decision(
            outline_ref, "outline_decision", "review_outline", outline.get("artifact_id", ""),
            "approved", "$.outline.decision_refs",
            outline.get("schema_version", ""), governed_subject_sha256(outline), author_only=True,
        )
    if outline.get("terminal_state") != "ready_for_author_review":
        add("terminal:state", "Phase 7A terminal state must be ready_for_author_review", "$.outline.terminal_state")

    return issues


def _parse_trusted_inputs(values: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for value in values:
        if "=" not in value:
            raise PackageValidationError(f"trusted input must use input_id=path: {value}")
        input_id, raw_path = value.split("=", 1)
        path = Path(raw_path).resolve()
        if not input_id or not path.is_file():
            raise PackageValidationError(f"trusted input is invalid: {value}")
        if input_id in result:
            raise PackageValidationError(f"duplicate trusted input ID: {input_id}")
        result[input_id] = {"path": path, "sha256": file_sha256(path)}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--source-registry", type=Path, required=True)
    parser.add_argument("--extractions", type=Path, required=True, help="JSON array of review_extraction_record values")
    parser.add_argument("--authority-bundle", type=Path, required=True)
    parser.add_argument("--authority-manifest-sha256", required=True)
    parser.add_argument("--synthesis-matrix", type=Path, required=True)
    parser.add_argument("--outline", type=Path, required=True)
    parser.add_argument("--trusted-input", action="append", default=[], help="Repeat input_id=path")
    parser.add_argument("--schemas-dir", type=Path, default=DEFAULT_SCHEMAS)
    parser.add_argument("--validator", type=Path, default=DEFAULT_VALIDATOR)
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args()
    try:
        scope = read_json(args.scope)
        registry = read_json(args.source_registry)
        extractions = read_json(args.extractions)
        authority_bundle = read_json(args.authority_bundle)
        synthesis = read_json(args.synthesis_matrix)
        outline = read_json(args.outline)
        if not isinstance(extractions, list):
            raise PackageValidationError("extractions input must be a JSON array")
        trusted_inputs = _parse_trusted_inputs(args.trusted_input)
        issues = validate_schema_layer(
            scope, registry, extractions, authority_bundle, synthesis, outline,
            args.schemas_dir, args.validator,
        )
        issues.extend(validate_review_package(
            scope, registry, extractions, authority_bundle, args.authority_manifest_sha256,
            synthesis, outline, trusted_inputs,
        ))
    except (OSError, json.JSONDecodeError, PackageValidationError, RuntimeError) as exc:
        print(f"package validation error: {exc}", file=sys.stderr)
        return 2
    result = {
        "valid": not issues,
        "terminal_state": "ready_for_author_review" if not issues else "invalid",
        "issue_count": len(issues),
        "issues": issues,
    }
    if args.json_report:
        write_json(args.json_report, result)
    if issues:
        for issue in issues:
            print(f"{issue['layer']} {issue['path']} [{issue['code']}] {issue['message']}")
        return 1
    print("Phase 7A review package valid; terminal_state=ready_for_author_review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
