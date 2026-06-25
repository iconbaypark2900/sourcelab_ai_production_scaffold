"""Tests for Research Gap Closure Loop v1.2 — orchestration replay."""

from __future__ import annotations

from pathlib import Path

from sourcelab.library.io import save_model, utc_now
from sourcelab.library.schemas import SourceExpansionSuggestion, SourceExpansionSuggestions
from sourcelab.research.gap_closure import build_gap_closure_report
from sourcelab.research.gap_closure_orchestration import write_gap_closure_orchestration
from sourcelab.research.gap_closure_replay import (
    format_replay_markdown,
    replay_gap_closure_orchestration,
    suggest_next_safe_command,
)
from sourcelab.research.library_expansion_plan import build_library_expansion_plan
from sourcelab.research.planner import build_research_plan
from sourcelab.research.schemas import (
    GapClosureOrchestrationReport,
    GenericnessReport,
    SourceCoverageReport,
)
from sourcelab.research.topic_profile import load_topic_profile


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
    suggestions = SourceExpansionSuggestions(
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
        ],
    )
    save_model(run_dir / "source_expansion_suggestions.json", suggestions)
    expansion_plan = build_library_expansion_plan(run_id, topic, pack, suggestions)
    save_model(run_dir / "library_expansion_plan.json", expansion_plan)
    return run_dir


def test_replay_prints_completed_steps(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "quantum topic", "quantum_finance_v1", 0.35, ["gap"])
    write_gap_closure_orchestration(root, run_dir, mode="dry_run", answer_text="planned answer")

    summary = replay_gap_closure_orchestration(root, run_dir)
    markdown = format_replay_markdown(
        GapClosureOrchestrationReport.model_validate_json(
            (run_dir / "gap_closure_orchestration.json").read_text(encoding="utf-8")
        )
    )

    assert "read_weak_run" in summary["completed_steps"] or any(
        "Read current weak run" in markdown for _ in [0]
    )
    assert "Commands planned" in markdown
    assert summary["next_safe_command"]


def test_replay_suggests_next_safe_command(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "topic", "pack_v1", 0.2, ["gap"])
    report = write_gap_closure_orchestration(
        root,
        run_dir,
        mode="dry_run",
        answer_text="Bridge answer text",
    )

    next_cmd = suggest_next_safe_command(report)
    assert "gap-closure run" in next_cmd
    assert "--execute" in next_cmd


def test_followup_run_id_chain_honored(tmp_path: Path):
    root = tmp_path / "proj"
    topic = "quantum hybrid portfolio optimizer"
    pack = "quantum_finance_v1"
    baseline = _seed_run(root, "run1", topic, pack, 0.35, ["baseline gap"])
    hop1 = _seed_run(root, "run2", topic, pack, 0.45, ["remaining gap"])
    hop2 = _seed_run(root, "run3", topic, pack, 0.62, [])

    write_gap_closure_orchestration(
        root,
        baseline,
        mode="dry_run",
        create_followup=False,
    )
    orch1 = GapClosureOrchestrationReport.model_validate_json(
        (baseline / "gap_closure_orchestration.json").read_text(encoding="utf-8")
    )
    orch1 = orch1.model_copy(update={"followup_run_id": "run2"})
    save_model(baseline / "gap_closure_orchestration.json", orch1)

    write_gap_closure_orchestration(root, hop1, mode="dry_run")
    orch2 = GapClosureOrchestrationReport.model_validate_json(
        (hop1 / "gap_closure_orchestration.json").read_text(encoding="utf-8")
    )
    orch2 = orch2.model_copy(update={"followup_run_id": "run3"})
    save_model(hop1 / "gap_closure_orchestration.json", orch2)

    plan = build_research_plan("run3", topic, pack)
    report = build_gap_closure_report(root, hop2, plan)
    assert report.baseline_run_id == "run1"


def test_topic_profile_stores_orchestration_runs_and_chain(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "topic", "pack_v1", 0.2, ["gap"])
    report = write_gap_closure_orchestration(root, run_dir, mode="dry_run")
    updated = report.model_copy(update={"followup_run_id": "run2"})
    save_model(run_dir / "gap_closure_orchestration.json", updated)

    from sourcelab.research.topic_profile import record_orchestration_completion

    record_orchestration_completion(root, updated)
    profile = load_topic_profile(root, "pack_v1", "topic")
    assert profile is not None
    assert "run1" in profile.orchestration_runs
    assert "run2" in profile.followup_chain
