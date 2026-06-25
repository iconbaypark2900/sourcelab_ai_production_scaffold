"""Genericness detection for research topics and lesson plans."""

from __future__ import annotations

import re

from sourcelab.library.io import utc_now
from sourcelab.research.schemas import (
    GenericnessReport,
    GenericnessSignal,
    GenericnessVerdict,
    ResearchPlan,
    SourceCoverageReport,
)
from sourcelab.generation.schemas import GeneratedLessonPackage

GENERIC_PHRASES = (
    "best practices",
    "in general",
    "it is important",
    "various approaches",
    "many systems",
    "typically",
    "generally speaking",
    "overall",
    "comprehensive overview",
)

DOMAIN_TERMS_BY_PACK: dict[str, tuple[str, ...]] = {
    "agentic_engineering_v1": ("agent", "orchestration", "control plane", "multi-agent", "grounding", "run"),
    "quantum_finance_v1": ("quantum", "portfolio", "qubit", "hybrid", "optimizer", "risk", "finance"),
    "biomedical_ai_v1": ("clinical", "evidence", "patient", "graph", "provenance", "biomedical", "pubmed"),
}


def _topic_specificity(topic: str, source_pack: str) -> tuple[float, list[GenericnessSignal]]:
    terms = [t for t in re.split(r"[^a-z0-9]+", topic.lower()) if len(t) > 3]
    pack_terms = DOMAIN_TERMS_BY_PACK.get(source_pack, ())
    overlap = sum(1 for term in terms if any(pt in term or term in pt for pt in pack_terms))
    ratio = overlap / max(len(terms), 1)
    triggered = ratio >= 0.34
    return ratio, [
        GenericnessSignal(
            signal_id="topic_domain_overlap",
            description="Topic terms overlap with pack-specific domain vocabulary",
            weight=0.35,
            triggered=triggered,
        )
    ]


def _lesson_specificity(package: GeneratedLessonPackage | None) -> tuple[float, list[GenericnessSignal]]:
    if not package or not package.lesson:
        return 0.0, [
            GenericnessSignal(
                signal_id="missing_lesson",
                description="No generated lesson package available",
                weight=0.20,
                triggered=True,
            )
        ]

    text = " ".join(
        [
            package.lesson.title,
            package.lesson.task_instructions,
            " ".join(package.lesson.learning_objectives),
        ]
    ).lower()
    generic_hits = sum(1 for phrase in GENERIC_PHRASES if phrase in text)
    source_binding = len(set(package.lesson.source_ids)) + len(set(package.lesson.chunk_ids))
    specificity = min(source_binding / 4.0, 1.0) - min(generic_hits * 0.15, 0.45)
    specificity = max(specificity, 0.0)

    signals = [
        GenericnessSignal(
            signal_id="generic_phrase_count",
            description="Count of generic boilerplate phrases in lesson text",
            weight=0.25,
            triggered=generic_hits >= 2,
        ),
        GenericnessSignal(
            signal_id="source_binding_depth",
            description="Lesson binds to multiple source and chunk IDs",
            weight=0.25,
            triggered=source_binding >= 2,
        ),
    ]
    return specificity, signals


def _coverage_specificity(coverage: SourceCoverageReport | None) -> tuple[float, list[GenericnessSignal]]:
    if coverage is None:
        return 0.0, [
            GenericnessSignal(
                signal_id="missing_coverage",
                description="No coverage report available",
                weight=0.20,
                triggered=True,
            )
        ]
    score = coverage.coverage_score
    return score, [
        GenericnessSignal(
            signal_id="coverage_score",
            description="Source coverage score from library-aware retrieval",
            weight=0.20,
            triggered=score >= 0.55,
        )
    ]


def build_genericness_report(
    run_id: str,
    topic: str,
    source_pack: str,
    plan: ResearchPlan,
    coverage: SourceCoverageReport | None = None,
    package: GeneratedLessonPackage | None = None,
) -> GenericnessReport:
    """Score topic/lesson genericness deterministically."""
    topic_score, topic_signals = _topic_specificity(topic, source_pack)
    lesson_score, lesson_signals = _lesson_specificity(package)
    coverage_score, coverage_signals = _coverage_specificity(coverage)

    plan_bonus = min(len(plan.subtopics) / 6.0, 0.15)
    composite = (
        0.35 * topic_score + 0.35 * lesson_score + 0.20 * coverage_score + plan_bonus
    )
    composite = round(min(max(composite, 0.0), 1.0), 4)
    genericness_score = round(1.0 - composite, 4)

    if genericness_score >= 0.62:
        verdict: GenericnessVerdict = "too_generic"
    elif genericness_score >= 0.38:
        verdict = "somewhat_generic"
    else:
        verdict = "specific"

    signals = topic_signals + lesson_signals + coverage_signals
    recommendations: list[str] = []
    if verdict == "too_generic":
        recommendations.append("Add pack-specific subtopics and narrow the lesson task instructions.")
        recommendations.append("Promote local library docs into the source pack for stronger grounding.")
    elif verdict == "somewhat_generic":
        recommendations.append("Bind each section to explicit chunk IDs from library-aware retrieval.")
    else:
        recommendations.append("Topic appears sufficiently specific for source-grounded study.")

    if coverage and "needs_source_expansion" in coverage.weak_labels:
        recommendations.append("Run library collectors suggested in source_expansion_suggestions.json.")

    return GenericnessReport(
        run_id=run_id,
        topic=topic,
        source_pack=source_pack,
        generated_at=utc_now(),
        verdict=verdict,
        genericness_score=genericness_score,
        signals=signals,
        recommendations=recommendations,
    )
