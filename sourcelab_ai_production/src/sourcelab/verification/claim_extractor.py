"""Claim extractor.

Instruction:
- Extract atomic claims from generated lessons, answer keys, and scenarios.
- Classify claims by type: definition, recommendation, risk_statement, process_step, warning, fact, unsupported_example.
- Preserve source IDs, chunk IDs, and trust tiers for verification.
"""

from __future__ import annotations

import re
import uuid

from sourcelab.generation.schemas import (
    ClaimCandidate,
    GeneratedAnswerKey,
    GeneratedLesson,
    GeneratedLessonPackage,
    GeneratedScenario,
)
from sourcelab.verification.schemas import AtomicClaim, ClaimType, Severity, TrustTier


def _generate_claim_id() -> str:
    """Generate a unique claim ID."""
    return f"claim_{uuid.uuid4().hex[:12]}"


def _classify_claim_type(text: str) -> ClaimType:
    """Classify a claim by its type based on content patterns."""
    text_lower = text.lower()

    # Definition patterns
    if any(
        phrase in text_lower
        for phrase in ["is defined as", "means", "refers to", "is a type of", "is characterized by"]
    ):
        return ClaimType.DEFINITION

    # Warning patterns
    if any(
        phrase in text_lower
        for phrase in [
            "should not",
            "must not",
            "avoid",
            "danger",
            "risk of",
            "warning",
            "caution",
            "do not",
        ]
    ):
        return ClaimType.WARNING

    # Risk statement patterns
    if any(
        phrase in text_lower
        for phrase in [
            "risk",
            "vulnerability",
            "threat",
            "exposure",
            "compromise",
            "failure",
            "attack",
        ]
    ):
        return ClaimType.RISK_STATEMENT

    # Recommendation patterns
    if any(
        phrase in text_lower
        for phrase in ["should", "must", "recommend", "advise", "best practice", "important to"]
    ):
        return ClaimType.RECOMMENDATION

    # Process step patterns
    if any(
        phrase in text_lower
        for phrase in [
            "step",
            "first",
            "second",
            "then",
            "next",
            "finally",
            "process",
            "procedure",
            "workflow",
        ]
    ):
        return ClaimType.PROCESS_STEP

    # Default to fact
    return ClaimType.FACT


def _assess_severity(text: str, claim_type: ClaimType) -> Severity:
    """Assess claim severity based on content and type."""
    text_lower = text.lower()

    # High severity for critical warnings and risk statements
    if claim_type == ClaimType.WARNING and any(
        word in text_lower for word in ["critical", "severe", "catastrophic", "fatal"]
    ):
        return Severity.HIGH

    # High severity for explicit vulnerability/breach claims (not just topic mentions)
    if any(
        phrase in text_lower
        for phrase in [
            "vulnerability",
            "breach",
            "attack vector",
            "compromised",
            "exploit",
            "insecure",
        ]
    ):
        return Severity.HIGH

    # Medium severity for recommendations and risk statements
    if claim_type in (ClaimType.RECOMMENDATION, ClaimType.RISK_STATEMENT):
        return Severity.MEDIUM

    return Severity.LOW


def extract_atomic_claims_from_lesson(
    lesson: GeneratedLesson,
    source_ids: list[str] | None = None,
    chunk_ids: list[str] | None = None,
) -> list[AtomicClaim]:
    """Extract atomic claims from a generated lesson."""
    claims: list[AtomicClaim] = []

    # Extract from learning objectives
    for obj in lesson.learning_objectives:
        claim_id = _generate_claim_id()
        claim_type = _classify_claim_type(obj)
        severity = _assess_severity(obj, claim_type)
        claims.append(
            AtomicClaim(
                claim_id=claim_id,
                text=obj,
                claim_type=claim_type,
                severity=severity,
                source_id=source_ids[0] if source_ids else None,
                chunk_id=chunk_ids[0] if chunk_ids else None,
                origin="lesson",
                confidence=0.6,
            )
        )

    # Extract from required source concepts
    for concept in lesson.required_source_concepts:
        claim_id = _generate_claim_id()
        claims.append(
            AtomicClaim(
                claim_id=claim_id,
                text=concept,
                claim_type=ClaimType.DEFINITION,
                severity=Severity.LOW,
                source_id=source_ids[0] if source_ids else None,
                chunk_id=chunk_ids[0] if chunk_ids else None,
                origin="lesson",
                confidence=0.7,
            )
        )

    # Extract from task instructions (if they contain claims)
    if lesson.task_instructions:
        sentences = re.split(r"(?<=[.!?])\s+", lesson.task_instructions.strip())
        for sent in sentences:
            sent = sent.strip()
            if len(sent) > 20:
                claim_id = _generate_claim_id()
                claim_type = _classify_claim_type(sent)
                severity = _assess_severity(sent, claim_type)
                claims.append(
                    AtomicClaim(
                        claim_id=claim_id,
                        text=sent,
                        claim_type=claim_type,
                        severity=severity,
                        source_id=source_ids[0] if source_ids else None,
                        chunk_id=chunk_ids[0] if chunk_ids else None,
                        origin="lesson",
                        confidence=0.5,
                    )
                )

    return claims


