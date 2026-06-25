"""Source-grounded lesson generator.

Instruction:
- Production should call real model backends through model_router.py.
- This scaffold creates deterministic lessons from retrieved chunks.
- Never generate final lessons without sources.
- generate_package() produces a complete lesson package for Generation v2.
- Accepts an optional ModelRouter for local LLM generation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sourcelab.core.models import LessonTask, SearchResult
from sourcelab.generation.schemas import (
    ClaimCandidate,
    GeneratedLesson,
    GeneratedLessonPackage,
    GeneratedScenario,
    GenerationTrace,
)
from sourcelab.generation.scenario_generator import ScenarioGenerator

if TYPE_CHECKING:
    from sourcelab.generation.model_router import ModelRouter


# Difficulty-to-level mapping
DIFFICULTY_LEVEL = {
    1: "beginner",
    2: "beginner",
    3: "intermediate",
    4: "advanced",
    5: "advanced",
}


class SourceGroundedLessonGenerator:
    """Generate a lesson task from retrieved sources."""

    def generate(self, topic: str, search_results: list[SearchResult]) -> LessonTask:
        """Legacy generate method for backward compatibility."""
        if not search_results:
            raise ValueError("Cannot generate a source-grounded lesson without sources.")

        source_ids = list({r.source_id for r in search_results})
        top = search_results[0]

        return LessonTask(
            topic=topic,
            title=f"Source-grounded lab: {topic}",
            scenario=(
                f"You are advising a technical team about {topic}. "
                f"Use the approved source '{top.title}' and avoid unsupported certainty."
            ),
            task=(
                "Write a practical explanation that separates confirmed facts, assumptions, "
                "risk levels, and first next actions."
            ),
            difficulty=3,
            expected_behavior=(
                "Use plain language, cite source-backed ideas, avoid hype, and recommend a concrete first step."
            ),
            failure_trap=(
                "Making confident claims that do not appear in the approved sources."
            ),
            source_ids=source_ids,
        )

    def generate_package(
        self,
        topic: str,
        search_results: list[SearchResult],
        difficulty: int = 3,
        task_format: str = "architecture_review",
        audience: str = "engineer",
        model_router: ModelRouter | None = None,
    ) -> GeneratedLessonPackage:
        """Generate a complete lesson package from retrieved sources.

        Fails closed if no search results are provided.
        """
        if not search_results:
            trace = GenerationTrace(
                topic=topic,
                difficulty=difficulty,
                task_format=task_format,
                timestamp="",
                fail_closed_reason="Cannot generate lesson package without sources.",
            )
            return GeneratedLessonPackage(
                topic=topic,
                level=DIFFICULTY_LEVEL.get(difficulty, "intermediate"),
                generation_trace=trace,
            )

        source_ids = list({r.source_id for r in search_results})
        chunk_ids = [r.chunk_id for r in search_results]
        level = DIFFICULTY_LEVEL.get(difficulty, "intermediate")

        # Generate scenario
        scenario_gen = ScenarioGenerator()
        scenario = scenario_gen.generate(
            topic=topic,
            search_results=search_results,
            difficulty=difficulty,
            task_format=task_format,
            audience=audience,
        )

        # Generate lesson content
        top = search_results[0]
        lesson = self._generate_lesson_content(
            topic=topic,
            search_results=search_results,
            source_ids=source_ids,
            chunk_ids=chunk_ids,
        )

        # Generate claim candidates
        claim_candidates = self._extract_claim_candidates(
            lesson=lesson,
            search_results=search_results,
        )

        # Generate trace
        trace = GenerationTrace(
            generation_backend="deterministic_local",
            prompt_version="v1.0",
            topic=topic,
            difficulty=difficulty,
            task_format=task_format,
            source_ids=source_ids,
            chunk_ids=chunk_ids,
        )

        # Update trace with model router info if available
        if model_router is not None:
            trace = model_router.update_generation_trace(trace)

        return GeneratedLessonPackage(
            topic=topic,
            level=level,
            scenario=scenario,
            lesson=lesson,
            source_ids=source_ids,
            chunk_ids=chunk_ids,
            generation_trace=trace,
            claim_candidates=claim_candidates,
        )

    def _generate_lesson_content(
        self,
        topic: str,
        search_results: list[SearchResult],
        source_ids: list[str],
        chunk_ids: list[str],
    ) -> GeneratedLesson:
        """Generate lesson content from search results."""
        top = search_results[0]
        source_previews = [r.text_preview for r in search_results[:3]]

        learning_objectives = [
            f"Understand the core concepts of {topic} as described in approved sources",
            f"Identify practical next steps for {topic} implementation",
            f"Separate confirmed facts from assumptions in {topic} discussions",
        ]

        required_concepts = []
        for preview in source_previews:
            # Extract key phrases from source previews
            words = preview.split()[:15]
            if words:
                required_concepts.append(" ".join(words))

        task_instructions = (
            f"Based on the approved sources about {topic}, write a practical explanation "
            f"that: (1) separates confirmed facts from assumptions, (2) identifies risk levels, "
            f"(3) recommends concrete first next actions, and (4) avoids unsupported certainty. "
            f"Reference specific source material where possible."
        )

        expected_qualities = [
            "Cites source-backed ideas with source IDs",
            "Uses plain language without hype",
            "Recommends concrete first steps",
            "Distinguishes facts from assumptions",
        ]

        failure_traps = [
            f"Making confident claims about {topic} that do not appear in approved sources",
            "Omitting source citations for key assertions",
            "Conflating short-term operational risk with long-term strategic risk",
        ]

        return GeneratedLesson(
            title=f"Source-grounded lab: {topic}",
            learning_objectives=learning_objectives,
            required_source_concepts=required_concepts,
            task_instructions=task_instructions,
            expected_answer_qualities=expected_qualities,
            failure_traps=failure_traps,
            source_ids=source_ids,
            chunk_ids=chunk_ids,
        )

    def _extract_claim_candidates(
        self,
        lesson: GeneratedLesson,
        search_results: list[SearchResult],
    ) -> list[ClaimCandidate]:
        """Extract claim candidates from the generated lesson for verification."""
        claims = []

        # Claim: lesson is based on approved sources
        if search_results:
            top = search_results[0]
            claims.append(
                ClaimCandidate(
                    claim="The lesson is based on approved retrieved sources.",
                    source_id=top.source_id,
                    chunk_id=top.chunk_id,
                    trust_tier=top.trust_tier,
                    severity="medium",
                )
            )

        # Claims from learning objectives
        for i, objective in enumerate(lesson.learning_objectives):
            sr = search_results[i % len(search_results)] if search_results else None
            claims.append(
                ClaimCandidate(
                    claim=objective,
                    source_id=sr.source_id if sr else None,
                    chunk_id=sr.chunk_id if sr else None,
                    trust_tier=sr.trust_tier if sr else None,
                    severity="medium",
                )
            )

        # Claims from expected answer qualities
        for quality in lesson.expected_answer_qualities:
            sr = search_results[0] if search_results else None
            claims.append(
                ClaimCandidate(
                    claim=quality,
                    source_id=sr.source_id if sr else None,
                    chunk_id=sr.chunk_id if sr else None,
                    trust_tier=sr.trust_tier if sr else None,
                    severity="low",
                )
            )

        return claims
