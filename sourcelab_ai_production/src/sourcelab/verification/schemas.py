"""Verification schemas for claim verification and grounding.

Instruction:
- These schemas define the complete verification v2 output.
- Every field must be serializable to JSON for the proof bundle.
- Keep schemas explicit so the harness can validate them.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    """Types of atomic claims extracted from lessons."""

    DEFINITION = "definition"
    RECOMMENDATION = "recommendation"
    RISK_STATEMENT = "risk_statement"
    PROCESS_STEP = "process_step"
    WARNING = "warning"
    FACT = "fact"
    UNSUPPORTED_EXAMPLE = "unsupported_example"


class SupportStatus(str, Enum):
    """Verification support status for claims."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNCERTAIN = "uncertain"
    CONFLICTING = "conflicting"


class Severity(str, Enum):
    """Claim severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TrustTier(str, Enum):
    """Source trust tiers."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class AtomicClaim(BaseModel):
    """An atomic claim extracted from a generated lesson or answer key."""

    claim_id: str
    text: str
    claim_type: ClaimType
    severity: Severity = Severity.MEDIUM
    source_id: str | None = None
    chunk_id: str | None = None
    trust_tier: TrustTier | None = None
    origin: Literal["lesson", "answer_key", "scenario"] = "lesson"
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class EvidenceMatch(BaseModel):
    """A match between a claim and a source chunk."""

    claim_id: str
    chunk_id: str
    source_id: str
    trust_tier: TrustTier
    overlap_score: float = Field(ge=0.0, le=1.0)
    phrase_matches: list[str] = Field(default_factory=list)
    match_quality: Literal["strong", "moderate", "weak"] = "moderate"


class ClaimVerificationResult(BaseModel):
    """Result of verifying a single atomic claim."""

    claim_id: str
    claim_text: str
    claim_type: ClaimType
    support_status: SupportStatus
    severity: Severity
    evidence_matches: list[EvidenceMatch] = Field(default_factory=list)
    best_match_score: float = Field(ge=0.0, le=1.0, default=0.0)
    requires_human_review: bool = False
    review_reason: str | None = None


class CitationResolutionResult(BaseModel):
    """Result of citation resolution across all claims."""

    total_claims: int = 0
    supported_claims: int = 0
    unsupported_claims: int = 0
    uncertain_claims: int = 0
    conflicting_claims: int = 0
    resolution_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    unsupported_high_risk: int = 0
    needs_review: int = 0
    has_blocking_issues: bool = False


class ConflictRecord(BaseModel):
    """A detected contradiction between claims."""

    conflict_id: str
    claim_id_1: str
    claim_id_2: str
    claim_text_1: str
    claim_text_2: str
    conflict_type: Literal["must_must_not", "safe_unsafe", "rsa_contradiction", "other"]
    severity: Severity
    requires_resolution: bool = True


class HumanReviewItem(BaseModel):
    """An item requiring human review."""

    item_id: str
    claim_id: str
    claim_text: str
    reason: str
    priority: Literal["low", "medium", "high"] = "medium"
    evidence_summary: str = ""
    recommended_action: str = ""


class TrustTierBreakdown(BaseModel):
    """Breakdown of claims by trust tier."""

    tier: TrustTier
    total_claims: int = 0
    supported: int = 0
    unsupported: int = 0
    uncertain: int = 0


class VerificationSummary(BaseModel):
    """Summary of the verification process."""

    total_claims: int = 0
    supported: int = 0
    unsupported: int = 0
    uncertain: int = 0
    conflicting: int = 0
    support_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    high_risk_unsupported: int = 0
    citation_resolution_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    human_review_items: int = 0
    conflicts_detected: int = 0
    release_gate_status: Literal["PASS", "FAIL", "REVIEW"] = "FAIL"


class VerificationReport(BaseModel):
    """Complete verification report for a generation run."""

    run_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    topic: str = ""
    summary: VerificationSummary = Field(default_factory=VerificationSummary)
    claims: list[ClaimVerificationResult] = Field(default_factory=list)
    citation_resolution: CitationResolutionResult = Field(default_factory=CitationResolutionResult)
    trust_tier_breakdown: list[TrustTierBreakdown] = Field(default_factory=list)
    conflicts: list[ConflictRecord] = Field(default_factory=list)
    human_review_items: list[HumanReviewItem] = Field(default_factory=list)
    release_gate_passed: bool = False
    blocking_reasons: list[str] = Field(default_factory=list)
