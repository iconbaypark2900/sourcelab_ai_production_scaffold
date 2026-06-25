"""Answer scoring golden eval for SourceLab AI.

Instruction:
- Evaluate answer scoring against golden test cases.
- Strong answers should score higher than weak answers.
- Unsupported answers should trigger review.
- Uses source pack eval fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

from sourcelab.core.models import AnswerReview
from sourcelab.evals.schemas import GoldenEvalFailure, GoldenEvalReport
from sourcelab.learning.schemas import AnswerReviewV2


def normalize_answer_score_result(review: AnswerReview | AnswerReviewV2) -> dict:
    """Normalize legacy or v2 answer reviews into eval score dicts."""
    if isinstance(review, AnswerReviewV2):
        breakdown = {
            "topic_relevance": review.source_grounding_score,
            "source_grounding": review.source_grounding_score,
            "practical_reasoning": review.rubric_alignment_score,
            "uncertainty_control": review.uncertainty_control_score,
            "trap_avoidance": review.trap_avoidance_score,
        }
        return {
            "overall_score": review.overall_score,
            "needs_review": review.needs_review,
            "breakdown": breakdown,
            "strengths": review.strengths,
            "weaknesses": review.weaknesses,
        }

    if isinstance(review, AnswerReview):
        needs_review = review.score < 0.25
        feedback_lower = review.feedback.lower()
        if any(
            marker in feedback_lower
            for marker in ("unsupported", "high-risk", "too brief", "lacks source grounding")
        ):
            needs_review = True
        return {
            "overall_score": review.score,
            "needs_review": needs_review,
            "breakdown": review.breakdown,
            "strengths": [review.feedback] if review.score >= 0.75 else [],
            "weaknesses": [review.feedback] if review.score < 0.5 else [],
        }

    raise TypeError(f"Unsupported answer review type: {type(review)!r}")


def load_answer_gold_cases(project_root: Path, pack_name: str) -> list[dict]:
    """Load answer golden eval cases from source pack."""
    eval_path = project_root / "data" / "source_packs" / pack_name / "evals" / "answer_gold.json"
    if not eval_path.exists():
        return []

    try:
        data = json.loads(eval_path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("cases", [])
    except (json.JSONDecodeError, KeyError):
        return []


def run_answer_gold_eval(
    project_root: Path,
    pack_name: str,
    score_fn,
) -> GoldenEvalReport:
    """Run answer scoring golden eval.

    Args:
        project_root: Project root directory.
        pack_name: Source pack name.
        score_fn: Function that takes (answer_text, topic) and returns dict with
                  'overall_score', 'needs_review', and optional 'breakdown'.

    Returns:
        GoldenEvalReport with pass/fail status.
    """
    cases = load_answer_gold_cases(project_root, pack_name)
    total = len(cases)
    passed = 0
    failures = []

    # Track scores by quality for comparison
    quality_scores: dict[str, list[float]] = {}

    for idx, case in enumerate(cases):
        answer = case.get("answer", "")
        topic = case.get("topic", "")
        expected_min = case.get("expected_min_score", 0.0)
        expected_max = case.get("expected_max_score", 1.0)
        expected_quality = case.get("expected_quality", "weak")
        should_review = case.get("should_trigger_review", False)
        description = case.get("description", f"Case {idx + 1}")

        if not answer or not topic:
            failures.append(GoldenEvalFailure(
                case_index=idx,
                case_description=description,
                expected="Non-empty answer and topic",
                actual="Empty answer or topic",
                details="Invalid test case configuration",
            ))
            continue

        try:
            result = score_fn(answer, topic)
            actual_score = result.get("overall_score", 0.0)
            actual_review = result.get("needs_review", False)

            # Track scores by quality
            if expected_quality not in quality_scores:
                quality_scores[expected_quality] = []
            quality_scores[expected_quality].append(actual_score)

            # Check score range
            if actual_score < expected_min or actual_score > expected_max:
                failures.append(GoldenEvalFailure(
                    case_index=idx,
                    case_description=description,
                    expected=f"Score in range [{expected_min}, {expected_max}]",
                    actual=f"Score: {actual_score:.3f}",
                    details=f"Quality: {expected_quality}",
                ))
                continue

            # Check review trigger
            if should_review and not actual_review:
                failures.append(GoldenEvalFailure(
                    case_index=idx,
                    case_description=description,
                    expected="Review triggered",
                    actual="No review triggered",
                    details=f"Score: {actual_score:.3f}, Quality: {expected_quality}",
                ))
                continue

            passed += 1

        except Exception as e:
            failures.append(GoldenEvalFailure(
                case_index=idx,
                case_description=description,
                expected="Successful scoring",
                actual=f"Exception: {e}",
                details=str(e),
            ))

    # Check quality ordering (strong > weak)
    if "strong" in quality_scores and "weak" in quality_scores:
        avg_strong = sum(quality_scores["strong"]) / len(quality_scores["strong"])
        avg_weak = sum(quality_scores["weak"]) / len(quality_scores["weak"])
        if avg_strong <= avg_weak:
            failures.append(GoldenEvalFailure(
                case_index=-1,
                case_description="Quality ordering check",
                expected=f"Strong answers ({avg_strong:.3f}) score higher than weak ({avg_weak:.3f})",
                actual=f"Strong avg: {avg_strong:.3f}, Weak avg: {avg_weak:.3f}",
                details="Quality ordering violation",
            ))

    pass_rate = passed / total if total > 0 else 0.0

    return GoldenEvalReport(
        eval_name="answer_gold",
        pack_name=pack_name,
        total_cases=total,
        passed_cases=passed,
        failed_cases=len(failures),
        pass_rate=pass_rate,
        failures=failures,
    )
