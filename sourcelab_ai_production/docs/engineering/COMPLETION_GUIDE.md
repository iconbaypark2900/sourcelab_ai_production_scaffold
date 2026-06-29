# Project Completion Guide

This guide outlines the remaining work to complete SourceLab AI Local v1 and transition toward production. Each remaining backlog item is paired with an implementation guide, scope notes, and verification steps.

## Current State

- **Version:** SourceLab Local v1.0.2 (including v1.0.3 extension pack eval alignment)
- **Tests:** 797 Python tests, 247 frontend tests
- **Strict release:** `sourcelab verify-release --strict` passes with 0 blocking failures
- **Source packs:** 18 packs (3 core + 9 extension + 2 curated + TEMPLATE), all passing golden evals

## Completed in v1.0.2–v1.0.3

- [x] Tokenizer-aware chunking (`src/sourcelab/retrieval/chunking.py`)
- [x] Rubric-based LLM judge (`src/sourcelab/learning/answer_scorer.py`)
- [x] Curriculum dashboard UI (`apps/web/app/curriculum/page.tsx`)
- [x] Extension pack eval alignment (6 packs strengthened, all pass 12/12 golden evals)
- [x] Frontend component tests (23 tests for curriculum dashboard)

## Remaining Work

### Priority 1 — Core Production Features

| Item | Epic | Guide | Scope |
|------|------|-------|-------|
| Postgres source tables | Epic 1 | [Postgres Persistence Guide](./POSTGRES_PERSISTENCE_GUIDE.md) | Implement `SourceRepository` with Postgres backend; keep filesystem fallback |
| Skill profile persistence to Postgres | Epic 5 | [Postgres Persistence Guide](./POSTGRES_PERSISTENCE_GUIDE.md) | Implement `SkillProfileRepository` with Postgres backend; keep filesystem fallback |
| Real LLM entailment scoring | Epic 4 | [LLM Entailment Guide](./LLM_ENTAILMENT_GUIDE.md) | Replace deterministic entailment with LLM-as-judge for claim verification |
| Grounding report UI | Epic 4 | [Grounding Report UI Guide](./GROUNDING_REPORT_UI_GUIDE.md) | Add grounding report visualization to Run Studio |

### Priority 2 — Model & Retrieval Enhancements

| Item | Epic | Guide | Scope |
|------|------|-------|-------|
| TurboQuant research adapter stub | Epic 2 | [Model Backends Guide](./MODEL_BACKENDS_GUIDE.md) | Add turboquant compression adapter stub to retrieval |
| DiffusionGemma backend | Epic 3 | [Model Backends Guide](./MODEL_BACKENDS_GUIDE.md) | Add DiffusionGemma model backend to model router |
| Fallback model backend | Epic 3 | [Model Backends Guide](./MODEL_BACKENDS_GUIDE.md) | Add automatic fallback routing when primary backend fails |

### Priority 3 — Release & Operations

| Item | Epic | Guide | Scope |
|------|------|-------|-------|
| Release versioning strategy | Epic 8 | [Release Automation Guide](./RELEASE_AUTOMATION_GUIDE.md) | Semantic versioning policy, version bump automation |
| Release changelog generation | Epic 8 | [Release Automation Guide](./RELEASE_AUTOMATION_GUIDE.md) | Auto-generate changelog from git log + release manifest |
| Release automation (CI/CD) | Epic 8 | [Release Automation Guide](./RELEASE_AUTOMATION_GUIDE.md) | GitHub Actions workflow for test, build, release |

### Priority 4 — Product UI Hardening (Out of scope for Local v1)

| Item | Epic | Scope Note |
|------|------|------------|
| Auth | Epic 6 | Not in scope for local-first; design for future hosted deployment |
| Workspace isolation | Epic 6 | Not in scope for local-first; design for future multi-tenant |
| Audit logs | Epic 6 | Can be added as filesystem-based audit log without auth |
| Deployment config | Epic 6 | Dockerfile + docker-compose for local deployment only |

## Verification Expectations

After completing each item, run:

```bash
# Python tests
source .venv/bin/activate && python -m pytest -q

# Frontend tests (if UI changes)
cd apps/web && npm run build && npm run test

# End-to-end demo
sourcelab local-demo

# Strict release gate
sourcelab verify-release --strict
```

## Implementation Principles

1. **Local-first:** All features must work without external services (Postgres optional, LLM optional)
2. **Fail closed:** Verification and scoring must fail closed when evidence is missing
3. **No threshold lowering:** Do not lower eval or release thresholds to hide failures
4. **Small scoped patches:** Prefer small patches over large new subsystems
5. **Regression tests:** Add tests for every new CLI flag or behavior change
6. **Deterministic by default:** All tests must pass deterministically without network access
