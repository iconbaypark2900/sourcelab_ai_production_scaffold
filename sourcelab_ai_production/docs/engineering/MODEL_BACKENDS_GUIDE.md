# Model Backends Guide

## Objective

Add three model-related features:
1. **TurboQuant research adapter stub** (Epic 2) — compression adapter for retrieval
2. **DiffusionGemma backend** (Epic 3) — model backend for generation
3. **Fallback model backend** (Epic 3) — automatic failover routing

## Current State

- `src/sourcelab/retrieval/compression.py` has int8, fp16, binary, and product quantization adapters
- `src/sourcelab/models/backends.py` has `DeterministicBackend`, `OllamaBackend`, `OpenAICompatibleBackend`
- `src/sourcelab/models/router.py` has `ModelRouter` with config-driven backend selection
- `src/sourcelab/models/config.py` has model configuration

---

## 1. TurboQuant Research Adapter Stub

### Implementation

File: `src/sourcelab/retrieval/compression.py`

Add `TurboQuantAdapter` as a stub that implements the `CompressionAdapter` interface:

```python
class TurboQuantAdapter(CompressionAdapter):
    """TurboQuant research adapter stub.
    
    This is a research stub that implements the interface but delegates
    to product quantization internally. Replace with real TurboQuant
    implementation when available.
    """
    
    name = "turboquant"
    
    def compress(self, vectors: np.ndarray) -> np.ndarray:
        # Delegate to ProductQuantizationAdapter for now
        ...
    
    def decompress(self, compressed: np.ndarray) -> np.ndarray:
        ...
```

### Wiring

- Add `"turboquant"` to compression adapter factory in `compression.py`
- Add `compression_method: "turboquant"` support in `RetrievalConfig`
- Document as research stub in README

### Tests

- Add tests in `tests/unit/test_compression.py` for TurboQuant adapter
- Test that stub produces same results as product quantization
- Test factory selection

---

## 2. DiffusionGemma Backend

### Implementation

File: `src/sourcelab/models/backends.py`

Add `DiffusionGemmaBackend` as a model backend:

```python
class DiffusionGemmaBackend(ModelBackend):
    """DiffusionGemma model backend.
    
    Connects to a DiffusionGemma server (local or remote) via
    OpenAI-compatible API. Requires a running DiffusionGemma instance.
    """
    
    name = "diffusion_gemma"
    
    def __init__(self, base_url: str, model_name: str = "diffusion-gemma"):
        self._base_url = base_url
        self._model_name = model_name
    
    def generate(self, prompt: str, **kwargs) -> ModelResponse:
        # Use OpenAI-compatible client to connect to DiffusionGemma server
        ...
```

### Wiring

- Add `"diffusion_gemma"` to `ModelRouter` backend selection
- Add configuration in `models/config.py`: `diffusion_gemma_base_url`, `diffusion_gemma_model_name`
- Add env var `SOURCELAB_DIFFUSION_GEMMA_URL` for endpoint
- Fall back to deterministic backend when DiffusionGemma is not available

### Tests

- Test backend initialization
- Test fallback to deterministic when server is not reachable
- Test response parsing

---

## 3. Fallback Model Backend

### Implementation

File: `src/sourcelab/models/router.py`

Add automatic fallback routing to `ModelRouter`:

```python
class ModelRouter:
    def __init__(
        self,
        primary_backend: str = "deterministic",
        fallback_backends: list[str] | None = None,
        ...
    ):
        self._primary = primary_backend
        self._fallbacks = fallback_backends or []
    
    def route(self, request: ModelRequest) -> ModelResponse:
        try:
            return self._backends[self._primary].generate(request)
        except Exception as e:
            for fallback in self._fallbacks:
                try:
                    return self._backends[fallback].generate(request)
                except Exception:
                    continue
            # If all fallbacks fail, use deterministic
            return self._backends["deterministic"].generate(request)
```

### Wiring

- Add `fallback_backends` to model config
- Add env var `SOURCELAB_FALLBACK_BACKENDS` (comma-separated list)
- Log fallback events for observability
- Add fallback event to `model_call_trace.json`

### Tests

- Test primary backend success (no fallback)
- Test primary backend failure → first fallback succeeds
- Test all backends fail → deterministic fallback
- Test fallback event logging

## Verification

```bash
source .venv/bin/activate

# All tests
python -m pytest tests/unit/test_compression.py tests/unit/test_model_backends.py -q

# Full suite
python -m pytest -q
sourcelab local-demo
sourcelab verify-release --strict
```

## Scope Notes

- TurboQuant is a stub only; do not implement real quantization algorithm
- DiffusionGemma requires a running server; must work without it (deterministic fallback)
- Fallback routing must always end with deterministic backend (never fail completely)
- Do not add external API dependencies; all backends must work locally or fall back gracefully
