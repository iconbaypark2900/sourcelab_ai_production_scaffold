"""Library statistics aggregation."""

from __future__ import annotations

from pathlib import Path

from sourcelab.library.io import load_model, utc_now
from sourcelab.library.normalize import load_raw_records, load_source_cards
from sourcelab.library.paths import ensure_library_layout, library_root
from sourcelab.library.schemas import DedupeReport, LibraryManifest, SourceQualityReport


def library_stats(project_root: Path) -> dict:
    """Aggregate bronze/silver/gold library statistics."""
    ensure_library_layout(project_root)
    lib_root = library_root(project_root)

    raw_counts: dict[str, int] = {}
    raw_root = lib_root / "raw"
    for origin_dir in sorted(raw_root.iterdir()) if raw_root.exists() else []:
        if origin_dir.is_dir():
            raw_counts[origin_dir.name] = len(list(origin_dir.glob("*.json")))

    cards = load_source_cards(project_root)
    chunks_dir = lib_root / "silver" / "chunks"
    chunk_count = len(list(chunks_dir.glob("*.json"))) if chunks_dir.exists() else 0

    manifest_path = lib_root / "silver" / "manifests" / "library_manifest.json"
    manifest = None
    if manifest_path.exists():
        manifest = load_model(manifest_path, LibraryManifest)

    dedupe_path = lib_root / "silver" / "dedupe" / "dedupe_report.json"
    dedupe = None
    if dedupe_path.exists():
        dedupe = load_model(dedupe_path, DedupeReport)

    quality_path = lib_root / "silver" / "quality" / "source_quality_report.json"
    quality = None
    if quality_path.exists():
        quality = load_model(quality_path, SourceQualityReport)

    promotion_reports = len(list((lib_root / "promotion" / "reports").glob("*.json")))
    promotion_candidates = len(list((lib_root / "promotion" / "candidates").rglob("*.md")))

    return {
        "generated_at": utc_now().isoformat(),
        "raw": {
            "total_records": len(load_raw_records(project_root)),
            "by_origin": raw_counts,
        },
        "silver": {
            "source_cards": len(cards),
            "chunks": chunk_count,
            "manifest": manifest.model_dump(mode="json") if manifest else None,
            "dedupe": {
                "total_cards": dedupe.total_cards if dedupe else 0,
                "unique_cards": dedupe.unique_cards if dedupe else 0,
                "clusters": len(dedupe.duplicate_clusters) if dedupe else 0,
            },
            "quality": {
                "total_sources": quality.total_sources if quality else 0,
                "average_score": quality.average_score if quality else 0.0,
            },
        },
        "promotion": {
            "reports": promotion_reports,
            "candidate_files": promotion_candidates,
        },
    }
