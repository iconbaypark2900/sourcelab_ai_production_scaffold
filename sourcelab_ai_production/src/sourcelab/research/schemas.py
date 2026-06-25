"""Pydantic schemas for the Library-Aware Research Engine v1."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EvidenceOrigin = Literal["source_pack", "library_silver", "promoted_candidate"]
WeakLabel = Literal["insufficient_evidence", "thin_lesson", "needs_source_expansion"]
GenericnessVerdict = Literal["specific", "somewhat_generic", "too_generic"]
EvidenceStrength = Literal["strong", "moderate", "weak", "missing"]


class ResearchSubtopic(BaseModel):
    """A focused subtopic within a research plan."""

    subtopic_id: str
    title: str
    rationale: str = ""
    priority: Literal["high", "medium", "low"] = "medium"


class ResearchPlan(BaseModel):
    """Topic-specific research plan for a lesson run."""

    run_id: str
    topic: str
    source_pack: str
    generated_at: datetime
    subtopics: list[ResearchSubtopic] = Field(default_factory=list)
    research_questions: list[str] = Field(default_factory=list)
    target_domains: list[str] = Field(default_factory=list)
    pack_focus_areas: list[str] = Field(default_factory=list)
    methodology_notes: list[str] = Field(default_factory=list)
    profile_context_used: bool = False
    profile_weak_concepts: list[str] = Field(default_factory=list)
    profile_known_gaps: list[str] = Field(default_factory=list)
    profile_source_expansion_suggestions: list[str] = Field(default_factory=list)
    follow_up_focus: list[str] = Field(default_factory=list)


class RetrievalQuery(BaseModel):
    """A query derived from the research plan."""

    query_id: str
    text: str
    rationale: str = ""
    priority: Literal["high", "medium", "low"] = "medium"
    subtopic_id: str | None = None


class LabeledRetrievalHit(BaseModel):
    """A retrieval hit with library-aware origin labeling."""

    chunk_id: str
    source_id: str
    library_card_id: str | None = None
    title: str
    score: float
    trust_tier: str
    text_preview: str
    origin: EvidenceOrigin
    query_id: str


class RetrievalStrategy(BaseModel):
    """Library-aware retrieval strategy and results."""

    run_id: str
    topic: str
    source_pack: str
    generated_at: datetime
    queries: list[RetrievalQuery] = Field(default_factory=list)
    origins_enabled: list[EvidenceOrigin] = Field(default_factory=list)
    source_pack_source_count: int = 0
    library_silver_card_count: int = 0
    promoted_candidate_count: int = 0
    hits: list[LabeledRetrievalHit] = Field(default_factory=list)
    selected_chunk_ids: list[str] = Field(default_factory=list)


class CoverageByOrigin(BaseModel):
    """Per-origin coverage counts."""

    origin: EvidenceOrigin
    source_count: int = 0
    chunk_count: int = 0
    hit_count: int = 0


class SourceCoverageReport(BaseModel):
    """Source coverage metrics with weak labels."""

    run_id: str
    topic: str
    source_pack: str
    generated_at: datetime
    coverage_score: float = Field(ge=0.0, le=1.0)
    retrieval_hit_count: int = 0
    unique_source_count: int = 0
    unique_library_card_count: int = 0
    by_origin: list[CoverageByOrigin] = Field(default_factory=list)
    weak_labels: list[WeakLabel] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EvidenceBoundSection(BaseModel):
    """A lesson section bound to explicit evidence."""

    section_id: str
    title: str
    objective: str = ""
    source_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    library_card_ids: list[str] = Field(default_factory=list)
    evidence_strength: EvidenceStrength = "missing"
    gaps: list[str] = Field(default_factory=list)


class EvidenceBoundLessonPlan(BaseModel):
    """Evidence-bound lesson plan derived from retrieval and verification."""

    run_id: str
    topic: str
    source_pack: str
    generated_at: datetime
    sections: list[EvidenceBoundSection] = Field(default_factory=list)
    overall_evidence_strength: EvidenceStrength = "missing"
    uncovered_objectives: list[str] = Field(default_factory=list)


class GenericnessSignal(BaseModel):
    """A signal contributing to genericness scoring."""

    signal_id: str
    description: str
    weight: float = 0.0
    triggered: bool = False


class GenericnessReport(BaseModel):
    """Genericness detection report for a lesson topic."""

    run_id: str
    topic: str
    source_pack: str
    generated_at: datetime
    verdict: GenericnessVerdict
    genericness_score: float = Field(ge=0.0, le=1.0)
    signals: list[GenericnessSignal] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class TopicProfile(BaseModel):
    """Adaptive topic memory persisted across runs."""

    topic: str
    topic_slug: str
    source_pack: str
    run_count: int = 0
    answer_submit_count: int = 0
    avg_coverage_score: float = 0.0
    last_coverage_score: float | None = None
    weak_label_counts: dict[str, int] = Field(default_factory=dict)
    genericness_history: list[GenericnessVerdict] = Field(default_factory=list)
    frequent_gaps: list[str] = Field(default_factory=list)
    last_run_id: str | None = None
    orchestration_runs: list[str] = Field(default_factory=list)
    followup_chain: list[str] = Field(default_factory=list)
    last_gap_closure_verdict: GapClosureVerdict | None = None
    updated_at: datetime


class TopicProfileUpdate(BaseModel):
    """Delta written per run; applied on answer submit."""

    run_id: str
    topic: str
    topic_slug: str
    source_pack: str
    generated_at: datetime
    coverage_score: float = 0.0
    weak_labels: list[WeakLabel] = Field(default_factory=list)
    genericness_verdict: GenericnessVerdict = "specific"
    new_gaps: list[str] = Field(default_factory=list)
    applied: bool = False


EvolutionVerdict = Literal["improved", "unchanged", "worse", "insufficient_history"]


class QualityDelta(BaseModel):
    """Quality metrics delta versus the most recent prior run."""

    coverage_delta: float | None = None
    genericness_score_delta: float | None = None
    gaps_closed: list[str] = Field(default_factory=list)
    gaps_new: list[str] = Field(default_factory=list)
    weak_concepts_addressed: list[str] = Field(default_factory=list)


class EvolutionChange(BaseModel):
    """Recorded adaptation between consecutive runs."""

    area: str
    description: str


class LessonEvolutionReport(BaseModel):
    """Follow-up run comparison against prior topic history."""

    run_id: str
    topic: str
    source_pack: str
    generated_at: datetime
    previous_run_ids: list[str] = Field(default_factory=list)
    profile_used: bool = False
    changes_from_previous: list[EvolutionChange] = Field(default_factory=list)
    quality_delta: QualityDelta = Field(default_factory=QualityDelta)
    verdict: EvolutionVerdict = "insufficient_history"


class CollectorQueryPlan(BaseModel):
    """Suggested collector invocation for library expansion."""

    collector: str
    query: str
    example_command: str
    priority: Literal["low", "medium", "high"] = "medium"


class LibraryExpansionPlan(BaseModel):
    """Actionable library expansion plan derived from thin-evidence suggestions."""

    run_id: str
    topic: str
    source_pack: str
    generated_at: datetime
    recommended_collectors: list[str] = Field(default_factory=list)
    collector_queries: list[CollectorQueryPlan] = Field(default_factory=list)
    promotion_targets: list[str] = Field(default_factory=list)
    manual_source_requests: list[str] = Field(default_factory=list)


ExpansionExecutionMode = Literal["dry_run", "execute"]
CollectorExecutionStatus = Literal["planned", "executed", "skipped", "error", "manual"]


class CollectorExecutionEntry(BaseModel):
    """Single collector invocation in an expansion execution report."""

    collector: str
    query: str
    command: str
    status: CollectorExecutionStatus = "planned"
    priority: Literal["low", "medium", "high"] = "medium"
    message: str = ""


class LibraryExpansionExecution(BaseModel):
    """Execution report for library expansion collector commands."""

    run_id: str
    topic: str
    source_pack: str
    generated_at: datetime
    mode: ExpansionExecutionMode = "dry_run"
    baseline_run_id: str | None = None
    baseline_topic: str | None = None
    baseline_source_pack: str | None = None
    collector_commands: list[str] = Field(default_factory=list)
    executed_collectors: list[CollectorExecutionEntry] = Field(default_factory=list)
    manual_collectors: list[CollectorExecutionEntry] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class LibraryImprovementReport(BaseModel):
    """Before/after library metrics following expansion execution."""

    run_id: str
    topic: str
    source_pack: str
    generated_at: datetime
    raw_sources_before: int = 0
    raw_sources_after: int = 0
    source_cards_before: int = 0
    source_cards_after: int = 0
    chunks_before: int = 0
    chunks_after: int = 0
    new_source_cards: int = 0
    new_chunks: int = 0
    quality_before: float = 0.0
    quality_after: float = 0.0
    promotion_candidates_before: int = 0
    promotion_candidates_after: int = 0
    executed_collectors: list[str] = Field(default_factory=list)
    manual_collectors: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class SourcePromotionEntry(BaseModel):
    """A source card proposed or promoted into a source pack."""

    source_id: str
    title: str
    domain_tags: list[str] = Field(default_factory=list)
    quality_score: float = 0.0
    match_reasons: list[str] = Field(default_factory=list)
    proposed_filename: str = ""
    status: Literal["proposed", "promoted", "skipped"] = "proposed"
    reason: str = ""


class SourcePromotionReport(BaseModel):
    """Promotion report derived from expansion plan and improved library state."""

    run_id: str
    topic: str
    source_pack: str
    generated_at: datetime
    mode: Literal["dry_run", "force"] = "dry_run"
    min_quality: float = 0.55
    missing_evidence_terms: list[str] = Field(default_factory=list)
    target_domains: list[str] = Field(default_factory=list)
    candidates: list[SourcePromotionEntry] = Field(default_factory=list)
    promoted_count: int = 0
    skipped_count: int = 0


GapClosureVerdict = Literal["improved", "unchanged", "worse", "insufficient_data"]


class GapClosureReport(BaseModel):
    """Compare weak baseline run vs follow-up run after expansion/promotion."""

    run_id: str
    topic: str
    source_pack: str
    generated_at: datetime
    baseline_run_id: str | None = None
    follow_up_run_id: str | None = None
    coverage_score_before: float | None = None
    coverage_score_after: float | None = None
    genericness_before: float | None = None
    genericness_after: float | None = None
    missing_evidence_before: list[str] = Field(default_factory=list)
    missing_evidence_after: list[str] = Field(default_factory=list)
    new_sources_used: list[str] = Field(default_factory=list)
    new_library_cards_used: list[str] = Field(default_factory=list)
    gaps_closed: list[str] = Field(default_factory=list)
    gaps_remaining: list[str] = Field(default_factory=list)
    verdict: GapClosureVerdict = "insufficient_data"


GapClosureOrchestrationMode = Literal["dry_run", "execute"]
GapClosureOrchestrationStepStatus = Literal["planned", "executed", "skipped", "error"]


class GapClosureOrchestrationStep(BaseModel):
    """Single step in a guided gap-closure orchestration plan."""

    step_id: str
    name: str
    status: GapClosureOrchestrationStepStatus = "planned"
    message: str = ""


class GapClosureOrchestrationReport(BaseModel):
    """Guided orchestration report for the research gap-closure loop."""

    run_id: str
    topic: str
    source_pack: str
    mode: GapClosureOrchestrationMode = "dry_run"
    generated_at: datetime
    steps: list[GapClosureOrchestrationStep] = Field(default_factory=list)
    commands_planned: list[str] = Field(default_factory=list)
    commands_executed: list[str] = Field(default_factory=list)
    reports_written: list[str] = Field(default_factory=list)
    promotion_status: str = "skipped"
    manifest_repair_status: str = "skipped"
    followup_lesson_command: str = ""
    followup_run_id: str | None = None
    gap_closure_verdict: GapClosureVerdict | None = None
    answer_submit_status: str = "skipped"
    answer_source: str | None = None
    answer_submission_run_id: str | None = None
    answer_score: float | None = None
    answer_review_required: bool = False
    topic_profile_updated: bool = False
    answer_artifacts_written: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
