"""CLI handlers for the SourceLab research command group."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sourcelab.library.expansion import maybe_write_source_expansion_suggestions
from sourcelab.library.io import load_model
from sourcelab.research import plan_research

from sourcelab.research.evolution import (
    write_lesson_evolution_report,
)
from sourcelab.research.expansion_execution import write_library_expansion_execution
from sourcelab.research.gap_closure import write_gap_closure_report
from sourcelab.research.gap_closure_orchestration import write_gap_closure_orchestration
from sourcelab.research.gap_closure_replay import replay_gap_closure_orchestration
from sourcelab.research.genericness import build_genericness_report
from sourcelab.research.library_expansion_plan import (
    build_library_expansion_plan,
    maybe_write_library_expansion_plan,
)
from sourcelab.research.slugs import topic_slug
from sourcelab.research.source_promotion import write_source_promotion_report
from sourcelab.library.schemas import SourceExpansionSuggestions
from sourcelab.research.schemas import (
    GapClosureReport,
    GenericnessReport,
    LessonEvolutionReport,
    LibraryExpansionPlan,
    ResearchPlan,
    RetrievalStrategy,
    SourceCoverageReport,
)
from sourcelab.research.source_coverage import build_source_coverage_report
from sourcelab.research.topic_profile import load_topic_profile
from sourcelab.ui.run_loader import get_latest_run, list_runs, summarize_run


def _json(data: object) -> None:
    print(json.dumps(data, indent=2, default=str))


def _project_root(args: argparse.Namespace) -> Path:
    return Path(getattr(args, "project_root", None) or Path.cwd())


def _resolve_run_dir(project_root: Path, run_ref: str) -> Path:
    if run_ref == "latest":
        summary = get_latest_run(project_root)
        if summary is None:
            print("No runs found.", file=sys.stderr)
            sys.exit(1)
        return project_root / "artifacts" / "runs" / summary.run_id
    return project_root / "artifacts" / "runs" / run_ref


def _resolve_run_ref(args: argparse.Namespace) -> str:
    return getattr(args, "run", "latest")


def cmd_research_plan(args: argparse.Namespace) -> None:
    run_id = "plan_preview"
    plan = plan_research(run_id, args.topic, args.source_pack)
    _json(plan.model_dump(mode="json"))


def cmd_research_coverage(args: argparse.Namespace) -> None:
    run_dir = _resolve_run_dir(_project_root(args), args.run)
    strategy_path = run_dir / "retrieval_strategy.json"
    plan_path = run_dir / "research_plan.json"
    if not strategy_path.exists() or not plan_path.exists():
        print(f"Missing research artifacts in {run_dir}", file=sys.stderr)
        sys.exit(1)

    strategy = load_model(strategy_path, RetrievalStrategy)
    plan = load_model(plan_path, ResearchPlan)
    coverage_path = run_dir / "source_coverage_report.json"
    if coverage_path.exists():
        coverage = load_model(coverage_path, SourceCoverageReport)
    else:
        coverage = build_source_coverage_report(strategy, plan)
    _json(coverage.model_dump(mode="json"))


def cmd_research_genericness(args: argparse.Namespace) -> None:
    run_dir = _resolve_run_dir(_project_root(args), args.run)
    report_path = run_dir / "genericness_report.json"
    if report_path.exists():
        _json(json.loads(report_path.read_text(encoding="utf-8")))
        return

    plan = load_model(run_dir / "research_plan.json", ResearchPlan)
    coverage = None
    coverage_path = run_dir / "source_coverage_report.json"
    if coverage_path.exists():
        coverage = load_model(coverage_path, SourceCoverageReport)
    report = build_genericness_report(
        run_id=plan.run_id,
        topic=plan.topic,
        source_pack=plan.source_pack,
        plan=plan,
        coverage=coverage,
    )
    _json(report.model_dump(mode="json"))


def cmd_research_profile(args: argparse.Namespace) -> None:
    root = _project_root(args)
    profile = load_topic_profile(root, args.source_pack, args.topic)
    if profile is None:
        _json(
            {
                "topic": args.topic,
                "topic_slug": topic_slug(args.topic),
                "source_pack": args.source_pack,
                "status": "no_profile",
            }
        )
        return
    _json(profile.model_dump(mode="json"))


def _load_expansion_payload(root: Path, run_dir: Path) -> tuple[SourceExpansionSuggestions | None, LibraryExpansionPlan]:
    expansion_path = run_dir / "source_expansion_suggestions.json"
    plan_path = run_dir / "research_plan.json"

    suggestions: SourceExpansionSuggestions | None = None
    if expansion_path.exists():
        suggestions = load_model(expansion_path, SourceExpansionSuggestions)
    elif plan_path.exists():
        summary = summarize_run(run_dir)
        topic = summary.topic if summary else "source expansion"
        maybe_write_source_expansion_suggestions(root, run_dir, topic)
        if expansion_path.exists():
            suggestions = load_model(expansion_path, SourceExpansionSuggestions)

    plan = load_model(plan_path, ResearchPlan) if plan_path.exists() else None
    topic = plan.topic if plan else (summarize_run(run_dir).topic or "source expansion")
    source_pack = plan.source_pack if plan else ""

    plan_path_out = run_dir / "library_expansion_plan.json"
    if plan_path_out.exists():
        payload = load_model(plan_path_out, LibraryExpansionPlan)
    else:
        payload = build_library_expansion_plan(run_dir.name, topic, source_pack, suggestions)
        if plan is not None:
            maybe_write_library_expansion_plan(run_dir, plan)

    return suggestions, payload


def cmd_research_expansion(args: argparse.Namespace) -> None:
    action = getattr(args, "expansion_action", None)
    if action == "run":
        cmd_research_expansion_run(args)
        return
    if action == "promote":
        cmd_research_expansion_promote(args)
        return

    root = _project_root(args)
    run_dir = _resolve_run_dir(root, _resolve_run_ref(args))
    suggestions, payload = _load_expansion_payload(root, run_dir)
    _json(
        {
            "expansion_suggestions": suggestions.model_dump(mode="json") if suggestions else None,
            "library_expansion_plan": payload.model_dump(mode="json"),
        }
    )


def cmd_research_expansion_run(args: argparse.Namespace) -> None:
    root = _project_root(args)
    run_dir = _resolve_run_dir(root, _resolve_run_ref(args))
    execute = getattr(args, "execute", False)
    mode = "execute" if execute else "dry_run"

    try:
        execution, improvement = write_library_expansion_execution(
            root,
            run_dir,
            mode=mode,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    payload: dict[str, object] = {
        "library_expansion_execution": execution.model_dump(mode="json"),
    }
    if improvement is not None:
        payload["library_improvement_report"] = improvement.model_dump(mode="json")
    _json(payload)


def cmd_research_expansion_promote(args: argparse.Namespace) -> None:
    root = _project_root(args)
    run_dir = _resolve_run_dir(root, _resolve_run_ref(args))
    force = getattr(args, "force", False)

    try:
        report = write_source_promotion_report(root, run_dir, force=force)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    _json({"source_promotion_report": report.model_dump(mode="json")})


def cmd_research_gap_closure(args: argparse.Namespace) -> None:
    action = getattr(args, "gap_closure_action", None)
    if action == "run":
        cmd_research_gap_closure_run(args)
        return
    if action == "replay":
        cmd_research_gap_closure_replay(args)
        return

    root = _project_root(args)
    if getattr(args, "topic", None) and getattr(args, "source_pack", None):
        run_dir = _find_latest_run_for_topic(root, args.topic, args.source_pack)
        if run_dir is None:
            print(
                f"No runs found for topic '{args.topic}' in pack '{args.source_pack}'.",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        run_dir = _resolve_run_dir(root, _resolve_run_ref(args))

    plan_path = run_dir / "research_plan.json"
    if not plan_path.exists():
        print(f"Missing research_plan.json in {run_dir}", file=sys.stderr)
        sys.exit(1)

    plan = load_model(plan_path, ResearchPlan)
    report_path = run_dir / "gap_closure_report.json"
    if report_path.exists() and not getattr(args, "refresh", False):
        report = load_model(report_path, GapClosureReport)
    else:
        report = write_gap_closure_report(root, run_dir, plan)

    _json({"gap_closure_report": report.model_dump(mode="json")})


def cmd_research_gap_closure_run(args: argparse.Namespace) -> None:
    root = _project_root(args)
    run_dir = _resolve_run_dir(root, _resolve_run_ref(args))
    execute = getattr(args, "execute", False)
    mode = "execute" if execute else "dry_run"
    promote_force = getattr(args, "promote_force", False)
    repair_manifests = getattr(args, "repair_manifests", False)
    create_followup = getattr(args, "create_followup", False)
    difficulty = int(getattr(args, "difficulty", 2))
    answer_text = getattr(args, "answer_text", None)
    answer_file_raw = getattr(args, "answer_file", None)
    answer_file = Path(answer_file_raw) if answer_file_raw else None
    skip_answer_submit = getattr(args, "skip_answer_submit", False)

    if answer_text and answer_file:
        print("Error: Provide only one of --answer-text or --answer-file.", file=sys.stderr)
        sys.exit(1)

    if repair_manifests and not promote_force:
        print(
            "Warning: --repair-manifests requires --promote-force; manifest repair will be skipped.",
            file=sys.stderr,
        )

    try:
        report = write_gap_closure_orchestration(
            root,
            run_dir,
            mode=mode,
            promote_force=promote_force,
            repair_manifests=repair_manifests,
            create_followup=create_followup,
            difficulty=difficulty,
            answer_text=answer_text,
            answer_file=answer_file,
            skip_answer_submit=skip_answer_submit,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    _json({"gap_closure_orchestration": report.model_dump(mode="json")})


def cmd_research_gap_closure_replay(args: argparse.Namespace) -> None:
    root = _project_root(args)
    run_dir = _resolve_run_dir(root, _resolve_run_ref(args))
    continue_run = getattr(args, "continue_run", False)

    try:
        summary = replay_gap_closure_orchestration(root, run_dir, continue_run=continue_run)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    print(summary.get("replay_markdown", ""))
    _json({"gap_closure_replay": summary})


def _find_latest_run_for_topic(root: Path, topic: str, source_pack: str) -> Path | None:
    slug = topic_slug(topic)
    matches: list[str] = []
    for summary in list_runs(root):
        run_dir = root / "artifacts" / "runs" / summary.run_id
        plan_path = run_dir / "research_plan.json"
        if plan_path.exists():
            plan = load_model(plan_path, ResearchPlan)
            if topic_slug(plan.topic) == slug and plan.source_pack == source_pack:
                matches.append(summary.run_id)
    if not matches:
        return None
    return root / "artifacts" / "runs" / matches[-1]


def cmd_research_evolution(args: argparse.Namespace) -> None:
    root = _project_root(args)
    if getattr(args, "topic", None) and getattr(args, "source_pack", None):
        run_dir = _find_latest_run_for_topic(root, args.topic, args.source_pack)
        if run_dir is None:
            print(f"No runs found for topic '{args.topic}' in pack '{args.source_pack}'.", file=sys.stderr)
            sys.exit(1)
    else:
        run_dir = _resolve_run_dir(root, args.run)

    report_path = run_dir / "lesson_evolution_report.json"
    plan_path = run_dir / "research_plan.json"
    if not plan_path.exists():
        print(f"Missing research_plan.json in {run_dir}", file=sys.stderr)
        sys.exit(1)

    plan = load_model(plan_path, ResearchPlan)
    if report_path.exists():
        report = load_model(report_path, LessonEvolutionReport)
    else:
        report = write_lesson_evolution_report(root, run_dir, None, plan)

    profile = load_topic_profile(root, plan.source_pack, plan.topic)
    _json(
        {
            "evolution_report": report.model_dump(mode="json"),
            "previous_runs": report.previous_run_ids,
            "profile_used": report.profile_used,
            "profile": profile.model_dump(mode="json") if profile else None,
            "quality_delta": report.quality_delta.model_dump(mode="json"),
            "verdict": report.verdict,
            "weak_concepts_addressed": report.quality_delta.weak_concepts_addressed,
            "gaps_closed": report.quality_delta.gaps_closed,
            "gaps_new": report.quality_delta.gaps_new,
        }
    )


def register_research_subparser(sub: argparse._SubParsersAction) -> None:
    """Register `sourcelab research ...` commands on the root parser."""
    research = sub.add_parser("research", help="Library-aware research engine commands.")
    research_sub = research.add_subparsers(required=True)

    plan_cmd = research_sub.add_parser("plan", help="Preview a research plan for a topic.")
    plan_cmd.add_argument("--topic", required=True, help="Research topic")
    plan_cmd.add_argument("--source-pack", required=True, help="Source pack name")
    plan_cmd.set_defaults(func=cmd_research_plan)

    coverage_cmd = research_sub.add_parser("coverage", help="Show source coverage for a run.")
    coverage_cmd.add_argument("--run", default="latest", help="Run ID or 'latest'")
    coverage_cmd.set_defaults(func=cmd_research_coverage)

    genericness_cmd = research_sub.add_parser("genericness", help="Show genericness report for a run.")
    genericness_cmd.add_argument("--run", default="latest", help="Run ID or 'latest'")
    genericness_cmd.set_defaults(func=cmd_research_genericness)

    profile_cmd = research_sub.add_parser("profile", help="Show adaptive topic profile.")
    profile_cmd.add_argument("--topic", required=True, help="Topic string")
    profile_cmd.add_argument("--source-pack", required=True, help="Source pack name")
    profile_cmd.set_defaults(func=cmd_research_profile)

    expansion_cmd = research_sub.add_parser("expansion", help="Library expansion plan and execution.")
    expansion_cmd.add_argument("--run", default="latest", help="Run ID or 'latest'")
    expansion_sub = expansion_cmd.add_subparsers(dest="expansion_action", required=False)
    expansion_cmd.set_defaults(func=cmd_research_expansion, expansion_action=None)

    expansion_run = expansion_sub.add_parser("run", help="Dry-run or execute expansion collector commands.")
    expansion_run.add_argument("--run", default="latest", help="Run ID or 'latest'")
    expansion_run.add_argument("--dry-run", action="store_true", default=True, help="Print commands without executing (default)")
    expansion_run.add_argument("--execute", action="store_true", default=False, help="Execute supported collectors")
    expansion_run.set_defaults(func=cmd_research_expansion, expansion_action="run")

    expansion_promote = expansion_sub.add_parser("promote", help="Propose or force-promote library cards into source pack.")
    expansion_promote.add_argument("--run", default="latest", help="Run ID or 'latest'")
    expansion_promote.add_argument("--dry-run", action="store_true", default=True, help="Proposal only (default)")
    expansion_promote.add_argument("--force", action="store_true", default=False, help="Write promoted sources into pack")
    expansion_promote.set_defaults(func=cmd_research_expansion, expansion_action="promote")

    evolution_cmd = research_sub.add_parser("evolution", help="Show lesson evolution report for a follow-up run.")
    evolution_cmd.add_argument("--run", default="latest", help="Run ID or 'latest'")
    evolution_cmd.add_argument("--topic", default=None, help="Topic string (uses latest matching run)")
    evolution_cmd.add_argument("--source-pack", default=None, help="Source pack (with --topic)")
    evolution_cmd.set_defaults(func=cmd_research_evolution)

    gap_closure_cmd = research_sub.add_parser("gap-closure", help="Compare baseline vs follow-up gap closure.")
    gap_closure_cmd.add_argument("--run", default="latest", help="Run ID or 'latest'")
    gap_closure_cmd.add_argument("--topic", default=None, help="Topic string (uses latest matching run)")
    gap_closure_cmd.add_argument("--source-pack", default=None, help="Source pack (with --topic)")
    gap_closure_sub = gap_closure_cmd.add_subparsers(dest="gap_closure_action", required=False)
    gap_closure_cmd.set_defaults(func=cmd_research_gap_closure, gap_closure_action=None)

    gap_closure_run = gap_closure_sub.add_parser("run", help="Guided gap-closure orchestration.")
    gap_closure_run.add_argument("--run", default="latest", help="Run ID or 'latest'")
    gap_closure_run.add_argument("--dry-run", action="store_true", default=True, help="Plan workflow without executing (default)")
    gap_closure_run.add_argument("--execute", action="store_true", default=False, help="Execute expansion, promotion, optional follow-up")
    gap_closure_run.add_argument("--promote-dry-run", action="store_true", default=True, help="Promotion proposal only (default)")
    gap_closure_run.add_argument("--promote-force", action="store_true", default=False, help="Force-promote matching sources into pack")
    gap_closure_run.add_argument("--repair-manifests", action="store_true", default=False, help="Repair manifests after promote force")
    gap_closure_run.add_argument("--create-followup", action="store_true", default=False, help="Create follow-up lesson after expansion/promotion")
    gap_closure_run.add_argument("--difficulty", type=int, default=2, help="Follow-up lesson difficulty (default: 2)")
    gap_closure_run.add_argument("--answer-text", default=None, help="Submit answer text against baseline run before expansion")
    gap_closure_run.add_argument("--answer-file", default=None, help="Submit answer from file against baseline run before expansion")
    gap_closure_run.add_argument("--skip-answer-submit", action="store_true", default=False, help="Skip answer submission even if answer flags are set")
    gap_closure_run.set_defaults(func=cmd_research_gap_closure, gap_closure_action="run")

    gap_closure_replay = gap_closure_sub.add_parser("replay", help="Replay orchestration plan from gap_closure_orchestration.json")
    gap_closure_replay.add_argument("--run", default="latest", help="Run ID or 'latest'")
    gap_closure_replay.add_argument("--continue", dest="continue_run", action="store_true", default=False, help="Run missing non-destructive steps")
    gap_closure_replay.set_defaults(func=cmd_research_gap_closure, gap_closure_action="replay")
