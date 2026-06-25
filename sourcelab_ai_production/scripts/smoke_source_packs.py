#!/usr/bin/env python3
"""
smoke_source_packs.py

Source Pack Smoke Matrix v1 — discover local source packs and run a lightweight
validation matrix via sourcelab CLI subprocesses.

Run from the SourceLab project root:

    python scripts/smoke_source_packs.py --packs core --run-evals --run-lessons
    python scripts/smoke_source_packs.py --packs all --run-evals
    python scripts/smoke_source_packs.py --packs agentic_engineering_v1 --dry-run

Writes:
- artifacts/source_pack_smoke_matrix.json
- artifacts/source_pack_smoke_matrix.md
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from bootstrap_sourcelab_source_packs import (  # noqa: E402
    GROUPS,
    PROTECTED_PACKS,
    find_project_root,
    run_command,
)

BUILTIN_SKIP_PACKS = PROTECTED_PACKS
JSON_REPORT = "source_pack_smoke_matrix.json"
MD_REPORT = "source_pack_smoke_matrix.md"


@dataclass
class PackSmokeRow:
    pack_name: str
    doctor_valid: bool = False
    source_count: int = 0
    eval_count: int = 0
    eval_status: str = "skipped"
    lesson_status: str = "skipped"
    run_id: str = ""
    proof_status: str = "skipped"
    harness_status: str = "skipped"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def discover_source_packs(root: Path, *, skip_builtins: bool = True) -> list[str]:
    """Discover pack directories under data/source_packs/."""
    packs_dir = root / "data" / "source_packs"
    if not packs_dir.is_dir():
        return []

    names: list[str] = []
    for pack_dir in sorted(packs_dir.iterdir()):
        if not pack_dir.is_dir():
            continue
        if skip_builtins and pack_dir.name in BUILTIN_SKIP_PACKS:
            continue
        if (pack_dir / "pack.json").is_file() or (pack_dir / "manifest.json").is_file():
            names.append(pack_dir.name)
    return names


def resolve_pack_selection(
    root: Path,
    selection: str,
    *,
    skip_builtins: bool,
) -> list[str]:
    """Resolve --packs all|core|comma-list into concrete pack names."""
    discovered = set(discover_source_packs(root, skip_builtins=skip_builtins))
    selection = selection.strip()

    if selection == "all":
        return sorted(discovered)

    if selection in GROUPS:
        return [name for name in GROUPS[selection] if name in discovered]

    names = [part.strip() for part in selection.split(",") if part.strip()]
    unknown = [name for name in names if name not in discovered]
    if unknown:
        raise SystemExit(
            f"Unknown or missing pack(s): {', '.join(unknown)}. "
            f"Discovered: {', '.join(sorted(discovered)) or '(none)'}"
        )
    return names


def _load_pack_metadata(root: Path, pack_name: str) -> dict[str, Any]:
    pack_dir = root / "data" / "source_packs" / pack_name
    for filename in ("pack.json", "manifest.json"):
        path = pack_dir / filename
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
    return {}


def select_lesson_topic(root: Path, pack_name: str) -> str:
    """Pick lesson topic from example_lessons, manifest, or first topics entry."""
    metadata = _load_pack_metadata(root, pack_name)
    example_lessons = metadata.get("example_lessons") or []
    if example_lessons:
        return str(example_lessons[0])

    manifest = root / "data" / "source_packs" / pack_name / "manifest.json"
    if manifest.is_file():
        try:
            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_lessons = manifest_data.get("example_lessons") or []
            if manifest_lessons:
                return str(manifest_lessons[0])
        except json.JSONDecodeError:
            pass

    topics = metadata.get("topics") or []
    if topics:
        return str(topics[0])

    title = metadata.get("title") or pack_name.replace("_", " ")
    return str(title)


def parse_json_output(output: str) -> dict[str, Any] | None:
    """Parse JSON emitted by sourcelab CLI commands."""
    text = output.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def _status_from_summary(summary: dict[str, Any] | None) -> str:
    if summary is None:
        return "error"
    total_failed = summary.get("total_failed")
    if total_failed is None:
        return "error"
    return "pass" if int(total_failed) == 0 else "fail"


def smoke_pack_row(
    root: Path,
    pack_name: str,
    *,
    difficulty: int,
    run_evals: bool,
    run_lessons: bool,
    dry_run: bool,
    command_runner: Callable[[list[str], Path], tuple[int, str]] = run_command,
) -> PackSmokeRow:
    """Run smoke checks for a single pack."""
    row = PackSmokeRow(pack_name=pack_name)

    doctor_cmd = ["sourcelab", "source-pack", "doctor", pack_name]
    if dry_run:
        row.warnings.append(f"dry-run: would run {' '.join(doctor_cmd)}")
        row.doctor_valid = True
        metadata = _load_pack_metadata(root, pack_name)
        row.source_count = len(metadata.get("sources") or [])
        row.eval_count = len(metadata.get("evals") or [])
        if run_evals:
            row.eval_status = "dry-run"
        if run_lessons:
            row.lesson_status = "dry-run"
            row.proof_status = "dry-run"
            row.harness_status = "dry-run"
        return row

    code, output = command_runner(doctor_cmd, root)
    doctor = parse_json_output(output)
    if doctor is None:
        row.errors.append("doctor: failed to parse JSON output")
        row.doctor_valid = False
    else:
        row.doctor_valid = bool(doctor.get("valid"))
        row.source_count = int(doctor.get("source_count") or 0)
        row.eval_count = int(doctor.get("eval_count") or 0)
        row.warnings.extend(str(w) for w in doctor.get("warnings") or [])
        if not row.doctor_valid:
            row.errors.extend(str(e) for e in doctor.get("errors") or [])
    if code != 0 and row.doctor_valid:
        row.errors.append(f"doctor exited with code {code}")

    if run_evals:
        eval_cmd = ["sourcelab", "evals", "run", "--pack", pack_name]
        eval_code, eval_output = command_runner(eval_cmd, root)
        eval_data = parse_json_output(eval_output)
        if eval_code != 0:
            row.eval_status = "error"
            row.errors.append(f"evals exited with code {eval_code}")
        elif eval_data is None:
            row.eval_status = "error"
            row.errors.append("evals: failed to parse JSON output")
        else:
            row.eval_status = _status_from_summary(eval_data.get("summary"))
            if row.eval_status == "fail":
                summary = eval_data.get("summary") or {}
                row.errors.append(
                    f"evals failed: {summary.get('total_failed', '?')} case(s) failed"
                )

    if run_lessons:
        topic = select_lesson_topic(root, pack_name)
        lesson_cmd = [
            "sourcelab",
            "lesson",
            "create",
            "--topic",
            topic,
            "--source-pack",
            pack_name,
            "--difficulty",
            str(difficulty),
        ]
        lesson_code, lesson_output = command_runner(lesson_cmd, root)
        lesson_data = parse_json_output(lesson_output)
        if lesson_code != 0:
            row.lesson_status = "error"
            row.errors.append(f"lesson create exited with code {lesson_code}")
        elif lesson_data is None:
            row.lesson_status = "error"
            row.errors.append("lesson create: failed to parse JSON output")
        elif lesson_data.get("error"):
            row.lesson_status = "error"
            row.errors.append(f"lesson create: {lesson_data['error']}")
        else:
            row.lesson_status = "pass"
            row.run_id = str(lesson_data.get("run_id") or "")

            if row.run_id:
                proof_cmd = ["sourcelab", "proof", "run", row.run_id]
                harness_cmd = ["sourcelab", "harness", "run", row.run_id]
            else:
                proof_cmd = ["sourcelab", "proof", "latest"]
                harness_cmd = ["sourcelab", "harness", "latest"]

            proof_code, proof_output = command_runner(proof_cmd, root)
            proof_data = parse_json_output(proof_output)
            if proof_code != 0 or proof_data is None or proof_data.get("error"):
                row.proof_status = "error"
                row.errors.append("proof: unavailable or failed")
            else:
                row.proof_status = "pass" if proof_data.get("artifact_count", 0) > 0 else "fail"

            harness_code, harness_output = command_runner(harness_cmd, root)
            harness_data = parse_json_output(harness_output)
            if harness_code != 0 or harness_data is None or harness_data.get("error"):
                row.harness_status = "error"
                row.errors.append("harness: unavailable or failed")
            else:
                passed = harness_data.get("passed")
                row.harness_status = "pass" if passed is True else "fail"
                if passed is not True:
                    row.errors.append("harness report did not pass")

    return row


def build_matrix_report(
    root: Path,
    pack_names: list[str],
    *,
    difficulty: int,
    run_evals: bool,
    run_lessons: bool,
    dry_run: bool,
    selection: str,
    skip_builtins: bool,
    command_runner: Callable[[list[str], Path], tuple[int, str]] = run_command,
) -> dict[str, Any]:
    """Run the smoke matrix and return the report payload."""
    rows: list[PackSmokeRow] = []
    for pack_name in pack_names:
        print(f"\n==> Smoke matrix: {pack_name}")
        row = smoke_pack_row(
            root,
            pack_name,
            difficulty=difficulty,
            run_evals=run_evals,
            run_lessons=run_lessons,
            dry_run=dry_run,
            command_runner=command_runner,
        )
        rows.append(row)
        status = "PASS" if not row.errors else "FAIL"
        print(f"    {status} doctor={row.doctor_valid} eval={row.eval_status} lesson={row.lesson_status}")

    failed = [row for row in rows if row.errors]
    return {
        "generated_at": now_iso(),
        "project_root": str(root),
        "selection": selection,
        "skip_builtins": skip_builtins,
        "dry_run": dry_run,
        "run_evals": run_evals,
        "run_lessons": run_lessons,
        "difficulty": difficulty,
        "pack_count": len(rows),
        "passed_count": len(rows) - len(failed),
        "failed_count": len(failed),
        "packs": [asdict(row) for row in rows],
    }


def render_matrix_markdown(report: dict[str, Any]) -> str:
    """Render markdown summary for the smoke matrix."""
    lines = [
        "# Source Pack Smoke Matrix",
        "",
        f"- Generated at: `{report.get('generated_at')}`",
        f"- Project root: `{report.get('project_root')}`",
        f"- Selection: `{report.get('selection')}`",
        f"- Skip builtins: `{report.get('skip_builtins')}`",
        f"- Dry run: `{report.get('dry_run')}`",
        f"- Run evals: `{report.get('run_evals')}`",
        f"- Run lessons: `{report.get('run_lessons')}`",
        f"- Difficulty: `{report.get('difficulty')}`",
        f"- Packs: `{report.get('pack_count')}`",
        f"- Passed: `{report.get('passed_count')}`",
        f"- Failed: `{report.get('failed_count')}`",
        "",
        "| Pack | Doctor | Sources | Evals | Eval Status | Lesson Status | Run ID | Proof | Harness | Errors |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for pack in report.get("packs") or []:
        errors = "; ".join(pack.get("errors") or []) or "—"
        lines.append(
            "| {pack_name} | {doctor} | {sources} | {evals} | {eval_status} | {lesson_status} | "
            "{run_id} | {proof} | {harness} | {errors} |".format(
                pack_name=pack.get("pack_name", ""),
                doctor="yes" if pack.get("doctor_valid") else "no",
                sources=pack.get("source_count", 0),
                evals=pack.get("eval_count", 0),
                eval_status=pack.get("eval_status", ""),
                lesson_status=pack.get("lesson_status", ""),
                run_id=pack.get("run_id") or "—",
                proof=pack.get("proof_status", ""),
                harness=pack.get("harness_status", ""),
                errors=errors.replace("|", "\\|"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def write_matrix_reports(root: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    """Write JSON and markdown smoke matrix artifacts."""
    artifacts_dir = root / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    json_path = artifacts_dir / JSON_REPORT
    md_path = artifacts_dir / MD_REPORT
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_matrix_markdown(report), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Source Pack Smoke Matrix v1.")
    parser.add_argument(
        "--packs",
        default="core",
        help="Pack group or comma-separated packs. Groups: core, research, business, watchlist, all.",
    )
    parser.add_argument("--difficulty", type=int, default=2, help="Lesson difficulty (default: 2).")
    parser.add_argument("--run-lessons", action="store_true", help="Run sourcelab lesson create per pack.")
    parser.add_argument("--run-evals", action="store_true", help="Run sourcelab evals run per pack.")
    parser.add_argument(
        "--skip-builtins",
        action="store_true",
        help="Skip pqc_v1 and ai_safety_v1 when discovering packs.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on the first pack failure instead of continuing.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan commands without executing sourcelab.")
    args = parser.parse_args()

    root = find_project_root(Path.cwd())
    pack_names = resolve_pack_selection(root, args.packs, skip_builtins=args.skip_builtins)

    print(f"SourceLab root: {root}")
    print(f"Smoke matrix packs ({len(pack_names)}): {', '.join(pack_names) or '(none)'}")

    if not pack_names:
        print("No packs selected.", file=sys.stderr)
        return 1

    exit_code = 0
    rows: list[PackSmokeRow] = []
    for pack_name in pack_names:
        row = smoke_pack_row(
            root,
            pack_name,
            difficulty=args.difficulty,
            run_evals=args.run_evals,
            run_lessons=args.run_lessons,
            dry_run=args.dry_run,
        )
        rows.append(row)
        print(f"\n==> {pack_name}: {'PASS' if not row.errors else 'FAIL'}")
        if row.errors:
            for error in row.errors:
                print(f"    ERROR: {error}", file=sys.stderr)
            exit_code = 1
            if args.strict:
                break

    report = {
        "generated_at": now_iso(),
        "project_root": str(root),
        "selection": args.packs,
        "skip_builtins": args.skip_builtins,
        "dry_run": args.dry_run,
        "run_evals": args.run_evals,
        "run_lessons": args.run_lessons,
        "difficulty": args.difficulty,
        "pack_count": len(rows),
        "passed_count": sum(1 for row in rows if not row.errors),
        "failed_count": sum(1 for row in rows if row.errors),
        "packs": [asdict(row) for row in rows],
    }

    if not args.dry_run:
        json_path, md_path = write_matrix_reports(root, report)
        print(f"\nReport written: {json_path}")
        print(f"Report written: {md_path}")
    else:
        print("\nDry run complete. No report artifacts written.")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
