# SourceLab AI — Local v1.0 GA

**SourceLab AI** is a source-grounded adaptive technical lab generator.

It turns trusted sources into technical lessons, verifies that claims are supported, scores learner answers with a visible rubric, and adapts the next task based on the learner's profile.

**SourceLab Local v1.0 GA** (`1.0.0`) is a reproducible local-first source-grounded learning/proof system that can be installed, tested, demoed, verified, exported, and inspected from CLI, API, dashboard, and release artifacts.

## What SourceLab is

SourceLab does **not** claim perfect correctness. The credible production claim is:

> SourceLab AI generates adaptive technical lessons from approved sources, verifies citation grounding, scores user answers with visible rubrics, and adapts the next task using a saved skill profile. It is designed to fail closed when sources are missing or important claims are unsupported.

## What Local v1 can do

| Capability | Command |
|---|---|
| First-run setup | `sourcelab init-local` |
| Environment checks | `sourcelab doctor` |
| Version metadata | `sourcelab version` |
| PQC source pack | `sourcelab source-pack install pqc_v1` |
| Full local demo | `sourcelab local-demo` |
| Golden evals (45 cases) | `sourcelab evals run --pack pqc_v1` |
| Strict release gate | `sourcelab verify-release --strict` |
| Release bundle | `sourcelab release bundle` |
| Release checksums | `sourcelab release checksums` |
| Release SBOM | `sourcelab release sbom` |
| Release attestation | `sourcelab release attest` |
| Dependency lock | `make freeze` |
| Release manifest | `sourcelab release manifest` |
| Export report | `sourcelab export latest --format markdown` |
| Batch runs (v2.5) | `sourcelab batch create --config examples/batch_pqc.json` |
| Compare runs (v2.0) | `sourcelab runs compare <id1> <id2>` |
| Compare learner answers (v2.5) | `sourcelab batch answers <batch_id> [--json] [--markdown]` |
| Research validation (v2.6) | Run Studio → **Research** mode on `/runs/[runId]`; **Reading Room** default; batch matrix on `/batches/[batchId]` |
| Library theme (v2.6) | Run Studio home → **SourceLab Research Library**; `/source-packs` → Collections; `/batches` → Study Sets (UI only) |
| Dashboard | `sourcelab dashboard --launch` |
| API | `sourcelab api --serve` |

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev,api,ui,ingest,retrieval,models]"
sourcelab init-local
sourcelab local-demo
sourcelab verify-release --strict
sourcelab dashboard --launch
sourcelab api --serve
```

Or use Make:

```bash
make install-all
make demo
make release-check
```

## One-command demo

```bash
bash scripts/local_v1_demo.sh
# or
make demo
```

Smoke validation:

```bash
bash scripts/local_v1_smoke.sh
# or
make smoke
```

## Dashboard & API

```bash
# Streamlit dashboard
sourcelab dashboard --launch
# or: bash scripts/start_dashboard.sh

# FastAPI server
sourcelab api --serve
# or: bash scripts/start_api.sh
curl http://localhost:8000/version
```

Docker (API default; optional dashboard profile):

```bash
docker compose up sourcelab-api
docker compose --profile dashboard up sourcelab-dashboard
```

The API service does not require the dashboard profile. Use `--profile dashboard` only when running Streamlit.

## Run Studio (Next.js frontend)

The **Run Studio** is a Next.js 16 web console (`apps/web/`) that visualizes runs
and supports **in-UI answer submission** with **live polling** of the FastAPI
backend (no WebSockets). The Streamlit dashboard remains the fallback/debug UI.

```bash
# 1. Backend (project root)
source .venv/bin/activate && sourcelab api --serve

