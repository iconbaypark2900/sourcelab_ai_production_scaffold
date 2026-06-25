"""Tests for Research Gap Closure Loop v1.2 — answer-submit bridge."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from sourcelab.library.io import save_model, utc_now
from sourcelab.library.schemas import SourceExpansionSuggestion, SourceExpansionSuggestions
from sourcelab.research.gap_closure_orchestration import (
    resolve_answer_input,
    run_gap_closure_orchestration,
    write_gap_closure_orchestration,
)
from sourcelab.research.library_expansion_plan import build_library_expansion_plan
from sourcelab.research.planner import build_research_plan
from sourcelab.research.schemas import (
    GenericnessReport,
    SourceCoverageReport,
    TopicProfileUpdate,
)
from sourcelab.research.topic_profile import load_topic_profile


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
        ],
    )


def _seed_run(root: Path, run_id: str, topic: str, pack: str) -> Path:
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
            coverage_score=0.35,
            gaps=["thin evidence"],
            weak_labels=["needs_source_expansion"],
        ),
    )
    save_model(
        run_dir / "genericness_report.json",
        GenericnessReport(
            run_id=run_id,
            topic=topic,
            source_pack=pack,
            generated_at=utc_now(),
            verdict="somewhat_generic",
            genericness_score=0.6,
        ),
    )
    suggestions = _expansion_suggestions(run_id, topic)
    save_model(run_dir / "source_expansion_suggestions.json", suggestions)
    expansion_plan = build_library_expansion_plan(run_id, topic, pack, suggestions)
    save_model(run_dir / "library_expansion_plan.json", expansion_plan)
    save_model(
        run_dir / "topic_profile_update.json",
        TopicProfileUpdate(
            run_id=run_id,
            topic=topic,
            topic_slug="quantum-hybrid-portfolio-optimizer",
            source_pack=pack,
            generated_at=utc_now(),
            coverage_score=0.35,
            weak_labels=["needs_source_expansion"],
            genericness_verdict="somewhat_generic",
            new_gaps=["thin evidence"],
            applied=False,
        ),
    )
    return run_dir


def test_answer_text_dry_run_does_not_submit(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "quantum hybrid portfolio optimizer", "quantum_finance_v1")
    submit_mock = MagicMock()

    report = run_gap_closure_orchestration(
        root,
        run_dir,
        mode="dry_run",
        answer_text="A strong answer defines objective, evidence, risks, and validation.",
        answer_submit_runner=submit_mock,
    )

    submit_mock.assert_not_called()
    assert report.answer_submit_status == "planned"
    assert report.answer_source == "text"
    assert not (run_dir / "answer_submission.json").exists()


def test_answer_text_execute_submits_and_updates_report(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "quantum hybrid portfolio optimizer", "quantum_finance_v1")

    def submit_mock(**kwargs: object) -> dict:
        (run_dir / "answer_submission.json").write_text("{}", encoding="utf-8")
        (run_dir / "answer_review.json").write_text(
            '{"topic": "quantum hybrid portfolio optimizer", "overall_score": 0.82, "needs_review": false}',
            encoding="utf-8",
        )
        update = TopicProfileUpdate.model_validate_json(
            (run_dir / "topic_profile_update.json").read_text(encoding="utf-8")
        )
        save_model(run_dir / "topic_profile_update.json", update.model_copy(update={"applied": True}))
        return {"run_id": "run1", "overall_score": 0.82}

    report = run_gap_closure_orchestration(
        root,
        run_dir,
        mode="execute",
        answer_text="A strong answer defines objective, evidence, risks, and validation.",
        answer_submit_runner=submit_mock,
        runners={},
    )

    assert report.answer_submit_status == "executed"
    assert report.answer_submission_run_id == "run1"
    assert report.answer_score == 0.82
    assert report.answer_review_required is False
    assert report.topic_profile_updated is True
    assert "answer_submission.json" in report.answer_artifacts_written


def test_answer_file_loads_content(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "topic", "pack_v1")
    answer_path = tmp_path / "answer.md"
    answer_path.write_text("Answer from file.", encoding="utf-8")

    text, source = resolve_answer_input(answer_file=answer_path)
    assert text == "Answer from file."
    assert source == "file"


def test_answer_text_and_file_fails():
    import pytest

    with pytest.raises(ValueError, match="only one"):
        resolve_answer_input(answer_text="text", answer_file=Path("/tmp/a.md"))


def test_skip_answer_submit_prevents_submission(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "topic", "pack_v1")
    submit_mock = MagicMock()

    report = run_gap_closure_orchestration(
        root,
        run_dir,
        mode="execute",
        answer_text="Should not submit",
        skip_answer_submit=True,
        answer_submit_runner=submit_mock,
    )

    submit_mock.assert_not_called()
    assert report.answer_submit_status == "skipped"
    assert any(step.step_id == "answer_submit" and step.status == "skipped" for step in report.steps)


def test_orchestration_report_stores_answer_fields(tmp_path: Path):
    root = tmp_path / "proj"
    run_dir = _seed_run(root, "run1", "topic", "pack_v1")

    report = write_gap_closure_orchestration(
        root,
        run_dir,
        mode="dry_run",
        answer_text="planned answer",
    )

    payload = (run_dir / "gap_closure_orchestration.json").read_text(encoding="utf-8")
    assert "answer_submit_status" in payload
    assert report.answer_source == "text"
    profile = load_topic_profile(root, "pack_v1", "topic")
    assert profile is not None
    assert "run1" in profile.orchestration_runs
