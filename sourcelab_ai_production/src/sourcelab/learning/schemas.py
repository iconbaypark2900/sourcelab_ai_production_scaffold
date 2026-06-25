"""Learning schemas for Answer Scoring v2 + Skill Profile v2.

Instruction:
- These schemas define the complete learning layer output.
- Every field must be serializable to JSON for the proof bundle.
- Keep schemas explicit so the harness can validate them.
- Learning must be explainable and auditable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnswerSubmission(BaseModel):
    """A learner answer submitted for scoring."""

    answer_id: str = ""
    topic: str
    run_id: str = ""
    lesson_id: str = ""
    answer_text: str
    submitted_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class RubricCriterionScore(BaseModel):
    """Score for a single rubric criterion."""

    criterion_name: str
    weight: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=0.0, le=1.0)
    evidence: str = ""
    feedback: str = ""
    llm_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="LLM judge score for this criterion, if used.",
    )
    llm_feedback: str = Field(
        default="",
        description="LLM judge feedback for this criterion, if used.",
    )


class AnswerScoreBreakdown(BaseModel):
    """Complete rubric-based score breakdown."""

    topic_relevance: float = Field(ge=0.0, le=1.0, default=0.0)
    source_grounding: float = Field(ge=0.0, le=1.0, default=0.0)
    practical_reasoning: float = Field(ge=0.0, le=1.0, default=0.0)
    uncertainty_control: float = Field(ge=0.0, le=1.0, default=0.0)
    trap_avoidance: float = Field(ge=0.0, le=1.0, default=0.0)
    clarity: float = Field(ge=0.0, le=1.0, default=0.0)
    citation_use_of_evidence: float = Field(ge=0.0, le=1.0, default=0.0)


class AnswerReviewV2(BaseModel):
    """Rubric-based answer review v2 with full breakdown."""

    answer_id: str = ""
    topic: str
    lesson_id: str = ""
    run_id: str = ""
    overall_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Final learner score after any risk cap or penalty.",
    )
    criterion_scores: list[RubricCriterionScore] = Field(default_factory=list)
    source_grounding_score: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
        description="Rubric-facing source grounding criterion score.",
    )
    rubric_alignment_score: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
        description="Weighted rubric average before any risk cap.",
    )
    uncapped_score: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
        description="Score after rubric bonuses/penalties but before any risk cap.",
    )
    cap_reason: str = Field(
        default="",
        description="Why overall_score was reduced below uncapped_score, if applicable.",
    )
    uncertainty_control_score: float = Field(ge=0.0, le=1.0, default=0.0)
    trap_avoidance_score: float = Field(ge=0.0, le=1.0, default=0.0)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommended_focus: str = ""
    needs_review: bool = False
    review_reason: str = ""
    llm_judge_used: bool = Field(
        default=False,
        description="Whether an LLM judge was used in scoring.",
    )
    llm_judge_warnings: list[str] = Field(
        default_factory=list,
        description="Warnings from the LLM judge (e.g. parse failures, timeouts).",
    )
    llm_blended_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Blended score if LLM judge was used; None if pure heuristic.",
    )
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class SkillAttempt(BaseModel):
    """A single skill attempt record."""

    attempt_id: str = ""
    topic: str = ""
    run_id: str = ""
    score: float = Field(ge=0.0, le=1.0)
    difficulty: int = Field(ge=1, le=5, default=3)
    task_format: str = ""
    source_grounding_score: float = Field(ge=0.0, le=1.0, default=0.0)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class WeaknessRecord(BaseModel):
    """A tracked weakness."""

    criterion: str
    topic: str
    occurrences: int = 1
    average_score: float = Field(ge=0.0, le=1.0)
    first_seen: str = ""
    last_seen: str = ""
    recommendation: str = ""


class SkillProfileV2(BaseModel):
    """Complete skill profile for a learner."""

    user_id: str = "local_user"
    topic_mastery: dict[str, float] = Field(default_factory=dict)
    criterion_mastery: dict[str, dict[str, float]] = Field(default_factory=dict)
    attempts: list[SkillAttempt] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[WeaknessRecord] = Field(default_factory=list)
    last_practiced: str = ""
    preferred_next_difficulty: int = Field(ge=1, le=5, default=3)
    preferred_guidance_level: int = Field(ge=1, le=5, default=3)
    source_grounding_history: list[float] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class MasteryUpdate(BaseModel):
    """Record of mastery changes from an answer review."""

    user_id: str = "local_user"
    topic: str = ""
    topic_mastery_before: float = Field(ge=0.0, le=1.0, default=0.55)
    topic_mastery_after: float = Field(ge=0.0, le=1.0, default=0.55)
    criterion_mastery_before: dict[str, float] = Field(default_factory=dict)
    criterion_mastery_after: dict[str, float] = Field(default_factory=dict)
    difficulty_multiplier: float = 1.0
    overall_score: float = Field(ge=0.0, le=1.0, default=0.0)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class NextTaskRationale(BaseModel):
    """Detailed rationale for next task selection."""

    next_task_format: str = ""
    difficulty: int = Field(ge=1, le=5, default=3)
    guidance_level: int = Field(ge=1, le=5, default=3)
    focus_area: str = ""
    required_source_behavior: str = ""
    reason: str = ""
    evidence_from_scores: dict[str, float] = Field(default_factory=dict)
    evidence_from_profile: dict[str, float] = Field(default_factory=dict)
    human_review_recommended: bool = False


class LearningReport(BaseModel):
    """Complete learning report for a scoring session."""

    report_id: str = ""
    user_id: str = "local_user"
    topic: str = ""
    run_id: str = ""
    answer_id: str = ""
    overall_score: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
        description="Final score after any risk cap (alias of final_score).",
    )
    rubric_alignment_score: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
        description="Weighted rubric average before any risk cap.",
    )
    uncapped_score: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
        description="Score after rubric bonuses/penalties but before any risk cap.",
    )
    final_score: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
        description="Final learner score after any risk cap.",
    )
    cap_reason: str = ""
    human_review_reason: str = ""
    rubric_breakdown: AnswerScoreBreakdown = Field(default_factory=AnswerScoreBreakdown)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    topic_mastery_before: float = Field(ge=0.0, le=1.0, default=0.55)
    topic_mastery_after: float = Field(ge=0.0, le=1.0, default=0.55)
    criterion_mastery_changes: dict[str, dict[str, float]] = Field(default_factory=dict)
    next_task_rationale: NextTaskRationale = Field(default_factory=NextTaskRationale)
    recommended_focus: str = ""
    human_review_flag: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class AnswerAttemptManifest(BaseModel):
    """Immutable manifest for a single answer submission attempt."""

    attempt_id: str
    run_id: str
    created_at: str
    user_id: str = "local_user"
    answer_preview: str = ""
    overall_score: float = Field(ge=0.0, le=1.0, default=0.0)
    rubric_alignment_score: float = Field(ge=0.0, le=1.0, default=0.0)
    uncapped_score: float = Field(ge=0.0, le=1.0, default=0.0)
    needs_review: bool = False
    cap_reason: str = ""
    human_review_reason: str = ""
    next_task_focus: str = ""


class AnswerAttemptSummary(BaseModel):
    """Summary row for an answer attempt in history listings."""

    attempt_id: str
    created_at: str
    overall_score: float = Field(ge=0.0, le=1.0)
    uncapped_score: float = Field(ge=0.0, le=1.0)
    rubric_alignment_score: float = Field(ge=0.0, le=1.0)
    needs_review: bool = False
    cap_reason: str = ""
    next_task_focus: str = ""


class AnswerAttemptDetail(BaseModel):
    """Full detail for a single answer attempt."""

    run_id: str
    attempt_id: str
    manifest: AnswerAttemptManifest
    answer_submission: dict = Field(default_factory=dict)
    answer_review: dict = Field(default_factory=dict)
    source_grounding_review: dict = Field(default_factory=dict)
    mastery_update: dict = Field(default_factory=dict)
    learning_report: dict = Field(default_factory=dict)
    learning_report_md: str = ""
    next_task_decision: dict = Field(default_factory=dict)
    artifact_names: list[str] = Field(
        default_factory=list,
        description="Snapshot artifact filenames present under the attempt directory.",
    )


class AnswerHistoryResponse(BaseModel):
    """List of answer attempts for a run."""

    run_id: str
    attempts: list[AnswerAttemptSummary] = Field(default_factory=list)
    total: int = 0


class AnswerDiffResponse(BaseModel):
    """Delta between two answer attempts."""

    run_id: str
    from_attempt_id: str
    to_attempt_id: str
    score_delta: float = 0.0
    rubric_alignment_delta: float = 0.0
    uncapped_delta: float = 0.0
    grounding_delta: float = 0.0
    needs_review_changed: bool = False
    cap_reason_changed: bool = False
    strengths_added: list[str] = Field(default_factory=list)
    strengths_removed: list[str] = Field(default_factory=list)
    weaknesses_added: list[str] = Field(default_factory=list)
    weaknesses_removed: list[str] = Field(default_factory=list)
    next_task_changed: bool = False
    from_next_task_focus: str = ""
    to_next_task_focus: str = ""
    from_overall_score: float = Field(ge=0.0, le=1.0, default=0.0)
    to_overall_score: float = Field(ge=0.0, le=1.0, default=0.0)
    from_needs_review: bool = False
    to_needs_review: bool = False
    from_cap_reason: str = ""
    to_cap_reason: str = ""


class SourceGroundingReview(BaseModel):
    """Source grounding review for a learner answer."""

    model_config = ConfigDict(populate_by_name=True)

    answer_id: str = ""
    topic: str = ""
    matched_source_ids: list[str] = Field(default_factory=list)
    matched_chunk_ids: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    unsupported_phrases: list[str] = Field(default_factory=list)
    concept_overlap_grounding_score: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
        alias="source_grounding_score",
        description="Concept-overlap grounding evidence score (matched source concepts / total).",
    )
    total_source_concepts: int = 0
    matched_source_concepts: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
