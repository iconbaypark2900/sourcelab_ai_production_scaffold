"""Markdown and HTML export for SourceLab runs.

Instruction:
- Export a readable report for a SourceLab run in markdown or HTML format.
- Reports include overview, lesson, grounding, harness, learning, and artifact inventory.
- Export works without Streamlit installed.
- Outputs are written to artifacts/exports/.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sourcelab.ui.run_loader import (
    RunSummary,
    load_json_artifact,
    load_markdown_artifact,
    load_artifact_inventory,
    summarize_run,
)


def generate_markdown_report(run_dir: Path) -> str:
    """Generate a full markdown report for a run."""
    summary = summarize_run(run_dir)
    lines = []

    # Header
    lines.append(f"# SourceLab Run Report: {summary.run_id}")
    lines.append("")
    lines.append(f"**Topic:** {summary.topic or '(not set)'}")
    lines.append(f"**Created:** {summary.created_at or '(unknown)'}")
    lines.append(f"**Run Directory:** `{summary.run_dir}`")
    lines.append("")

    # Overview
    lines.append("## Overview")
    lines.append("")
    harness_str = "PASS" if summary.harness_passed is True else (
        "FAIL" if summary.harness_passed is False else "UNKNOWN"
    )
    lines.append(f"- **Harness Status:** {harness_str}")
    lines.append(f"- **Proof Bundle Status:** {summary.proof_bundle_status or 'unknown'}")
    if summary.has_answer or summary.answer_score is not None:
        score_label = f"{summary.answer_score:.2f}" if summary.answer_score is not None else "N/A"
        lines.append(f"- **Answer Score:** {score_label}")
        if summary.rubric_alignment_score is not None:
            lines.append(f"- **Rubric Alignment Score:** {summary.rubric_alignment_score:.2f}")
        if summary.uncapped_score is not None:
            lines.append(f"- **Uncapped Score:** {summary.uncapped_score:.2f}")
        if summary.overall_score is not None:
            lines.append(f"- **Overall Score:** {summary.overall_score:.2f}")
        if summary.cap_reason:
            lines.append(f"- **Cap Reason:** {summary.cap_reason}")
        if summary.needs_review is not None:
            lines.append(f"- **Needs Review:** {'Yes' if summary.needs_review else 'No'}")
        if summary.human_review_reason:
            lines.append(f"- **Human Review Reason:** {summary.human_review_reason}")
        if summary.source_grounding_score is not None:
            lines.append(f"- **Source Grounding Score:** {summary.source_grounding_score:.2f}")
        if summary.concept_overlap_grounding_score is not None:
            lines.append(
                f"- **Concept Overlap Grounding Score:** {summary.concept_overlap_grounding_score:.2f}"
            )
    else:
        lines.append("- **Answer Score:** N/A (no answer submitted)")
    if summary.citation_resolution_rate is not None:
        lines.append(f"- **Citation Resolution Rate:** {summary.citation_resolution_rate:.2f}")
    lines.append(f"- **Unsupported High-Risk Claims:** {summary.unsupported_high_risk_claims}")
    lines.append(f"- **Human Review Items:** {summary.human_review_count}")
    lines.append(f"- **Artifact Count:** {summary.artifact_count}")
    lines.append("")

    # Generated lesson
    lesson_md = load_markdown_artifact(run_dir, "generated_lesson.md")
    if lesson_md:
        lines.append("## Generated Lesson")
        lines.append("")
        lines.append(lesson_md)
        lines.append("")

    # Grounding report
    grounding_md = load_markdown_artifact(run_dir, "grounding_report.md")
    if grounding_md:
        lines.append("## Grounding Report")
        lines.append("")
        lines.append(grounding_md)
        lines.append("")

    # Harness report
    harness_data = load_json_artifact(run_dir, "harness_report.json")
    if harness_data:
        lines.append("## Harness Report")
        lines.append("")
        lines.append(f"- **Passed:** {harness_data.get('passed', 'unknown')}")
        lines.append(f"- **Artifact Count:** {harness_data.get('artifact_count', 'unknown')}")
        blocking = harness_data.get("blocking_failures", [])
        if blocking:
            lines.append("- **Blocking Failures:**")
            for b in blocking:
                lines.append(f"  - {b}")
        warnings = harness_data.get("warnings", [])
        if warnings:
            lines.append("- **Warnings:**")
            for w in warnings:
                lines.append(f"  - {w}")
        lines.append("")

    # Learning report
    learning_md = load_markdown_artifact(run_dir, "learning_report.md")
    if learning_md:
        lines.append("## Learning Report")
        lines.append("")
        lines.append(learning_md)
        lines.append("")

    # Answer attempt history (summary only — no raw answer dump)
    from sourcelab.learning.answer_history import summarize_answer_history_for_export

    history_stats = summarize_answer_history_for_export(run_dir)
    if history_stats.get("total_attempts", 0) > 0:
        lines.append("## Answer Attempt History")
        lines.append("")
        lines.append(f"- **Total Attempts:** {history_stats['total_attempts']}")
        lines.append(f"- **Latest Score:** {history_stats['latest_score']:.2%}")
        lines.append(f"- **Best Score:** {history_stats['best_score']:.2%} ({history_stats['best_attempt_id']})")
        lines.append(f"- **Needs Review Count:** {history_stats['needs_review_count']}")
        if history_stats.get("latest_cap_reason"):
            lines.append(f"- **Latest Cap Reason:** {history_stats['latest_cap_reason']}")
        lines.append(f"- **Score Trend:** {history_stats['score_trend']}")
        scores = history_stats.get("scores", [])
        if len(scores) >= 2:
            trend_line = " → ".join(f"{s:.0%}" for s in scores)
            lines.append(f"- **Score Progression:** {trend_line}")
        lines.append("")

    # Next task decision
    next_task = load_json_artifact(run_dir, "next_task_decision.json")
    if next_task:
        lines.append("## Next Task Decision")
        lines.append("")
        lines.append(f"- **Format:** {next_task.get('format', 'unknown')}")
        lines.append(f"- **Difficulty:** {next_task.get('difficulty', 'unknown')}")
        lines.append(f"- **Focus Area:** {next_task.get('focus_area', 'unknown')}")
        lines.append(f"- **Reason:** {next_task.get('reason', 'unknown')}")
        lines.append("")

    # Source pack status
    source_pack = load_json_artifact(run_dir, "source_pack_status.json")
    if source_pack:
        lines.append("## Source Pack Status")
        lines.append("")
        lines.append(f"- **Pack Name:** {source_pack.get('pack_name', 'unknown')}")
        lines.append(f"- **Installed:** {source_pack.get('installed', False)}")
        lines.append(f"- **Source Count:** {source_pack.get('source_count', 0)}")
        lines.append(f"- **Manifest Version:** {source_pack.get('manifest_version', 'unknown')}")
        lines.append("")

    # Golden eval summary
    golden_eval = load_json_artifact(run_dir, "golden_eval_summary.json")
    if golden_eval:
        lines.append("## Golden Evaluation Summary")
        lines.append("")
        lines.append(f"- **Overall Pass Rate:** {golden_eval.get('overall_pass_rate', 0):.2%}")
        lines.append(f"- **Total Cases:** {golden_eval.get('total_cases', 0)}")
        lines.append(f"- **Passed:** {golden_eval.get('passed', 0)}")
        lines.append(f"- **Failed:** {golden_eval.get('failed', 0)}")
        if golden_eval.get("eval_results"):
            lines.append("- **Eval Results:**")
            for result in golden_eval["eval_results"]:
                status = "PASS" if result.get("passed") else "FAIL"
                lines.append(f"  - {result.get('eval_name', 'unknown')}: {status} ({result.get('pass_rate', 0):.2%})")
        lines.append("")

    # Proof bundle summary
    proof_summary = load_json_artifact(run_dir, "proof_summary.json")
    if proof_summary:
        lines.append("## Proof Bundle Summary")
        lines.append("")
        lines.append(f"- **Status:** {proof_summary.get('status', 'unknown')}")
        lines.append(f"- **Artifact Count:** {proof_summary.get('artifact_count', 0)}")
        lines.append(f"- **Total Size:** {proof_summary.get('total_size', 0):,} bytes")
        lines.append("")

    # Release status
    release_manifest = load_json_artifact(run_dir, "release_manifest.json")
    if release_manifest:
        lines.append("## Release Status")
        lines.append("")
        lines.append(f"- **Release Version:** {release_manifest.get('release_version', 'unknown')}")
        lines.append(f"- **Status:** {release_manifest.get('release_status', 'unknown')}")
        lines.append(f"- **Strict Verification:** {release_manifest.get('strict_verification_status', 'unknown')}")
        lines.append(f"- **Pytest Status:** {release_manifest.get('pytest_status', 'unknown')}")
        lines.append("")

    # Artifact inventory
    lines.append("## Artifact Inventory")
    lines.append("")
    inventory = load_artifact_inventory(run_dir)
    lines.append("| Name | Type | Required | Exists | Validated | Size |")
    lines.append("|------|------|----------|--------|-----------|------|")
    for row in inventory:
        size_str = f"{row.size:,}" if row.size else "-"
        exists_str = "Yes" if row.exists else "No"
        validated_str = "Yes" if row.validated else "No"
        required_str = "Yes" if row.required else "No"
        lines.append(f"| {row.name} | {row.artifact_type} | {required_str} | {exists_str} | {validated_str} | {size_str} |")
    lines.append("")

    return "\n".join(lines)


def generate_html_report(markdown_content: str) -> str:
    """Convert markdown report to a simple HTML page."""
    import re

    html = markdown_content

    # Escape HTML entities
    html = html.replace("&", "&amp;")
    html = html.replace("<", "&lt;")
    html = html.replace(">", "&gt;")

    # Convert markdown headers
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)

    # Convert bold
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)

    # Convert inline code
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)

    # Convert list items
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)

    # Convert tables
    lines = html.split("\n")
    new_lines = []
    in_table = False
    table_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(stripped)
        else:
            if in_table:
                new_lines.extend(_render_table(table_lines))
                in_table = False
                table_lines = []
            new_lines.append(line)
    if in_table:
        new_lines.extend(_render_table(table_lines))
    html = "\n".join(new_lines)

    # Wrap in HTML structure
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>SourceLab Run Report</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; line-height: 1.6; }}
        h1 {{ border-bottom: 2px solid #333; padding-bottom: 8px; }}
        h2 {{ border-bottom: 1px solid #ccc; padding-bottom: 4px; color: #333; }}
        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
        table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
        th {{ background: #f4f4f4; font-weight: 600; }}
        li {{ margin: 4px 0; }}
        strong {{ color: #1a1a1a; }}
    </style>
</head>
<body>
{html}
</body>
</html>"""
    return html


