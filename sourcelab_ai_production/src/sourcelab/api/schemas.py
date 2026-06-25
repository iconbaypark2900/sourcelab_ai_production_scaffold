"""API request/response schemas.

Instruction:
- These Pydantic models define the REST API contract for SourceLab.
- They map to existing CLI command inputs/outputs.
- Keep schemas stable for frontend consumers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Health / readiness
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"


class ReadinessResponse(BaseModel):
    """Readiness check response."""
    status: str = "ready"
    components: dict[str, str] = Field(default_factory=dict)


class VersionResponse(BaseModel):
    """Version response."""
    version: str
    release_label: str
    api_version: str = "v1"
    python_version: str = ""
    project_root: str = ""
    artifacts_directory: str = ""


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

class SourceResponse(BaseModel):
    """Source record response."""
    source_id: str
    title: str
    path: str | None = None
    url: str | None = None
    publisher: str = "local"
    source_type: str = "local_note"
    trust_tier: Literal["A", "B", "C", "D", "E"] = "C"
    retrieved_at: datetime | None = None
    hash_sha256: str = ""
    status: Literal["active", "pending_review", "rejected", "stale", "archived"] = "active"
    approval_status: Literal["approved", "needs_review", "rejected"] = "approved"


class SourceListResponse(BaseModel):
    """List of sources response."""
    sources: list[SourceResponse]
    total: int


class SourceValidationResponse(BaseModel):
    """Source validation response."""
    status: Literal["PASS", "FAIL"]
    source_count: int
    errors: list[str]
    warnings: list[str]


class SourceActionRequest(BaseModel):
    """Source action request (approve/reject/archive)."""
    reason: str = ""


class SourceActionResponse(BaseModel):
    """Source action response."""
    source_id: str
    action: str
    success: bool
    message: str


class SourceIngestRequest(BaseModel):
    """Source ingestion request."""
    source_id: str
    title: str = ""
    path: str
    publisher: str = "local"
    source_type: str = "local_file"
    trust_tier: Literal["A", "B", "C", "D", "E"] = "C"


class SourceIngestResponse(BaseModel):
    """Source ingestion response."""
    source_id: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    """Search request."""
    query: str
    top_k: int = Field(default=5, ge=1, le=50)
    mode: Literal["keyword", "vector", "hybrid"] = "hybrid"


class SearchResultItem(BaseModel):
    """Single search result item."""
    chunk_id: str
    source_id: str
    title: str
    score: float
    trust_tier: Literal["A", "B", "C", "D", "E"]
    text_preview: str


class SearchResponse(BaseModel):
    """Search response."""
    query: str
    mode: str
    results: list[SearchResultItem]
    total: int


class IndexBuildResponse(BaseModel):
    """Index build response."""
    status: str
    chunk_count: int
    source_count: int


class RetrievalDiagnosticsResponse(BaseModel):
    """Retrieval diagnostics response."""
    query: str
    mode: str
    result_count: int
    total_chunks: int
    weights: dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Lessons
# ---------------------------------------------------------------------------

LessonFormat = Literal[
    "architecture_review",
    "implementation_plan",
    "concept_lesson",
    "threat_model",
    "quiz",
    "executive_explanation",
    "debugging",
    "hands_on_lab",
    "risk_review",
]

RetrievalMode = Literal["hybrid", "keyword", "vector"]

ModelMode = Literal["deterministic", "local", "local_llm", "ollama", "openai_compatible"]


class LessonCreateRequest(BaseModel):
    """Lesson creation request."""
    topic: str = Field(min_length=1)
    source_pack: str = Field(min_length=1)
    level: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    source_policy: Literal["approved_only", "include_pending", "include_archived"] = "approved_only"
    difficulty: int = Field(default=3, ge=1, le=5)
    task_format: LessonFormat = "architecture_review"
    lesson_format: LessonFormat | None = None
    retrieval_mode: RetrievalMode = "hybrid"
    audience: str = "engineer"
    model_mode: ModelMode | None = "deterministic"
    model_backend: Literal["deterministic", "ollama", "openai_compatible"] | None = None
    model_name: str | None = None
    model_base_url: str | None = None

    @field_validator("topic", "source_pack")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @model_validator(mode="after")
    def normalize_lesson_format(self) -> LessonCreateRequest:
        if self.lesson_format is not None:
            object.__setattr__(self, "task_format", self.lesson_format)
        return self


class LessonCreateResponse(BaseModel):
    """Lesson creation response."""
    lesson_id: str
    run_id: str
    status: str
    topic: str
    source_pack: str
    harness_status: str
    proof_status: str
    artifact_count: int
    run_url: str


class LessonShowResponse(BaseModel):
    """Lesson show response."""
    run_id: str
    topic: str
    lesson_markdown: str
    answer_key_markdown: str | None = None
    sources: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

class RunSummaryResponse(BaseModel):
    """Run summary response."""
    run_id: str
    run_dir: str
    topic: str = ""
    harness_passed: bool | None = None
    proof_bundle_status: str = ""
    answer_score: float | None = None
    has_answer: bool = False
    rubric_alignment_score: float | None = None
    uncapped_score: float | None = None
    overall_score: float | None = None
    cap_reason: str = ""
    needs_review: bool | None = None
    human_review_reason: str = ""
    source_grounding_score: float | None = None
    concept_overlap_grounding_score: float | None = None
    citation_resolution_rate: float | None = None
    unsupported_high_risk_claims: int = 0
    human_review_count: int = 0
    artifact_count: int = 0
    created_at: str = ""
    next_task_focus: str = ""


class RunListResponse(BaseModel):
    """Run list response."""
    runs: list[RunSummaryResponse]
    total: int


class ArtifactRowResponse(BaseModel):
    """Artifact row response."""
    name: str
    artifact_type: str
    required: bool
    exists: bool
    validated: bool
    sha256: str = ""
    size: int = 0


class ArtifactListResponse(BaseModel):
    """Artifact list response."""
    artifacts: list[ArtifactRowResponse]
    total: int


class RunArtifactContentResponse(BaseModel):
    """Parsed content of a single run artifact.

    Read-only access to an artifact's body so frontends can render
    claim/evidence/citation detail that the inventory endpoint omits.
    JSON artifacts populate ``content_json``; markdown/text populate
    ``content_text``.
    """
    run_id: str
    artifact_name: str
    exists: bool
    artifact_type: Literal["json", "markdown", "text", "unknown"] = "unknown"
    content_json: Any | None = None
    content_text: str | None = None


class ProofBundleResponse(BaseModel):
    """Proof bundle response."""
    run_id: str
    status: str
    manifest: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)


class HarnessReportResponse(BaseModel):
    """Harness report response."""
    run_id: str
    passed: bool
    checks: list[dict[str, Any]] = Field(default_factory=list)
    blocking_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    artifact_count: int = 0


# ---------------------------------------------------------------------------
# Learning
# ---------------------------------------------------------------------------

class AnswerSubmitRequest(BaseModel):
    """Answer submission request.

    ``run_id`` accepts a concrete run id, the literal ``"latest"``, or ``null``
    to target the most recent run. ``topic`` is optional and resolved from the
    run's manifest when omitted. ``user_id`` is accepted for forward
    compatibility; local mode always scores against the single ``local_user``
    profile.
    """
    answer_text: str
    run_id: str | None = None
    topic: str | None = None
    user_id: str = "local_user"


class AnswerSubmitResponse(BaseModel):
    """Answer submission response.

    Exposes the transparent learning metrics (v1.0.2) so the UI renders the same
    numbers the run summary shows. The legacy ``score``/``feedback`` fields are
    retained for backward compatibility with earlier API consumers.
    """
    run_id: str
    topic: str
    attempt_id: str | None = None
    attempt_manifest_path: str | None = None
    overall_score: float | None = None
    rubric_alignment_score: float | None = None
    uncapped_score: float | None = None
    source_grounding_score: float | None = None
    concept_overlap_grounding_score: float | None = None
    needs_review: bool | None = None
    cap_reason: str = ""
    human_review_reason: str = ""
    next_task_focus: str = ""
    next_task_decision: dict[str, Any] = Field(default_factory=dict)
    learning_report_path: str | None = None
    # Legacy / backward-compatible fields
    score: float = 0.0
    feedback: str = ""
    next_task_id: str | None = None
    breakdown: dict[str, float] = Field(default_factory=dict)


class ProfileShowResponse(BaseModel):
    """Skill profile response."""
    profile_id: str
    topic: str | None = None
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    mastery: dict[str, float] = Field(default_factory=dict)
    strengths: list[dict[str, Any] | str] = Field(default_factory=list)
    weaknesses: list[dict[str, Any] | str] = Field(default_factory=list)
    source_grounding_history: list[float | dict[str, Any]] = Field(default_factory=list)


class CurriculumResponse(BaseModel):
    """Full curriculum overview with profile, latest report, and next task."""
    profile: dict[str, Any] = Field(default_factory=dict)
    latest_report: dict[str, Any] | None = None
    latest_next_task: dict[str, Any] | None = None


class LearningReportResponse(BaseModel):
    """Learning report response."""
    run_id: str
    topic: str
    report_markdown: str
    report_json: dict[str, Any] = Field(default_factory=dict)


class NextTaskResponse(BaseModel):
    """Next task response."""
    topic: str
    focus: str
    task_format: str
    difficulty: int
    guidance_level: int
    reason: str


class AnswerAttemptManifestResponse(BaseModel):
    """Attempt manifest exposed via the API."""
    attempt_id: str
    run_id: str
    created_at: str
    user_id: str = "local_user"
    answer_preview: str = ""
    overall_score: float = 0.0
    rubric_alignment_score: float = 0.0
    uncapped_score: float = 0.0
    needs_review: bool = False
    cap_reason: str = ""
    human_review_reason: str = ""
    next_task_focus: str = ""


class AnswerAttemptSummaryResponse(BaseModel):
    """Summary row for answer attempt history."""
    attempt_id: str
    created_at: str
    overall_score: float
    uncapped_score: float
    rubric_alignment_score: float
    needs_review: bool = False
    cap_reason: str = ""
    next_task_focus: str = ""


class AnswerHistoryResponse(BaseModel):
    """Answer attempt history for a run."""
    run_id: str
    attempts: list[AnswerAttemptSummaryResponse] = Field(default_factory=list)
    total: int = 0


class AnswerAttemptDetailResponse(BaseModel):
    """Full detail for a single answer attempt."""
    run_id: str
    attempt_id: str
    manifest: AnswerAttemptManifestResponse
    answer_submission: dict[str, Any] = Field(default_factory=dict)
    answer_review: dict[str, Any] = Field(default_factory=dict)
    source_grounding_review: dict[str, Any] = Field(default_factory=dict)
    mastery_update: dict[str, Any] = Field(default_factory=dict)
    learning_report: dict[str, Any] = Field(default_factory=dict)
    learning_report_md: str = ""
    next_task_decision: dict[str, Any] = Field(default_factory=dict)
    artifact_names: list[str] = Field(default_factory=list)


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
    from_overall_score: float = 0.0
    to_overall_score: float = 0.0
    from_needs_review: bool = False
    to_needs_review: bool = False
    from_cap_reason: str = ""
    to_cap_reason: str = ""


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Structured error response."""
    error: str
    detail: str = ""
    code: str = ""


