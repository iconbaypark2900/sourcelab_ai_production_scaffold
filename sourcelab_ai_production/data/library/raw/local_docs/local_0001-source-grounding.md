# ADR 0001: Source grounding is mandatory

## Status

Accepted

## Decision

Lessons cannot be generated without source-linked retrieved chunks.

## Reason

The core product claim depends on grounding. If the system generates unsupported lessons, it becomes an unreliable generic chatbot.

## Consequences

- More metadata work is required.
- Every lesson must include sources.
- The harness can fail closed.
