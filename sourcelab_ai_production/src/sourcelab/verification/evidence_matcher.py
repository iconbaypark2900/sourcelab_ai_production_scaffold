"""Evidence matcher for claim-to-chunk matching.

Instruction:
- Match atomic claims to source chunks using token overlap, phrase overlap, and trust weight.
- Apply claim type weighting to determine match quality.
- Use minimum support threshold to filter weak matches.
"""

from __future__ import annotations

import re
from collections import Counter

from sourcelab.core.models import SearchResult
from sourcelab.verification.schemas import (
    AtomicClaim,
    ClaimType,
    EvidenceMatch,
    TrustTier,
)


# Trust tier weights for scoring
TRUST_TIER_WEIGHTS: dict[TrustTier, float] = {
    TrustTier.A: 1.0,
    TrustTier.B: 0.85,
    TrustTier.C: 0.7,
    TrustTier.D: 0.4,
    TrustTier.E: 0.2,
}

# Claim type weights for scoring
CLAIM_TYPE_WEIGHTS: dict[ClaimType, float] = {
    ClaimType.DEFINITION: 1.0,
    ClaimType.FACT: 0.9,
    ClaimType.WARNING: 0.95,
    ClaimType.RISK_STATEMENT: 0.9,
    ClaimType.RECOMMENDATION: 0.8,
    ClaimType.PROCESS_STEP: 0.7,
    ClaimType.UNSUPPORTED_EXAMPLE: 0.3,
}

# Minimum support threshold for considering a match valid
MIN_SUPPORT_THRESHOLD = 0.3


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words."""
    return re.findall(r"\b\w+\b", text.lower())


def _extract_phrases(text: str, n: int = 3) -> list[str]:
    """Extract n-gram phrases from text."""
    words = _tokenize(text)
    if len(words) < n:
        return [" ".join(words)] if words else []
    return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]


def _compute_token_overlap(claim_tokens: list[str], chunk_tokens: list[str]) -> float:
    """Compute token overlap score between claim and chunk."""
    if not claim_tokens or not chunk_tokens:
        return 0.0

    claim_counter = Counter(claim_tokens)
    chunk_counter = Counter(chunk_tokens)

    # Count common tokens
    common_tokens = sum((claim_counter & chunk_counter).values())
    total_claim_tokens = sum(claim_counter.values())

    if total_claim_tokens == 0:
        return 0.0

    return common_tokens / total_claim_tokens


def _compute_phrase_matches(claim_text: str, chunk_text: str) -> list[str]:
    """Find matching phrases between claim and chunk."""
    claim_phrases = set(_extract_phrases(claim_text, n=3))
    chunk_phrases = set(_extract_phrases(chunk_text, n=3))

    matches = claim_phrases.intersection(chunk_phrases)
    return sorted(matches)[:5]  # Return top 5 matches


def _determine_match_quality(
    overlap_score: float,
    phrase_matches: list[str],
    trust_tier: TrustTier,
    claim_type: ClaimType,
) -> str:
    """Determine match quality based on scores and weights."""
    trust_weight = TRUST_TIER_WEIGHTS.get(trust_tier, 0.5)
    type_weight = CLAIM_TYPE_WEIGHTS.get(claim_type, 0.5)

    # Weighted score
    weighted_score = overlap_score * trust_weight * type_weight

    # Bonus for phrase matches
    phrase_bonus = min(len(phrase_matches) * 0.05, 0.2)
    final_score = min(weighted_score + phrase_bonus, 1.0)

    if final_score >= 0.6:
        return "strong"
    elif final_score >= 0.4:
        return "moderate"
    else:
        return "weak"


def match_claim_to_chunks(
    claim: AtomicClaim,
    search_results: list[SearchResult],
    min_threshold: float = MIN_SUPPORT_THRESHOLD,
) -> list[EvidenceMatch]:
    """Match a single claim to source chunks."""
    matches: list[EvidenceMatch] = []

    claim_tokens = _tokenize(claim.text)

    for result in search_results:
        chunk_tokens = _tokenize(result.text_preview)

        # Compute overlap score
        overlap_score = _compute_token_overlap(claim_tokens, chunk_tokens)

        # Skip if below threshold
        if overlap_score < min_threshold:
            continue

        # Find phrase matches
        phrase_matches = _compute_phrase_matches(claim.text, result.text_preview)

        # Get trust tier
        try:
            trust_tier = TrustTier(result.trust_tier)
        except ValueError:
            trust_tier = TrustTier.C

        # Determine match quality
        match_quality = _determine_match_quality(
            overlap_score, phrase_matches, trust_tier, claim.claim_type
        )

        matches.append(
            EvidenceMatch(
                claim_id=claim.claim_id,
                chunk_id=result.chunk_id,
                source_id=result.source_id,
                trust_tier=trust_tier,
                overlap_score=round(overlap_score, 4),
                phrase_matches=phrase_matches,
                match_quality=match_quality,
            )
        )

    # Sort by overlap score (best matches first)
    matches.sort(key=lambda m: m.overlap_score, reverse=True)

    return matches


def match_all_claims(
    claims: list[AtomicClaim],
    search_results: list[SearchResult],
    min_threshold: float = MIN_SUPPORT_THRESHOLD,
) -> dict[str, list[EvidenceMatch]]:
    """Match all claims to source chunks.

    Returns a dictionary mapping claim_id to list of evidence matches.
    """
    results: dict[str, list[EvidenceMatch]] = {}

    for claim in claims:
        matches = match_claim_to_chunks(claim, search_results, min_threshold)
        results[claim.claim_id] = matches

    return results


def get_best_match(
    matches: list[EvidenceMatch],
) -> EvidenceMatch | None:
    """Get the best match from a list of evidence matches."""
    if not matches:
        return None
    return matches[0]  # Already sorted by overlap_score
