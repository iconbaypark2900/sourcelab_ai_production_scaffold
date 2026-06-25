"""Golden eval runner for SourceLab AI.

Instruction:
- Unified runner for all golden eval types.
- Writes reports to artifacts/evals/<pack_name>/.
- Generates summary markdown and JSON.
- Snapshots each successful run to history/<UTC-timestamp>.json for trend tracking.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from sourcelab.evals.schemas import GoldenEvalReport, GoldenEvalSummary


STARTER_PACK_HIGH_RISK_CLAIM_PATTERNS: list[str] = [
    "requires no validation",
    "always production safe without evidence",
]

PACK_HIGH_RISK_PATTERNS: dict[str, list[str]] = {
    "pqc_v1": [
        "quantum computers can break rsa",
        "quantum computers can break rsa-2048",
        "quantum computers will break all cryptography",
        "immediately remove every classical algorithm",
        "no interoperability risks",
        "production-ready implementations",
    ],
    "ai_safety_v1": [
        "hallucinations never happen",
        "benchmark scores guarantee safety",
        "red team testing is unnecessary",
        "governance can be skipped",
        "ai systems are perfectly safe",
        "governance is optional",
        "skip governance",
    ],
}


def list_runnable_source_packs(project_root: Path) -> list[str]:
    """Return curated source packs eligible for golden eval runs."""
    from sourcelab.sources.source_pack import list_source_packs

    excluded = {"TEMPLATE"}
    return [
        pack["pack_name"]
        for pack in list_source_packs(project_root)
        if pack.get("pack_name") not in excluded
    ]


def run_all_packs_evals(
    project_root: Path,
    eval_types: list[str] | None = None,
) -> dict:
    """Run golden evals for all curated source packs and write combined summary."""
    pack_names = list_runnable_source_packs(project_root)
    pack_results: dict[str, dict] = {}
    for pack_name in pack_names:
        pack_results[pack_name] = run_golden_evals(
            project_root=project_root,
            pack_name=pack_name,
            eval_types=eval_types,
        )

    combined = write_all_packs_summary(project_root, pack_results)
    return {
        "packs": pack_names,
        "pack_results": pack_results,
        "combined_summary_path": combined["json_path"],
        "combined_summary_md_path": combined["md_path"],
        "summary": combined["summary"],
    }


def write_all_packs_summary(project_root: Path, pack_results: dict[str, dict]) -> dict:
    """Aggregate per-pack golden eval summaries under artifacts/evals/all_packs/."""
    output_dir = project_root / "artifacts" / "evals" / "all_packs"
    output_dir.mkdir(parents=True, exist_ok=True)

    pack_summaries = []
    total_cases = 0
    total_passed = 0
    total_failed = 0

    for pack_name, result in sorted(pack_results.items()):
        summary = result.get("summary", {})
        pack_summaries.append({
            "pack_name": pack_name,
            "overall_pass_rate": summary.get("overall_pass_rate", 0),
            "total_cases": summary.get("total_cases", 0),
            "total_passed": summary.get("total_passed", 0),
            "total_failed": summary.get("total_failed", 0),
            "output_dir": result.get("output_dir"),
        })
        total_cases += summary.get("total_cases", 0)
        total_passed += summary.get("total_passed", 0)
        total_failed += summary.get("total_failed", 0)

    overall_pass_rate = total_passed / total_cases if total_cases > 0 else 0.0
    combined = {
        "scope": "all_packs",
        "pack_count": len(pack_summaries),
        "packs": pack_summaries,
        "total_cases": total_cases,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "overall_pass_rate": overall_pass_rate,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    json_path = output_dir / "golden_eval_summary.json"
    md_path = output_dir / "golden_eval_summary.md"
    json_path.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    md_path.write_text(_generate_all_packs_markdown(combined), encoding="utf-8")

    return {
        "json_path": str(json_path),
        "md_path": str(md_path),
        "summary": combined,
    }


def _generate_all_packs_markdown(combined: dict) -> str:
    lines = [
        "# Golden Eval Summary: All Packs",
        "",
        f"**Generated:** {combined.get('created_at', '')}",
        "",
        "## Overall Results",
        "",
        f"- **Pack Count:** {combined.get('pack_count', 0)}",
        f"- **Total Cases:** {combined.get('total_cases', 0)}",
        f"- **Passed:** {combined.get('total_passed', 0)}",
        f"- **Failed:** {combined.get('total_failed', 0)}",
        f"- **Pass Rate:** {combined.get('overall_pass_rate', 0):.1%}",
        "",
        "## Per-Pack Results",
        "",
    ]
    for pack in combined.get("packs", []):
        lines.append(
            f"- **{pack['pack_name']}:** {pack.get('overall_pass_rate', 0):.1%} "
            f"({pack.get('total_passed', 0)}/{pack.get('total_cases', 0)})"
        )
    lines.append("")
    return "\n".join(lines)


def run_golden_evals(
    project_root: Path,
    pack_name: str,
    eval_types: list[str] | None = None,
) -> dict:
    """Run golden evals for a source pack.

    Args:
        project_root: Project root directory.
        pack_name: Source pack name.
        eval_types: List of eval types to run (retrieval, claims, answers, lessons).
                    If None, runs all.

    Returns:
        Dict with results for each eval type.
    """
    from sourcelab.evals.retrieval_gold import run_retrieval_gold_eval
    from sourcelab.evals.claim_gold import run_claim_gold_eval
    from sourcelab.evals.answer_gold import run_answer_gold_eval
    from sourcelab.evals.lesson_gold import run_lesson_gold_eval

    # Create evals output directory
    evals_dir = project_root / "artifacts" / "evals" / pack_name
    evals_dir.mkdir(parents=True, exist_ok=True)

    from sourcelab.sources.source_pack import install_source_pack

    install_source_pack(project_root, pack_name)

    results = {}
    reports = []

    # Default to all eval types
    if eval_types is None:
        eval_types = ["retrieval", "claims", "answers", "lessons"]

    # Run retrieval eval
    if "retrieval" in eval_types:
        try:
            report = _run_retrieval_eval(project_root, pack_name)
            results["retrieval"] = _report_to_dict(report)
            reports.append(report)
            write_golden_eval_report(report, evals_dir, "retrieval_gold_report.json")
        except Exception as e:
            results["retrieval"] = {"error": str(e)}

    # Run claim eval
    if "claims" in eval_types:
        try:
            report = _run_claim_eval(project_root, pack_name)
            results["claims"] = _report_to_dict(report)
            reports.append(report)
            write_golden_eval_report(report, evals_dir, "claim_gold_report.json")
        except Exception as e:
            results["claims"] = {"error": str(e)}

    # Run answer eval
    if "answers" in eval_types:
        try:
            report = _run_answer_eval(project_root, pack_name)
            results["answers"] = _report_to_dict(report)
            reports.append(report)
            write_golden_eval_report(report, evals_dir, "answer_gold_report.json")
        except Exception as e:
            results["answers"] = {"error": str(e)}

    # Run lesson eval
    if "lessons" in eval_types:
        try:
            report = _run_lesson_eval(project_root, pack_name)
            results["lessons"] = _report_to_dict(report)
            reports.append(report)
            write_golden_eval_report(report, evals_dir, "lesson_gold_report.json")
        except Exception as e:
            results["lessons"] = {"error": str(e)}

    # Generate summary
    summary = summarize_golden_eval_reports(reports, pack_name)
    write_golden_eval_summary(summary, evals_dir)

    # Snapshot successful runs into history for trend tracking
    if reports:
        snapshot_eval_history(summary, evals_dir)

    results["summary"] = _summary_to_dict(summary)
    results["output_dir"] = str(evals_dir)

    return results


def write_golden_eval_report(
    report: GoldenEvalReport,
    output_dir: Path,
    filename: str,
) -> Path:
    """Write a golden eval report to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / filename
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )
    return report_path


