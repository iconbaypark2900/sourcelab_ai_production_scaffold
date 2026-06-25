"""Promote library source cards into a run's source pack from expansion context."""

from __future__ import annotations

import re
from pathlib import Path

from sourcelab.library.io import load_model, utc_now
from sourcelab.library.normalize import load_source_cards
from sourcelab.library.promote import _card_to_markdown, promote_library
from sourcelab.library.quality import quality_library
from sourcelab.research.expansion_execution import COLLECTOR_DOMAINS, _resolve_expansion_plan
from sourcelab.research.schemas import (
    LibraryExpansionPlan,
    ResearchPlan,
    SourceCoverageReport,
    SourcePromotionEntry,
    SourcePromotionReport,
)
from sourcelab.sources.registry import normalize_source_id


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) >= 3}


def _missing_evidence_terms(
    topic: str,
    coverage: SourceCoverageReport | None,
    plan: ResearchPlan | None,
) -> list[str]:
    terms: set[str] = set()
    terms.update(_tokenize(topic))
    if coverage:
        for gap in coverage.gaps:
            terms.update(_tokenize(gap))
    if plan:
        for gap in plan.profile_known_gaps:
            terms.update(_tokenize(gap))
        for concept in plan.profile_weak_concepts:
            terms.update(_tokenize(concept))
    return sorted(terms)


def _target_domains(expansion_plan: LibraryExpansionPlan) -> list[str]:
    domains: set[str] = set()
    for collector in expansion_plan.recommended_collectors:
        domain = COLLECTOR_DOMAINS.get(collector)
        if domain:
            domains.add(domain)
    for query in expansion_plan.collector_queries:
        domain = COLLECTOR_DOMAINS.get(query.collector)
        if domain:
            domains.add(domain)
    if not domains:
        domains.add("research")
    return sorted(domains)


def _card_matches_terms(card_text: str, terms: set[str]) -> bool:
    if not terms:
        return True
    card_tokens = _tokenize(card_text)
    overlap = card_tokens & terms
    return len(overlap) >= 1


def select_promotion_candidates(
    project_root: Path,
    expansion_plan: LibraryExpansionPlan,
    coverage: SourceCoverageReport | None,
    research_plan: ResearchPlan | None,
    min_quality: float = 0.55,
) -> tuple[list[SourcePromotionEntry], list[str], list[str]]:
    """Select source cards matching topic, domain, missing evidence, and quality."""
    cards = load_source_cards(project_root)
    if not cards or any(card.quality_score is None for card in cards):
        quality_library(project_root)
        cards = load_source_cards(project_root)

    evidence_terms = _missing_evidence_terms(expansion_plan.topic, coverage, research_plan)
    term_set = set(evidence_terms)
    domains = _target_domains(expansion_plan)
    candidates: list[SourcePromotionEntry] = []

    for card in cards:
        if (card.quality_score or 0.0) < min_quality:
            continue
        if not any(domain in card.domain_tags for domain in domains):
            continue

        searchable = " ".join(
            [
                card.title,
                card.summary,
                " ".join(card.key_terms),
                " ".join(card.topic_tags),
            ]
        )
        if not _card_matches_terms(searchable, term_set):
            continue

        match_reasons = ["domain_match", "quality_threshold"]
        overlap = sorted(_tokenize(searchable) & term_set)
        if overlap:
            match_reasons.append(f"term_overlap:{','.join(overlap[:4])}")

        filename = f"{normalize_source_id(card.source_id)}.md"
        candidates.append(
            SourcePromotionEntry(
                source_id=card.source_id,
                title=card.title,
                domain_tags=card.domain_tags,
                quality_score=card.quality_score or 0.0,
                match_reasons=match_reasons,
                proposed_filename=filename,
                status="proposed",
                reason="matches_expansion_plan_criteria",
            )
        )

    return candidates, evidence_terms, domains


