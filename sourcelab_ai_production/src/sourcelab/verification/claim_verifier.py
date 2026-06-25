"""Claim verifier.

Instruction:
- Verify every atomic claim against source chunks.
- Preserve backward compatibility with legacy ClaimRecord.
- Mark high-risk unsupported claims for blocking.
"""

from __future__ import annotations

from sourcelab.core.models import ClaimRecord, SearchResult
from sourcelab.generation.schemas import GeneratedLessonPackage
from sourcelab.verification.claim_extractor import extract_all_atomic_claims
from sourcelab.verification.evidence_matcher import match_all_claims, get_best_match
from sourcelab.verification.schemas import (
    AtomicClaim,
    ClaimVerificationResult,
    ClaimType,
    EvidenceMatch,
    Severity,
    SupportStatus,
)


# Threshold for determining support status
STRONG_SUPPORT_THRESHOLD = 0.5
MODERATE_SUPPORT_THRESHOLD = 0.3
WEAK_SUPPORT_THRESHOLD = 0.15

INSTRUCTIONAL_SCAFFOLDING_PATTERNS = (
    "you are a practicing",
    "write a practical explanation that:",
    "reference specific source material",
    "based on the approved sources about",
)


def _is_instructional_scaffolding(claim: AtomicClaim) -> bool:
    """Return True for pedagogical scaffolding that should not require chunk evidence."""
    text_lower = claim.text.lower()
    if claim.origin not in {"lesson", "scenario"}:
        return False
    return any(pattern in text_lower for pattern in INSTRUCTIONAL_SCAFFOLDING_PATTERNS)