def extract_atomic_claims_from_answer_key(
    answer_key: GeneratedAnswerKey,
) -> list[AtomicClaim]:
    """Extract atomic claims from an answer key."""
    claims: list[AtomicClaim] = []

    # Extract facts as claims
    for fact in answer_key.facts:
        claim_id = _generate_claim_id()
        claims.append(
            AtomicClaim(
                claim_id=claim_id,
                text=fact,
                claim_type=ClaimType.FACT,
                severity=Severity.LOW,
                origin="answer_key",
                confidence=0.8,
            )
        )

    # Extract assumptions as claims
    for assumption in answer_key.assumptions:
        claim_id = _generate_claim_id()
        claims.append(
            AtomicClaim(
                claim_id=claim_id,
                text=assumption,
                claim_type=ClaimType.RECOMMENDATION,
                severity=Severity.MEDIUM,
                origin="answer_key",
                confidence=0.6,
            )
        )

    # Extract warnings from what_not_to_claim
    for warning in answer_key.what_not_to_claim:
        claim_id = _generate_claim_id()
        claims.append(
            AtomicClaim(
                claim_id=claim_id,
                text=warning,
                claim_type=ClaimType.WARNING,
                severity=Severity.HIGH,
                origin="answer_key",
                confidence=0.9,
            )
        )

    # Extract source references as claims
    for ref in answer_key.source_references:
        claim_id = _generate_claim_id()
        claims.append(
            AtomicClaim(
                claim_id=claim_id,
                text=ref.claim,
                claim_type=ClaimType.FACT,
                severity=Severity.LOW,
                source_id=ref.source_id,
                chunk_id=ref.chunk_id,
                trust_tier=TrustTier(ref.trust_tier) if ref.trust_tier else None,
                origin="answer_key",
                confidence=0.9,
            )
        )

    return claims


def extract_atomic_claims_from_scenario(
    scenario: GeneratedScenario,
) -> list[AtomicClaim]:
    """Extract atomic claims from a scenario."""
    claims: list[AtomicClaim] = []

    # Extract from context
    if scenario.context:
        sentences = re.split(r"(?<=[.!?])\s+", scenario.context.strip())
        for sent in sentences:
            sent = sent.strip()
            if len(sent) > 20:
                claim_id = _generate_claim_id()
                claim_type = _classify_claim_type(sent)
                severity = _assess_severity(sent, claim_type)
                claims.append(
                    AtomicClaim(
                        claim_id=claim_id,
                        text=sent,
                        claim_type=claim_type,
                        severity=severity,
                        source_id=scenario.source_ids[0] if scenario.source_ids else None,
                        chunk_id=scenario.chunk_ids[0] if scenario.chunk_ids else None,
                        origin="scenario",
                        confidence=0.5,
                    )
                )

    return claims


def extract_all_atomic_claims(
    package: GeneratedLessonPackage,
) -> list[AtomicClaim]:
    """Extract all atomic claims from a lesson package."""
    all_claims: list[AtomicClaim] = []

    if package.lesson:
        all_claims.extend(
            extract_atomic_claims_from_lesson(
                package.lesson,
                source_ids=package.source_ids,
                chunk_ids=package.chunk_ids,
            )
        )

    if package.answer_key:
        all_claims.extend(extract_atomic_claims_from_answer_key(package.answer_key))

    if package.scenario:
        all_claims.extend(extract_atomic_claims_from_scenario(package.scenario))

    return all_claims


def extract_claims(text: str) -> list[str]:
    """Legacy claim extraction for backward compatibility."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 20]
