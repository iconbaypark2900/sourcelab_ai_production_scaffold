"""Grounding report generator.

Instruction:
- Generate a comprehensive grounding report with verification summary.
- Include trust tier breakdown, conflict table, citation resolution rate.
- Include human review items and release gate status.
- Produce both markdown and JSON outputs.
"""

from __future__ import annotations

from pathlib import Path

from sourcelab.core.models import ClaimRecord
from sourcelab.verification.schemas import (
    CitationResolutionResult,
    ClaimVerificationResult,
    ConflictRecord,
    HumanReviewItem,
    Severity,
    SupportStatus,
    TrustTier,
    TrustTierBreakdown,
    VerificationReport,
    VerificationSummary,
)


def _compute_trust_tier_breakdown(
    results: list[ClaimVerificationResult],
) -> list[TrustTierBreakdown]:
    """Compute trust tier breakdown from verification results."""
    tier_data: dict[str, dict] = {}

    for result in results:
        for match in result.evidence_matches:
            tier = match.trust_tier.value
            if tier not in tier_data:
                tier_data[tier] = {
                    "total": 0,
                    "supported": 0,
                    "unsupported": 0,
                    "uncertain": 0,
                }

            tier_data[tier]["total"] += 1
            if result.support_status == SupportStatus.SUPPORTED:
                tier_data[tier]["supported"] += 1
            elif result.support_status == SupportStatus.UNSUPPORTED:
                tier_data[tier]["unsupported"] += 1
            elif result.support_status == SupportStatus.UNCERTAIN:
                tier_data[tier]["uncertain"] += 1

    breakdowns = []
    for tier in ["A", "B", "C", "D", "E"]:
        if tier in tier_data:
            data = tier_data[tier]
            breakdowns.append(
                TrustTierBreakdown(
                    tier=TrustTier(tier),
                    total_claims=data["total"],
                    supported=data["supported"],
                    unsupported=data["unsupported"],
                    uncertain=data["uncertain"],
                )
            )

    return breakdowns


def _compute_summary(
    results: list[ClaimVerificationResult],
    citation_resolution: CitationResolutionResult,
    conflicts: list[ConflictRecord],
    human_review_items: list[HumanReviewItem],
) -> VerificationSummary:
    """Compute verification summary."""
    total = len(results)
    supported = sum(1 for r in results if r.support_status == SupportStatus.SUPPORTED)
    unsupported = sum(1 for r in results if r.support_status == SupportStatus.UNSUPPORTED)
    uncertain = sum(1 for r in results if r.support_status == SupportStatus.UNCERTAIN)
    conflicting = sum(1 for r in results if r.support_status == SupportStatus.CONFLICTING)

    support_rate = round(supported / total, 4) if total > 0 else 0.0

    high_risk_unsupported = citation_resolution.unsupported_high_risk

    # Determine release gate status
    if high_risk_unsupported > 0:
        release_gate_status = "FAIL"
    elif citation_resolution.resolution_rate < 0.3:
        release_gate_status = "FAIL"
    elif len(conflicts) > 0:
        release_gate_status = "REVIEW"
    elif len(human_review_items) > 0:
        release_gate_status = "REVIEW"
    else:
        release_gate_status = "PASS"

    return VerificationSummary(
        total_claims=total,
        supported=supported,
        unsupported=unsupported,
        uncertain=uncertain,
        conflicting=conflicting,
        support_rate=support_rate,
        high_risk_unsupported=high_risk_unsupported,
        citation_resolution_rate=citation_resolution.resolution_rate,
        human_review_items=len(human_review_items),
        conflicts_detected=len(conflicts),
        release_gate_status=release_gate_status,
    )


def generate_verification_report(
    run_id: str,
    topic: str,
    verification_results: list[ClaimVerificationResult],
    citation_resolution: CitationResolutionResult,
    conflicts: list[ConflictRecord],
    human_review_items: list[HumanReviewItem],
) -> VerificationReport:
    """Generate a complete verification report."""
    summary = _compute_summary(
        verification_results, citation_resolution, conflicts, human_review_items
    )

    trust_tier_breakdown = _compute_trust_tier_breakdown(verification_results)

    blocking_reasons: list[str] = []
    if summary.high_risk_unsupported > 0:
        blocking_reasons.append(
            f"{summary.high_risk_unsupported} high-risk claims unsupported"
        )
    if citation_resolution.resolution_rate < 0.3:
        blocking_reasons.append(
            f"Citation resolution rate {citation_resolution.resolution_rate:.2%} below 80%"
        )

    return VerificationReport(
        run_id=run_id,
        topic=topic,
        summary=summary,
        claims=verification_results,
        citation_resolution=citation_resolution,
        trust_tier_breakdown=trust_tier_breakdown,
        conflicts=conflicts,
        human_review_items=human_review_items,
        release_gate_passed=summary.release_gate_status == "PASS",
        blocking_reasons=blocking_reasons,
    )