def build_source_promotion_report(
    project_root: Path,
    run_dir: Path,
    force: bool = False,
    min_quality: float = 0.55,
) -> SourcePromotionReport:
    """Build promotion report from expansion plan and improved library state."""
    expansion_plan = _resolve_expansion_plan(project_root, run_dir)
    coverage_path = run_dir / "source_coverage_report.json"
    coverage = load_model(coverage_path, SourceCoverageReport) if coverage_path.exists() else None
    plan_path = run_dir / "research_plan.json"
    research_plan = load_model(plan_path, ResearchPlan) if plan_path.exists() else None

    candidates, evidence_terms, domains = select_promotion_candidates(
        project_root,
        expansion_plan,
        coverage,
        research_plan,
        min_quality=min_quality,
    )

    promoted_count = 0
    skipped_count = 0
    mode: str = "force" if force else "dry_run"

    if force and candidates:
        for domain in domains:
            promote_library(
                project_root,
                domain=domain,
                target_pack=expansion_plan.source_pack,
                min_quality=min_quality,
                dry_run=False,
                force=True,
            )

        pack_sources_dir = project_root / "data" / "source_packs" / expansion_plan.source_pack / "sources"
        for candidate in candidates:
            target_path = pack_sources_dir / candidate.proposed_filename
            if target_path.exists():
                candidate.status = "promoted"
                candidate.reason = "already_in_pack"
                promoted_count += 1
            else:
                cards = load_source_cards(project_root)
                card = next((item for item in cards if item.source_id == candidate.source_id), None)
                if card is None:
                    candidate.status = "skipped"
                    candidate.reason = "card_not_found"
                    skipped_count += 1
                    continue
                domain = next((tag for tag in card.domain_tags if tag in domains), domains[0])
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(_card_to_markdown(card, domain), encoding="utf-8")
                candidate.status = "promoted"
                candidate.reason = "written_to_source_pack"
                promoted_count += 1
    elif not force:
        for candidate in candidates:
            candidate.status = "proposed"
            candidate.reason = "dry_run"

    return SourcePromotionReport(
        run_id=run_dir.name,
        topic=expansion_plan.topic,
        source_pack=expansion_plan.source_pack,
        generated_at=utc_now(),
        mode=mode,  # type: ignore[arg-type]
        min_quality=min_quality,
        missing_evidence_terms=evidence_terms,
        target_domains=domains,
        candidates=candidates,
        promoted_count=promoted_count,
        skipped_count=skipped_count,
    )


def render_source_promotion_markdown(report: SourcePromotionReport) -> str:
    """Render a human-readable source promotion report."""
    lines = [
        f"# Source Promotion Report — {report.topic}",
        "",
        f"- **Run:** `{report.run_id}`",
        f"- **Source pack:** `{report.source_pack}`",
        f"- **Mode:** `{report.mode}`",
        f"- **Min quality:** {report.min_quality}",
        f"- **Generated:** {report.generated_at.isoformat()}",
        "",
        "## Target domains",
        "",
    ]
    for domain in report.target_domains:
        lines.append(f"- `{domain}`")

    lines.extend(["", "## Missing evidence terms", ""])
    if report.missing_evidence_terms:
        lines.append(", ".join(report.missing_evidence_terms[:20]))
    else:
        lines.append("_(none)_")

    lines.extend(["", "## Candidates", ""])
    if report.candidates:
        for candidate in report.candidates:
            lines.append(
                f"- **{candidate.title}** (`{candidate.source_id}`) — "
                f"{candidate.status} · q={candidate.quality_score:.2f} · {candidate.reason}"
            )
    else:
        lines.append("- _(no matching cards)_")

    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Promoted: {report.promoted_count}",
            f"- Skipped: {report.skipped_count}",
            "",
        ]
    )
    return "\n".join(lines)


def write_source_promotion_report(
    project_root: Path,
    run_dir: Path,
    force: bool = False,
    min_quality: float = 0.55,
) -> SourcePromotionReport:
    """Write source_promotion_report.json and .md."""
    report = build_source_promotion_report(project_root, run_dir, force=force, min_quality=min_quality)
    (run_dir / "source_promotion_report.json").write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (run_dir / "source_promotion_report.md").write_text(
        render_source_promotion_markdown(report),
        encoding="utf-8",
    )
    return report
