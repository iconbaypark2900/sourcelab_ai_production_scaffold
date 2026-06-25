"""Artifact inventory for production runs.

Instruction:
- Define all required and optional artifacts for a production run.
- The harness uses this inventory to validate proof bundles.
- Required artifacts must exist for a run to pass.
- Optional artifacts trigger warnings if missing.
"""

from __future__ import annotations

from sourcelab.harness.schemas import ArtifactRecord


# All artifacts in the order they are produced
ARTIFACT_ORDER = [
    # 1. Source registry
    "source_registry_snapshot.json",
    "source_quality_report.json",
    "source_freshness_report.json",
    # 2. Retrieval
    "retrieved_chunks.json",
    "compression_report.json",
    "retrieval_diagnostics.json",
    "retrieval_evaluation_report.json",
    "index_manifest.json",
    # 3. Generation
    "generated_lesson_package.json",
    "generated_lesson.md",
    "rubric.json",
    "answer_key.md",
    "answer_key.json",
    "generation_trace.json",
    "lesson_task.json",
    # 4. Verification
    "atomic_claims.json",
    "evidence_matches.json",
    "verification_report.json",
    "citation_resolution.json",
    "human_review_queue.json",
    "claim_map.json",
    "grounding_report.md",
    "grounding_report.json",
    # 5. Learning v2
    "answer_submission.json",
    "answer_review.json",
    "source_grounding_review.json",
    "mastery_update.json",
    "skill_profile_snapshot.json",
    "learning_report.json",
    "learning_report.md",
    "next_task_decision.json",
    # 6. Model Router v2
    "model_call_trace.json",
    # 7. Proof bundle v2
    "run_manifest.json",
    "proof_bundle_manifest.json",
    "proof_summary.json",
    # 8. Harness
    "harness_report.json",
    # 9. Trace
    "trace.json",
    # 10. Research engine v1 (optional, lesson create)
    "research_plan.json",
    "research_plan.md",
    "retrieval_strategy.json",
    "source_coverage_report.json",
    "source_coverage_report.md",
    "evidence_bound_lesson_plan.json",
    "genericness_report.json",
    "topic_profile_update.json",
    "source_expansion_suggestions.json",
    # 11. Golden evals (optional, per pack)
    "golden_eval_summary.json",
]

# Required artifacts for a passing run
# Note: harness_report.json and proof_bundle_manifest.json are NOT included
# because they are self-referential (harness validates itself, manifest records all artifacts).
# They are written as the last artifacts.
# answer_review.json and next_task_decision.json are only produced by the full demo flow.
REQUIRED_ARTIFACTS = [
    "source_registry_snapshot.json",
    "retrieved_chunks.json",
    "compression_report.json",
    "generated_lesson_package.json",
    "generated_lesson.md",
    "rubric.json",
    "answer_key.md",
    "generation_trace.json",
    "atomic_claims.json",
    "evidence_matches.json",
    "verification_report.json",
    "citation_resolution.json",
    "human_review_queue.json",
    "claim_map.json",
    "grounding_report.md",
    "trace.json",
    "run_manifest.json",
    "proof_summary.json",
]

# Learning v2 artifacts are only produced by the demo flow and answer submit.
LEARNING_V2_ARTIFACTS = [
    "answer_submission.json",
    "answer_review.json",
    "source_grounding_review.json",
    "mastery_update.json",
    "skill_profile_snapshot.json",
    "learning_report.json",
    "learning_report.md",
    "next_task_decision.json",
]

# Optional artifacts that are only produced by the full demo flow
FULL_DEMO_ARTIFACTS = []

# Optional artifacts that trigger warnings if missing
OPTIONAL_ARTIFACTS = [
    "answer_key.json",
    "grounding_report.json",
    "lesson_task.json",
    "rubric.json",
    "model_call_trace.json",
    "golden_eval_summary.json",
    "research_plan.json",
    "retrieval_strategy.json",
    "source_coverage_report.json",
    "evidence_bound_lesson_plan.json",
    "genericness_report.json",
    "topic_profile_update.json",
    "source_expansion_suggestions.json",
]

