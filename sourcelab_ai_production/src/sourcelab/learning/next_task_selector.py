"""Next task selector v2.

Instruction:
- This is the safe self-evolving component.
- It evolves task settings, not source code.
- v2 adds: profile-aware selection, weakness-driven focus, source-grounding response.
- The selector uses skill profile, answer review, and mastery to determine the next task.
"""

from __future__ import annotations

from sourcelab.core.models import AnswerReview, NextTaskDecision
from sourcelab.learning.schemas import (
    AnswerReviewV2,
    NextTaskRationale,
    SkillProfileV2,
)
from sourcelab.learning.mastery import mastery_band, should_increase_difficulty, should_increase_guidance
from sourcelab.learning.skill_profile import get_weakest_criteria, get_topic_mastery


class NextTaskSelector:
    """Select the next task based on learner performance and profile."""

    def select(self, topic: str, answer_review: AnswerReview) -> NextTaskDecision:
        """Select next task (backward-compatible version).

        Maintains the original interface for backward compatibility.
        """
        if answer_review.score >= 0.75:
            difficulty = 4
            guidance = 2
            focus = "architecture-level reasoning with tighter citation discipline"
            reason = "The answer was strong, so the next task increases difficulty and lowers guidance."
        else:
            difficulty = 2
            guidance = 4
            focus = "source-grounded fundamentals"
            reason = "The answer needs more grounding, so the next task adds guidance."

        return NextTaskDecision(
            topic=topic,
            focus=focus,
            task_format="architecture review",
            difficulty=difficulty,
            guidance_level=guidance,
            reason=reason,
            score=round(answer_review.score, 4),
        )

    def select_v2(
        self,
        topic: str,
        answer_review: AnswerReviewV2,
        profile: SkillProfileV2 | None = None,
        previous_task_format: str = "",
    ) -> tuple[NextTaskDecision, NextTaskRationale]:
        """Select next task with full rationale.

        Returns both a NextTaskDecision (backward compatible) and a NextTaskRationale.
        """
        # Build evidence from scores
        evidence_from_scores = {
            "overall_score": answer_review.overall_score,
            "source_grounding": answer_review.source_grounding_score,
            "uncertainty_control": answer_review.uncertainty_control_score,
            "trap_avoidance": answer_review.trap_avoidance_score,
        }

        # Build evidence from profile
        evidence_from_profile = {}
        if profile:
            evidence_from_profile["topic_mastery"] = get_topic_mastery(profile, topic)
            weakest = get_weakest_criteria(profile, topic)
            if weakest:
                evidence_from_profile["weakest_criteria_count"] = len(weakest)

        # Determine focus area based on weaknesses
        focus_area = self._determine_focus_area(answer_review, profile, topic)

        # Determine task format based on focus
        task_format = self._determine_task_format(focus_area, previous_task_format)

        # Determine difficulty and guidance
        difficulty, guidance = self._determine_difficulty_guidance(
            answer_review, profile, topic
        )

        # Determine required source behavior
        required_source_behavior = self._determine_source_behavior(answer_review)

        # Build reason
        reason = self._build_reason(answer_review, profile, topic, focus_area)

        # Check if human review is recommended
        human_review_recommended = (
            answer_review.needs_review
            or answer_review.overall_score < 0.3
            or answer_review.source_grounding_score < 0.2
        )

        # Build rationale
        rationale = NextTaskRationale(
            next_task_format=task_format,
            difficulty=difficulty,
            guidance_level=guidance,
            focus_area=focus_area,
            required_source_behavior=required_source_behavior,
            reason=reason,
            evidence_from_scores=evidence_from_scores,
            evidence_from_profile=evidence_from_profile,
            human_review_recommended=human_review_recommended,
        )

        # Build backward-compatible decision
        decision = NextTaskDecision(
            topic=topic,
            focus=focus_area,
            task_format=task_format,
            difficulty=difficulty,
            guidance_level=guidance,
            reason=reason,
            score=round(answer_review.overall_score, 4),
        )

        return decision, rationale

    def _determine_focus_area(
        self,
        answer_review: AnswerReviewV2,
        profile: SkillProfileV2 | None,
        topic: str,
    ) -> str:
        """Determine the focus area for the next task."""
        # Priority 1: Source grounding is weak
        if answer_review.source_grounding_score < 0.4:
            return "source-grounded fundamentals with explicit source references"

        # Priority 2: Uncertainty control is weak
        if answer_review.uncertainty_control_score < 0.4:
            return "separating facts from assumptions with uncertainty labels"

        # Priority 3: Trap avoidance is weak
        if answer_review.trap_avoidance_score < 0.4:
            return "failure-trap recognition and avoidance strategies"

        # Priority 4: Check profile for repeated weaknesses
        if profile:
            weakest = get_weakest_criteria(profile, topic)
            if weakest:
                return f"improving {weakest[0].replace('_', ' ')}"

        # Priority 5: Overall score based
        if answer_review.overall_score >= 0.75:
            return "architecture-level reasoning with tighter citation discipline"
        elif answer_review.overall_score >= 0.5:
            return "balanced practical reasoning and source grounding"
        else:
            return "source-grounded fundamentals with step-by-step guidance"

    def _determine_task_format(self, focus_area: str, previous_format: str) -> str:
        """Determine the task format based on focus area."""
        if "source" in focus_area or "citation" in focus_area:
            return "architecture_review"
        elif "uncertainty" in focus_area or "assumption" in focus_area:
            return "risk_review"
        elif "trap" in focus_area or "avoidance" in focus_area:
            return "debugging"
        elif "practical" in focus_area or "step" in focus_area:
            return "hands_on_lab"
        elif "executive" in focus_area:
            return "executive_explanation"
        else:
            # Vary format if we've done the same one recently
            formats = ["architecture_review", "risk_review", "debugging", "hands_on_lab"]
            if previous_format in formats:
                idx = formats.index(previous_format)
                return formats[(idx + 1) % len(formats)]
            return "architecture_review"

    def _determine_difficulty_guidance(
        self,
        answer_review: AnswerReviewV2,
        profile: SkillProfileV2 | None,
        topic: str,
    ) -> tuple[int, int]:
        """Determine difficulty and guidance level."""
        # Start with profile preferences
        difficulty = 3
        guidance = 3
        if profile:
            difficulty = profile.preferred_next_difficulty
            guidance = profile.preferred_guidance_level

        # Adjust based on score
        if answer_review.overall_score >= 0.75:
            difficulty = min(5, difficulty + 1)
            guidance = max(1, guidance - 1)
        elif answer_review.overall_score < 0.4:
            difficulty = max(1, difficulty - 1)
            guidance = min(5, guidance + 1)

        # Adjust for weak source grounding
        if answer_review.source_grounding_score < 0.3:
            guidance = min(5, guidance + 1)

        return difficulty, guidance

    def _determine_source_behavior(self, answer_review: AnswerReviewV2) -> str:
        """Determine required source behavior for the next task."""
        if answer_review.source_grounding_score < 0.3:
            return "must cite at least 2 source chunks with explicit references"
        elif answer_review.source_grounding_score < 0.6:
            return "should reference source concepts and cite at least 1 source"
        else:
            return "may use sources freely with proper attribution"

    def _build_reason(
        self,
        answer_review: AnswerReviewV2,
        profile: SkillProfileV2 | None,
        topic: str,
        focus_area: str,
    ) -> str:
        """Build an explainable reason for the next task selection."""
        parts = []

        # Score-based reason
        if answer_review.overall_score >= 0.75:
            parts.append("The answer was strong (score >= 0.75)")
        elif answer_review.overall_score >= 0.5:
            parts.append("The answer was adequate but has room for improvement")
        else:
            parts.append("The answer needs significant improvement")

        # Source grounding reason
        if answer_review.source_grounding_score < 0.4:
            parts.append("source grounding is weak - next task requires explicit source references")
        elif answer_review.source_grounding_score >= 0.7:
            parts.append("source grounding is strong")

        # Uncertainty reason
        if answer_review.uncertainty_control_score < 0.4:
            parts.append("uncertainty control needs work - next task focuses on separating facts from assumptions")

        # Trap avoidance reason
        if answer_review.trap_avoidance_score < 0.4:
            parts.append("trap avoidance is weak - next task targets failure-trap recognition")

        # Profile-based reason
        if profile:
            mastery = get_topic_mastery(profile, topic)
            band = mastery_band(mastery)
            parts.append(f"topic mastery is {band} ({mastery:.2f})")

            weakest = get_weakest_criteria(profile, topic)
            if weakest:
                parts.append(f"weakest criteria: {', '.join(weakest)}")

        # Focus area reason
        parts.append(f"next focus: {focus_area}")

        return ". ".join(parts) + "."
