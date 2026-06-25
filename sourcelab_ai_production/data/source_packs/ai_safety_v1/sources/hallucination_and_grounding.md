---
source_id: hallucination_and_grounding
title: Hallucination and Grounding
publisher: SourceLab (local summary)
source_type: technical_notes
trust_tier: B
approval_status: approved
status: active
retrieved_at: 2026-01-15T00:00:00Z
last_checked_at: 2026-06-20T00:00:00Z
---

# Hallucination and Grounding

## Hallucination Risk

Large language models can generate plausible but unsupported statements. Hallucinations are especially risky when users treat fluent text as verified fact. Systems should fail closed when sources are missing or claims lack evidence.

## Grounding Strategies

Grounding ties outputs to approved sources through retrieval, citation checks, and claim verification. Effective grounding requires source inventory, chunk quality, and explicit unsupported-claim handling.

## Operational Guidance

Prefer answers that cite sources, surface uncertainty, and route high-risk claims to human review. Measure grounding with golden evals rather than assuming retrieval alone prevents hallucination.
