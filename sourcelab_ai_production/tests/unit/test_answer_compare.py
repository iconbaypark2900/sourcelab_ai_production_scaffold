"""Unit tests for answer comparison across runs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sourcelab.comparison.answer_compare import (
    answer_compare_to_markdown,
    build_answer_recommendations,
    compare_batch_answers,
    compare_run_answers,
)
from sourcelab.learning.answer_history import write_answer_attempt
from sourcelab.learning.schemas import (
    AnswerReviewV2,
    AnswerSubmission,
    LearningReport,
    MasteryUpdate,
    SourceGroundingReview,
)


def _write_attempt(
    run_dir: Path,
    *,
    attempt_id: str,
    score: float,
    needs_review: bool = False,
    cap_reason: str = "",
    focus: str = "focus",
) -> None:
    submission = AnswerSubmission(
        answer_id="a1",
        topic="t",
        answer_text="answer text",
        run_id=run_dir.name,
    )
    review = AnswerReviewV2(
        answer_id="a1",
        topic="t",
        overall_score=score,
        rubric_alignment_score=score,
        uncapped_score=score,
        needs_review=needs_review,
        cap_reason=cap_reason,
    )
    write_answer_attempt(
        run_dir,
        run_id=run_dir.name,
        user_id="local_user",
        submission=submission,
        review=review,
        source_grounding=SourceGroundingReview(answer_id="a1", topic="t"),
        mastery_update=MasteryUpdate(topic="t"),
        learning_report=LearningReport(topic="t", run_id=run_dir.name),
        next_task={},
        next_task_focus=focus,
        attempt_id=attempt_id,
    )


@pytest.fixture
def two_runs_with_manifest(tmp_path: Path):
    runs_dir = tmp_path / "artifacts" / "runs"
    run_a = runs_dir / "run_a"
    run_b = runs_dir / "run_b"
    for run_dir, topic in ((run_a, "topic alpha"), (run_b, "topic beta")):
        run_dir.mkdir(parents=True)
        (run_dir / "run_manifest.json").write_text(
            json.dumps({"run_id": run_dir.name, "topic": topic}),
            encoding="utf-8",
        )
    return tmp_path, run_a, run_b


def test_compare_run_answers_without_attempts(two_runs_with_manifest):
    project_root, _, _ = two_runs_with_manifest
    result = compare_run_answers(project_root, ["run_a", "run_b"])
    assert result.summary.runs_with_attempts == 0
    assert result.summary.total_runs == 2
    assert all(row.attempt_count == 0 for row in result.per_run)
    assert "2 runs have no attempts" in result.recommendation


def test_build_answer_recommendations_weak_and_review():
    from sourcelab.comparison.schemas import AnswerComparePerRun, AnswerCompareSummary

    per_run = [
        AnswerComparePerRun(
            run_id="run_a",
            attempt_count=2,
            latest_score=0.55,
            best_score=0.80,
            needs_review_count=1,
            capped_count=1,
            latest_cap_reason="cap",
        ),
        AnswerComparePerRun(run_id="run_b", attempt_count=0),
    ]
    summary = AnswerCompareSummary(
        total_runs=2,
        runs_with_attempts=1,
        runs_without_attempts=1,
        run_ids_without_attempts=["run_b"],
        best_run_by_best_score="run_a",
        weakest_by_latest="run_a",
        review_heavy_runs=["run_a"],
    )
    bullets = build_answer_recommendations(summary, per_run)
    assert any("no attempts" in b for b in bullets)
    assert any("weakest latest" in b for b in bullets)
    assert any("Review-heavy" in b for b in bullets)
    assert any("Best score" in b for b in bullets)
    assert any("Weak latest" in b for b in bullets)
    assert any("Regression" in b for b in bullets)


def test_answer_compare_to_markdown_with_and_without_attempts(two_runs_with_manifest):
    project_root, run_a, _ = two_runs_with_manifest
    empty = compare_run_answers(project_root, ["run_a", "run_b"])
    md_empty = answer_compare_to_markdown(empty)
    assert "No learner answer attempts" in md_empty
    assert "Runs without attempts" in md_empty

    _write_attempt(run_a, attempt_id="attempt_001", score=0.75)
    with_attempts = compare_run_answers(project_root, ["run_a", "run_b"])
    md = answer_compare_to_markdown(with_attempts)
    assert "## Learner Answer Comparison" in md
    assert "### Answer recommendation" in md
    assert "run_a" in md


def test_compare_run_answers_with_attempts(two_runs_with_manifest):
    project_root, run_a, run_b = two_runs_with_manifest
    _write_attempt(run_a, attempt_id="attempt_001", score=0.55, focus="improve citations")
    _write_attempt(run_a, attempt_id="attempt_002", score=0.72, cap_reason="rubric_cap")
    _write_attempt(run_b, attempt_id="attempt_001", score=0.40, needs_review=True)

    result = compare_run_answers(project_root, ["run_a", "run_b"])
    assert result.summary.runs_with_attempts == 2
    assert result.summary.best_run_by_best_score == "run_a"
    assert result.summary.weakest_by_latest == "run_b"

    by_id = {row.run_id: row for row in result.per_run}
    assert by_id["run_a"].attempt_count == 2
    assert by_id["run_a"].best_score == 0.72
    assert by_id["run_a"].latest_score == 0.72
    assert by_id["run_a"].capped_count == 1
    assert by_id["run_b"].needs_review_count == 1


def test_compare_run_answers_missing_run(two_runs_with_manifest):
    project_root, _, _ = two_runs_with_manifest
    with pytest.raises(FileNotFoundError):
        compare_run_answers(project_root, ["run_a", "missing"])


def test_compare_batch_answers(tmp_path: Path, two_runs_with_manifest):
    project_root, run_a, run_b = two_runs_with_manifest
    batch_id = "batch_test"
    batch_dir = project_root / "artifacts" / "batches" / batch_id
    batch_dir.mkdir(parents=True)
    (batch_dir / "batch_manifest.json").write_text(
        json.dumps(
            {
                "batch_id": batch_id,
                "batch_name": "test",
                "run_ids": ["run_a", "run_b"],
                "runs": [],
                "failures": [],
            }
        ),
        encoding="utf-8",
    )
    _write_attempt(run_a, attempt_id="attempt_001", score=0.6)

    result = compare_batch_answers(project_root, batch_id)
    assert result.summary.runs_with_attempts == 1
    assert result.per_run[0].run_id == "run_a"


def test_compare_batch_answers_missing_batch(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        compare_batch_answers(tmp_path, "missing")
