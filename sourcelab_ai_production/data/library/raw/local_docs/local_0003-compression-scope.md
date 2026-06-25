# ADR 0003: Compression starts with practical baselines

## Status

Accepted

## Decision

The scaffold uses simple int8 compression and defines extension points for FAISS, Qdrant, product quantization, and TurboQuant-style adapters.

## Reason

Full TurboQuant support should be added only after the retrieval and grounding layers are reliable.

## Consequences

- The demo remains runnable.
- Compression claims remain modest and measurable.
