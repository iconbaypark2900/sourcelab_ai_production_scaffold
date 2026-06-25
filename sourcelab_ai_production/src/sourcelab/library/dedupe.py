"""Deduplicate silver source cards."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

from sourcelab.library.io import save_model, utc_now
from sourcelab.library.normalize import load_source_cards, normalize_library
from sourcelab.library.paths import ensure_library_layout, library_root
from sourcelab.library.schemas import DedupeCluster, DedupeReport, LibraryBuildReport


def _canonical_url(url: str | None) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip().lower())
    host = parsed.netloc.replace("www.", "")
    path = parsed.path.rstrip("/")
    return f"{host}{path}"


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def _title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_title(a), _normalize_title(b)).ratio()


def build_dedupe_report(cards: list) -> DedupeReport:
    """Build dedupe clusters from source cards."""
    assigned: set[str] = set()
    clusters: list[DedupeCluster] = []
    checksum_matches = 0
    url_matches = 0
    external_id_matches = 0
    title_similarity_matches = 0

    by_checksum: dict[str, list] = {}
    by_url: dict[str, list] = {}
    by_external: dict[str, list] = {}
    for card in cards:
        by_checksum.setdefault(card.checksum, []).append(card)
        canonical = _canonical_url(card.url)
        if canonical:
            by_url.setdefault(canonical, []).append(card)
        if card.external_id:
            by_external.setdefault(card.external_id, []).append(card)

    def _add_cluster(reason: str, group, counter_attr: str) -> None:
        nonlocal checksum_matches, url_matches, external_id_matches, title_similarity_matches
        if len(group) < 2:
            return
        canonical = sorted(group, key=lambda c: c.retrieved_at)[0]
        duplicate_ids = [c.source_id for c in group if c.source_id != canonical.source_id]
        if not duplicate_ids:
            return
        cluster_id = f"cluster_{len(clusters)+1:03d}"
        clusters.append(
            DedupeCluster(
                cluster_id=cluster_id,
                canonical_source_id=canonical.source_id,
                duplicate_source_ids=duplicate_ids,
                match_reasons=[reason],
            )
        )
        assigned.update(duplicate_ids)
        if counter_attr == "checksum":
            checksum_matches += len(duplicate_ids)
        elif counter_attr == "url":
            url_matches += len(duplicate_ids)
        elif counter_attr == "external_id":
            external_id_matches += len(duplicate_ids)

    for group in by_checksum.values():
        _add_cluster("checksum", group, "checksum")
    for group in by_url.values():
        _add_cluster("canonical_url", group, "url")
    for group in by_external.values():
        _add_cluster("external_id", group, "external_id")

    remaining = [card for card in cards if card.source_id not in assigned]
    for i, left in enumerate(remaining):
        for right in remaining[i + 1 :]:
            if _title_similarity(left.title, right.title) >= 0.92:
                cluster_id = f"cluster_{len(clusters)+1:03d}"
                canonical, duplicate = (
                    (left, right) if len(left.title) >= len(right.title) else (right, left)
                )
                clusters.append(
                    DedupeCluster(
                        cluster_id=cluster_id,
                        canonical_source_id=canonical.source_id,
                        duplicate_source_ids=[duplicate.source_id],
                        match_reasons=["title_similarity"],
                    )
                )
                assigned.add(duplicate.source_id)
                title_similarity_matches += 1

    duplicate_ids = {dup for cluster in clusters for dup in cluster.duplicate_source_ids}
    return DedupeReport(
        generated_at=utc_now(),
        total_cards=len(cards),
        unique_cards=len(cards) - len(duplicate_ids),
        duplicate_clusters=clusters,
        checksum_matches=checksum_matches,
        url_matches=url_matches,
        external_id_matches=external_id_matches,
        title_similarity_matches=title_similarity_matches,
    )


def dedupe_library(project_root: Path) -> LibraryBuildReport:
    """Run dedupe over silver source cards."""
    ensure_library_layout(project_root)
    cards = load_source_cards(project_root)
    if not cards:
        normalize_library(project_root)
        cards = load_source_cards(project_root)

    report = build_dedupe_report(cards)
    save_model(library_root(project_root) / "silver" / "dedupe" / "dedupe_report.json", report)
    return LibraryBuildReport(
        generated_at=report.generated_at,
        stage="dedupe",
        status="ok",
        message=f"Deduped {report.total_cards} cards into {report.unique_cards} unique",
        counts={
            "total_cards": report.total_cards,
            "unique_cards": report.unique_cards,
            "clusters": len(report.duplicate_clusters),
        },
    )