# ---------------------------------------------------------------------------
# Source Packs
# ---------------------------------------------------------------------------

class SourcePackInfo(BaseModel):
    """Source pack information."""
    pack_name: str
    version: str = "unknown"
    title: str = ""
    description: str = ""
    source_count: int = 0
    eval_count: int = 0


class SourcePackListResponse(BaseModel):
    """List of source packs response."""
    packs: list[SourcePackInfo]
    total: int


class SourcePackValidationResponse(BaseModel):
    """Source pack validation response."""
    valid: bool
    errors: list[str]
    warnings: list[str]


class SourcePackInstallRequest(BaseModel):
    """Source pack install request."""
    pack_name: str


class SourcePackInstallResponse(BaseModel):
    """Source pack install response."""
    success: bool
    pack_name: str = ""
    installed: int = 0
    skipped: int = 0
    total_sources: int = 0
    installed_sources: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    error: str | None = None


class SourcePackStatusResponse(BaseModel):
    """Source pack status response."""
    installed: bool
    pack_name: str = ""
    version: str = ""
    total_sources: int = 0
    installed_count: int = 0
    installed_sources: list[str] = Field(default_factory=list)
    error: str | None = None


# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------

class EvalsRunRequest(BaseModel):
    """Evals run request."""
    pack_name: str
    eval_type: Literal["retrieval", "claims", "answers", "lessons"] | None = None


