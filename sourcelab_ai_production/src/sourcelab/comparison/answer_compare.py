"""Artifact-driven answer attempt comparison across runs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sourcelab.comparison.schemas import (
    AnswerComparePerRun,
    AnswerCompareResult,
    AnswerCompareSummary,
)
from sourcelab.learning.answer_history import list_answer_attempts
from sourcelab.ui.run_loader import load_json_artifact


def _run_topic(run_dir: Path) -> str:
    manifest = load_json_artifact(run_dir, "run_manifest.json") or {}
    lesson_task = load_json_artifact(run_dir, "lesson_task.json") or {}
    return str(manifest.get("topic") or lesson_task.get("topic") or "")


def _summarize_run_answers(run_dir: Path) -> AnswerComparePerRun:
    run_id = run_dir.name
    topic = _run_topic(run_dir)
    history = list_answer_attempts(run_dir, run_id)
    attempts = history.attempts

    if not attempts:
        return AnswerComparePerRun(
            run_id=run_id,
            topic=topic,
            attempt_count=0,
        )

    latest = attempts[-1]
    best = max(attempts, key=lambda item: item.overall_score)
    needs_review_count = sum(1 for item in attempts if item.needs_review)
    capped_count = sum(1 for item in attempts if item.cap_reason)

    return AnswerComparePerRun(
        run_id=run_id,
        topic=topic,
        attempt_count=len(attempts),
        latest_attempt_id=latest.attempt_id,
        latest_score=latest.overall_score,
        best_attempt_id=best.attempt_id,
        best_score=best.overall_score,
        needs_review_count=needs_review_count,
        capped_count=capped_count,
        latest_cap_reason=latest.cap_reason,
        latest_next_task_focus=latest.next_task_focus,
        best_next_task_focus=best.next_task_focus,
    )


def _build_summary(per_run: list[AnswerComparePerRun]) -> AnswerCompareSummary:
    with_attempts = [row for row in per_run if row.attempt_count > 0]
    without_attempts = [row.run_id for row in per_run if row.attempt_count == 0]

    best_run_id = ""
    weakest_run_id = ""
    avg_latest: float | None = None
    avg_best: float | None = None

    if with_attempts:
        best_row = max(with_attempts, key=lambda row: row.best_score)
        weakest_row = min(with_attempts, key=lambda row: row.latest_score)
        best_run_id = best_row.run_id
        weakest_run_id = weakest_row.run_id
        avg_latest = round(
            sum(row.latest_score for row in with_attempts) / len(with_attempts),
            4,
        )
        avg_best = round(
            sum(row.best_score for row in with_attempts) / len(with_attempts),
            4,
        )

    review_heavy = sorted(
        row.run_id
        for row in with_attempts
        if row.needs_review_count > 0 or row.latest_cap_reason
    )

    return AnswerCompareSummary(
        total_runs=len(per_run),
        runs_with_attempts=len(with_attempts),
        runs_without_attempts=len(without_attempts),
        run_ids_without_attempts=without_attempts,
        best_run_by_best_score=best_run_id,
        weakest_by_latest=weakest_run_id,
        avg_latest_score=avg_latest,
        avg_best_score=avg_best,
        review_heavy_runs=review_heavy,
    )


WEAK_LATEST_THRESHOLD = 0.60
REGRESSION_DELTA_THRESHOLD = 0.15


def _is_weak_latest(row: AnswerComparePerRun) -> bool:
    return row.attempt_count > 0 and row.latest_score < WEAK_LATEST_THRESHOLD


def _is_regression(row: AnswerComparePerRun) -> bool:
    if row.attempt_count == 0:
        return False
    return (row.best_score - row.latest_score) >= REGRESSION_DELTA_THRESHOLD


def build_answer_recommendations(
    summary: AnswerCompareSummary,
    per_run: list[AnswerComparePerRun],
) -> list[str]:
    """Deterministic recommendation bullets for answer comparison views."""
    recommendations: list[str] = []

    if summary.runs_without_attempts:
        count = summary.runs_without_attempts
        recommendations.append(
            f"{count} run{'s' if count != 1 else ''} have no attempts — submit sample answers to compare scores."
        )

    if summary.runs_with_attempts == 0:
        return recommendations

    if summary.weakest_by_latest:
        weakest = next(row for row in per_run if row.run_id == summary.weakest_by_latest)
        if weakest.attempt_count:
            recommendations.append(
                f"Run {weakest.run_id} has the weakest latest score ({weakest.latest_score:.2%})."
            )

    if summary.review_heavy_runs:
        ids = ", ".join(summary.review_heavy_runs)
        recommendations.append(f"Review-heavy runs: {ids}.")

    if summary.best_run_by_best_score:
        best = next(row for row in per_run if row.run_id == summary.best_run_by_best_score)
        if best.attempt_count:
            recommendations.append(
                f"Best score from run {best.run_id} ({best.best_score:.2%})."
            )

    weak_runs = [row.run_id for row in per_run if _is_weak_latest(row)]
    if weak_runs:
        recommendations.append(
            f"Weak latest scores (<{WEAK_LATEST_THRESHOLD:.0%}): {', '.join(weak_runs)}."
        )

    regression_runs = [row.run_id for row in per_run if _is_regression(row)]
    if regression_runs:
        recommendations.append(
            f"Regression (best >> latest): {', '.join(regression_runs)}."
        )

    return recommendations


def _build_recommendation(summary: AnswerCompareSummary, per_run: list[AnswerComparePerRun]) -> str:
    bullets = build_answer_recommendations(summary, per_run)
    if not bullets:
        return "Inspect per-run attempt counts and review flags to prioritize learner follow-up."
    return " ".join(bullets)


def answer_compare_to_markdown(result: AnswerCompareResult) -> str:
    """Render answer comparison as markdown (table + recommendations)."""
    lines: list[str] = []
    summary = result.summary

    if summary.runs_with_attempts == 0:
        lines.append("No learner answer attempts found for compared runs.")
        if summary.runs_without_attempts:
            lines.append("")
            lines.append(
                f"- **Runs without attempts:** {summary.runs_without_attempts}/{summary.total_runs}"
            )
        bullets = build_answer_recommendations(summary, result.per_run)
        if bullets:
            lines.append("")
            lines.append("### Answer recommendation")
            lines.append("")
            for bullet in bullets:
                lines.append(f"- {bullet}")
        return "\n".join(lines)

    lines.append("## Learner Answer Comparison")
    lines.append("")
    lines.append(f"- **Runs with attempts:** {summary.runs_with_attempts}/{summary.total_runs}")
    if summary.runs_without_attempts:
        lines.append(
            f"- **Runs without attempts:** {summary.runs_without_attempts}/{summary.total_runs}"
        )
    if summary.avg_latest_score is not None:
        lines.append(f"- **Average latest score:** {summary.avg_latest_score:.2%}")
    if summary.avg_best_score is not None:
        lines.append(f"- **Average best score:** {summary.avg_best_score:.2%}")
    if summary.best_run_by_best_score:
        lines.append(f"- **Best run (peak score):** `{summary.best_run_by_best_score}`")
    if summary.weakest_by_latest:
        lines.append(f"- **Weakest latest:** `{summary.weakest_by_latest}`")
    if summary.review_heavy_runs:
        lines.append(
            f"- **Review-heavy runs:** {', '.join(f'`{rid}`' for rid in summary.review_heavy_runs)}"
        )

    weak_runs = [row.run_id for row in result.per_run if _is_weak_latest(row)]
    if weak_runs:
        lines.append(
            f"- **Weak latest (<{WEAK_LATEST_THRESHOLD:.0%}):** {', '.join(f'`{rid}`' for rid in weak_runs)}"
        )
    regression_runs = [row.run_id for row in result.per_run if _is_regression(row)]
    if regression_runs:
        lines.append(
            f"- **Regression (best >> latest):** {', '.join(f'`{rid}`' for rid in regression_runs)}"
        )
    lines.append("")

    lines.append("| Run ID | Attempts | Latest | Best | Review | Capped | Latest focus |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for row in result.per_run:
        latest = f"{row.latest_score:.2%}" if row.attempt_count else "—"
        best = f"{row.best_score:.2%}" if row.attempt_count else "—"
        focus = row.latest_next_task_focus or "—"
        if len(focus) > 48:
            focus = focus[:45] + "..."
        lines.append(
            f"| `{row.run_id}` | {row.attempt_count} | {latest} | {best} | "
            f"{row.needs_review_count} | {row.capped_count} | {focus} |"
        )
    lines.append("")

    bullets = build_answer_recommendations(summary, result.per_run)
    if bullets:
        lines.append("### Answer recommendation")
        lines.append("")
        for bullet in bullets:
            lines.append(f"- {bullet}")
        lines.append("")

    if result.recommendation:
        lines.append(result.recommendation)
        lines.append("")

    return "\n".join(lines)


def compare_run_answers(project_root: Path, run_ids: list[str]) -> AnswerCompareResult:
    """Compare answer attempts for two or more runs from on-disk artifacts."""
    runs_dir = project_root / "artifacts" / "runs"
    normalized_ids = [rid.strip() for rid in run_ids if rid.strip()]

    per_run: list[AnswerComparePerRun] = []
    for run_id in normalized_ids:
        run_dir = runs_dir / run_id
        if not run_dir.exists():
            raise FileNotFoundError(run_id)
        per_run.append(_summarize_run_answers(run_dir))

    summary = _build_summary(per_run)
    result = AnswerCompareResult(
        run_ids=normalized_ids,
        compared_at=datetime.now(timezone.utc).isoformat(),
        per_run=per_run,
        summary=summary,
    )
    result.recommendation = _build_recommendation(summary, per_run)
    return result


def compare_batch_answers(project_root: Path, batch_id: str) -> AnswerCompareResult:
    """Compare answer attempts for all runs in a batch."""
    from sourcelab.batch.service import get_batch

    batch = get_batch(project_root, batch_id)
    run_ids = batch.get("run_ids", [])
    if not run_ids:
        raise ValueError("Batch has no runs to compare")
    return compare_run_answers(project_root, run_ids)
