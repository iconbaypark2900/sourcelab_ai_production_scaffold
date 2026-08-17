"""Answer scorer v2 with optional LLM judge integration.

Instruction:
- Production should combine rubric heuristics with an LLM judge and source-citation checks.
- Always return a visible score breakdown.
- v2 adds: rubric-based scoring, source grounding check, uncertainty control, trap avoidance.
- LLM judge blends LLM rubric scores with heuristic scores when enabled.
- Scoring is deterministic using token overlap, marker detection, and rubric criteria.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sourcelab.core.models import AnswerReview, LessonTask, SearchResult
from sourcelab.generation.schemas import GeneratedLessonPackage, GeneratedRubric
from sourcelab.learning.schemas import (
    AnswerReviewV2,
    AnswerScoreBreakdown,
    RubricCriterionScore,
)
from sourcelab.models.prompts import PromptTemplates
from sourcelab.models.schemas import ModelRequest, ModelResponse


WORD_RE = re.compile(r"[a-zA-Z0-9_\-]+")


def words(text: str) -> set[str]:
    """Extract words from text, filtering short words."""
    result: set[str] = set()
    for token in WORD_RE.findall(text):
        lowered = token.lower()
        if len(lowered) > 3:
            result.add(lowered)
        for part in lowered.split("-"):
            if len(part) > 3:
                result.add(part)
    return result


TOPIC_ALIASES = {
    "cryptography": {"pqc", "crypto", "encryption", "symmetric", "algorithms"},
    "migration": {"migrate", "transition", "inventory", "plan"},
    "agility": {"swap", "flexible", "algorithm"},
    "exchange": {"hybrid", "ecdh", "ml-kem", "kem"},
}


# Marker sets for heuristic scoring
PRACTICAL_MARKERS = {
    "first", "step", "identify", "inventory", "assess", "plan",
    "migrate", "deploy", "implement", "configure", "review", "audit",
    "prioritize", "categorize", "catalog", "document", "test", "validate",
}

UNCERTAINTY_MARKERS = {
    "avoid", "evidence", "risk", "assumption", "uncertain", "unclear",
    "likely", "possible", "may", "might", "could", "speculative",
    "unknown", "depends", "estimate", "approximately", "roughly",
}

TRAP_MARKERS = {
    "avoid", "trap", "pitfall", "mistake", "error", "wrong",
    "incorrect", "false", "misleading", "unsupported", "claim",
    "fact", "fiction", "myth", "reality", "truth",
}

CITATION_MARKERS = {
    "source", "reference", "cite", "according", "based",
    "evidence", "study", "research", "document", "standard",
    "guideline", "recommendation", "specification", "rfc", "nist",
}

TECHNICAL_MARKERS = {"ml-kem", "ecdh", "kdf", "concatenation", "hybrid", "ml-dsa", "slh-dsa"}

DISMISSIVE_PHRASES = (
    "not urgent",
    "years away",
    "wait until",
    "no point",
    "no need to worry",
)

# High-risk unsupported statement patterns
HIGH_RISK_PATTERNS = [
    re.compile(r"will (be |)broken? (by |with |)quantum", re.IGNORECASE),
    re.compile(r"quantum (computers? )?(\w+\s+){0,4}(break|crack)", re.IGNORECASE),
    re.compile(r"(definitely|certainly|guaranteed|always) (true|safe|secure)", re.IGNORECASE),
    re.compile(r"(never|impossible) (to |)(break|crack|compromise)", re.IGNORECASE),
    re.compile(r"remove (all |every )?(rsa|ecc|classical)", re.IGNORECASE),
    re.compile(r"ignore nist", re.IGNORECASE),
    re.compile(r"(scam|overhyped|conspiracy)", re.IGNORECASE),
    re.compile(r"drop-in replacements with no compatibility", re.IGNORECASE),
    re.compile(r"implement ml-kem everywhere", re.IGNORECASE),
    re.compile(r"ignore hybrid", re.IGNORECASE),
    re.compile(r"guaranteed to (always )?work in production", re.IGNORECASE),
]

RISK_REVIEW_CAP_SCORE = 0.09
DEFAULT_CRITERION_WEIGHTS = {
    "topic_relevance": 0.20,
    "source_grounding": 0.25,
    "practical_reasoning": 0.20,
    "uncertainty_control": 0.15,
    "trap_avoidance": 0.10,
    "clarity": 0.05,
    "citation_use_of_evidence": 0.05,
}


LLM_JUDGE_CRITERIA = [
    "topic_relevance",
    "source_grounding",
    "practical_reasoning",
    "uncertainty_control",
    "trap_avoidance",
    "clarity",
    "citation_use_of_evidence",
]


class AnswerScorer:
    """Score learner answers against the generated rubric.

    Supports optional LLM judge integration. When ``enable_llm_judge`` is
    True and a ``model_router`` is provided, each criterion score is blended
    between the heuristic score and the LLM judge score:

        blended = llm_judge_blend * llm_score + (1 - llm_judge_blend) * heuristic_score

    If the LLM judge fails (timeout, parse error, invalid JSON), a warning
    is recorded and the pure heuristic score is used for that criterion.
    """

    def __init__(
        self,
        enable_llm_judge: bool = False,
        llm_judge_blend: float = 0.5,
        model_router: Any = None,
    ):
        self._enable_llm_judge = enable_llm_judge
        self._llm_judge_blend = max(0.0, min(1.0, llm_judge_blend))
        self._model_router = model_router

    def score(
        self,
        topic: str,
        task: LessonTask,
        answer: str,
        search_results: list[SearchResult],
        rubric: GeneratedRubric | None = None,
        package: GeneratedLessonPackage | None = None,
    ) -> AnswerReview:
        """Score an answer using rubric-based heuristics.

        Maintains backward compatibility with the original AnswerReview schema.
        """
        answer_words = words(answer)
        topic_words = words(topic)
        source_words = set()
        for result in search_results:
            source_words |= words(result.text_preview)

        # Compute individual criterion scores
        topic_score = self._score_topic_relevance(answer_words, topic_words)
        source_score = self._score_source_grounding(answer_words, source_words, answer)
        practicality = self._score_practical_reasoning(answer_words, answer)
        uncertainty = self._score_uncertainty_control(answer_words, answer)
        trap_score = self._score_trap_avoidance(answer_words, answer)
        clarity_score = self._score_clarity(answer)
        citation_score = self._score_citation_use(answer_words, answer)

        # Weighted total
        total = round(
            min(
                1.0,
                0.20 * topic_score
                + 0.25 * source_score
                + 0.20 * practicality
                + 0.15 * uncertainty
                + 0.10 * trap_score
                + 0.05 * clarity_score
                + 0.05 * citation_score,
            ),
            4,
        )

        # Build breakdown dict for backward compatibility
        breakdown = {
            "topic_relevance": round(topic_score, 4),
            "source_grounding": round(source_score, 4),
            "practicality": round(practicality, 4),
            "uncertainty_control": round(uncertainty, 4),
            "trap_avoidance": round(trap_score, 4),
            "clarity": round(clarity_score, 4),
            "citation_use_of_evidence": round(citation_score, 4),
        }

        feedback = self._generate_feedback(total, breakdown, answer_words)

        return AnswerReview(
            topic=topic,
            score=total,
            breakdown=breakdown,
            feedback=feedback,
            next_recommendation="Increase difficulty" if total >= 0.75 else "Provide more guidance",
        )

    def score_v2(
        self,
        topic: str,
        answer: str,
        search_results: list[SearchResult],
        rubric: GeneratedRubric | None = None,
        package: GeneratedLessonPackage | None = None,
        run_id: str = "",
    ) -> AnswerReviewV2:
        """Score an answer with full rubric-based breakdown.

        Returns the v2 review with criterion scores, strengths, weaknesses, etc.
        """
        answer_words = words(answer)
        topic_words = words(topic)
        source_words = set()
        for result in search_results:
            source_words |= words(result.text_preview)

        # Compute individual criterion scores
        topic_score = self._score_topic_relevance(answer_words, topic_words)
        source_score = self._score_source_grounding(answer_words, source_words, answer)
        practicality = self._score_practical_reasoning(answer_words, answer)
        uncertainty = self._score_uncertainty_control(answer_words, answer)
        trap_score = self._score_trap_avoidance(answer_words, answer)
        clarity_score = self._score_clarity(answer)
        citation_score = self._score_citation_use(answer_words, answer)

        heuristic_scores = {
            "topic_relevance": topic_score,
            "source_grounding": source_score,
            "practical_reasoning": practicality,
            "uncertainty_control": uncertainty,
            "trap_avoidance": trap_score,
            "clarity": clarity_score,
            "citation_use_of_evidence": citation_score,
        }

        # Optional LLM judge — blend scores if available
        llm_judge_used = False
        llm_judge_warnings: list[str] = []
        llm_blended_score: float | None = None
        llm_feedback_text = ""
        llm_strengths_extras: list[str] = []
        llm_weaknesses_extras: list[str] = []

        if self._enable_llm_judge:
            llm_scores, jw, jf, js, jw2 = self._llm_judge(
                topic, answer, search_results, rubric
            )
            llm_judge_warnings = jw

            if llm_scores is not None:
                llm_judge_used = True
                llm_feedback_text = jf
                llm_strengths_extras = js
                llm_weaknesses_extras = jw2
                b = self._llm_judge_blend
                for name in LLM_JUDGE_CRITERIA:
                    h = heuristic_scores.get(name, 0.5)
                    l = llm_scores.get(name, h)
                    heuristic_scores[name] = round(b * l + (1.0 - b) * h, 4)

                raw_blended = (
                    b * sum(llm_scores.get(n, 0.5) for n in LLM_JUDGE_CRITERIA)
                    + (1.0 - b)
                    * sum(heuristic_scores.get(n, 0.5) for n in LLM_JUDGE_CRITERIA)
                ) / len(LLM_JUDGE_CRITERIA)
                llm_blended_score = round(min(1.0, raw_blended), 4)

        if not llm_judge_used:
            llm_judge_warnings = [w for w in llm_judge_warnings if "No model_router" not in w]

        topic_score = heuristic_scores["topic_relevance"]
        source_score = heuristic_scores["source_grounding"]
        practicality = heuristic_scores["practical_reasoning"]
        uncertainty = heuristic_scores["uncertainty_control"]
        trap_score = heuristic_scores["trap_avoidance"]
        clarity_score = heuristic_scores["clarity"]
        citation_score = heuristic_scores["citation_use_of_evidence"]

        # Build criterion scores from rubric
        criterion_scores = []
        if rubric and rubric.criteria:
            score_map = {
                "topic_relevance": topic_score,
                "source_grounding": source_score,
                "practical_reasoning": practicality,
                "uncertainty_control": uncertainty,
                "trap_avoidance": trap_score,
                "clarity": clarity_score,
                "citation_use_of_evidence": citation_score,
            }
            for criterion in rubric.criteria:
                criterion_score_val = score_map.get(criterion.name, 0.5)
                cs = RubricCriterionScore(
                    criterion_name=criterion.name,
                    weight=criterion.weight,
                    score=round(criterion_score_val, 4),
                    evidence=self._get_criterion_evidence(criterion.name, answer_words, source_words, answer),
                    feedback=self._get_criterion_feedback(criterion.name, criterion_score_val),
                )
                if llm_judge_used and llm_scores is not None:
                    cs.llm_score = round(llm_scores.get(criterion.name, criterion_score_val), 4)
                    cs.llm_feedback = llm_feedback_text
                criterion_scores.append(cs)

        # Weighted rubric average before any risk cap
        rubric_alignment_score = self._compute_rubric_alignment(
            criterion_scores=criterion_scores,
            topic_score=topic_score,
            source_score=source_score,
            practicality=practicality,
            uncertainty=uncertainty,
            trap_score=trap_score,
            clarity_score=clarity_score,
            citation_score=citation_score,
        )

        uncapped_score = rubric_alignment_score
        if source_score >= 0.35 and (CITATION_MARKERS & answer_words):
            uncapped_score = round(min(1.0, uncapped_score + 0.08), 4)

        if len(answer_words) >= 25 and PRACTICAL_MARKERS & answer_words:
            uncapped_score = round(min(1.0, uncapped_score + 0.05), 4)

        if practicality >= 0.55 and source_score >= 0.2:
            uncapped_score = round(min(1.0, uncapped_score + 0.07), 4)

        if len(answer.split()) >= 12 and topic_score >= 0.1:
            uncapped_score = round(min(1.0, uncapped_score + 0.04), 4)

        if len(answer_words & TECHNICAL_MARKERS) >= 2:
            uncapped_score = round(min(1.0, uncapped_score + 0.05), 4)

        if any(phrase in answer.lower() for phrase in DISMISSIVE_PHRASES):
            uncapped_score = round(max(0.0, uncapped_score - 0.06), 4)

        # Check for unsupported high-risk statements
        needs_review, review_reason = self._check_high_risk(answer)
        cap_reason = ""
        if needs_review:
            cap_reason = review_reason
            overall_score = round(min(uncapped_score, RISK_REVIEW_CAP_SCORE), 4)
        else:
            overall_score = uncapped_score

        # Identify strengths and weaknesses
        breakdown = AnswerScoreBreakdown(
            topic_relevance=round(topic_score, 4),
            source_grounding=round(source_score, 4),
            practical_reasoning=round(practicality, 4),
            uncertainty_control=round(uncertainty, 4),
            trap_avoidance=round(trap_score, 4),
            clarity=round(clarity_score, 4),
            citation_use_of_evidence=round(citation_score, 4),
        )
        strengths, weaknesses = self._identify_strengths_weaknesses(breakdown)
        if llm_strengths_extras:
            strengths.extend(llm_strengths_extras)
        if llm_weaknesses_extras:
            weaknesses.extend(llm_weaknesses_extras)

        recommended_focus = self._determine_recommended_focus(breakdown, weaknesses)

        answer_id = f"answer_{uuid.uuid4().hex[:12]}"

        return AnswerReviewV2(
            answer_id=answer_id,
            topic=topic,
            run_id=run_id,
            overall_score=overall_score,
            criterion_scores=criterion_scores,
            source_grounding_score=round(source_score, 4),
            rubric_alignment_score=rubric_alignment_score,
            uncapped_score=uncapped_score,
            cap_reason=cap_reason,
            uncertainty_control_score=round(uncertainty, 4),
            trap_avoidance_score=round(trap_score, 4),
            strengths=strengths,
            weaknesses=weaknesses,
            recommended_focus=recommended_focus,
            needs_review=needs_review,
            review_reason=review_reason,
            llm_judge_used=llm_judge_used,
            llm_judge_warnings=llm_judge_warnings,
            llm_blended_score=llm_blended_score,
        )

    def _compute_rubric_alignment(
        self,
        criterion_scores: list[RubricCriterionScore],
        topic_score: float,
        source_score: float,
        practicality: float,
        uncertainty: float,
        trap_score: float,
        clarity_score: float,
        citation_score: float,
    ) -> float:
        """Compute the weighted rubric average before any risk cap."""
        if criterion_scores:
            weighted = sum(criterion.weight * criterion.score for criterion in criterion_scores)
            return round(min(1.0, weighted), 4)

        score_map = {
            "topic_relevance": topic_score,
            "source_grounding": source_score,
            "practical_reasoning": practicality,
            "uncertainty_control": uncertainty,
            "trap_avoidance": trap_score,
            "clarity": clarity_score,
            "citation_use_of_evidence": citation_score,
        }
        weighted = sum(
            DEFAULT_CRITERION_WEIGHTS[name] * score_map[name]
            for name in DEFAULT_CRITERION_WEIGHTS
        )
        return round(min(1.0, weighted), 4)

    def _score_topic_relevance(self, answer_words: set[str], topic_words: set[str]) -> float:
        """Score how relevant the answer is to the topic."""
        if not topic_words:
            return 0.0

        expanded_topic = set(topic_words)
        for term in topic_words:
            for alias_key, aliases in TOPIC_ALIASES.items():
                if alias_key in term:
                    expanded_topic |= aliases

        overlap = len(answer_words & expanded_topic)
        return min(1.0, overlap / max(1, len(topic_words)))

    def _score_source_grounding(self, answer_words: set[str], source_words: set[str], answer: str) -> float:
        """Score how well the answer is grounded in sources."""
        if not source_words:
            return 0.0
        overlap = len(answer_words & source_words)
        score = min(1.0, overlap / max(1, min(len(source_words), 40)))

        # Boost for explicit source references
        if any(marker in answer.lower() for marker in ["source", "reference", "according to", "based on"]):
            score = min(1.0, score + 0.15)

        return score

    def _score_practical_reasoning(self, answer_words: set[str], answer: str) -> float:
        """Score practical reasoning quality."""
        has_practical = bool(PRACTICAL_MARKERS & answer_words)
        has_steps = any(marker in answer.lower() for marker in ["step 1", "step 2", "first", "second", "third"])
        has_specifics = len(answer_words) > 30  # Longer answers tend to be more specific

        score = 0.3
        if has_practical:
            score += 0.3
        if has_steps:
            score += 0.2
        if has_specifics:
            score += 0.2
        return min(1.0, score)

    def _score_uncertainty_control(self, answer_words: set[str], answer: str) -> float:
        """Score how well the answer handles uncertainty."""
        has_uncertainty = bool(UNCERTAINTY_MARKERS & answer_words)
        has_avoidance = any(marker in answer.lower() for marker in ["avoid", "should not", "must not"])
        has_caveats = any(marker in answer.lower() for marker in ["caveat", "limitation", "however", "but"])

        score = 0.3
        if has_uncertainty:
            score += 0.3
        if has_avoidance:
            score += 0.2
        if has_caveats:
            score += 0.2
        return min(1.0, score)

    def _score_trap_avoidance(self, answer_words: set[str], answer: str) -> float:
        """Score how well the answer avoids failure traps."""
        has_trap_awareness = bool(TRAP_MARKERS & answer_words)
        has_caveats = any(marker in answer.lower() for marker in ["without evidence", "unsupported", "assumption"])

        score = 0.3
        if has_trap_awareness:
            score += 0.35
        if has_caveats:
            score += 0.35
        return min(1.0, score)

    def _score_clarity(self, answer: str) -> float:
        """Score answer clarity."""
        sentences = [s.strip() for s in re.split(r"[.!?]+", answer) if s.strip()]
        avg_length = sum(len(s.split()) for s in sentences) / max(1, len(sentences))
        has_structure = any(marker in answer.lower() for marker in ["##", "###", "-", "1.", "2."])

        score = 0.3
        if 10 <= avg_length <= 30:  # Good sentence length
            score += 0.3
        if has_structure:
            score += 0.2
        if len(answer) > 100:  # Not too short
            score += 0.2
        return min(1.0, score)

    def _score_citation_use(self, answer_words: set[str], answer: str) -> float:
        """Score citation and evidence use."""
        has_citations = bool(CITATION_MARKERS & answer_words)
        has_evidence = any(marker in answer.lower() for marker in ["evidence", "according", "research", "data"])

        score = 0.2
        if has_citations:
            score += 0.4
        if has_evidence:
            score += 0.4
        return min(1.0, score)

    def _generate_feedback(self, total: float, breakdown: dict, answer_words: set[str]) -> str:
        """Generate human-readable feedback."""
        if total >= 0.8:
            return "Excellent answer with strong source grounding and practical reasoning."
        elif total >= 0.6:
            weakest = min(breakdown, key=breakdown.get)
            return f"Good answer. Consider strengthening {weakest.replace('_', ' ')}."
        elif total >= 0.4:
            return "Answer needs more source-grounded detail and practical next steps."
        else:
            return "Answer is too brief or lacks source grounding. Provide more specific, evidence-based content."

    def _get_criterion_evidence(self, criterion_name: str, answer_words: set[str], source_words: set[str], answer: str) -> str:
        """Get evidence for a specific criterion score."""
        if criterion_name == "topic_relevance":
            overlap = answer_words & source_words
            return f"Topic term overlap: {len(overlap)} words"
        elif criterion_name == "source_grounding":
            overlap = answer_words & source_words
            return f"Source concept overlap: {len(overlap)} terms"
        elif criterion_name == "practical_reasoning":
            return "Practical markers detected" if PRACTICAL_MARKERS & answer_words else "No practical markers found"
        elif criterion_name == "uncertainty_control":
            return "Uncertainty markers detected" if UNCERTAINTY_MARKERS & answer_words else "No uncertainty markers found"
        elif criterion_name == "trap_avoidance":
            return "Trap awareness detected" if TRAP_MARKERS & answer_words else "No trap awareness detected"
        elif criterion_name == "clarity":
            return "Structured content" if "##" in answer or "-" in answer else "Unstructured content"
        elif criterion_name == "citation_use_of_evidence":
            return "Citation markers detected" if CITATION_MARKERS & answer_words else "No citation markers found"
        return ""

    def _get_criterion_feedback(self, criterion_name: str, score: float) -> str:
        """Get feedback for a specific criterion score."""
        if score >= 0.75:
            return f"Strong {criterion_name.replace('_', ' ')}"
        elif score >= 0.5:
            return f"Adequate {criterion_name.replace('_', ' ')} - room for improvement"
        else:
            return f"Weak {criterion_name.replace('_', ' ')} - needs attention"

    def _identify_strengths_weaknesses(self, breakdown: AnswerScoreBreakdown) -> tuple[list[str], list[str]]:
        """Identify strengths and weaknesses from the breakdown."""
        strengths = []
        weaknesses = []

        scores = {
            "topic_relevance": breakdown.topic_relevance,
            "source_grounding": breakdown.source_grounding,
            "practical_reasoning": breakdown.practical_reasoning,
            "uncertainty_control": breakdown.uncertainty_control,
            "trap_avoidance": breakdown.trap_avoidance,
            "clarity": breakdown.clarity,
            "citation_use_of_evidence": breakdown.citation_use_of_evidence,
        }

        for name, score in scores.items():
            readable = name.replace("_", " ")
            if score >= 0.7:
                strengths.append(f"Strong {readable}")
            elif score < 0.4:
                weaknesses.append(f"Weak {readable}")

        return strengths, weaknesses

    def _check_high_risk(self, answer: str) -> tuple[bool, str]:
        """Check for unsupported high-risk statements."""
        citation_spans = self._citation_spans(answer)
        for pattern in HIGH_RISK_PATTERNS:
            match = pattern.search(answer)
            if match and not self._overlaps_any(match, citation_spans) and not self._is_negated_claim(answer, match):
                return True, f"Contains potentially unsupported high-risk statement: {pattern.pattern}"
        return False, ""

    def _citation_spans(self, answer: str) -> list[tuple[int, int]]:
        """Return (start, end) spans of citation constructs.

        Citations are the opposite of unsupported claims, so a high-risk
        phrase inside a single-quoted source title (``'Title'``) or a
        bracketed source id (``[source_id]``) is not an unsupported claim.
        """
        spans: list[tuple[int, int]] = []
        for match in re.finditer(r"'([^']{1,80})'", answer):
            spans.append((match.start(), match.end()))
        for match in re.finditer(r"\[([^\]]{1,80})\]", answer):
            spans.append((match.start(), match.end()))
        return spans

    @staticmethod
    def _overlaps_any(match: re.Match[str], spans: list[tuple[int, int]]) -> bool:
        start, end = match.start(), match.end()
        return any(span_start <= start < span_end or span_start < end <= span_end
                   for span_start, span_end in spans)

    def _is_negated_claim(self, answer: str, match: re.Match[str]) -> bool:
        """Return True when the matched span is a negated or cautionary claim."""
        window = answer[max(0, match.start() - 24): match.end()].lower()
        negation_markers = (
            "cannot ",
            "can't ",
            "can not ",
            "do not ",
            "don't ",
            "does not ",
            "doesn't ",
            "will not ",
            "won't ",
            " not ",
            "avoid claiming ",
            "avoid ",
            "without evidence",
            "no evidence ",
        )
        return any(marker in window for marker in negation_markers)

    def _determine_recommended_focus(self, breakdown: AnswerScoreBreakdown, weaknesses: list[str]) -> str:
        """Determine recommended focus area."""
        if breakdown.source_grounding < 0.4:
            return "source-grounded fundamentals with explicit source references"
        elif breakdown.uncertainty_control < 0.4:
            return "separating facts from assumptions with uncertainty labels"
        elif breakdown.trap_avoidance < 0.4:
            return "failure-trap recognition and avoidance strategies"
        elif breakdown.practical_reasoning < 0.4:
            return "practical step-by-step reasoning with specific actions"
        elif weaknesses:
            return weaknesses[0].lower().replace("weak ", "")
        else:
            return "maintain current level and increase difficulty"

    def _build_judge_prompt(
        self,
        topic: str,
        answer: str,
        rubric: GeneratedRubric | None,
        search_results: list[SearchResult],
    ) -> str:
        rubric_text_lines: list[str] = []
        if rubric and rubric.criteria:
            for c in rubric.criteria:
                rubric_text_lines.append(f"  - {c.name} (weight {c.weight}): {c.description}")
        else:
            for name, weight in DEFAULT_CRITERION_WEIGHTS.items():
                rubric_text_lines.append(f"  - {name} (weight {weight})")

        source_lines: list[str] = []
        source_ids: list[str] = []
        for r in search_results[:5]:
            source_ids.append(r.source_id)
            source_lines.append(f"  [{r.source_id}] {r.text_preview[:200]}")

        rendered = PromptTemplates.render(
            route="answer_judging",
            source_ids=source_ids,
            topic=topic,
            answer=answer,
            rubric_text="\n".join(rubric_text_lines),
            source_context="\n".join(source_lines) if source_lines else "No source context provided.",
        )
        return rendered.prompt

    def _llm_judge(
        self,
        topic: str,
        answer: str,
        search_results: list[SearchResult],
        rubric: GeneratedRubric | None = None,
    ) -> tuple[dict[str, float] | None, list[str], str, list[str], list[str]]:
        """Call the LLM judge and parse per-criterion scores.

        Returns:
            Tuple of (criterion_scores_dict, warnings, feedback, strengths, weaknesses).
            criterion_scores_dict is None if the judge call failed entirely.
        """
        warnings: list[str] = []
        if self._model_router is None:
            return None, ["No model_router provided; LLM judge skipped."], "", [], []

        try:
            prompt = self._build_judge_prompt(topic, answer, rubric, search_results)
            request = ModelRequest(
                prompt=prompt,
                route="answer_judging",
                temperature=0.0,
                max_tokens=2048,
                json_mode=True,
            )
            response: ModelResponse = self._model_router.generate(request)
        except Exception as e:
            return None, [f"LLM judge call failed: {e}"], "", [], []

        if response.raw_error:
            warnings.append(f"LLM judge error: {response.raw_error}")
            if response.deterministic_fallback_used:
                warnings.append("LLM judge used deterministic fallback; scores may not reflect real LLM.")
            if not response.text.strip():
                return None, warnings, "", [], []

        try:
            data = json.loads(response.text)
        except (json.JSONDecodeError, ValueError) as e:
            return None, [f"LLM judge JSON parse failed: {e}"], "", [], []

        criteria_scores = data.get("criteria_scores")
        if not criteria_scores or not isinstance(criteria_scores, dict):
            return None, ["LLM judge response missing 'criteria_scores' field."], "", [], []

        scores: dict[str, float] = {}
        for name in LLM_JUDGE_CRITERIA:
            raw = criteria_scores.get(name)
            if raw is not None and isinstance(raw, (int, float)):
                scores[name] = max(0.0, min(1.0, float(raw)))
            else:
                scores[name] = 0.5

        feedback = str(data.get("feedback", ""))
        strengths = [str(s) for s in data.get("strengths", []) if s]
        weaknesses = [str(w) for w in data.get("weaknesses", []) if w]

        return scores, warnings, feedback, strengths, weaknesses