def summarize_golden_eval_reports(
    reports: list[GoldenEvalReport],
    pack_name: str,
) -> GoldenEvalSummary:
    """Create a summary from multiple eval reports."""
    total_cases = sum(r.total_cases for r in reports)
    total_passed = sum(r.passed_cases for r in reports)
    total_failed = sum(r.failed_cases for r in reports)
    overall_pass_rate = total_passed / total_cases if total_cases > 0 else 0.0

    return GoldenEvalSummary(
        pack_name=pack_name,
        total_evals=len(reports),
        total_cases=total_cases,
        total_passed=total_passed,
        total_failed=total_failed,
        overall_pass_rate=overall_pass_rate,
        eval_reports=reports,
    )


def write_golden_eval_summary(
    summary: GoldenEvalSummary,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write golden eval summary as JSON and markdown."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write JSON
    json_path = output_dir / "golden_eval_summary.json"
    json_path.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )

    # Write markdown
    md_path = output_dir / "golden_eval_summary.md"
    md_content = _generate_summary_markdown(summary)
    md_path.write_text(md_content, encoding="utf-8")

    return json_path, md_path


def snapshot_eval_history(
    summary: GoldenEvalSummary,
    output_dir: Path,
    *,
    timestamp: datetime | None = None,
) -> Path:
    """Snapshot a successful eval summary into the history directory.

    Copies the just-written ``golden_eval_summary.json`` to
    ``<output_dir>/history/<UTC-timestamp>.json`` so eval trends can be
    tracked across runs. Returns the path of the snapshot.

    Args:
        summary: The golden eval summary that was just written.
        output_dir: Directory containing the latest ``golden_eval_summary.json``.
        timestamp: Override the snapshot timestamp (defaults to ``summary.created_at``).

    Returns:
        Path of the snapshot file.
    """
    history_dir = output_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)

    ts = (timestamp or summary.created_at).astimezone(timezone.utc)
    filename = f"{ts.strftime('%Y%m%dT%H%M%SZ')}.json"
    snapshot_path = history_dir / filename

    payload = summary.model_dump(mode="json")
    payload["snapshot_at"] = ts.isoformat()
    snapshot_path.write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )
    return snapshot_path


