#!/usr/bin/env python3
"""Deterministic semantic-consistency checks for story-planning artifacts.

These checks validate identities, links, declared statuses, and coverage. They do
not determine whether an experiment scientifically supports a claim.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class CheckIssue:
    code: str
    path: str
    message: str
    severity: str = "error"


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one artifact and fail when the JSON root is not an object."""
    payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Artifact root must be an object: {path}")
    return payload


def issue_dicts(issues: Iterable[CheckIssue]) -> list[dict[str, str]]:
    return [asdict(item) for item in issues]


def _index_records(
    records: Any,
    id_field: str,
    path: str,
    issues: list[CheckIssue],
) -> dict[str, dict[str, Any]]:
    """Index typed records while reporting missing and duplicate identifiers."""
    indexed: dict[str, dict[str, Any]] = {}
    if not isinstance(records, list):
        issues.append(CheckIssue("records_not_array", path, "Expected an array of records."))
        return indexed
    for index, record in enumerate(records):
        item_path = f"{path}[{index}]"
        if not isinstance(record, dict):
            issues.append(CheckIssue("record_not_object", item_path, "Expected an object record."))
            continue
        record_id = record.get(id_field)
        if not isinstance(record_id, str) or not record_id:
            issues.append(CheckIssue("missing_id", f"{item_path}.{id_field}", "Missing stable identifier."))
            continue
        if record_id in indexed:
            issues.append(CheckIssue("duplicate_id", f"{item_path}.{id_field}", f"Duplicate ID: {record_id}"))
            continue
        indexed[record_id] = record
    return indexed


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def _check_nested_author_approvals(
    value: Any,
    path: str,
    issues: list[CheckIssue],
) -> None:
    """Find pending nested approval fields inside an artifact declared approved."""
    if isinstance(value, dict):
        if "author_approval" in value and value.get("author_approval") != "approved":
            issues.append(
                CheckIssue(
                    "approved_artifact_has_unapproved_child",
                    f"{path}.author_approval",
                    f"Expected approved; got {value.get('author_approval')!r}.",
                )
            )
        for key, child in value.items():
            _check_nested_author_approvals(child, f"{path}.{key}", issues)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _check_nested_author_approvals(child, f"{path}[{index}]", issues)


def _check_terminal_decisions(
    decisions: Any,
    path: str,
    issues: list[CheckIssue],
) -> None:
    """Require each declared author decision to reach an explicit terminal state."""
    if not isinstance(decisions, list):
        return
    for index, decision in enumerate(decisions):
        if isinstance(decision, dict) and decision.get("status") not in {"approved", "rejected"}:
            issues.append(
                CheckIssue(
                    "approved_plan_has_unresolved_decision",
                    f"{path}[{index}].status",
                    f"Decision remains {decision.get('status')!r}.",
                )
            )


