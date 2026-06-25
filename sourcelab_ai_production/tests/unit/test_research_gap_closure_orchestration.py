"""Tests for Research Gap Closure Loop v1.1 — guided orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from sourcelab.library.io import save_model, utc_now
from sourcelab.library.schemas import LibraryBuildReport, SourceExpansionSuggestion, SourceExpansionSuggestions
from sourcelab.research.expansion_execution import SUPPORTED_COLLECTORS, write_library_expansion_execution
from sourcelab.research.gap_closure import build_gap_closure_report
from sourcelab.research.gap_closure_orchestration import (
    build_followup_lesson_command,
    run_gap_closure_orchestration,
    write_gap_closure_orchestration,
)
from sourcelab.research.library_expansion_plan import build_library_expansion_plan
from sourcelab.research.planner import build_research_plan
from sourcelab.research.schemas import (
    CollectorQueryPlan,
    GenericnessReport,
    LabeledRetrievalHit,
    LibraryExpansionExecution,
    RetrievalStrategy,
    SourceCoverageReport,
)
from sourcelab.research.source_promotion import write_source_promotion_report


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


def test_guided_dry_run_writes_orchestration_report(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "quantum hybrid portfolio optimizer", "quantum_finance_v1", 0.35, ["thin evidence"])

    report = write_gap_closure_orchestration(root, run_dir, mode="dry_run")

    assert (run_dir / "gap_closure_orchestration.json").exists()
    assert (run_dir / "gap_closure_orchestration.md").exists()
    assert report.mode == "dry_run"
    assert report.followup_lesson_command == build_followup_lesson_command(
        "quantum hybrid portfolio optimizer",
        "quantum_finance_v1",
        2,
    )
    assert "library_expansion_execution.json" in report.reports_written
    assert report.promotion_status == "dry_run"
    assert report.manifest_repair_status == "skipped"


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
    report = run_gap_closure_orchestration(root, run_dir, mode="execute", runners=runners)

    assert report.mode == "execute"
    assert any("expansion run" in cmd for cmd in report.commands_executed)
    execution_path = run_dir / "library_expansion_execution.json"
    assert execution_path.exists()
    execution = LibraryExpansionExecution.model_validate_json(execution_path.read_text(encoding="utf-8"))
    assert any(entry.status == "executed" for entry in execution.executed_collectors)


def test_promote_force_requires_explicit_flag(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "quantum hybrid portfolio optimizer", "quantum_finance_v1", 0.35, ["gap"])

    dry = run_gap_closure_orchestration(root, run_dir, mode="dry_run", promote_force=False)
    assert dry.promotion_status == "dry_run"

    forced = run_gap_closure_orchestration(root, run_dir, mode="dry_run", promote_force=True)
    assert forced.promotion_status == "force"


def test_repair_manifests_only_runs_after_promote_force(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "topic", "pack_v1", 0.2, ["gap"])

    repair_mock = MagicMock(return_value=(["repaired manifest.json"], 0, "ok"))

    skipped = run_gap_closure_orchestration(
        root,
        run_dir,
        mode="dry_run",
        repair_manifests=True,
        promote_force=False,
        manifest_repair_runner=repair_mock,
    )
    assert skipped.manifest_repair_status == "skipped"
    repair_mock.assert_not_called()

    executed = run_gap_closure_orchestration(
        root,
        run_dir,
        mode="dry_run",
        repair_manifests=True,
        promote_force=True,
        manifest_repair_runner=repair_mock,
    )
    assert executed.manifest_repair_status == "executed"
    repair_mock.assert_called_once_with(root)


def test_followup_command_generation(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "quantum topic", "quantum_finance_v1", 0.3, ["gap"])

    report = run_gap_closure_orchestration(root, run_dir, mode="dry_run", difficulty=3)

    assert report.followup_lesson_command == (
        'sourcelab lesson create --topic "quantum topic" --source-pack quantum_finance_v1 --difficulty 3'
    )
    assert report.followup_run_id is None
    assert any("lesson create" in cmd for cmd in report.commands_planned)


def test_create_followup_executes_mocked_lesson_create(tmp_path: Path):
    root = tmp_path / "proj"
    topic = "quantum hybrid portfolio optimizer"
    pack = "quantum_finance_v1"
    run_dir = _seed_run(root, "run1", topic, pack, 0.35, ["gap"])
    _seed_run(root, "run0", topic, pack, 0.30, ["baseline gap"])

    def mock_runner(**kwargs: object) -> dict:
        follow_up = _seed_run(root, "run2", topic, pack, 0.62, [])
        save_model(
            follow_up / "retrieval_strategy.json",
            RetrievalStrategy(
                run_id="run2",
                topic=topic,
                source_pack=pack,
                generated_at=utc_now(),
                hits=[
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
                    )
                ],
            ),
        )
        return {"run_id": "run2"}

    mock_report = LibraryBuildReport(
        generated_at=utc_now(),
        stage="collect-mock",
        status="ok",
        message="mocked",
        counts={"records": 1},
    )
    runners = {name: (lambda _root, _query: mock_report) for name in SUPPORTED_COLLECTORS}

    report = run_gap_closure_orchestration(
        root,
        run_dir,
        mode="execute",
        create_followup=True,
        runners=runners,
        lesson_create_runner=mock_runner,
    )

    assert report.followup_run_id == "run2"
    assert report.gap_closure_verdict is not None
    assert (root / "artifacts" / "runs" / "run2" / "gap_closure_report.json").exists()


def test_baseline_run_id_stored_in_expansion_execution(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "topic", "pack_v1", 0.2, ["gap"])

    execution, _ = write_library_expansion_execution(root, run_dir, mode="dry_run")

    assert execution.baseline_run_id == "run1"
    assert execution.baseline_topic == "topic"
    assert execution.baseline_source_pack == "pack_v1"


def test_gap_closure_uses_persisted_baseline(tmp_path: Path):
    root = tmp_path / "proj"
    topic = "quantum hybrid portfolio optimizer"
    pack = "quantum_finance_v1"
    baseline = _seed_run(root, "run1", topic, pack, 0.35, ["Missing hybrid workflow sources"])
    follow_up = _seed_run(root, "run2", topic, pack, 0.62, [])
    _seed_run(root, "run0", topic, pack, 0.20, ["older gap"])

    write_library_expansion_execution(root, baseline, mode="dry_run")

    plan = build_research_plan("run2", topic, pack)
    report = build_gap_closure_report(root, follow_up, plan)
    assert report.baseline_run_id == "run1"


def test_promotion_force_in_orchestration_does_not_write_without_candidates(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "topic", "pack_v1", 0.2, ["gap"])

    report = run_gap_closure_orchestration(root, run_dir, mode="dry_run", promote_force=True)
    assert report.promotion_status == "force"
    promotion = write_source_promotion_report(root, run_dir, force=True)
    assert promotion.mode == "force"
