"""Integration tests for pack-scoped golden evals and release gating."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sourcelab.evals.answer_gold import normalize_answer_score_result
from sourcelab.evals.pack_scope import build_pack_search, get_pack_scoped_registry
from sourcelab.evals.runner import (
    STARTER_PACK_HIGH_RISK_CLAIM_PATTERNS,
    _run_answer_eval,
    _run_claim_eval,
    _run_learning_loop_eval,
    _run_retrieval_eval,
    run_golden_evals,
)
from sourcelab.harness.release_gate import verify_release
from sourcelab.learning.answer_scorer import AnswerScorer
from sourcelab.learning.mastery import update_mastery
from sourcelab.learning.next_task_selector import NextTaskSelector
from sourcelab.learning.schemas import SkillProfileV2
from sourcelab.learning.skill_profile import update_from_answer_review
from sourcelab.retrieval.index import PocketIndex
from sourcelab.sources.registry import SourceRegistry
from sourcelab.sources.source_pack import install_source_pack


DEMO_SOURCE_IDS = {"nist_pqc_notes", "rag_grounding_notes", "developer_tools_notes"}


@pytest.fixture
def project_root():
    return Path.cwd()


@pytest.fixture
def pack_name():
    return "pqc_v1"


class TestSourcePackMetadata:
    def test_install_writes_pack_metadata(self, project_root, pack_name):
        result = install_source_pack(project_root, pack_name)
        assert result["success"] is True

        registry = SourceRegistry.load_from_json(project_root / "data" / "source_registry.json")
        pack_sources = [source for source in registry.sources if source.source_id.startswith("nist_pqc_") or source.source_pack == pack_name]
        assert pack_sources
        for source in registry.sources:
            if source.source_id in {
                "nist_pqc_overview",
                "crypto_inventory_migration",
                "hybrid_key_exchange_notes",
            }:
                assert source.source_pack == pack_name
                assert source.pack_name == pack_name
                assert source.status == "active"
                assert source.approval_status == "approved"

    def test_idempotent_install_preserves_pack_metadata(self, project_root, pack_name):
        install_source_pack(project_root, pack_name)
        install_source_pack(project_root, pack_name)

        registry = SourceRegistry.load_from_json(project_root / "data" / "source_registry.json")
        for source in registry.sources:
            if source.source_id == "crypto_inventory_migration":
                assert source.source_pack == pack_name
                assert source.pack_name == pack_name


class TestRetrievalEvalScope:
    def test_retrieval_eval_scopes_to_pqc_v1(self, project_root, pack_name):
        install_source_pack(project_root, pack_name)
        report = _run_retrieval_eval(project_root, pack_name)

        assert report.pass_rate >= 0.8
        for diag in report.diagnostics:
            assert set(diag["candidate_source_ids"]).isdisjoint(DEMO_SOURCE_IDS)
            assert not set(diag["returned_source_ids"]) & DEMO_SOURCE_IDS

    def test_cryptographic_inventory_returns_expected_source(self, project_root, pack_name):
        install_source_pack(project_root, pack_name)
        search_fn, _ = build_pack_search(project_root, pack_name)
        results = search_fn("What is a cryptographic inventory?", top_k=5)
        source_ids = {result.source_id for result in results}
        assert "crypto_inventory_migration" in source_ids


class TestAnswerEvalScoring:
    def test_normalize_answer_review_v2(self):
        from sourcelab.learning.schemas import AnswerReviewV2

        review = AnswerReviewV2(
            topic="PQC",
            overall_score=0.82,
            needs_review=False,
            source_grounding_score=0.7,
            rubric_alignment_score=0.8,
            uncertainty_control_score=0.6,
            trap_avoidance_score=0.7,
        )
        result = normalize_answer_score_result(review)
        assert result["overall_score"] == 0.82
        assert result["needs_review"] is False

    def test_answer_eval_uses_overall_score(self, project_root, pack_name):
        install_source_pack(project_root, pack_name)
        report = _run_answer_eval(project_root, pack_name)
        assert report.total_cases == 15
        assert report.passed_cases == 15
        assert report.pass_rate == 1.0

    def test_strong_answers_score_higher_than_weak(self, project_root, pack_name):
        install_source_pack(project_root, pack_name)
        registry = get_pack_scoped_registry(project_root, pack_name)
        index = PocketIndex.from_registry(registry)
        scorer = AnswerScorer()

        strong = scorer.score_v2(
            topic="post-quantum cryptography migration",
            answer=(
                "According to NIST guidance, begin with a cryptographic inventory, "
                "prioritize migration based on risk, and use hybrid key exchange during transition."
            ),
            search_results=index.search("post-quantum cryptography migration", top_k=4),
        )
        weak = scorer.score_v2(
            topic="post-quantum cryptography migration",
            answer="PQC is important but not urgent. Just wait and see.",
            search_results=index.search("post-quantum cryptography migration", top_k=4),
        )
        assert strong.overall_score > weak.overall_score

    def test_risky_answer_triggers_review(self, project_root, pack_name):
        install_source_pack(project_root, pack_name)
        registry = get_pack_scoped_registry(project_root, pack_name)
        index = PocketIndex.from_registry(registry)
        scorer = AnswerScorer()
        review = scorer.score_v2(
            topic="quantum computing risk",
            answer="Quantum computers can definitely break RSA-2048 right now. Migrate immediately.",
            search_results=index.search("quantum computing risk", top_k=4),
        )
        assert review.needs_review is True


class TestLessonEvalScope:
    def test_lesson_eval_uses_pqc_source_ids(self, project_root, pack_name):
        install_source_pack(project_root, pack_name)
        results = run_golden_evals(project_root, pack_name, eval_types=["lessons"])
        report = results["lessons"]
        assert report["pass_rate"] >= 0.8
        assert report["failed_cases"] == 0


class TestLearningLoopEval:
    def test_learning_loop_eval_passes(self, project_root, pack_name):
        install_source_pack(project_root, pack_name)
        report = _run_learning_loop_eval(project_root, pack_name)
        assert report.total_cases == 3
        assert report.passed_cases == 3
        assert report.pass_rate == 1.0

    def test_strong_answer_raises_mastery_and_increases_difficulty(self, project_root, pack_name):
        install_source_pack(project_root, pack_name)
        registry = get_pack_scoped_registry(project_root, pack_name)
        index = PocketIndex.from_registry(registry)
        scorer = AnswerScorer()
        selector = NextTaskSelector()
        topic = "post-quantum cryptography migration"
        profile = SkillProfileV2(user_id="local_user")
        review = scorer.score_v2(
            topic=topic,
            answer=(
                "Based on NIST guidance, begin with a comprehensive cryptographic inventory "
                "that captures algorithms, key types, protocols, and dependencies. Prioritize "
                "migration based on data lifetime and risk, starting with long-lived sensitive "
                "data, and use hybrid implementations during transition."
            ),
            search_results=index.search(topic, top_k=4),
        )
        profile = update_from_answer_review(
            profile=profile, review=review, difficulty=3,
            task_format="architecture_review",
        )
        mastery = update_mastery(profile=profile, review=review, difficulty=3)
        next_task, rationale = selector.select_v2(
            topic=topic, answer_review=review, profile=profile,
            previous_task_format="architecture_review",
        )
        assert next_task.focus
        assert mastery.topic_mastery_after > mastery.topic_mastery_before
        assert next_task.difficulty >= 4
        assert next_task.guidance_level <= 2
        assert rationale.human_review_recommended is False

    def test_bad_answer_drops_mastery_and_raises_guidance(self, project_root, pack_name):
        install_source_pack(project_root, pack_name)
        registry = get_pack_scoped_registry(project_root, pack_name)
        index = PocketIndex.from_registry(registry)
        scorer = AnswerScorer()
        selector = NextTaskSelector()
        topic = "quantum computing risk"
        profile = SkillProfileV2(user_id="local_user")
        review = scorer.score_v2(
            topic=topic,
            answer="Quantum computers can definitely break RSA-2048 right now. Migrate immediately or your data is at risk.",
            search_results=index.search(topic, top_k=4),
        )
        profile = update_from_answer_review(
            profile=profile, review=review, difficulty=3,
            task_format="architecture_review",
        )
        mastery = update_mastery(profile=profile, review=review, difficulty=3)
        next_task, rationale = selector.select_v2(
            topic=topic, answer_review=review, profile=profile,
            previous_task_format="architecture_review",
        )
        assert mastery.topic_mastery_after < mastery.topic_mastery_before
        assert next_task.guidance_level >= 4
        assert rationale.human_review_recommended is True

    def test_learning_loop_runs_through_runner(self, project_root, pack_name):
        install_source_pack(project_root, pack_name)
        results = run_golden_evals(project_root, pack_name, eval_types=["learning_loop"])
        report = results["learning_loop"]
        assert report["total_cases"] == 3
        assert report["passed_cases"] == 3
        assert report["pass_rate"] == 1.0


class TestReleaseGating:
    def test_strict_release_fails_when_golden_evals_fail(self, project_root, tmp_path):
        evals_dir = project_root / "artifacts" / "evals" / "pqc_v1"
        evals_dir.mkdir(parents=True, exist_ok=True)
        summary_path = evals_dir / "golden_eval_summary.json"
        original = summary_path.read_text(encoding="utf-8") if summary_path.exists() else None

        summary_path.write_text(
            json.dumps(
                {
                    "pack_name": "pqc_v1",
                    "overall_pass_rate": 0.33,
                    "total_failed": 10,
                    "eval_reports": [
                        {"eval_name": "retrieval_gold", "pass_rate": 0.0},
                        {"eval_name": "answer_gold", "pass_rate": 0.0},
                    ],
                }
            ),
            encoding="utf-8",
        )
        try:
            report = verify_release(project_root, strict=True)
            golden_checks = [c for c in report["checks"] if c["check_name"] == "golden_evals_pass"]
            assert golden_checks
            assert golden_checks[0]["passed"] is False
            assert report["status"] == "FAIL"
        finally:
            if original is None:
                summary_path.unlink(missing_ok=True)
            else:
                summary_path.write_text(original, encoding="utf-8")

    def test_local_demo_passes_when_golden_evals_pass(self, project_root, pack_name):
        install_source_pack(project_root, pack_name)
        results = run_golden_evals(project_root, pack_name)
        assert results["summary"]["overall_pass_rate"] >= 0.8


class TestStarterPackEvalAlignment:
    @pytest.mark.parametrize("pack_name", ["agentic_engineering_v1", "local_ai_infra_v1", "rag_doc_intelligence_v1"])
    def test_core_pack_golden_evals_pass(self, project_root, pack_name):
        results = run_golden_evals(project_root, pack_name)
        summary = results["summary"]
        assert summary["total_failed"] == 0
        assert summary["overall_pass_rate"] == 1.0

    def test_starter_pack_high_risk_claim_patterns(self):
        assert "requires no validation" in STARTER_PACK_HIGH_RISK_CLAIM_PATTERNS
        assert "always production safe without evidence" in STARTER_PACK_HIGH_RISK_CLAIM_PATTERNS

    def test_starter_pack_claim_guardrail_is_unsupported(self, project_root):
        report = _run_claim_eval(project_root, "agentic_engineering_v1")
        guardrail_failures = [
            failure
            for failure in report.failures
            if "starter pack guardrails" in failure.case_description
        ]
        assert guardrail_failures == []

    def test_starter_pack_risky_answer_triggers_review(self, project_root):
        registry = get_pack_scoped_registry(project_root, "agentic_engineering_v1")
        index = PocketIndex.from_registry(registry)
        scorer = AnswerScorer()
        review = scorer.score_v2(
            topic="multi-agent software engineering control plane",
            answer=(
                "This approach is guaranteed to always work in production "
                "without validation or review."
            ),
            search_results=index.search("multi-agent software engineering control plane", top_k=4),
        )
        assert review.needs_review is True

    def test_local_ai_infra_retrieval_covers_hardware_terms(self, project_root):
        report = _run_retrieval_eval(project_root, "local_ai_infra_v1")
        assert report.failed_cases == 0
        assert report.pass_rate == 1.0
