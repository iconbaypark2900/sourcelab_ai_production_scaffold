# Architecture

SourceLab AI is designed as a modular source-grounded learning platform.

## Core rule

No source, no claim.

## System layers

1. Source layer
2. Retrieval layer
3. Generation layer
4. Model router layer
5. Verification layer
6. Harness layer
7. Learning layer
8. UI/API layer
9. Observability layer

## Data flow

1. Sources are registered and trusted.
2. Sources are chunked with metadata.
3. Chunks are embedded and compressed.
4. Retrieval returns source-linked chunks.
5. Generator creates lesson/task from chunks.
6. Verifier maps claims to chunks.
7. Harness writes proof bundle.
8. Learner answers task.
9. Answer scorer updates profile.
10. Next-task selector adapts path.

## Retrieval architecture

The retrieval layer supports three search modes:

### Vector search
- Hashed embeddings (deterministic, no model API needed)
- int8 compression for memory efficiency
- Trust-tier weighting applied to scores

### Keyword search (BM25)
- Lightweight BM25 implementation (no external dependencies)
- Okapi BM25 formula with k1=1.5, b=0.75
- Term frequency saturation and document length normalization
- Trust-tier weighting applied to scores

### Hybrid search
- Combines keyword and vector scores (configurable weights)
- Normalizes scores to [0, 1] before combining
- Applies trust-tier weighting to final score
- Returns diagnostics with score components

### Search modes

```bash
sourcelab search "query" --mode vector    # Vector-only search
sourcelab search "query" --mode keyword   # BM25 keyword search
sourcelab search "query" --mode hybrid    # Combined search
```

## Model router architecture

The model router provides a routing layer between generation components and model backends:

### Two modes
- **deterministic** (default): No model required, deterministic responses always work.
- **local_llm**: Uses configured backend if available, falls back to deterministic on failure.

### Three backends
- **DeterministicBackend**: Always works, no dependencies.
- **OllamaBackend**: Calls local Ollama server at `http://localhost:11434`.
- **OpenAICompatibleBackend**: Supports vLLM, SGLang, LiteLLM, NIM endpoints.

### Configuration (env vars)
- `SOURCELAB_MODEL_MODE`: `deterministic` or `local_llm`
- `SOURCELAB_MODEL_BACKEND`: `deterministic`, `ollama`, or `openai_compatible`
- `SOURCELAB_MODEL_NAME`: Model name for the backend
- `SOURCELAB_MODEL_BASE_URL`: Base URL for the backend
- `SOURCELAB_MODEL_TIMEOUT_SECONDS`: Timeout (default: 60)
- `SOURCELAB_MODEL_FALLBACK`: Fallback mode (always `deterministic`)

### CLI commands
```bash
sourcelab models config          # Show current model configuration
sourcelab models health          # Check backend health
sourcelab models test            # Test a backend with sample prompt
sourcelab demo --model-mode local_llm --model-backend ollama --model-name llama2
sourcelab lesson create --topic "test" --model-mode local_llm
```

### API endpoints
- `GET /models/config` - Show model configuration
- `GET /models/health` - Check backend health
- `POST /models/test` - Test a model backend
- `POST /lessons/` - Create lesson with optional model params

### Proof bundle
- `model_call_trace.json` - Trace of all model calls with latency, fallback info

### Trust-tier weighting

| Tier | Weight | Description |
|------|--------|-------------|
| A | 1.00 | Highly trusted |
| B | 0.85 | Trusted |
| C | 0.65 | Moderate trust |
| D | 0.45 | Low trust |
| E | 0.25 | Untrusted |

## Generation v2 architecture

Retrieval feeds Generation v2, which creates a complete lesson package.

### Generation v2 flow

1. Retrieval returns source-linked chunks with trust tiers.
2. ScenarioGenerator creates a source-grounded scenario.
3. SourceGroundedLessonGenerator produces a full lesson package.
4. RubricGenerator creates a weighted rubric (weights sum to 1.0).
5. AnswerKeyGenerator creates a source-grounded answer key.
6. ClaimVerifier verifies generated claims against sources.
7. HarnessRunner validates all artifacts and fails on high-risk unsupported claims.

### Lesson package components

- `generated_lesson_package.json` - Complete package with scenario, lesson, rubric, answer key
- `generated_lesson.md` - Human-readable lesson markdown
- `rubric.json` - Weighted rubric criteria
- `answer_key.md` - Source-grounded answer key
- `generation_trace.json` - Trace metadata for debugging

### Artifact validation

The harness validates:
- All required artifacts exist
- Rubric weights sum to 1.0
- Answer key has source references
- Generation trace has source IDs and chunk IDs
- No high-risk unsupported claims exist

## Verification v2 architecture

Verification v2 provides advanced claim verification with citation gates.

### Verification v2 flow

1. Extract atomic claims from lesson, answer key, and scenario.
2. Classify claims by type (definition, recommendation, risk_statement, process_step, warning, fact).
3. Match claims to source chunks using token overlap, phrase matching, and trust tier weighting.
4. Verify each claim and assign support status (supported, unsupported, uncertain, conflicting).
5. Calculate citation resolution rate.
6. Detect contradictions between claims.
7. Build human review queue for uncertain items.
8. Generate comprehensive grounding report.
9. Validate release gate (citation resolution rate, high-risk unsupported claims).

### Verification v2 artifacts

- `atomic_claims.json` - Extracted atomic claims with types
- `evidence_matches.json` - Claim-to-chunk matches with scores
- `verification_report.json` - Complete verification report
- `citation_resolution.json` - Citation resolution metrics
- `human_review_queue.json` - Items requiring human review
- `grounding_report.json` - Comprehensive grounding report

### Claim types

| Type | Description | Weight |
|------|-------------|--------|
| definition | Definitions and explanations | 1.0 |
| fact | Factual statements | 0.9 |
| warning | Warnings and cautions | 0.95 |
| risk_statement | Risk assessments | 0.9 |
| recommendation | Recommendations | 0.8 |
| process_step | Process steps | 0.7 |
| unsupported_example | Examples without support | 0.3 |

### Trust tier weighting

| Tier | Weight | Description |
|------|--------|-------------|
| A | 1.00 | Highly trusted |
| B | 0.85 | Trusted |
| C | 0.70 | Moderate trust |
| D | 0.40 | Low trust |
| E | 0.20 | Untrusted |

### Release gate

The release gate passes when:
- Citation resolution rate >= 0.3 (production: 0.8)
- No high-risk unsupported claims
- No unresolved conflicts
- All required artifacts present
