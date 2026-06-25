"""Mastery model v2.

Instruction:
- Production can evolve this into Bayesian knowledge tracing or bandit-based adaptation.
- v2 adds: deterministic mastery update logic with difficulty multipliers,
  criterion-level updates, and weakness persistence.
- Output a MasteryUpdate artifact for auditability.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sourcelab.learning.schemas import (
    AnswerReviewV2,
    MasteryUpdate,
    SkillProfileV2,
)


def mastery_band(score: float) -> str:
    """Get the mastery band for a score."""
    if score >= 0.8:
        return "advanced"
    if score >= 0.6:
        return "developing"
    return "needs_support"


def compute_difficulty_multiplier(difficulty: int, score: float) -> float:
    """Compute a difficulty multiplier for mastery updates.

    High difficulty with high score increases mastery more.
    Low difficulty with high score increases mastery less.
    """
    base_multiplier = 0.3

    # Difficulty boost: higher difficulty = more impact
    difficulty_boost = (difficulty - 3) * 0.05

    # Score boost: high score with high difficulty = extra boost
    if score >= 0.75 and difficulty >= 4:
        difficulty_boost += 0.1

    # Low score penalty: if score is low, reduce the update
    if score < 0.4:
        base_multiplier *= 0.5

    return max(0.1, min(0.6, base_multiplier + difficulty_boost))


def update_mastery(
    profile: SkillProfileV2,
    review: AnswerReviewV2,
    difficulty: int = 3,
) -> MasteryUpdate:
    """Update mastery from an answer review.

    Returns a MasteryUpdate artifact documenting the changes.
    """
    topic = review.topic
    overall_score = review.overall_score

    # Get before values
    topic_mastery_before = profile.topic_mastery.get(topic, 0.55)
    criterion_mastery_before = profile.criterion_mastery.get(topic, {}).copy()

    # Compute difficulty multiplier
    multiplier = compute_difficulty_multiplier(difficulty, overall_score)

    # Update topic mastery
    topic_mastery_after = round(
        (1 - multiplier) * topic_mastery_before + multiplier * overall_score,
        4,
    )
    topic_mastery_after = max(0.0, min(1.0, topic_mastery_after))

    # Update criterion-level mastery
    criterion_mastery_after = criterion_mastery_before.copy()
    for criterion_score in review.criterion_scores:
        criterion = criterion_score.criterion_name
        current = criterion_mastery_before.get(criterion, 0.55)
        updated = round(
            (1 - multiplier) * current + multiplier * criterion_score.score,
            4,
        )
        criterion_mastery_after[criterion] = max(0.0, min(1.0, updated))

    # Apply to profile
    profile.topic_mastery[topic] = topic_mastery_after
    if topic not in profile.criterion_mastery:
        profile.criterion_mastery[topic] = {}
    profile.criterion_mastery[topic] = criterion_mastery_after

    return MasteryUpdate(
        user_id=profile.user_id,
        topic=topic,
        topic_mastery_before=topic_mastery_before,
        topic_mastery_after=topic_mastery_after,
        criterion_mastery_before=criterion_mastery_before,
        criterion_mastery_after=criterion_mastery_after,
        difficulty_multiplier=multiplier,
        overall_score=overall_score,
    )


def should_increase_guidance(profile: SkillProfileV2, topic: str) -> bool:
    """Determine if guidance should be increased based on mastery."""
    mastery = profile.topic_mastery.get(topic, 0.55)

    # Check for repeated weaknesses
    repeated_weaknesses = [
        w for w in profile.weaknesses
        if w.topic == topic and w.occurrences >= 3
    ]

    return mastery < 0.5 or len(repeated_weaknesses) > 0


def should_increase_difficulty(profile: SkillProfileV2, topic: str) -> bool:
    """Determine if difficulty should be increased based on mastery."""
    mastery = profile.topic_mastery.get(topic, 0.55)
    return mastery >= 0.75
