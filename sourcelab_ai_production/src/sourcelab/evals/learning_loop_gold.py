"""Golden eval for the full learning loop.

The learning loop eval exercises the entire loop end-to-end:
score -> mastery update -> next-task decision. Known-good answers should
raise topic mastery and increase difficulty / lower guidance; known-bad
answers should lower mastery and increase guidance.

The pipeline sequence is authoritative and matches core/pipeline.py:
    update_from_answer_review -> update_mastery -> select_v2
All three read the post-update profile.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

from .schemas import (
    GoldenEvalFailure,
    GoldenEvalReport,
    LearningLoopGoldCase,
)

logger = logging.getLogger(__name__)


def load_learning_loop_gold_cases(
    project_root: Path, pack_name: str
) -> list[LearningLoopGoldCase]:
    """Load learning-loop golden cases for a source pack."""
    path = (
        project_root
        / "data"
        / "source_packs"
        / pack_name
        / "evals"
        / "learning_loop_gold.json"
    )
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases", data) if isinstance(data, dict) else data
    return [LearningLoopGoldCase(**case) for case in cases]


def run_learning_loop_gold_eval(
    project_root: Path,
    pack_name: str,
    loop_fn: Callable[[str, str], dict],
) -> GoldenEvalReport:
    """Run the learning-loop golden eval.

    ``loop_fn(answer_text, topic)`` must run the full loop and return a dict
    with keys: overall_score, topic_mastery_before, topic_mastery_after,
    difficulty, guidance_level, human_review_recommended.
    """
    cases = load_learning_loop_gold_cases(project_root, pack_name)
    failures: list[GoldenEvalFailure] = []
    passed = 0

    for i, case in enumerate(cases):
        result = loop_fn(case.answer, case.topic)
        case_failures: list[str] = []

        score = result["overall_score"]
        if not (case.expected_min_score <= score <= case.expected_max_score):
            case_failures.append(
                f"score {score:.4f} outside expected "
                f"[{case.expected_min_score:.4f}, {case.expected_max_score:.4f}]"
            )

        mastery_before = result["topic_mastery_before"]
        mastery_after = result["topic_mastery_after"]
        delta = mastery_after - mastery_before
        # Tolerance for "none": EMA/multiplier rounding can nudge mastery
        # slightly; treat |delta| <= 0.01 as effectively flat.
        if case.mastery_direction == "rise" and not delta > 0.01:
            case_failures.append(
                f"mastery should rise: before={mastery_before:.4f} "
                f"after={mastery_after:.4f}"
            )
        elif case.mastery_direction == "drop" and not delta < -0.01:
            case_failures.append(
                f"mastery should drop: before={mastery_before:.4f} "
                f"after={mastery_after:.4f}"
            )
        elif case.mastery_direction == "none" and abs(delta) > 0.01:
            case_failures.append(
                f"mastery should stay: before={mastery_before:.4f} "
                f"after={mastery_after:.4f}"
            )

        difficulty = result["difficulty"]
        if case.difficulty_direction == "increase" and difficulty <= 3:
            case_failures.append(
                f"difficulty should increase above baseline, got {difficulty}"
            )
        elif case.difficulty_direction == "decrease" and difficulty >= 3:
            case_failures.append(
                f"difficulty should decrease below baseline, got {difficulty}"
            )
        elif case.difficulty_direction == "unchanged" and difficulty != 3:
            case_failures.append(f"difficulty should stay 3, got {difficulty}")

        guidance = result["guidance_level"]
        if case.guidance_direction == "increase" and guidance <= 3:
            case_failures.append(
                f"guidance should increase above baseline, got {guidance}"
            )
        elif case.guidance_direction == "decrease" and guidance >= 3:
            case_failures.append(
                f"guidance should decrease below baseline, got {guidance}"
            )
        elif case.guidance_direction == "unchanged" and guidance != 3:
            case_failures.append(f"guidance should stay 3, got {guidance}")

        review = result["human_review_recommended"]
        if case.should_trigger_review and not review:
            case_failures.append(
                "human review should be recommended, got False"
            )

        if case_failures:
            failures.append(
                GoldenEvalFailure(
                    case_index=i,
                    case_description=case.description or f"case {i}",
                    expected="; ".join(case_failures),
                    actual=(
                        f"score={score:.4f} mastery "
                        f"{mastery_before:.4f}->{mastery_after:.4f} "
                        f"difficulty={difficulty} guidance={guidance} "
                        f"review={review}"
                    ),
                )
            )
        else:
            passed += 1

    total = len(cases)
    return GoldenEvalReport(
        eval_name="learning_loop",
        pack_name=pack_name,
        total_cases=total,
        passed_cases=passed,
        failed_cases=len(failures),
        pass_rate=(passed / total) if total else 0.0,
        failures=failures,
        diagnostics=[],
    )
