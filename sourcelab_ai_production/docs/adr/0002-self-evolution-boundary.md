# ADR 0002: Self-evolution changes tasks, not source code

## Status

Accepted

## Decision

The self-evolving component may adapt difficulty, format, focus, guidance level, and rubric strictness. It may not mutate production code in v1.

## Reason

Task adaptation is useful and safe. Code self-modification creates unacceptable risk for v1.

## Consequences

- The system remains auditable.
- Users can override the next task.
- Future code-evolution experiments must be sandboxed separately.
