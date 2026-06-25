"""Immutable answer attempt history for Run Studio v1.2.

Each answer submission writes a snapshot under
``artifacts/runs/<run_id>/answer_attempts/attempt_<id>/`` while preserving
the latest mutable artifacts at the run root for backward compatibility.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sourcelab.learning.schemas import (
    AnswerAttemptDetail,
    AnswerAttemptManifest,
    AnswerAttemptSummary,
    AnswerDiffResponse,
    AnswerHistoryResponse,
    AnswerReviewV2,
    AnswerSubmission,
    LearningReport,
    MasteryUpdate,
    SourceGroundingReview,
)

ATTEMPT_ARTIFACTS = (
    "answer_submission.json",
    "answer_review.json",
    "source_grounding_review.json",
    "mastery_update.json",
    "learning_report.json",
    "learning_report.md",
    "next_task_decision.json",
)

ATTEMPT_DETAIL_ARTIFACTS = ("attempt_manifest.json",) + ATTEMPT_ARTIFACTS


def generate_attempt_id() -> str:
    """Return a deterministic, sortable attempt id based on UTC timestamp."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"attempt_{ts}"


def answer_attempts_dir(run_dir: Path) -> Path:
    """Directory holding immutable attempt snapshots for a run."""
    return run_dir / "answer_attempts"


def _answer_preview(answer_text: str, max_len: int = 120) -> str:
    preview = " ".join(answer_text.split())
    if len(preview) <= max_len:
        return preview
    return preview[: max_len - 3] + "..."


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_answer_attempt(
    run_dir: Path,
    *,
    run_id: str,
    user_id: str,
    submission: AnswerSubmission,
    review: AnswerReviewV2,
    source_grounding: SourceGroundingReview,
    mastery_update: MasteryUpdate,
    learning_report: LearningReport,
    next_task: dict,
    next_task_focus: str,
    attempt_id: str | None = None,
) -> tuple[str, Path]:
    """Write an immutable attempt snapshot and return (attempt_id, attempt_dir)."""
    attempt_id = attempt_id or generate_attempt_id()
    attempt_dir = answer_attempts_dir(run_dir) / attempt_id
    attempt_dir.mkdir(parents=True, exist_ok=True)

    for name in ATTEMPT_ARTIFACTS:
        src = run_dir / name
        if src.exists():
            shutil.copy2(src, attempt_dir / name)

    manifest = AnswerAttemptManifest(
        attempt_id=attempt_id,
        run_id=run_id,
        created_at=review.created_at or datetime.now(timezone.utc).isoformat(),
        user_id=user_id,
        answer_preview=_answer_preview(submission.answer_text),
        overall_score=review.overall_score,
        rubric_alignment_score=review.rubric_alignment_score,
        uncapped_score=review.uncapped_score,
        needs_review=review.needs_review,
        cap_reason=review.cap_reason,
        human_review_reason=review.review_reason if review.needs_review else "",
        next_task_focus=next_task_focus,
    )
    manifest_path = attempt_dir / "attempt_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )
    return attempt_id, attempt_dir


def _load_manifest(attempt_dir: Path) -> AnswerAttemptManifest | None:
    manifest_path = attempt_dir / "attempt_manifest.json"
    if not manifest_path.exists():
        return None
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return AnswerAttemptManifest(**data)


def list_attempt_dirs(run_dir: Path) -> list[Path]:
    """Return attempt directories sorted chronologically by attempt id."""
    base = answer_attempts_dir(run_dir)
    if not base.exists():
        return []
    dirs = [p for p in base.iterdir() if p.is_dir() and p.name.startswith("attempt_")]
    return sorted(dirs, key=lambda p: p.name)


def list_answer_attempts(run_dir: Path, run_id: str) -> AnswerHistoryResponse:
    """List all answer attempts for a run (empty list when none exist)."""
    summaries: list[AnswerAttemptSummary] = []
    for attempt_dir in list_attempt_dirs(run_dir):
        manifest = _load_manifest(attempt_dir)
        if manifest is None:
            continue
        summaries.append(
            AnswerAttemptSummary(
                attempt_id=manifest.attempt_id,
                created_at=manifest.created_at,
                overall_score=manifest.overall_score,
                uncapped_score=manifest.uncapped_score,
                rubric_alignment_score=manifest.rubric_alignment_score,
                needs_review=manifest.needs_review,
                cap_reason=manifest.cap_reason,
                next_task_focus=manifest.next_task_focus,
            )
        )
    return AnswerHistoryResponse(run_id=run_id, attempts=summaries, total=len(summaries))


def resolve_attempt_dir(run_dir: Path, attempt_id: str) -> Path | None:
    """Locate an attempt directory by id."""
    attempt_dir = answer_attempts_dir(run_dir) / attempt_id
    if attempt_dir.exists() and attempt_dir.is_dir():
        return attempt_dir
    return None


