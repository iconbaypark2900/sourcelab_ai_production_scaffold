"""Core Pydantic schemas shared across the system.

Instruction:
- Do not pass unstructured dictionaries between modules.
- Add fields here when data must cross module boundaries.
- Keep schemas explicit so proof bundles can be validated.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


TrustTier = Literal["A", "B", "C", "D", "E"]


class SourceRecord(BaseModel):
    """Metadata for a trusted source."""

    source_id: str
    title: str
    path: str | None = None
    url: str | None = None
    publisher: str = "local"
    source_type: str = "local_note"
    trust_tier: TrustTier = "C"
    retrieved_at: datetime
    last_checked_at: datetime | None = None
    hash_sha256: str
    status: Literal["active", "pending_review", "rejected", "stale", "archived"] = "active"
    approval_status: Literal["approved", "needs_review", "rejected"] = "approved"
    source_pack: str | None = None
    pack_name: str | None = None


class SourceChunk(BaseModel):
    """A retrievable source chunk that preserves source metadata."""

    chunk_id: str
    source_id: str
    text: str
    section_title: str = "body"
    trust_tier: TrustTier
    token_count: int


class SearchResult(BaseModel):
    """Search result returned by the retriever."""

    chunk_id: str
    source_id: str
    title: str
    score: float
    trust_tier: TrustTier
    text_preview: str


class LessonTask(BaseModel):
    """Generated task shown to the user."""

    topic: str
    title: str
    scenario: str
    task: str
    difficulty: int = Field(ge=1, le=5)
    expected_behavior: str
    failure_trap: str
    source_ids: list[str]


class ClaimRecord(BaseModel):
    """A generated claim and its support status."""

    claim: str
    support_status: Literal["supported", "unsupported", "uncertain"]
    source_id: str | None = None
    chunk_id: str | None = None
    trust_tier: TrustTier | None = None
    severity: Literal["low", "medium", "high"] = "medium"


class AnswerReview(BaseModel):
    """Rubric-based answer review."""

    topic: str
    score: float = Field(ge=0, le=1)
    breakdown: dict[str, float]
    feedback: str
    next_recommendation: str


class NextTaskDecision(BaseModel):
    """Adaptive next-task decision with an explanation."""

    topic: str
    focus: str
    task_format: str
    difficulty: int = Field(ge=1, le=5)
    guidance_level: int = Field(ge=1, le=5)
    reason: str
    score: float
