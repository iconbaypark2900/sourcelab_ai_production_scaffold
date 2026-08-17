"""Scoring behavior for bundled example learner answers."""

from __future__ import annotations

from pathlib import Path

import pytest

from sourcelab.evals.pack_scope import get_pack_scoped_registry
from sourcelab.learning.answer_scorer import AnswerScorer
from sourcelab.retrieval.index import PocketIndex
from sourcelab.sources.source_pack import install_source_pack
from sourcelab.learning.answer_scorer import HIGH_RISK_PATTERNS


TOPIC = "post-quantum cryptography migration"


@pytest.fixture
def search_results():
    root = Path.cwd()
    install_source_pack(root, "pqc_v1")
    registry = get_pack_scoped_registry(root, "pqc_v1")
    index = PocketIndex.from_registry(registry)
    return index.search(TOPIC, top_k=4)


def _score_example(filename: str, search_results) -> dict:
    answer = (Path.cwd() / "examples" / filename).read_text(encoding="utf-8")
    review = AnswerScorer().score_v2(
        topic=TOPIC,
        answer=answer,
        search_results=search_results,
    )
    return {
        "overall_score": review.overall_score,
        "needs_review": review.needs_review,
        "source_grounding_score": review.source_grounding_score,
        "rubric_alignment_score": review.rubric_alignment_score,
        "weaknesses": review.weaknesses,
    }


class TestExampleAnswerScoring:
    def test_strong_beats_weak(self, search_results):
        strong = _score_example("strong_answer.md", search_results)
        weak = _score_example("weak_answer.md", search_results)
        assert strong["overall_score"] > weak["overall_score"]

    def test_strong_answer_not_capped_near_nine_percent(self, search_results):
        strong = _score_example("strong_answer.md", search_results)
        assert strong["overall_score"] >= 0.5
        assert strong["needs_review"] is False

    def test_unsupported_answer_triggers_review(self, search_results):
        unsupported = _score_example("unsupported_answer.md", search_results)
        assert unsupported["needs_review"] is True
        assert unsupported["overall_score"] <= 0.09

    def test_citing_source_title_with_risky_phrase_is_not_high_risk(self):
        # Regression: a learner who correctly cites a source whose *title*
        # contains a risky phrase (e.g. "Quantum Breaks Rsa Today") must not be
        # penalized as an unsupported high-risk claim.
        scorer = AnswerScorer()
        answer = (
            "On risk framing, 'Risk Myths Quantum Breaks Rsa Today' clarifies "
            "that quantum computers cannot break RSA-2048 today."
        )
        needs_review, _ = scorer._check_high_risk(answer)
        assert needs_review is False

    def test_unsupported_claim_with_risky_phrase_still_triggers_review(self):
        # A genuine unsupported claim containing a risky phrase must still
        # trigger review even when it is quoted (not a source-title citation).
        scorer = AnswerScorer()
        answer = (
            "Quantum computers can break RSA-2048 within 2 years; this is a "
            "certain fact."
        )
        needs_review, _ = scorer._check_high_risk(answer)
        assert needs_review is True
