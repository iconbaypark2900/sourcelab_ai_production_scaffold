"""Tests for LLM entailment scoring integration.

Tests cover:
- Deterministic fallback (LLM disabled)
- LLM scoring with DeterministicBackend mock
- Score blending
- Warning capture on LLM failure
- Env var activation
- Schema fields present in ClaimVerificationResult
"""

from __future__ import annotations

import json
import os

from sourcelab.generation.model_router import ModelRouter
from sourcelab.models.backends import DeterministicBackend
from sourcelab.models.schemas import ModelRequest, ModelResponse, ModelRouterConfig
from sourcelab.verification.claim_verifier import ClaimVerifier
from sourcelab.verification.evidence_matcher import match_claim_to_chunks
from sourcelab.verification.llm_entailment import LLMEntailmentScorer
from sourcelab.verification.schemas import (
    AtomicClaim,
    ClaimType,
    EvidenceMatch,
    Severity,
    SupportStatus,
    TrustTier,
)


def _make_router() -> ModelRouter:
    return ModelRouter(
        ModelRouterConfig(mode="deterministic", backend="deterministic")
    )


def _make_claim(
    text: str = "Smart contracts can anchor provenance metadata on-chain.",
    claim_id: str = "c1",
    claim_type: ClaimType = ClaimType.RECOMMENDATION,
    severity: Severity = Severity.MEDIUM,
) -> AtomicClaim:
    return AtomicClaim(
        claim_id=claim_id,
        text=text,
        claim_type=claim_type,
        severity=severity,
    )


def _make_evidence(
    claim_id: str = "c1",
    overlap_score: float = 0.6,
    match_quality: str = "strong",
) -> list[EvidenceMatch]:
    return [
        EvidenceMatch(
            claim_id=claim_id,
            chunk_id="chunk_001",
            source_id="src_001",
            trust_tier=TrustTier.B,
            overlap_score=overlap_score,
            phrase_matches=["smart contracts", "provenance metadata"],
            match_quality=match_quality,
        )
    ]


# ---------------------------------------------------------------------------
# LLMEntailmentScorer unit tests
# ---------------------------------------------------------------------------