# 2. Frontend (separate shell)
cd apps/web && npm install && npm run dev   # http://localhost:3000
```

Open `/runs/new` to create a run from the browser (topic + source pack + lesson
format), `/batches/new` to create compared batch runs with progress UX and presets (v2.1), or open an existing run at `/runs/[runId]`, paste a learner answer (or load a sample) into the
**Submit answer** panel, and submit. The answer is scored server-side via the same
deterministic path as `sourcelab answer submit` (`POST /learning/answers`), and the
timeline, learning update, and artifact matrix refresh automatically. A top control
strip exposes a manual **Refresh** button, an **auto-refresh** toggle (5s), the
last-updated time, and an API connection status (cached data stays on screen if the
backend goes offline). See [docs/frontend/RUN_STUDIO.md](docs/frontend/RUN_STUDIO.md) and [docs/frontend/BATCH_RUNS.md](docs/frontend/BATCH_RUNS.md).

## Proof bundle

Every demo run writes artifacts under `artifacts/runs/<run_id>/`:

- `generated_lesson.md`, `claim_map.json`, `citation_resolution.json`
- `harness_report.json`, `proof_bundle_manifest.json`
- `learning_report.json`, `model_call_trace.json` (when applicable)

Inspect with:

```bash
sourcelab proof latest
sourcelab harness latest
sourcelab runs show latest
```

## Golden evals

```bash
sourcelab source-pack validate pqc_v1
sourcelab evals run --pack pqc_v1
sourcelab evals latest --pack pqc_v1
```

Expected: **45/45** cases passing for `pqc_v1`.

## Source Pack Smoke Matrix

Validate bootstrapped source packs with the local smoke matrix (doctor, optional evals, optional lesson runs):

```bash
python scripts/bootstrap_sourcelab_source_packs.py --repair-manifests
python scripts/smoke_source_packs.py --packs core --run-evals --run-lessons
python scripts/smoke_source_packs.py --packs all --run-evals
python scripts/bootstrap_sourcelab_source_packs.py --list-legacy-evals
```

Reports are written to `artifacts/source_pack_smoke_matrix.json` and `artifacts/source_pack_smoke_matrix.md`.

Legacy eval cleanup (never deletes gold eval files):

```bash
python scripts/bootstrap_sourcelab_source_packs.py --list-legacy-evals
python scripts/bootstrap_sourcelab_source_packs.py --delete-legacy-evals
```

See [docs/source_packs/TOPIC_BACKLOG.md](docs/source_packs/TOPIC_BACKLOG.md) for pack groups and example lesson topics.

## SourceLab Library Builder v1

Local-first **Bronze → Silver → Gold** pipeline for expanding source packs from project docs and metadata-first collectors (no blind PDF or restricted bulk download).

```text
data/library/
  raw/{local_docs,arxiv,pubmed,nvd,sec,nasa,govinfo,github}/
  silver/{source_cards,chunks,manifests,dedupe,quality}/
  promotion/{candidates,reports}/
