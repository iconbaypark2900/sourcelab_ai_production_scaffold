"""sourcelab.verification package.

Instruction:
- This package handles claim verification, citation checking, and grounding reports.
- Use the schemas module for all data models.
"""

from sourcelab.verification.schemas import (
    AtomicClaim,
    ClaimType,
    ClaimVerificationResult,
    CitationResolutionResult,
    ConflictRecord,
    EvidenceMatch,
    HumanReviewItem,
    SupportStatus,
    TrustTierBreakdown,
    VerificationReport,
    VerificationSummary,
)

__all__ = [
    "AtomicClaim",
    "ClaimType",
    "ClaimVerificationResult",
    "CitationResolutionResult",
    "ConflictRecord",
    "EvidenceMatch",
    "HumanReviewItem",
    "SupportStatus",
    "TrustTierBreakdown",
    "VerificationReport",
    "VerificationSummary",
]