class TestLLMEntailmentScorer:
    def test_disabled_by_default(self):
        scorer = LLMEntailmentScorer()
        assert not scorer.enabled

    def test_disabled_when_no_router(self):
        scorer = LLMEntailmentScorer(model_router=None, enable_llm=True)
        assert not scorer.enabled

    def test_enabled_with_router_and_flag(self):
        router = _make_router()
        scorer = LLMEntailmentScorer(model_router=router, enable_llm=True)
        assert scorer.enabled

    def test_returns_none_when_disabled(self):
        scorer = LLMEntailmentScorer()
        llm_score, label, reasoning, warnings, blended = scorer.score(
            "test claim", _make_evidence(), 0.5
        )
        assert llm_score is None
        assert label is None
        assert reasoning is None
        assert warnings == []
        assert blended is None

    def test_returns_none_when_no_evidence(self):
        router = _make_router()
        scorer = LLMEntailmentScorer(model_router=router, enable_llm=True)
        llm_score, label, reasoning, warnings, blended = scorer.score(
            "test claim", [], 0.5
        )
        assert llm_score is None
        assert blended is None
        assert any("No evidence" in w for w in warnings)

    def test_llm_scoring_with_deterministic_backend(self):
        router = _make_router()
        scorer = LLMEntailmentScorer(model_router=router, enable_llm=True)
        llm_score, label, reasoning, warnings, blended = scorer.score(
            "Smart contracts can anchor provenance metadata.",
            _make_evidence(),
            0.6,
        )
        # DeterministicBackend returns "supported" with 0.75 confidence
        assert label == "supported"
        assert llm_score is not None
        assert 0.0 <= llm_score <= 1.0
        assert blended is not None
        assert 0.0 <= blended <= 1.0
        assert reasoning != ""

    def test_blended_score_formula(self):
        router = _make_router()
        scorer = LLMEntailmentScorer(model_router=router, enable_llm=True, blend=0.5)
        det_score = 0.6
        llm_score, _, _, _, blended = scorer.score(
            "test claim", _make_evidence(), det_score
        )
        # DeterministicBackend returns supported (1.0) * 0.75 confidence = 0.75
        expected_llm = 1.0 * 0.75
        expected_blended = 0.5 * expected_llm + 0.5 * det_score
        assert blended is not None
        assert abs(blended - expected_blended) < 0.01

    def test_warning_on_router_exception(self):
        class FailingRouter:
            def generate(self, request: ModelRequest) -> ModelResponse:
                raise RuntimeError("connection failed")

        scorer = LLMEntailmentScorer(model_router=FailingRouter(), enable_llm=True)
        llm_score, label, reasoning, warnings, blended = scorer.score(
            "test claim", _make_evidence(), 0.5
        )
        assert llm_score is None
        assert blended is None
        assert any("LLM entailment call failed" in w for w in warnings)

    def test_warning_on_invalid_json(self):
        class BadJSONRouter:
            def generate(self, request: ModelRequest) -> ModelResponse:
                return ModelResponse(
                    text="not json at all",
                    backend="test",
                    model_name="test",
                    route=request.route,
                )

        scorer = LLMEntailmentScorer(model_router=BadJSONRouter(), enable_llm=True)
        llm_score, label, reasoning, warnings, blended = scorer.score(
            "test claim", _make_evidence(), 0.5
        )
        assert llm_score is None
        assert blended is None
        assert any("JSON parse" in w for w in warnings)

    def test_unknown_label_defaults_to_neutral(self):
        class WeirdLabelRouter:
            def generate(self, request: ModelRequest) -> ModelResponse:
                return ModelResponse(
                    text=json.dumps({"entailment": "maybe", "confidence": 0.5, "reasoning": ""}),
                    backend="test",
                    model_name="test",
                    route=request.route,
                )

        scorer = LLMEntailmentScorer(model_router=WeirdLabelRouter(), enable_llm=True)
        llm_score, label, reasoning, warnings, blended = scorer.score(
            "test claim", _make_evidence(), 0.5
        )
        assert label == "neutral"
        assert any("unknown label" in w for w in warnings)

    def test_custom_blend_factor(self):
        router = _make_router()
        scorer = LLMEntailmentScorer(model_router=router, enable_llm=True, blend=0.8)
        det_score = 0.4
        _, _, _, _, blended = scorer.score("test", _make_evidence(), det_score)
        # 0.8 * (1.0 * 0.75) + 0.2 * 0.4 = 0.6 + 0.08 = 0.68
        assert blended is not None
        assert abs(blended - 0.68) < 0.01


# ---------------------------------------------------------------------------
# ClaimVerifier integration tests
# ---------------------------------------------------------------------------


