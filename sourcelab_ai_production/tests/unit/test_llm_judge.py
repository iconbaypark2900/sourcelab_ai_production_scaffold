"""Tests for LLM judge integration in the answer scorer."""

import json
from pathlib import Path

import pytest

from sourcelab.core.models import SearchResult
from sourcelab.generation.schemas import GeneratedRubric, RubricCriterion
from sourcelab.generation.model_router import ModelRouter
from sourcelab.learning.answer_scorer import AnswerScorer, LLM_JUDGE_CRITERIA
from sourcelab.models.config import get_model_config
from sourcelab.models.schemas import ModelRouterConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_SEARCH_RESULTS = [
    SearchResult(
        chunk_id="chunk_001",
        source_id="src_a",
        title="Source A",
        score=0.95,
        trust_tier="A",
        text_preview="Post-quantum cryptography migration requires careful inventory planning.",
    ),
    SearchResult(
        chunk_id="chunk_002",
        source_id="src_b",
        title="Source B",
        score=0.85,
        trust_tier="B",
        text_preview="NIST recommends hybrid certificate authorities for TLS 1.3.",
    ),
]

_SAMPLE_RUBRIC = GeneratedRubric(
    criteria=[
        RubricCriterion(name="topic_relevance", weight=0.20, description="Relevance to topic"),
        RubricCriterion(name="source_grounding", weight=0.25, description="Grounded in sources"),
        RubricCriterion(name="practical_reasoning", weight=0.20, description="Practical steps"),
        RubricCriterion(name="uncertainty_control", weight=0.15, description="Handles uncertainty"),
        RubricCriterion(name="trap_avoidance", weight=0.10, description="Avoids traps"),
        RubricCriterion(name="clarity", weight=0.05, description="Clear structure"),
        RubricCriterion(name="citation_use_of_evidence", weight=0.05, description="Uses citations"),
    ]
)

_STRONG_ANSWER = (
    "Migrating to post-quantum cryptography requires a systematic approach. "
    "First, organizations should conduct a cryptographic inventory to identify "
    "all uses of RSA and ECC. NIST guidance recommends prioritizing systems "
    "that handle long-lived data. A hybrid approach using both classical and "
    "quantum-resistant algorithms minimizes risk during transition. "
    "It is important to avoid claiming that any single algorithm is a "
    "drop-in replacement, as compatibility testing is essential. "
    "Reference: NIST SP 800-227."
)


def _make_router() -> ModelRouter:
    return ModelRouter(
        ModelRouterConfig(mode="deterministic", backend="deterministic")
    )


# ---------------------------------------------------------------------------
# Basic construction
# ---------------------------------------------------------------------------


def test_scorer_default_no_llm():
    scorer = AnswerScorer()
    assert not scorer._enable_llm_judge
    assert scorer._model_router is None


def test_scorer_with_llm_enabled():
    router = _make_router()
    scorer = AnswerScorer(enable_llm_judge=True, model_router=router)
    assert scorer._enable_llm_judge
    assert scorer._model_router is router


def test_scorer_with_blend():
    router = _make_router()
    scorer = AnswerScorer(enable_llm_judge=True, model_router=router, llm_judge_blend=0.7)
    assert scorer._llm_judge_blend == 0.7


def test_scorer_blend_clamped():
    router = _make_router()
    scorer = AnswerScorer(enable_llm_judge=True, model_router=router, llm_judge_blend=1.5)
    assert scorer._llm_judge_blend == 1.0
    scorer2 = AnswerScorer(enable_llm_judge=True, model_router=router, llm_judge_blend=-0.5)
    assert scorer2._llm_judge_blend == 0.0


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


def test_build_judge_prompt_includes_topic_and_answer():
    router = _make_router()
    scorer = AnswerScorer(enable_llm_judge=True, model_router=router)
    prompt = scorer._build_judge_prompt(
        topic="PQC Migration",
        answer=_STRONG_ANSWER,
        rubric=_SAMPLE_RUBRIC,
        search_results=_SAMPLE_SEARCH_RESULTS,
    )
    assert "PQC Migration" in prompt
    assert "Migrating to post-quantum cryptography" in prompt
    assert "topic_relevance" in prompt
    assert "src_a" in prompt


def test_build_judge_prompt_without_rubric():
    router = _make_router()
    scorer = AnswerScorer(enable_llm_judge=True, model_router=router)
    prompt = scorer._build_judge_prompt(
        topic="PQC", answer="Some answer.", rubric=None, search_results=[]
    )
    assert "topic_relevance" in prompt
    assert "DEFAULT_CRITERION_WEIGHTS" not in prompt  # should use default weights text


# ---------------------------------------------------------------------------
# LLM judge call with deterministic backend
# ---------------------------------------------------------------------------


