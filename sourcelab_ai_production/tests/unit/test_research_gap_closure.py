"""Tests for Research Gap Closure Loop v1."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from sourcelab.library.io import save_model, utc_now
from sourcelab.library.schemas import LibraryBuildReport, SourceExpansionSuggestion, SourceExpansionSuggestions
from sourcelab.research.expansion_execution import (
    SUPPORTED_COLLECTORS,
    build_library_expansion_execution,
    write_library_expansion_execution,
)
from sourcelab.research.gap_closure import build_gap_closure_report, write_gap_closure_report
from sourcelab.research.library_expansion_plan import build_library_expansion_plan
from sourcelab.research.library_improvement import build_library_improvement_report, snapshot_library_metrics
from sourcelab.research.planner import build_research_plan
from sourcelab.research.schemas import (
    CollectorQueryPlan,
    GenericnessReport,
    LabeledRetrievalHit,
    LibraryExpansionExecution,
    RetrievalStrategy,
    SourceCoverageReport,
)
from sourcelab.research.source_promotion import (
    build_source_promotion_report,
    write_source_promotion_report,
)


def _expansion_suggestions(run_id: str, topic: str) -> SourceExpansionSuggestions:
    return SourceExpansionSuggestions(
        run_id=run_id,
        generated_at=utc_now(),
        thin_evidence=True,
        triggers=["low_retrieval_count:1"],
        suggestions=[
            SourceExpansionSuggestion(
                suggestion_id=f"{run_id}_local",
                reason="local docs",
                collector="local_docs",
                query_hint=".",
                domain_tags=["user_project_library"],
                priority="high",
            ),
            SourceExpansionSuggestion(
                suggestion_id=f"{run_id}_arxiv",
                reason="arxiv",
                collector="arxiv",
                query_hint=topic,
                domain_tags=["research"],
                priority="medium",
            ),
            SourceExpansionSuggestion(
                suggestion_id=f"{run_id}_custom",
                reason="unsupported",
                collector="custom_feed",
                query_hint=topic,
                domain_tags=["research"],
                priority="low",
            ),
        ],
    )


def _seed_run(root: Path, run_id: str, topic: str, pack: str, coverage_score: float, gaps: list[str]) -> Path:
    run_dir = root / "artifacts" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    plan = build_research_plan(run_id, topic, pack)
    save_model(run_dir / "research_plan.json", plan)
    save_model(
        run_dir / "source_coverage_report.json",
        SourceCoverageReport(
            run_id=run_id,
            topic=topic,
            source_pack=pack,
            generated_at=utc_now(),
            coverage_score=coverage_score,
            gaps=gaps,
            weak_labels=["needs_source_expansion"] if gaps else [],
        ),
    )
    save_model(
        run_dir / "genericness_report.json",
        GenericnessReport(
            run_id=run_id,
            topic=topic,
            source_pack=pack,
            generated_at=utc_now(),
            verdict="somewhat_generic" if coverage_score < 0.5 else "specific",
            genericness_score=0.6 if coverage_score < 0.5 else 0.3,
        ),
    )
    suggestions = _expansion_suggestions(run_id, topic)
    save_model(run_dir / "source_expansion_suggestions.json", suggestions)
    expansion_plan = build_library_expansion_plan(run_id, topic, pack, suggestions)
    save_model(run_dir / "library_expansion_plan.json", expansion_plan)
    return run_dir


def test_expansion_plan_command_rendering():
    suggestions = _expansion_suggestions("run1", "quantum hybrid portfolio optimizer")
    plan = build_library_expansion_plan(
        "run1",
        "quantum hybrid portfolio optimizer",
        "quantum_finance_v1",
        suggestions,
    )
    assert any("collect-local" in q.example_command for q in plan.collector_queries)
    assert any("collect-arxiv" in q.example_command for q in plan.collector_queries)
    assert any(q.collector == "custom_feed" for q in plan.collector_queries)


def test_dry_run_execution_writes_report_without_running_collectors(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "quantum hybrid portfolio optimizer", "quantum_finance_v1", 0.35, ["thin evidence"])

    execution, improvement = write_library_expansion_execution(root, run_dir, mode="dry_run")

    assert (run_dir / "library_expansion_execution.json").exists()
    assert (run_dir / "library_expansion_execution.md").exists()
    assert execution.mode == "dry_run"
    assert improvement is None
    assert all(entry.status in ("planned", "manual") for entry in execution.executed_collectors + execution.manual_collectors)
    assert any(entry.collector == "custom_feed" and entry.status == "manual" for entry in execution.manual_collectors)


def test_execute_mode_invokes_mocked_collectors(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "quantum hybrid portfolio optimizer", "quantum_finance_v1", 0.35, ["thin evidence"])

    mock_report = LibraryBuildReport(
        generated_at=utc_now(),
        stage="collect-mock",
        status="ok",
        message="mocked",
        counts={"records": 1},
    )

    def mock_runner(project_root: Path, query: CollectorQueryPlan) -> LibraryBuildReport:
        return mock_report

    runners = {name: mock_runner for name in SUPPORTED_COLLECTORS}
    execution, improvement = write_library_expansion_execution(
        root,
        run_dir,
        mode="execute",
        runners=runners,
    )

    assert execution.mode == "execute"
    assert any(entry.status == "executed" for entry in execution.executed_collectors)
    assert improvement is not None
    assert (run_dir / "library_improvement_report.json").exists()


def test_unsupported_collectors_become_manual_actions(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "topic", "pack_v1", 0.2, ["gap"])
    execution, _ = build_library_expansion_execution(root, run_dir, mode="dry_run")
    manual_names = {entry.collector for entry in execution.manual_collectors}
    assert "custom_feed" in manual_names
    assert "local_docs" not in manual_names


def test_library_improvement_metrics_before_after():
    before = {
        "raw_sources": 2,
        "source_cards": 3,
        "chunks": 10,
        "quality": 0.4,
        "promotion_candidates": 1,
    }
    after = {
        "raw_sources": 5,
        "source_cards": 6,
        "chunks": 18,
        "quality": 0.55,
        "promotion_candidates": 2,
    }
    execution = LibraryExpansionExecution(
        run_id="run1",
        topic="topic",
        source_pack="pack",
        generated_at=utc_now(),
        mode="execute",
        executed_collectors=[],
        manual_collectors=[],
    )
    report = build_library_improvement_report("run1", "topic", "pack", before, after, execution)
    assert report.new_source_cards == 3
    assert report.new_chunks == 8
    assert report.quality_after > report.quality_before


def test_promotion_dry_run_selects_matching_cards(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "quantum hybrid portfolio optimizer", "quantum_finance_v1", 0.35, ["Missing quantum workflow"])
    from sourcelab.library.paths import ensure_library_layout
    from sourcelab.library.schemas import SourceCard
    ensure_library_layout(root)
    cards_dir = root / "data" / "library" / "silver" / "source_cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    card = SourceCard(
        source_id="quantum_paper",
        origin="arxiv",
        title="Quantum Hybrid Portfolio Optimizer",
        retrieved_at=utc_now(),
        domain_tags=["research"],
        topic_tags=["quantum", "portfolio"],
        summary="Hybrid quantum workflow for portfolio optimization.",
        key_terms=["quantum", "portfolio", "optimizer"],
        raw_path="raw/arxiv/x.json",
        checksum="abc",
        quality_score=0.72,
    )
    save_model(cards_dir / "quantum_paper.json", card)

    report = build_source_promotion_report(root, run_dir, force=False)
    assert report.mode == "dry_run"
    assert len(report.candidates) >= 1
    assert report.candidates[0].status == "proposed"


def test_promotion_force_requires_explicit_flag(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "quantum hybrid portfolio optimizer", "quantum_finance_v1", 0.35, ["Missing quantum workflow"])
    dry = write_source_promotion_report(root, run_dir, force=False)
    assert dry.mode == "dry_run"
    assert dry.promoted_count == 0

    pack_sources = root / "data" / "source_packs" / "quantum_finance_v1" / "sources"
    assert not pack_sources.exists() or len(list(pack_sources.glob("*.md"))) == 0


def test_gap_closure_verdict_improved(tmp_path: Path):
    root = tmp_path / "proj"
    topic = "quantum hybrid portfolio optimizer"
    pack = "quantum_finance_v1"
    baseline = _seed_run(root, "run1", topic, pack, 0.35, ["Missing hybrid workflow sources"])
    follow_up = _seed_run(root, "run2", topic, pack, 0.62, [])

    save_model(
        baseline / "retrieval_strategy.json",
        RetrievalStrategy(
            run_id="run1",
            topic=topic,
            source_pack=pack,
            generated_at=utc_now(),
            hits=[
                LabeledRetrievalHit(
                    chunk_id="c1",
                    source_id="pack_src",
                    title="Pack",
                    score=0.5,
                    trust_tier="A",
                    text_preview="x",
                    origin="source_pack",
                    query_id="q1",
                )
            ],
        ),
    )
    save_model(
        follow_up / "retrieval_strategy.json",
        RetrievalStrategy(
            run_id="run2",
            topic=topic,
            source_pack=pack,
            generated_at=utc_now(),
            hits=[
                LabeledRetrievalHit(
                    chunk_id="c1",
                    source_id="pack_src",
                    title="Pack",
                    score=0.5,
                    trust_tier="A",
                    text_preview="x",
                    origin="source_pack",
                    query_id="q1",
                ),
                LabeledRetrievalHit(
                    chunk_id="c2",
                    source_id="library_card",
                    library_card_id="card_new",
                    title="Library",
                    score=0.7,
                    trust_tier="B",
                    text_preview="y",
                    origin="library_silver",
                    query_id="q2",
                ),
            ],
        ),
    )

    plan = build_research_plan("run2", topic, pack)
    report = build_gap_closure_report(root, follow_up, plan)
    assert report.verdict == "improved"
    assert report.gaps_closed
    assert report.new_library_cards_used == ["card_new"]


def test_gap_closure_verdict_worse(tmp_path: Path):
    root = tmp_path / "proj"
    topic = "quantum hybrid portfolio optimizer"
    pack = "quantum_finance_v1"
    _seed_run(root, "run1", topic, pack, 0.55, [])
    follow_up = _seed_run(root, "run2", topic, pack, 0.30, ["New gap", "Another gap"])

    plan = build_research_plan("run2", topic, pack)
    report = build_gap_closure_report(root, follow_up, plan)
    assert report.verdict == "worse"


def test_gap_closure_verdict_unchanged(tmp_path: Path):
    root = tmp_path / "proj"
    topic = "quantum hybrid portfolio optimizer"
    pack = "quantum_finance_v1"
    _seed_run(root, "run1", topic, pack, 0.45, ["same gap"])
    follow_up = _seed_run(root, "run2", topic, pack, 0.46, ["same gap"])

    plan = build_research_plan("run2", topic, pack)
    report = build_gap_closure_report(root, follow_up, plan)
    assert report.verdict == "unchanged"


def test_gap_closure_report_written(tmp_path: Path):
    root = tmp_path / "proj"
    topic = "quantum hybrid portfolio optimizer"
    pack = "quantum_finance_v1"
    _seed_run(root, "run1", topic, pack, 0.35, ["gap"])
    follow_up = _seed_run(root, "run2", topic, pack, 0.60, [])
    plan = build_research_plan("run2", topic, pack)
    report = write_gap_closure_report(root, follow_up, plan)
    assert (follow_up / "gap_closure_report.json").exists()
    assert report.baseline_run_id == "run1"


def test_network_collectors_mocked_not_called_in_dry_run(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "topic", "pack_v1", 0.2, ["gap"])
    arxiv_mock = MagicMock()
    runners = {"arxiv": arxiv_mock}
    write_library_expansion_execution(root, run_dir, mode="dry_run", runners=runners)
    arxiv_mock.assert_not_called()