class ClaimVerifier:
    """Verifies claims against source chunks."""

    def __init__(
        self,
        strong_threshold: float = STRONG_SUPPORT_THRESHOLD,
        moderate_threshold: float = MODERATE_SUPPORT_THRESHOLD,
    ):
        self.strong_threshold = strong_threshold
        self.moderate_threshold = moderate_threshold

    def _determine_support_status(
        self,
        evidence_matches: list[EvidenceMatch],
        claim_type: ClaimType,
        severity: Severity,
    ) -> tuple[SupportStatus, str | None]:
        """Determine support status based on evidence matches."""
        if not evidence_matches:
            if severity == Severity.HIGH:
                return SupportStatus.UNSUPPORTED, "No evidence found for high-risk claim"
            return SupportStatus.UNSUPPORTED, "No evidence found"

        best_match = evidence_matches[0]
        score = best_match.overlap_score

        # Strong support
        if score >= self.strong_threshold:
            return SupportStatus.SUPPORTED, None

        # Moderate support - may need human review
        if score >= self.moderate_threshold:
            if severity == Severity.HIGH or claim_type == ClaimType.WARNING:
                return SupportStatus.UNCERTAIN, "Moderate support for high-risk claim"
            return SupportStatus.SUPPORTED, None

        # Weak support
        if score >= WEAK_SUPPORT_THRESHOLD:
            if severity == Severity.HIGH:
                return SupportStatus.UNSUPPORTED, "Weak support for high-risk claim"
            return SupportStatus.UNCERTAIN, "Weak support"

        # Very weak or no support
        if severity == Severity.HIGH:
            return SupportStatus.UNSUPPORTED, "Insufficient evidence for high-risk claim"
        return SupportStatus.UNCERTAIN, "Insufficient evidence"

    def _needs_human_review(
        self,
        support_status: SupportStatus,
        severity: Severity,
        claim_type: ClaimType,
        evidence_matches: list[EvidenceMatch],
    ) -> tuple[bool, str | None]:
        """Determine if claim needs human review."""
        # High-risk uncertain claims need review
        if support_status == SupportStatus.UNCERTAIN and severity == Severity.HIGH:
            return True, "High-risk claim with uncertain support"

        # Warnings always need review if not strongly supported
        if claim_type == ClaimType.WARNING and support_status != SupportStatus.SUPPORTED:
            return True, "Warning claim needs verification"

        # Risk statements need review if weakly supported
        if claim_type == ClaimType.RISK_STATEMENT and support_status == SupportStatus.UNCERTAIN:
            return True, "Risk statement needs verification"

        # Multiple conflicting matches need review
        if len(evidence_matches) >= 3:
            top_scores = [m.overlap_score for m in evidence_matches[:3]]
            if max(top_scores) - min(top_scores) < 0.1:
                return True, "Multiple similar matches detected"

        return False, None

    def verify_claim(
        self,
        claim: AtomicClaim,
        evidence_matches: list[EvidenceMatch],
    ) -> ClaimVerificationResult:
        """Verify a single atomic claim."""
        if _is_instructional_scaffolding(claim):
            return ClaimVerificationResult(
                claim_id=claim.claim_id,
                claim_text=claim.text,
                claim_type=claim.claim_type,
                support_status=SupportStatus.SUPPORTED,
                severity=claim.severity,
                evidence_matches=evidence_matches,
                best_match_score=round(
                    evidence_matches[0].overlap_score if evidence_matches else 1.0,
                    4,
                ),
                requires_human_review=False,
                review_reason=None,
            )

        support_status, review_reason = self._determine_support_status(
            evidence_matches, claim.claim_type, claim.severity
        )

        needs_review, review_reason = self._needs_human_review(
            support_status, claim.severity, claim.claim_type, evidence_matches
        )

        best_match_score = evidence_matches[0].overlap_score if evidence_matches else 0.0

        return ClaimVerificationResult(
            claim_id=claim.claim_id,
            claim_text=claim.text,
            claim_type=claim.claim_type,
            support_status=support_status,
            severity=claim.severity,
            evidence_matches=evidence_matches,
            best_match_score=round(best_match_score, 4),
            requires_human_review=needs_review,
            review_reason=review_reason,
        )

    def verify_all_claims(
        self,
        claims: list[AtomicClaim],
        evidence_map: dict[str, list[EvidenceMatch]],
    ) -> list[ClaimVerificationResult]:
        """Verify all claims against their evidence matches."""
        results: list[ClaimVerificationResult] = []

        for claim in claims:
            matches = evidence_map.get(claim.claim_id, [])
            result = self.verify_claim(claim, matches)
            results.append(result)

        return results

    def verify_lesson_package(
        self,
        package: GeneratedLessonPackage,
        search_results: list[SearchResult],
    ) -> list[ClaimRecord]:
        """Verify claims from a lesson package (backward compatible).

        Returns a list of ClaimRecord for compatibility with existing code.
        """
        # Extract atomic claims
        claims = extract_all_atomic_claims(package)

        # If no claims extracted, create a single unsupported claim
        if not claims:
            return [
                ClaimRecord(
                    claim="No claims extracted from lesson package",
                    support_status="unsupported",
                    severity="high",
                )
            ]

        # Match claims to chunks
        evidence_map = match_all_claims(claims, search_results)

        # Verify claims
        verification_results = self.verify_all_claims(claims, evidence_map)

        # Convert to ClaimRecord for backward compatibility
        claim_records: list[ClaimRecord] = []
        for result in verification_results:
            # Get best match for source/chunk info
            best_match = result.evidence_matches[0] if result.evidence_matches else None

            claim_records.append(
                ClaimRecord(
                    claim=result.claim_text,
                    support_status=result.support_status.value,
                    source_id=best_match.source_id if best_match else None,
                    chunk_id=best_match.chunk_id if best_match else None,
                    trust_tier=best_match.trust_tier.value if best_match else None,
                    severity=result.severity.value,
                )
            )

        return claim_records

    def verify_lesson(
        self,
        lesson,
        search_results: list[SearchResult],
    ) -> list[ClaimRecord]:
        """Verify claims from lesson (backward compatible).

        Accepts either a string or a LessonTask object.
        Returns a list of ClaimRecord for compatibility with existing code.
        """
        from sourcelab.core.models import LessonTask
        from sourcelab.verification.claim_extractor import extract_claims

        # Handle both string and LessonTask objects
        if isinstance(lesson, LessonTask):
            lesson_text = f"{lesson.title} {lesson.scenario} {lesson.task} {lesson.expected_behavior} {lesson.failure_trap}"
        elif isinstance(lesson, str):
            lesson_text = lesson
        else:
            lesson_text = str(lesson)

        # Extract claims using legacy method
        raw_claims = extract_claims(lesson_text)

        if not raw_claims:
            return [
                ClaimRecord(
                    claim="No claims extracted from lesson",
                    support_status="unsupported",
                    severity="high",
                )
            ]

        # Convert to AtomicClaim objects
        atomic_claims = [
            AtomicClaim(
                claim_id=f"legacy_{i}",
                text=claim,
                claim_type=ClaimType.FACT,
                severity=Severity.MEDIUM,
            )
            for i, claim in enumerate(raw_claims)
        ]

        # Match and verify
        evidence_map = match_all_claims(atomic_claims, search_results)
        verification_results = self.verify_all_claims(atomic_claims, evidence_map)

        # Convert to ClaimRecord
        claim_records: list[ClaimRecord] = []
        for result in verification_results:
            best_match = result.evidence_matches[0] if result.evidence_matches else None

            claim_records.append(
                ClaimRecord(
                    claim=result.claim_text,
                    support_status=result.support_status.value,
                    source_id=best_match.source_id if best_match else None,
                    chunk_id=best_match.chunk_id if best_match else None,
                    trust_tier=best_match.trust_tier.value if best_match else None,
                    severity=result.severity.value,
                )
            )

        return claim_records
