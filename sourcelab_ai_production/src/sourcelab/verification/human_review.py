"""Human review queue builder.

Instruction:
- Build a queue of items requiring human review.
- Prioritize items by severity and claim type.
- Write human_review_queue.json for the harness.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from sourcelab.verification.schemas import (
    ClaimVerificationResult,
    ConflictRecord,
    HumanReviewItem,
    Severity,
    SupportStatus,
)


def _generate_item_id() -> str:
    """Generate a unique review item ID."""
    return f"review_{uuid.uuid4().hex[:12]}"


def _determine_priority(
    severity: Severity,
    support_status: SupportStatus,
    claim_type: str,
) -> str:
    """Determine review priority based on claim characteristics."""
    # High severity unsupported claims get high priority
    if severity == Severity.HIGH and support_status == SupportStatus.UNSUPPORTED:
        return "high"

    # Warnings always get at least medium priority
    if claim_type == "warning":
        return "high" if severity == Severity.HIGH else "medium"

    # Risk statements get medium priority if uncertain
    if claim_type == "risk_statement" and support_status == SupportStatus.UNCERTAIN:
        return "medium"

    # Conflicts get high priority
    if support_status == SupportStatus.CONFLICTING:
        return "high"

    # Default to low
    return "low"


def _build_evidence_summary(
    result: ClaimVerificationResult,
) -> str:
    """Build a summary of evidence for a claim."""
    if not result.evidence_matches:
        return "No evidence matches found."

    best_match = result.evidence_matches[0]
    summary_parts = [
        f"Best match score: {result.best_match_score:.2%}",
        f"Source: {best_match.source_id}",
        f"Trust tier: {best_match.trust_tier.value}",
    ]

    if best_match.phrase_matches:
        summary_parts.append(f"Phrase matches: {', '.join(best_match.phrase_matches[:3])}")

    return "; ".join(summary_parts)


def _build_recommended_action(
    result: ClaimVerificationResult,
) -> str:
    """Build recommended action for a claim."""
    if result.support_status == SupportStatus.UNSUPPORTED:
        return "Remove claim or add source evidence"
    elif result.support_status == SupportStatus.UNCERTAIN:
        return "Verify claim accuracy or strengthen evidence"
    elif result.requires_human_review:
        return "Review for accuracy and completeness"
    else:
        return "No action required"


def build_review_items_from_verification(
    results: list[ClaimVerificationResult],
) -> list[HumanReviewItem]:
    """Build review items from verification results."""
    items: list[HumanReviewItem] = []

    for result in results:
        if not result.requires_human_review:
            continue

        item = HumanReviewItem(
            item_id=_generate_item_id(),
            claim_id=result.claim_id,
            claim_text=result.claim_text,
            reason=result.review_reason or "Requires human review",
            priority=_determine_priority(
                result.severity, result.support_status, result.claim_type.value
            ),
            evidence_summary=_build_evidence_summary(result),
            recommended_action=_build_recommended_action(result),
        )
        items.append(item)

    return items


def build_review_items_from_conflicts(
    conflicts: list[ConflictRecord],
) -> list[HumanReviewItem]:
    """Build review items from detected conflicts."""
    items: list[HumanReviewItem] = []

    for conflict in conflicts:
        item = HumanReviewItem(
            item_id=_generate_item_id(),
            claim_id=conflict.claim_id_1,
            claim_text=f"Conflict: {conflict.claim_text_1} vs {conflict.claim_text_2}",
            reason=f"Detected {conflict.conflict_type} conflict",
            priority="high" if conflict.severity == Severity.HIGH else "medium",
            evidence_summary=f"Conflict type: {conflict.conflict_type}",
            recommended_action="Resolve contradiction between claims",
        )
        items.append(item)

    return items


def build_human_review_queue(
    verification_results: list[ClaimVerificationResult],
    conflicts: list[ConflictRecord],
) -> list[HumanReviewItem]:
    """Build the complete human review queue."""
    items: list[HumanReviewItem] = []

    # Add items from verification results
    items.extend(build_review_items_from_verification(verification_results))

    # Add items from conflicts
    items.extend(build_review_items_from_conflicts(conflicts))

    # Sort by priority (high first)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda x: priority_order.get(x.priority, 3))

    return items


def write_review_queue(
    items: list[HumanReviewItem],
    run_dir: Path,
) -> Path:
    """Write the human review queue to a JSON file."""
    import json

    queue_data = {
        "total_items": len(items),
        "high_priority": sum(1 for i in items if i.priority == "high"),
        "medium_priority": sum(1 for i in items if i.priority == "medium"),
        "low_priority": sum(1 for i in items if i.priority == "low"),
        "items": [item.model_dump() for item in items],
    }

    queue_path = run_dir / "human_review_queue.json"
    queue_path.write_text(json.dumps(queue_data, indent=2), encoding="utf-8")

    return queue_path
