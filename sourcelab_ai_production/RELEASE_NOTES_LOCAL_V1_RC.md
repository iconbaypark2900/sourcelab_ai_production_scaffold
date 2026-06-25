# SourceLab Local v1.0 RC — Release Notes

**Version:** 1.0.0-rc1  
**Release label:** SourceLab Local v1.0 RC  
**Date:** 2026-06-20

## Product claim

SourceLab Local v1.0 can be installed locally, run a complete PQC source-grounded learning workflow, produce proof artifacts, pass strict release verification, launch an API/dashboard, and export a reviewable report.

## What works (deterministic / mock)

These features run offline with no paid APIs or live model servers:

| Capability | Command / artifact |
|---|---|
| First-run setup | `sourcelab init-local` |
| Environment checks | `sourcelab doctor` |
| PQC source pack install | `sourcelab source-pack install pqc_v1` |
| Source-grounded lesson | `sourcelab demo` / `sourcelab local-demo` |
| Claim verification & citation gates | artifacts in `artifacts/runs/<run_id>/` |
| Answer scoring with rubric | `sourcelab answer submit` |
| Proof bundle & harness validation | `sourcelab proof latest`, `sourcelab harness latest` |
| Golden evals (45 cases) | `sourcelab evals run --pack pqc_v1` |
| Strict release gate | `sourcelab verify-release --strict` |
| Release manifest & report | `sourcelab release manifest`, `sourcelab release report` |
| Markdown export | `sourcelab export latest --format markdown` |
| Unit/integration tests | `pytest -q` (398+ passed) |

Deterministic fallbacks in use:

- Mock/heuristic generation instead of live DiffusionGemma
- Hashed embeddings instead of neural embeddings
- int8 compression instead of full TurboQuant
- Heuristic answer scoring instead of LLM judge

## Optional model-enabled parts

Install extras for extended capabilities:

```bash
pip install -e ".[api,ui,ingest,retrieval,models]"
```

| Extra | Enables |
|---|---|
| `api` | FastAPI server (`sourcelab api --serve`) |
| `ui` | Streamlit dashboard (`sourcelab dashboard --launch`) |
| `ingest` | PDF and URL ingestion |
| `retrieval` | sentence-transformers + FAISS backends |
| `models` | Local LLM backends (Ollama, OpenAI-compatible) with deterministic fallback |

Configure via environment:

```bash
export SOURCELAB_MODEL_MODE=local_llm
export SOURCELAB_MODEL_BACKEND=ollama
export SOURCELAB_MODEL_NAME=llama3
```

## Known limitations

- No authentication or multi-user support
- No persistent database (Postgres), Redis, or Qdrant
- No background workers or live web search
- No guarantee of factual correctness — fail-closed when sources are missing
- Docker packaging exposes API only (no dashboard container in v1 RC)
- `sourcelab local-demo` and golden evals are slow (~1–3 minutes)

## Reproduce commands

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev,api,ui,ingest,retrieval,models]"

sourcelab init-local
sourcelab local-demo
sourcelab verify-release --strict
sourcelab release manifest
sourcelab export latest --format markdown

# Optional one-command paths
make demo
make smoke
make release-check

# Docker API
docker compose config
docker compose up sourcelab-api
```

## Next milestones

1. **Local v1.0 GA** — polish dashboard UX, pinned dependency lockfile, signed release artifacts
2. **Hosted preview** — single-tenant deploy with auth boundary
3. **Real retrieval** — pgvector/Qdrant with neural embeddings as default
4. **Human review workflow** — operator queue with approval SLAs

See `docs/engineering/ROADMAP.md` for the full engineering roadmap.