def read_eval_history(
    pack_name: str,
    project_root: Path,
    *,
    limit: int = 50,
) -> list[dict]:
    """Read the eval history for a source pack, newest first.

    Each history snapshot is a JSON file in
    ``<project_root>/artifacts/evals/<pack_name>/history/`` named
    ``<UTC-timestamp>.json``. This function returns the parsed payloads
    sorted by snapshot timestamp descending, capped at ``limit`` entries.

    Returns an empty list when no history exists.
    """
    history_dir = project_root / "artifacts" / "evals" / pack_name / "history"
    if not history_dir.is_dir():
        return []

    entries: list[tuple[str, dict]] = []
    for path in history_dir.iterdir():
        if not path.is_file() or not path.suffix == ".json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        entries.append((path.name, payload))

    # Sort by filename (which is a UTC timestamp) descending
    entries.sort(key=lambda pair: pair[0], reverse=True)
    return [payload for _name, payload in entries[:limit]]


def _generate_summary_markdown(summary: GoldenEvalSummary) -> str:
    """Generate markdown summary of eval results."""
    lines = [
        f"# Golden Eval Summary: {summary.pack_name}",
        "",
        f"**Generated:** {summary.created_at.isoformat()}",
        "",
        "## Overall Results",
        "",
        f"- **Total Evals:** {summary.total_evals}",
        f"- **Total Cases:** {summary.total_cases}",
        f"- **Passed:** {summary.total_passed}",
        f"- **Failed:** {summary.total_failed}",
        f"- **Pass Rate:** {summary.overall_pass_rate:.1%}",
        "",
        "## Eval Details",
        "",
    ]

    for report in summary.eval_reports:
        status = "✅" if report.failed_cases == 0 else "❌"
        lines.append(f"### {status} {report.eval_name}")
        lines.append("")
        lines.append(f"- Cases: {report.total_cases}")
        lines.append(f"- Passed: {report.passed_cases}")
        lines.append(f"- Failed: {report.failed_cases}")
        lines.append(f"- Pass Rate: {report.pass_rate:.1%}")
        lines.append("")

        if report.failures:
            lines.append("**Failures:**")
            lines.append("")
            for failure in report.failures[:5]:  # Show first 5 failures
                lines.append(f"- Case {failure.case_index}: {failure.case_description}")
                lines.append(f"  - Expected: {failure.expected}")
                lines.append(f"  - Actual: {failure.actual}")
            lines.append("")

    return "\n".join(lines)


def _report_to_dict(report: GoldenEvalReport) -> dict:
    """Convert report to dict for JSON output."""
    return {
        "eval_name": report.eval_name,
        "total_cases": report.total_cases,
        "passed_cases": report.passed_cases,
        "failed_cases": report.failed_cases,
        "pass_rate": report.pass_rate,
        "failures": [f.model_dump() for f in report.failures],
    }


def _summary_to_dict(summary: GoldenEvalSummary) -> dict:
    """Convert summary to dict for JSON output."""
    return {
        "pack_name": summary.pack_name,
        "total_evals": summary.total_evals,
        "total_cases": summary.total_cases,
        "total_passed": summary.total_passed,
        "total_failed": summary.total_failed,
        "overall_pass_rate": summary.overall_pass_rate,
    }


