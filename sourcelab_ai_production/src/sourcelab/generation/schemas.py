"""Generation schemas for the lesson package.

Instruction:
- These schemas define the complete output of Generation v2.
- Every field must be serializable to JSON for the proof bundle.
- Keep schemas explicit so verification can validate them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class GeneratedScenario(BaseModel):
    """A source-grounded scenario for the learner."""

    title: str
    context: str
    audience: str
    task_format: str
    difficulty: int = Field(ge=1, le=5)
    source_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)


class GeneratedLesson(BaseModel):
    """A complete lesson with objectives and instructions."""

    title: str
    learning_objectives: list[str] = Field(default_factory=list)
    required_source_concepts: list[str] = Field(default_factory=list)
    task_instructions: str = ""
    expected_answer_qualities: list[str] = Field(default_factory=list)
    failure_traps: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)


class RubricCriterion(BaseModel):
    """A single rubric criterion with scoring guidance."""

    name: str
    weight: float = Field(ge=0.0, le=1.0)
    description: str = ""
    high_score_behavior: str = ""
    low_score_behavior: str = ""


class GeneratedRubric(BaseModel):
    """A weighted rubric for evaluating learner answers."""

    criteria: list[RubricCriterion] = Field(default_factory=list)

    def weights_sum(self) -> float:
        return round(sum(c.weight for c in self.criteria), 4)


class AnswerKeyEntry(BaseModel):
    """A single entry in the answer key."""

    claim: str
    source_id: str
    chunk_id: str
    trust_tier: str = "C"
    category: Literal["fact", "assumption", "inference"] = "fact"


class GeneratedAnswerKey(BaseModel):
    """A source-grounded answer key with facts and assumptions."""

    source_references: list[AnswerKeyEntry] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    what_not_to_claim: list[str] = Field(default_factory=list)
    sample_strong_answer: str = ""
    sample_weak_answer: str = ""
    source_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)


class ClaimCandidate(BaseModel):
    """A claim extracted from the generated lesson for verification."""

    claim: str
    source_id: str | None = None
    chunk_id: str | None = None
    trust_tier: str | None = None
    severity: Literal["low", "medium", "high"] = "medium"


class GenerationTrace(BaseModel):
    """Trace metadata for a generation run."""

    generation_backend: str = "deterministic_local"
    prompt_version: str = "v1.0"
    topic: str = ""
    difficulty: int = 3
    task_format: str = "architecture_review"
    source_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    timestamp: str = ""
    warnings: list[str] = Field(default_factory=list)
    fail_closed_reason: str | None = None


class GeneratedLessonPackage(BaseModel):
    """Complete lesson package combining all generation outputs."""

    topic: str
    level: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    scenario: GeneratedScenario | None = None
    lesson: GeneratedLesson | None = None
    rubric: GeneratedRubric | None = None
    answer_key: GeneratedAnswerKey | None = None
    source_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    generation_trace: GenerationTrace | None = None
    claim_candidates: list[ClaimCandidate] = Field(default_factory=list)