```

Quick start:

```bash
sourcelab library collect-local --path . --domain user_project_library
sourcelab library stats
sourcelab library dedupe
sourcelab library quality
sourcelab library promote --domain user_project_library --target-pack agentic_engineering_v1 --dry-run
```

Collectors: `collect-local`, `collect-arxiv`, `collect-pubmed`, `collect-nvd`. Pipeline stages: `normalize`, `dedupe`, `quality`, `promote`. Runs with thin retrieval/grounding evidence write `artifacts/runs/<run_id>/source_expansion_suggestions.json`.

## Library-Aware Research Engine v1

Topic → research plan → library-aware retrieval → coverage report → evidence-bound lesson → genericness check → expansion suggestions → adaptive topic profiles.

```bash
sourcelab research plan --topic "multi-agent control plane" --source-pack agentic_engineering_v1
sourcelab lesson create --topic "..." --source-pack agentic_engineering_v1 --difficulty 2
sourcelab research coverage --run latest
sourcelab research genericness --run latest
sourcelab research profile --topic "..." --source-pack agentic_engineering_v1
sourcelab research expansion --run latest
```

Run artifacts (under `artifacts/runs/<run_id>/`): `research_plan.json`, `retrieval_strategy.json`, `source_coverage_report.json`, `evidence_bound_lesson_plan.json`, `genericness_report.json`, `topic_profile_update.json`, `source_expansion_suggestions.json`. Topic profiles persist at `artifacts/research/topic_profiles/<pack>/<topic_slug>.json` and update on answer submit.

## Adaptive Research Loop v1

Prove lessons improve over time: initial lesson → answer submit → follow-up lesson → evolution report comparing coverage, genericness, and gaps.

Follow-up runs load the persisted topic profile into `research_plan.json` (`profile_context_used`, `profile_weak_concepts`, `profile_known_gaps`, `follow_up_focus`). Each run writes `lesson_evolution_report.json` comparing against prior runs for the same topic. Thin-evidence runs also get `library_expansion_plan.json` with collector commands.

```bash
sourcelab lesson create --topic "quantum hybrid portfolio optimizer" --source-pack quantum_finance_v1 --difficulty 2
sourcelab answer submit --run latest --answer "..."
sourcelab lesson create --topic "quantum hybrid portfolio optimizer" --source-pack quantum_finance_v1 --difficulty 2
sourcelab research evolution --run latest
sourcelab research evolution --topic "quantum hybrid portfolio optimizer" --source-pack quantum_finance_v1
sourcelab research expansion --run latest
```

Additional artifacts: `lesson_evolution_report.json`, `library_expansion_plan.json`.

## Research Gap Closure Loop v1

Close the loop from thin evidence → collector execution → library improvement → source promotion → follow-up lesson → honest gap closure verdict.

```bash
sourcelab lesson create --topic "quantum hybrid portfolio optimizer" --source-pack quantum_finance_v1
sourcelab answer submit --run latest --text "..."
sourcelab lesson create --topic "quantum hybrid portfolio optimizer" --source-pack quantum_finance_v1

sourcelab research evolution --run latest
sourcelab research expansion --run latest
sourcelab research expansion run --run latest --dry-run
sourcelab research expansion run --run latest --execute
sourcelab research expansion promote --run latest --dry-run
sourcelab research expansion promote --run latest --force

