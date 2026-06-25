"""Normalize bronze raw records into silver source cards."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from sourcelab.library.chunking import chunk_source_card
from sourcelab.library.io import load_model, save_model, utc_now
from sourcelab.library.paths import ensure_library_layout, library_root
from sourcelab.library.schemas import LibraryBuildReport, LibraryManifest, RawSourceRecord, SourceCard


def _trust_tier_for_origin(origin: str) -> str:
    tiers = {
        "local_docs": "B",
        "arxiv": "C",
        "pubmed": "B",
        "nvd": "A",
        "sec": "A",
        "nasa": "A",
        "govinfo": "A",
        "github": "C",
    }
    return tiers.get(origin, "C")


def load_raw_records(project_root: Path) -> list[RawSourceRecord]:
    lib_root = library_root(project_root)
    records: list[RawSourceRecord] = []
    raw_root = lib_root / "raw"
    if not raw_root.exists():
        return records
    for meta_path in sorted(raw_root.rglob("*.json")):
        record = load_model(meta_path, RawSourceRecord)
        records.append(record)
    return records


def raw_to_source_card(record: RawSourceRecord) -> SourceCard:
    return SourceCard(
        source_id=record.record_id,
        origin=record.origin,
        title=record.title,
        url=record.url,
        publisher=record.publisher,
        authors=record.authors,
        published_at=record.published_at,
        retrieved_at=record.retrieved_at,
        license=record.license,
        source_type=record.source_type,
        trust_tier=_trust_tier_for_origin(record.origin),
        domain_tags=record.domain_tags,
        topic_tags=record.topic_tags,
        summary=record.summary,
        key_terms=record.key_terms,
        raw_path=record.raw_path,
        checksum=record.checksum,
        external_id=record.external_id,
    )


def save_source_card(project_root: Path, card: SourceCard) -> Path:
    cards_dir = library_root(project_root) / "silver" / "source_cards"
    path = cards_dir / f"{card.source_id}.json"
    save_model(path, card)
    return path


def load_source_cards(project_root: Path) -> list[SourceCard]:
    cards_dir = library_root(project_root) / "silver" / "source_cards"
    if not cards_dir.exists():
        return []
    cards: list[SourceCard] = []
    for path in sorted(cards_dir.glob("*.json")):
        cards.append(load_model(path, SourceCard))
    return cards


def write_library_manifest(project_root: Path, cards: list[SourceCard], chunk_count: int) -> LibraryManifest:
    origins = Counter(card.origin for card in cards)
    domains = Counter(tag for card in cards for tag in card.domain_tags)
    manifest = LibraryManifest(
        built_at=utc_now(),
        raw_record_count=len(load_raw_records(project_root)),
        source_card_count=len(cards),
        chunk_count=chunk_count,
        origins=dict(origins),
        domain_tags=dict(domains),
    )
    save_model(library_root(project_root) / "silver" / "manifests" / "library_manifest.json", manifest)
    return manifest


def normalize_library(project_root: Path) -> LibraryBuildReport:
    """Convert all bronze raw records to silver source cards and chunks."""
    ensure_library_layout(project_root)
    records = load_raw_records(project_root)
    cards: list[SourceCard] = []
    chunk_count = 0

    for record in records:
        card = raw_to_source_card(record)
        chunks = chunk_source_card(project_root, card)
        card.chunk_paths = [str(path.relative_to(project_root)) for path in chunks]
        save_source_card(project_root, card)
        cards.append(card)
        chunk_count += len(chunks)

    write_library_manifest(project_root, cards, chunk_count)
    return LibraryBuildReport(
        generated_at=utc_now(),
        stage="normalize",
        status="ok",
        message=f"Normalized {len(cards)} source cards with {chunk_count} chunks",
        counts={"source_cards": len(cards), "chunks": chunk_count},
    )
