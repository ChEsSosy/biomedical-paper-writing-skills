"""Synthetic package factory for deterministic Phase 8A tests.

The fixtures contain no real scientific data.  They exercise identities,
trusted-file inspection, authority, units, analysis-output provenance, and
non-circular hashes without invoking a plotting or statistical backend.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


STAMP = "2026-08-31T00:00:00Z"
ZERO_HASH = "0" * 64
SOURCE_MANIFEST_FILE = "source-data-manifest.json"
CARD_FILES = ["figure-card-panel-a.json", "figure-card-panel-b.json"]
CONTRACT_FILES = ["figure-contract-figure-1.json"]
RECIPE_FILES = ["plot-recipe-panel-a.json", "plot-recipe-panel-b.json"]
TRUST_FILES = {
    "trusted_source_inputs": "trusted-source-inputs.json",
    "trusted_analysis_outputs": "trusted-analysis-outputs.json",
    "trusted_authority_inputs": "trusted-authority-inputs.json",
}
MANIFEST_FILE = "design-package-manifest.json"
TRUST_ROOT_FILE = "trusted-inputs-root.json"


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def payload_sha256(value: dict[str, Any], field: str) -> str:
    return canonical_sha256({key: item for key, item in value.items() if key != field})


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _governed_projection(value: Any) -> Any:
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


def decision_ref(record: dict[str, Any]) -> dict[str, str]:
    return {
        "decision_id": record["decision_id"],
        "interface_version": record["interface_version"],
        "decision_sha256": record["decision_sha256"],
    }


def analysis_ref(record: dict[str, Any]) -> dict[str, str]:
    return {
        "analysis_output_id": record["analysis_output_id"],
        "record_version": record["record_version"],
        "record_sha256": record["record_sha256"],
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_ref(value: dict[str, Any], path: Path, kind: str) -> dict[str, Any]:
    return {
        "artifact_type": kind,
        "artifact_id": value["artifact_id"],
        "artifact_version": value["schema_version"],
        "artifact_sha256": value["artifact_sha256"],
        "path": path.name,
        "file_sha256": file_sha256(path),
    }


def _collection_ref(value: dict[str, Any], path: Path) -> dict[str, Any]:
    return {
        "interface_name": value["interface_name"],
        "collection_id": value["collection_id"],
        "collection_version": value["collection_version"],
        "collection_sha256": value["collection_sha256"],
        "path": path.name,
        "file_sha256": file_sha256(path),
    }


def _refresh_refs(value: Any, decisions: dict[str, dict[str, Any]], analyses: dict[str, dict[str, Any]]) -> None:
    if isinstance(value, list):
        for item in value:
            _refresh_refs(item, decisions, analyses)
        return
    if not isinstance(value, dict):
        return
    decision_id = value.get("decision_id")
    if decision_id in decisions and "interface_version" in value and "decision_sha256" in value:
        value.update(decision_ref(decisions[decision_id]))
    analysis_id = value.get("analysis_output_id")
    if analysis_id in analyses and "record_version" in value and "record_sha256" in value:
        value.update(analysis_ref(analyses[analysis_id]))
    for item in value.values():
        _refresh_refs(item, decisions, analyses)


def _subject_index(documents: dict[str, Any]) -> dict[tuple[str, str], tuple[str, Any]]:
    subjects: dict[tuple[str, str], tuple[str, Any]] = {}
    for card in documents["cards"]:
        version = card["schema_version"]
        subjects[("figure_card", card["artifact_id"])] = (version, card)
        representative = card.get("representative_image")
        if isinstance(representative, dict):
            subjects[("representative_image", representative["representative_image_id"])] = (
                version, representative
            )
    for contract in documents["contracts"]:
        version = contract["schema_version"]
        subjects[("figure_contract", contract["artifact_id"])] = (version, contract)
        for omission in contract.get("omitted_evidence", []):
            subjects[("evidence_omission", omission["omission_id"])] = (version, omission)
        for layout in contract.get("layout_decisions", []):
            subjects[("layout", layout["layout_id"])] = (version, layout)
        subjects[("finality", contract["artifact_id"])] = (
            version,
            {"figure_contract_id": contract["artifact_id"], "finality_state": contract["finality_state"]},
        )
    for analysis in documents["analysis_collection"]["records"]:
        subjects[("analysis_output", analysis["analysis_output_id"])] = (
            analysis["record_version"], analysis
        )
    return subjects


def _load_documents(root: Path) -> dict[str, Any]:
    return {
        "source_manifest": read_json(root / SOURCE_MANIFEST_FILE),
        "cards": [read_json(root / name) for name in CARD_FILES],
        "contracts": [read_json(root / name) for name in CONTRACT_FILES],
        "recipes": [read_json(root / name) for name in RECIPE_FILES],
        "source_collection": read_json(root / TRUST_FILES["trusted_source_inputs"]),
        "analysis_collection": read_json(root / TRUST_FILES["trusted_analysis_outputs"]),
        "authority_collection": read_json(root / TRUST_FILES["trusted_authority_inputs"]),
        "manifest": read_json(root / MANIFEST_FILE),
    }


def _write_documents(root: Path, documents: dict[str, Any]) -> None:
    write_json(root / SOURCE_MANIFEST_FILE, documents["source_manifest"])
    for name, card in zip(CARD_FILES, documents["cards"], strict=True):
        write_json(root / name, card)
    for name, contract in zip(CONTRACT_FILES, documents["contracts"], strict=True):
        write_json(root / name, contract)
    for name, recipe in zip(RECIPE_FILES, documents["recipes"], strict=True):
        write_json(root / name, recipe)
    write_json(root / TRUST_FILES["trusted_source_inputs"], documents["source_collection"])
    write_json(root / TRUST_FILES["trusted_analysis_outputs"], documents["analysis_collection"])
    write_json(root / TRUST_FILES["trusted_authority_inputs"], documents["authority_collection"])
    write_json(root / MANIFEST_FILE, documents["manifest"])


def rehash_package(root: Path, *, refresh_decision_subjects: bool = True) -> None:
    """Refresh intentional hashes and manifest references after a test mutation."""
    documents = _load_documents(root)
    subjects = _subject_index(documents)
    decisions = documents["authority_collection"]["records"]
    if refresh_decision_subjects:
        for decision in decisions:
            for subject in decision.get("subject_refs", []):
                governed = subjects.get((subject.get("subject_type"), subject.get("subject_id")))
                if governed is not None:
                    subject["subject_version"] = governed[0]
                    subject["governed_content_sha256"] = governed_content_sha256(governed[1])
    for decision in decisions:
        decision["decision_sha256"] = payload_sha256(decision, "decision_sha256")
    decision_by_id = {item["decision_id"]: item for item in decisions}

    analyses = documents["analysis_collection"]["records"]
    analysis_by_id = {item["analysis_output_id"]: item for item in analyses}
    for value in [*documents["cards"], *documents["contracts"], *analyses]:
        _refresh_refs(value, decision_by_id, analysis_by_id)
    for analysis in analyses:
        analysis["record_sha256"] = payload_sha256(analysis, "record_sha256")
    analysis_by_id = {item["analysis_output_id"]: item for item in analyses}
    for value in [*documents["cards"], *documents["contracts"], *documents["recipes"]]:
        _refresh_refs(value, decision_by_id, analysis_by_id)

    for collection_key in ("source_collection", "analysis_collection", "authority_collection"):
        collection = documents[collection_key]
        collection["collection_sha256"] = payload_sha256(collection, "collection_sha256")
    for artifact in [
        documents["source_manifest"], *documents["cards"], *documents["contracts"], *documents["recipes"]
    ]:
        artifact["artifact_sha256"] = payload_sha256(artifact, "artifact_sha256")

    # Component/trust files must exist before their byte hashes enter the manifest.
    _write_documents(root, documents)
    manifest = documents["manifest"]
    manifest["components"] = {
        "source_data_manifest": _artifact_ref(
            documents["source_manifest"], root / SOURCE_MANIFEST_FILE, "source_data_manifest"
        ),
        "figure_cards": [
            _artifact_ref(value, root / name, "figure_card")
            for name, value in zip(CARD_FILES, documents["cards"], strict=True)
        ],
        "figure_contracts": [
            _artifact_ref(value, root / name, "figure_contract")
            for name, value in zip(CONTRACT_FILES, documents["contracts"], strict=True)
        ],
        "plot_recipes": [
            _artifact_ref(value, root / name, "plot_recipe")
            for name, value in zip(RECIPE_FILES, documents["recipes"], strict=True)
        ],
    }
    manifest["trust_bindings"] = {
        key: _collection_ref(documents[{
            "trusted_source_inputs": "source_collection",
            "trusted_analysis_outputs": "analysis_collection",
            "trusted_authority_inputs": "authority_collection",
        }[key]], root / filename)
        for key, filename in TRUST_FILES.items()
    }
    manifest["design_package_hash"] = payload_sha256(manifest, "design_package_hash")
    write_json(root / MANIFEST_FILE, manifest)


def load_package(root: Path) -> dict[str, Any]:
    return _load_documents(root)


def write_external_trust_root(package_root: Path, target: Path) -> str:
    """Write caller-held collection identities outside the model package.

    The returned file SHA-256 represents the value a calling workflow must retain
    independently; package rehashing deliberately never updates this file.
    """
    documents = _load_documents(package_root)
    collections = {
        "trusted_source_inputs": documents["source_collection"],
        "trusted_analysis_outputs": documents["analysis_collection"],
        "trusted_authority_inputs": documents["authority_collection"],
    }
    trust_root = {
        "schema_name": "trusted_inputs_root",
        "schema_version": "0.1.0",
        "trust_root_id": "phase8a-caller-trust-root",
        "supplied_by": "synthetic-caller-outside-package",
        "collections": {
            name: {
                "collection_id": collection["collection_id"],
                "collection_version": collection["collection_version"],
                "collection_sha256": collection["collection_sha256"],
            }
            for name, collection in collections.items()
        },
    }
    write_json(target, trust_root)
    return file_sha256(target)


def save_package(root: Path, documents: dict[str, Any], *, rehash: bool = True, refresh_decision_subjects: bool = True) -> None:
    _write_documents(root, documents)
    if rehash:
        rehash_package(root, refresh_decision_subjects=refresh_decision_subjects)


def set_maturity(documents: dict[str, Any], maturity: str) -> None:
    documents["manifest"]["maturity"] = maturity
    documents["source_manifest"]["maturity"] = maturity
    for artifact in [*documents["cards"], *documents["contracts"], *documents["recipes"]]:
        artifact["maturity"] = maturity


def make_decision(
    decision_id: str,
    decision_type: str,
    subject_type: str,
    subject_id: str,
    subject_version: str,
    governed_value: Any,
    *,
    role: str = "author",
    input_binding: tuple[str, str, str] | None = None,
) -> dict[str, Any]:
    author = role == "author"
    record: dict[str, Any] = {
        "decision_id": decision_id,
        "interface_version": "0.1.0",
        "decision_sha256": ZERO_HASH,
        "decision_type": decision_type,
        "subject_refs": [{
            "subject_type": subject_type,
            "subject_id": subject_id,
            "asserted_state": "approved",
            "subject_version": subject_version,
            "governed_content_sha256": governed_content_sha256(governed_value),
        }],
        "decision_value": "approve" if author else "confirm",
        "authorization_origin": "author" if author else "calling_workflow",
        "authorization_state": "author_approved" if author else "caller_accepted",
        "decision_producer_role": role,
        "created_at": STAMP,
        "created_by": "phase8a-synthetic-fixture",
        "reviewed_by": "phase8a-synthetic-reviewer",
        "upstream_input_bindings": [],
        "conditions": [],
    }
    if input_binding is not None:
        record["upstream_input_bindings"].append({
            "input_id": input_binding[0],
            "input_version": input_binding[1],
            "input_sha256": input_binding[2],
        })
    record["decision_sha256"] = payload_sha256(record, "decision_sha256")
    return record


def _unit_context() -> dict[str, str]:
    return {
        "observation_unit": "animal_measurement",
        "feature_unit": "response_measurement",
        "experimental_unit": "animal",
        "inference_unit": "animal",
    }


def _replicate_context() -> dict[str, Any]:
    return {
        "biological_replicate": "independently assigned animal",
        "biological_replicate_unit": "animal",
        "technical_replicate": "single assay read per animal",
        "technical_replicate_unit": "assay_read",
        "n_definition": "number of independently assigned animals",
        "n_unit": "animal",
        "n_by_group": {"control": 2, "treated": 2},
    }


def _design_context() -> dict[str, Any]:
    return {
        "groups": ["control", "treated"],
        "controls": ["control"],
        "comparators": ["control"],
        "contrasts": ["contrast-treated-vs-control"],
        "paired": False,
        "repeated": False,
        "nested": False,
        "clustered": False,
        "batch_variable": None,
        "time_variable": None,
    }


def _card_design_context() -> dict[str, Any]:
    return {
        "group_ids": ["control", "treated"],
        "control_ids": ["control"],
        "comparison_ids": ["contrast-treated-vs-control"],
        "paired": False,
        "repeated": False,
        "nested": False,
        "clustered": False,
    }


def build_valid_package(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    data_path = root / "data" / "source.csv"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(
        "sample_id,group,response\n"
        "animal-1,control,1.0\n"
        "animal-2,control,1.2\n"
        "animal-3,treated,2.4\n"
        "animal-4,treated,2.8\n",
        encoding="utf-8",
    )
    data_hash = file_sha256(data_path)
    data_size = data_path.stat().st_size
    upstream_ref = {
        "artifact_id": "manuscript-plan-1",
        "artifact_version": "0.1.1",
        "artifact_sha256": "a" * 64,
    }
    ceiling = {
        "strength": "comparative",
        "causality": "association",
        "mechanism": "none",
        "generalization": "system_only",
    }
    units = _unit_context()
    replicates = _replicate_context()
    source_record: dict[str, Any] = {
        "source_data_id": "source-data-1",
        "record_version": "0.1.0",
        "source_class": "tabular",
        "origin": "author_supplied",
        "availability": "available",
        "trusted_input_id": "trusted-input-1",
        "file_identity": {
            "path": "data/source.csv", "format": "csv", "size": data_size, "sha256": data_hash
        },
        "data_status": "raw",
        "locators": [
            {"locator_type": "header", "value": "sample_id"},
            {"locator_type": "header", "value": "group"},
            {"locator_type": "header", "value": "response"},
        ],
        "variables": [
            {"variable_id": "sample_id", "data_type": "string", "unit": "identifier", "role": "entity_id", "missingness_status": "none"},
            {"variable_id": "group", "data_type": "category", "unit": "category", "role": "group", "missingness_status": "none"},
            {"variable_id": "response", "data_type": "number", "unit": "arbitrary_unit", "role": "measurement", "missingness_status": "none"},
        ],
        "units": copy.deepcopy(units),
        "replicates": copy.deepcopy(replicates),
        "design_context": _design_context(),
        "transformations": [],
        "processing_history": [],
        "analysis_output_ids": ["analysis-output-1"],
        "declared_inspection_state": "content_expected",
        "provenance_gaps": [],
    }
    source_manifest: dict[str, Any] = {
        "schema_name": "source_data_manifest",
        "schema_version": "0.1.0",
        "contract_version": "0.1.1",
        "artifact_id": "source-data-manifest-1",
        "artifact_sha256": ZERO_HASH,
        "document_type": "original_article",
        "maturity": "ready_for_author_review",
        "created_by": "phase8a-synthetic-fixture",
        "source_records": [source_record],
    }

    source_collection: dict[str, Any] = {
        "interface_name": "trusted_source_inputs",
        "interface_version": "0.1.0",
        "collection_kind": "trusted_source_inputs",
        "collection_id": "trusted-source-collection-1",
        "collection_version": "0.1.0",
        "collection_sha256": ZERO_HASH,
        "supplied_by": "synthetic-caller",
        "records": [{
            "trusted_input_id": "trusted-input-1",
            "source_data_id": "source-data-1",
            "access_mode": "package_relative_file",
            "path": "data/source.csv",
            "resolver_ref": None,
            "format": "csv",
            "expected_size": data_size,
            "expected_sha256": data_hash,
            "expected_locators": [
                {"locator_type": "header", "value": "sample_id"},
                {"locator_type": "header", "value": "group"},
                {"locator_type": "header", "value": "response"},
            ],
            "adapter": {"name": "python-csv", "version": "stdlib"},
        }],
    }

    source_record_hash = canonical_sha256(source_record)
    analysis: dict[str, Any] = {
        "analysis_output_id": "analysis-output-1",
        "record_version": "0.1.0",
        "record_sha256": ZERO_HASH,
        "result_status": "supplied",
        "source_data_refs": [{
            "source_data_id": "source-data-1",
            "source_data_version": "0.1.0",
            "source_data_sha256": source_record_hash,
            "trusted_input_id": "trusted-input-1",
        }],
        "input_data_hashes": [data_hash],
        "analysis_origin": "authorized_analysis_workflow",
        "workflow": {
            "name": "synthetic-authorized-analysis",
            "version": "1.0.0",
            "output_sha256": canonical_sha256("synthetic analysis output"),
        },
        "comparison_ids": ["contrast-treated-vs-control"],
        "group_ids": ["control", "treated"],
        "contrast_definition": "treated minus control",
        "unit_context": copy.deepcopy(units),
        "n_by_group": copy.deepcopy(replicates["n_by_group"]),
        "n_definition": replicates["n_definition"],
        "n_unit": replicates["n_unit"],
        "statistic_type": "mean_difference",
        "estimate": 1.5,
        "center_definition": "arithmetic mean",
        "spread_or_interval_definition": "95% confidence interval",
        "test_name": "externally supplied synthetic test",
        "model_specification": None,
        "paired": False,
        "repeated": False,
        "nested": False,
        "clustered": False,
        "sidedness": "two_sided",
        "multiplicity_correction": None,
        "p_value": 0.04,
        "adjusted_p_value": None,
        "effect_size": 1.5,
        "interval": {"lower": 0.2, "upper": 2.8, "level": 0.95},
        "review_status": "approved",
        "authorization_state": "caller_accepted",
    }
    analysis_decision = make_decision(
        "analysis-review-1", "analysis_output_review", "analysis_output", "analysis-output-1",
        "0.1.0", analysis, role="authorized_analysis_workflow",
        input_binding=("trusted-input-1", "0.1.0", data_hash),
    )
    analysis["decision_ref"] = decision_ref(analysis_decision)
    analysis["record_sha256"] = payload_sha256(analysis, "record_sha256")
    analysis_collection: dict[str, Any] = {
        "interface_name": "trusted_analysis_outputs",
        "interface_version": "0.1.0",
        "collection_kind": "trusted_analysis_outputs",
        "collection_id": "trusted-analysis-collection-1",
        "collection_version": "0.1.0",
        "collection_sha256": ZERO_HASH,
        "supplied_by": "synthetic-caller",
        "records": [analysis],
    }
    authority_collection: dict[str, Any] = {
        "interface_name": "trusted_authority_inputs",
        "interface_version": "0.1.0",
        "collection_kind": "trusted_authority_inputs",
        "collection_id": "trusted-authority-collection-1",
        "collection_version": "0.1.0",
        "collection_sha256": ZERO_HASH,
        "supplied_by": "synthetic-caller",
        "records": [analysis_decision],
    }
    analysis_reference = analysis_ref(analysis)

    cards: list[dict[str, Any]] = []
    recipes: list[dict[str, Any]] = []
    for label, role, stat_status in (
        ("panel-a", "show group-level observations and supplied comparison", "supplied"),
        ("panel-b", "show the same bounded response distribution without a second test", "not_applicable"),
    ):
        card: dict[str, Any] = {
            "schema_name": "figure_card",
            "schema_version": "0.1.0",
            "contract_version": "0.1.1",
            "artifact_id": f"figure-card-{label}",
            "artifact_sha256": ZERO_HASH,
            "document_type": "original_article",
            "maturity": "ready_for_author_review",
            "figure_id": "figure-1",
            "panel_id": label,
            "panel_kind": "quantitative_plot",
            "evidence_role": "evidence_bearing",
            "data_bearing": True,
            "scientific_question": "How does the supplied response differ between declared groups?",
            "panel_role": role,
            "upstream_ref": copy.deepcopy(upstream_ref),
            "claim_ids": ["claim-1"],
            "evidence_bindings": [{"claim_id": "claim-1", "evidence_id": "evidence-1", "relation_type": "support"}],
            "source_data_ids": ["source-data-1"],
            "data_locators": [
                {"source_data_id": "source-data-1", "locator_type": "variable", "value": "group"},
                {"source_data_id": "source-data-1", "locator_type": "variable", "value": "response"},
            ],
            "experiment_labels": ["animal_in_vivo"],
            "units": copy.deepcopy(units),
            "replicates": copy.deepcopy(replicates),
            "design_context": _card_design_context(),
            "visual_encoding": {
                "plot_archetype": "raw_points_with_summary",
                "mappings": {"x": "group", "y": "response", "color": "group"},
                "origin": "model_proposed",
                "review_status": "author_review_required",
            },
            "statistical_annotations": [{
                "annotation_id": f"annotation-{label}",
                "status": stat_status,
                "comparison_id": "contrast-treated-vs-control" if stat_status == "supplied" else None,
                "symbol": "p=0.04" if stat_status == "supplied" else None,
                **({"analysis_output_ref": copy.deepcopy(analysis_reference)} if stat_status == "supplied" else {}),
            }],
            "required_visibility_ids": ["evidence-1"],
            "origin": "model_proposed",
            "review_status": "author_review_required",
            "decision_refs": [],
            "representative_image": None,
            "reference_abstractions": [],
            "reuse_group_id": None,
        }
        cards.append(card)
        recipe: dict[str, Any] = {
            "schema_name": "plot_recipe",
            "schema_version": "0.1.0",
            "contract_version": "0.1.1",
            "artifact_id": f"plot-recipe-{label}",
            "artifact_sha256": ZERO_HASH,
            "recipe_id": f"recipe-{label}",
            "figure_id": "figure-1",
            "panel_id": label,
            "document_type": "original_article",
            "maturity": "ready_for_author_review",
            "source_data_ids": ["source-data-1"],
            "variable_mappings": [
                {"aesthetic": "x", "source_data_id": "source-data-1", "variable_id": "group"},
                {"aesthetic": "y", "source_data_id": "source-data-1", "variable_id": "response"},
                {"aesthetic": "color", "source_data_id": "source-data-1", "variable_id": "group"},
            ],
            "filters": [],
            "exclusions": [],
            "transformation_ids": [],
            "aggregation": "summary by declared experimental unit",
            "ordering": ["control", "treated"],
            "layers": [{
                "layer_id": f"layer-{label}", "mark": "point",
                "summary_intent": "show supplied group center and interval",
                "raw_observation_policy": "show every declared experimental unit",
                "uncertainty_representation": "bind to supplied analysis output",
            }],
            "statistical_annotations": [{
                "annotation_id": f"annotation-{label}",
                "status": stat_status,
                "comparison_id": "contrast-treated-vs-control" if stat_status == "supplied" else None,
                "symbol": "p=0.04" if stat_status == "supplied" else None,
                **({"analysis_output_ref": copy.deepcopy(analysis_reference)} if stat_status == "supplied" else {}),
            }],
            "axes": [
                {"axis": "x", "variable_id": "group", "scale": "categorical", "unit": "category", "limits_policy": "show all declared groups"},
                {"axis": "y", "variable_id": "response", "scale": "linear", "unit": "arbitrary_unit", "limits_policy": "data-derived without truncation"},
            ],
            "palette_keys": ["control", "treated"],
            "image_instructions": [],
            "legend_intent": ["define group colors"],
            "export_intent": ["prototype recipe only"],
            "backend_route": None,
            "implementation_status": "not_executed",
            "review_status": "author_review_required",
        }
        recipes.append(recipe)

    contract: dict[str, Any] = {
        "schema_name": "figure_contract",
        "schema_version": "0.1.0",
        "contract_version": "0.1.1",
        "artifact_id": "figure-contract-1",
        "artifact_sha256": ZERO_HASH,
        "figure_id": "figure-1",
        "document_type": "original_article",
        "maturity": "ready_for_author_review",
        "intended_location": "Results",
        "upstream_ref": copy.deepcopy(upstream_ref),
        "upstream_figure_or_brief_id": "figure-1",
        "conclusion": {
            "text": "The supplied groups differ in the measured response within the declared system.",
            "origin": "model_proposed",
            "review_status": "author_review_required",
            "structured_ceiling": copy.deepcopy(ceiling),
        },
        "ordered_panel_ids": ["panel-a", "panel-b"],
        "panel_roles": [
            {"panel_id": "panel-a", "role": "primary comparison"},
            {"panel_id": "panel-b", "role": "distribution context"},
        ],
        "claim_ids": ["claim-1"],
        "evidence_ids": ["evidence-1"],
        "evidence_unit_ids": ["evidence-unit-1"],
        "independent_evidence_unit_count": 1,
        "source_data_ids": ["source-data-1"],
        "required_visibility_ids": ["evidence-1"],
        "omitted_evidence": [],
        "palette_semantics": [
            {"semantic_key": "control", "value": "#4477AA", "scope": "project", "version": "0.1.0"},
            {"semantic_key": "treated", "value": "#CC6677", "scope": "project", "version": "0.1.0"},
        ],
        "layout_decisions": [{
            "layout_id": "layout-1", "description": "place panels in declared order",
            "origin": "model_proposed", "review_status": "author_review_required",
        }],
        "legend_requirements": ["define n as animals", "identify supplied statistic"],
        "accessibility_requirements": ["do not rely on color alone"],
        "requested_outputs": ["backend-independent recipe"],
        "finality_state": "author_review_required",
        "review_status": "author_review_required",
        "decision_refs": [],
    }

    manifest: dict[str, Any] = {
        "schema_name": "design_package_manifest",
        "schema_version": "0.1.0",
        "contract_version": "0.1.1",
        "design_package_id": "design-package-1",
        "design_package_version": "0.1.0",
        "design_package_hash": ZERO_HASH,
        "created_at": STAMP,
        "document_type": "original_article",
        "maturity": "ready_for_author_review",
        "upstream_context": {
            "artifact_ref": copy.deepcopy(upstream_ref),
            "claims": [{
                "claim_id": "claim-1",
                "claim_origin": "source_claim",
                "source_ids": ["source-publication-1"],
                "evidence_unit_ids": ["evidence-unit-1"],
                "structured_ceiling": copy.deepcopy(ceiling),
            }],
            "evidence": [{
                "evidence_id": "evidence-1", "evidence_unit_id": "evidence-unit-1",
                "linked_source_ids": ["source-publication-1"], "relation_status": "support",
            }],
            "claim_evidence_relations": [{
                "claim_id": "claim-1", "evidence_id": "evidence-1", "relation_type": "support"
            }],
            "required_visibility_ids": ["evidence-1"],
            "figure_sequence": [{
                "figure_id": "figure-1", "order": 1, "claim_ids": ["claim-1"],
                "evidence_ids": ["evidence-1"], "author_approval": "pending",
            }],
            "review_figure_briefs": [],
        },
        "components": {},
        "trust_bindings": {},
        "ruleset": {
            "ruleset_id": "phase8a-deterministic-rules",
            "ruleset_version": "0.1.0",
            "ruleset_sha256": canonical_sha256("phase8a-deterministic-rules-0.1.0"),
        },
        "profiles": [
            {"profile_kind": "experiment", "status": "not_assessed", "profile_id": None, "profile_version": None, "profile_sha256": None},
            {"profile_kind": "journal", "status": "not_assessed", "profile_id": None, "profile_version": None, "profile_sha256": None},
            {"profile_kind": "reporting", "status": "not_assessed", "profile_id": None, "profile_version": None, "profile_sha256": None},
            {"profile_kind": "backend", "status": "not_assessed", "profile_id": None, "profile_version": None, "profile_sha256": None},
        ],
    }
    documents = {
        "source_manifest": source_manifest,
        "cards": cards,
        "contracts": [contract],
        "recipes": recipes,
        "source_collection": source_collection,
        "analysis_collection": analysis_collection,
        "authority_collection": authority_collection,
        "manifest": manifest,
    }
    _write_documents(root, documents)
    rehash_package(root)
    return root
