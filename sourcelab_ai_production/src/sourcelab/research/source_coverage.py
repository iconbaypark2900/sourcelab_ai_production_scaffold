"""Source coverage metrics and weak labels."""

from __future__ import annotations

from sourcelab.library.io import utc_now
from sourcelab.research.schemas import (
    CoverageByOrigin,
    EvidenceOrigin,
    ResearchPlan,
    RetrievalStrategy,
    SourceCoverageReport,
    WeakLabel,
)
from sourcelab.generation.schemas import GeneratedLessonPackage


THIN_RETRIEVAL_THRESHOLD = 2
THIN_COVERAGE_THRESHOLD = 0.45
THIN_SECTION_THRESHOLD = 0.5


def _origin_counts(strategy: RetrievalStrategy) -> dict[EvidenceOrigin, CoverageByOrigin]:
    counts: dict[EvidenceOrigin, CoverageByOrigin] = {
        "source_pack": CoverageByOrigin(origin="source_pack"),
        "library_silver": CoverageByOrigin(origin="library_silver"),
        "promoted_candidate": CoverageByOrigin(origin="promoted_candidate"),
    }
    counts["source_pack"].source_count = strategy.source_pack_source_count
    counts["library_silver"].source_count = strategy.library_silver_card_count
    counts["promoted_candidate"].source_count = strategy.promoted_candidate_count

    for hit in strategy.hits:
        entry = counts[hit.origin]
        entry.hit_count += 1
        entry.chunk_count = len({h.chunk_id for h in strategy.hits if h.origin == hit.origin})
    return counts


def compute_coverage_score(strategy: RetrievalStrategy, plan: ResearchPlan) -> float:
    """Deterministic coverage score in [0, 1]."""
    if not plan.subtopics:
        return 0.0

    hit_subtopics = set()
    for hit in strategy.hits:
        for query in strategy.queries:
            if query.query_id == hit.query_id and query.subtopic_id:
                hit_subtopics.add(query.subtopic_id)

    subtopic_ratio = len(hit_subtopics) / max(len(plan.subtopics), 1)
    retrieval_ratio = min(len(strategy.hits) / 4.0, 1.0)
    origin_diversity = len({hit.origin for hit in strategy.hits}) / 3.0
    pack_ratio = min(strategy.source_pack_source_count / 2.0, 1.0) if strategy.hits else 0.0

    score = 0.45 * subtopic_ratio + 0.30 * retrieval_ratio + 0.15 * origin_diversity + 0.10 * pack_ratio
    return round(min(max(score, 0.0), 1.0), 4)


def detect_weak_labels(
    strategy: RetrievalStrategy,
    coverage_score: float,
    package: GeneratedLessonPackage | None = None,
) -> list[WeakLabel]:
    """Assign weak labels from retrieval and lesson signals."""
    labels: list[WeakLabel] = []

    if len(strategy.hits) < THIN_RETRIEVAL_THRESHOLD:
        labels.append("insufficient_evidence")

    if coverage_score < THIN_COVERAGE_THRESHOLD:
        labels.append("needs_source_expansion")

    if package and package.lesson:
        bound_chunks = set(package.lesson.chunk_ids)
        retrieved_chunks = {hit.chunk_id for hit in strategy.hits}
        if bound_chunks and len(bound_chunks & retrieved_chunks) / len(bound_chunks) < THIN_SECTION_THRESHOLD:
            labels.append("thin_lesson")
    elif len(strategy.hits) < 3:
        labels.append("thin_lesson")

    return sorted(set(labels))


def build_coverage_gaps(
    strategy: RetrievalStrategy,
    plan: ResearchPlan,
    weak_labels: list[WeakLabel],
) -> list[str]:
    """List explicit coverage gaps."""
    gaps: list[str] = []
    covered_subtopics = {
        query.subtopic_id
        for hit in strategy.hits
        for query in strategy.queries
        if query.query_id == hit.query_id and query.subtopic_id
    }
    for sub in plan.subtopics:
        if sub.subtopic_id not in covered_subtopics:
            gaps.append(f"No retrieval hits for subtopic: {sub.title}")

    if strategy.library_silver_card_count == 0:
        gaps.append("Silver library has no source cards — run library collect-local + normalize.")
    if not any(hit.origin == "source_pack" for hit in strategy.hits):
        gaps.append("No source-pack chunks retrieved for this topic.")
    if "needs_source_expansion" in weak_labels:
        gaps.append("Coverage score below threshold — consider library collectors or pack promotion.")
    return gaps


def build_source_coverage_report(
    strategy: RetrievalStrategy,
    plan: ResearchPlan,
    package: GeneratedLessonPackage | None = None,
) -> SourceCoverageReport:
    """Build the source coverage report artifact."""
    coverage_score = compute_coverage_score(strategy, plan)
    weak_labels = detect_weak_labels(strategy, coverage_score, package)
    by_origin = list(_origin_counts(strategy).values())
    unique_sources = sorted({hit.source_id for hit in strategy.hits})
    unique_cards = sorted({hit.library_card_id for hit in strategy.hits if hit.library_card_id})

    notes: list[str] = []
    if strategy.promoted_candidate_count:
        notes.append(f"{strategy.promoted_candidate_count} promoted candidates available for pack.")
    if strategy.library_silver_card_count:
        notes.append(f"{strategy.library_silver_card_count} silver library cards indexed.")

    return SourceCoverageReport(
        run_id=strategy.run_id,
        topic=strategy.topic,
        source_pack=strategy.source_pack,
        generated_at=utc_now(),
        coverage_score=coverage_score,
        retrieval_hit_count=len(strategy.hits),
        unique_source_count=len(unique_sources),
        unique_library_card_count=len(unique_cards),
        by_origin=by_origin,
        weak_labels=weak_labels,
        gaps=build_coverage_gaps(strategy, plan, weak_labels),
        notes=notes,
    )


def render_coverage_markdown(report: SourceCoverageReport) -> str:
    """Render source coverage report as markdown."""
    lines = [
        f"# Source Coverage — {report.topic}",
        "",
        f"- **Coverage score:** {report.coverage_score:.2f}",
        f"- **Retrieval hits:** {report.retrieval_hit_count}",
        f"- **Unique sources:** {report.unique_source_count}",
        f"- **Library cards used:** {report.unique_library_card_count}",
        "",
    ]
    if report.weak_labels:
        lines.extend(["## Weak labels", ""])
        for label in report.weak_labels:
            lines.append(f"- `{label}`")
        lines.append("")
    if report.by_origin:
        lines.extend(["## By origin", ""])
        for row in report.by_origin:
            lines.append(
                f"- **{row.origin}**: sources={row.source_count}, hits={row.hit_count}, chunks={row.chunk_count}"
            )
        lines.append("")
    if report.gaps:
        lines.extend(["## Gaps", ""])
        for gap in report.gaps:
            lines.append(f"- {gap}")
        lines.append("")
    return "\n".join(lines)