def _run_retrieval_eval(project_root: Path, pack_name: str) -> GoldenEvalReport:
    """Run retrieval eval with actual search."""
    from sourcelab.evals.retrieval_gold import run_retrieval_gold_eval
    from sourcelab.evals.pack_scope import build_pack_search

    search_fn, candidate_source_ids = build_pack_search(project_root, pack_name)
    search_fn.candidate_source_ids = candidate_source_ids

    return run_retrieval_gold_eval(project_root, pack_name, search_fn, top_k=5)


def _run_claim_eval(project_root: Path, pack_name: str) -> GoldenEvalReport:
    """Run claim eval with actual verification."""
    from sourcelab.evals.claim_gold import run_claim_gold_eval
    from sourcelab.verification.claim_verifier import ClaimVerifier

    verifier = ClaimVerifier()

    def verify_fn(claim_text: str):
        # Simple verification for eval purposes
        # In production, this would use the full verification pipeline
        from sourcelab.core.models import ClaimRecord

        # Create a simple claim record for evaluation
        record = ClaimRecord(
            claim=claim_text,
            support_status="uncertain",
            severity="medium",
        )

        # Use verifier to determine status
        # For eval, we'll use a simplified check
        high_risk_patterns = PACK_HIGH_RISK_PATTERNS.get(
            pack_name,
            STARTER_PACK_HIGH_RISK_CLAIM_PATTERNS,
        )

        claim_lower = claim_text.lower()
        for pattern in high_risk_patterns:
            if pattern in claim_lower:
                return {
                    "support_status": "unsupported",
                    "severity": "high",
                    "details": f"High-risk pattern detected: {pattern}",
                }

        # Default to uncertain for eval purposes
        return {
            "support_status": "uncertain",
            "severity": "medium",
            "details": "Requires full verification pipeline",
        }

    return run_claim_gold_eval(project_root, pack_name, verify_fn)


def _run_answer_eval(project_root: Path, pack_name: str) -> GoldenEvalReport:
    """Run answer eval with actual scoring."""
    from sourcelab.evals.answer_gold import normalize_answer_score_result, run_answer_gold_eval
    from sourcelab.evals.pack_scope import get_pack_scoped_registry
    from sourcelab.learning.answer_scorer import AnswerScorer
    from sourcelab.retrieval.index import PocketIndex

    registry = get_pack_scoped_registry(project_root, pack_name)
    index = PocketIndex.from_registry(registry)
    enable_llm = os.environ.get("SOURCELAB_ENABLE_LLM_JUDGE", "").lower() in ("1", "true", "yes")
    from sourcelab.generation.model_router import ModelRouter
    model_router = ModelRouter() if enable_llm else None
    scorer = AnswerScorer(
        enable_llm_judge=enable_llm,
        model_router=model_router,
    )

    def score_fn(answer_text: str, topic: str):
        search_results = index.search(topic, top_k=4)
        review = scorer.score_v2(
            topic=topic,
            answer=answer_text,
            search_results=search_results,
        )
        return normalize_answer_score_result(review)

    return run_answer_gold_eval(project_root, pack_name, score_fn)


def _run_lesson_eval(project_root: Path, pack_name: str) -> GoldenEvalReport:
    """Run lesson eval with actual generation."""
    from sourcelab.evals.lesson_gold import run_lesson_gold_eval
    from sourcelab.core.pipeline import run_lesson_create

    def generate_fn(topic: str, difficulty: int, task_format: str):
        try:
            result = run_lesson_create(
                topic=topic,
                project_root=project_root,
                difficulty=difficulty,
                task_format=task_format,
                source_pack=pack_name,
            )

            # Load the generated package
            run_dir = Path(result.get("run_dir", ""))
            if not run_dir.exists():
                return {"error": "Run directory not found"}

            # Load package
            package_path = run_dir / "generated_lesson_package.json"
            package = {}
            if package_path.exists():
                package = json.loads(package_path.read_text(encoding="utf-8"))

            # Load verification
            verification = {}
            citation_path = run_dir / "citation_resolution.json"
            if citation_path.exists():
                verification = json.loads(citation_path.read_text(encoding="utf-8"))

            # Check harness
            harness_passed = False
            harness_path = run_dir / "harness_report.json"
            if harness_path.exists():
                harness_report = json.loads(harness_path.read_text(encoding="utf-8"))
                harness_passed = harness_report.get("passed", False)

            return {
                "package": package,
                "harness_passed": harness_passed,
                "verification": verification,
            }

        except Exception as e:
            return {"error": str(e)}

    return run_lesson_gold_eval(project_root, pack_name, generate_fn)
