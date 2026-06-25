"""Deterministic research planning keyed by source pack and topic."""

from __future__ import annotations

import re
from pathlib import Path

from sourcelab.library.io import utc_now
from sourcelab.research.slugs import topic_slug
from sourcelab.research.schemas import ResearchPlan, ResearchSubtopic


PACK_PLAN_TEMPLATES: dict[str, dict] = {
    "agentic_engineering_v1": {
        "target_domains": ["agentic_systems", "software_engineering", "control_plane"],
        "pack_focus_areas": [
            "multi-agent orchestration",
            "control-plane observability",
            "human-in-the-loop guardrails",
            "deterministic run artifacts",
        ],
        "subtopics": [
            ("agent_topologies", "Agent topologies and coordination", "high"),
            ("control_plane", "Control plane responsibilities", "high"),
            ("grounding", "Source-grounded agent outputs", "medium"),
            ("ops_loop", "Run → verify → learn loop", "medium"),
        ],
        "questions": [
            "What control-plane signals are required for multi-agent runs?",
            "Which agent roles need explicit human approval gates?",
            "How should retrieval and verification artifacts constrain agent actions?",
            "What failure modes appear when orchestration lacks grounding?",
        ],
        "methodology": [
            "Map topic terms to agentic engineering source pack concepts.",
            "Cross-check silver library cards for local project docs.",
            "Prefer promoted candidates that mention Run Studio or batch workflows.",
        ],
    },
    "quantum_finance_v1": {
        "target_domains": ["quantum_computing", "quantum_finance", "portfolio_optimization"],
        "pack_focus_areas": [
            "hybrid classical-quantum workflows",
            "portfolio constraint encoding",
            "noise and calibration sensitivity",
            "risk-aware optimization metrics",
        ],
        "subtopics": [
            ("hybrid_workflow", "Hybrid optimizer workflow", "high"),
            ("encoding", "Problem encoding and qubit budget", "high"),
            ("risk_metrics", "Risk and benchmark metrics", "medium"),
            ("deployment", "Production deployment constraints", "medium"),
        ],
        "questions": [
            "Which portfolio constraints must be encoded for a hybrid optimizer?",
            "How do calibration and noise affect optimizer reliability?",
            "What classical baselines should quantum results be compared against?",
            "Which risk metrics are mandatory for finance-grade answers?",
        ],
        "methodology": [
            "Anchor planning on quantum finance pack sources.",
            "Pull arXiv-style library cards when hybrid algorithms are mentioned.",
            "Flag thin coverage when fewer than two finance-specific sources hit.",
        ],
    },
    "biomedical_ai_v1": {
        "target_domains": ["biomedical_ai", "clinical_evidence", "knowledge_graphs"],
        "pack_focus_areas": [
            "clinical evidence graphs",
            "provenance and citation chains",
            "patient-safety guardrails",
            "structured biomedical retrieval",
        ],
        "subtopics": [
            ("evidence_graph", "Clinical evidence graph design", "high"),
            ("provenance", "Provenance and trust tiers", "high"),
            ("safety", "Safety and unsupported-claim controls", "high"),
            ("retrieval", "Biomedical retrieval strategy", "medium"),
        ],
        "questions": [
            "Which evidence nodes and edges are required for clinical answers?",
            "How should unsupported clinical claims be blocked or flagged?",
            "What provenance metadata must accompany graph-derived facts?",
            "Which PubMed or guideline sources fill known coverage gaps?",
        ],
        "methodology": [
            "Prioritize biomedical pack sources and PubMed library cards.",
            "Treat low retrieval count as needs_source_expansion.",
            "Require explicit gaps when clinical claims lack chunk support.",
        ],
    },
}

DEFAULT_TEMPLATE = {
    "target_domains": ["research"],
    "pack_focus_areas": ["source-grounded lesson design", "retrieval coverage", "verification"],
    "subtopics": [
        ("core_concepts", "Core concepts", "high"),
        ("application", "Applied scenario", "medium"),
        ("verification", "Verification and grounding", "medium"),
    ],
    "questions": [
        "What source-backed concepts define this topic?",
        "Which claims require explicit chunk citations?",
        "What evidence gaps should block a confident lesson?",
    ],
    "methodology": [
        "Build a deterministic plan from the topic and source pack.",
        "Search source pack, silver library, and promoted candidates.",
    ],
}


