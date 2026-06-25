"""Conflict detector for contradiction detection.

Instruction:
- Detect contradictions between claims.
- Identify must/must-not, safe/unsafe, and RSA-related contradictions.
- Produce ConflictRecord list for verification reports.
"""

from __future__ import annotations

import re
import uuid

from sourcelab.verification.schemas import (
    AtomicClaim,
    ClaimType,
    ConflictRecord,
    Severity,
)


# Patterns that indicate negation or opposition
NEGATION_PATTERNS = [
    r"\bshould not\b",
    r"\bmust not\b",
    r"\bdo not\b",
    r"\bcannot\b",
    r"\bnever\b",
    r"\bavoid\b",
    r"\bprohibited\b",
    r"\bforbidden\b",
]

# Patterns that indicate positive assertion
AFFIRMATION_PATTERNS = [
    r"\bshould\b",
    r"\bmust\b",
    r"\bcan\b",
    r"\balways\b",
    r"\brecommended\b",
    r"\brequired\b",
    r"\bmandatory\b",
]

# RSA-related patterns
RSA_PATTERNS = [
    r"\brsa\b",
    r"\brsa-?\d+\b",
    r"\bpublic key\b",
    r"\basymmetric\b",
    r"\bquantum\b",
    r"\bpq[c ]?\b",
]

# Safety-related patterns
SAFETY_PATTERNS = [
    r"\bsafe\b",
    r"\bsecure\b",
    r"\bunsafe\b",
    r"\binsecure\b",
    r"\bvulnerability\b",
    r"\battack\b",
    r"\bbreach\b",
]


def _has_negation(text: str) -> bool:
    """Check if text contains negation patterns."""
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in NEGATION_PATTERNS)


def _has_affirmation(text: str) -> bool:
    """Check if text contains affirmation patterns."""
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in AFFIRMATION_PATTERNS)


def _has_rsa_reference(text: str) -> bool:
    """Check if text references RSA or post-quantum cryptography."""
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in RSA_PATTERNS)


def _has_safety_reference(text: str) -> bool:
    """Check if text references safety or security."""
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in SAFETY_PATTERNS)


def _extract_subject(text: str) -> str:
    """Extract the main subject from a claim sentence."""
    # Simple heuristic: take the first few words
    words = text.split()
    if len(words) <= 3:
        return text
    return " ".join(words[:4])


def _subjects_match(subject1: str, subject2: str) -> bool:
    """Check if two subjects are similar enough to compare."""
    # Simple token overlap check
    tokens1 = set(subject1.lower().split())
    tokens2 = set(subject2.lower().split())

    if not tokens1 or not tokens2:
        return False

    overlap = len(tokens1.intersection(tokens2))
    min_len = min(len(tokens1), len(tokens2))

    return overlap / min_len >= 0.5


def detect_must_must_not_conflicts(
    claims: list[AtomicClaim],
) -> list[ConflictRecord]:
    """Detect must/must-not contradictions between claims."""
    conflicts: list[ConflictRecord] = []

    for i, claim1 in enumerate(claims):
        for claim2 in claims[i + 1 :]:
            # Check if one has negation and other doesn't
            has_neg1 = _has_negation(claim1.text)
            has_neg2 = _has_negation(claim2.text)

            if has_neg1 == has_neg2:
                continue  # Both have negation or both don't

            # Check if subjects match
            subject1 = _extract_subject(claim1.text)
            subject2 = _extract_subject(claim2.text)

            if not _subjects_match(subject1, subject2):
                continue

            # Determine conflict type
            conflict_type = "must_must_not"

            conflicts.append(
                ConflictRecord(
                    conflict_id=f"conflict_{uuid.uuid4().hex[:8]}",
                    claim_id_1=claim1.claim_id,
                    claim_id_2=claim2.claim_id,
                    claim_text_1=claim1.text,
                    claim_text_2=claim2.text,
                    conflict_type=conflict_type,
                    severity=Severity.HIGH,
                    requires_resolution=True,
                )
            )

    return conflicts


def detect_safe_unsafe_conflicts(
    claims: list[AtomicClaim],
) -> list[ConflictRecord]:
    """Detect safe/unsafe contradictions between claims."""
    conflicts: list[ConflictRecord] = []

    for i, claim1 in enumerate(claims):
        for claim2 in claims[i + 1 :]:
            # Check for safety references
            has_safety1 = _has_safety_reference(claim1.text)
            has_safety2 = _has_safety_reference(claim2.text)

            if not (has_safety1 and has_safety2):
                continue

            # Check for conflicting safety assertions
            text1_lower = claim1.text.lower()
            text2_lower = claim2.text.lower()

            safe1 = "safe" in text1_lower or "secure" in text1_lower
            unsafe1 = "unsafe" in text1_lower or "insecure" in text1_lower
            safe2 = "safe" in text2_lower or "secure" in text2_lower
            unsafe2 = "unsafe" in text2_lower or "insecure" in text2_lower

            if (safe1 and unsafe2) or (unsafe1 and safe2):
                conflicts.append(
                    ConflictRecord(
                        conflict_id=f"conflict_{uuid.uuid4().hex[:8]}",
                        claim_id_1=claim1.claim_id,
                        claim_id_2=claim2.claim_id,
                        claim_text_1=claim1.text,
                        claim_text_2=claim2.text,
                        conflict_type="safe_unsafe",
                        severity=Severity.HIGH,
                        requires_resolution=True,
                    )
                )

    return conflicts


def detect_rsa_contradictions(
    claims: list[AtomicClaim],
) -> list[ConflictRecord]:
    """Detect RSA-related contradictions (e.g., quantum-safe vs vulnerable)."""
    conflicts: list[ConflictRecord] = []

    # Filter claims that mention RSA or quantum
    rsa_claims = [c for c in claims if _has_rsa_reference(c.text)]

    for i, claim1 in enumerate(rsa_claims):
        for claim2 in rsa_claims[i + 1 :]:
            text1_lower = claim1.text.lower()
            text2_lower = claim2.text.lower()

            # Check for quantum safety contradictions
            quantum_safe1 = "quantum" in text1_lower and (
                "safe" in text1_lower or "resistant" in text1_lower
            )
            quantum_safe2 = "quantum" in text2_lower and (
                "safe" in text2_lower or "resistant" in text2_lower
            )
            quantum_vulnerable1 = "quantum" in text1_lower and (
                "vulnerable" in text1_lower or "break" in text1_lower
            )
            quantum_vulnerable2 = "quantum" in text2_lower and (
                "vulnerable" in text2_lower or "break" in text2_lower
            )

            if (quantum_safe1 and quantum_vulnerable2) or (
                quantum_vulnerable1 and quantum_safe2
            ):
                conflicts.append(
                    ConflictRecord(
                        conflict_id=f"conflict_{uuid.uuid4().hex[:8]}",
                        claim_id_1=claim1.claim_id,
                        claim_id_2=claim2.claim_id,
                        claim_text_1=claim1.text,
                        claim_text_2=claim2.text,
                        conflict_type="rsa_contradiction",
                        severity=Severity.HIGH,
                        requires_resolution=True,
                    )
                )

    return conflicts


def detect_all_conflicts(
    claims: list[AtomicClaim],
) -> list[ConflictRecord]:
    """Detect all types of conflicts between claims."""
    all_conflicts: list[ConflictRecord] = []

    all_conflicts.extend(detect_must_must_not_conflicts(claims))
    all_conflicts.extend(detect_safe_unsafe_conflicts(claims))
    all_conflicts.extend(detect_rsa_contradictions(claims))

    return all_conflicts
