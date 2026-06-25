"""Tests for Adaptive Research Loop v1."""

from __future__ import annotations

from pathlib import Path

from sourcelab.library.io import save_model, utc_now
from sourcelab.library.schemas import SourceExpansionSuggestion, SourceExpansionSuggestions
from sourcelab.research.evolution import (
    build_lesson_evolution_report,
    find_previous_run_ids,
    write_lesson_evolution_report,
)
from sourcelab.research.genericness import build_genericness_report
from sourcelab.research.library_expansion_plan import build_library_expansion_plan
from sourcelab.research.planner import build_research_plan
from sourcelab.research.schemas import GenericnessReport, ResearchPlan, RetrievalStrategy, SourceCoverageReport, TopicProfile
from sourcelab.research.source_coverage import build_source_coverage_report
from sourcelab.research.topic_profile import apply_topic_profile_update, build_topic_profile_update


def _seed_profile(root: Path, topic: str, source_pack: str, run_id: str) -> TopicProfile:
    coverage = SourceCoverageReport(
        run_id=run_id,
        topic=topic,
        source_pack=source_pack,
        generated_at=utc_now(),
        coverage_score=0.45,
        weak_labels=["needs_source_expansion", "thin_lesson"],
        gaps=["No finance-specific library cards"],
    )
    genericness = GenericnessReport(
        run_id=run_id,
        topic=topic,
        source_pack=source_pack,
        generated_at=utc_now(),
        verdict="somewhat_generic",
        genericness_score=0.48,
    )
    update = build_topic_profile_update(run_id, topic, source_pack, coverage, genericness)
    return apply_topic_profile_update(root, update)