class GoldenEvalSummaryResponse(BaseModel):
    """Golden eval summary response."""
    pack_name: str
    total_evals: int
    total_cases: int
    total_passed: int
    total_failed: int
    overall_pass_rate: float


class EvalsRunResponse(BaseModel):
    """Evals run response."""
    status: str
    pack_name: str
    summary: GoldenEvalSummaryResponse | None = None
    results: dict[str, Any] = Field(default_factory=dict)
    output_dir: str = ""


class EvalsLatestResponse(BaseModel):
    """Evals latest response."""
    pack_name: str
    summary: dict[str, Any] = Field(default_factory=dict)
    markdown: str = ""


class EvalsHistoryEntry(BaseModel):
    """A single historical eval snapshot."""

    snapshot_at: str
    pack_name: str | None = None
    total_evals: int | None = None
    total_cases: int | None = None
    total_passed: int | None = None
    total_failed: int | None = None
    overall_pass_rate: float | None = None


class EvalsHistoryResponse(BaseModel):
    """Evals history response."""

    pack_name: str
    history: list[EvalsHistoryEntry] = Field(default_factory=list)
    latest_pass_rate: float | None = None
    previous_pass_rate: float | None = None
    pass_rate_delta: float | None = None
    run_count: int = 0


class PackThresholdResponse(BaseModel):
    """Per-pack eval thresholds and compliance response."""

    pack_name: str
    thresholds: dict[str, Any] = Field(default_factory=dict)
    overall_pass_rate: float | None = None
    total_cases: int = 0
    total_failed: int = 0
    eval_names: list[str] = Field(default_factory=list)
    checks: list[dict[str, Any]] = Field(default_factory=list)
    meets_thresholds: bool = False