def validate_claim_map(payload: dict[str, Any]) -> list[CheckIssue]:
    """Check claim/evidence identity, explicit links, and declared support consistency."""
    issues: list[CheckIssue] = []
    claims = _index_records(payload.get("claim_records"), "claim_id", "$.claim_records", issues)
    evidence = _index_records(
        payload.get("evidence_records"), "evidence_id", "$.evidence_records", issues
    )
    links = _index_records(
        payload.get("claim_evidence_links"), "link_id", "$.claim_evidence_links", issues
    )
    _index_records(payload.get("frozen_elements"), "element_id", "$.frozen_elements", issues)
    _index_records(payload.get("author_decisions"), "decision_id", "$.author_decisions", issues)

    links_by_claim: dict[str, list[dict[str, Any]]] = {claim_id: [] for claim_id in claims}
    seen_pairs: set[tuple[str, str]] = set()
    for link_id, link in links.items():
        claim_id = link.get("claim_id")
        evidence_id = link.get("evidence_id")
        path = f"$.claim_evidence_links[{link_id}]"
        if claim_id not in claims:
            issues.append(CheckIssue("unknown_claim_ref", f"{path}.claim_id", f"Unknown claim ID: {claim_id}"))
        else:
            links_by_claim[claim_id].append(link)
        if evidence_id not in evidence:
            issues.append(
                CheckIssue("unknown_evidence_ref", f"{path}.evidence_id", f"Unknown evidence ID: {evidence_id}")
            )
        if isinstance(claim_id, str) and isinstance(evidence_id, str):
            pair = (claim_id, evidence_id)
            if pair in seen_pairs:
                issues.append(CheckIssue("duplicate_claim_evidence_pair", path, f"Duplicate relation pair: {pair}"))
            seen_pairs.add(pair)

    for claim_id, claim in claims.items():
        path = f"$.claim_records[{claim_id}]"
        declared_evidence = _string_set(claim.get("evidence_ids"))
        linked_evidence = {
            item.get("evidence_id")
            for item in links_by_claim.get(claim_id, [])
            if isinstance(item.get("evidence_id"), str)
        }
        for evidence_id in sorted(declared_evidence - set(evidence)):
            issues.append(
                CheckIssue("unknown_declared_evidence", f"{path}.evidence_ids", f"Unknown evidence ID: {evidence_id}")
            )
        if declared_evidence != linked_evidence:
            issues.append(
                CheckIssue(
                    "claim_link_set_mismatch",
                    path,
                    "Claim evidence_ids must exactly match its explicit claim_evidence_links.",
                )
            )

        relations = {item.get("relation") for item in links_by_claim.get(claim_id, [])}
        status = claim.get("support_status")
        if status == "supported" and "supports" not in relations:
            issues.append(
                CheckIssue("supported_without_supporting_link", path, "A supported claim needs a supports relation.")
            )
        elif status == "partially_supported" and not relations.intersection(
            {"supports", "partially_supports"}
        ):
            issues.append(
                CheckIssue(
                    "partial_without_supporting_link",
                    path,
                    "A partially supported claim needs a supports or partially_supports relation.",
                )
            )
        elif status == "conflicting" and "conflicts" not in relations:
            issues.append(
                CheckIssue("conflicting_without_conflict_link", path, "A conflicting claim needs a conflicts relation.")
            )

        if (
            claim.get("claim_origin") == "architect_proposed_restatement"
            and claim.get("author_approval") == "not_requested"
        ):
            issues.append(
                CheckIssue(
                    "architect_restatement_not_reviewable",
                    f"{path}.author_approval",
                    "An architect-proposed restatement must enter an author-review state.",
                )
            )
    return issues


