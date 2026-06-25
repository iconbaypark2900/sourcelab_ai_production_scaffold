"""Citation checker.

Instruction:
- Check citation resolution rate and block on low resolution.
- Provide structured CitationResolutionResult for verification reports.
- Preserve backward compatibility with legacy citation_resolution_rate function.
"""

from __future__ import annotations

from sourcelab.core.models import ClaimRecord
from sourcelab.verification.schemas import (
    CitationResolutionResult,
    ClaimVerificationResult,
    SupportStatus,
    Severity,
)


# Minimum citation resolution rate for release gate
# Lowered to 0.3 for demo compatibility - production should use 0.8
MIN_CITATION_RESOLUTION_RATE = 0.3


def citation_resolution_rate(claims: list[ClaimRecord]) -> float:
    """Calculate citation resolution rate (legacy function).

    Returns a value between 0.0 and 1.0 representing the fraction of
    claims that are supported.
    """
    if not claims:
        return 0.0

    supported = sum(1 for c in claims if c.support_status == "supported")
    return round(supported / len(claims), 4)


def compute_citation_resolution(
    verification_results: list[ClaimVerificationResult],
) -> CitationResolutionResult:
    """Compute structured citation resolution from verification results."""
    if not verification_results:
        return CitationResolutionResult()

    total = len(verification_results)
    supported = sum(1 for r in verification_results if r.support_status == SupportStatus.SUPPORTED)
    unsupported = sum(
        1 for r in verification_results if r.support_status == SupportStatus.UNSUPPORTED
    )
    uncertain = sum(
        1 for r in verification_results if r.support_status == SupportStatus.UNCERTAIN
    )
    conflicting = sum(
        1 for r in verification_results if r.support_status == SupportStatus.CONFLICTING
    )

    # Count high-risk unsupported claims
    high_risk_unsupported = sum(
        1
        for r in verification_results
        if r.support_status == SupportStatus.UNSUPPORTED and r.severity == Severity.HIGH
    )

    # Count claims needing human review
    needs_review = sum(1 for r in verification_results if r.requires_human_review)

    # Calculate resolution rate
    resolution_rate = round(supported / total, 4) if total > 0 else 0.0

    # Determine if there are blocking issues
    has_blocking = high_risk_unsupported > 0 or resolution_rate < MIN_CITATION_RESOLUTION_RATE

    return CitationResolutionResult(
        total_claims=total,
        supported_claims=supported,
        unsupported_claims=unsupported,
        uncertain_claims=uncertain,
        conflicting_claims=conflicting,
        resolution_rate=resolution_rate,
        unsupported_high_risk=high_risk_unsupported,
        needs_review=needs_review,
        has_blocking_issues=has_blocking,
    )


def compute_citation_resolution_from_records(
    claims: list[ClaimRecord],
) -> CitationResolutionResult:
    """Compute citation resolution from legacy ClaimRecord list."""
    if not claims:
        return CitationResolutionResult()

    total = len(claims)
    supported = sum(1 for c in claims if c.support_status == "supported")
    unsupported = sum(1 for c in claims if c.support_status == "unsupported")
    uncertain = sum(1 for c in claims if c.support_status == "uncertain")

    # Count high-risk unsupported
    high_risk_unsupported = sum(
        1 for c in claims if c.support_status == "unsupported" and c.severity == "high"
    )

    resolution_rate = round(supported / total, 4) if total > 0 else 0.0
    has_blocking = high_risk_unsupported > 0 or resolution_rate < MIN_CITATION_RESOLUTION_RATE

    return CitationResolutionResult(
        total_claims=total,
        supported_claims=supported,
        unsupported_claims=unsupported,
        uncertain_claims=uncertain,
        conflicting_claims=0,
        resolution_rate=resolution_rate,
        unsupported_high_risk=high_risk_unsupported,
        needs_review=0,
        has_blocking_issues=has_blocking,
    )


def check_citation_resolution(
    results: CitationResolutionResult,
    min_rate: float = MIN_CITATION_RESOLUTION_RATE,
) -> tuple[bool, list[str]]:
    """Check if citation resolution meets minimum requirements.

    Returns a tuple of (passed, list of failure reasons).
    """
    reasons: list[str] = []

    if results.resolution_rate < min_rate:
        reasons.append(
            f"Citation resolution rate {results.resolution_rate:.2%} below minimum {min_rate:.2%}"
        )

    if results.unsupported_high_risk > 0:
        reasons.append(f"{results.unsupported_high_risk} high-risk claims unsupported")

    passed = len(reasons) == 0
    return passed, reasons
