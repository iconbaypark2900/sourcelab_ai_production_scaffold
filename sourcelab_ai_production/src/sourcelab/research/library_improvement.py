"""Library improvement metrics before/after expansion execution."""

from __future__ import annotations

from pathlib import Path

from sourcelab.library.io import utc_now
from sourcelab.library.normalize import load_source_cards
from sourcelab.library.paths import ensure_library_layout, library_root
from sourcelab.library.stats import library_stats
from sourcelab.research.schemas import LibraryExpansionExecution, LibraryImprovementReport


def snapshot_library_metrics(project_root: Path) -> dict[str, int | float]:
    """Capture library counts and average quality at a point in time."""
    ensure_library_layout(project_root)
    stats = library_stats(project_root)
    lib_root = library_root(project_root)
    promotion_candidates = len(list((lib_root / "promotion" / "candidates").rglob("*.md")))

    return {
        "raw_sources": int(stats["raw"]["total_records"]),
        "source_cards": int(stats["silver"]["source_cards"]),
        "chunks": int(stats["silver"]["chunks"]),
        "quality": float(stats["silver"]["quality"]["average_score"] or 0.0),
        "promotion_candidates": promotion_candidates,
    }


def build_library_improvement_report(
    run_id: str,
    topic: str,
    source_pack: str,
    before: dict[str, int | float],
    after: dict[str, int | float],
    execution: LibraryExpansionExecution,
) -> LibraryImprovementReport:
    """Compute before/after library improvement metrics."""
    cards_before = int(before.get("source_cards", 0))
    cards_after = int(after.get("source_cards", 0))
    chunks_before = int(before.get("chunks", 0))
    chunks_after = int(after.get("chunks", 0))

    executed_names = sorted(
        {
            entry.collector
            for entry in execution.executed_collectors
            if entry.status == "executed"
        }
    )
    manual_names = sorted({entry.collector for entry in execution.manual_collectors})

    return LibraryImprovementReport(
        run_id=run_id,
        topic=topic,
        source_pack=source_pack,
        generated_at=utc_now(),
        raw_sources_before=int(before.get("raw_sources", 0)),
        raw_sources_after=int(after.get("raw_sources", 0)),
        source_cards_before=cards_before,
        source_cards_after=cards_after,
        chunks_before=chunks_before,
        chunks_after=chunks_after,
        new_source_cards=max(0, cards_after - cards_before),
        new_chunks=max(0, chunks_after - chunks_before),
        quality_before=float(before.get("quality", 0.0)),
        quality_after=float(after.get("quality", 0.0)),
        promotion_candidates_before=int(before.get("promotion_candidates", 0)),
        promotion_candidates_after=int(after.get("promotion_candidates", 0)),
        executed_collectors=executed_names,
        manual_collectors=manual_names,
        errors=list(execution.errors),
    )


def render_library_improvement_markdown(report: LibraryImprovementReport) -> str:
    """Render a human-readable library improvement report."""
    lines = [
        f"# Library Improvement Report — {report.topic}",
        "",
        f"- **Run:** `{report.run_id}`",
        f"- **Source pack:** `{report.source_pack}`",
        f"- **Generated:** {report.generated_at.isoformat()}",
        "",
        "## Library counts",
        "",
        f"- Raw sources: {report.raw_sources_before} → {report.raw_sources_after}",
        f"- Source cards: {report.source_cards_before} → {report.source_cards_after} (+{report.new_source_cards})",
        f"- Chunks: {report.chunks_before} → {report.chunks_after} (+{report.new_chunks})",
        f"- Avg quality: {report.quality_before:.3f} → {report.quality_after:.3f}",
        f"- Promotion candidates: {report.promotion_candidates_before} → {report.promotion_candidates_after}",
        "",
        "## Collectors",
        "",
    ]
    if report.executed_collectors:
        lines.append(f"- Executed: {', '.join(report.executed_collectors)}")
    else:
        lines.append("- Executed: _(none)_")
    if report.manual_collectors:
        lines.append(f"- Manual: {', '.join(report.manual_collectors)}")
    if report.errors:
        lines.extend(["", "## Errors", ""])
        for error in report.errors:
            lines.append(f"- {error}")
    lines.append("")
    return "\n".join(lines)


def write_library_improvement_report(run_dir: Path, report: LibraryImprovementReport) -> None:
    """Write library_improvement_report.json and .md."""
    (run_dir / "library_improvement_report.json").write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (run_dir / "library_improvement_report.md").write_text(
        render_library_improvement_markdown(report),
        encoding="utf-8",
    )


def list_new_source_card_ids(project_root: Path, card_ids_before: set[str]) -> list[str]:
    """Return source card IDs added since a prior snapshot."""
    cards = load_source_cards(project_root)
    return sorted(card.source_id for card in cards if card.source_id not in card_ids_before)
