"""Tests for batch comparison markdown answer section."""

from __future__ import annotations

import json
from pathlib import Path

from sourcelab.batch.service import compare_batch_runs
from sourcelab.learning.answer_history import write_answer_attempt
from sourcelab.learning.schemas import (
    AnswerReviewV2,
    AnswerSubmission,
    LearningReport,
    MasteryUpdate,
    SourceGroundingReview,
)


def _seed_batch_with_runs(tmp_path: Path) -> tuple[str, Path, Path]:
    runs_dir = tmp_path / "artifacts" / "runs"
    run_a = runs_dir / "20260101T000000Z"
    run_b = runs_dir / "20260101T000001Z"
    for run_dir, topic in ((run_a, "alpha"), (run_b, "beta")):
        run_dir.mkdir(parents=True)
        for name, payload in (
            ("run_manifest.json", {"run_id": run_dir.name, "topic": topic}),
            ("retrieved_chunks.json", []),
            ("atomic_claims.json", []),
            ("citation_resolution.json", {"total_claims": 0, "supported_claims": 0}),
            ("proof_summary.json", {"release_gate_status": "PASS"}),
        ):
            (run_dir / name).write_text(json.dumps(payload), encoding="utf-8")
        (run_dir / "generated_lesson.md").write_text("# Lesson\n", encoding="utf-8")

    batch_id = "batch_md_test"
    batch_dir = tmp_path / "artifacts" / "batches" / batch_id
    batch_dir.mkdir(parents=True)
    (batch_dir / "batch_manifest.json").write_text(
        json.dumps(
            {
                "batch_id": batch_id,
                "batch_name": "md test",
                "created_at": "2026-01-01T00:00:00Z",
                "run_ids": [run_a.name, run_b.name],
                "runs": [],
                "failures": [],
            }
        ),
        encoding="utf-8",
    )
    return batch_id, run_a, run_b


def test_comparison_markdown_without_answers(tmp_path: Path):
    batch_id, _, _ = _seed_batch_with_runs(tmp_path)
    compare_batch_runs(tmp_path, batch_id)
    md = (tmp_path / "artifacts" / "batches" / batch_id / "comparison_report.md").read_text()
    assert "No learner answer attempts found" in md


def test_comparison_markdown_with_answers(tmp_path: Path):
    batch_id, run_a, _ = _seed_batch_with_runs(tmp_path)
    write_answer_attempt(
        run_a,
        run_id=run_a.name,
        user_id="local_user",
        submission=AnswerSubmission(answer_id="a", topic="alpha", answer_text="text", run_id=run_a.name),
        review=AnswerReviewV2(answer_id="a", topic="alpha", overall_score=0.8),
        source_grounding=SourceGroundingReview(answer_id="a", topic="alpha"),
        mastery_update=MasteryUpdate(topic="alpha"),
        learning_report=LearningReport(topic="alpha", run_id=run_a.name),
        next_task={},
        next_task_focus="next",
        attempt_id="attempt_001",
    )
    compare_batch_runs(tmp_path, batch_id)
    md = (tmp_path / "artifacts" / "batches" / batch_id / "comparison_report.md").read_text()
    assert "## Learner Answer Comparison" in md
    assert run_a.name in md
