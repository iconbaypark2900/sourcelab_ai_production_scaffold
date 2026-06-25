"""Unit tests for API schemas.

These tests validate the Pydantic models used in the REST API.
Run with: pytest tests/unit/test_api_schemas.py -v
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sourcelab.api.schemas import (
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    ArtifactListResponse,
    ArtifactRowResponse,
    ErrorResponse,
    HealthResponse,
    HarnessReportResponse,
    IndexBuildResponse,
    LearningReportResponse,
    LessonCreateRequest,
    LessonCreateResponse,
    LessonShowResponse,
    NextTaskResponse,
    ProfileShowResponse,
    ProofBundleResponse,
    ReadinessResponse,
    RunListResponse,
    RunSummaryResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SourceActionRequest,
    SourceActionResponse,
    SourceIngestRequest,
    SourceIngestResponse,
    SourceListResponse,
    SourceResponse,
    SourceValidationResponse,
    VersionResponse,
)


def test_health_response():
    """Test HealthResponse schema."""
    response = HealthResponse()
    assert response.status == "ok"

    response = HealthResponse(status="healthy")
    assert response.status == "healthy"


def test_readiness_response():
    """Test ReadinessResponse schema."""
    response = ReadinessResponse()
    assert response.status == "ready"
    assert response.components == {}

    response = ReadinessResponse(
        status="ready",
        components={"source_registry": "ok"},
    )
    assert response.components["source_registry"] == "ok"


def test_version_response():
    """Test VersionResponse schema."""
    from sourcelab.version import RELEASE_LABEL, __version__

    response = VersionResponse(
        version=__version__,
        release_label=RELEASE_LABEL,
        python_version="3.12.0",
        project_root="/tmp",
        artifacts_directory="/tmp/artifacts",
    )
    assert response.version == __version__
    assert response.release_label == RELEASE_LABEL
    assert response.api_version == "v1"


def test_source_response():
    """Test SourceResponse schema."""
    response = SourceResponse(
        source_id="test_source",
        title="Test Source",
    )
    assert response.source_id == "test_source"
    assert response.title == "Test Source"
    assert response.trust_tier == "C"
    assert response.status == "active"


def test_source_list_response():
    """Test SourceListResponse schema."""
    sources = [
        SourceResponse(source_id="s1", title="Source 1"),
        SourceResponse(source_id="s2", title="Source 2"),
    ]
    response = SourceListResponse(sources=sources, total=2)
    assert len(response.sources) == 2
    assert response.total == 2


def test_source_validation_response():
    """Test SourceValidationResponse schema."""
    response = SourceValidationResponse(
        status="PASS",
        source_count=5,
        errors=[],
        warnings=[],
    )
    assert response.status == "PASS"
    assert response.source_count == 5


def test_source_action_request():
    """Test SourceActionRequest schema."""
    request = SourceActionRequest()
    assert request.reason == ""

    request = SourceActionRequest(reason="Duplicate source")
    assert request.reason == "Duplicate source"


def test_source_action_response():
    """Test SourceActionResponse schema."""
    response = SourceActionResponse(
        source_id="test_source",
        action="approve",
        success=True,
        message="Source approved",
    )
    assert response.source_id == "test_source"
    assert response.success is True


def test_source_ingest_request():
    """Test SourceIngestRequest schema."""
    request = SourceIngestRequest(
        source_id="new_source",
        path="/path/to/source.md",
    )
    assert request.source_id == "new_source"
    assert request.trust_tier == "C"


def test_source_ingest_response():
    """Test SourceIngestResponse schema."""
    response = SourceIngestResponse(
        source_id="new_source",
        status="pending",
        message="Ingestion queued",
    )
    assert response.source_id == "new_source"
    assert response.status == "pending"


def test_search_request():
    """Test SearchRequest schema."""
    request = SearchRequest(query="test query")
    assert request.query == "test query"
    assert request.top_k == 5
    assert request.mode == "hybrid"

    request = SearchRequest(
        query="another query",
        top_k=10,
        mode="keyword",
    )
    assert request.top_k == 10
    assert request.mode == "keyword"


def test_search_request_validation():
    """Test SearchRequest validation."""
    with pytest.raises(ValidationError):
        SearchRequest(query="test", top_k=0)  # top_k must be >= 1

    with pytest.raises(ValidationError):
        SearchRequest(query="test", top_k=51)  # top_k must be <= 50


def test_search_result_item():
    """Test SearchResultItem schema."""
    item = SearchResultItem(
        chunk_id="chunk_1",
        source_id="source_1",
        title="Test Source",
        score=0.85,
        trust_tier="A",
        text_preview="This is a preview...",
    )
    assert item.chunk_id == "chunk_1"
    assert item.score == 0.85


def test_search_response():
    """Test SearchResponse schema."""
    results = [
        SearchResultItem(
            chunk_id="c1",
            source_id="s1",
            title="Source 1",
            score=0.9,
            trust_tier="A",
            text_preview="Preview 1",
        )
    ]
    response = SearchResponse(
        query="test",
        mode="hybrid",
        results=results,
        total=1,
    )
    assert response.total == 1


def test_index_build_response():
    """Test IndexBuildResponse schema."""
    response = IndexBuildResponse(
        status="ok",
        chunk_count=100,
        source_count=10,
    )
    assert response.status == "ok"
    assert response.chunk_count == 100


def test_lesson_create_request():
    """Test LessonCreateRequest schema."""
    request = LessonCreateRequest(topic="test topic", source_pack="pqc_v1")
    assert request.topic == "test topic"
    assert request.source_pack == "pqc_v1"
    assert request.level == "intermediate"
    assert request.difficulty == 3
    assert request.retrieval_mode == "hybrid"

    request = LessonCreateRequest(
        topic="advanced topic",
        source_pack="pqc_v1",
        level="advanced",
        difficulty=5,
        lesson_format="threat_model",
    )
    assert request.level == "advanced"
    assert request.difficulty == 5
    assert request.task_format == "threat_model"


def test_lesson_create_response():
    """Test LessonCreateResponse schema."""
    response = LessonCreateResponse(
        lesson_id="lesson_123",
        run_id="run_123",
        status="created",
        topic="test topic",
        source_pack="pqc_v1",
        harness_status="PASS",
        proof_status="PASS",
        artifact_count=12,
        run_url="/runs/run_123",
    )
    assert response.lesson_id == "lesson_123"
    assert response.status == "created"
    assert response.run_url == "/runs/run_123"


def test_lesson_show_response():
    """Test LessonShowResponse schema."""
    response = LessonShowResponse(
        run_id="run_123",
        topic="test topic",
        lesson_markdown="# Test Lesson",
        sources=["source_1", "source_2"],
    )
    assert response.run_id == "run_123"
    assert len(response.sources) == 2


def test_run_summary_response():
    """Test RunSummaryResponse schema."""
    response = RunSummaryResponse(
        run_id="run_123",
        run_dir="/path/to/run",
        topic="test topic",
    )
    assert response.run_id == "run_123"
    assert response.harness_passed is None


def test_run_list_response():
    """Test RunListResponse schema."""
    runs = [
        RunSummaryResponse(run_id="r1", run_dir="/path/r1"),
        RunSummaryResponse(run_id="r2", run_dir="/path/r2"),
    ]
    response = RunListResponse(runs=runs, total=2)
    assert len(response.runs) == 2


def test_artifact_row_response():
    """Test ArtifactRowResponse schema."""
    response = ArtifactRowResponse(
        name="run_manifest.json",
        artifact_type="json",
        required=True,
        exists=True,
        validated=True,
    )
    assert response.name == "run_manifest.json"
    assert response.required is True


def test_artifact_list_response():
    """Test ArtifactListResponse schema."""
    artifacts = [
        ArtifactRowResponse(
            name="a1.json",
            artifact_type="json",
            required=True,
            exists=True,
            validated=True,
        )
    ]
    response = ArtifactListResponse(artifacts=artifacts, total=1)
    assert response.total == 1


def test_proof_bundle_response():
    """Test ProofBundleResponse schema."""
    response = ProofBundleResponse(
        run_id="run_123",
        status="PASS",
        manifest={"version": "2.0"},
        summary={"score": 0.85},
    )
    assert response.run_id == "run_123"
    assert response.status == "PASS"


def test_harness_report_response():
    """Test HarnessReportResponse schema."""
    response = HarnessReportResponse(
        run_id="run_123",
        passed=True,
        checks=[],
        blocking_failures=[],
        warnings=[],
        artifact_count=10,
    )
    assert response.run_id == "run_123"
    assert response.passed is True


def test_answer_submit_request():
    """Test AnswerSubmitRequest schema."""
    request = AnswerSubmitRequest(topic="test topic", answer_text="My answer")
    assert request.topic == "test topic"
    assert request.answer_text == "My answer"
    assert request.run_id is None

    request = AnswerSubmitRequest(
        topic="another topic",
        run_id="run_123",
        answer_text="Another answer",
    )
    assert request.topic == "another topic"
    assert request.run_id == "run_123"


def test_answer_submit_response():
    """Test AnswerSubmitResponse schema."""
    response = AnswerSubmitResponse(
        run_id="run_123",
        topic="test topic",
        score=0.85,
        feedback="Good answer",
        breakdown={"topic_relevance": 0.9},
    )
    assert response.run_id == "run_123"
    assert response.score == 0.85


def test_profile_show_response():
    """Test ProfileShowResponse schema."""
    response = ProfileShowResponse(
        profile_id="profile_123",
        topic="test topic",
        attempts=[],
        mastery={"topic_relevance": 0.8},
        strengths=["topic_relevance"],
        weaknesses=["source_grounding"],
    )
    assert response.profile_id == "profile_123"
    assert len(response.strengths) == 1


def test_learning_report_response():
    """Test LearningReportResponse schema."""
    response = LearningReportResponse(
        run_id="run_123",
        topic="test topic",
        report_markdown="# Learning Report",
        report_json={"score": 0.85},
    )
    assert response.run_id == "run_123"
    assert response.report_markdown == "# Learning Report"


def test_next_task_response():
    """Test NextTaskResponse schema."""
    response = NextTaskResponse(
        topic="test topic",
        focus="source_grounding",
        task_format="architecture_review",
        difficulty=3,
        guidance_level=3,
        reason="Focus on source grounding",
    )
    assert response.topic == "test topic"
    assert response.difficulty == 3


def test_error_response():
    """Test ErrorResponse schema."""
    response = ErrorResponse(
        error="Not found",
        detail="Source not found",
        code="NOT_FOUND",
    )
    assert response.error == "Not found"
    assert response.code == "NOT_FOUND"