def get_answer_attempt_detail(run_dir: Path, run_id: str, attempt_id: str) -> AnswerAttemptDetail | None:
    """Load full attempt detail including artifact payloads."""
    attempt_dir = resolve_attempt_dir(run_dir, attempt_id)
    if attempt_dir is None:
        return None

    manifest = _load_manifest(attempt_dir)
    if manifest is None:
        return None

    learning_report_md = ""
    md_path = attempt_dir / "learning_report.md"
    if md_path.exists():
        learning_report_md = md_path.read_text(encoding="utf-8")

    artifact_names = [
        name for name in ATTEMPT_DETAIL_ARTIFACTS if (attempt_dir / name).exists()
    ]

    return AnswerAttemptDetail(
        run_id=run_id,
        attempt_id=attempt_id,
        manifest=manifest,
        answer_submission=_load_json(attempt_dir / "answer_submission.json"),
        answer_review=_load_json(attempt_dir / "answer_review.json"),
        source_grounding_review=_load_json(attempt_dir / "source_grounding_review.json"),
        mastery_update=_load_json(attempt_dir / "mastery_update.json"),
        learning_report=_load_json(attempt_dir / "learning_report.json"),
        learning_report_md=learning_report_md,
        next_task_decision=_load_json(attempt_dir / "next_task_decision.json"),
        artifact_names=artifact_names,
    )


def _grounding_score_from_review(review_data: dict) -> float:
    return float(review_data.get("source_grounding_score", 0.0))


def compute_answer_diff(
    run_dir: Path,
    run_id: str,
    from_attempt_id: str,
    to_attempt_id: str,
) -> AnswerDiffResponse | None:
    """Compute score and content deltas between two attempts."""
    from_dir = resolve_attempt_dir(run_dir, from_attempt_id)
    to_dir = resolve_attempt_dir(run_dir, to_attempt_id)
    if from_dir is None or to_dir is None:
        return None

    from_manifest = _load_manifest(from_dir)
    to_manifest = _load_manifest(to_dir)
    if from_manifest is None or to_manifest is None:
        return None

    from_review = _load_json(from_dir / "answer_review.json")
    to_review = _load_json(to_dir / "answer_review.json")

    from_strengths = set(from_review.get("strengths") or [])
    to_strengths = set(to_review.get("strengths") or [])
    from_weaknesses = set(from_review.get("weaknesses") or [])
    to_weaknesses = set(to_review.get("weaknesses") or [])

    from_focus = from_manifest.next_task_focus
    to_focus = to_manifest.next_task_focus

    return AnswerDiffResponse(
        run_id=run_id,
        from_attempt_id=from_attempt_id,
        to_attempt_id=to_attempt_id,
        score_delta=to_manifest.overall_score - from_manifest.overall_score,
        rubric_alignment_delta=to_manifest.rubric_alignment_score - from_manifest.rubric_alignment_score,
        uncapped_delta=to_manifest.uncapped_score - from_manifest.uncapped_score,
        grounding_delta=_grounding_score_from_review(to_review) - _grounding_score_from_review(from_review),
        needs_review_changed=from_manifest.needs_review != to_manifest.needs_review,
        cap_reason_changed=from_manifest.cap_reason != to_manifest.cap_reason,
        strengths_added=sorted(to_strengths - from_strengths),
        strengths_removed=sorted(from_strengths - to_strengths),
        weaknesses_added=sorted(to_weaknesses - from_weaknesses),
        weaknesses_removed=sorted(from_weaknesses - to_weaknesses),
        next_task_changed=from_focus != to_focus,
        from_next_task_focus=from_focus,
        to_next_task_focus=to_focus,
        from_overall_score=from_manifest.overall_score,
        to_overall_score=to_manifest.overall_score,
        from_needs_review=from_manifest.needs_review,
        to_needs_review=to_manifest.needs_review,
        from_cap_reason=from_manifest.cap_reason,
        to_cap_reason=to_manifest.cap_reason,
    )


def summarize_answer_history_for_export(run_dir: Path) -> dict:
    """Aggregate attempt history stats for markdown export."""
    attempts = list_answer_attempts(run_dir, run_dir.name).attempts
    if not attempts:
        return {"total_attempts": 0}

    scores = [a.overall_score for a in attempts]
    needs_review_count = sum(1 for a in attempts if a.needs_review)
    latest = attempts[-1]
    best = max(attempts, key=lambda a: a.overall_score)

    trend = "stable"
    if len(scores) >= 2:
        delta = scores[-1] - scores[0]
        if delta > 0.01:
            trend = "improving"
        elif delta < -0.01:
            trend = "declining"

    return {
        "total_attempts": len(attempts),
        "latest_score": latest.overall_score,
        "best_score": best.overall_score,
        "best_attempt_id": best.attempt_id,
        "needs_review_count": needs_review_count,
        "latest_cap_reason": latest.cap_reason,
        "score_trend": trend,
        "scores": scores,
    }