def build_research_plan(
    run_id: str,
    topic: str,
    source_pack: str,
    project_root: Path | None = None,
) -> ResearchPlan:
    """Build a pack-aware research plan for the given topic."""
    from sourcelab.research.topic_profile import load_topic_profile

    template = PACK_PLAN_TEMPLATES.get(source_pack, DEFAULT_TEMPLATE)
    topic_terms = [term for term in re.split(r"[^a-z0-9]+", topic.lower()) if len(term) > 3]

    profile = load_topic_profile(project_root, source_pack, topic) if project_root else None
    profile_context_used = profile is not None and profile.run_count > 0
    profile_weak_concepts: list[str] = []
    profile_known_gaps: list[str] = []
    profile_source_expansion_suggestions: list[str] = []
    follow_up_focus: list[str] = []

    if profile_context_used and profile is not None:
        profile_weak_concepts = [
            label
            for label, _ in sorted(profile.weak_label_counts.items(), key=lambda item: item[1], reverse=True)
        ][:5]
        profile_known_gaps = list(profile.frequent_gaps[:5])
        if profile.answer_submit_count > 0:
            follow_up_focus.append("prerequisite review")
        if profile_known_gaps:
            follow_up_focus.append("gap repair")
        if profile_weak_concepts:
            follow_up_focus.append("weak concept reinforcement")
        recent_genericness = profile.genericness_history[-3:]
        if any(v in ("somewhat_generic", "too_generic") for v in recent_genericness):
            follow_up_focus.append("next-step challenge")
        if "needs_source_expansion" in profile_weak_concepts:
            profile_source_expansion_suggestions.append(
                "Run arxiv and pubmed collectors for topic-specific gaps"
            )

    subtopics: list[ResearchSubtopic] = []
    for subtopic_id, title, priority in template["subtopics"]:
        rationale = f"Cover {title.lower()} for topic terms: {', '.join(topic_terms[:4]) or topic}"
        subtopics.append(
            ResearchSubtopic(
                subtopic_id=subtopic_id,
                title=title,
                rationale=rationale,
                priority=priority,  # type: ignore[arg-type]
            )
        )

    if profile_context_used:
        for focus in follow_up_focus:
            subtopics.append(
                ResearchSubtopic(
                    subtopic_id=f"followup_{focus.replace(' ', '_')}",
                    title=focus.title(),
                    rationale=f"Adaptive follow-up from topic profile (run_count={profile.run_count if profile else 0})",
                    priority="high" if focus != "next-step challenge" else "medium",
                )
            )

    questions = list(template["questions"])
    if topic_terms:
        questions.append(f"How do {' and '.join(topic_terms[:3])} interact in {source_pack}?")

    if profile_context_used:
        for gap in profile_known_gaps[:2]:
            questions.append(f"What source-backed evidence closes the gap: {gap}?")
        for concept in profile_weak_concepts[:2]:
            questions.append(
                f"How should the lesson reinforce weak area: {concept.replace('_', ' ')}?"
            )

    methodology = list(template["methodology"])
    if profile_context_used and follow_up_focus:
        methodology.append(
            f"Follow-up focus: {', '.join(follow_up_focus)} — adapted from prior run history."
        )

    return ResearchPlan(
        run_id=run_id,
        topic=topic,
        source_pack=source_pack,
        generated_at=utc_now(),
        subtopics=subtopics,
        research_questions=questions,
        target_domains=list(template["target_domains"]),
        pack_focus_areas=list(template["pack_focus_areas"]),
        methodology_notes=methodology,
        profile_context_used=profile_context_used,
        profile_weak_concepts=profile_weak_concepts,
        profile_known_gaps=profile_known_gaps,
        profile_source_expansion_suggestions=profile_source_expansion_suggestions,
        follow_up_focus=follow_up_focus,
    )


def render_research_plan_markdown(plan: ResearchPlan) -> str:
    """Render a human-readable research plan."""
    lines = [
        f"# Research Plan — {plan.topic}",
        "",
        f"- **Run:** `{plan.run_id}`",
        f"- **Source pack:** `{plan.source_pack}`",
        f"- **Generated:** {plan.generated_at.isoformat()}",
        "",
        "## Subtopics",
        "",
    ]
    for sub in plan.subtopics:
        lines.append(f"- **{sub.title}** ({sub.priority}): {sub.rationale}")
    lines.extend(["", "## Research questions", ""])
    for question in plan.research_questions:
        lines.append(f"- {question}")
    lines.extend(["", "## Focus areas", ""])
    for area in plan.pack_focus_areas:
        lines.append(f"- {area}")
    lines.extend(["", "## Methodology", ""])
    for note in plan.methodology_notes:
        lines.append(f"- {note}")
    if plan.profile_context_used:
        lines.extend(["", "## Adaptive profile context", ""])
        lines.append(f"- Profile context used: **yes**")
        if plan.follow_up_focus:
            lines.append(f"- Follow-up focus: {', '.join(plan.follow_up_focus)}")
        if plan.profile_weak_concepts:
            lines.append("- Weak concepts:")
            for concept in plan.profile_weak_concepts:
                lines.append(f"  - {concept}")
        if plan.profile_known_gaps:
            lines.append("- Known gaps:")
            for gap in plan.profile_known_gaps:
                lines.append(f"  - {gap}")
    lines.append("")
    return "\n".join(lines)
