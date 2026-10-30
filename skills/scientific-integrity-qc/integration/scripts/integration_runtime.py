#!/usr/bin/env python3
"""Deterministic Module 06 integration runtime for Article, Review, and Figure routes."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


INTEGRATION_VERSION = "0.1.1"
CONTRACT_VERSION = "0.1.2"
CONTRACT_SHA256 = "7528d3e23d95479faeee2ef11955ed5ad06fa4f4853adea9ca5d55cbcfe45fc4"
REGISTRY_SHA256 = "2a29111dbafe41d3cb704df404858859a4a9b445929a0bf91e3490966e3a76e6"
ZERO_HASH = "0" * 64

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
CORE_ROOT = PACKAGE_ROOT / "frozen-core"
VENDOR_ROOT = PACKAGE_ROOT / "vendor"
CONTRACT_ROOT = PACKAGE_ROOT / "integration-contract"
INTEGRATION_SCHEMA_ROOT = PACKAGE_ROOT / "integration" / "schemas"
CORE_SCHEMA_ROOT = PACKAGE_ROOT / "frozen-core" / "schemas"
SHARED_VALIDATOR_PATH = PACKAGE_ROOT / "shared-core" / "scripts" / "validate_artifact.py"

PRODUCER_PATHS = {
    "article_revision": VENDOR_ROOT / "m03",
    "review_revision": VENDOR_ROOT / "m04",
    "figure_qc": VENDOR_ROOT / "m05",
}

BASE_DOMAINS = {
    "article_revision": "text_preservation",
    "review_revision": "text_preservation",
    "figure_qc": "identity_state_handoff_closure",
}

_SCHEMA_VALIDATOR: Any | None = None


class IntegrationError(RuntimeError):
    """Fail-closed error carrying a stable reviewable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha_bytes(encoded)


def payload_sha256(value: dict[str, Any], field: str) -> str:
    return canonical_sha256({key: item for key, item in value.items() if key != field})


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_schema_value(value: Any, schema_path: Path) -> list[str]:
    """Run the inventory-pinned dependency-free schema validator on an in-memory value."""

    global _SCHEMA_VALIDATOR
    try:
        if _SCHEMA_VALIDATOR is None:
            spec = importlib.util.spec_from_file_location("module06_shared_schema_validator", SHARED_VALIDATOR_PATH)
            if spec is None or spec.loader is None:
                raise RuntimeError("cannot load package-local shared schema validator")
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            _SCHEMA_VALIDATOR = module
        store = _SCHEMA_VALIDATOR.SchemaStore()
        schema = store.load(schema_path.resolve())
        issues = _SCHEMA_VALIDATOR.validate_instance(value, schema, schema_path.resolve(), schema, store)
        return [f"{item.path} [{item.keyword}] {item.message}" for item in issues]
    except Exception as exc:  # an unsupported schema must fail closed
        return [f"schema runtime failure for {schema_path.name}: {type(exc).__name__}: {exc}"]


def _safe_timestamp(value: Any) -> str:
    if isinstance(value, str):
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            if "T" in value:
                return value
        except ValueError:
            pass
    return "1970-01-01T00:00:00Z"


def _safe_text(value: Any, fallback: str) -> str:
    return value if isinstance(value, str) and value else fallback


def _safe_identifier(value: Any, fallback: str) -> str:
    """Keep generated artifact identifiers schema-valid for rejected requests."""
    if isinstance(value, str) and len(value) <= 120 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]+", value):
        return value
    return fallback