def generate_grounding_report_markdown(
    report: VerificationReport,
) -> str:
    """Generate markdown grounding report."""
    lines = [
        "# Grounding Report",
        "",
        f"**Run ID:** {report.run_id}",
        f"**Topic:** {report.topic}",
        f"**Timestamp:** {report.timestamp}",
        "",
        "## Verification Summary",
        "",
        f"- **Total Claims:** {report.summary.total_claims}",
        f"- **Supported:** {report.summary.supported}",
        f"- **Unsupported:** {report.summary.unsupported}",
        f"- **Uncertain:** {report.summary.uncertain}",
        f"- **Conflicting:** {report.summary.conflicting}",
        f"- **Support Rate:** {report.summary.support_rate:.2%}",
        f"- **Citation Resolution Rate:** {report.summary.citation_resolution_rate:.2%}",
        f"- **High-Risk Unsupported:** {report.summary.high_risk_unsupported}",
        f"- **Human Review Items:** {report.summary.human_review_items}",
        f"- **Conflicts Detected:** {report.summary.conflicts_detected}",
        "",
        f"## Release Gate: {report.summary.release_gate_status}",
        "",
    ]

    if report.blocking_reasons:
        lines.append("### Blocking Reasons")
        for reason in report.blocking_reasons:
            lines.append(f"- {reason}")
        lines.append("")

    # Trust tier breakdown
    if report.trust_tier_breakdown:
        lines.append("## Trust Tier Breakdown")
        lines.append("")
        lines.append("| Tier | Total | Supported | Unsupported | Uncertain |")
        lines.append("|------|-------|-----------|-------------|-----------|")
        for tier in report.trust_tier_breakdown:
            lines.append(
                f"| {tier.tier.value} | {tier.total_claims} | "
                f"{tier.supported} | {tier.unsupported} | {tier.uncertain} |"
            )
        lines.append("")

    # Conflicts
    if report.conflicts:
        lines.append("## Conflicts")
        lines.append("")
        for conflict in report.conflicts:
            lines.append(f"### {conflict.conflict_type}")
            lines.append(f"- **Claim 1:** {conflict.claim_text_1}")
            lines.append(f"- **Claim 2:** {conflict.claim_text_2}")
            lines.append(f"- **Severity:** {conflict.severity.value}")
            lines.append("")

    # Human review items
    if report.human_review_items:
        lines.append("## Human Review Items")
        lines.append("")
        for item in report.human_review_items:
            lines.append(f"### {item.item_id}")
            lines.append(f"- **Claim:** {item.claim_text}")
            lines.append(f"- **Reason:** {item.reason}")
            lines.append(f"- **Priority:** {item.priority}")
            lines.append(f"- **Evidence:** {item.evidence_summary}")
            lines.append(f"- **Recommended Action:** {item.recommended_action}")
            lines.append("")

    # Claim details
    if report.claims:
        lines.append("## Claim Details")
        lines.append("")
        lines.append("| Claim | Type | Status | Severity | Score |")
        lines.append("|-------|------|--------|----------|-------|")
        for claim in report.claims:
            text_short = claim.claim_text[:50] + "..." if len(claim.claim_text) > 50 else claim.claim_text
            lines.append(
                f"| {text_short} | {claim.claim_type.value} | "
                f"{claim.support_status.value} | {claim.severity.value} | "
                f"{claim.best_match_score:.2%} |"
            )
        lines.append("")

    return "\n".join(lines)


def generate_grounding_report_from_records(
    run_id: str,
    topic: str,
    claims: list[ClaimRecord],
) -> str:
    """Generate grounding report from legacy ClaimRecord list."""
    lines = [
        "# Grounding Report",
        "",
        f"**Run ID:** {run_id}",
        f"**Topic:** {topic}",
        "",
        "## Claim Summary",
        "",
        f"- **Total Claims:** {len(claims)}",
    ]

    supported = sum(1 for c in claims if c.support_status == "supported")
    unsupported = sum(1 for c in claims if c.support_status == "unsupported")

    lines.extend(
        [
            f"- **Supported:** {supported}",
            f"- **Unsupported:** {unsupported}",
            f"- **Support Rate:** {supported / len(claims):.2%}" if claims else "- **Support Rate:** N/A",
            "",
        ]
    )

    if claims:
        lines.extend(["## Claims", ""])
        for i, claim in enumerate(claims, 1):
            lines.append(f"{i}. **{claim.support_status.upper()}**: {claim.claim}")
            if claim.source_id:
                lines.append(f"   - Source: {claim.source_id}")
            lines.append("")

    return "\n".join(lines)


def write_grounding_report(
    report: VerificationReport,
    run_dir: Path,
) -> tuple[Path, Path]:
    """Write grounding report in both markdown and JSON formats."""
    import json

    # Write markdown
    md_content = generate_grounding_report_markdown(report)
    md_path = run_dir / "grounding_report.md"
    md_path.write_text(md_content, encoding="utf-8")

    # Write JSON
    json_path = run_dir / "grounding_report.json"
    json_path.write_text(
        json.dumps(report.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )

    return md_path, json_path
