"""Source grounding checker for learner answers.

Instruction:
- This module checks how well a learner answer is grounded in the retrieved sources.
- It compares the answer against retrieved chunks, answer key facts, source IDs, and chunk IDs.
- This is separate from lesson claim verification - it's about the learner's answer.
- Return matched source IDs, chunk IDs, terms, unsupported phrases, and a grounding score.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sourcelab.core.models import SearchResult
from sourcelab.generation.schemas import GeneratedAnswerKey, GeneratedLessonPackage
from sourcelab.learning.schemas import SourceGroundingReview


WORD_RE = re.compile(r"[a-zA-Z0-9_\-]+")


def _words(text: str) -> set[str]:
    """Extract meaningful words from text."""
    return {w.lower() for w in WORD_RE.findall(text) if len(w) > 3}


def _extract_ngrams(text: str, n: int = 3) -> set[str]:
    """Extract n-grams from text for phrase matching."""
    words_list = WORD_RE.findall(text.lower())
    words_list = [w for w in words_list if len(w) > 2]
    ngrams = set()
    for i in range(len(words_list) - n + 1):
        ngrams.add(" ".join(words_list[i:i + n]))
    return ngrams


def check_source_grounding(
    answer_text: str,
    search_results: list[SearchResult],
    answer_key: GeneratedAnswerKey | None = None,
    package: GeneratedLessonPackage | None = None,
    topic: str = "",
    answer_id: str = "",
) -> SourceGroundingReview:
    """Check how well a learner answer is grounded in the sources.

    Args:
        answer_text: The learner's answer text.
        search_results: Retrieved source chunks.
        answer_key: Optional answer key with facts and assumptions.
        package: Optional lesson package with source concepts.
        topic: The topic of the lesson.
        answer_id: ID of the answer being reviewed.

    Returns:
        SourceGroundingReview with matched sources, terms, and grounding score.
    """
    answer_words = _words(answer_text)
    answer_ngrams = _extract_ngrams(answer_text)

    # Collect source concepts
    source_words = set()
    source_ngrams = set()
    all_source_ids = set()
    all_chunk_ids = set()

    for result in search_results:
        source_words |= _words(result.text_preview)
        source_ngrams |= _extract_ngrams(result.text_preview)
        all_source_ids.add(result.source_id)
        all_chunk_ids.add(result.chunk_id)

    # Add answer key facts if available
    if answer_key:
        for fact in answer_key.facts:
            source_words |= _words(fact)
            source_ngrams |= _extract_ngrams(fact)
        for ref in answer_key.source_references:
            all_source_ids.add(ref.source_id)
            all_chunk_ids.add(ref.chunk_id)

    # Add lesson package source concepts if available
    if package and package.lesson:
        for concept in package.lesson.required_source_concepts:
            source_words |= _words(concept)
            source_ngrams |= _extract_ngrams(concept)

    # Find matched terms
    matched_words = answer_words & source_words
    matched_ngrams = answer_ngrams & source_ngrams
    matched_terms = sorted(matched_words | matched_ngrams)

    # Find matched source and chunk IDs (by text matching)
    matched_source_ids = []
    matched_chunk_ids = []
    for result in search_results:
        result_words = _words(result.text_preview)
        if answer_words & result_words:
            if result.source_id not in matched_source_ids:
                matched_source_ids.append(result.source_id)
            if result.chunk_id not in matched_chunk_ids:
                matched_chunk_ids.append(result.chunk_id)

    # Find unsupported phrases (3-grams in answer not found in sources)
    unsupported_phrases = sorted(answer_ngrams - source_ngrams)

    # Calculate grounding score
    total_source_concepts = len(source_words) + len(source_ngrams)
    matched_concepts = len(matched_words) + len(matched_ngrams)

    if total_source_concepts == 0:
        grounding_score = 0.0
    else:
        grounding_score = min(1.0, matched_concepts / max(1, total_source_concepts))

    # Boost for matching source IDs
    if all_source_ids and matched_source_ids:
        id_coverage = len(matched_source_ids) / len(all_source_ids)
        grounding_score = min(1.0, grounding_score + 0.1 * id_coverage)

    return SourceGroundingReview(
        answer_id=answer_id,
        topic=topic,
        matched_source_ids=matched_source_ids,
        matched_chunk_ids=matched_chunk_ids,
        matched_terms=matched_terms[:20],  # Limit to top 20
        unsupported_phrases=unsupported_phrases[:10],  # Limit to top 10
        concept_overlap_grounding_score=round(grounding_score, 4),
        total_source_concepts=total_source_concepts,
        matched_source_concepts=matched_concepts,
    )
