"""Scenario generator.

Instruction:
- This is where DiffusionGemma or another generation backend should plug in.
- In production, generated scenarios must be grounded in retrieved chunks.
- Supports difficulty (1-5), task_format, and audience parameters.
"""

from __future__ import annotations

from sourcelab.core.models import SearchResult
from sourcelab.generation.schemas import GeneratedScenario

# Task format descriptions for deterministic scenario generation
TASK_FORMATS = {
    "executive_explanation": "Explain a technical concept to an executive audience",
    "architecture_review": "Review and critique an architectural decision",
    "debugging": "Diagnose and fix a technical problem",
    "hands_on_lab": "Complete a practical hands-on exercise",
    "risk_review": "Assess risks and propose mitigations",
}

AUDIENCE_DESCRIPTIONS = {
    "student": "a technical student learning about",
    "engineer": "a practicing engineer working with",
    "cto": "a CTO evaluating decisions about",
    "security_team": "a security team assessing",
}

DIFFICULTY_FRAMING = {
    1: "basic overview of",
    2: "foundational understanding of",
    3: "practical application of",
    4: "advanced analysis of",
    5: "expert-level evaluation of",
}


class ScenarioGenerator:
    """Generate source-grounded scenarios from retrieved chunks."""

    def generate(
        self,
        topic: str,
        search_results: list[SearchResult],
        difficulty: int = 3,
        task_format: str = "architecture_review",
        audience: str = "engineer",
    ) -> GeneratedScenario:
        """Create a deterministic scenario grounded in retrieved sources."""
        source_ids = list({r.source_id for r in search_results})
        chunk_ids = [r.chunk_id for r in search_results]

        # Build scenario from retrieved context
        top = search_results[0] if search_results else None
        source_title = top.title if top else "approved sources"
        source_preview = top.text_preview if top else "technical documentation"

        format_desc = TASK_FORMATS.get(task_format, TASK_FORMATS["architecture_review"])
        audience_desc = AUDIENCE_DESCRIPTIONS.get(audience, AUDIENCE_DESCRIPTIONS["engineer"])
        difficulty_desc = DIFFICULTY_FRAMING.get(difficulty, DIFFICULTY_FRAMING[3])

        context = (
            f"You are {audience_desc} {topic}. "
            f"This scenario involves a {difficulty_desc} {topic} using insights from "
            f"'{source_title}'. "
            f"Context from sources: {source_preview[:200]}..."
        )

        title = f"{format_desc}: {topic}"

        return GeneratedScenario(
            title=title,
            context=context,
            audience=audience,
            task_format=task_format,
            difficulty=difficulty,
            source_ids=source_ids,
            chunk_ids=chunk_ids,
        )

    def generate_variants(
        self,
        topic: str,
        search_results: list[SearchResult],
        count: int = 5,
    ) -> list[GeneratedScenario]:
        """Generate multiple scenario variants for a topic."""
        formats = list(TASK_FORMATS.keys())
        variants = []
        for i, fmt in enumerate(formats[:count]):
            variants.append(
                self.generate(
                    topic=topic,
                    search_results=search_results,
                    difficulty=3,
                    task_format=fmt,
                    audience="engineer",
                )
            )
        return variants
