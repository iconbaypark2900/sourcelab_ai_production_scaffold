"""Guided orchestration for the research gap-closure loop."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from sourcelab.core.pipeline import run_answer_submit, run_lesson_create
from sourcelab.library.io import load_model, utc_now
from sourcelab.research.expansion_execution import (
    CollectorRunner,
    write_library_expansion_execution,
)
from sourcelab.research.gap_closure import write_gap_closure_report
from sourcelab.research.library_expansion_plan import (
    build_library_expansion_plan,
    maybe_write_library_expansion_plan,
)
from sourcelab.research.manifest_repair import run_manifest_repair
from sourcelab.library.schemas import SourceExpansionSuggestions
from sourcelab.learning.schemas import AnswerReviewV2
from sourcelab.research.schemas import (
    GapClosureOrchestrationMode,
    GapClosureOrchestrationReport,
    GapClosureOrchestrationStep,
    GapClosureVerdict,
    LibraryExpansionPlan,
    ResearchPlan,
    SourceCoverageReport,
    TopicProfileUpdate,
)
from sourcelab.research.topic_profile import record_orchestration_completion
from sourcelab.research.source_promotion import write_source_promotion_report


LessonCreateRunner = Callable[..., dict[str, Any]]
AnswerSubmitRunner = Callable[..., dict[str, Any]]

ANSWER_ARTIFACT_NAMES = [
    "answer_submission.json",
    "answer_review.json",
    "source_grounding_review.json",
    "mastery_update.json",
    "skill_profile_snapshot.json",
    "learning_report.json",
    "learning_report.md",
    "next_task_decision.json",
]


def build_followup_lesson_command(topic: str, source_pack: str, difficulty: int) -> str:
    """CLI command for a follow-up lesson after expansion/promotion."""
    return (
        f'sourcelab lesson create --topic "{topic}" '
        f"--source-pack {source_pack} --difficulty {difficulty}"
    )


def resolve_answer_input(
    answer_text: str | None = None,
    answer_file: Path | None = None,
) -> tuple[str | None, str | None]:
    """Return (answer text, source) where source is ``text``, ``file``, or None."""
    if answer_text and answer_file:
        raise ValueError("Provide only one of answer_text or answer_file")
    if answer_file:
        if not answer_file.exists():
            raise FileNotFoundError(f"Answer file not found: {answer_file}")
        return answer_file.read_text(encoding="utf-8"), "file"
    if answer_text:
        return answer_text, "text"
    return None, None


def build_answer_submit_command(
    run_id: str,
    *,
    execute: bool = False,
    answer_text: str | None = None,
    answer_file: Path | None = None,
    skip_answer_submit: bool = False,
) -> str | None:
    """Build CLI fragment for answer-submit bridge flags."""
    if skip_answer_submit or (not answer_text and not answer_file):
        return None
    mode_flag = "--execute" if execute else "--dry-run"
    if answer_file:
        return (
            f"sourcelab research gap-closure run --run {run_id} {mode_flag} "
            f"--answer-file {answer_file}"
        )
    escaped = answer_text.replace('"', '\\"') if answer_text else ""
    return (
        f'sourcelab research gap-closure run --run {run_id} {mode_flag} '
        f'--answer-text "{escaped}"'
    )


def build_orchestration_workflow_commands(
    run_id: str,
    topic: str,
    source_pack: str,
    *,
    execute: bool = False,
    promote_force: bool = False,
    repair_manifests: bool = False,
    create_followup: bool = False,
    difficulty: int = 2,
    answer_text: str | None = None,
    answer_file: Path | None = None,
    skip_answer_submit: bool = False,
) -> list[str]:
    """Build the full guided gap-closure CLI workflow."""
    expansion_mode = "execute" if execute else "dry-run"
    promote_mode = "force" if promote_force else "dry-run"
    orchestration_cmd = f"sourcelab research gap-closure run --run {run_id} --{'execute' if execute else 'dry-run'}"
    if not skip_answer_submit:
        if answer_file:
            orchestration_cmd += f" --answer-file {answer_file}"
        elif answer_text:
            escaped = answer_text.replace('"', '\\"')
            orchestration_cmd += f' --answer-text "{escaped}"'
    elif skip_answer_submit and (answer_text or answer_file):
        orchestration_cmd += " --skip-answer-submit"
    commands = [
        orchestration_cmd,
        f"sourcelab research expansion run --run {run_id} --{expansion_mode}",
        f"sourcelab research expansion promote --run {run_id} --{promote_mode}",
    ]
    if repair_manifests and promote_force:
        commands.append("python scripts/bootstrap_sourcelab_source_packs.py --repair-manifests")
    followup = build_followup_lesson_command(topic, source_pack, difficulty)
    if create_followup:
        commands.append(followup)
        commands.append(f"sourcelab research gap-closure --run latest")
    else:
        commands.append(f"# After follow-up lesson: {followup}")
        commands.append("# Then compare: sourcelab research gap-closure --run latest")
    commands.append(f"sourcelab research gap-closure replay --run {run_id}")
    return commands


def _step(
    step_id: str,
    name: str,
    status: str,
    message: str = "",
) -> GapClosureOrchestrationStep:
    return GapClosureOrchestrationStep(
        step_id=step_id,
        name=name,
        status=status,  # type: ignore[arg-type]
        message=message,
    )


def _load_weak_run_context(run_dir: Path) -> tuple[ResearchPlan, SourceCoverageReport | None]:
    plan_path = run_dir / "research_plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"Missing research_plan.json in {run_dir}")
    plan = load_model(plan_path, ResearchPlan)
    coverage_path = run_dir / "source_coverage_report.json"
    coverage = load_model(coverage_path, SourceCoverageReport) if coverage_path.exists() else None
    return plan, coverage


def _ensure_expansion_plan(project_root: Path, run_dir: Path, plan: ResearchPlan) -> LibraryExpansionPlan:
    plan_path = run_dir / "library_expansion_plan.json"
    if plan_path.exists():
        return load_model(plan_path, LibraryExpansionPlan)

    suggestions: SourceExpansionSuggestions | None = None
    suggestions_path = run_dir / "source_expansion_suggestions.json"
    if suggestions_path.exists():
        suggestions = load_model(suggestions_path, SourceExpansionSuggestions)

    maybe_write_library_expansion_plan(run_dir, plan)
    if plan_path.exists():
        return load_model(plan_path, LibraryExpansionPlan)
    return build_library_expansion_plan(run_dir.name, plan.topic, plan.source_pack, suggestions)


def render_gap_closure_orchestration_markdown(report: GapClosureOrchestrationReport) -> str:
    """Render a human-readable orchestration report."""
    lines = [
        f"# Gap Closure Orchestration — {report.topic}",
        "",
        f"- **Run:** `{report.run_id}`",
        f"- **Source pack:** `{report.source_pack}`",
        f"- **Mode:** `{report.mode}`",
        f"- **Promotion:** `{report.promotion_status}`",
        f"- **Manifest repair:** `{report.manifest_repair_status}`",
        f"- **Answer submit:** `{report.answer_submit_status}`",
        f"- **Topic profile updated:** `{report.topic_profile_updated}`",
        f"- **Generated:** {report.generated_at.isoformat()}",
        "",
        "## Steps",
        "",
    ]
    for step in report.steps:
        lines.append(f"- **{step.name}** (`{step.status}`): {step.message or '—'}")

    if report.answer_source:
        lines.extend(["", "## Answer bridge", ""])
        lines.append(f"- Source: `{report.answer_source}`")
        if report.answer_submission_run_id:
            lines.append(f"- Submission run: `{report.answer_submission_run_id}`")
        if report.answer_score is not None:
            lines.append(f"- Score: `{report.answer_score:.3f}`")
        lines.append(f"- Review required: `{report.answer_review_required}`")
        if report.answer_artifacts_written:
            lines.append("- Artifacts:")
            for name in report.answer_artifacts_written:
                lines.append(f"  - `{name}`")

    lines.extend(["", "## Commands planned", ""])
    for command in report.commands_planned:
        lines.append(f"- `{command}`")

    if report.commands_executed:
        lines.extend(["", "## Commands executed", ""])
        for command in report.commands_executed:
            lines.append(f"- `{command}`")

    if report.reports_written:
        lines.extend(["", "## Reports written", ""])
        for name in report.reports_written:
            lines.append(f"- `{name}`")

    lines.extend(["", "## Follow-up", ""])
    lines.append(f"- Command: `{report.followup_lesson_command}`")
    if report.followup_run_id:
        lines.append(f"- Follow-up run: `{report.followup_run_id}`")
    if report.gap_closure_verdict:
        lines.append(f"- Gap closure verdict: `{report.gap_closure_verdict}`")
    elif not report.followup_run_id:
        lines.append("- Run gap-closure after creating the follow-up lesson.")

    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in report.warnings:
            lines.append(f"- {warning}")

    if report.errors:
        lines.extend(["", "## Errors", ""])
        for error in report.errors:
            lines.append(f"- {error}")

    lines.append("")
    return "\n".join(lines)


def run_gap_closure_orchestration(
    project_root: Path,
    run_dir: Path,
    *,
    mode: GapClosureOrchestrationMode = "dry_run",
    promote_force: bool = False,
    repair_manifests: bool = False,
    create_followup: bool = False,
    difficulty: int = 2,
    answer_text: str | None = None,
    answer_file: Path | None = None,
    skip_answer_submit: bool = False,
    runners: dict[str, CollectorRunner] | None = None,
    lesson_create_runner: LessonCreateRunner | None = None,
    answer_submit_runner: AnswerSubmitRunner | None = None,
    manifest_repair_runner: Callable[[Path], tuple[list[str], int, str]] | None = None,
) -> GapClosureOrchestrationReport:
    """Execute or plan the guided gap-closure orchestration workflow."""
    run_id = run_dir.name
    steps: list[GapClosureOrchestrationStep] = []
    commands_planned: list[str] = []
    commands_executed: list[str] = []
    reports_written: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []
    promotion_status = "skipped"
    manifest_repair_status = "skipped"
    followup_run_id: str | None = None
    gap_closure_verdict: GapClosureVerdict | None = None
    answer_submit_status = "skipped"
    answer_source: str | None = None
    answer_submission_run_id: str | None = None
    answer_score: float | None = None
    answer_review_required = False
    topic_profile_updated = False
    answer_artifacts_written: list[str] = []

    resolved_answer, resolved_source = resolve_answer_input(answer_text, answer_file)
    if skip_answer_submit and resolved_answer:
        resolved_answer = None
        resolved_source = None

    plan, coverage = _load_weak_run_context(run_dir)
    topic = plan.topic
    source_pack = plan.source_pack
    followup_command = build_followup_lesson_command(topic, source_pack, difficulty)

    commands_planned = build_orchestration_workflow_commands(
        run_id,
        topic,
        source_pack,
        execute=mode == "execute",
        promote_force=promote_force,
        repair_manifests=repair_manifests,
        create_followup=create_followup,
        difficulty=difficulty,
        answer_text=answer_text,
        answer_file=answer_file,
        skip_answer_submit=skip_answer_submit,
    )

    coverage_msg = (
        f"coverage={coverage.coverage_score:.3f}, gaps={len(coverage.gaps)}"
        if coverage
        else "no coverage report"
    )
    steps.append(_step("read_weak_run", "Read current weak run", "executed", coverage_msg))

    if resolved_answer:
        answer_source = resolved_source
        submit_cmd = build_answer_submit_command(
            run_id,
            execute=mode == "execute",
            answer_text=answer_text,
            answer_file=answer_file,
        )
        if mode == "execute":
            submit_runner = answer_submit_runner or run_answer_submit
            try:
                result = submit_runner(
                    topic=topic,
                    answer_text=resolved_answer,
                    project_root=project_root,
                    run_id=run_id,
                )
                if result.get("error"):
                    message = str(result["error"])
                    errors.append(message)
                    answer_submit_status = "failed"
                    steps.append(_step("answer_submit", "Submit baseline answer", "error", message))
                else:
                    answer_submit_status = "executed"
                    answer_submission_run_id = str(result.get("run_id", run_id))
                    score = result.get("overall_score")
                    answer_score = float(score) if score is not None else None
                    review_path = run_dir / "answer_review.json"
                    if review_path.exists():
                        review = load_model(review_path, AnswerReviewV2)
                        answer_review_required = review.needs_review
                    answer_artifacts_written = [
                        name for name in ANSWER_ARTIFACT_NAMES if (run_dir / name).exists()
                    ]
                    if (run_dir / "answer_attempts").exists():
                        answer_artifacts_written.append("answer_attempts/")
                    update_path = run_dir / "topic_profile_update.json"
                    if update_path.exists():
                        pending = load_model(update_path, TopicProfileUpdate)
                        topic_profile_updated = pending.applied
                    if submit_cmd:
                        commands_executed.append(submit_cmd)
                    steps.append(
                        _step(
                            "answer_submit",
                            "Submit baseline answer",
                            "executed",
                            f"score={answer_score}, review={answer_review_required}",
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                errors.append(message)
                answer_submit_status = "failed"
                steps.append(_step("answer_submit", "Submit baseline answer", "error", message))
        else:
            answer_submit_status = "planned"
            if submit_cmd:
                steps.append(
                    _step(
                        "answer_submit",
                        "Submit baseline answer",
                        "planned",
                        submit_cmd,
                    )
                )
    elif skip_answer_submit and (answer_text or answer_file):
        answer_submit_status = "skipped"
        steps.append(
            _step(
                "answer_submit",
                "Submit baseline answer",
                "skipped",
                "Skipped via --skip-answer-submit",
            )
        )
    else:
        steps.append(
            _step(
                "answer_submit",
                "Submit baseline answer",
                "skipped",
                "No answer provided",
            )
        )

    try:
        expansion_plan = _ensure_expansion_plan(project_root, run_dir, plan)
        collector_count = len(expansion_plan.collector_queries)
        steps.append(
            _step(
                "inspect_expansion_plan",
                "Inspect expansion plan",
                "executed",
                f"{collector_count} collector queries",
            )
        )
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        errors.append(message)
        steps.append(_step("inspect_expansion_plan", "Inspect expansion plan", "error", message))

    expansion_mode = mode
    expansion_cmd = f"sourcelab research expansion run --run {run_id} --{expansion_mode.replace('_', '-')}"
    try:
        execution, improvement = write_library_expansion_execution(
            project_root,
            run_dir,
            mode=expansion_mode,
            runners=runners,
        )
        reports_written.extend(["library_expansion_execution.json", "library_expansion_execution.md"])
        if improvement is not None:
            reports_written.extend(["library_improvement_report.json", "library_improvement_report.md"])
        if mode == "execute":
            commands_executed.append(expansion_cmd)
            step_status = "executed"
            step_msg = f"{len(execution.executed_collectors)} collector entries"
        else:
            step_status = "planned"
            step_msg = f"{len(execution.collector_commands)} commands planned"
        if execution.errors:
            warnings.extend(execution.errors)
        steps.append(_step("expansion_execution", "Run expansion collectors", step_status, step_msg))
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        errors.append(message)
        steps.append(_step("expansion_execution", "Run expansion collectors", "error", message))

    if mode == "execute":
        steps.append(
            _step(
                "dedupe_quality",
                "Dedupe and quality pass",
                "executed",
                "Ran after successful collector execution",
            )
        )
    else:
        steps.append(
            _step(
                "dedupe_quality",
                "Dedupe and quality pass",
                "planned",
                "Runs automatically in execute mode after collectors",
            )
        )

    promote_cmd = (
        f"sourcelab research expansion promote --run {run_id} --{'force' if promote_force else 'dry-run'}"
    )
    try:
        promotion = write_source_promotion_report(project_root, run_dir, force=promote_force)
        reports_written.extend(["source_promotion_report.json", "source_promotion_report.md"])
        promotion_status = promotion.mode
        if promote_force:
            commands_executed.append(promote_cmd)
            step_status = "executed"
        else:
            step_status = "planned"
        steps.append(
            _step(
                "promotion",
                "Propose promotion candidates",
                step_status,
                f"{len(promotion.candidates)} candidates, promoted={promotion.promoted_count}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        errors.append(message)
        steps.append(_step("promotion", "Propose promotion candidates", "error", message))

    if repair_manifests:
        if not promote_force:
            manifest_repair_status = "skipped"
            warning = "Manifest repair requires --promote-force; skipped."
            warnings.append(warning)
            steps.append(_step("manifest_repair", "Repair manifests", "skipped", warning))
        else:
            repair_runner = manifest_repair_runner or run_manifest_repair
            repair_cmd = "python scripts/bootstrap_sourcelab_source_packs.py --repair-manifests"
            try:
                lines, returncode, _output = repair_runner(project_root)
                if returncode == 0:
                    manifest_repair_status = "executed"
                    commands_executed.append(repair_cmd)
                    steps.append(
                        _step(
                            "manifest_repair",
                            "Repair manifests",
                            "executed",
                            f"{len(lines)} repair actions",
                        )
                    )
                else:
                    manifest_repair_status = "failed"
                    warning = f"Manifest repair exited with code {returncode}"
                    warnings.append(warning)
                    if lines:
                        warnings.extend(lines[:5])
                    steps.append(_step("manifest_repair", "Repair manifests", "error", warning))
            except Exception as exc:  # noqa: BLE001
                manifest_repair_status = "failed"
                message = str(exc)
                warnings.append(message)
                steps.append(_step("manifest_repair", "Repair manifests", "error", message))
    else:
        steps.append(
            _step("manifest_repair", "Repair manifests", "skipped", "Not requested")
        )

    steps.append(
        _step(
            "followup_command",
            "Suggest follow-up lesson command",
            "executed",
            followup_command,
        )
    )

    if create_followup:
        if mode != "execute":
            warning = "Follow-up lesson creation requires orchestration --execute; skipped."
            warnings.append(warning)
            steps.append(_step("followup_lesson", "Create follow-up lesson", "skipped", warning))
        else:
            create_runner = lesson_create_runner or run_lesson_create
            try:
                result = create_runner(
                    topic=topic,
                    project_root=project_root,
                    difficulty=difficulty,
                    source_pack=source_pack,
                )
                followup_run_id = str(result.get("run_id", "")) or None
                if followup_run_id:
                    commands_executed.append(followup_command)
                    steps.append(
                        _step(
                            "followup_lesson",
                            "Create follow-up lesson",
                            "executed",
                            f"run_id={followup_run_id}",
                        )
                    )
                    follow_up_dir = project_root / "artifacts" / "runs" / followup_run_id
                    follow_up_plan_path = follow_up_dir / "research_plan.json"
                    if follow_up_plan_path.exists():
                        follow_up_plan = load_model(follow_up_plan_path, ResearchPlan)
                        gap_report = write_gap_closure_report(project_root, follow_up_dir, follow_up_plan)
                        gap_closure_verdict = gap_report.verdict
                        reports_written.extend(["gap_closure_report.json", "gap_closure_report.md"])
                        commands_executed.append(
                            f"sourcelab research gap-closure --run {followup_run_id}"
                        )
                        steps.append(
                            _step(
                                "gap_closure_compare",
                                "Compare gap closure",
                                "executed",
                                f"verdict={gap_report.verdict}",
                            )
                        )
                    else:
                        warning = f"Follow-up run {followup_run_id} missing research_plan.json"
                        warnings.append(warning)
                        steps.append(
                            _step("gap_closure_compare", "Compare gap closure", "error", warning)
                        )
                else:
                    error = "Lesson create did not return run_id"
                    errors.append(error)
                    steps.append(_step("followup_lesson", "Create follow-up lesson", "error", error))
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                errors.append(message)
                steps.append(_step("followup_lesson", "Create follow-up lesson", "error", message))
    else:
        steps.append(
            _step(
                "gap_closure_compare",
                "Compare gap closure",
                "planned",
                "Run gap-closure after follow-up lesson",
            )
        )

    report = GapClosureOrchestrationReport(
        run_id=run_id,
        topic=topic,
        source_pack=source_pack,
        mode=mode,
        generated_at=utc_now(),
        steps=steps,
        commands_planned=commands_planned,
        commands_executed=commands_executed,
        reports_written=reports_written,
        promotion_status=promotion_status,
        manifest_repair_status=manifest_repair_status,
        followup_lesson_command=followup_command,
        followup_run_id=followup_run_id,
        gap_closure_verdict=gap_closure_verdict,
        answer_submit_status=answer_submit_status,
        answer_source=answer_source,
        answer_submission_run_id=answer_submission_run_id,
        answer_score=answer_score,
        answer_review_required=answer_review_required,
        topic_profile_updated=topic_profile_updated,
        answer_artifacts_written=answer_artifacts_written,
        errors=errors,
        warnings=warnings,
    )
    return report


def write_gap_closure_orchestration(
    project_root: Path,
    run_dir: Path,
    **kwargs: object,
) -> GapClosureOrchestrationReport:
    """Write gap_closure_orchestration.json and .md."""
    report = run_gap_closure_orchestration(project_root, run_dir, **kwargs)  # type: ignore[arg-type]
    record_orchestration_completion(project_root, report)
    (run_dir / "gap_closure_orchestration.json").write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (run_dir / "gap_closure_orchestration.md").write_text(
        render_gap_closure_orchestration_markdown(report),
        encoding="utf-8",
    )
    return report