def test_llm_judge_returns_valid_scores():
    router = _make_router()
    scorer = AnswerScorer(enable_llm_judge=True, model_router=router)
    llm_scores, warnings, feedback, strengths, weaknesses = scorer._llm_judge(
        topic="PQC",
        answer=_STRONG_ANSWER,
        search_results=_SAMPLE_SEARCH_RESULTS,
        rubric=_SAMPLE_RUBRIC,
    )
    assert llm_scores is not None
    assert len(llm_scores) == len(LLM_JUDGE_CRITERIA)
    for name in LLM_JUDGE_CRITERIA:
        assert name in llm_scores
        assert 0.0 <= llm_scores[name] <= 1.0
    assert feedback
    assert strengths
    assert weaknesses


def test_llm_judge_no_model_router():
    scorer = AnswerScorer(enable_llm_judge=True, model_router=None)
    llm_scores, warnings, feedback, strengths, weaknesses = scorer._llm_judge(
        topic="PQC", answer="test", search_results=[], rubric=None,
    )
    assert llm_scores is None
    assert any("No model_router" in w for w in warnings)


# ---------------------------------------------------------------------------
# Full score_v2 with and without LLM judge
# ---------------------------------------------------------------------------


def test_score_v2_without_llm_matches_heuristic():
    """When enable_llm_judge=False, output should match pure heuristic."""
    scorer = AnswerScorer(enable_llm_judge=False)
    review = scorer.score_v2(
        topic="PQC Migration",
        answer=_STRONG_ANSWER,
        search_results=_SAMPLE_SEARCH_RESULTS,
        rubric=_SAMPLE_RUBRIC,
    )
    assert not review.llm_judge_used
    assert review.llm_judge_warnings == []
    assert review.llm_blended_score is None
    assert 0.0 <= review.overall_score <= 1.0


def test_score_v2_with_llm_judge_adds_blended_score():
    """When LLM judge is enabled, llm_blended_score should be set."""
    router = _make_router()
    scorer = AnswerScorer(enable_llm_judge=True, model_router=router, llm_judge_blend=0.5)
    review = scorer.score_v2(
        topic="PQC Migration",
        answer=_STRONG_ANSWER,
        search_results=_SAMPLE_SEARCH_RESULTS,
        rubric=_SAMPLE_RUBRIC,
    )
    assert review.llm_judge_used
    assert review.llm_blended_score is not None
    assert 0.0 <= review.llm_blended_score <= 1.0
    # Criterion scores should have llm fields
    for cs in review.criterion_scores:
        assert cs.llm_score is not None
        assert cs.llm_feedback


def test_score_v2_with_llm_blend_zero():
    """blend=0 means pure heuristic even with LLM enabled."""
    router = _make_router()
    scorer = AnswerScorer(enable_llm_judge=True, model_router=router, llm_judge_blend=0.0)
    review = scorer.score_v2(
        topic="PQC Migration",
        answer=_STRONG_ANSWER,
        search_results=_SAMPLE_SEARCH_RESULTS,
        rubric=_SAMPLE_RUBRIC,
    )
    assert review.llm_judge_used
    assert review.llm_blended_score is not None


def test_score_v2_with_llm_blend_one():
    """blend=1 means only LLM scores used."""
    router = _make_router()
    scorer = AnswerScorer(enable_llm_judge=True, model_router=router, llm_judge_blend=1.0)
    review = scorer.score_v2(
        topic="PQC Migration",
        answer=_STRONG_ANSWER,
        search_results=_SAMPLE_SEARCH_RESULTS,
        rubric=_SAMPLE_RUBRIC,
    )
    assert review.llm_judge_used


def test_score_v2_llm_fallback_no_router():
    """When no router provided, LLM judge logs warnings but scoring still works."""
    scorer = AnswerScorer(enable_llm_judge=True, model_router=None)
    review = scorer.score_v2(
        topic="PQC Migration",
        answer=_STRONG_ANSWER,
        search_results=_SAMPLE_SEARCH_RESULTS,
        rubric=_SAMPLE_RUBRIC,
    )
    # Fallback to pure heuristic; no model_router warning is suppressed
    assert not review.llm_judge_used
    assert review.llm_blended_score is None
    assert 0.0 <= review.overall_score <= 1.0


# ---------------------------------------------------------------------------
# Score blending verification
# ---------------------------------------------------------------------------


