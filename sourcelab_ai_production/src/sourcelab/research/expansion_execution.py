"""Execute library expansion plans via supported collectors."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sourcelab.library.collectors.arxiv import collect_arxiv
from sourcelab.library.collectors.local_docs import collect_local_docs
from sourcelab.library.collectors.nvd import collect_nvd
from sourcelab.library.collectors.pubmed import collect_pubmed
from sourcelab.library.dedupe import dedupe_library
from sourcelab.library.expansion import maybe_write_source_expansion_suggestions
from sourcelab.library.io import load_model, utc_now
from sourcelab.library.schemas import SourceExpansionSuggestions
from sourcelab.research.schemas import LibraryExpansionPlan, ResearchPlan
from sourcelab.ui.run_loader import summarize_run
from sourcelab.library.normalize import normalize_library
from sourcelab.library.quality import quality_library
from sourcelab.library.schemas import LibraryBuildReport
from sourcelab.research.library_expansion_plan import (
    _example_command,
    build_library_expansion_plan,
    maybe_write_library_expansion_plan,
)
from sourcelab.research.library_improvement import (
    build_library_improvement_report,
    snapshot_library_metrics,
    write_library_improvement_report,
)
from sourcelab.research.schemas import (
    CollectorExecutionEntry,
    CollectorQueryPlan,
    ExpansionExecutionMode,
    LibraryExpansionExecution,
    LibraryExpansionPlan,
)

SUPPORTED_COLLECTORS = frozenset({"local_docs", "arxiv", "pubmed", "nvd"})

COLLECTOR_DOMAINS: dict[str, str] = {
    "local_docs": "user_project_library",
    "arxiv": "research",
    "pubmed": "research",
    "nvd": "security",
}

CollectorRunner = Callable[[Path, CollectorQueryPlan], LibraryBuildReport]


def _default_run_local_docs(project_root: Path, query: CollectorQueryPlan) -> LibraryBuildReport:
    scan_path = Path(query.query) if query.query.strip() else project_root
    if not scan_path.is_absolute():
        scan_path = project_root / scan_path
    report = collect_local_docs(project_root, scan_path, domain=COLLECTOR_DOMAINS["local_docs"])
    normalize_library(project_root)
    return report


def _default_run_arxiv(project_root: Path, query: CollectorQueryPlan) -> LibraryBuildReport:
    return collect_arxiv(
        project_root,
        query=query.query,
        domain=COLLECTOR_DOMAINS["arxiv"],
        max_results=5,
    )


def _default_run_pubmed(project_root: Path, query: CollectorQueryPlan) -> LibraryBuildReport:
    return collect_pubmed(
        project_root,
        query=query.query,
        domain=COLLECTOR_DOMAINS["pubmed"],
        max_results=5,
    )


def _default_run_nvd(project_root: Path, query: CollectorQueryPlan) -> LibraryBuildReport:
    return collect_nvd(
        project_root,
        domain=COLLECTOR_DOMAINS["nvd"],
        keyword=query.query,
        max_results=5,
    )


DEFAULT_COLLECTOR_RUNNERS: dict[str, CollectorRunner] = {
    "local_docs": _default_run_local_docs,
    "arxiv": _default_run_arxiv,
    "pubmed": _default_run_pubmed,
    "nvd": _default_run_nvd,
}


def _resolve_expansion_plan(project_root: Path, run_dir: Path) -> LibraryExpansionPlan:
    plan_path = run_dir / "library_expansion_plan.json"
    if plan_path.exists():
        return load_model(plan_path, LibraryExpansionPlan)

    expansion_path = run_dir / "source_expansion_suggestions.json"
    suggestions: SourceExpansionSuggestions | None = None
    if expansion_path.exists():
        suggestions = load_model(expansion_path, SourceExpansionSuggestions)
    else:
        research_plan_path = run_dir / "research_plan.json"
        if research_plan_path.exists():
            research_plan = load_model(research_plan_path, ResearchPlan)
            maybe_write_source_expansion_suggestions(project_root, run_dir, research_plan.topic)
            if expansion_path.exists():
                suggestions = load_model(expansion_path, SourceExpansionSuggestions)

    research_plan_path = run_dir / "research_plan.json"
    if research_plan_path.exists():
        research_plan = load_model(research_plan_path, ResearchPlan)
        maybe_write_library_expansion_plan(run_dir, research_plan)
        if plan_path.exists():
            return load_model(plan_path, LibraryExpansionPlan)
        return build_library_expansion_plan(
            run_dir.name,
            research_plan.topic,
            research_plan.source_pack,
            suggestions,
        )

    summary = summarize_run(run_dir)
    topic = summary.topic if summary else "source expansion"
    return build_library_expansion_plan(run_dir.name, topic, "", suggestions)


def _build_execution_entries(
    plan: LibraryExpansionPlan,
    mode: ExpansionExecutionMode,
    runners: dict[str, CollectorRunner],
    project_root: Path,
) -> tuple[list[CollectorExecutionEntry], list[CollectorExecutionEntry], list[str]]:
    executed: list[CollectorExecutionEntry] = []
    manual: list[CollectorExecutionEntry] = []
    errors: list[str] = []

    for query_plan in plan.collector_queries:
        command = query_plan.example_command or _example_command(query_plan.collector, query_plan.query)
        if query_plan.collector not in SUPPORTED_COLLECTORS:
            manual.append(
                CollectorExecutionEntry(
                    collector=query_plan.collector,
                    query=query_plan.query,
                    command=command,
                    status="manual",
                    priority=query_plan.priority,
                    message="Unsupported collector — run manually or add a custom integration.",
                )
            )
            continue

        if mode == "dry_run":
            executed.append(
                CollectorExecutionEntry(
                    collector=query_plan.collector,
                    query=query_plan.query,
                    command=command,
                    status="planned",
                    priority=query_plan.priority,
                    message="Dry-run — collector not executed.",
                )
            )
            continue

        runner = runners.get(query_plan.collector)
        if runner is None:
            errors.append(f"No runner registered for collector '{query_plan.collector}'")
            executed.append(
                CollectorExecutionEntry(
                    collector=query_plan.collector,
                    query=query_plan.query,
                    command=command,
                    status="error",
                    priority=query_plan.priority,
                    message="Runner missing.",
                )
            )
            continue

        try:
            report = runner(project_root, query_plan)
            executed.append(
                CollectorExecutionEntry(
                    collector=query_plan.collector,
                    query=query_plan.query,
                    command=command,
                    status="executed",
                    priority=query_plan.priority,
                    message=report.message or report.status,
                )
            )
        except Exception as exc:  # noqa: BLE001 — surface collector failures in artifact
            message = str(exc)
            errors.append(f"{query_plan.collector}: {message}")
            executed.append(
                CollectorExecutionEntry(
                    collector=query_plan.collector,
                    query=query_plan.query,
                    command=command,
                    status="error",
                    priority=query_plan.priority,
                    message=message,
                )
            )

    return executed, manual, errors


def build_library_expansion_execution(
    project_root: Path,
    run_dir: Path,
    mode: ExpansionExecutionMode = "dry_run",
    runners: dict[str, CollectorRunner] | None = None,
    before_metrics: dict[str, int | float] | None = None,
) -> tuple[LibraryExpansionExecution, dict[str, int | float] | None]:
    """Build expansion execution report; optionally run collectors in execute mode."""
    plan = _resolve_expansion_plan(project_root, run_dir)
    active_runners = runners if runners is not None else DEFAULT_COLLECTOR_RUNNERS
    metrics_before = before_metrics if before_metrics is not None else snapshot_library_metrics(project_root)

    executed, manual, errors = _build_execution_entries(plan, mode, active_runners, project_root)

    if mode == "execute" and any(entry.status == "executed" for entry in executed):
        normalize_library(project_root)
        dedupe_library(project_root)
        quality_library(project_root)

    commands = [
        entry.command
        for entry in (*executed, *manual)
        if entry.command
    ]
    if not commands:
        commands = [
            _example_command(query.collector, query.query)
            for query in plan.collector_queries
        ]

    execution = LibraryExpansionExecution(
        run_id=run_dir.name,
        topic=plan.topic,
        source_pack=plan.source_pack,
        generated_at=utc_now(),
        mode=mode,
        baseline_run_id=run_dir.name,
        baseline_topic=plan.topic,
        baseline_source_pack=plan.source_pack,
        collector_commands=commands,
        executed_collectors=executed,
        manual_collectors=manual,
        errors=errors,
    )
    metrics_after = snapshot_library_metrics(project_root) if mode == "execute" else None
    return execution, metrics_before if mode == "execute" else metrics_after


def render_expansion_execution_markdown(report: LibraryExpansionExecution) -> str:
    """Render a human-readable expansion execution report."""
    lines = [
        f"# Library Expansion Execution — {report.topic}",
        "",
        f"- **Run:** `{report.run_id}`",
        f"- **Source pack:** `{report.source_pack}`",
        f"- **Mode:** `{report.mode}`",
        f"- **Generated:** {report.generated_at.isoformat()}",
        "",
        "## Collector commands",
        "",
    ]
    for command in report.collector_commands:
        lines.append(f"- `{command}`")

    lines.extend(["", "## Executed / planned collectors", ""])
    if report.executed_collectors:
        for entry in report.executed_collectors:
            lines.append(
                f"- **{entry.collector}** ({entry.status}): `{entry.command}` — {entry.message or entry.query}"
            )
    else:
        lines.append("- _(none)_")

    lines.extend(["", "## Manual collectors", ""])
    if report.manual_collectors:
        for entry in report.manual_collectors:
            lines.append(f"- **{entry.collector}**: {entry.message or entry.query}")
    else:
        lines.append("- _(none)_")

    if report.errors:
        lines.extend(["", "## Errors", ""])
        for error in report.errors:
            lines.append(f"- {error}")

    lines.append("")
    return "\n".join(lines)


def write_library_expansion_execution(
    project_root: Path,
    run_dir: Path,
    mode: ExpansionExecutionMode = "dry_run",
    runners: dict[str, CollectorRunner] | None = None,
) -> tuple[LibraryExpansionExecution, object | None]:
    """Write library_expansion_execution.json/.md and optional improvement report."""
    before_metrics = snapshot_library_metrics(project_root)
    execution, metrics_before = build_library_expansion_execution(
        project_root,
        run_dir,
        mode=mode,
        runners=runners,
        before_metrics=before_metrics,
    )
    plan_path = run_dir / "library_expansion_plan.json"
    if not plan_path.exists():
        plan_path.write_text(
            _resolve_expansion_plan(project_root, run_dir).model_dump_json(indent=2),
            encoding="utf-8",
        )
    markdown = render_expansion_execution_markdown(execution)
    (run_dir / "library_expansion_execution.json").write_text(
        execution.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (run_dir / "library_expansion_execution.md").write_text(markdown, encoding="utf-8")

    improvement = None
    if mode == "execute":
        after_metrics = snapshot_library_metrics(project_root)
        improvement = build_library_improvement_report(
            run_dir.name,
            execution.topic,
            execution.source_pack,
            metrics_before or before_metrics,
            after_metrics,
            execution,
        )
        write_library_improvement_report(run_dir, improvement)

    return execution, improvement
