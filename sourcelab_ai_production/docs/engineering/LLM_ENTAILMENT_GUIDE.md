# LLM Entailment Scoring Guide

## Objective

Replace the deterministic token-overlap entailment scorer with LLM-as-judge entailment scoring for claim verification (Epic 4), while preserving deterministic fallback.

## Current State

- `src/sourcelab/verification/evidence_matcher.py` uses token/phrase overlap for evidence matching
- `src/sourcelab/verification/claim_verifier.py` determines support status from overlap scores
- `src/sourcelab/learning/answer_scorer.py` already has LLM judge integration (v1.0.2) — use as pattern
- `src/sourcelab/models/backends.py` has `DeterministicBackend` and `OpenAICompatibleBackend`
- `src/sourcelab/models/router.py` has `ModelRouter` for model selection

## Implementation Plan

### Step 1: Add entailment prompt template

File: `src/sourcelab/models/prompts.py`

Add a new `claim_entailment` prompt template that:
- Takes a claim and a list of evidence passages
- Returns JSON: `{"entailment": "supported|refuted|neutral", "confidence": 0.0-1.0, "reasoning": "..."}`
- Instructs the model to fail closed (return "neutral") when evidence is insufficient

### Step 2: Add entailment scorer

File: `src/sourcelab/verification/llm_entailment.py`

```python
class LLMEntailmentScorer:
    """LLM-as-judge entailment scorer with deterministic fallback."""
    
    def __init__(
        self,
        model_router: ModelRouter | None = None,
        enable_llm: bool = False,
        blend: float = 0.5,
    ):
        self._router = model_router
        self._enable_llm = enable_llm
        self._blend = blend
    
    def score(
        self,
        claim: str,
        evidence: list[EvidenceMatch],
    ) -> EntailmentResult:
        # 1. Run deterministic token-overlap scorer
        # 2. If LLM enabled, run LLM entailment
        # 3. Blend scores: blended = blend * llm + (1 - blend) * deterministic
        # 4. Return result with warnings on fallback
        ...
```

### Step 3: Wire into claim verifier

File: `src/sourcelab/verification/claim_verifier.py`

- Add `enable_llm_entailment` parameter (default: `False`)
- Use `SOURCELAB_ENABLE_LLM_ENTAILMENT` env var to activate
- Fall back to pure deterministic when LLM fails or is disabled
- Capture warnings in verification report

### Step 4: Update verification report schema

File: `src/sourcelab/verification/schemas.py`

Add to `ClaimVerificationResult`:
```python
llm_entailment_used: bool = False
llm_entailment_score: float | None = None
llm_entailment_label: str | None = None  # "supported", "refuted", "neutral"
llm_entailment_reasoning: str | None = None
llm_warnings: list[str] = []
```

### Step 5: Wire into pipeline

File: `src/sourcelab/core/pipeline.py`

- Pass `enable_llm_entailment` from env var to `ClaimVerifier`
- Same pattern as `SOURCELAB_ENABLE_LLM_JUDGE` for answer scoring

### Step 6: Tests

File: `tests/unit/test_llm_entailment.py`

- Test deterministic fallback (LLM disabled)
- Test LLM scoring with `DeterministicBackend` mock
- Test score blending
- Test warning capture on LLM failure
- Test env var activation

## Verification

```bash
source .venv/bin/activate

# Without LLM (deterministic fallback)
python -m pytest tests/unit/test_llm_entailment.py -q

# With LLM
export SOURCELAB_ENABLE_LLM_ENTAILMENT=1
python -m pytest tests/unit/test_llm_entailment.py -q

# Full suite
python -m pytest -q
sourcelab local-demo
sourcelab verify-release --strict
```

## Scope Notes

- LLM entailment is optional; deterministic fallback must always work
- Use existing `ModelRouter` and `DeterministicBackend` patterns from LLM judge
- Do not add external API calls; use local models or deterministic backend
- Blend factor configurable (default 50/50)
- Warnings captured per-claim for diagnostics