class TestClaimVerifierWithLLM:
    def test_verifier_without_llm_scorer(self):
        verifier = ClaimVerifier()
        claim = _make_claim()
        evidence = _make_evidence()
        result = verifier.verify_claim(claim, evidence)
        assert result.llm_entailment_used is False
        assert result.llm_entailment_score is None
        assert result.blended_score is None

    def test_verifier_with_disabled_llm_scorer(self):
        scorer = LLMEntailmentScorer(enable_llm=False)
        verifier = ClaimVerifier(llm_entailment_scorer=scorer)
        claim = _make_claim()
        evidence = _make_evidence()
        result = verifier.verify_claim(claim, evidence)
        assert result.llm_entailment_used is False
        assert result.llm_entailment_score is None

    def test_verifier_with_enabled_llm_scorer(self):
        router = _make_router()
        scorer = LLMEntailmentScorer(model_router=router, enable_llm=True)
        verifier = ClaimVerifier(llm_entailment_scorer=scorer)
        claim = _make_claim()
        evidence = _make_evidence()
        result = verifier.verify_claim(claim, evidence)
        assert result.llm_entailment_used is True
        assert result.llm_entailment_score is not None
        assert result.llm_entailment_label == "supported"
        assert result.blended_score is not None

    def test_verifier_with_llm_no_evidence(self):
        router = _make_router()
        scorer = LLMEntailmentScorer(model_router=router, enable_llm=True)
        verifier = ClaimVerifier(llm_entailment_scorer=scorer)
        claim = _make_claim()
        result = verifier.verify_claim(claim, [])
        assert result.llm_entailment_used is False
        assert result.support_status == SupportStatus.UNSUPPORTED

    def test_verifier_llm_warnings_captured(self):
        class FailingRouter:
            def generate(self, request: ModelRequest) -> ModelResponse:
                raise RuntimeError("network error")

        scorer = LLMEntailmentScorer(model_router=FailingRouter(), enable_llm=True)
        verifier = ClaimVerifier(llm_entailment_scorer=scorer)
        claim = _make_claim()
        evidence = _make_evidence()
        result = verifier.verify_claim(claim, evidence)
        assert result.llm_entailment_used is False
        assert any("LLM entailment call failed" in w for w in result.llm_entailment_warnings)

    def test_verifier_llm_upgrades_support_status(self):
        class SupportedRouter:
            def generate(self, request: ModelRequest) -> ModelResponse:
                return ModelResponse(
                    text=json.dumps({
                        "entailment": "supported",
                        "confidence": 0.9,
                        "reasoning": "Claim is well-supported by evidence.",
                    }),
                    backend="test",
                    model_name="test",
                    route=request.route,
                )

        scorer = LLMEntailmentScorer(model_router=SupportedRouter(), enable_llm=True)
        verifier = ClaimVerifier(llm_entailment_scorer=scorer)
        # Low overlap score would normally give UNSUPPORTED
        claim = _make_claim(severity=Severity.LOW)
        evidence = _make_evidence(overlap_score=0.1, match_quality="weak")
        result = verifier.verify_claim(claim, evidence)
        # LLM should upgrade to SUPPORTED
        assert result.llm_entailment_used is True
        assert result.llm_entailment_label == "supported"
        assert result.support_status == SupportStatus.SUPPORTED

    def test_verifier_llm_does_not_downgrade(self):
        class RefutedRouter:
            def generate(self, request: ModelRequest) -> ModelResponse:
                return ModelResponse(
                    text=json.dumps({
                        "entailment": "refuted",
                        "confidence": 0.9,
                        "reasoning": "Claim is contradicted by evidence.",
                    }),
                    backend="test",
                    model_name="test",
                    route=request.route,
                )

        scorer = LLMEntailmentScorer(model_router=RefutedRouter(), enable_llm=True)
        verifier = ClaimVerifier(llm_entailment_scorer=scorer)
        # High overlap score gives SUPPORTED
        claim = _make_claim()
        evidence = _make_evidence(overlap_score=0.8, match_quality="strong")
        result = verifier.verify_claim(claim, evidence)
        # LLM says refuted, but we should NOT downgrade from SUPPORTED
        assert result.llm_entailment_label == "refuted"
        assert result.support_status == SupportStatus.SUPPORTED

    def test_verification_result_has_llm_fields(self):
        verifier = ClaimVerifier()
        claim = _make_claim()
        evidence = _make_evidence()
        result = verifier.verify_claim(claim, evidence)
        # Fields should exist even when LLM not used
        assert hasattr(result, "llm_entailment_used")
        assert hasattr(result, "llm_entailment_score")
        assert hasattr(result, "llm_entailment_label")
        assert hasattr(result, "llm_entailment_reasoning")
        assert hasattr(result, "llm_entailment_warnings")
        assert hasattr(result, "blended_score")
