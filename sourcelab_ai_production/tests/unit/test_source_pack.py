"""Tests for source pack and golden evals.

Instruction:
- Test source pack manifest validation.
- Test source pack install and idempotency.
- Test golden eval loading and execution.
- Test eval summary generation.
- Test CLI commands.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sourcelab.sources.source_pack import (
    list_source_packs,
    load_source_pack_manifest,
    install_source_pack,
    validate_source_pack,
    source_pack_status,
)
from sourcelab.evals.schemas import (
    RetrievalGoldCase,
    ClaimGoldCase,
    AnswerGoldCase,
    LessonGoldCase,
    GoldenEvalReport,
    GoldenEvalSummary,
    GoldenEvalFailure,
)
from sourcelab.evals.retrieval_gold import load_retrieval_gold_cases, run_retrieval_gold_eval
from sourcelab.evals.claim_gold import load_claim_gold_cases, run_claim_gold_eval
from sourcelab.evals.answer_gold import load_answer_gold_cases, run_answer_gold_eval
from sourcelab.evals.lesson_gold import load_lesson_gold_cases, run_lesson_gold_eval
from sourcelab.evals.runner import (
    run_golden_evals,
    summarize_golden_eval_reports,
    write_golden_eval_report,
    write_golden_eval_summary,
)


@pytest.fixture
def project_root():
    """Return project root directory."""
    return Path.cwd()


@pytest.fixture
def pack_name():
    """Return test pack name."""
    return "pqc_v1"


class TestSourcePackSchemas:
    """Test source pack schemas."""

    def test_source_pack_manifest_loads(self, project_root, pack_name):
        manifest = load_source_pack_manifest(project_root, pack_name)
        assert manifest is not None
        assert manifest["pack_name"] == pack_name
        assert "sources" in manifest
        assert len(manifest["sources"]) > 0

    def test_source_pack_list(self, project_root):
        packs = list_source_packs(project_root)
        assert len(packs) > 0
        assert any(p["pack_name"] == "pqc_v1" for p in packs)

    def test_source_pack_validate(self, project_root, pack_name):
        result = validate_source_pack(project_root, pack_name)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_source_pack_status(self, project_root, pack_name):
        result = source_pack_status(project_root, pack_name)
        assert "installed" in result
        assert "pack_name" in result
        assert result["pack_name"] == pack_name


class TestSourcePackInstall:
    """Test source pack installation."""

    def test_install_source_pack(self, project_root, pack_name):
        result = install_source_pack(project_root, pack_name)
        assert result["success"] is True
        assert result["pack_name"] == pack_name
        # Sources may be installed or skipped (already present from prior run)
        total_handled = result["installed"] + result["skipped"]
        assert total_handled == 7, f"Expected 7 sources handled, got {total_handled}"

    def test_install_source_pack_idempotent(self, project_root, pack_name):
        # Install twice
        result1 = install_source_pack(project_root, pack_name)
        result2 = install_source_pack(project_root, pack_name)

        assert result1["success"] is True
        assert result2["success"] is True
        # Second install should skip existing sources
        assert result2["skipped"] > 0

    def test_install_nonexistent_pack(self, project_root):
        result = install_source_pack(project_root, "nonexistent_pack")
        assert result["success"] is False
        assert "error" in result


class TestGoldenEvalSchemas:
    """Test golden eval schemas."""

    def test_retrieval_gold_case(self):
        case = RetrievalGoldCase(
            query="test query",
            expected_source_ids=["source1"],
            expected_terms=["term1"],
        )
        assert case.query == "test query"
        assert case.expected_source_ids == ["source1"]

    def test_claim_gold_case(self):
        case = ClaimGoldCase(
            claim="test claim",
            expected_status="supported",
            claim_type="fact",
        )
        assert case.claim == "test claim"
        assert case.expected_status == "supported"

    def test_answer_gold_case(self):
        case = AnswerGoldCase(
            answer="test answer",
            topic="test topic",
            expected_quality="strong",
        )
        assert case.answer == "test answer"
        assert case.expected_quality == "strong"

    def test_lesson_gold_case(self):
        case = LessonGoldCase(
            topic="test topic",
            difficulty=3,
            task_format="architecture_review",
        )
        assert case.topic == "test topic"
        assert case.difficulty == 3

    def test_golden_eval_report(self):
        report = GoldenEvalReport(
            eval_name="test_eval",
            pack_name="test_pack",
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            pass_rate=0.8,
        )
        assert report.eval_name == "test_eval"
        assert report.pass_rate == 0.8

    def test_golden_eval_summary(self):
        summary = GoldenEvalSummary(
            pack_name="test_pack",
            total_evals=4,
            total_cases=40,
            total_passed=32,
            total_failed=8,
            overall_pass_rate=0.8,
        )
        assert summary.pack_name == "test_pack"
        assert summary.overall_pass_rate == 0.8

    def test_golden_eval_failure(self):
        failure = GoldenEvalFailure(
            case_index=0,
            case_description="Test case",
            expected="Expected value",
            actual="Actual value",
        )
        assert failure.case_index == 0
        assert failure.expected == "Expected value"


class TestRetrievalGold:
    """Test retrieval golden eval."""

    def test_load_retrieval_gold_cases(self, project_root, pack_name):
        cases = load_retrieval_gold_cases(project_root, pack_name)
        assert len(cases) == 10
        assert all("query" in c for c in cases)
        assert all("expected_source_ids" in c for c in cases)

    def test_run_retrieval_gold_eval(self, project_root, pack_name):
        def mock_search(query, top_k):
            # Return mock results that match expected sources
            from sourcelab.core.models import SearchResult

            return [
                SearchResult(
                    chunk_id="chunk1",
                    source_id="crypto_inventory_migration",
                    title="Test",
                    score=0.9,
                    trust_tier="B",
                    text_preview="Test content about " + query,
                )
            ]

        report = run_retrieval_gold_eval(project_root, pack_name, mock_search)
        assert report.eval_name == "retrieval_gold"
        assert report.total_cases == 10
        assert report.passed_cases > 0


class TestClaimGold:
    """Test claim golden eval."""

    def test_load_claim_gold_cases(self, project_root, pack_name):
        cases = load_claim_gold_cases(project_root, pack_name)
        assert len(cases) == 15
        assert all("claim" in c for c in cases)
        assert all("expected_status" in c for c in cases)

    def test_run_claim_gold_eval(self, project_root, pack_name):
        def mock_verify(claim_text):
            # Mock verification that correctly identifies high-risk claims
            high_risk_patterns = [
                "quantum computers can break rsa",
                "quantum computers can break rsa-2048",
                "quantum computers will break all cryptography",
                "immediately remove every classical algorithm",
                "no interoperability risks",
                "production-ready implementations",
            ]

            claim_lower = claim_text.lower()
            for pattern in high_risk_patterns:
                if pattern in claim_lower:
                    return {
                        "support_status": "unsupported",
                        "severity": "high",
                    }

            return {
                "support_status": "supported",
                "severity": "low",
            }

        report = run_claim_gold_eval(project_root, pack_name, mock_verify)
        assert report.eval_name == "claim_gold"
        assert report.total_cases == 15
        assert report.passed_cases > 0


class TestAnswerGold:
    """Test answer golden eval."""

    def test_load_answer_gold_cases(self, project_root, pack_name):
        cases = load_answer_gold_cases(project_root, pack_name)
        assert len(cases) == 15
        assert all("answer" in c for c in cases)
        assert all("expected_quality" in c for c in cases)

    def test_run_answer_gold_eval(self, project_root, pack_name):
        def mock_score(answer_text, topic):
            # Mock scoring based on answer quality
            answer_lower = answer_text.lower()

            # Check for unsupported claims
            if any(phrase in answer_lower for phrase in [
                "quantum computers can break rsa",
                "quantum computers can break rsa-2048",
                "quantum computers will break all cryptography",
                "immediately remove every classical algorithm",
                "no interoperability risks",
                "production-ready implementations",
            ]):
                return {
                    "overall_score": 0.1,
                    "needs_review": True,
                }

            # Strong answers have source citations and specific details
            if any(phrase in answer_lower for phrase in [
                "according to",
                "based on",
                "nist",
                "inventory",
                "hybrid",
            ]):
                return {
                    "overall_score": 0.8,
                    "needs_review": False,
                }

            # Weak answers are vague
            return {
                "overall_score": 0.4,
                "needs_review": False,
            }

        report = run_answer_gold_eval(project_root, pack_name, mock_score)
        assert report.eval_name == "answer_gold"
        assert report.total_cases == 15
        assert report.passed_cases > 0


class TestLessonGold:
    """Test lesson golden eval."""

    def test_load_lesson_gold_cases(self, project_root, pack_name):
        cases = load_lesson_gold_cases(project_root, pack_name)
        assert len(cases) == 5
        assert all("topic" in c for c in cases)
        assert all("required_source_ids" in c for c in cases)

    def test_run_lesson_gold_eval(self, project_root, pack_name):
        def mock_generate(topic, difficulty, task_format):
            # Map topics to their required source_ids from lesson_gold.json
            topic_sources = {
                "post-quantum cryptography migration planning": ["crypto_inventory_migration", "nist_pqc_overview"],
                "cryptographic inventory best practices": ["crypto_inventory_migration"],
                "hybrid key exchange implementation": ["hybrid_key_exchange_notes"],
                "crypto agility for post-quantum transition": ["crypto_agility_notes"],
                "quantum cybersecurity myths debunked": ["risk_myths_quantum_breaks_rsa_today"],
            }
            source_ids = topic_sources.get(topic, ["crypto_inventory_migration", "nist_pqc_overview"])

            # Mock generation that returns valid package
            return {
                "package": {
                    "topic": topic,
                    "source_ids": source_ids,
                },
                "harness_passed": True,
                "verification": {
                    "unsupported_high_risk": 0,
                    "claim_map": [],
                },
            }

        report = run_lesson_gold_eval(project_root, pack_name, mock_generate)
        assert report.eval_name == "lesson_gold"
        assert report.total_cases == 5
        assert report.passed_cases == 5


class TestEvalRunner:
    """Test eval runner."""

    def test_summarize_golden_eval_reports(self):
        reports = [
            GoldenEvalReport(
                eval_name="retrieval",
                pack_name="test",
                total_cases=10,
                passed_cases=8,
                failed_cases=2,
                pass_rate=0.8,
            ),
            GoldenEvalReport(
                eval_name="claims",
                pack_name="test",
                total_cases=15,
                passed_cases=12,
                failed_cases=3,
                pass_rate=0.8,
            ),
        ]

        summary = summarize_golden_eval_reports(reports, "test")
        assert summary.total_evals == 2
        assert summary.total_cases == 25
        assert summary.total_passed == 20
        assert summary.total_failed == 5
        assert summary.overall_pass_rate == 0.8

    def test_write_golden_eval_report(self, tmp_path):
        report = GoldenEvalReport(
            eval_name="test",
            pack_name="test",
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            pass_rate=0.8,
        )

        path = write_golden_eval_report(report, tmp_path, "test_report.json")
        assert path.exists()

        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["eval_name"] == "test"
        assert loaded["pass_rate"] == 0.8

    def test_write_golden_eval_summary(self, tmp_path):
        summary = GoldenEvalSummary(
            pack_name="test",
            total_evals=1,
            total_cases=10,
            total_passed=8,
            total_failed=2,
            overall_pass_rate=0.8,
        )

        json_path, md_path = write_golden_eval_summary(summary, tmp_path)
        assert json_path.exists()
        assert md_path.exists()

        loaded = json.loads(json_path.read_text(encoding="utf-8"))
        assert loaded["pack_name"] == "test"

        md_content = md_path.read_text(encoding="utf-8")
        assert "Golden Eval Summary" in md_content
        assert "80.0%" in md_content


class TestCLIBackend:
    """Test CLI backend functions."""

    def test_cmd_source_pack_list(self, project_root):
        from sourcelab.cli import cmd_source_pack_list
        import argparse

        args = argparse.Namespace()
        # Should not raise
        cmd_source_pack_list(args)

    def test_cmd_source_pack_validate(self, project_root):
        from sourcelab.cli import cmd_source_pack_validate
        import argparse

        args = argparse.Namespace(pack_name="pqc_v1")
        # Should not raise
        cmd_source_pack_validate(args)

    def test_cmd_source_pack_install(self, project_root):
        from sourcelab.cli import cmd_source_pack_install
        import argparse

        args = argparse.Namespace(pack_name="pqc_v1")
        # Should not raise
        cmd_source_pack_install(args)

    def test_cmd_source_pack_status(self, project_root):
        from sourcelab.cli import cmd_source_pack_status
        import argparse

        args = argparse.Namespace(pack_name="pqc_v1")
        # Should not raise
        cmd_source_pack_status(args)
