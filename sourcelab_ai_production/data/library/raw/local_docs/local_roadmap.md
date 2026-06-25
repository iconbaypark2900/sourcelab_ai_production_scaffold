# Roadmap

## Phase 0: Scaffold

- Production project tree.
- Source registry.
- Local compressed search.
- Source-grounded lesson generator.
- Claim verifier.
- Proof bundle.
- Answer scorer.
- Next-task selector.
- Tests and docs.

## Phase 1: Reliable source foundation

- [x] PDF ingestion.
- [x] URL ingestion.
- [x] Source trust tiers.
- [x] Retrieved date and hash tracking.
- [x] Freshness checks.
- [x] Source approval workflow.
- [x] Source quality reports.
- [x] Safe retrieval filtering.

## Phase 2: Real retrieval

- Real embedding backend.
- Qdrant or pgvector.
- BM25 keyword search.
- Hybrid search.
- Reranker.
- Compression adapters.

## Phase 3: Real generation

- [x] Model router with deterministic + local LLM backends.
- [x] Ollama backend (local LLM at localhost:11434).
- [x] OpenAI-compatible backend (vLLM, SGLang, LiteLLM, NIM).
- [x] Source-grounded prompt templates with fail-closed instructions.
- [x] JSON schema enforcement on model outputs.
- [x] Generation v2: Complete lesson packages with scenario, rubric, answer key.
- [x] Generation trace logging with model_call_trace.json.

## Phase 4: Verification v2

- Atomic claim extraction with types (definition, recommendation, risk_statement, process_step, warning, fact).
- Evidence matching with token overlap, phrase overlap, and trust tier weighting.
- Claim verification with support status determination.
- Citation resolution rate calculation.
- Conflict detection (must/must-not, safe/unsafe, RSA contradictions).
- Human review queue generation.
- Comprehensive grounding report with trust tier breakdown.
- Harness validation for verification artifacts.
- Release gate with citation resolution and high-risk claim checks.

## Phase 5: Adaptive learning v2

- Answer submission with rubric-based scoring (7 criteria: topic relevance, source grounding, practical reasoning, uncertainty control, trap avoidance, clarity, citation use).
- Source grounding review comparing learner answers against retrieved chunks and answer key.
- Skill profile v2 with criterion-level mastery, strengths, weaknesses, and source grounding history.
- Deterministic mastery updates with difficulty multipliers.
- Profile-aware next-task selection with weakness-driven focus and explainable rationale.
- Learning report generation with markdown and JSON output.
- Harness validation for learning v2 artifacts.
- CLI commands for answer submission, profile viewing, and learning reports.

## Phase 6: Product UI

- [x] Dashboard v1 with tabbed interface (Overview, Lesson, Sources, Verification, Harness, Learning, Artifacts).
- [x] Run explorer with terminal and Streamlit interfaces.
- [x] Report export (markdown and HTML).
- [x] Lesson viewer.
- [x] Source explorer.
- [x] Answer editor.
- [x] Score breakdown.
- [x] Skill map.
- [x] Proof bundle viewer.
- [x] Admin source approval UI.
- [x] API v1 with FastAPI REST interface.

## Phase 7: Domain Source Packs & Golden Evals

- [x] Source pack format (manifest.json + sources/ + evals/).
- [x] PQC v1 source pack with 7 curated sources.
- [x] Source pack loader (list, validate, install, status).
- [x] CLI commands for source packs.
- [x] Golden eval schemas (retrieval, claim, answer, lesson).
- [x] Golden eval cases (10 retrieval, 15 claims, 15 answers, 5 lessons).
- [x] Golden eval runners with mock and real pipelines.
- [x] Eval runner with summary and markdown reports.
- [x] CLI commands for evals (run, latest).
- [x] API endpoints for source-packs and evals.
- [x] Proof bundle includes golden_eval_summary.json.
- [x] Release gate --strict mode with golden eval checks.
- [x] 353 tests passing.

## Phase 8: Local v1 Release Candidate Hardening

- [x] Release manifest schema (Pydantic model with version, status, verification results).
- [x] Release checklist (12 individual checks for release readiness).
- [x] Release thresholds (configurable pass rates for retrieval, golden eval, citation).
- [x] Local-demo CLI command (13-step full demonstration pipeline).
- [x] Release CLI commands (check, manifest, report).
- [x] Strict release verification (15 checks including PQC pack, source validation, UI commands, API routes).
- [x] Dashboard Release tab (release status, manifest, report, golden eval summary).
- [x] Export report enhancements (source pack, golden eval, proof, release sections).
- [x] Release unit tests (11 tests for config, schemas, manifest, checklist).
- [x] 387 tests passing.