def check_artifact_links(
    claim_map: dict[str, Any],
    interpretation_cards: list[dict[str, Any]],
    plan: dict[str, Any],
) -> list[CheckIssue]:
    """Check cross-artifact references, evidence assignment, and approval consistency."""
    issues = validate_claim_map(claim_map)
    claims = {
        record["claim_id"]: record
        for record in claim_map.get("claim_records", [])
        if isinstance(record, dict) and isinstance(record.get("claim_id"), str)
    }
    evidence = {
        record["evidence_id"]: record
        for record in claim_map.get("evidence_records", [])
        if isinstance(record, dict) and isinstance(record.get("evidence_id"), str)
    }
    claim_evidence_pairs = {
        (link["claim_id"], link["evidence_id"])
        for link in claim_map.get("claim_evidence_links", [])
        if isinstance(link, dict)
        and isinstance(link.get("claim_id"), str)
        and isinstance(link.get("evidence_id"), str)
    }

    cards: dict[str, dict[str, Any]] = {}
    boundary_ids: set[str] = set()
    card_boundary_ids: dict[str, set[str]] = {}
    card_ids: set[str] = set()
    for index, card in enumerate(interpretation_cards):
        path = f"$.interpretation_cards[{index}]"
        artifact_id = card.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            issues.append(CheckIssue("missing_card_artifact_id", f"{path}.artifact_id", "Missing card artifact ID."))
            continue
        if artifact_id in cards:
            issues.append(CheckIssue("duplicate_card_artifact_id", f"{path}.artifact_id", artifact_id))
            continue
        cards[artifact_id] = card
        card_boundary_ids[artifact_id] = set()
        card_id = card.get("card_id")
        if isinstance(card_id, str):
            if card_id in card_ids:
                issues.append(CheckIssue("duplicate_card_id", f"{path}.card_id", card_id))
            card_ids.add(card_id)
        _index_records(
            card.get("alternative_explanations"),
            "alternative_id",
            f"{path}.alternative_explanations",
            issues,
        )
        _index_records(
            card.get("validation_needs"),
            "validation_need_id",
            f"{path}.validation_needs",
            issues,
        )
        _index_records(
            card.get("proposed_validation_experiments"),
            "experiment_proposal_id",
            f"{path}.proposed_validation_experiments",
            issues,
        )
        _index_records(
            card.get("author_decisions"),
            "decision_id",
            f"{path}.author_decisions",
            issues,
        )
        claim_id = card.get("claim_id")
        if claim_id not in claims:
            issues.append(CheckIssue("unknown_card_claim", f"{path}.claim_id", f"Unknown claim ID: {claim_id}"))
        declared_card_evidence = _string_set(card.get("evidence_ids"))
        for evidence_id in sorted(declared_card_evidence):
            if evidence_id not in evidence:
                issues.append(
                    CheckIssue(
                        "unknown_card_evidence",
                        f"{path}.evidence_ids",
                        f"Unknown evidence ID: {evidence_id}",
                    )
                )
            elif claim_id in claims and (claim_id, evidence_id) not in claim_evidence_pairs:
                issues.append(
                    CheckIssue(
                        "card_evidence_not_linked_to_claim",
                        f"{path}.evidence_ids",
                        f"Evidence {evidence_id} has no explicit relation to card claim {claim_id}.",
                    )
                )
        boundary = card.get("boundary")
        boundary_id = boundary.get("boundary_id") if isinstance(boundary, dict) else None
        if isinstance(boundary_id, str):
            if boundary_id in boundary_ids:
                issues.append(CheckIssue("duplicate_boundary_id", f"{path}.boundary.boundary_id", boundary_id))
            boundary_ids.add(boundary_id)
            card_boundary_ids[artifact_id].add(boundary_id)

    map_artifact_id = claim_map.get("artifact_id")
    if plan.get("claim_evidence_map_id") != map_artifact_id:
        issues.append(
            CheckIssue(
                "plan_claim_map_mismatch",
                "$.plan.claim_evidence_map_id",
                "Plan must reference the supplied claim-map artifact ID.",
            )
        )
    planned_card_ids = _string_set(plan.get("interpretation_card_ids"))
    for card_id in sorted(planned_card_ids - set(cards)):
        issues.append(CheckIssue("unknown_plan_card", "$.plan.interpretation_card_ids", card_id))
    referenced_cards = [cards[card_id] for card_id in sorted(planned_card_ids) if card_id in cards]
    planned_card_claim_ids = {
        card["claim_id"]
        for card in referenced_cards
        if isinstance(card.get("claim_id"), str)
    }
    planned_boundary_ids = {
        boundary_id
        for card_id in planned_card_ids
        for boundary_id in card_boundary_ids.get(card_id, set())
    }

    source_ids = _string_set(plan.get("source_artifact_ids"))
    required_sources = ({map_artifact_id} if isinstance(map_artifact_id, str) else set()) | planned_card_ids
    for artifact_id in sorted(required_sources - source_ids):
        issues.append(CheckIssue("missing_plan_source_artifact", "$.plan.source_artifact_ids", artifact_id))

    anchors = plan.get("story_anchors", {})
    key_claim_ids = _string_set(anchors.get("key_claim_ids"))
    key_boundary_ids = _string_set(anchors.get("key_boundary_ids"))
    for claim_id in sorted(key_claim_ids - set(claims)):
        issues.append(CheckIssue("unknown_key_claim", "$.plan.story_anchors.key_claim_ids", claim_id))
    for claim_id in sorted((key_claim_ids & set(claims)) - planned_card_claim_ids):
        issues.append(
            CheckIssue(
                "key_claim_missing_interpretation_card",
                "$.plan.story_anchors.key_claim_ids",
                f"Key claim has no interpretation card referenced by the plan: {claim_id}",
            )
        )
    for boundary_id in sorted(key_boundary_ids - boundary_ids):
        issues.append(CheckIssue("unknown_key_boundary", "$.plan.story_anchors.key_boundary_ids", boundary_id))
    for boundary_id in sorted((key_boundary_ids & boundary_ids) - planned_boundary_ids):
        issues.append(
            CheckIssue(
                "key_boundary_not_from_planned_card",
                "$.plan.story_anchors.key_boundary_ids",
                f"Key boundary belongs only to an interpretation card not referenced by the plan: {boundary_id}",
            )
        )

    _index_records(plan.get("section_plans"), "section_id", "$.plan.section_plans", issues)
    _index_records(plan.get("gaps_and_risks"), "gap_id", "$.plan.gaps_and_risks", issues)
    _index_records(plan.get("author_decisions"), "decision_id", "$.plan.author_decisions", issues)
    current_outline = plan.get("current_structure_assessment", {}).get("reverse_outline_items", [])
    _index_records(
        current_outline,
        "source_paragraph_id",
        "$.plan.current_structure_assessment.reverse_outline_items",
        issues,
    )

    paragraph_ids: set[str] = set()
    paragraph_assigned_evidence: set[str] = set()
    for section_index, section in enumerate(plan.get("section_plans", [])):
        section_path = f"$.plan.section_plans[{section_index}]"
        for claim_id in sorted(_string_set(section.get("claim_ids")) - set(claims)):
            issues.append(CheckIssue("unknown_section_claim", f"{section_path}.claim_ids", claim_id))
        for paragraph_index, paragraph in enumerate(section.get("paragraph_plans", [])):
            paragraph_path = f"{section_path}.paragraph_plans[{paragraph_index}]"
            paragraph_id = paragraph.get("paragraph_id")
            if isinstance(paragraph_id, str):
                if paragraph_id in paragraph_ids:
                    issues.append(
                        CheckIssue("duplicate_paragraph_id", f"{paragraph_path}.paragraph_id", paragraph_id)
                    )
                paragraph_ids.add(paragraph_id)
            declared_paragraph_claims = _string_set(paragraph.get("claim_ids"))
            for claim_id in sorted(declared_paragraph_claims - set(claims)):
                issues.append(CheckIssue("unknown_paragraph_claim", f"{paragraph_path}.claim_ids", claim_id))
            declared_paragraph_evidence = _string_set(paragraph.get("evidence_ids"))
            paragraph_assigned_evidence |= declared_paragraph_evidence
            valid_paragraph_claims = declared_paragraph_claims & set(claims)
            for evidence_id in sorted(declared_paragraph_evidence):
                if evidence_id not in evidence:
                    issues.append(
                        CheckIssue("unknown_paragraph_evidence", f"{paragraph_path}.evidence_ids", evidence_id)
                    )
                elif not any(
                    (claim_id, evidence_id) in claim_evidence_pairs
                    for claim_id in valid_paragraph_claims
                ):
                    issues.append(
                        CheckIssue(
                            "paragraph_evidence_not_linked_to_claim",
                            f"{paragraph_path}.evidence_ids",
                            f"Evidence has no explicit relation to any claim in this paragraph: {evidence_id}",
                        )
                    )

    _index_records(plan.get("figure_sequence"), "figure_id", "$.plan.figure_sequence", issues)
    figure_orders: set[int] = set()
    figure_assigned_evidence: set[str] = set()
    for figure_index, figure in enumerate(plan.get("figure_sequence", [])):
        path = f"$.plan.figure_sequence[{figure_index}]"
        order = figure.get("order")
        if isinstance(order, int) and not isinstance(order, bool):
            if order in figure_orders:
                issues.append(CheckIssue("duplicate_figure_order", f"{path}.order", f"Duplicate order: {order}"))
            figure_orders.add(order)
        declared_figure_claims = _string_set(figure.get("claim_ids"))
        for claim_id in sorted(declared_figure_claims - set(claims)):
            issues.append(CheckIssue("unknown_figure_claim", f"{path}.claim_ids", claim_id))
        declared_figure_evidence = _string_set(figure.get("evidence_ids"))
        figure_assigned_evidence |= declared_figure_evidence
        valid_figure_claims = declared_figure_claims & set(claims)
        for evidence_id in sorted(declared_figure_evidence):
            if evidence_id not in evidence:
                issues.append(CheckIssue("unknown_figure_evidence", f"{path}.evidence_ids", evidence_id))
            elif not any(
                (claim_id, evidence_id) in claim_evidence_pairs
                for claim_id in valid_figure_claims
            ):
                issues.append(
                    CheckIssue(
                        "figure_evidence_not_linked_to_claim",
                        f"{path}.evidence_ids",
                        f"Evidence has no explicit relation to any claim in this Figure: {evidence_id}",
                    )
                )

    audit = plan.get("evidence_assignment_audit", {})
    assigned = _string_set(audit.get("assigned_evidence_ids"))
    unassigned_records = audit.get("unassigned_evidence", [])
    unassigned_index = _index_records(
        unassigned_records,
        "evidence_id",
        "$.plan.evidence_assignment_audit.unassigned_evidence",
        issues,
    )
    unassigned = set(unassigned_index)
    for evidence_id in sorted((assigned | unassigned) - set(evidence)):
        issues.append(CheckIssue("unknown_audited_evidence", "$.plan.evidence_assignment_audit", evidence_id))
    for evidence_id in sorted(assigned & unassigned):
        issues.append(CheckIssue("evidence_double_assigned", "$.plan.evidence_assignment_audit", evidence_id))
    for evidence_id in sorted(set(evidence) - assigned - unassigned):
        issues.append(CheckIssue("evidence_missing_from_audit", "$.plan.evidence_assignment_audit", evidence_id))
    actual_assignments = paragraph_assigned_evidence | figure_assigned_evidence
    for evidence_id in sorted(assigned - actual_assignments):
        issues.append(
            CheckIssue(
                "evidence_marked_assigned_but_unused",
                "$.plan.evidence_assignment_audit.assigned_evidence_ids",
                f"Evidence is marked assigned but appears in no paragraph or Figure assignment: {evidence_id}",
            )
        )
    for evidence_id in sorted(actual_assignments - assigned):
        issues.append(
            CheckIssue(
                "evidence_used_but_not_marked_assigned",
                "$.plan.evidence_assignment_audit.assigned_evidence_ids",
                f"Evidence is used in the plan but is not marked assigned: {evidence_id}",
            )
        )

    if plan.get("status") == "author_approved":
        summary = plan.get("approval_summary", {})
        if summary.get("overall_status") != "approved":
            issues.append(
                CheckIssue("approved_plan_summary_mismatch", "$.plan.approval_summary.overall_status", "Expected approved.")
            )
        if summary.get("pending_decision_count") != 0 or summary.get("open_blocker_count") != 0:
            issues.append(
                CheckIssue(
                    "approved_plan_has_open_items",
                    "$.plan.approval_summary",
                    "An author-approved plan cannot declare pending decisions or open blockers.",
                )
            )
        for anchor_name in ("central_question", "take_home_message", "novelty_scope"):
            anchor = anchors.get(anchor_name, {})
            if anchor.get("author_approval") != "approved":
                issues.append(
                    CheckIssue(
                        "approved_plan_has_unapproved_anchor",
                        f"$.plan.story_anchors.{anchor_name}.author_approval",
                        "Every story anchor must be approved for an author-approved plan.",
                    )
                )
        if claim_map.get("status") != "author_approved" or any(
            card.get("status") != "author_approved" for card in referenced_cards
        ):
            issues.append(
                CheckIssue(
                    "approved_plan_has_unapproved_sources",
                    "$.plan.source_artifact_ids",
                    "Claim map and referenced interpretation cards must be author approved first.",
                )
            )
        _check_nested_author_approvals(
            claim_map,
            "$.claim_map",
            issues,
        )
        for index, card in enumerate(referenced_cards):
            _check_nested_author_approvals(card, f"$.interpretation_cards[{index}]", issues)
        for field in (
            "frozen_elements",
            "section_plans",
            "figure_sequence",
            "evidence_assignment_audit",
        ):
            _check_nested_author_approvals(plan.get(field), f"$.plan.{field}", issues)

        _check_terminal_decisions(claim_map.get("author_decisions"), "$.claim_map.author_decisions", issues)
        for index, card in enumerate(referenced_cards):
            _check_terminal_decisions(
                card.get("author_decisions"),
                f"$.interpretation_cards[{index}].author_decisions",
                issues,
            )
        _check_terminal_decisions(plan.get("author_decisions"), "$.plan.author_decisions", issues)
        for index, gap in enumerate(plan.get("gaps_and_risks", [])):
            if isinstance(gap, dict) and gap.get("status") not in {"resolved", "accepted_risk"}:
                issues.append(
                    CheckIssue(
                        "approved_plan_has_unresolved_gap",
                        f"$.plan.gaps_and_risks[{index}].status",
                        f"Gap remains {gap.get('status')!r}.",
                    )
                )
        if isinstance(unassigned_records, list):
            for index, record in enumerate(unassigned_records):
                if isinstance(record, dict) and record.get("reason") == "unresolved":
                    issues.append(
                        CheckIssue(
                            "approved_plan_has_unresolved_evidence",
                            f"$.plan.evidence_assignment_audit.unassigned_evidence[{index}].reason",
                            "An author-approved plan cannot retain evidence with reason 'unresolved'.",
                        )
                    )
    return issues


