"""Learning report generator.

Instruction:
- This module generates learning reports as part of the proof bundle.
- Reports include answer score summary, rubric breakdown, strengths, weaknesses,
  topic mastery before/after, criterion mastery changes, next-task rationale,
  recommended focus, and human review flag.
- Write learning_report.md, learning_report.json, mastery_update.json,
  and skill_profile_snapshot.json.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from sourcelab.learning.schemas import (
    AnswerReviewV2,
    AnswerScoreBreakdown,
    LearningReport,
    MasteryUpdate,
    NextTaskRationale,
    SkillProfileV2,
    SourceGroundingReview,
)


def _breakdown_from_review(review: AnswerReviewV2) -> AnswerScoreBreakdown:
    """Build rubric breakdown from criterion scores when available."""
    if review.criterion_scores:
        by_name = {criterion.criterion_name: criterion.score for criterion in review.criterion_scores}
        return AnswerScoreBreakdown(
            topic_relevance=by_name.get("topic_relevance", 0.0),
            source_grounding=by_name.get("source_grounding", review.source_grounding_score),
            practical_reasoning=by_name.get("practical_reasoning", 0.0),
            uncertainty_control=by_name.get("uncertainty_control", review.uncertainty_control_score),
            trap_avoidance=by_name.get("trap_avoidance", review.trap_avoidance_score),
            clarity=by_name.get("clarity", 0.0),
            citation_use_of_evidence=by_name.get("citation_use_of_evidence", 0.0),
        )

    return AnswerScoreBreakdown(
        topic_relevance=0.0,
        source_grounding=review.source_grounding_score,
        practical_reasoning=0.0,
        uncertainty_control=review.uncertainty_control_score,
        trap_avoidance=review.trap_avoidance_score,
        clarity=0.0,
        citation_use_of_evidence=0.0,
    )


def generate_learning_report(
    review: AnswerReviewV2,
    mastery_update: MasteryUpdate,
    rationale: NextTaskRationale,
    source_grounding: SourceGroundingReview | None = None,
    profile: SkillProfileV2 | None = None,
) -> LearningReport:
    """Generate a complete learning report."""
    report_id = f"report_{uuid.uuid4().hex[:12]}"

    # Determine recommended focus
    recommended_focus = review.recommended_focus
    if not recommended_focus and rationale.focus_area:
        recommended_focus = rationale.focus_area

    return LearningReport(
        report_id=report_id,
        user_id=profile.user_id if profile else "local_user",
        topic=review.topic,
        run_id=review.run_id,
        answer_id=review.answer_id,
        overall_score=review.overall_score,
        rubric_alignment_score=review.rubric_alignment_score,
        uncapped_score=review.uncapped_score,
        final_score=review.overall_score,
        cap_reason=review.cap_reason,
        human_review_reason=review.review_reason if review.needs_review else "",
        rubric_breakdown=_breakdown_from_review(review),
        strengths=review.strengths,
        weaknesses=review.weaknesses,
        topic_mastery_before=mastery_update.topic_mastery_before,
        topic_mastery_after=mastery_update.topic_mastery_after,
        criterion_mastery_changes={
            k: {"before": mastery_update.criterion_mastery_before.get(k, 0.55), "after": v}
            for k, v in mastery_update.criterion_mastery_after.items()
        },
        next_task_rationale=rationale,
        recommended_focus=recommended_focus,
        human_review_flag=review.needs_review or rationale.human_review_recommended,
    )


def render_learning_report_markdown(report: LearningReport) -> str:
    """Render a learning report as markdown."""
    lines = []
    lines.append(f"# Learning Report: {report.topic}")
    lines.append("")
    lines.append(f"**Report ID:** {report.report_id}")
    lines.append(f"**Topic:** {report.topic}")
    lines.append(f"**Rubric Alignment Score:** {report.rubric_alignment_score:.2%}")
    lines.append(f"**Uncapped Score:** {report.uncapped_score:.2%}")
    lines.append(f"**Final Score:** {report.final_score:.2%}")
    lines.append(f"**Overall Score:** {report.overall_score:.2%}")
    lines.append("")

    if report.cap_reason:
        lines.append("## Score Cap")
        lines.append("")
        lines.append(f"- Cap Reason: {report.cap_reason}")
        lines.append("")

    if report.human_review_reason:
        lines.append("## Human Review Reason")
        lines.append("")
        lines.append(report.human_review_reason)
        lines.append("")

    # Score breakdown
    lines.append("## Score Breakdown")
    lines.append("")
    lines.append(f"- Topic Relevance: {report.rubric_breakdown.topic_relevance:.2%}")
    lines.append(f"- Source Grounding: {report.rubric_breakdown.source_grounding:.2%}")
    lines.append(f"- Practical Reasoning: {report.rubric_breakdown.practical_reasoning:.2%}")
    lines.append(f"- Uncertainty Control: {report.rubric_breakdown.uncertainty_control:.2%}")
    lines.append(f"- Trap Avoidance: {report.rubric_breakdown.trap_avoidance:.2%}")
    lines.append(f"- Clarity: {report.rubric_breakdown.clarity:.2%}")
    lines.append(f"- Citation Use: {report.rubric_breakdown.citation_use_of_evidence:.2%}")
    lines.append("")

    # Strengths
    if report.strengths:
        lines.append("## Strengths")
        lines.append("")
        for s in report.strengths:
            lines.append(f"- {s}")
        lines.append("")

    # Weaknesses
    if report.weaknesses:
        lines.append("## Weaknesses")
        lines.append("")
        for w in report.weaknesses:
            lines.append(f"- {w}")
        lines.append("")

    # Mastery changes
    lines.append("## Mastery Changes")
    lines.append("")
    lines.append(f"- Topic Mastery: {report.topic_mastery_before:.2%} -> {report.topic_mastery_after:.2%}")
    if report.criterion_mastery_changes:
        lines.append("- Criterion Mastery Changes:")
        for criterion, changes in report.criterion_mastery_changes.items():
            lines.append(f"  - {criterion}: {changes['before']:.2%} -> {changes['after']:.2%}")
    lines.append("")

    # Next task rationale
    lines.append("## Next Task Rationale")
    lines.append("")
    lines.append(f"- Focus Area: {report.next_task_rationale.focus_area}")
    lines.append(f"- Difficulty: {report.next_task_rationale.difficulty}")
    lines.append(f"- Guidance Level: {report.next_task_rationale.guidance_level}")
    lines.append(f"- Reason: {report.next_task_rationale.reason}")
    lines.append("")

    # Recommended focus
    lines.append("## Recommended Focus")
    lines.append("")
    lines.append(report.recommended_focus)
    lines.append("")

    # Human review flag
    if report.human_review_flag:
        lines.append("## Human Review")
        lines.append("")
        lines.append("This answer requires human review.")
        lines.append("")

    return "\n".join(lines)


def write_learning_artifacts(
    report: LearningReport,
    mastery_update: MasteryUpdate,
    profile: SkillProfileV2,
    run_dir: Path,
) -> dict[str, Path]:
    """Write all learning artifacts to the run directory.

    Returns a mapping of artifact names to file paths.
    """
    artifacts = {}

    # Write learning_report.json
    report_path = run_dir / "learning_report.json"
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )
    artifacts["learning_report.json"] = report_path

    # Write learning_report.md
    md_path = run_dir / "learning_report.md"
    md_path.write_text(
        render_learning_report_markdown(report),
        encoding="utf-8",
    )
    artifacts["learning_report.md"] = md_path

    # Write mastery_update.json
    mastery_path = run_dir / "mastery_update.json"
    mastery_path.write_text(
        json.dumps(mastery_update.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )
    artifacts["mastery_update.json"] = mastery_path

    # Write skill_profile_snapshot.json
    profile_path = run_dir / "skill_profile_snapshot.json"
    profile_path.write_text(
        json.dumps(profile.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )
    artifacts["skill_profile_snapshot.json"] = profile_path

    return artifacts
