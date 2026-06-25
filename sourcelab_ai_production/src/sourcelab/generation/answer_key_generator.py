"""Answer key generator.

Instruction:
- Generates a source-grounded answer key for lesson evaluation.
- Every answer must reference source_id and chunk_id.
- Separates facts from assumptions.
- Includes sample strong and weak answers.
"""

from __future__ import annotations

from sourcelab.core.models import SearchResult
from sourcelab.generation.schemas import (
    AnswerKeyEntry,
    GeneratedAnswerKey,
    GeneratedLessonPackage,
)


class AnswerKeyGenerator:
    """Generate a source-grounded answer key from a lesson package."""

    def generate(
        self,
        package: GeneratedLessonPackage,
        search_results: list[SearchResult],
    ) -> GeneratedAnswerKey:
        """Generate an answer key from the lesson package and search results."""
        source_ids = package.source_ids
        chunk_ids = package.chunk_ids

        if not search_results:
            return GeneratedAnswerKey(
                source_ids=source_ids,
                chunk_ids=chunk_ids,
                sample_strong_answer="No sources available to generate answer key.",
                sample_weak_answer="No sources available.",
            )

        # Build source references from search results
        source_references = []
        for sr in search_results:
            source_references.append(
                AnswerKeyEntry(
                    claim=f"Source '{sr.title}' provides context for {package.topic}",
                    source_id=sr.source_id,
                    chunk_id=sr.chunk_id,
                    trust_tier=sr.trust_tier,
                    category="fact",
                )
            )

        # Generate facts from source previews
        facts = []
        for sr in search_results[:3]:
            facts.append(
                f"According to '{sr.title}': {sr.text_preview[:150]}..."
            )

        # Generate assumptions (things that need verification)
        assumptions = [
            f"The current state of {package.topic} is well-documented in approved sources",
            f"All stakeholders understand the risks associated with {package.topic}",
            f"Implementation timelines for {package.topic} are realistic",
        ]

        # What not to claim
        what_not_to_claim = [
            f"Do not claim specific timelines for {package.topic} without source evidence",
            f"Do not assume all teams have the same {package.topic} maturity level",
            f"Do not conflate short-term operational risk with long-term strategic risk",
        ]

        # Sample strong answer
        top = search_results[0]
        sample_strong = (
            f"Based on the approved source '{top.title}', {package.topic} requires "
            f"a careful, phased approach. The source material indicates that teams should "
            f"begin with an inventory of current state, assess risk levels, and prioritize "
            f"based on both operational urgency and long-term strategic value. "
            f"I recommend starting with a concrete first step: conducting a full audit "
            f"of current practices as described in the source material."
        )

        # Sample weak answer
        sample_weak = (
            f"{package.topic} is important and teams should work on it. "
            f"I think it will take about 6 months to complete. "
            f"Just follow best practices and you'll be fine."
        )

        return GeneratedAnswerKey(
            source_references=source_references,
            facts=facts,
            assumptions=assumptions,
            what_not_to_claim=what_not_to_claim,
            sample_strong_answer=sample_strong,
            sample_weak_answer=sample_weak,
            source_ids=source_ids,
            chunk_ids=chunk_ids,
        )