def test_same_topic_follow_up_uses_profile(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    topic = "quantum hybrid portfolio optimizer"
    pack = "quantum_finance_v1"
    _seed_profile(root, topic, pack, "run1")

    first = build_research_plan("run1", topic, pack)
    follow_up = build_research_plan("run2", topic, pack, project_root=root)

    assert not first.profile_context_used
    assert follow_up.profile_context_used
    assert follow_up.profile_weak_concepts
    assert "needs_source_expansion" in follow_up.profile_weak_concepts


def test_weak_concept_in_follow_up_plan(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    topic = "clinical evidence graph assistant"
    pack = "biomedical_ai_v1"
    _seed_profile(root, topic, pack, "run1")

    plan = build_research_plan("run2", topic, pack, project_root=root)
    assert "weak concept reinforcement" in plan.follow_up_focus
    assert any("reinforce weak area" in q.lower() for q in plan.research_questions)


def test_evolution_report_written(tmp_path: Path):
    root = tmp_path / "proj"
    topic = "quantum hybrid portfolio optimizer"
    pack = "quantum_finance_v1"

    run1 = root / "artifacts" / "runs" / "run1"
    run2 = root / "artifacts" / "runs" / "run2"
    run1.mkdir(parents=True)
    run2.mkdir(parents=True)

    plan1 = build_research_plan("run1", topic, pack)
    plan2 = build_research_plan("run2", topic, pack, project_root=root)
    save_model(run1 / "research_plan.json", plan1)
    save_model(run2 / "research_plan.json", plan2)

    coverage1 = SourceCoverageReport(
        run_id="run1",
        topic=topic,
        source_pack=pack,
        generated_at=utc_now(),
        coverage_score=0.40,
        gaps=["Missing hybrid workflow sources"],
    )
    coverage2 = SourceCoverageReport(
        run_id="run2",
        topic=topic,
        source_pack=pack,
        generated_at=utc_now(),
        coverage_score=0.55,
        gaps=[],
    )
    save_model(run1 / "source_coverage_report.json", coverage1)
    save_model(run2 / "source_coverage_report.json", coverage2)

    report = write_lesson_evolution_report(root, run2, None, plan2, coverage=coverage2)
    assert (run2 / "lesson_evolution_report.json").exists()
    assert (run2 / "lesson_evolution_report.md").exists()
    assert report.previous_run_ids == ["run1"]
    assert report.verdict in ("improved", "unchanged", "worse")


def test_genericness_comparison(tmp_path: Path):
    root = tmp_path / "proj"
    topic = "multi-agent control plane"
    pack = "agentic_engineering_v1"
    run1 = root / "artifacts" / "runs" / "run1"
    run2 = root / "artifacts" / "runs" / "run2"
    run1.mkdir(parents=True)
    run2.mkdir(parents=True)

    plan1 = build_research_plan("run1", topic, pack)
    plan2 = build_research_plan("run2", topic, pack)
    save_model(run1 / "research_plan.json", plan1)
    save_model(run2 / "research_plan.json", plan2)

    gen1 = GenericnessReport(
        run_id="run1",
        topic=topic,
        source_pack=pack,
        generated_at=utc_now(),
        verdict="too_generic",
        genericness_score=0.72,
    )
    gen2 = GenericnessReport(
        run_id="run2",
        topic=topic,
        source_pack=pack,
        generated_at=utc_now(),
        verdict="specific",
        genericness_score=0.25,
    )
    save_model(run1 / "genericness_report.json", gen1)
    save_model(run2 / "genericness_report.json", gen2)

    report = build_lesson_evolution_report(root, run2, plan2)
    assert report.quality_delta.genericness_score_delta is not None
    assert report.quality_delta.genericness_score_delta < 0


def test_expansion_suggestions_to_collector_queries():
    suggestions = SourceExpansionSuggestions(
        run_id="run1",
        generated_at=utc_now(),
        thin_evidence=True,
        triggers=["low_retrieval_count:1"],
        suggestions=[
            SourceExpansionSuggestion(
                suggestion_id="run1_arxiv",
                reason="Add arXiv metadata",
                collector="arxiv",
                query_hint="quantum portfolio optimizer",
                priority="medium",
            ),
            SourceExpansionSuggestion(
                suggestion_id="run1_nvd",
                reason="Add CVE metadata",
                collector="nvd",
                query_hint="quantum portfolio optimizer",
                priority="low",
            ),
        ],
    )
    plan = build_library_expansion_plan("run1", "quantum hybrid portfolio optimizer", "quantum_finance_v1", suggestions)
    assert "arxiv" in plan.recommended_collectors
    assert any("collect-arxiv" in q.example_command for q in plan.collector_queries)
    assert any("collect-nvd" in q.example_command for q in plan.collector_queries)


def test_insufficient_history_safe(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = root / "artifacts" / "runs" / "run_only"
    run_dir.mkdir(parents=True)
    plan = build_research_plan("run_only", "new topic", "quantum_finance_v1")
    save_model(run_dir / "research_plan.json", plan)

    report = build_lesson_evolution_report(root, run_dir, plan)
    assert report.verdict == "insufficient_history"
    assert report.previous_run_ids == []
    assert find_previous_run_ids(root, plan.topic, plan.source_pack, "run_only") == []


def test_three_topics_differ_not_same_pattern():
    agentic = build_research_plan("r1", "multi-agent software engineering control plane", "agentic_engineering_v1")
    quantum = build_research_plan("r2", "quantum hybrid portfolio optimizer", "quantum_finance_v1")
    biomedical = build_research_plan("r3", "clinical evidence graph assistant", "biomedical_ai_v1")

    question_sets = [
        tuple(agentic.research_questions),
        tuple(quantum.research_questions),
        tuple(biomedical.research_questions),
    ]
    assert len(set(question_sets)) == 3

    focus_sets = [
        tuple(agentic.pack_focus_areas),
        tuple(quantum.pack_focus_areas),
        tuple(biomedical.pack_focus_areas),
    ]
    assert len(set(focus_sets)) == 3

    genericness_scores = []
    for plan in (agentic, quantum, biomedical):
        strategy = RetrievalStrategy(
            run_id=plan.run_id,
            topic=plan.topic,
            source_pack=plan.source_pack,
            generated_at=utc_now(),
            hits=[],
            selected_chunk_ids=[],
            source_pack_source_count=1,
            library_silver_card_count=0,
        )
        coverage = build_source_coverage_report(strategy, plan)
        report = build_genericness_report(
            run_id=plan.run_id,
            topic=plan.topic,
            source_pack=plan.source_pack,
            plan=plan,
            coverage=coverage,
        )
        genericness_scores.append(report.genericness_score)

    assert len(set(round(s, 2) for s in genericness_scores)) >= 2
