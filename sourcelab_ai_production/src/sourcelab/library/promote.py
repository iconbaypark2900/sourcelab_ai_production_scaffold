"""Promote silver source cards into gold source pack candidates."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sourcelab.library.io import save_model, utc_now
from sourcelab.library.normalize import load_source_cards
from sourcelab.library.paths import ensure_library_layout, library_root
from sourcelab.library.quality import quality_library
from sourcelab.library.schemas import LibraryBuildReport, PromotionCandidate, SourceCard
from sourcelab.sources.registry import normalize_source_id


def _card_to_markdown(card: SourceCard, domain: str) -> str:
    created_at = datetime.now(timezone.utc).isoformat()
    lines = [
        "---",
        f"source_id: {card.source_id}",
        f"title: {card.title}",
        f"domain: {domain}",
        f"trust_tier: {card.trust_tier}",
        "version: 1.0",
        f"created_at: {created_at}",
        "---",
        "",
        f"# {card.title}",
        "",
        "## Summary",
        "",
        card.summary or "No summary available.",
        "",
    ]
    if card.key_terms:
        lines.extend(["## Key Terms", ""])
        for term in card.key_terms[:12]:
            lines.append(f"- {term}")
        lines.append("")
    if card.url:
        lines.extend(["## Reference", "", f"- {card.url}", ""])
    lines.extend(
        [
            "## Source Quality Note",
            "",
            "Promoted by SourceLab Library Builder v1 from silver source cards.",
            "",
        ]
    )
    return "\n".join(lines)


def promote_library(
    project_root: Path,
    domain: str,
    target_pack: str,
    min_quality: float = 0.55,
    dry_run: bool = True,
    force: bool = False,
) -> LibraryBuildReport:
    """Select high-quality cards and propose or write pack markdown."""
    ensure_library_layout(project_root)
    cards = load_source_cards(project_root)
    if not cards or any(card.quality_score is None for card in cards):
        quality_library(project_root)
        cards = load_source_cards(project_root)

    matching = [
        card
        for card in cards
        if domain in card.domain_tags and (card.quality_score or 0.0) >= min_quality
    ]
    candidates: list[PromotionCandidate] = []
    promoted_count = 0

    pack_sources_dir = project_root / "data" / "source_packs" / target_pack / "sources"
    candidates_dir = library_root(project_root) / "promotion" / "candidates" / target_pack
    reports_dir = library_root(project_root) / "promotion" / "reports"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    for card in matching:
        filename = f"{normalize_source_id(card.source_id)}.md"
        candidate = PromotionCandidate(
            source_id=card.source_id,
            title=card.title,
            domain_tags=card.domain_tags,
            quality_score=card.quality_score or 0.0,
            target_pack=target_pack,
            proposed_filename=filename,
            status="proposed" if dry_run and not force else "promoted",
            reason="meets_domain_and_quality_threshold",
        )
        markdown = _card_to_markdown(card, domain)
        proposal_path = candidates_dir / filename
        proposal_path.write_text(markdown, encoding="utf-8")

        if force and not dry_run:
            pack_sources_dir.mkdir(parents=True, exist_ok=True)
            target_path = pack_sources_dir / filename
            if target_path.exists():
                candidate.status = "skipped"
                candidate.reason = "target_file_exists"
            else:
                target_path.write_text(markdown, encoding="utf-8")
                promoted_count += 1
                candidate.status = "promoted"
        candidates.append(candidate)

    status = "dry_run" if dry_run or not force else "ok"
    report = LibraryBuildReport(
        generated_at=utc_now(),
        stage="promote",
        status=status,
        message=(
            f"Proposed {len(candidates)} candidates for {target_pack}"
            if dry_run or not force
            else f"Promoted {promoted_count} sources into {target_pack}"
        ),
        counts={
            "candidates": len(candidates),
            "promoted": promoted_count,
        },
        candidates=candidates,
    )
    save_model(reports_dir / f"promotion_{target_pack}.json", report)
    return report