# Schema names for JSON artifacts that have Pydantic schemas
SCHEMA_MAP = {
    "source_registry_snapshot.json": "list[SourceRecord]",
    "source_quality_report.json": "dict",
    "source_freshness_report.json": "dict",
    "retrieved_chunks.json": "list[SearchResult]",
    "compression_report.json": "dict",
    "retrieval_diagnostics.json": "RetrievalDiagnostics",
    "retrieval_evaluation_report.json": "RetrievalEvaluationReport",
    "index_manifest.json": "IndexManifest",
    "generated_lesson_package.json": "GeneratedLessonPackage",
    "rubric.json": "GeneratedRubric",
    "answer_key.json": "GeneratedAnswerKey",
    "generation_trace.json": "GenerationTrace",
    "atomic_claims.json": "list[AtomicClaim]",
    "evidence_matches.json": "list[EvidenceMatch]",
    "verification_report.json": "VerificationReport",
    "citation_resolution.json": "CitationResolutionResult",
    "human_review_queue.json": "dict",
    "claim_map.json": "list[ClaimRecord]",
    "grounding_report.json": "VerificationReport",
    "answer_submission.json": "AnswerSubmission",
    "answer_review.json": "AnswerReviewV2",
    "source_grounding_review.json": "SourceGroundingReview",
    "mastery_update.json": "MasteryUpdate",
    "skill_profile_snapshot.json": "SkillProfileV2",
    "learning_report.json": "LearningReport",
    "next_task_decision.json": "NextTaskDecision",
    "model_call_trace.json": "ModelCallTraceLog",
    "run_manifest.json": "RunManifest",
    "proof_bundle_manifest.json": "ProofBundleManifest",
    "proof_summary.json": "dict",
    "harness_report.json": "HarnessReport",
    "trace.json": "dict",
    "lesson_task.json": "LessonTask",
    "golden_eval_summary.json": "GoldenEvalSummary",
    "research_plan.json": "ResearchPlan",
    "retrieval_strategy.json": "RetrievalStrategy",
    "source_coverage_report.json": "SourceCoverageReport",
    "evidence_bound_lesson_plan.json": "EvidenceBoundLessonPlan",
    "genericness_report.json": "GenericnessReport",
    "topic_profile_update.json": "TopicProfileUpdate",
    "source_expansion_suggestions.json": "SourceExpansionSuggestions",
}

# Artifact types
ARTIFACT_TYPES = {
    "source_registry_snapshot.json": "json",
    "source_quality_report.json": "json",
    "source_freshness_report.json": "json",
    "retrieved_chunks.json": "json",
    "compression_report.json": "json",
    "retrieval_diagnostics.json": "json",
    "retrieval_evaluation_report.json": "json",
    "index_manifest.json": "json",
    "generated_lesson_package.json": "json",
    "generated_lesson.md": "markdown",
    "rubric.json": "json",
    "answer_key.md": "markdown",
    "answer_key.json": "json",
    "generation_trace.json": "json",
    "lesson_task.json": "json",
    "atomic_claims.json": "json",
    "evidence_matches.json": "json",
    "verification_report.json": "json",
    "citation_resolution.json": "json",
    "human_review_queue.json": "json",
    "claim_map.json": "json",
    "grounding_report.md": "markdown",
    "grounding_report.json": "json",
    "answer_submission.json": "json",
    "answer_review.json": "json",
    "source_grounding_review.json": "json",
    "mastery_update.json": "json",
    "skill_profile_snapshot.json": "json",
    "learning_report.json": "json",
    "learning_report.md": "markdown",
    "next_task_decision.json": "json",
    "model_call_trace.json": "json",
    "run_manifest.json": "json",
    "proof_bundle_manifest.json": "json",
    "proof_summary.json": "json",
    "harness_report.json": "json",
    "trace.json": "json",
    "golden_eval_summary.json": "json",
    "research_plan.json": "json",
    "research_plan.md": "markdown",
    "retrieval_strategy.json": "json",
    "source_coverage_report.json": "json",
    "source_coverage_report.md": "markdown",
    "evidence_bound_lesson_plan.json": "json",
    "genericness_report.json": "json",
    "topic_profile_update.json": "json",
    "source_expansion_suggestions.json": "json",
}


def get_artifact_record(
    artifact_name: str,
    run_dir,
    *,
    required: bool = True,
) -> ArtifactRecord:
    """Get an artifact record for a given artifact name."""
    from pathlib import Path

    path = run_dir / artifact_name
    exists = path.exists()
    sha256 = ""
    artifact_type = ARTIFACT_TYPES.get(artifact_name, "json")
    schema_name = SCHEMA_MAP.get(artifact_name, "")
    error = None
    validated = False

    if exists and artifact_type == "json":
        try:
            import json
            json.loads(path.read_text(encoding="utf-8"))
            validated = True
        except (json.JSONDecodeError, ValueError) as e:
            error = f"Invalid JSON: {e}"
            validated = False

    if exists and not sha256:
        try:
            import hashlib
            content = path.read_bytes()
            sha256 = hashlib.sha256(content).hexdigest()
        except Exception:
            sha256 = "compute_error"

    return ArtifactRecord(
        artifact_name=artifact_name,
        path=str(path),
        artifact_type=artifact_type,
        required=required,
        exists=exists,
        sha256=sha256,
        schema_name=schema_name,
        validated=validated,
        error=error,
    )


def build_artifact_inventory(run_dir) -> list[ArtifactRecord]:
    """Build a complete artifact inventory for a run directory."""
    from pathlib import Path

    if isinstance(run_dir, str):
        run_dir = Path(run_dir)

    records = []
    required_set = set(REQUIRED_ARTIFACTS)
    optional_set = set(OPTIONAL_ARTIFACTS)

    for artifact_name in ARTIFACT_ORDER:
        is_required = artifact_name in required_set
        record = get_artifact_record(
            artifact_name,
            run_dir,
            required=is_required,
        )
        records.append(record)

    return records