def _render_table(table_lines: list[str]) -> list[str]:
    """Render markdown table lines to HTML."""
    if len(table_lines) < 2:
        return table_lines

    result = ["<table>"]
    for i, line in enumerate(table_lines):
        cells = [c.strip() for c in line.strip("|").split("|")]
        if i == 0:
            result.append("<tr>")
            for cell in cells:
                result.append(f"<th>{cell}</th>")
            result.append("</tr>")
        elif i == 1:
            continue  # Skip separator row
        else:
            result.append("<tr>")
            for cell in cells:
                result.append(f"<td>{cell}</td>")
            result.append("</tr>")
    result.append("</table>")
    return result


def export_run(
    project_root: Path,
    run_id: str = "latest",
    fmt: str = "markdown",
) -> Path:
    """Export a run report. Returns the path to the exported file.

    Args:
        project_root: Project root directory.
        run_id: Run ID to export, or "latest".
        fmt: Export format, either "markdown" or "html".

    Returns:
        Path to the exported file.
    """
    runs_dir = project_root / "artifacts" / "runs"
    if not runs_dir.exists():
        raise FileNotFoundError("No runs directory found. Run 'sourcelab demo' first.")

    if run_id == "latest":
        run_dirs = sorted(
            [d for d in runs_dir.iterdir() if d.is_dir()],
            key=lambda p: p.name,
        )
        if not run_dirs:
            raise FileNotFoundError("No runs found. Run 'sourcelab demo' first.")
        run_dir = run_dirs[-1]
        run_id = run_dir.name
    else:
        run_dir = runs_dir / run_id
        if not run_dir.exists():
            raise FileNotFoundError(f"Run not found: {run_id}")

    # Generate markdown report
    md_content = generate_markdown_report(run_dir)

    # Ensure export directory exists
    export_dir = project_root / "artifacts" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    if fmt == "html":
        content = generate_html_report(md_content)
        ext = "html"
    else:
        content = md_content
        ext = "md"

    filename = f"report_{run_id}.{ext}"
    export_path = export_dir / filename
    export_path.write_text(content, encoding="utf-8")

    return export_path
