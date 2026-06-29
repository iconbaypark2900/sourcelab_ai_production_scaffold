"""LLM-as-judge entailment scorer for claim verification.

Instruction:
- Blend LLM entailment scores with deterministic token-overlap scores.
- Fall back to pure deterministic when LLM is disabled or fails.
- Capture warnings per-claim for diagnostics.
- Uses the same ModelRouter pattern as the answer scorer LLM judge.
"""

from __future__ import annotations

import json
from typing import Any

from sourcelab.models.prompts import PromptTemplates
from sourcelab.models.schemas import ModelRequest, ModelResponse
from sourcelab.verification.schemas import EvidenceMatch


# Map LLM entailment labels to numeric scores
LABEL_TO_SCORE: dict[str, float] = {
    "supported": 1.0,
    "refuted": 0.0,
    "neutral": 0.5,
}

# Map LLM entailment labels to support status values
LABEL_TO_SUPPORT: dict[str, str] = {
    "supported": "supported",
    "refuted": "unsupported",
    "neutral": "uncertain",
}


class LLMEntailmentScorer:
    """LLM-as-judge entailment scorer with deterministic fallback."""

    def __init__(
        self,
        model_router: Any | None = None,
        enable_llm: bool = False,
        blend: float = 0.5,
    ) -> None:
        self._router = model_router
        self._enable_llm = enable_llm
        self._blend = blend

    @property
    def enabled(self) -> bool:
        return self._enable_llm and self._router is not None

    def score(
        self,
        claim_text: str,
        evidence_matches: list[EvidenceMatch],
        deterministic_score: float,
    ) -> tuple[float | None, str | None, str | None, list[str], float | None]:
        """Score a claim's entailment using LLM and blend with deterministic score.

        Returns:
            Tuple of (llm_score, llm_label, llm_reasoning, warnings, blended_score).
            llm_score is None if LLM is disabled or failed.
            blended_score is None if LLM is disabled or failed.
        """
        warnings: list[str] = []

        if not self.enabled:
            return None, None, None, [], None

        if not evidence_matches:
            warnings.append("No evidence matches; LLM entailment skipped.")
            return None, None, None, warnings, None

        try:
            prompt = self._build_entailment_prompt(claim_text, evidence_matches)
            request = ModelRequest(
                prompt=prompt,
                route="entailment_scoring",
                temperature=0.0,
                max_tokens=512,
                json_mode=True,
            )
            response: ModelResponse = self._router.generate(request)
        except Exception as e:
            warnings.append(f"LLM entailment call failed: {e}")
            return None, None, None, warnings, None

        if response.raw_error:
            warnings.append(f"LLM entailment error: {response.raw_error}")
            if response.deterministic_fallback_used:
                warnings.append("LLM entailment used deterministic fallback.")
            if not response.text.strip():
                return None, None, None, warnings, None

        try:
            data = json.loads(response.text)
        except (json.JSONDecodeError, ValueError) as e:
            warnings.append(f"LLM entailment JSON parse failed: {e}")
            return None, None, None, warnings, None

        label = str(data.get("entailment", "neutral")).lower().strip()
        if label not in LABEL_TO_SCORE:
            warnings.append(f"LLM entailment returned unknown label: {label}")
            label = "neutral"

        confidence_raw = data.get("confidence", 0.5)
        if not isinstance(confidence_raw, (int, float)):
            confidence_raw = 0.5
        confidence = max(0.0, min(1.0, float(confidence_raw)))

        reasoning = str(data.get("reasoning", ""))

        llm_score = LABEL_TO_SCORE[label] * confidence
        blended = self._blend * llm_score + (1.0 - self._blend) * deterministic_score
        blended = max(0.0, min(1.0, blended))

        return llm_score, label, reasoning, warnings, blended

    def _build_entailment_prompt(
        self,
        claim_text: str,
        evidence_matches: list[EvidenceMatch],
    ) -> str:
        evidence_lines: list[str] = []
        source_ids: list[str] = []
        for i, match in enumerate(evidence_matches[:5]):
            source_ids.append(match.source_id)
            evidence_lines.append(
                f"  [{match.source_id} (tier {match.trust_tier.value})] "
                f"overlap={match.overlap_score:.2f} "
                f"quality={match.match_quality}"
            )

        rendered = PromptTemplates.render(
            route="entailment_scoring",
            claim=claim_text,
            evidence="\n".join(evidence_lines) if evidence_lines else "No evidence available.",
            source_ids=source_ids,
        )
        return rendered.prompt