def contained_path(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise IntegrationError("path:absolute", f"absolute path is not allowed in an admission request: {relative}")
    resolved_root = root.resolve()
    resolved = (resolved_root / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise IntegrationError("path:escape", f"path escapes invocation root: {relative}") from exc
    if not resolved.is_file():
        raise IntegrationError("path:missing", f"required artifact is missing: {relative}")
    return resolved


def contained_directory(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise IntegrationError("path:absolute", f"absolute directory is not allowed: {relative}")
    resolved_root = root.resolve()
    resolved = (resolved_root / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise IntegrationError("path:escape", f"directory escapes invocation root: {relative}") from exc
    if not resolved.is_dir():
        raise IntegrationError("path:missing", f"required directory is missing: {relative}")
    return resolved


def canonical_self_hash(value: dict[str, Any], field: str) -> str:
    return canonical_sha256({key: item for key, item in value.items() if key != field})


def _figure_qc_matches_fresh(supplied: dict[str, Any], fresh: dict[str, Any]) -> bool:
    """Compare repeatable QC content while preserving the producer's timestamped self-hash."""

    claimed = supplied.get("figure_qc_sha256")
    if not isinstance(claimed, str) or payload_sha256(supplied, "figure_qc_sha256") != claimed:
        return False
    volatile = {"generated_at", "figure_qc_sha256"}
    supplied_repeatable = {key: value for key, value in supplied.items() if key not in volatile}
    fresh_repeatable = {key: value for key, value in fresh.items() if key not in volatile}
    return canonical_sha256(supplied_repeatable) == canonical_sha256(fresh_repeatable)


def verify_inventory(package_root: Path, expected_file_sha256: str | None = None) -> dict[str, Any]:
    """Verify a package inventory, its canonical self-hash, and its exact file set."""

    inventory_path = package_root / "package-inventory.json"
    if not inventory_path.is_file():
        raise IntegrationError("package:inventory_missing", f"package inventory missing: {package_root}")
    if expected_file_sha256 and file_sha256(inventory_path) != expected_file_sha256:
        raise IntegrationError("package:inventory_file_hash", "package inventory file SHA-256 mismatch")
    inventory = read_json(inventory_path)
    if canonical_self_hash(inventory, "package_manifest_sha256") != inventory.get("package_manifest_sha256"):
        raise IntegrationError("package:self_hash", "package inventory canonical self-hash mismatch")
    expected = {item["path"]: item for item in inventory.get("files", [])}
    actual = {
        path.relative_to(package_root).as_posix(): path
        for path in package_root.rglob("*")
        if path.is_file()
        and path != inventory_path
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    }
    if set(actual) != set(expected):
        raise IntegrationError("package:file_set", "package file set does not match its inventory")
    for name, path in actual.items():
        record = expected[name]
        if path.stat().st_size != record.get("size_bytes") or file_sha256(path) != record.get("sha256"):
            raise IntegrationError("package:file_hash", f"package payload mismatch: {name}")
    return inventory


def load_contract_registry() -> dict[str, Any]:
    contract_path = CONTRACT_ROOT / "MODULE06_ARTICLE_REVIEW_FIGURE_INTEGRATION_CONTRACT.md"
    registry_path = CONTRACT_ROOT / "module06-integration-interface-registry.json"
    if file_sha256(contract_path) != CONTRACT_SHA256 or file_sha256(registry_path) != REGISTRY_SHA256:
        raise IntegrationError("contract:hash", "frozen integration contract or registry hash mismatch")
    registry = read_json(registry_path)
    if registry.get("contract_version") != CONTRACT_VERSION:
        raise IntegrationError("contract:version", "unexpected integration contract version")
    return registry


def _payload_identity(value: dict[str, Any], artifact_class: str) -> tuple[str, str, str | None]:
    id_keys = (
        "artifact_id", "revision_contract_id", "permission_id", "proposal_id", "manifest_id",
        "query_list_id", "receipt_id", "validation_result_id", "inventory_id", "profile_id",
        "plan_id", "execution_id", "execution_result_id", "render_manifest_id", "inspection_id",
        "trust_root_id",
    )
    version_keys = (
        "artifact_version", "revision_contract_version", "permission_version", "schema_version",
        "lineage_map_version", "inventory_version", "record_version", "interface_version",
    )
    identity = next((value[key] for key in id_keys if isinstance(value.get(key), str) and value[key]), None)
    if identity is None:
        identity = f"{artifact_class}:{canonical_sha256(value)[:24]}"
    version = next((value[key] for key in version_keys if isinstance(value.get(key), str) and value[key]), None)
    if version is None and artifact_class == "referenced_phase7a_closure":
        version = "phase7a.1-0.1.1"
    if version is None:
        raise IntegrationError("artifact:version", f"artifact has no extractable version: {artifact_class}")
    status_keys = ("status", "producer_state", "readiness_gate", "terminal_state", "authorization_state")
    status = next((value[key] for key in status_keys if isinstance(value.get(key), str)), None)
    return identity, version, status


def describe_artifact(path: Path, artifact_class: str, *, phase: str | None = None, authority: bool = False) -> dict[str, Any]:
    value = read_json(path)
    identity, version, status = _payload_identity(value, artifact_class)
    record: dict[str, Any] = {
        "artifact_class": artifact_class,
        "path": path.name,
        "file_sha256": file_sha256(path),
        "canonical_sha256": canonical_sha256(value),
        "artifact_id": identity,
        "artifact_version": version,
    }
    if phase:
        record["phase"] = phase
    if status:
        record["status"] = status
    if authority:
        record["caller_expected_file_sha256"] = record["file_sha256"]
    return record


class ArtifactIndex:
    """Loaded, hash-checked invocation artifacts indexed by class and optional phase."""

    def __init__(self, request: dict[str, Any], invocation_root: Path) -> None:
        self.root = invocation_root.resolve()
        self.records: list[dict[str, Any]] = []
        self.values: dict[int, dict[str, Any]] = {}
        seen_paths: set[Path] = set()
        seen_keys: set[tuple[str, str | None, str]] = set()
        for record in request.get("artifacts", []):
            if not isinstance(record, dict):
                raise IntegrationError("artifact:shape", "each artifact descriptor must be an object")
            path = contained_path(self.root, record.get("path", ""))
            if path in seen_paths:
                raise IntegrationError("artifact:duplicate_path", f"duplicate artifact path: {record.get('path')}")
            seen_paths.add(path)
            if file_sha256(path) != record.get("file_sha256"):
                raise IntegrationError("artifact:file_hash", f"artifact file SHA-256 mismatch: {record.get('path')}")
            value = read_json(path)
            if canonical_sha256(value) != record.get("canonical_sha256"):
                raise IntegrationError("artifact:canonical_hash", f"artifact canonical SHA-256 mismatch: {record.get('path')}")
            artifact_class = record.get("artifact_class")
            if not isinstance(artifact_class, str) or not artifact_class:
                raise IntegrationError("artifact:class", "artifact_class must be non-empty")
            identity, version, status = _payload_identity(value, artifact_class)
            if record.get("artifact_id") != identity or record.get("artifact_version") != version:
                raise IntegrationError("artifact:identity", f"artifact identity/version mismatch: {record.get('path')}")
            if "status" in record and record.get("status") != status:
                raise IntegrationError("artifact:status", f"artifact status mismatch: {record.get('path')}")
            expected = record.get("caller_expected_file_sha256")
            if expected is not None and expected != file_sha256(path):
                raise IntegrationError("artifact:caller_hash", f"caller-held artifact hash mismatch: {record.get('path')}")
            key = (artifact_class, record.get("phase"), identity)
            if key in seen_keys:
                raise IntegrationError("artifact:duplicate_identity", f"duplicate artifact identity: {identity}")
            seen_keys.add(key)
            loaded = dict(record)
            loaded["resolved_path"] = path
            self.records.append(loaded)
            self.values[id(loaded)] = value

    def many(self, artifact_class: str, phase: str | None = None) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        matches = [
            record for record in self.records
            if record["artifact_class"] == artifact_class and (phase is None or record.get("phase") == phase)
        ]
        return [(record, self.values[id(record)]) for record in matches]

    def one(self, artifact_class: str, phase: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        matches = self.many(artifact_class, phase)
        if len(matches) != 1:
            suffix = f" phase={phase}" if phase else ""
            raise IntegrationError("closure:cardinality", f"expected exactly one {artifact_class}{suffix}; got {len(matches)}")
        return matches[0]


def _validate_class_set(index: ArtifactIndex, required: dict[tuple[str, str | None], tuple[int, int]], allowed: set[tuple[str, str | None]]) -> None:
    actual = Counter((record["artifact_class"], record.get("phase")) for record in index.records)
    for key, (minimum, maximum) in required.items():
        count = actual.get(key, 0)
        if count < minimum or count > maximum:
            raise IntegrationError("closure:cardinality", f"invalid count for {key}: {count}")
    extras = sorted(key for key in actual if key not in allowed)
    if extras:
        raise IntegrationError("closure:extra", f"unsupported artifact classes supplied: {extras}")


def _require_authority_hash(index: ArtifactIndex, artifact_class: str, phase: str | None = None) -> None:
    record, _ = index.one(artifact_class, phase)
    if record.get("caller_expected_file_sha256") != record.get("file_sha256"):
        raise IntegrationError("authority:caller_hash", f"caller-held hash is required for {artifact_class}")


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(command, text=True, capture_output=True, env=environment, check=False)


def _producer_identity(request: dict[str, Any], registry: dict[str, Any], route: str) -> tuple[Path, dict[str, Any]]:
    route_record = next(item for item in registry["interfaces"] if item.get("route") == route)
    producer = request.get("producer", {})
    baseline = next(
        item for item in registry["frozen_baselines"]["producer_packages"]
        if item["skill_name"] == route_record["producer_skill"]
    )
    expected = {
        "skill_name": route_record["producer_skill"],
        "skill_package_version": baseline["skill_package_version"],
        "package_manifest_sha256": baseline["package_manifest_sha256"],
        "producer_interface": route_record["producer_interface"],
        "producer_interface_version": route_record["producer_interface_version"],
    }
    if any(producer.get(key) != value for key, value in expected.items()):
        raise IntegrationError("producer:identity", "producer package/interface identity mismatch")
    if producer.get("expected_inventory_file_sha256") != baseline["inventory_file_sha256"]:
        raise IntegrationError("producer:caller_inventory_hash", "caller-held producer inventory hash mismatch")
    if "build_generation" in baseline and producer.get("build_generation") != baseline["build_generation"]:
        raise IntegrationError("producer:build_generation", "producer build generation mismatch")
    package_root = PRODUCER_PATHS[route]
    inventory = verify_inventory(package_root, baseline["inventory_file_sha256"])
    if inventory.get("skill_name") != expected["skill_name"] or inventory.get("skill_package_version") != expected["skill_package_version"]:
        raise IntegrationError("producer:inventory_identity", "vendored producer inventory identity mismatch")
    if inventory.get("package_manifest_sha256") != expected["package_manifest_sha256"]:
        raise IntegrationError("producer:manifest_hash", "vendored producer manifest hash mismatch")
    interfaces = {(item.get("direction"), item.get("name"), item.get("version")) for item in inventory.get("supported_interfaces", [])}
    if ("output", expected["producer_interface"], expected["producer_interface_version"]) not in interfaces:
        raise IntegrationError("producer:interface", "vendored producer does not expose required output interface")
    return package_root, route_record


def _article_validation(index: ArtifactIndex, package_root: Path) -> dict[str, Any]:
    required = {
        ("source_document", None): (1, 1), ("candidate_document", None): (1, 1),
        ("change_manifest", None): (1, 1), ("author_query_list", None): (1, 1),
        ("revision_lineage_map", None): (1, 1), ("article_polisher_change_inventory", None): (1, 1),
        ("article_polisher_patch_application_receipt", None): (1, 1), ("revision_contract", None): (1, 1),
    }
    allowed = set(required) | {("upstream_artifact", None)}
    _validate_class_set(index, required, allowed)
    _require_authority_hash(index, "revision_contract")
    source_record, source = index.one("source_document")
    candidate_record, candidate = index.one("candidate_document")
    if source.get("document_type") != "original_article" or candidate.get("document_type") != "original_article":
        raise IntegrationError("route:document_type", "Article route requires original_article source and candidate")
    if source.get("document_id") != candidate.get("document_id"):
        raise IntegrationError("identity:document", "Article source/candidate document identity mismatch")
    _, change_manifest = index.one("change_manifest")
    required_upstream_ids = {
        reference["artifact_id"]
        for change in change_manifest.get("changes", [])
        if isinstance(change, dict)
        for reference in change.get("upstream_artifact_refs", [])
        if isinstance(reference, dict) and isinstance(reference.get("artifact_id"), str)
    }
    supplied_upstream_ids = {
        record["artifact_id"] for record, _ in index.many("upstream_artifact")
    }
    missing_upstream_ids = sorted(required_upstream_ids - supplied_upstream_ids)
    if missing_upstream_ids:
        raise IntegrationError(
            "closure:upstream_missing",
            f"referenced Article upstream artifacts were not supplied: {missing_upstream_ids}",
        )
    extra_upstream_ids = sorted(supplied_upstream_ids - required_upstream_ids)
    if extra_upstream_ids:
        raise IntegrationError(
            "closure:upstream_extra",
            f"unreferenced Article upstream artifacts were supplied: {extra_upstream_ids}",
        )
    lineage_record, lineage = index.one("revision_lineage_map")
    if lineage.get("origin") != "deterministic_patch_layer":
        raise IntegrationError("lineage:origin", "Article lineage must originate from deterministic_patch_layer")
    receipt_record, receipt = index.one("article_polisher_patch_application_receipt")
    if receipt.get("lineage_origin") != "deterministic_patch_layer" or receipt.get("terminal_state") != "ready_for_package_validation":
        raise IntegrationError("receipt:state", "Article patch receipt is not ready or deterministic")
    if receipt.get("author_approval_claimed") is not False or receipt.get("scientific_safety_claimed") is not False:
        raise IntegrationError("receipt:authority", "Article patch receipt claims prohibited authority")
    with tempfile.TemporaryDirectory(prefix="m06-a-") as raw:
        temporary = Path(raw)
        fresh_inventory = temporary / "fresh-inventory.json"
        fresh_report = temporary / "fresh-validation.json"
        command = [
            sys.executable, "-B", str(package_root / "scripts" / "validate_revision_package.py"),
            "--source-document", str(source_record["resolved_path"]),
            "--candidate-document", str(candidate_record["resolved_path"]),
            "--lineage-map", str(lineage_record["resolved_path"]),
            "--revision-contract", str(index.one("revision_contract")[0]["resolved_path"]),
            "--change-manifest", str(index.one("change_manifest")[0]["resolved_path"]),
            "--author-queries", str(index.one("author_query_list")[0]["resolved_path"]),
            "--write-inventory", str(fresh_inventory), "--json-report", str(fresh_report),
        ]
        for record, _ in index.many("upstream_artifact"):
            command.extend(["--upstream-artifact", str(record["resolved_path"])])
        completed = _run(command)
        if completed.returncode != 0 or not fresh_report.is_file():
            raise IntegrationError("producer:validation", f"fresh Module 03 validation failed: {completed.stdout}{completed.stderr}".strip())
        report = read_json(fresh_report)
        if report.get("valid") is not True or report.get("ready_for_independent_qc") is not True:
            raise IntegrationError("producer:state", "Module 03 producer is not ready_for_independent_qc")
        _, supplied_inventory = index.one("article_polisher_change_inventory")
        if read_json(fresh_inventory) != supplied_inventory:
            raise IntegrationError("producer:inventory_rebuild", "fresh Module 03 inventory differs from supplied inventory")
    queries = index.one("author_query_list")[1]
    blocking_queries = [
        item for item in queries.get("queries", [])
        if item.get("blocks_revision") is True and item.get("resolution_status") == "unresolved"
    ]
    return {
        "source": source, "candidate": candidate, "lineage": lineage,
        "revision_contract": index.one("revision_contract")[1],
        "blocking_queries": blocking_queries,
    }


def _review_validation(index: ArtifactIndex, package_root: Path, request: dict[str, Any]) -> dict[str, Any]:
    required = {
        ("source_document", None): (1, 1), ("candidate_document", None): (1, 1),
        ("review_revision_permission", None): (1, 1), ("review_revision_proposal", None): (1, 1),
        ("review_change_manifest", None): (1, 1), ("review_author_query_list", None): (1, 1),
        ("review_revision_lineage_map", None): (1, 1), ("review_protected_change_inventory", None): (1, 1),
        ("review_patch_application_receipt", None): (1, 1), ("review_package_validation_result", None): (1, 1),
        ("referenced_phase7a_closure", None): (1, 1),
    }
    allowed = set(required) | {("review_profile", None)}
    _validate_class_set(index, required, allowed)
    _require_authority_hash(index, "review_revision_permission")
    _require_authority_hash(index, "referenced_phase7a_closure")
    source_record, source = index.one("source_document")
    candidate_record, candidate = index.one("candidate_document")
    if source.get("document_type") != "review_article" or candidate.get("document_type") != "review_article":
        raise IntegrationError("route:document_type", "Review route requires review_article source and candidate")
    if source.get("manuscript_id") != candidate.get("manuscript_id"):
        raise IntegrationError("identity:manuscript", "Review source/candidate manuscript identity mismatch")
    lineage_record, lineage = index.one("review_revision_lineage_map")
    if lineage.get("origin") != "deterministic_patch_layer":
        raise IntegrationError("lineage:origin", "Review lineage must originate from deterministic_patch_layer")
    expected_permission = request.get("producer_validation", {}).get("expected_permission_sha256")
    permission = index.one("review_revision_permission")[1]
    if expected_permission != permission.get("permission_sha256"):
        raise IntegrationError("authority:permission_hash", "caller-held permission payload SHA-256 mismatch")
    with tempfile.TemporaryDirectory(prefix="m06-r-") as raw:
        fresh_report = Path(raw) / "fresh-validation.json"
        command = [
            sys.executable, "-B", str(package_root / "scripts" / "validate_review_revision_package.py"),
            "--source-document", str(source_record["resolved_path"]),
            "--candidate-document", str(candidate_record["resolved_path"]),
            "--permission", str(index.one("review_revision_permission")[0]["resolved_path"]),
            "--expected-permission-sha256", expected_permission,
            "--proposal", str(index.one("review_revision_proposal")[0]["resolved_path"]),
            "--change-manifest", str(index.one("review_change_manifest")[0]["resolved_path"]),
            "--author-query-list", str(index.one("review_author_query_list")[0]["resolved_path"]),
            "--lineage-map", str(lineage_record["resolved_path"]),
            "--protected-inventory", str(index.one("review_protected_change_inventory")[0]["resolved_path"]),
            "--phase7a-package", str(index.one("referenced_phase7a_closure")[0]["resolved_path"]),
            "--application-receipt", str(index.one("review_patch_application_receipt")[0]["resolved_path"]),
            "--package-validation-result", str(index.one("review_package_validation_result")[0]["resolved_path"]),
            "--json-report", str(fresh_report),
        ]
        profiles = index.many("review_profile")
        if profiles:
            command.extend(["--review-profile", str(profiles[0][0]["resolved_path"])])
        completed = _run(command)
        if completed.returncode != 0 or not fresh_report.is_file():
            raise IntegrationError("producer:validation", f"fresh Module 04 validation failed: {completed.stdout}{completed.stderr}".strip())
        report = read_json(fresh_report)
        if report.get("valid") is not True or report.get("producer_state") != "ready_for_independent_qc":
            raise IntegrationError("producer:state", "Module 04 producer is not ready_for_independent_qc")
    queries = index.one("review_author_query_list")[1]
    blocking_queries = [
        item for item in queries.get("queries", [])
        if item.get("blocks_revision") is True and item.get("status") == "unresolved"
    ]
    return {
        "source": source, "candidate": candidate, "lineage": lineage,
        "revision_contract": None, "blocking_queries": blocking_queries,
    }


def _figure_required(variant: str) -> tuple[dict[tuple[str, str | None], tuple[int, int]], set[tuple[str, str | None]]]:
    required = {
        ("design_package_manifest", None): (1, 1), ("source_data_manifest", None): (1, 1),
        ("figure_card", None): (1, 1000), ("figure_contract", None): (1, 1000),
        ("plot_recipe", None): (1, 1000), ("trusted_inputs_root", None): (1, 1),
        ("figure_qc", "phase8a"): (1, 1),
    }
    if variant == "phase8b_prototype":
        required.update({
            ("phase8a_admission_receipt", None): (1, 1),
            ("backend_environment_profile", None): (1, 1),
            ("bounded_program_plan", None): (1, 1),
            ("prototype_execution_manifest", None): (1, 1),
            ("prototype_execution_authorization", None): (1, 1),
            ("prototype_execution_result", None): (1, 1),
            ("render_output_manifest", None): (1, 1),
            ("render_inspection_record", None): (1, 1000),
            ("figure_qc", "phase8b"): (1, 1),
        })
    return required, set(required)


def _figure_validation(index: ArtifactIndex, package_root: Path, request: dict[str, Any]) -> dict[str, Any]:
    validation = request.get("producer_validation", {})
    variant = validation.get("variant")
    if variant not in {"phase8a_design", "phase8b_prototype"}:
        raise IntegrationError("figure:variant", "unsupported Figure admission variant")
    required, allowed = _figure_required(variant)
    _validate_class_set(index, required, allowed)
    _require_authority_hash(index, "trusted_inputs_root")
    phase8a_root = contained_directory(index.root, validation.get("phase8a_package_root", ""))
    manifest_record, manifest = index.one("design_package_manifest")
    if manifest_record["resolved_path"] != (phase8a_root / "design-package-manifest.json").resolve():
        raise IntegrationError("closure:figure_manifest", "supplied design_package_manifest is not the validated Phase 8A root manifest")

    def component_paths(name: str) -> set[Path]:
        raw = manifest.get("components", {}).get(name)
        records = raw if isinstance(raw, list) else [raw]
        if not records or any(not isinstance(item, dict) or not isinstance(item.get("path"), str) for item in records):
            raise IntegrationError("closure:figure_components", f"invalid design-manifest component set: {name}")
        return {(phase8a_root / item["path"]).resolve() for item in records}

    exact_components = {
        "source_data_manifest": component_paths("source_data_manifest"),
        "figure_card": component_paths("figure_cards"),
        "figure_contract": component_paths("figure_contracts"),
        "plot_recipe": component_paths("plot_recipes"),
    }
    for artifact_class, expected_paths in exact_components.items():
        supplied_paths = {record["resolved_path"] for record, _ in index.many(artifact_class)}
        if supplied_paths != expected_paths:
            raise IntegrationError("closure:figure_components", f"supplied {artifact_class} set differs from the exact design manifest")
    trust_record, _ = index.one("trusted_inputs_root")
    expected_trust_hash = validation.get("expected_trust_root_sha256")
    if expected_trust_hash != trust_record.get("caller_expected_file_sha256"):
        raise IntegrationError("authority:trust_hash", "caller-held Figure trust-root hash mismatch")
    if variant == "phase8a_design":
        command = [
            sys.executable, "-B", str(package_root / "candidate" / "scripts" / "validate_figure_package.py"),
            str(phase8a_root), "--trust-root", str(trust_record["resolved_path"]),
            "--trust-root-sha256", expected_trust_hash,
        ]
        completed = _run(command)
        if completed.returncode != 0:
            raise IntegrationError("producer:validation", f"fresh Phase 8A validation failed: {completed.stdout}{completed.stderr}".strip())
        fresh = json.loads(completed.stdout)
        supplied_qc = index.one("figure_qc", "phase8a")[1]
        if fresh.get("valid") is not True or not _figure_qc_matches_fresh(supplied_qc, fresh.get("qc", {})):
            raise IntegrationError("producer:figure_qc", "fresh Phase 8A QC differs from supplied Figure QC")
        readiness = supplied_qc.get("readiness_gate")
        if readiness not in {"pass_for_declared_maturity", "author_review_required"}:
            raise IntegrationError("producer:state", f"Phase 8A readiness not admissible: {readiness}")
        admission_state = "accepted_degraded" if readiness == "author_review_required" else "accepted"
        return {"variant": variant, "admission_state": admission_state, "producer_qc": supplied_qc}

    _require_authority_hash(index, "prototype_execution_authorization")
    phase8a_qc = index.one("figure_qc", "phase8a")[1]
    auth_record, _ = index.one("prototype_execution_authorization")
    command = [
        sys.executable, "-B", str(package_root / "phase8b-candidate" / "scripts" / "validate_phase8b_package.py"),
        str(phase8a_root), "--trust-root", str(trust_record["resolved_path"]),
        "--trust-root-sha256", expected_trust_hash,
        "--design-package-hash", validation.get("expected_design_package_hash", ""),
        "--phase8a-qc-sha256", phase8a_qc.get("figure_qc_sha256", ""),
        "--phase8a-qc-artifact-id", phase8a_qc.get("artifact_id", ""),
        "--phase8a-qc-schema-version", phase8a_qc.get("schema_version", ""),
        "--admission-receipt", str(index.one("phase8a_admission_receipt")[0]["resolved_path"]),
        "--profile", str(index.one("backend_environment_profile")[0]["resolved_path"]),
        "--plan", str(index.one("bounded_program_plan")[0]["resolved_path"]),
        "--execution-manifest", str(index.one("prototype_execution_manifest")[0]["resolved_path"]),
        "--authorization", str(auth_record["resolved_path"]),
        "--authorization-file-sha256", auth_record["caller_expected_file_sha256"],
        "--execution-result", str(index.one("prototype_execution_result")[0]["resolved_path"]),
        "--render-manifest", str(index.one("render_output_manifest")[0]["resolved_path"]),
    ]
    for record, _ in index.many("render_inspection_record"):
        command.extend(["--inspection", str(record["resolved_path"])])
    completed = _run(command)
    if completed.returncode != 0:
        raise IntegrationError("producer:validation", f"fresh Phase 8B validation failed: {completed.stdout}{completed.stderr}".strip())
    fresh = json.loads(completed.stdout)
    supplied_qc = index.one("figure_qc", "phase8b")[1]
    if fresh.get("valid") is not True or not _figure_qc_matches_fresh(supplied_qc, fresh.get("qc", {})):
        raise IntegrationError("producer:figure_qc", "fresh Phase 8B QC differs from supplied Figure QC")
    readiness = supplied_qc.get("readiness_gate")
    if readiness not in {"prepared_for_future_figure_qc", "author_review_required"}:
        raise IntegrationError("producer:state", f"Phase 8B readiness not admissible: {readiness}")
    if supplied_qc.get("maturity") == "prototype_generated_unverified":
        admission_state = "accepted_degraded"
    else:
        admission_state = "accepted_degraded" if readiness == "author_review_required" else "accepted"
    return {"variant": variant, "admission_state": admission_state, "producer_qc": supplied_qc}


def _validate_request_shape(request: dict[str, Any], route_record: dict[str, Any]) -> None:
    if request.get("schema_name") != "module06_integration_admission_request" or request.get("schema_version") != "0.1.0":
        raise IntegrationError("request:identity", "unsupported admission request schema")
    if request.get("consumer_interface") != route_record["consumer_interface"] or request.get("consumer_interface_version") != route_record["consumer_interface_version"]:
        raise IntegrationError("request:consumer_interface", "consumer admission interface mismatch")
    claims = request.get("claims", {})
    if claims != {"admission_passed": False, "scientific_truth_claimed": False, "author_approval_claimed": False}:
        raise IntegrationError("request:authority", "admission request contains prohibited or incomplete authority claims")
    domains = request.get("requested_domains")
    if not isinstance(domains, list) or not domains or len(domains) != len(set(domains)) or not all(isinstance(item, str) and item for item in domains):
        raise IntegrationError("request:domains", "requested_domains must be a non-empty unique string array")
    if BASE_DOMAINS[request["route"]] not in domains:
        raise IntegrationError("request:base_domain", "route-required base domain was not requested")


def validate_admission(
    request: dict[str, Any], invocation_root: Path, registry: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], ArtifactIndex, dict[str, Any], dict[str, Any]]:
    verify_inventory(PACKAGE_ROOT)
    registry = registry or load_contract_registry()
    schema_issues = validate_schema_value(
        request, INTEGRATION_SCHEMA_ROOT / "module06-integration-admission-request.schema.json"
    )
    if schema_issues:
        raise IntegrationError("request:schema", "; ".join(schema_issues[:8]))
    route = request.get("route")
    if route not in PRODUCER_PATHS:
        raise IntegrationError("route:unsupported", f"unsupported route: {route}")
    package_root, route_record = _producer_identity(request, registry, route)
    _validate_request_shape(request, route_record)
    index = ArtifactIndex(request, invocation_root)
    if route == "article_revision":
        context = _article_validation(index, package_root)
        context["admission_state"] = "accepted"
    elif route == "review_revision":
        context = _review_validation(index, package_root, request)
        context["admission_state"] = "accepted"
    else:
        context = _figure_validation(index, package_root, request)
    return registry, index, route_record, context


def _document_units(document: dict[str, Any], expected_type: str, side: str) -> tuple[str, list[dict[str, Any]]]:
    if document.get("document_type") != expected_type or document.get("side") != side:
        raise IntegrationError("projection:route_identity", f"{side} document type/side mismatch")
    document_id = document.get("document_id") if expected_type == "original_article" else document.get("manuscript_id")
    units = document.get("paragraphs") if expected_type == "original_article" else document.get("units")
    if not isinstance(document_id, str) or not isinstance(units, list) or not units:
        raise IntegrationError("projection:shape", f"{side} document has no stable identity or units")
    ids: set[str] = set()
    ordinals: list[int] = []
    for unit in units:
        unit_id = unit.get("unit_id")
        ordinal = unit.get("ordinal")
        text = unit.get("text")
        if not isinstance(unit_id, str) or not unit_id or unit_id in ids:
            raise IntegrationError("projection:unit_id", f"{side} unit identity is missing or duplicated")
        ids.add(unit_id)
        if not isinstance(ordinal, int) or isinstance(ordinal, bool):
            raise IntegrationError("projection:ordinal", f"{side} unit ordinal is invalid")
        ordinals.append(ordinal)
        if not isinstance(text, str):
            raise IntegrationError("projection:text", f"{side} unit text is not a string")
        sentences = unit.get("sentences")
        if isinstance(sentences, list):
            sentence_texts = [sentence.get("text") for sentence in sentences]
            if not all(isinstance(item, str) for item in sentence_texts) or " ".join(sentence_texts) != text:
                raise IntegrationError("projection:sentence_closure", f"{side} unit text differs from its exact sentence closure")
    if ordinals != list(range(1, len(units) + 1)):
        raise IntegrationError("projection:ordinal", f"{side} unit ordinals are not contiguous and ordered")
    return document_id, units


def project_text_pair(route: str, context: dict[str, Any], output_dir: Path, created_at: str) -> tuple[Path, Path, dict[str, Any]]:
    expected_type = "original_article" if route == "article_revision" else "review_article"
    source_id, source_units = _document_units(context["source"], expected_type, "source")
    candidate_id, candidate_units = _document_units(context["candidate"], expected_type, "candidate")
    if source_id != candidate_id:
        raise IntegrationError("projection:document_identity", "source/candidate projection identities differ")
    source_path = output_dir / "source-projection.md"
    candidate_path = output_dir / "candidate-projection.md"
    source_bytes = "\n\n".join(unit["text"] for unit in source_units).encode("utf-8")
    candidate_bytes = "\n\n".join(unit["text"] for unit in candidate_units).encode("utf-8")
    source_path.write_bytes(source_bytes)
    candidate_path.write_bytes(candidate_bytes)

    def side_record(side: str, document: dict[str, Any], units: list[dict[str, Any]], path: Path, raw: bytes) -> dict[str, Any]:
        return {
            "side": side,
            "document_artifact_id": document["artifact_id"],
            "document_artifact_version": document["artifact_version"],
            "document_artifact_sha256": document["artifact_sha256"],
            "projected_path": path.name,
            "projected_file_sha256": sha_bytes(raw),
            "unit_count": len(units),
            "units": [
                {
                    "unit_id": unit["unit_id"], "ordinal": unit["ordinal"],
                    "text_sha256": sha_bytes(unit["text"].encode("utf-8")),
                    "locator": unit.get("locator", {}),
                }
                for unit in units
            ],
        }

    receipt: dict[str, Any] = {
        "schema_name": "structured_text_projection_receipt",
        "schema_version": "0.1.0",
        "projection_id": f"projection:{source_id}",
        "projection_sha256": ZERO_HASH,
        "created_at": created_at,
        "route": route,
        "document_id": source_id,
        "encoding": "utf-8",
        "unit_delimiter": "\\n\\n",
        "normalization_performed": False,
        "source": side_record("source", context["source"], source_units, source_path, source_bytes),
        "candidate": side_record("candidate", context["candidate"], candidate_units, candidate_path, candidate_bytes),
    }
    receipt["projection_sha256"] = payload_sha256(receipt, "projection_sha256")
    write_json(output_dir / "structured-text-projection-receipt.json", receipt)
    return source_path, candidate_path, receipt


def _lineage_alignments(route: str, lineage: dict[str, Any], projection: dict[str, Any], source_snapshot: dict[str, Any], candidate_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    field = "paragraph_lineage" if route == "article_revision" else "unit_lineage"
    entries = lineage.get(field)
    if not isinstance(entries, list):
        raise IntegrationError("projection:lineage", f"missing {field}")
    source_receipt = {item["unit_id"]: item for item in projection["source"]["units"]}
    candidate_receipt = {item["unit_id"]: item for item in projection["candidate"]["units"]}
    source_snapshot_by_ordinal = {item["ordinal"]: item for item in source_snapshot["units"]}
    candidate_snapshot_by_ordinal = {item["ordinal"]: item for item in candidate_snapshot["units"]}
    source_use = Counter(source_id for entry in entries for source_id in entry.get("source_unit_ids", []))
    candidate_seen: set[str] = set()
    alignments: list[dict[str, Any]] = []
    for position, entry in enumerate(entries, start=1):
        candidate_id = entry.get("candidate_unit_id")
        source_ids = entry.get("source_unit_ids")
        if candidate_id not in candidate_receipt or candidate_id in candidate_seen or not isinstance(source_ids, list):
            raise IntegrationError("projection:lineage", "lineage has unknown/duplicate candidate or invalid source list")
        candidate_seen.add(candidate_id)
        if any(source_id not in source_receipt for source_id in source_ids):
            raise IntegrationError("projection:lineage", "lineage references an unknown source unit")
        candidate_unit = candidate_snapshot_by_ordinal[candidate_receipt[candidate_id]["ordinal"]]
        source_units = [source_snapshot_by_ordinal[source_receipt[source_id]["ordinal"]] for source_id in source_ids]
        if not source_ids:
            relation = "added"
        elif len(source_ids) > 1:
            relation = "merge"
        elif source_use[source_ids[0]] > 1:
            relation = "split"
        elif source_receipt[source_ids[0]]["ordinal"] != candidate_receipt[candidate_id]["ordinal"]:
            relation = "moved"
        else:
            relation = "one_to_one"
        alignments.append({
            "alignment_id": f"lineage-alignment:{position}",
            "source_unit_ids": [item["unit_id"] for item in source_units],
            "candidate_unit_ids": [candidate_unit["unit_id"]],
            "source_locators": [item["locator"] for item in source_units],
            "candidate_locators": [candidate_unit["locator"]],
            "alignment_type": relation,
            "alignment_origin": "producing_skill",
            "review_status": "caller_accepted",
            "execution_support": "supported" if relation == "one_to_one" else "unassessable",
        })
    if candidate_seen != set(candidate_receipt):
        raise IntegrationError("projection:lineage", "lineage does not cover every candidate unit")
    referenced_source = {source_id for entry in entries for source_id in entry.get("source_unit_ids", [])}
    for source_id in source_receipt:
        if source_id not in referenced_source:
            source_unit = source_snapshot_by_ordinal[source_receipt[source_id]["ordinal"]]
            alignments.append({
                "alignment_id": f"lineage-alignment:{len(alignments) + 1}",
                "source_unit_ids": [source_unit["unit_id"]], "candidate_unit_ids": [],
                "source_locators": [source_unit["locator"]], "candidate_locators": [],
                "alignment_type": "removed", "alignment_origin": "producing_skill",
                "review_status": "caller_accepted", "execution_support": "unassessable",
            })
    return alignments


def run_text_qc(route: str, context: dict[str, Any], output_dir: Path, created_at: str) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    scripts = CORE_ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from qc_gate_core import build_manifest, build_snapshot, compare_snapshots, validate_package_semantics  # type: ignore

    source_path, candidate_path, projection = project_text_pair(route, context, output_dir, created_at)
    document_id = projection["document_id"]
    source_snapshot = build_snapshot(source_path, "source", document_id, "source-projection")
    candidate_snapshot = build_snapshot(candidate_path, "candidate", document_id, "candidate-projection")
    manifest = build_manifest(
        source_snapshot, candidate_snapshot,
        # The frozen core schema names Article explicitly and represents other
        # upstream skills through its declared ``other_skill`` category.
        producer="article_polisher" if route == "article_revision" else "other_skill",
        accept_one_to_one=False,
        revision_contract=context.get("revision_contract"),
    )
    manifest["unit_alignments"] = _lineage_alignments(route, context["lineage"], projection, source_snapshot, candidate_snapshot)
    if any(item["execution_support"] == "unassessable" for item in manifest["unit_alignments"]):
        manifest["degraded_modes"] = ["unsupported_lineage_transform"]
    findings, report = compare_snapshots(manifest, source_snapshot, candidate_snapshot)
    semantic_issues = validate_package_semantics(manifest, source_snapshot, candidate_snapshot, findings, report)
    if semantic_issues:
        raise IntegrationError("core:recomputation", "; ".join(semantic_issues))
    write_json(output_dir / "comparison-manifest.json", manifest)
    write_json(output_dir / "source-preservation-snapshot.json", source_snapshot)
    write_json(output_dir / "candidate-preservation-snapshot.json", candidate_snapshot)
    findings_dir = output_dir / "findings"
    findings_dir.mkdir(parents=True, exist_ok=True)
    for position, finding in enumerate(findings, start=1):
        write_json(findings_dir / f"finding-{position:04d}.json", finding)
    write_json(output_dir / "qc-report.json", report)
    return findings, report, projection


def _artifact_refs(index: ArtifactIndex) -> list[dict[str, Any]]:
    return [
        {
            "artifact_class": record["artifact_class"], "phase": record.get("phase"),
            "artifact_id": record["artifact_id"], "artifact_version": record["artifact_version"],
            "file_sha256": record["file_sha256"], "canonical_sha256": record["canonical_sha256"],
            "path": record["path"],
        }
        for record in index.records
    ]


def _finding(
    request: dict[str, Any], code: str, message: str, *, severity: str = "blocker",
    check_id: str = "module06_integration_admission", evidence: list[str] | None = None,
) -> dict[str, Any]:
    created_at = _safe_timestamp(request.get("created_at"))
    request_id = _safe_identifier(request.get("request_id"), "unknown")
    return {
        "schema_name": "qc-finding", "schema_version": "0.3.0",
        "artifact_id": f"finding:{request_id}:{code}",
        "created_at": created_at, "created_by": "scientific-integrity-qc/integration-0.1.0",
        "source_artifact_ids": [], "status": "author_review_required", "warnings": [],
        "finding_id": f"finding:{request_id}:{code}",
        "check_id": check_id, "finding_class": "identity" if "identity" in code or "hash" in code else "execution",
        "severity": severity, "message": message, "evidence": evidence or [code],
        "execution_state": "failed", "finding_status": "open",
    }


def _blocking_query_findings(request: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for position, query in enumerate(context.get("blocking_queries", []), start=1):
        query_id = _safe_text(query.get("query_id"), f"unknown-{position}")
        token = sha_bytes(query_id.encode("utf-8"))[:16]
        findings.append(_finding(
            request,
            f"required_author_query_unresolved:{token}",
            f"Required blocking author query remains unresolved: {query_id}",
            check_id="required_author_query_resolution",
            evidence=[f"query_id={query_id}", "blocks_revision=true", "resolution_status=unresolved"],
        ))
    return findings


def _domain_coverage(route: str, registry: dict[str, Any], requested: list[str], core_outcome: str | None) -> list[dict[str, Any]]:
    coverage: list[dict[str, Any]] = []
    base = BASE_DOMAINS[route]
    base_state = "passed"
    if core_outcome == "fail":
        base_state = "failed"
    elif core_outcome == "unassessable":
        base_state = "unassessable"
    coverage.append({"domain": base, "requested": True, "implemented": True, "execution_state": "executed", "assessment_state": base_state})
    unimplemented = list(registry["explicitly_unimplemented_domains"].get("review" if route == "review_revision" else "figure" if route == "figure_qc" else "article", []))
    for domain in unimplemented:
        coverage.append({
            "domain": domain, "requested": domain in requested, "implemented": False,
            "execution_state": "not_run_unimplemented", "assessment_state": "not_assessed",
        })
    known = {item["domain"] for item in coverage}
    for domain in requested:
        if domain not in known:
            coverage.append({
                "domain": domain, "requested": True, "implemented": False,
                "execution_state": "not_run_unsupported", "assessment_state": "not_assessed",
            })
    return coverage


def _error_terminal_state(
    request: dict[str, Any], error: IntegrationError, registry: dict[str, Any] | None,
) -> str:
    """Classify only unsupported or contradictory type errors as ``rejected``."""
    if error.code in {"route:unsupported", "route:document_type", "figure:variant", "producer:interface"}:
        return "rejected"
    if error.code not in {"request:schema", "request:consumer_interface", "producer:identity"}:
        return "blocked"
    route = request.get("route")
    if not isinstance(route, str) or route not in PRODUCER_PATHS:
        return "rejected"
    route_record = None
    if isinstance(registry, dict):
        route_record = next(
            (item for item in registry.get("interfaces", []) if item.get("route") == route),
            None,
        )
    if route_record is None:
        return "blocked"
    consumer = request.get("consumer_interface")
    consumer_version = request.get("consumer_interface_version")
    if consumer is not None and consumer != route_record.get("consumer_interface"):
        return "rejected"
    if consumer_version is not None and consumer_version != route_record.get("consumer_interface_version"):
        return "rejected"
    producer = request.get("producer")
    if isinstance(producer, dict):
        producer_skill = producer.get("skill_name")
        producer_interface = producer.get("producer_interface")
        producer_interface_version = producer.get("producer_interface_version")
        if producer_skill is not None and producer_skill != route_record.get("producer_skill"):
            return "rejected"
        if producer_interface is not None and producer_interface != route_record.get("producer_interface"):
            return "rejected"
        if producer_interface_version is not None and producer_interface_version != route_record.get("producer_interface_version"):
            return "rejected"
    if route == "figure_qc":
        validation = request.get("producer_validation")
        variant = validation.get("variant") if isinstance(validation, dict) else None
        if variant is not None and variant not in {"phase8a_design", "phase8b_prototype"}:
            return "rejected"
    return "blocked"


def _write_outputs(
    request: dict[str, Any], output_dir: Path, registry: dict[str, Any] | None,
    route_record: dict[str, Any] | None, index: ArtifactIndex | None, context: dict[str, Any] | None,
    error: IntegrationError | None,
) -> tuple[dict[str, Any], int]:
    route = _safe_text(request.get("route"), "unknown")
    request_id = _safe_identifier(request.get("request_id"), "unknown")
    created_at = _safe_timestamp(request.get("created_at"))
    consumer_interface_version = "0.1.0"
    findings: list[dict[str, Any]] = []
    core_report: dict[str, Any] | None = None
    projection: dict[str, Any] | None = None
    if error is None and context is not None and route in {"article_revision", "review_revision"}:
        try:
            findings, core_report, projection = run_text_qc(route, context, output_dir, created_at)
        except IntegrationError as exc:
            error = exc
    if error is not None:
        admission_state = "rejected"
        findings = [_finding(request, error.code, error.message)]
        gate_outcome = "unassessable"
        terminal_state = _error_terminal_state(request, error, registry)
        domain_coverage: list[dict[str, Any]] = []
    else:
        admission_state = context.get("admission_state", "accepted") if context else "accepted"
        if route == "figure_qc":
            findings = [_finding(request, "figure_domains_unimplemented", "Figure scientific/visual assessment domains are unimplemented", severity="warning")]
            gate_outcome = "unassessable"
            terminal_state = "qc_unassessable_author_review_required"
            core_outcome = None
        else:
            core_outcome = core_report["gate_outcome"] if core_report else "unassessable"
            gate_outcome = core_outcome
            terminal_state = "qc_unassessable_author_review_required" if gate_outcome == "unassessable" else "qc_complete_author_review_required"
            query_findings = _blocking_query_findings(request, context or {})
            if query_findings:
                findings.extend(query_findings)
                gate_outcome = "fail"
                terminal_state = "qc_complete_author_review_required"
        domain_coverage = _domain_coverage(route, registry or {}, request.get("requested_domains", []), core_outcome)
        if route == "figure_qc" or (
            gate_outcome != "fail"
            and any(item["requested"] and not item["implemented"] for item in domain_coverage)
        ):
            gate_outcome = "unassessable"
            terminal_state = "qc_unassessable_author_review_required"

    receipt: dict[str, Any] = {
        "schema_name": "module06_integration_admission_receipt", "schema_version": "0.1.0",
        "receipt_id": f"admission:{request_id}", "receipt_sha256": ZERO_HASH,
        "created_at": created_at, "request_id": request_id, "route": route,
        "consumer_interface": _safe_text(request.get("consumer_interface"), "unknown"),
        "consumer_interface_version": consumer_interface_version,
        "producer": request.get("producer", {}) if isinstance(request.get("producer"), dict) else {}, "admission_state": admission_state,
        "admitted_artifacts": _artifact_refs(index) if index else [],
        "issues": [] if error is None else [{"code": error.code, "message": error.message}],
        "author_approval_claimed": False, "scientific_truth_claimed": False,
    }
    receipt["receipt_sha256"] = payload_sha256(receipt, "receipt_sha256")
    write_json(output_dir / "module06-integration-admission-receipt.json", receipt)
    findings_dir = output_dir / "findings"
    findings_dir.mkdir(parents=True, exist_ok=True)
    for position, finding in enumerate(findings, start=1):
        write_json(findings_dir / f"finding-{position:04d}.json", finding)

    limitations = [
        "Admission and QC do not establish scientific truth or author approval.",
        "No input is rewritten and no automatic repair is performed.",
    ]
    if route == "figure_qc":
        limitations.append("Figure integration covers identity/state/handoff closure only; clean Figure pass is prohibited.")
    gate: dict[str, Any] = {
        "schema_name": "module06_gate_report", "schema_version": "0.1.0",
        "gate_report_id": f"gate:{request_id}", "gate_report_sha256": ZERO_HASH,
        "created_at": created_at, "request_id": request_id, "route": route,
        "admission_state": admission_state, "gate_outcome": gate_outcome, "terminal_state": terminal_state,
        "domain_coverage": domain_coverage, "finding_ids": [item["finding_id"] for item in findings],
        "human_review_required": True, "limitations": limitations,
        "author_approval_claimed": False, "scientific_truth_claimed": False, "automatic_repair_performed": False,
    }
    gate["gate_report_sha256"] = payload_sha256(gate, "gate_report_sha256")
    write_json(output_dir / "module06-gate-report.json", gate)

    output_paths = [
        output_dir / "module06-integration-admission-receipt.json",
        output_dir / "module06-gate-report.json",
        *sorted((output_dir / "findings").glob("finding-*.json")),
    ]
    if projection is not None:
        output_paths.extend([
            output_dir / "structured-text-projection-receipt.json", output_dir / "comparison-manifest.json",
            output_dir / "source-preservation-snapshot.json", output_dir / "candidate-preservation-snapshot.json",
            output_dir / "qc-report.json", output_dir / "source-projection.md", output_dir / "candidate-projection.md",
        ])
    output_refs = [
        {
            "path": path.relative_to(output_dir).as_posix(), "file_sha256": file_sha256(path),
            "canonical_sha256": canonical_sha256(read_json(path)) if path.suffix == ".json" else None,
        }
        for path in output_paths
    ]
    bundle: dict[str, Any] = {
        "schema_name": "module06_integrity_qc_bundle", "schema_version": "0.1.0",
        "bundle_id": f"module06-qc:{request_id}", "bundle_sha256": ZERO_HASH,
        "created_at": created_at, "request_id": request_id, "route": route,
        "consumer_interface": _safe_text(request.get("consumer_interface"), "unknown"),
        "consumer_interface_version": consumer_interface_version,
        "output_interface": "module06_integrity_qc_bundle", "output_interface_version": "0.1.0",
        "contract_version": CONTRACT_VERSION, "integration_version": INTEGRATION_VERSION,
        "admission_receipt_ref": {"id": receipt["receipt_id"], "version": receipt["schema_version"], "sha256": receipt["receipt_sha256"]},
        "gate_report_ref": {"id": gate["gate_report_id"], "version": gate["schema_version"], "sha256": gate["gate_report_sha256"]},
        "output_artifacts": output_refs, "terminal_state": terminal_state,
        "human_review_required": True, "author_approval_claimed": False,
        "scientific_truth_claimed": False, "automatic_repair_performed": False,
    }
    bundle["bundle_sha256"] = payload_sha256(bundle, "bundle_sha256")
    write_json(output_dir / "module06-integrity-qc-bundle.json", bundle)
    return bundle, 1 if error is not None else 0


def process_request(request: dict[str, Any], invocation_root: Path, output_dir: Path) -> tuple[dict[str, Any], int]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise IntegrationError("output:not_empty", f"output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    registry: dict[str, Any] | None = None
    index: ArtifactIndex | None = None
    route_record: dict[str, Any] | None = None
    context: dict[str, Any] | None = None
    error: IntegrationError | None = None
    try:
        registry = load_contract_registry()
        registry, index, route_record, context = validate_admission(request, invocation_root, registry)
    except (IntegrationError, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        error = exc if isinstance(exc, IntegrationError) else IntegrationError("admission:runtime", str(exc))
    return _write_outputs(request, output_dir, registry, route_record, index, context, error)
