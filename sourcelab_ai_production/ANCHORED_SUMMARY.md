# Anchored Summary

## Goal
- Implement **API v1 — FastAPI REST Interface** milestone for the SourceLab AI production scaffold, exposing stable local functionality through a REST API so the dashboard, frontend, automation scripts, or external clients can use SourceLab without shelling out to the CLI.

## Constraints & Preferences
- Do not rewrite the project; preserve existing architecture and keep all existing tests passing
- Do not add auth, databases, Redis, external APIs, or external model APIs
- Do not add real LLM model calls
- Keep API as thin layer over existing services
- Preserve existing CLI commands
- Keep everything local and deterministic by default
- Missing optional API dependencies should fail cleanly with helpful install instructions
- Keep tests deterministic and add comments/instructions at the top of new files

## Progress
### Done
- **Milestone 1**: Source Registry v1 + Local Source Ingestion v1
- **Milestone 2**: Retrieval v1 with vector, keyword, and hybrid search
- **Milestone 3**: Generation v2 with source-grounded lesson packages
- **Milestone 4**: Verification v2 with claim extraction, evidence matching, citation gates, conflict detection, human review queue
- **Milestone 5**: Harness v2 / Proof Bundle v2 with artifact hashes, schema validation, proof summaries, release gates
- **Milestone 6**: Learning v2 with rubric-based scoring, source-grounding review, skill profile, mastery updates, learning reports, adaptive next-task selection
- **Milestone 7**: Dashboard v1 + Run Explorer + Markdown/HTML export
- **Milestone 8**: Real Source Ingestion v2 with PDF/URL ingestion, source approval workflow, freshness checks, quality reports
- **Milestone 9**: Retrieval v2 with embedding backends, vector store adapters, JSON index, retrieval diagnostics, and retrieval evaluation
- **Milestone 10**: API v1 — FastAPI REST Interface

### In Progress
- (none)

### Blocked
- (none)

## Key Decisions
- API v1 is a thin layer over existing services; no business logic duplication in route files
- API optional dependencies: `["fastapi>=0.110", "uvicorn>=0.27", "httpx>=0.27"]` via `pip install -e ".[api]"`
- CORS middleware for local development only
- All API endpoints map to existing CLI commands
- Structured JSON error responses with error code and details
- No auth in this milestone
- Route ordering matters: `/validate` must come before `/{source_id}` to avoid parameter matching issues

## Next Steps
- (none - Milestone 10 is complete)

## Critical Context
- API v1 implementation is complete with all endpoints working
- All unit and integration tests pass (284 passed, 1 skipped)
- API can be started with `sourcelab api` or `uvicorn sourcelab.api.main:app --reload`
- API docs available at http://localhost:8000/docs when server is running

## Relevant Files
- `src/sourcelab/api/main.py`: FastAPI application with CORS, health, readiness, version endpoints
- `src/sourcelab/api/schemas.py`: Pydantic request/response models for all endpoints
- `src/sourcelab/api/errors.py`: Structured error handling with error codes
- `src/sourcelab/api/config.py`: API configuration from environment variables
- `src/sourcelab/api/services.py`: Thin service wrappers over existing CLI/pipeline functions
- `src/sourcelab/api/routes_sources.py`: Source endpoints (list, get, validate, approve, reject, archive, ingest)
- `src/sourcelab/api/routes_retrieval.py`: Retrieval endpoints (search, index, diagnostics)
- `src/sourcelab/api/routes_lessons.py`: Lesson endpoints (create, show)
- `src/sourcelab/api/routes_runs.py`: Run endpoints (list, get, artifacts, proof, harness)
- `src/sourcelab/api/routes_learning.py`: Learning endpoints (answers, profile, reports, next-task)
- `src/sourcelab/cli.py`: Updated with `sourcelab api` command
- `pyproject.toml`: Updated with httpx in API extras
- `tests/unit/test_api_schemas.py`: Unit tests for API schemas
- `tests/integration/test_api_v1.py`: Integration tests for API endpoints
- `docs/engineering/API_CONTRACTS.md`: Complete API documentation
- `docs/engineering/ROADMAP.md`: Updated with API v1 completion
- `docs/engineering/BACKLOG.md`: Updated with API v1 completion
