"""Unit tests for immutable answer attempt history (Run Studio v1.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sourcelab.core.pipeline import run_answer_submit, run_lesson_create
from sourcelab.learning.answer_history import (
    compute_answer_diff,
    get_answer_attempt_detail,
    list_answer_attempts,
    summarize_answer_history_for_export,
    write_answer_attempt,
)
from sourcelab.learning.schemas import (
    AnswerReviewV2,
    AnswerSubmission,
    LearningReport,
    MasteryUpdate,
    SourceGroundingReview,
)


@pytest.fixture
def seeded_run(tmp_path):
    source_dir = tmp_path / "data" / "demo_sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_dir.joinpath("nist_pqc_notes.md").write_text(
        "Post-quantum migration begins with a cryptographic inventory.",
        encoding="utf-8",
    )
    return run_lesson_create(
        topic="post-quantum cryptography migration",
        project_root=tmp_path,
        difficulty=3,
        task_format="architecture_review",
    )


def _strong_answer() -> str:
    return (
        "A safe post-quantum migration starts with a full cryptographic inventory. "
        "Separate harvest-now-decrypt-later risk from operational risk. "
        "I am uncertain about the exact timeline for cryptographically relevant quantum computers."
    )


def _weak_answer() -> str:
    return "We should switch to quantum-safe encryption soon. It is more secure."


class TestAnswerAttemptArtifacts:
    def test_submit_writes_attempt_history(self, tmp_path, seeded_run):
        run_id = seeded_run["run_id"]
        result = run_answer_submit(
            topic=seeded_run["topic"],
            answer_text=_strong_answer(),
            project_root=tmp_path,
            run_id=run_id,
        )
        assert "attempt_id" in result
        assert "attempt_manifest_path" in result

        run_dir = Path(seeded_run["run_dir"])
        attempt_dir = run_dir / "answer_attempts" / result["attempt_id"]
        assert attempt_dir.exists()
        for name in (
            "answer_submission.json",
            "answer_review.json",
            "source_grounding_review.json",
            "mastery_update.json",
            "learning_report.json",
            "learning_report.md",
            "next_task_decision.json",
            "attempt_manifest.json",
        ):
            assert (attempt_dir / name).exists()

        # Latest snapshot files still at run root
        assert (run_dir / "answer_submission.json").exists()
        assert (run_dir / "answer_review.json").exists()

    def test_multiple_attempts_accumulate(self, tmp_path, seeded_run):
        run_id = seeded_run["run_id"]
        run_answer_submit(
            topic=seeded_run["topic"],
            answer_text=_strong_answer(),
            project_root=tmp_path,
            run_id=run_id,
        )
        run_answer_submit(
            topic=seeded_run["topic"],
            answer_text=_weak_answer(),
            project_root=tmp_path,
            run_id=run_id,
        )

        run_dir = Path(seeded_run["run_dir"])
        history = list_answer_attempts(run_dir, run_id)
        assert history.total == 2
        assert len(history.attempts) == 2

    def test_diff_between_attempts(self, tmp_path, seeded_run):
        run_id = seeded_run["run_id"]
        run_dir = Path(seeded_run["run_dir"])
        run_answer_submit(
            topic=seeded_run["topic"],
            answer_text=_weak_answer(),
            project_root=tmp_path,
            run_id=run_id,
        )
        run_answer_submit(
            topic=seeded_run["topic"],
            answer_text=_strong_answer(),
            project_root=tmp_path,
            run_id=run_id,
        )

        history = list_answer_attempts(run_dir, run_id)
        assert history.total == 2
        diff = compute_answer_diff(
            run_dir,
            run_id,
            history.attempts[0].attempt_id,
            history.attempts[1].attempt_id,
        )
        assert diff is not None
        assert diff.score_delta > 0

    def test_export_summary(self, tmp_path, seeded_run):
        run_id = seeded_run["run_id"]
        run_dir = Path(seeded_run["run_dir"])
        run_answer_submit(
            topic=seeded_run["topic"],
            answer_text=_strong_answer(),
            project_root=tmp_path,
            run_id=run_id,
        )
        stats = summarize_answer_history_for_export(run_dir)
        assert stats["total_attempts"] == 1
        assert stats["latest_score"] > 0

    def test_get_attempt_detail(self, tmp_path, seeded_run):
        run_id = seeded_run["run_id"]
        result = run_answer_submit(
            topic=seeded_run["topic"],
            answer_text=_strong_answer(),
            project_root=tmp_path,
            run_id=run_id,
        )
        run_dir = Path(seeded_run["run_dir"])
        detail = get_answer_attempt_detail(run_dir, run_id, result["attempt_id"])
        assert detail is not None
        assert detail.manifest.attempt_id == result["attempt_id"]
        assert detail.answer_review.get("overall_score") is not None
        assert detail.learning_report.get("overall_score") is not None
        assert "attempt_manifest.json" in detail.artifact_names
        assert "answer_review.json" in detail.artifact_names
        assert "learning_report.json" in detail.artifact_names

    def test_get_attempt_detail_missing_returns_none(self, tmp_path, seeded_run):
        run_id = seeded_run["run_id"]
        run_dir = Path(seeded_run["run_dir"])
        assert get_answer_attempt_detail(run_dir, run_id, "attempt_missing") is None

    def test_write_answer_attempt_manifest_fields(self, tmp_path):
        run_dir = tmp_path / "artifacts" / "runs" / "run_test"
        run_dir.mkdir(parents=True)
        (run_dir / "answer_submission.json").write_text("{}", encoding="utf-8")

        submission = AnswerSubmission(topic="t", run_id="run_test", answer_text="hello world")
        review = AnswerReviewV2(
            topic="t",
            run_id="run_test",
            overall_score=0.7,
            rubric_alignment_score=0.75,
            uncapped_score=0.8,
            cap_reason="test cap",
            needs_review=True,
            review_reason="human check",
        )
        grounding = SourceGroundingReview(topic="t", concept_overlap_grounding_score=0.6)
        mastery = MasteryUpdate(topic="t")
        report = LearningReport(topic="t", run_id="run_test", overall_score=0.7)

        attempt_id, attempt_dir = write_answer_attempt(
            run_dir=run_dir,
            run_id="run_test",
            user_id="local_user",
            submission=submission,
            review=review,
            source_grounding=grounding,
            mastery_update=mastery,
            learning_report=report,
            next_task={"focus": "grounding"},
            next_task_focus="grounding",
        )

        manifest = json.loads((attempt_dir / "attempt_manifest.json").read_text(encoding="utf-8"))
        assert manifest["attempt_id"] == attempt_id
        assert manifest["answer_preview"].startswith("hello world")
        assert manifest["cap_reason"] == "test cap"
        assert manifest["next_task_focus"] == "grounding"
