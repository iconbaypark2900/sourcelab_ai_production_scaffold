"""Rubric generator.

Instruction:
- Production rubrics should be source-aware and task-specific.
- Keep criteria visible to the learner.
- Weights must sum to 1.0.
"""

from __future__ import annotations

from sourcelab.generation.schemas import GeneratedLessonPackage, GeneratedRubric, RubricCriterion


def default_rubric() -> dict:
    """Legacy default rubric for backward compatibility."""
    return {
        "criteria": {
            "topic_relevance": 0.25,
            "source_grounding": 0.25,
            "practicality": 0.20,
            "uncertainty_control": 0.15,
            "trap_avoidance": 0.15,
        }
    }


class RubricGenerator:
    """Generate a weighted rubric for a lesson package."""

    def generate(self, package: GeneratedLessonPackage) -> GeneratedRubric:
        """Generate a rubric based on the lesson package."""
        criteria = [
            RubricCriterion(
                name="topic_relevance",
                weight=0.20,
                description="How well the answer addresses the core topic",
                high_score_behavior="Directly addresses the topic with specific, relevant details",
                low_score_behavior="Tangential or generic response that misses the core topic",
            ),
            RubricCriterion(
                name="source_grounding",
                weight=0.25,
                description="Use of approved source material with citations",
                high_score_behavior="Cites specific sources and chunk references throughout",
                low_score_behavior="No source citations or references to unapproved material",
            ),
            RubricCriterion(
                name="practical_reasoning",
                weight=0.20,
                description="Practical, actionable recommendations with clear next steps",
                high_score_behavior="Provides concrete first steps with rationale",
                low_score_behavior="Vague or theoretical without actionable guidance",
            ),
            RubricCriterion(
                name="uncertainty_control",
                weight=0.15,
                description="Appropriate handling of uncertainty and limitations",
                high_score_behavior="Clearly distinguishes facts from assumptions",
                low_score_behavior="States assumptions as facts or omits uncertainty",
            ),
            RubricCriterion(
                name="trap_avoidance",
                weight=0.10,
                description="Avoids common failure traps identified in the lesson",
                high_score_behavior="Explicitly avoids all identified failure traps",
                low_score_behavior="Falls into one or more identified failure traps",
            ),
            RubricCriterion(
                name="clarity",
                weight=0.05,
                description="Clear, accessible communication without unnecessary jargon",
                high_score_behavior="Uses plain language appropriate for the audience",
                low_score_behavior="Overly complex or unclear communication",
            ),
            RubricCriterion(
                name="citation_use_of_evidence",
                weight=0.05,
                description="Effective use of evidence from sources to support claims",
                high_score_behavior="Integrates source evidence naturally into the response",
                low_score_behavior="Mentions sources without meaningful integration",
            ),
        ]

        return GeneratedRubric(criteria=criteria)
