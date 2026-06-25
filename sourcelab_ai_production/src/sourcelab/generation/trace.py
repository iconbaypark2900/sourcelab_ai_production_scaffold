"""Generation trace logging.

Instruction:
- Each generated lesson package should emit trace metadata.
- Traces capture backend, prompt version, topic, difficulty, sources used, and warnings.
- Production should write traces to observability backends.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sourcelab.generation.schemas import GenerationTrace


def create_generation_trace(
    topic: str,
    difficulty: int,
    task_format: str,
    source_ids: list[str],
    chunk_ids: list[str],
    generation_backend: str = "deterministic_local",
    prompt_version: str = "v1.0",
    warnings: list[str] | None = None,
    fail_closed_reason: str | None = None,
) -> GenerationTrace:
    """Create a generation trace with current timestamp."""
    return GenerationTrace(
        generation_backend=generation_backend,
        prompt_version=prompt_version,
        topic=topic,
        difficulty=difficulty,
        task_format=task_format,
        source_ids=source_ids,
        chunk_ids=chunk_ids,
        timestamp=datetime.now(timezone.utc).isoformat(),
        warnings=warnings or [],
        fail_closed_reason=fail_closed_reason,
    )


def trace_to_dict(trace: GenerationTrace) -> dict:
    """Convert a generation trace to a dictionary for JSON serialization."""
    return trace.model_dump(mode="json")
