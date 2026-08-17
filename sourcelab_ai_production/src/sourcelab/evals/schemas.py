"""Golden eval schemas for SourceLab AI.

Instruction:
- Define schemas for golden evaluation cases and reports.
- Used for retrieval, claim, answer, and lesson evaluations.
- Reports include pass/fail status and failure details.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class RetrievalGoldCase(BaseModel):
    """A single retrieval golden eval case."""

    query: str
    expected_source_ids: list[str]
    expected_terms: list[str] = Field(default_factory=list)
    forbidden_source_ids: list[str] = Field(default_factory=list)
    min_hit_at_k: int = 1
    description: str = ""


class ClaimGoldCase(BaseModel):
    """A single claim verification golden eval case."""

    claim: str
    expected_status: Literal["supported", "unsupported", "uncertain", "needs_review"]
    claim_type: str = "fact"
    severity: str = "medium"
    description: str = ""
    should_block: bool = False


class AnswerGoldCase(BaseModel):
    """A single answer scoring golden eval case."""

    answer: str
    topic: str
    expected_min_score: float = 0.0
    expected_max_score: float = 1.0
    expected_quality: Literal["strong", "weak", "unsupported", "risky"]
    should_trigger_review: bool = False
    description: str = ""


class LessonGoldCase(BaseModel):
    """A single lesson generation golden eval case."""

    topic: str
    difficulty: int = 3
    task_format: str = "architecture_review"
    required_source_ids: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    description: str = ""


class LearningLoopGoldCase(BaseModel):
    """A single learning-loop golden eval case.

    Exercises the full learning loop end-to-end:
    score -> mastery update -> next-task decision. Known-good answers
    should raise mastery and increase difficulty / lower guidance;
    known-bad answers should lower mastery and increase guidance.
    """

    answer: str
    topic: str
    expected_min_score: float = 0.0
    expected_max_score: float = 1.0
    mastery_direction: Literal["rise", "drop", "none"] = "none"
    difficulty_direction: Literal["increase", "decrease", "unchanged", "none"] = "none"
    guidance_direction: Literal["increase", "decrease", "unchanged", "none"] = "none"
    should_trigger_review: bool = False
    description: str = ""


class GoldenEvalFailure(BaseModel):
    """Details of a failed eval case."""

    case_index: int
    case_description: str
    expected: str
    actual: str
    details: str = ""


class GoldenEvalReport(BaseModel):
    """Report for a golden eval run."""

    eval_name: str
    pack_name: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    failures: list[GoldenEvalFailure] = Field(default_factory=list)
    diagnostics: list[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GoldenEvalSummary(BaseModel):
    """Summary of all golden eval results."""

    pack_name: str
    total_evals: int
    total_cases: int
    total_passed: int
    total_failed: int
    overall_pass_rate: float
    eval_reports: list[GoldenEvalReport] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
