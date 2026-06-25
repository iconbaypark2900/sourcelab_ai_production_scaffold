"""Tests for genericness detection."""

from __future__ import annotations

from sourcelab.library.io import utc_now
from sourcelab.research.genericness import build_genericness_report
from sourcelab.research.planner import build_research_plan
from sourcelab.research.schemas import SourceCoverageReport
from sourcelab.generation.schemas import GeneratedLesson, GeneratedLessonPackage


def test_specific_topic_scores_lower_genericness():
    plan = build_research_plan("run1", "multi-agent software engineering control plane", "agentic_engineering_v1")
    coverage = SourceCoverageReport(
        run_id="run1",
        topic=plan.topic,
        source_pack=plan.source_pack,
        generated_at=utc_now(),
        coverage_score=0.72,
    )
    package = GeneratedLessonPackage(
        topic=plan.topic,
        lesson=GeneratedLesson(
            title="Control plane for multi-agent runs",
            learning_objectives=["Explain orchestration guardrails"],
            task_instructions="Design a control plane with grounding checks.",
            source_ids=["agent_doc"],
            chunk_ids=["agent::chunk-000"],
        )
    )
    report = build_genericness_report("run1", plan.topic, plan.source_pack, plan, coverage, package)
    assert report.verdict in {"specific", "somewhat_generic"}


def test_vague_topic_can_be_too_generic():
    plan = build_research_plan("run2", "overview", "quantum_finance_v1")
    coverage = SourceCoverageReport(
        run_id="run2",
        topic=plan.topic,
        source_pack=plan.source_pack,
        generated_at=utc_now(),
        coverage_score=0.2,
        weak_labels=["insufficient_evidence", "needs_source_expansion"],
    )
    report = build_genericness_report("run2", plan.topic, plan.source_pack, plan, coverage, None)
    assert report.genericness_score >= 0.38
