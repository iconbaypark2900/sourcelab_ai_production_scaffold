"""Model configuration for SourceLab AI.

Instruction:
- Configuration via environment variables.
- No paid remote APIs allowed.
- Deterministic mode must always work.
- Fallback is always deterministic.
"""

from __future__ import annotations

import os

from sourcelab.models.schemas import ModelRouterConfig


def get_model_config() -> ModelRouterConfig:
    """Get model configuration from environment variables."""
    return ModelRouterConfig(
        mode=os.environ.get("SOURCELAB_MODEL_MODE", "deterministic"),
        backend=os.environ.get("SOURCELAB_MODEL_BACKEND", "deterministic"),
        model_name=os.environ.get("SOURCELAB_MODEL_NAME", ""),
        base_url=os.environ.get("SOURCELAB_MODEL_BASE_URL", ""),
        timeout_seconds=int(os.environ.get("SOURCELAB_MODEL_TIMEOUT_SECONDS", "60")),
        fallback=os.environ.get("SOURCELAB_MODEL_FALLBACK", "deterministic"),
    )
