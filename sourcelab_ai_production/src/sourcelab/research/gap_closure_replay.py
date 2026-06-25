"""Replay and continue guided gap-closure orchestration from persisted artifacts."""

from __future__ import annotations

from pathlib import Path

from sourcelab.library.io import load_model
from sourcelab.research.expansion_execution import write_library_expansion_execution
from sourcelab.research.gap_closure import write_gap_closure_report
from sourcelab.research.schemas import GapClosureOrchestrationReport, GapClosureOrchestrationStep, ResearchPlan
from sourcelab.research.source_promotion import write_source_promotion_report


DESTRUCTIVE_STEP_IDS = frozenset(
    {
        "answer_submit",
        "expansion_execution",
        "promotion",
        "manifest_repair",
        "followup_lesson",
    }
)


def load_gap_closure_orchestration(run_dir: Path) -> GapClosureOrchestrationReport:
    """Load gap_closure_orchestration.json from a run directory."""
    path = run_dir / "gap_closure_orchestration.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing gap_closure_orchestration.json in {run_dir}")
    return load_model(path, GapClosureOrchestrationReport)


def _step_map(report: GapClosureOrchestrationReport) -> dict[str, GapClosureOrchestrationStep]:
    return {step.step_id: step for step in report.steps}


def _completed_step_ids(report: GapClosureOrchestrationReport) -> list[str]:
    return [step.step_id for step in report.steps if step.status == "executed"]


def _remaining_step_ids(report: GapClosureOrchestrationReport) -> list[str]:
    return [
        step.step_id
        for step in report.steps
        if step.status in {"planned", "skipped"}
        and step.step_id not in {"read_weak_run", "followup_command"}
    ]


def suggest_next_safe_command(report: GapClosureOrchestrationReport) -> str:
    """Suggest the next non-destructive CLI command from orchestration state."""
    steps = _step_map(report)
    run_id = report.run_id

    answer_step = steps.get("answer_submit")
    if answer_step and answer_step.status in {"planned", "skipped"} and report.answer_source:
        flag = "--answer-file" if report.answer_source == "file" else "--answer-text"
        sample = '"<answer text>"' if report.answer_source == "text" else "path/to/answer.md"
        return f"sourcelab research gap-closure run --run {run_id} --execute {flag} {sample}"

    expansion_step = steps.get("expansion_execution")
    if expansion_step and expansion_step.status in {"planned", "skipped"}:
        return f"sourcelab research expansion run --run {run_id} --dry-run"

    promotion_step = steps.get("promotion")
    if promotion_step and promotion_step.status in {"planned", "skipped"}:
        return f"sourcelab research expansion promote --run {run_id} --dry-run"

    compare_step = steps.get("gap_closure_compare")
    if compare_step and compare_step.status in {"planned", "skipped"}:
        target = report.followup_run_id or "latest"
        return f"sourcelab research gap-closure --run {target}"

    followup_step = steps.get("followup_lesson")
    if followup_step and followup_step.status in {"planned", "skipped"} and report.followup_lesson_command:
        return report.followup_lesson_command

    if report.commands_planned:
        for command in report.commands_planned:
            if not command.startswith("#"):
                return command

    return f"sourcelab research gap-closure replay --run {run_id}"


def build_replay_summary(report: GapClosureOrchestrationReport) -> dict[str, object]:
    """Build structured replay summary for CLI/API output."""
    completed = _completed_step_ids(report)
    remaining = _remaining_step_ids(report)
    return {
        "run_id": report.run_id,
        "topic": report.topic,
        "source_pack": report.source_pack,
        "mode": report.mode,
        "completed_steps": completed,
        "remaining_steps": remaining,
        "commands_planned": report.commands_planned,
        "commands_executed": report.commands_executed,
        "next_safe_command": suggest_next_safe_command(report),
        "answer_submit_status": report.answer_submit_status,
        "topic_profile_updated": report.topic_profile_updated,
        "followup_run_id": report.followup_run_id,
        "gap_closure_verdict": report.gap_closure_verdict,
    }


def format_replay_markdown(report: GapClosureOrchestrationReport) -> str:
    """Render human-readable replay output."""
    summary = build_replay_summary(report)
    lines = [
        f"# Gap Closure Orchestration Replay — {report.topic}",
        "",
        f"- **Run:** `{report.run_id}`",
        f"- **Mode:** `{report.mode}`",
        f"- **Answer submit:** `{report.answer_submit_status}`",
        f"- **Topic profile updated:** `{report.topic_profile_updated}`",
        "",
        "## Completed steps",
        "",
    ]
    for step_id in summary["completed_steps"]:
        step = _step_map(report).get(str(step_id))
        name = step.name if step else step_id
        lines.append(f"- {name} (`{step_id}`)")

    lines.extend(["", "## Remaining steps", ""])
    remaining = summary["remaining_steps"]
    if remaining:
        for step_id in remaining:
            step = _step_map(report).get(str(step_id))
            name = step.name if step else step_id
            status = step.status if step else "planned"
            lines.append(f"- {name} (`{step_id}`, `{status}`)")
    else:
        lines.append("- _(none)_")

    lines.extend(["", "## Commands planned", ""])
    for command in report.commands_planned:
        lines.append(f"- `{command}`")

    if report.commands_executed:
        lines.extend(["", "## Commands executed", ""])
        for command in report.commands_executed:
            lines.append(f"- `{command}`")

    lines.extend(
        [
            "",
            "## Next safe command",
            "",
            f"`{summary['next_safe_command']}`",
            "",
        ]
    )
    return "\n".join(lines)


def replay_gap_closure_orchestration(
    project_root: Path,
    run_dir: Path,
    *,
    continue_run: bool = False,
) -> dict[str, object]:
    """Print replay summary; optionally continue missing non-destructive steps."""
    report = load_gap_closure_orchestration(run_dir)
    summary = build_replay_summary(report)
    continued: list[str] = []

    if continue_run:
        steps = _step_map(report)
        run_id = report.run_id
        plan_path = run_dir / "research_plan.json"
        if plan_path.exists():
            compare_step = steps.get("gap_closure_compare")
            if compare_step and compare_step.status in {"planned", "skipped"}:
                target_id = report.followup_run_id
                if target_id:
                    target_dir = project_root / "artifacts" / "runs" / target_id
                    target_plan_path = target_dir / "research_plan.json"
                    if target_plan_path.exists():
                        target_plan = load_model(target_plan_path, ResearchPlan)
                        write_gap_closure_report(project_root, target_dir, target_plan)
                        continued.append(f"sourcelab research gap-closure --run {target_id}")

            expansion_step = steps.get("expansion_execution")
            if expansion_step and expansion_step.status in {"planned", "skipped"}:
                write_library_expansion_execution(project_root, run_dir, mode="dry_run")
                continued.append(f"sourcelab research expansion run --run {run_id} --dry-run")

            promotion_step = steps.get("promotion")
            if promotion_step and promotion_step.status in {"planned", "skipped"}:
                write_source_promotion_report(project_root, run_dir, force=False)
                continued.append(f"sourcelab research expansion promote --run {run_id} --dry-run")

        destructive_remaining = [
            step_id
            for step_id in _remaining_step_ids(report)
            if step_id in DESTRUCTIVE_STEP_IDS
        ]
        if destructive_remaining:
            summary["destructive_remaining"] = destructive_remaining
            summary["destructive_note"] = (
                "Destructive steps require explicit flags on gap-closure run "
                "(--execute, --promote-force, --repair-manifests, --create-followup, --answer-text)."
            )

        summary["continued_commands"] = continued

    summary["replay_markdown"] = format_replay_markdown(report)
    return summary