def check_section_coverage(
    claim_map: dict[str, Any], plan: dict[str, Any]
) -> tuple[list[CheckIssue], dict[str, Any]]:
    """Check that key claims and section declarations reach actual paragraph plans."""
    issues: list[CheckIssue] = []
    claims = {
        record["claim_id"]: record
        for record in claim_map.get("claim_records", [])
        if isinstance(record, dict) and isinstance(record.get("claim_id"), str)
    }
    anchors = plan.get("story_anchors", {})
    key_claims = _string_set(anchors.get("key_claim_ids"))
    section_claims: set[str] = set()
    paragraph_claims: set[str] = set()
    paragraph_evidence: set[str] = set()
    figure_claims: set[str] = set()
    figure_evidence: set[str] = set()

    for section_index, section in enumerate(plan.get("section_plans", [])):
        path = f"$.plan.section_plans[{section_index}]"
        declared = _string_set(section.get("claim_ids"))
        section_claims |= declared
        local_paragraph_claims: set[str] = set()
        for paragraph in section.get("paragraph_plans", []):
            local_paragraph_claims |= _string_set(paragraph.get("claim_ids"))
            paragraph_claims |= _string_set(paragraph.get("claim_ids"))
            paragraph_evidence |= _string_set(paragraph.get("evidence_ids"))
        for claim_id in sorted(declared - local_paragraph_claims):
            issues.append(CheckIssue("section_claim_without_paragraph", f"{path}.claim_ids", claim_id))
        for claim_id in sorted(local_paragraph_claims - declared):
            issues.append(CheckIssue("paragraph_claim_not_declared_by_section", path, claim_id))

    for figure in plan.get("figure_sequence", []):
        figure_claims |= _string_set(figure.get("claim_ids"))
        figure_evidence |= _string_set(figure.get("evidence_ids"))

    for claim_id in sorted(key_claims - section_claims):
        issues.append(CheckIssue("key_claim_missing_from_sections", "$.plan.story_anchors.key_claim_ids", claim_id))
    for claim_id in sorted(key_claims - paragraph_claims):
        issues.append(CheckIssue("key_claim_missing_from_paragraphs", "$.plan.story_anchors.key_claim_ids", claim_id))
    for claim_id, claim in claims.items():
        if claim.get("claim_class") in {"central", "primary_result"} and claim_id not in paragraph_claims:
            issues.append(CheckIssue("core_claim_unplanned", "$.plan.section_plans", claim_id))
    for claim_id in sorted(figure_claims - paragraph_claims):
        issues.append(CheckIssue("figure_claim_without_paragraph", "$.plan.figure_sequence", claim_id))
    for evidence_id in sorted(figure_evidence - paragraph_evidence):
        issues.append(CheckIssue("figure_evidence_without_paragraph", "$.plan.figure_sequence", evidence_id))

    summary = {
        "claim_count": len(claims),
        "key_claim_count": len(key_claims),
        "section_count": len(plan.get("section_plans", [])),
        "section_claim_count": len(section_claims),
        "paragraph_claim_count": len(paragraph_claims),
        "paragraph_evidence_count": len(paragraph_evidence),
        "figure_claim_count": len(figure_claims),
        "figure_evidence_count": len(figure_evidence),
    }
    return issues, summary
