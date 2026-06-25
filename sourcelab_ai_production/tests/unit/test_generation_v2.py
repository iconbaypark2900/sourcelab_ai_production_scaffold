"""Tests for Generation v2: Real Source-Grounded Lesson Package.

Instruction:
- Test schema validation, fail-closed behavior, rubric weights,
  answer key citations, generation trace, and pipeline artifacts.
"""

from pathlib import Path

import pytest

from sourcelab.core.models import SearchResult
from sourcelab.generation.answer_key_generator import AnswerKeyGenerator
from sourcelab.generation.lesson_generator import SourceGroundedLessonGenerator
from sourcelab.generation.rubric_generator import RubricGenerator
from sourcelab.generation.schemas import (
    GeneratedAnswerKey,
    GeneratedLessonPackage,
    GeneratedRubric,
    GenerationTrace,
)
from sourcelab.generation.scenario_generator import ScenarioGenerator
from sourcelab.generation.trace import create_generation_trace
from sourcelab.retrieval.index import PocketIndex
from sourcelab.sources.registry import SourceRegistry
from sourcelab.verification.claim_verifier import ClaimVerifier


def _get_search_results(topic: str = "post quantum cryptography migration") -> list[SearchResult]:
    """Helper to get search results for testing."""
    registry = SourceRegistry.bootstrap_demo(Path.cwd())
    index = PocketIndex.from_registry(registry)
    return index.search(topic, top_k=4)


def test_lesson_package_schema_validates():
    """Lesson package schema validates with required fields."""
    package = GeneratedLessonPackage(
        topic="test topic",
        level="intermediate",
        source_ids=["src1"],
        chunk_ids=["chunk1"],
    )
    assert package.topic == "test topic"
    assert package.level == "intermediate"
    assert "src1" in package.source_ids


def test_generation_fails_when_no_sources():
    """Generation fails closed when no sources are provided."""
    generator = SourceGroundedLessonGenerator()
    package = generator.generate_package(
        topic="test topic",
        search_results=[],
        difficulty=3,
        task_format="architecture_review",
        audience="engineer",
    )
    assert package.generation_trace is not None
    assert package.generation_trace.fail_closed_reason is not None
    assert "without sources" in package.generation_trace.fail_closed_reason
    assert package.lesson is None


def test_rubric_weights_sum_to_one():
    """Rubric weights must sum to 1.0."""
    package = GeneratedLessonPackage(topic="test")
    rubric_gen = RubricGenerator()
    rubric = rubric_gen.generate(package)
    assert rubric.weights_sum() == 1.0
    assert len(rubric.criteria) > 0
    for criterion in rubric.criteria:
        assert criterion.weight > 0
        assert criterion.name
        assert criterion.description


def test_answer_key_includes_source_ids_and_chunk_ids():
    """Answer key must include source_ids and chunk_ids."""
    search_results = _get_search_results()
    generator = SourceGroundedLessonGenerator()
    package = generator.generate_package(
        topic="post quantum cryptography migration",
        search_results=search_results,
        difficulty=3,
    )
    answer_key_gen = AnswerKeyGenerator()
    answer_key = answer_key_gen.generate(package, search_results)
    assert len(answer_key.source_ids) > 0
    assert len(answer_key.chunk_ids) > 0
    assert len(answer_key.source_references) > 0
    for ref in answer_key.source_references:
        assert ref.source_id
        assert ref.chunk_id


def test_generation_trace_includes_source_ids_and_chunk_ids():
    """Generation trace must include source_ids and chunk_ids."""
    search_results = _get_search_results()
    generator = SourceGroundedLessonGenerator()
    package = generator.generate_package(
        topic="post quantum cryptography migration",
        search_results=search_results,
        difficulty=3,
    )
    trace = package.generation_trace
    assert trace is not None
    assert len(trace.source_ids) > 0
    assert len(trace.chunk_ids) > 0
    assert trace.topic == "post quantum cryptography migration"
    assert trace.difficulty == 3


def test_generation_trace_creation():
    """Test the create_generation_trace helper function."""
    trace = create_generation_trace(
        topic="test topic",
        difficulty=3,
        task_format="architecture_review",
        source_ids=["src1", "src2"],
        chunk_ids=["c1", "c2"],
    )
    assert trace.topic == "test topic"
    assert trace.source_ids == ["src1", "src2"]
    assert trace.chunk_ids == ["c1", "c2"]
    assert trace.timestamp  # Should have a timestamp


def test_claim_verifier_works_with_lesson_package():
    """Claim verifier can verify claims from a lesson package."""
    search_results = _get_search_results()
    generator = SourceGroundedLessonGenerator()
    package = generator.generate_package(
        topic="post quantum cryptography migration",
        search_results=search_results,
        difficulty=3,
    )
    verifier = ClaimVerifier()
    claims = verifier.verify_lesson_package(package, search_results)
    assert len(claims) > 0
    for claim in claims:
        assert claim.claim
        assert claim.support_status in ("supported", "unsupported", "uncertain")


def test_claim_verifier_fails_closed_without_sources():
    """Claim verifier fails closed when no sources provided."""
    generator = SourceGroundedLessonGenerator()
    package = generator.generate_package(
        topic="test topic",
        search_results=[],
        difficulty=3,
    )
    verifier = ClaimVerifier()
    claims = verifier.verify_lesson_package(package, [])
    assert len(claims) == 1
    assert claims[0].support_status == "unsupported"
    assert claims[0].severity == "high"


def test_scenario_generator_produces_valid_output():
    """Scenario generator produces valid output with all parameters."""
    search_results = _get_search_results()
    gen = ScenarioGenerator()
    scenario = gen.generate(
        topic="post quantum cryptography migration",
        search_results=search_results,
        difficulty=4,
        task_format="risk_review",
        audience="cto",
    )
    assert scenario.difficulty == 4
    assert scenario.task_format == "risk_review"
    assert scenario.audience == "cto"
    assert len(scenario.source_ids) > 0
    assert len(scenario.chunk_ids) > 0


def test_lesson_package_has_all_components():
    """Lesson package includes scenario, lesson, rubric, answer key, and trace."""
    search_results = _get_search_results()
    generator = SourceGroundedLessonGenerator()
    package = generator.generate_package(
        topic="post quantum cryptography migration",
        search_results=search_results,
        difficulty=3,
        task_format="architecture_review",
        audience="engineer",
    )
    assert package.scenario is not None
    assert package.lesson is not None
    assert package.generation_trace is not None
    assert len(package.source_ids) > 0
    assert len(package.chunk_ids) > 0
    assert len(package.claim_candidates) > 0


def test_backward_compatibility_legacy_generate():
    """Legacy generate method still works for backward compatibility."""
    search_results = _get_search_results()
    generator = SourceGroundedLessonGenerator()
    lesson = generator.generate("post quantum cryptography migration", search_results)
    assert lesson.topic == "post quantum cryptography migration"
    assert lesson.title
    assert len(lesson.source_ids) > 0
