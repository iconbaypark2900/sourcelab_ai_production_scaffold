"""Evidence-bound lesson plan generation."""

from __future__ import annotations

from sourcelab.library.io import utc_now
from sourcelab.research.schemas import (
    EvidenceBoundLessonPlan,
    EvidenceBoundSection,
    EvidenceStrength,
    ResearchPlan,
    RetrievalStrategy,
)
from sourcelab.generation.schemas import GeneratedLessonPackage


def _strength_for_hits(hit_count: int, has_pack: bool) -> EvidenceStrength:
    if hit_count >= 2 and has_pack:
        return "strong"
    if hit_count >= 1:
        return "moderate"
    if hit_count == 0:
        return "missing"
    return "weak"


def _hits_for_subtopic(strategy: RetrievalStrategy, subtopic_id: str) -> list:
    query_ids = {q.query_id for q in strategy.queries if q.subtopic_id == subtopic_id}
    return [hit for hit in strategy.hits if hit.query_id in query_ids]


def build_evidence_bound_lesson_plan(
    strategy: RetrievalStrategy,
    plan: ResearchPlan,
    package: GeneratedLessonPackage | None = None,
) -> EvidenceBoundLessonPlan:
    """Build sections with explicit evidence bindings."""
    sections: list[EvidenceBoundSection] = []

    for sub in plan.subtopics:
        hits = _hits_for_subtopic(strategy, sub.subtopic_id)
        if not hits and strategy.hits:
            hits = strategy.hits[:1]

        source_ids = sorted({hit.source_id for hit in hits})
        chunk_ids = [hit.chunk_id for hit in hits]
        card_ids = sorted({hit.library_card_id for hit in hits if hit.library_card_id})
        has_pack = any(hit.origin == "source_pack" for hit in hits)
        strength = _strength_for_hits(len(hits), has_pack)
        gaps: list[str] = []
        if strength in {"weak", "missing"}:
            gaps.append(f"Insufficient evidence for subtopic: {sub.title}")

        objective = sub.title
        if package and package.lesson and package.lesson.learning_objectives:
            for obj in package.lesson.learning_objectives:
                if sub.title.lower().split()[0] in obj.lower():
                    objective = obj
                    break

        sections.append(
            EvidenceBoundSection(
                section_id=sub.subtopic_id,
                title=sub.title,
                objective=objective,
                source_ids=source_ids,
                chunk_ids=chunk_ids,
                library_card_ids=card_ids,
                evidence_strength=strength,
                gaps=gaps,
            )
        )

    if package and package.lesson and package.lesson.task_instructions:
        sections.append(
            EvidenceBoundSection(
                section_id="task_instructions",
                title="Task instructions",
                objective=package.lesson.task_instructions[:240],
                source_ids=sorted(set(package.lesson.source_ids)),
                chunk_ids=list(package.lesson.chunk_ids),
                library_card_ids=sorted(
                    {
                        hit.library_card_id
                        for hit in strategy.hits
                        if hit.library_card_id and hit.chunk_id in package.lesson.chunk_ids
                    }
                ),
                evidence_strength=_strength_for_hits(len(package.lesson.chunk_ids), bool(package.lesson.source_ids)),
                gaps=[] if package.lesson.chunk_ids else ["Lesson package lacks chunk bindings."],
            )
        )

    strengths = [section.evidence_strength for section in sections]
    if "missing" in strengths:
        overall: EvidenceStrength = "missing"
    elif strengths.count("weak") >= len(strengths) // 2:
        overall = "weak"
    elif all(s in {"strong", "moderate"} for s in strengths):
        overall = "strong" if "strong" in strengths else "moderate"
    else:
        overall = "moderate"

    uncovered = [section.title for section in sections if section.evidence_strength in {"weak", "missing"}]

    return EvidenceBoundLessonPlan(
        run_id=strategy.run_id,
        topic=strategy.topic,
        source_pack=strategy.source_pack,
        generated_at=utc_now(),
        sections=sections,
        overall_evidence_strength=overall,
        uncovered_objectives=uncovered,
    )