def test_llm_judge_blends_correctly():
    """Verify blend math: blended = blend * llm + (1-blend) * heuristic."""
    router = _make_router()
    # The deterministic backend returns topic_relevance=0.85
    # The heuristic for topic_relevance can be computed
    scorer = AnswerScorer(enable_llm_judge=True, model_router=router, llm_judge_blend=0.5)

    # First get heuristic-only scores
    heuristic_scorer = AnswerScorer(enable_llm_judge=False)
    heuristic_review = heuristic_scorer.score_v2(
        topic="PQC Migration",
        answer=_STRONG_ANSWER,
        search_results=_SAMPLE_SEARCH_RESULTS,
        rubric=_SAMPLE_RUBRIC,
    )

    # Now get LLM-blended scores
    blended_review = scorer.score_v2(
        topic="PQC Migration",
        answer=_STRONG_ANSWER,
        search_results=_SAMPLE_SEARCH_RESULTS,
        rubric=_SAMPLE_RUBRIC,
    )

    # The scores should differ (LLM judge changes them)
    assert blended_review.llm_judge_used

    # The LLM judge output contains the raw LLM scores in criterion_scores[0].llm_score
    # The blended score in criterion_scores[0].score should be between the LLM and heuristic
    for cs_blended, cs_heuristic in zip(blended_review.criterion_scores, heuristic_review.criterion_scores):
        if cs_blended.llm_score is not None:
            # The blended score should be between the LLM score and the heuristic score
            # (or equal to one of them if blend is 0 or 1)
            lower = min(cs_blended.llm_score, cs_heuristic.score)
            upper = max(cs_blended.llm_score, cs_heuristic.score)
            assert lower <= cs_blended.score <= upper + 0.01, (
                f"{cs_blended.criterion_name}: heuristic={cs_heuristic.score}, "
                f"llm={cs_blended.llm_score}, blended={cs_blended.score}"
            )


# ---------------------------------------------------------------------------
# Criterion score with LLM fields
# ---------------------------------------------------------------------------


def test_criterion_scores_include_llm_fields():
    router = _make_router()
    scorer = AnswerScorer(enable_llm_judge=True, model_router=router)
    review = scorer.score_v2(
        topic="PQC",
        answer=_STRONG_ANSWER,
        search_results=_SAMPLE_SEARCH_RESULTS,
        rubric=_SAMPLE_RUBRIC,
    )
    for cs in review.criterion_scores:
        assert cs.llm_score is not None, f"{cs.criterion_name} missing llm_score"
        assert 0.0 <= cs.llm_score <= 1.0, f"{cs.criterion_name} llm_score out of range"


def test_criterion_scores_no_llm_fields_when_disabled():
    scorer = AnswerScorer(enable_llm_judge=False)
    review = scorer.score_v2(
        topic="PQC",
        answer=_STRONG_ANSWER,
        search_results=_SAMPLE_SEARCH_RESULTS,
        rubric=_SAMPLE_RUBRIC,
    )
    for cs in review.criterion_scores:
        assert cs.llm_score is None
        assert cs.llm_feedback == ""


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_answer():
    router = _make_router()
    scorer = AnswerScorer(enable_llm_judge=True, model_router=router)
    review = scorer.score_v2(
        topic="PQC",
        answer="",
        search_results=_SAMPLE_SEARCH_RESULTS,
        rubric=_SAMPLE_RUBRIC,
    )
    # Should still return a valid review
    assert review.overall_score >= 0.0
    assert review.llm_judge_used


def test_no_search_results():
    router = _make_router()
    scorer = AnswerScorer(enable_llm_judge=True, model_router=router)
    review = scorer.score_v2(
        topic="PQC",
        answer=_STRONG_ANSWER,
        search_results=[],
        rubric=_SAMPLE_RUBRIC,
    )
    assert review.overall_score >= 0.0
    assert review.llm_judge_used


def test_no_rubric_with_llm():
    router = _make_router()
    scorer = AnswerScorer(enable_llm_judge=True, model_router=router)
    review = scorer.score_v2(
        topic="PQC",
        answer=_STRONG_ANSWER,
        search_results=_SAMPLE_SEARCH_RESULTS,
        rubric=None,
    )
    assert review.overall_score >= 0.0
    assert review.llm_judge_used
    assert review.criterion_scores == []  # No rubric -> no criterion_scores


# ---------------------------------------------------------------------------
# LLM judge with warnings
# ---------------------------------------------------------------------------


def test_llm_judge_warnings_empty_on_success():
    router = _make_router()
    scorer = AnswerScorer(enable_llm_judge=True, model_router=router)
    review = scorer.score_v2(
        topic="PQC",
        answer=_STRONG_ANSWER,
        search_results=_SAMPLE_SEARCH_RESULTS,
        rubric=_SAMPLE_RUBRIC,
    )
    assert review.llm_judge_used
    # Should be no warnings since deterministic backend succeeds
    assert len(review.llm_judge_warnings) == 0


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


def test_backward_compatibility_score_v1_still_works():
    """The legacy score() method should be unchanged."""
    from sourcelab.core.models import LessonTask

    scorer = AnswerScorer()
    task = LessonTask(
        topic="PQC",
        title="Test",
        scenario="Test scenario",
        task="Analyze",
        difficulty=3,
        expected_behavior="Good answer",
        failure_trap="Bad answer",
        source_ids=["src_a"],
    )
    review = scorer.score(
        topic="PQC",
        task=task,
        answer=_STRONG_ANSWER,
        search_results=_SAMPLE_SEARCH_RESULTS,
        rubric=_SAMPLE_RUBRIC,
    )
    assert 0.0 <= review.score <= 1.0
    assert "topic_relevance" in review.breakdown