sourcelab lesson create --topic "quantum hybrid portfolio optimizer" --source-pack quantum_finance_v1
sourcelab research gap-closure --run latest
```

Additional artifacts: `library_expansion_execution.json`, `library_improvement_report.json`, `source_promotion_report.json`, `gap_closure_report.json` (each with `.md` companion). Supported collectors for `--execute`: `local_docs`, `arxiv`, `pubmed`, `nvd`. Unsupported collectors are listed as manual actions. Gap closure verdict is `improved` only when coverage/genericness/gaps artifacts support it.

## Guided Gap Closure Orchestration v1.1

Run the full gap-closure workflow from a weak baseline run with safe defaults (dry-run expansion and promotion unless explicitly overridden):

```bash
sourcelab research gap-closure run --run latest --dry-run
sourcelab research gap-closure run --run latest --execute
sourcelab research gap-closure run --run latest --execute --promote-force --repair-manifests
sourcelab research gap-closure run --run latest --execute --create-followup --difficulty 2
```

Orchestration writes `gap_closure_orchestration.json` and `gap_closure_orchestration.md` with planned/executed commands, promotion/manifest repair status, follow-up lesson command, and optional gap-closure verdict after `--create-followup`. Expansion execution persists `baseline_run_id` for deterministic baseline pairing in gap-closure reports.

## Adaptive Research Loop v1.2 — Answer-Submit Bridge + Orchestration Replay

Submit a baseline answer before expansion/follow-up, replay orchestration from artifacts, and track multi-hop topic evolution:

```bash
sourcelab research gap-closure run --run latest --dry-run --answer-text "A strong answer should define the objective, evidence, risks, and validation path."
sourcelab research gap-closure run --run latest --execute --answer-file path/to/answer.md
sourcelab research gap-closure run --run latest --execute --answer-text "..." --skip-answer-submit
sourcelab research gap-closure replay --run latest
sourcelab research gap-closure replay --run latest --continue
```

Answer-submit bridge runs before expansion when `--answer-text` or `--answer-file` is set (execute mode submits; dry-run plans only). Orchestration replay reads `gap_closure_orchestration.json`, prints completed vs remaining steps, and suggests the next safe command. Topic profiles under `artifacts/research/topic_profiles/` store `orchestration_runs`, `followup_chain`, and `last_gap_closure_verdict` for multi-hop chains linked by `followup_run_id`.

## Starter Pack Eval Alignment (v1.0.2)

Core starter packs (`agentic_engineering_v1`, `local_ai_infra_v1`, `rag_doc_intelligence_v1`) use shared guardrail patterns for claim and answer golden evals. `local_ai_infra_v1` source markdown includes DGX Spark and EVO-X2 hardware terms expected by retrieval gold evals.

Verify alignment:

```bash
python scripts/bootstrap_sourcelab_source_packs.py --repair-manifests
python scripts/smoke_source_packs.py --packs core --run-evals --run-lessons
python scripts/bootstrap_sourcelab_source_packs.py --delete-legacy-evals --dry-run
```

Strict release validation for `pqc_v1` and `ai_safety_v1` is unchanged.

## Extension Pack Eval Alignment (v1.0.3)

Nine extension starter packs (`biomedical_ai_v1`, `materials_ai_v1`, `quantum_finance_v1`, `trading_research_v1`, `blockchain_provenance_v1`, `logistics_earth_v1`, `grantops_business_v1`, `emerging_tech_watchlist_v1`, `career_learning_v1`) use the same gold eval patterns as core packs. Source markdown was strengthened with domain retrieval terms (for example SBIR/STTR, smart contracts, QAOA, Kalshi, MDC CodePath, fusion) expected by retrieval gold evals. Extension pack smoke failures are non-blocking for `sourcelab verify-release --strict`.

Verify alignment:

```bash
python scripts/bootstrap_sourcelab_source_packs.py --packs blockchain_provenance_v1,career_learning_v1,emerging_tech_watchlist_v1,grantops_business_v1,quantum_finance_v1,trading_research_v1 --force --skip-topic-backlog
python scripts/smoke_source_packs.py --packs all --run-evals
python scripts/smoke_source_packs.py --packs all --run-evals --run-lessons
sourcelab verify-release --strict
```


- Deterministic/mock generation, hashed embeddings, heuristic scoring — no live LLM required
- No auth, Postgres, Redis, Qdrant, or background workers
- No live web search
- Docker-lite exposes API only in v1 RC

See `RELEASE_NOTES_LOCAL_V1_RC.md` for full details.

## Roadmap

See `docs/engineering/ROADMAP.md`. Next milestone: **Local v1.0 GA** (pinned deps, UX polish, signed artifacts).

## Project layout

```text
src/sourcelab/
  sources/        Source registry, ingestion, source packs
  retrieval/      Hybrid search, embeddings, compression
  generation/     Lesson, rubric, answer-key generation
  verification/   Claim extraction, evidence matching, citation gates
  harness/        Proof bundles, run validators, release gates
  learning/       Answer scoring, mastery profile, next-task evolution
  api/            FastAPI entrypoint
  ui/             Dashboard, run explorer, report export
docs/
  demo/           Local v1 demo script, walkthrough, screenshot checklist
  product/        PRD, requirements
  engineering/    Architecture, roadmap, backlog
  testing/        Test plan, release gate criteria
scripts/          local_v1_demo.sh, local_v1_smoke.sh, start_api.sh, start_dashboard.sh
```

## Additional commands

```bash
sourcelab demo --topic "post-quantum cryptography migration"
sourcelab lesson create --topic "post-quantum cryptography migration" --difficulty 3
sourcelab sources list
sourcelab sources validate
sourcelab search "crypto inventory" --mode hybrid
sourcelab answer submit --topic "post-quantum cryptography migration" --text "..."
sourcelab release check
sourcelab release report
pytest -q
```

## Documentation

- [Local v1 walkthrough](docs/demo/LOCAL_V1_WALKTHROUGH.md)
- [Demo presenter script](docs/demo/LOCAL_V1_DEMO_SCRIPT.md)
- [Release notes](RELEASE_NOTES_LOCAL_V1_RC.md)
- [Changelog](CHANGELOG.md)
- [Runbook](docs/operations/RUNBOOK.md)
