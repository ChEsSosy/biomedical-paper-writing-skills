#!/usr/bin/env python3
"""Materialize one Figure-centric sequence from a bounded raw proposal.

The materializer performs structural grouping only. It preserves the exact
claim/evidence associations proposed upstream, rejects unknown identifiers, and
never infers a new scientific relationship.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


MATERIALIZER_VERSION = "0.1.0"
REQUIRED_FIELDS = {
    "figure_id",
    "order",
    "purpose",
    "claim_ids",
    "evidence_ids",
    "author_approval",
}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ordered_unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _require_known(values: list[str], allowed: set[str], field: str, index: int) -> None:
    unknown = [value for value in values if value not in allowed]
    if unknown:
        raise ValueError(f"proposal[{index}].{field} contains unknown IDs: {unknown}")


def materialize_figure_sequence(
    proposals: list[dict[str, Any]],
    *,
    allowed_figure_ids: Iterable[str],
    allowed_claim_ids: Iterable[str],
    allowed_evidence_ids: Iterable[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Group raw entries by Figure ID and return a formal sequence plus receipt."""

    figure_universe = set(allowed_figure_ids)
    claim_universe = set(allowed_claim_ids)
    evidence_universe = set(allowed_evidence_ids)
    if not proposals:
        raise ValueError("at least one Figure-sequence proposal is required")

    normalized: list[tuple[int, int, dict[str, Any]]] = []
    for index, item in enumerate(proposals):
        missing = REQUIRED_FIELDS - set(item)
        if missing:
            raise ValueError(f"proposal[{index}] missing fields: {sorted(missing)}")
        if not isinstance(item["order"], int) or item["order"] < 1:
            raise ValueError(f"proposal[{index}].order must be a positive integer")
        if item["figure_id"] not in figure_universe:
            raise ValueError(f"proposal[{index}].figure_id is outside the allowed universe")
        if not item["claim_ids"] or not item["evidence_ids"]:
            raise ValueError(f"proposal[{index}] must retain claim and evidence IDs")
        _require_known(item["claim_ids"], claim_universe, "claim_ids", index)
        _require_known(item["evidence_ids"], evidence_universe, "evidence_ids", index)
        normalized.append((item["order"], index, item))

    groups: dict[str, dict[str, Any]] = {}
    for proposed_order, source_index, item in sorted(normalized):
        figure_id = item["figure_id"]
        if figure_id not in groups:
            groups[figure_id] = {
                "first_proposed_order": proposed_order,
                "first_source_index": source_index,
                "source_indexes": [],
                "purposes": [],
                "claim_ids": [],
                "evidence_ids": [],
                "author_approval_states": [],
            }
        group = groups[figure_id]
        group["source_indexes"].append(source_index)
        group["purposes"].append(item["purpose"])
        group["claim_ids"].extend(item["claim_ids"])
        group["evidence_ids"].extend(item["evidence_ids"])
        group["author_approval_states"].append(item["author_approval"])

    ordered_groups = sorted(
        groups.items(),
        key=lambda pair: (
            pair[1]["first_proposed_order"],
            pair[1]["first_source_index"],
        ),
    )
    sequence: list[dict[str, Any]] = []
    operations: list[dict[str, Any]] = []
    for formal_order, (figure_id, group) in enumerate(ordered_groups, 1):
        approval_states = ordered_unique(group["author_approval_states"])
        if len(approval_states) != 1:
            raise ValueError(f"conflicting author_approval states for {figure_id}: {approval_states}")
        purposes = ordered_unique(group["purposes"])
        claim_ids = ordered_unique(group["claim_ids"])
        evidence_ids = ordered_unique(group["evidence_ids"])
        sequence.append(
            {
                "figure_id": figure_id,
                "order": formal_order,
                # Joining exact proposal fragments retains both purposes without
                # adding a model- or materializer-inferred scientific statement.
                "purpose": " | ".join(purposes),
                "claim_ids": claim_ids,
                "evidence_ids": evidence_ids,
                "author_approval": approval_states[0],
            }
        )
        operations.append(
            {
                "figure_id": figure_id,
                "source_proposal_indexes": group["source_indexes"],
                "formal_order": formal_order,
                "purpose_fragments_preserved": len(purposes),
                "claim_ids_ordered_unique": claim_ids,
                "evidence_ids_ordered_unique": evidence_ids,
            }
        )

    input_claims = set(value for item in proposals for value in item["claim_ids"])
    input_evidence = set(value for item in proposals for value in item["evidence_ids"])
    output_claims = set(value for item in sequence for value in item["claim_ids"])
    output_evidence = set(value for item in sequence for value in item["evidence_ids"])
    if input_claims != output_claims or input_evidence != output_evidence:
        raise RuntimeError("materialization changed the proposed claim/evidence association universe")

    receipt = {
        "schema_id": "manuscript-story-architect-figure-materialization-receipt",
        "schema_version": "0.1.0",
        "materializer_version": MATERIALIZER_VERSION,
        "raw_proposal_sha256": canonical_sha256(proposals),
        "formal_sequence_sha256": canonical_sha256(sequence),
        "input_entry_count": len(proposals),
        "output_entry_count": len(sequence),
        "grouping_key": "figure_id",
        "ordering_rule": "proposed_order_then_first_occurrence_renumbered_contiguously",
        "scientific_associations_added": False,
        "operations": operations,
    }
    return sequence, receipt


def write_new(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--sequence-output", type=Path, required=True)
    parser.add_argument("--receipt-output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.proposal.read_text(encoding="utf-8"))
    sequence, receipt = materialize_figure_sequence(
        payload["figure_sequence_proposals"],
        allowed_figure_ids=payload["allowed_figure_ids"],
        allowed_claim_ids=payload["allowed_claim_ids"],
        allowed_evidence_ids=payload["allowed_evidence_ids"],
    )
    write_new(args.sequence_output, sequence)
    write_new(args.receipt_output, receipt)
    print(json.dumps({"input": len(payload["figure_sequence_proposals"]), "output": len(sequence)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
