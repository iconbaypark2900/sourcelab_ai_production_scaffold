"""Skill profile v2.

Instruction:
- Production should store this in Postgres.
- The profile must be explainable and exportable.
- v2 adds: criterion-level mastery, attempts, strengths, weaknesses,
  preferred difficulty/guidance, source-grounding history.
- Persist locally as artifacts/profiles/local_user_skill_profile.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sourcelab.learning.schemas import (
    AnswerReviewV2,
    SkillAttempt,
    SkillProfileV2,
    WeaknessRecord,
)


def load_profile(user_id: str = "local_user", project_root: Path | None = None) -> SkillProfileV2:
    """Load a skill profile from disk."""
    if project_root is None:
        project_root = Path.cwd()

    profile_path = project_root / "artifacts" / "profiles" / f"{user_id}_skill_profile.json"

    if profile_path.exists():
        try:
            data = json.loads(profile_path.read_text(encoding="utf-8"))
            return SkillProfileV2.model_validate(data)
        except Exception:
            pass

    # Return default profile
    return SkillProfileV2(user_id=user_id)


def save_profile(profile: SkillProfileV2, project_root: Path | None = None) -> Path:
    """Save a skill profile to disk."""
    if project_root is None:
        project_root = Path.cwd()

    profiles_dir = project_root / "artifacts" / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    profile_path = profiles_dir / f"{profile.user_id}_skill_profile.json"
    profile.updated_at = datetime.now(timezone.utc).isoformat()
    profile_path.write_text(
        json.dumps(profile.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )
    return profile_path


def update_from_answer_review(
    profile: SkillProfileV2,
    review: AnswerReviewV2,
    difficulty: int = 3,
    task_format: str = "architecture_review",
) -> SkillProfileV2:
    """Update the skill profile from an answer review.

    This function updates topic mastery, criterion mastery, attempts,
    strengths, weaknesses, and preferences.
    """
    topic = review.topic

    # Update topic mastery
    current_mastery = profile.topic_mastery.get(topic, 0.55)
    updated_mastery = round(0.7 * current_mastery + 0.3 * review.overall_score, 4)
    profile.topic_mastery[topic] = updated_mastery

    # Update criterion-level mastery
    if topic not in profile.criterion_mastery:
        profile.criterion_mastery[topic] = {}

    for criterion_score in review.criterion_scores:
        criterion = criterion_score.criterion_name
        current_criterion = profile.criterion_mastery[topic].get(criterion, 0.55)
        updated_criterion = round(0.7 * current_criterion + 0.3 * criterion_score.score, 4)
        profile.criterion_mastery[topic][criterion] = updated_criterion

    # Record attempt
    attempt = SkillAttempt(
        attempt_id=f"attempt_{len(profile.attempts) + 1}",
        topic=topic,
        run_id=review.run_id,
        score=review.overall_score,
        difficulty=difficulty,
        task_format=task_format,
        source_grounding_score=review.source_grounding_score,
    )
    profile.attempts.append(attempt)

    # Update strengths (criteria with score >= 0.7)
    new_strengths = [s for s in review.strengths if s not in profile.strengths]
    profile.strengths.extend(new_strengths)
    # Keep only top 10 strengths
    profile.strengths = profile.strengths[-10:]

    # Update weaknesses
    for weakness_text in review.weaknesses:
        criterion = weakness_text.lower().replace("weak ", "")
        existing = next(
            (w for w in profile.weaknesses if w.criterion == criterion and w.topic == topic),
            None,
        )
        if existing:
            existing.occurrences += 1
            existing.average_score = round(
                (existing.average_score * (existing.occurrences - 1) + review.overall_score) / existing.occurrences,
                4,
            )
            existing.last_seen = datetime.now(timezone.utc).isoformat()
        else:
            profile.weaknesses.append(WeaknessRecord(
                criterion=criterion,
                topic=topic,
                occurrences=1,
                average_score=review.overall_score,
                first_seen=datetime.now(timezone.utc).isoformat(),
                last_seen=datetime.now(timezone.utc).isoformat(),
                recommendation=f"Practice {criterion} with explicit source references",
            ))

    # Update last practiced
    profile.last_practiced = datetime.now(timezone.utc).isoformat()

    # Update source grounding history
    profile.source_grounding_history.append(review.source_grounding_score)
    # Keep only last 20 entries
    profile.source_grounding_history = profile.source_grounding_history[-20:]

    # Update preferences based on performance
    if review.overall_score >= 0.75:
        profile.preferred_next_difficulty = min(5, difficulty + 1)
        profile.preferred_guidance_level = max(1, profile.preferred_guidance_level - 1)
    elif review.overall_score < 0.5:
        profile.preferred_next_difficulty = max(1, difficulty - 1)
        profile.preferred_guidance_level = min(5, profile.preferred_guidance_level + 1)

    return profile


def get_topic_mastery(profile: SkillProfileV2, topic: str) -> float:
    """Get the mastery level for a specific topic."""
    return profile.topic_mastery.get(topic, 0.55)


def get_weakest_criteria(profile: SkillProfileV2, topic: str, top_n: int = 3) -> list[str]:
    """Get the weakest criteria for a specific topic."""
    if topic not in profile.criterion_mastery:
        return []

    criteria = profile.criterion_mastery[topic]
    sorted_criteria = sorted(criteria.items(), key=lambda x: x[1])
    return [c[0] for c in sorted_criteria[:top_n]]


# Backward compatibility: keep the old SkillProfile class
class SkillProfile:
    """Legacy skill profile for backward compatibility."""

    def __init__(self):
        self.topic_mastery: dict[str, float] = {}

    def update(self, topic: str, score: float) -> float:
        current = self.topic_mastery.get(topic, 0.55)
        updated = round(0.7 * current + 0.3 * score, 4)
        self.topic_mastery[topic] = updated
        return updated
