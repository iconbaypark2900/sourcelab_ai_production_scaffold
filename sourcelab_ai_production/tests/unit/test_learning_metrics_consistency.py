"""Learning Metrics Consistency Patch v1.0.2 tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sourcelab.evals.pack_scope import get_pack_scoped_registry
from sourcelab.generation.schemas import GeneratedRubric
from sourcelab.learning.answer_scorer import AnswerScorer
from sourcelab.learning.report import generate_learning_report, render_learning_report_markdown
from sourcelab.learning.schemas import MasteryUpdate, NextTaskRationale
from sourcelab.learning.source_grounding import check_source_grounding
from sourcelab.retrieval.index import PocketIndex
from sourcelab.sources.source_pack import install_source_pack


TOPIC = "post-quantum cryptography migration"


@pytest.fixture
def rubric() -> GeneratedRubric:
    runs_dir = Path.cwd() / "artifacts" / "runs"
    if runs_dir.exists():
        for run_dir in sorted(runs_dir.glob("*"), reverse=True):
            rubric_path = run_dir / "rubric.json"
            if rubric_path.exists():
                return GeneratedRubric(**json.loads(rubric_path.read_text(encoding="utf-8")))
    pytest.skip("No rubric.json found in artifacts/runs")


@pytest.fixture
def search_results():
    root = Path.cwd()
    install_source_pack(root, "pqc_v1")
    registry = get_pack_scoped_registry(root, "pqc_v1")
    index = PocketIndex.from_registry(registry)
    return index.search(TOPIC, top_k=4)


def _score_example(filename: str, search_results, rubric: GeneratedRubric):
    answer = (Path.cwd() / "examples" / filename).read_text(encoding="utf-8")
    return AnswerScorer().score_v2(TOPIC, answer, search_results, rubric=rubric)


class TestAnswerReviewMetrics:
    def test_strong_answer_scores_are_internally_consistent(self, search_results, rubric):
        review = _score_example("strong_answer.md", search_results, rubric)
        weighted = sum(c.weight * c.score for c in review.criterion_scores)

        assert review.rubric_alignment_score == pytest.approx(round(min(1.0, weighted), 4))
        assert review.uncapped_score >= review.rubric_alignment_score
        assert review.overall_score == pytest.approx(review.uncapped_score)
        assert review.cap_reason == ""
        assert review.needs_review is False

    def test_unsupported_answer_records_cap_metadata(self, search_results, rubric):
        review = _score_example("unsupported_answer.md", search_results, rubric)

        assert review.needs_review is True
        assert review.review_reason
        assert review.cap_reason == review.review_reason
        assert review.uncapped_score > review.overall_score
        assert review.overall_score <= 0.09

    def test_rubric_and_evidence_grounding_scores_are_distinct(self, search_results, rubric):
        answer = (Path.cwd() / "examples" / "strong_answer.md").read_text(encoding="utf-8")
        review = _score_example("strong_answer.md", search_results, rubric)
        grounding = check_source_grounding(
            answer_text=answer,
            search_results=search_results,
            topic=TOPIC,
            answer_id=review.answer_id,
        )

        assert review.source_grounding_score != grounding.concept_overlap_grounding_score
        assert review.source_grounding_score == pytest.approx(
            next(c.score for c in review.criterion_scores if c.criterion_name == "source_grounding")
        )


class TestLearningReportMetrics:
    def test_learning_report_exposes_score_transparency_fields(self, search_results, rubric):
        review = _score_example("unsupported_answer.md", search_results, rubric)
        report = generate_learning_report(
            review=review,
            mastery_update=MasteryUpdate(
                topic=TOPIC,
                topic_mastery_before=0.4,
                topic_mastery_after=0.35,
                overall_score=review.overall_score,
            ),
            rationale=NextTaskRationale(human_review_recommended=True),
        )

        assert report.rubric_alignment_score == review.rubric_alignment_score
        assert report.uncapped_score == review.uncapped_score
        assert report.final_score == review.overall_score
        assert report.overall_score == review.overall_score
        assert report.cap_reason == review.cap_reason
        assert report.human_review_reason == review.review_reason

        markdown = render_learning_report_markdown(report)
        assert "Uncapped Score" in markdown
        assert "Final Score" in markdown
        assert "Cap Reason" in markdown
        assert "Human Review Reason" in markdown
