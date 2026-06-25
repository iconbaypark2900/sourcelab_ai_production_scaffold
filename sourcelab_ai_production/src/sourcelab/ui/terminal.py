"""Terminal run explorer for SourceLab CLI.

Instruction:
- Print a terminal-friendly summary of a SourceLab run.
- Used by the `sourcelab runs show` CLI command.
- No external dependencies; prints plain text to stdout.
"""

from __future__ import annotations

from pathlib import Path

from sourcelab.ui.run_loader import RunSummary, summarize_run


def _format_score(score: float | None) -> str:
    """Format a score for terminal display."""
    return f"{score:.2f}" if score is not None else "N/A"


def _is_score_capped(summary: RunSummary) -> bool:
    """Return True when the final score was capped below the uncapped score."""
    if summary.cap_reason:
        return True
    if summary.answer_score is None or summary.uncapped_score is None:
        return False
    return summary.uncapped_score > summary.answer_score + 1e-6


def print_run_summary(summary: RunSummary) -> None:
    """Print a terminal-friendly run summary."""
    print("SourceLab Run Explorer")
    print("=" * 40)
    print(f"Run:             {summary.run_id}")
    print(f"Topic:           {summary.topic or '(not set)'}")
    print(f"Created:         {summary.created_at or '(unknown)'}")
    print()

    # Status line
    harness_str = "PASS" if summary.harness_passed is True else (
        "FAIL" if summary.harness_passed is False else "UNKNOWN"
    )
    proof_str = summary.proof_bundle_status or "UNKNOWN"
    print(f"Harness:         {harness_str}")
    print(f"Proof Bundle:    {proof_str}")

    # Scores
    if summary.has_answer or summary.answer_score is not None:
        print(f"Answer score:    {_format_score(summary.answer_score)}")
        if _is_score_capped(summary):
            print(f"Uncapped score:  {_format_score(summary.uncapped_score)}")
            if summary.cap_reason:
                print(f"Cap reason:      {summary.cap_reason}")
            if summary.needs_review is not None:
                print(f"Needs review:    {'Yes' if summary.needs_review else 'No'}")
    else:
        print("Answer score:    N/A")

    if summary.citation_resolution_rate is not None:
        print(f"Citation resolution: {summary.citation_resolution_rate:.2f}")
    else:
        print("Citation resolution: (not available)")

    # Flags
    print(f"Unsupported high-risk claims: {summary.unsupported_high_risk_claims}")
    print(f"Human review items: {summary.human_review_count}")
    print(f"Artifacts:       {summary.artifact_count}")

    # Next task
    if summary.next_task_focus:
        print(f"Next task:       {summary.next_task_focus}")

    print("=" * 40)


def print_run_list(summaries: list[RunSummary]) -> None:
    """Print a terminal-friendly list of runs."""
    if not summaries:
        print("No runs found.")
        return

    print(f"{'Run ID':<28} {'Topic':<40} {'Harness':<10} {'Score':<8} {'Artifacts':<10}")
    print("-" * 96)
    for s in summaries:
        harness_str = "PASS" if s.harness_passed is True else (
            "FAIL" if s.harness_passed is False else "UNKNOWN"
        )
        score_str = _format_score(s.answer_score) if (s.has_answer or s.answer_score is not None) else "-"
        topic_short = (s.topic[:37] + "...") if len(s.topic) > 40 else s.topic
        print(f"{s.run_id:<28} {topic_short:<40} {harness_str:<10} {score_str:<8} {s.artifact_count:<10}")

    print(f"\nTotal: {len(summaries)} run(s)")
