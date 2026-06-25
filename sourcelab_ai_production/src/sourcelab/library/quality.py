"""Score silver source cards for library quality."""

from __future__ import annotations

from pathlib import Path

from sourcelab.library.dedupe import build_dedupe_report
from sourcelab.library.io import save_model, utc_now
from sourcelab.library.normalize import load_source_cards, normalize_library, save_source_card
from sourcelab.library.paths import ensure_library_layout, library_root
from sourcelab.library.schemas import LibraryBuildReport, SourceQualityEntry, SourceQualityReport


TRUST_SCORES = {"A": 1.0, "B": 0.85, "C": 0.7, "D": 0.5, "E": 0.3}


def score_source_card(card) -> SourceQualityEntry:
    factors: dict[str, float] = {}
    notes: list[str] = []

    title_score = 1.0 if len(card.title.strip()) >= 8 else 0.4
    factors["title"] = title_score
    if title_score < 1.0:
        notes.append("short_title")

    summary_score = min(1.0, len(card.summary.strip()) / 120.0)
    factors["summary"] = round(summary_score, 4)
    if summary_score < 0.5:
        notes.append("thin_summary")

    terms_score = min(1.0, len(card.key_terms) / 6.0)
    factors["key_terms"] = round(terms_score, 4)

    chunk_score = min(1.0, len(card.chunk_paths) / 2.0)
    factors["chunks"] = round(chunk_score, 4)
    if not card.chunk_paths:
        notes.append("no_chunks")

    trust_score = TRUST_SCORES.get(card.trust_tier, 0.5)
    factors["trust_tier"] = trust_score

    metadata_score = 0.5
    if card.url:
        metadata_score += 0.2
    if card.authors:
        metadata_score += 0.15
    if card.published_at:
        metadata_score += 0.15
    factors["metadata"] = round(min(1.0, metadata_score), 4)

    quality_score = round(
        sum(factors.values()) / max(len(factors), 1),
        4,
    )

    return SourceQualityEntry(
        source_id=card.source_id,
        quality_score=quality_score,
        factors=factors,
        notes=notes,
    )


def quality_library(project_root: Path) -> LibraryBuildReport:
    """Score all silver source cards and write quality report."""
    ensure_library_layout(project_root)
    cards = load_source_cards(project_root)
    if not cards:
        normalize_library(project_root)
        cards = load_source_cards(project_root)

    dedupe_report = build_dedupe_report(cards)
    duplicate_ids = {dup for cluster in dedupe_report.duplicate_clusters for dup in cluster.duplicate_source_ids}

    entries: list[SourceQualityEntry] = []
    for card in cards:
        entry = score_source_card(card)
        if card.source_id in duplicate_ids:
            entry.quality_score = round(entry.quality_score * 0.5, 4)
            entry.notes.append("duplicate")
        card.quality_score = entry.quality_score
        save_source_card(project_root, card)
        entries.append(entry)

    average = round(sum(entry.quality_score for entry in entries) / max(len(entries), 1), 4)
    report = SourceQualityReport(
        generated_at=utc_now(),
        total_sources=len(entries),
        average_score=average,
        entries=entries,
    )
    save_model(library_root(project_root) / "silver" / "quality" / "source_quality_report.json", report)
    return LibraryBuildReport(
        generated_at=report.generated_at,
        stage="quality",
        status="ok",
        message=f"Scored {report.total_sources} sources (avg={average})",
        counts={"sources_scored": report.total_sources},
    )
