"""Model router v2 for SourceLab AI.

Instruction:
- This package provides the model routing layer.
- Supports deterministic mode (default) and local_llm mode.
- No paid remote APIs are allowed.
- Deterministic fallback must always work.
"""

from sourcelab.models.backends import BaseModelBackend, DeterministicBackend, get_backend
from sourcelab.models.config import get_model_config
from sourcelab.models.prompts import PromptTemplates
from sourcelab.models.schemas import (
    ModelBackendInfo,
    ModelCallTrace,
    ModelHealthCheck,
    ModelRequest,
    ModelResponse,
    ModelRoute,
    ModelRouterConfig,
    PromptRenderResult,
    PromptTemplate,
)

__all__ = [
    "BaseModelBackend",
    "DeterministicBackend",
    "get_backend",
    "get_model_config",
    "PromptTemplates",
    "ModelBackendInfo",
    "ModelCallTrace",
    "ModelHealthCheck",
    "ModelRequest",
    "ModelResponse",
    "ModelRoute",
    "ModelRouterConfig",
    "PromptRenderResult",
    "PromptTemplate",
]