# ---------------------------------------------------------------------------
# Batch runs & comparison (v2.0)
# ---------------------------------------------------------------------------

class BatchItemRequest(BaseModel):
    """Single item in a batch run request."""
    topic: str = Field(min_length=1)
    source_pack: str = Field(min_length=1)
    difficulty: int = Field(default=3, ge=1, le=5)
    lesson_format: LessonFormat = "architecture_review"
    retrieval_mode: RetrievalMode = "hybrid"
    model_mode: ModelMode | None = "deterministic"

    @field_validator("topic", "source_pack")
    @classmethod
    def strip_batch_item_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class BatchCreateRequest(BaseModel):
    """Batch lesson creation request."""
    batch_name: str = Field(min_length=1)
    items: list[BatchItemRequest] = Field(min_length=1)

    @field_validator("batch_name")
    @classmethod
    def strip_batch_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class BatchRunResultResponse(BaseModel):
    """Result for a single run within a batch."""
    index: int = 0
    run_id: str
    topic: str
    source_pack: str = ""
    status: str
    harness_status: str
    proof_status: str
    artifact_count: int = 0
    run_url: str = ""


class BatchFailureResponse(BaseModel):
    """Failure entry for a batch item that did not create a run."""
    index: int
    topic: str = ""
    source_pack: str = ""
    error: str


class BatchCreateResponse(BaseModel):
    """Batch creation response."""
    batch_id: str
    batch_name: str
    status: str
    created_at: str
    runs: list[BatchRunResultResponse] = Field(default_factory=list)
    failures: list[BatchFailureResponse] = Field(default_factory=list)


class BatchListItemResponse(BaseModel):
    """Summary row for batch list."""
    batch_id: str
    batch_name: str
    created_at: str
    status: str
    run_count: int = 0
    failure_count: int = 0
    topics: list[str] = Field(default_factory=list)
    source_packs: list[str] = Field(default_factory=list)


class BatchListResponse(BaseModel):
    """List of batches."""
    batches: list[BatchListItemResponse]
    total: int


class BatchDetailResponse(BaseModel):
    """Batch detail with run summaries."""
    batch_id: str
    batch_name: str
    created_at: str
    status: str
    version: str = "v2.1"
    items: list[dict[str, Any]] = Field(default_factory=list)
    runs: list[dict[str, Any]] = Field(default_factory=list)
    failures: list[dict[str, Any]] = Field(default_factory=list)
    run_ids: list[str] = Field(default_factory=list)
    run_summaries: list[RunSummaryResponse] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    batch_dir: str = ""
    has_comparison: bool = False


class BatchReportResponse(BaseModel):
    """Batch comparison report export."""
    batch_id: str
    comparison_report_json: dict[str, Any] = Field(default_factory=dict)
    comparison_report_md: str = ""
    batch_summary: dict[str, Any] = Field(default_factory=dict)
    report_paths: dict[str, str] = Field(default_factory=dict)


class RunComparisonResponse(BaseModel):
    """Multi-run comparison response."""
    run_ids: list[str] = Field(default_factory=list)
    compared_at: str = ""
    retrieval_overlap: dict[str, Any] = Field(default_factory=dict)
    claim_deltas: dict[str, Any] = Field(default_factory=dict)
    proof_gate_comparison: dict[str, Any] = Field(default_factory=dict)
    lesson_comparison: dict[str, Any] = Field(default_factory=dict)
    recommendation: str = ""
    artifact_paths: dict[str, str] = Field(default_factory=dict)


class AnswerComparePerRunResponse(BaseModel):
    """Answer attempt summary for one run."""
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


class AnswerCompareSummaryResponse(BaseModel):
    """Aggregate answer comparison stats."""
    total_runs: int = 0
    runs_with_attempts: int = 0
    runs_without_attempts: int = 0
    run_ids_without_attempts: list[str] = Field(default_factory=list)
    best_run_by_best_score: str = ""
    weakest_by_latest: str = ""
    avg_latest_score: float | None = None
    avg_best_score: float | None = None
    review_heavy_runs: list[str] = Field(default_factory=list)


class AnswerCompareResponse(BaseModel):
    """Multi-run answer comparison response."""
    run_ids: list[str] = Field(default_factory=list)
    compared_at: str = ""
    per_run: list[AnswerComparePerRunResponse] = Field(default_factory=list)
    summary: AnswerCompareSummaryResponse = Field(default_factory=AnswerCompareSummaryResponse)
    recommendation: str = ""
    batch_id: str = ""
