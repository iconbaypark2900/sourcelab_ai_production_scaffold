"""Schemas for deterministic run comparison results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RetrievalOverlapPerRun(BaseModel):
    run_id: str
    source_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    source_count: int = 0
    chunk_count: int = 0


class RetrievalOverlapPair(BaseModel):
    run_id_a: str
    run_id_b: str
    shared_source_ids: list[str] = Field(default_factory=list)
    shared_chunk_ids: list[str] = Field(default_factory=list)
    source_jaccard: float = 0.0
    chunk_jaccard: float = 0.0
    unique_sources_a: list[str] = Field(default_factory=list)
    unique_sources_b: list[str] = Field(default_factory=list)
    unique_chunks_a: list[str] = Field(default_factory=list)
    unique_chunks_b: list[str] = Field(default_factory=list)


class RetrievalOverlapComparison(BaseModel):
    per_run: list[RetrievalOverlapPerRun] = Field(default_factory=list)
    pairwise: list[RetrievalOverlapPair] = Field(default_factory=list)
    all_shared_source_ids: list[str] = Field(default_factory=list)
    all_shared_chunk_ids: list[str] = Field(default_factory=list)


class ClaimStatsPerRun(BaseModel):
    run_id: str
    total_claims: int = 0
    supported_claims: int = 0
    unsupported_claims: int = 0
    uncertain_claims: int = 0
    needs_review: int = 0
    unsupported_high_risk: int = 0
    citation_resolution_rate: float | None = None
    has_blocking_issues: bool = False


class ClaimDeltaPair(BaseModel):
    run_id_a: str
    run_id_b: str
    total_claims_delta: int = 0
    supported_delta: int = 0
    unsupported_delta: int = 0
    resolution_rate_delta: float | None = None
    high_risk_delta: int = 0


class ClaimComparison(BaseModel):
    per_run: list[ClaimStatsPerRun] = Field(default_factory=list)
    pairwise_deltas: list[ClaimDeltaPair] = Field(default_factory=list)


class ProofGatePerRun(BaseModel):
    run_id: str
    harness_passed: bool | None = None
    proof_bundle_status: str = ""
    release_gate_status: str = ""
    artifact_count: int = 0
    missing_required: list[str] = Field(default_factory=list)
    failed_validation: list[str] = Field(default_factory=list)


class ProofGateComparison(BaseModel):
    per_run: list[ProofGatePerRun] = Field(default_factory=list)
    all_passed_harness: bool = False
    all_passed_proof: bool = False


class LessonComparisonPerRun(BaseModel):
    run_id: str
    topic: str = ""
    lesson_format: str = ""
    source_pack: str = ""
    difficulty: int | None = None
    retrieval_mode: str = ""
    lesson_length_chars: int = 0
    section_count: int = 0


class LessonComparison(BaseModel):
    per_run: list[LessonComparisonPerRun] = Field(default_factory=list)


class RunComparisonResult(BaseModel):
    run_ids: list[str] = Field(default_factory=list)
    compared_at: str = ""
    retrieval_overlap: RetrievalOverlapComparison = Field(default_factory=RetrievalOverlapComparison)
    claim_deltas: ClaimComparison = Field(default_factory=ClaimComparison)
    proof_gate_comparison: ProofGateComparison = Field(default_factory=ProofGateComparison)
    lesson_comparison: LessonComparison = Field(default_factory=LessonComparison)
    recommendation: str = ""
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    raw_summary: dict[str, Any] = Field(default_factory=dict)


class AnswerComparePerRun(BaseModel):
    """Answer attempt summary for a single run."""

    run_id: str
    topic: str = ""
    attempt_count: int = 0
    latest_attempt_id: str = ""
    latest_score: float = 0.0
    best_attempt_id: str = ""
    best_score: float = 0.0
    needs_review_count: int = 0
    capped_count: int = 0
    latest_cap_reason: str = ""
    latest_next_task_focus: str = ""
    best_next_task_focus: str = ""


class AnswerCompareSummary(BaseModel):
    """Aggregate answer comparison across runs."""

    total_runs: int = 0
    runs_with_attempts: int = 0
    runs_without_attempts: int = 0
    run_ids_without_attempts: list[str] = Field(default_factory=list)
    best_run_by_best_score: str = ""
    weakest_by_latest: str = ""
    avg_latest_score: float | None = None
    avg_best_score: float | None = None
    review_heavy_runs: list[str] = Field(default_factory=list)


class AnswerCompareResult(BaseModel):
    """Multi-run answer comparison result."""

    run_ids: list[str] = Field(default_factory=list)
    compared_at: str = ""
    per_run: list[AnswerComparePerRun] = Field(default_factory=list)
    summary: AnswerCompareSummary = Field(default_factory=AnswerCompareSummary)
    recommendation: str = ""
    batch_id: str = ""
