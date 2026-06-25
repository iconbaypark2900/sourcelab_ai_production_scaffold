# Run Studio — Next.js 16 Frontend

The **Run Studio** (a.k.a. *Generation Console*) is a Next.js 16 web UI that
visualizes SourceLab runs as a progressive, source-grounded pipeline. It lives
under [`apps/web/`](../../apps/web) and talks to the existing FastAPI backend
over HTTP. The Streamlit dashboard (`src/sourcelab/ui/dashboard.py`) is
unchanged and remains the fallback/debug UI.

> **Vocabulary note.** The diffusion-console language ("generation field",
> "evidence signal", "claim denoising", "citation locking", "proof
> stabilization", "learning update") is an **aesthetic metaphor only**.
> SourceLab is a deterministic source-grounded pipeline, not a diffusion model.

## Run it locally (two processes)

### Backend — FastAPI

From the project root (`sourcelab_ai_production`):

```bash
source .venv/bin/activate
sourcelab api --serve            # http://127.0.0.1:8000
sourcelab api routes             # enumerate the live routes
```

### Frontend — Next.js

```bash
cd apps/web
cp .env.example .env.local       # NEXT_PUBLIC_SOURCELAB_API_URL=http://127.0.0.1:8000
npm install
npm run dev                      # http://localhost:3000
```

Or from the project root via the Makefile:

```bash
make web-install
make web-build      # verify a production build
make web-dev        # start the dev server
```

If the backend is offline, the UI renders a clear connection card on every page
(it never crashes).

## Pages

| Route | Purpose |
| --- | --- |
| `/` | API status, latest run, strict release + golden-eval status |
| `/runs` | All runs with key signals |
| `/runs/new` | Create a new source-grounded run from the browser |
| `/runs/compare` | Compare 2+ runs side-by-side (v2.0) |
| `/batches` | List batch runs (v2.0) |
| `/batches/new` | Create a batch with templates, presets, and progress UX (v2.1) |
| `/batches/[batchId]` | Batch detail, refresh bar, run + answer comparison, report preview, attempt-aware cross-run diff, demo bundle export (v2.5) |
| `/runs/[runId]` | Run Studio — 3-column console with Overview / Detailed / Forensic modes |
| `/source-packs` | Curated packs, install status, eval pass rates, strict-release flag |
| `/release` | Release readiness composed from live API signals |
| `/api-health` | API liveness/readiness, version, model router detail |

## Backend endpoints consumed

All client functions in `apps/web/lib/sourcelab-api.ts` map to **verified**
routes (confirmed with `sourcelab api routes`):

| Client function | Method & path |
| --- | --- |
| `getHealth` | `GET /health` |
| `getReadiness` | `GET /ready` |
| `getVersion` | `GET /version` |
| `listRuns` | `GET /runs/` |
| `getLatestRun` | `GET /runs/latest` |
| `getRun` | `GET /runs/{run_id}` |
| `getRunArtifacts` | `GET /runs/{run_id}/artifacts` |
| `getRunArtifactJson` / `getRunArtifact` | `GET /runs/{run_id}/artifacts/{artifact_name}` |
| `refreshRunContext` | *composed* — run summary + all forensic artifacts (the loader the page polls) |
| `submitAnswer` | `POST /learning/answers` |
| `getRunProof` | `GET /runs/{run_id}/proof` |
| `getRunHarness` | `GET /runs/{run_id}/harness` |
| `getRunLearning` | `GET /learning/reports/{run_id}` |
| `getNextTask` | `GET /learning/next-task/{run_id}` |
| `getLesson` | `GET /lessons/{run_id}` |
| `createLessonRun` | `POST /lessons/` |
| `getSourcePacks` | `GET /source-packs/` |
| `getSourcePackStatus` | `GET /source-packs/{pack_name}/status` |
| `validateSourcePack` | `GET /source-packs/{pack_name}/validate` |
| `getLatestEvals` | `GET /evals/latest/{pack_name}` |
| `getModelConfig` / `getModelHealth` | `GET /models/config` · `GET /models/health` |
| `getReleaseManifest` | *composed* — no `/release` route exists; built from proof + evals + harness + version + source-pack |

### Backend additions made for this UI

Minimal, in-scope additions:

1. **`GET /runs/{run_id}/artifacts/{artifact_name}`** — a read-only endpoint
   returning a single artifact's parsed JSON (or markdown/text). The existing
   inventory endpoint only returns names + hashes, so this is needed to render
   the evidence field, claim denoising table, citation locking, and forensic
   raw-JSON panels. It reuses the dashboard loaders and refuses path traversal.
2. **`POST /lessons/`** (enriched, v1.9) — synchronous run creation wrapping
   `run_lesson_create`. Requires `topic` and `source_pack`; validates the pack,
   returns `run_id`, harness/proof status, artifact count, and `run_url`.
3. **`sourcelab api routes`** — a CLI subcommand that enumerates the FastAPI
   routes from the OpenAPI schema (used during development and acceptance).
4. **`POST /learning/answers`** (enriched) — the existing answer endpoint was
   thin (always returned `score=0.0`) and required `topic`. v1.1 makes `topic`
   optional (resolved from the run manifest), accepts `run_id: "latest"` (and a
   `user_id`), resolves `latest` to a concrete run, returns the transparent
   learning metrics (`overall_score`, `rubric_alignment_score`, `uncapped_score`,
   `needs_review`, `cap_reason`, `human_review_reason`, `next_task_decision`,
   `learning_report_path`), and returns structured errors (404 for a missing
   run, 422 for an empty answer). It remains a thin wrapper over
   `run_answer_submit` — the same deterministic path as the `answer submit` CLI.

All are covered by Python regression tests
(`tests/integration/test_api_v1.py`, `tests/unit/test_cli_api_routes.py`).

## v1.1 — Live updates + in-UI answer submission

The Run Studio (`/runs/[runId]`) is live and interactive:

- **Answer submission** — `components/AnswerSubmissionPanel.tsx` provides a
  textarea, Strong/Weak/Unsupported sample buttons, and loading/success/error
  states. On submit it calls `submitAnswer(runId, …)`; the response shows the
  final score, rubric alignment, uncapped score, needs-review flag, cap reason,
  and next-task focus, then triggers a page refresh.
- **Live polling** — `lib/use-run-refresh.ts` drives the page: a manual refresh,
  an auto-refresh toggle (default 5s, **polling only — no WebSockets**), a
  last-updated timestamp, pause-on-error, and `visibilitychange` pausing when the
  tab is hidden. `components/RunRefreshBar.tsx` renders these controls plus an
  API connection status. On disconnect the page keeps the last cached snapshot on
  screen instead of blanking out.
- **Reactive timeline** — `components/DiffusionTimeline.tsx` derives each stage
  from artifact presence and run metrics, so after a UI submit the
  answer/profile/next-task stages move `MISSING → PASS/REVIEW`.
- **Forensic artifact loader** — `components/ArtifactViewer.tsx` adds quick
  buttons (`answer_review.json`, `learning_report.json`,
  `source_grounding_review.json`, `next_task_decision.json`,
  `verification_report.json`, `citation_resolution.json`, `proof_summary.json`,
  `harness_report.json`) that fetch raw content via `getRunArtifact`.

## v1.4 — Attempt timeline & historical view

Run Studio surfaces answer attempt history without backend changes:

- **Attempt trajectory** — `AttemptScoreSparkline`, timeline summary bar, and
  diffusion-timeline attempt lane (`computeAttemptTimelineSummary` in
  `lib/attempt-summary.ts`).
- **Historical overlay** — selecting a non-latest attempt overlays Learning
  update + TopStatusBar answer signals while preserving the latest run snapshot.
- **Diff presets** — attempt-aware compare shortcuts (selected→latest,
  first→latest, previous→selected, selected→best).

## v1.5 — Deep links & keyboard navigation

Frontend-only; no API changes.

- **`?attempt=<attempt_id>`** — shareable URLs; invalid ids warn and fall back
  to latest. Selection syncs back to the URL via `router.replace`.
- **`useAnswerHistory`** — single history fetch + detail-on-select; powers
  History, Diff, Learning update, TopStatusBar, and timeline lane.
- **Keyboard navigation** in History/Diff: arrow keys, Home/End, Enter (focus
  detail), Escape (latest snapshot). Skipped when typing in form fields.
- **Copy attempt link** button on attempt detail.
- **Vitest** — `npm run test` covers `attempt-summary.ts` metrics.

## v1.6 — Compare pinning, notes & filter-aware keyboard

Frontend-only; no API changes.

- **`?attempt=&from=&to=`** — shareable compare URLs; invalid `from`/`to` warn
  and fall back. Pin/Clear/Copy comparison controls on the Diff tab.
- **Private notes** — `useAttemptNotes` stores annotations in localStorage per
  run; not synced or exported as proof artifacts.
- **Filter-aware keyboard** — History arrow/Home/End navigation respects the
  active filter (needs review, passed, capped).
- **Sparkline** — enlarged invisible marker hit targets for mobile tap/click.

## v1.7 — Attempt annotations export & session restore

Frontend-only; no API changes.

- **`?tab=&filter=`** — workspace URL params restore Attempts tab
  (`submit` | `history` | `diff`) and History filter (`all` | `needs_review` |
  `passed` | `capped`). Invalid values fall back safely. Tab/filter changes sync
  via `router.replace` (other params preserved).
- **Session restore defaults** — `from`+`to` without `tab` opens Diff;
  `attempt` only opens History; no attempt state keeps current default.
- **Notes export/import** — export JSON (`sourcelab_attempt_notes_<run_id>.json`),
  import with validation + merge (newer `updated_at` wins), clear all with
  confirm. Browser-only — not proof artifacts.
- **Copy workspace link** — includes attempt, compare pins, tab, and filter.
- **Answer text comparison** (Diff tab) — lightweight side-by-side preview when
  both attempt details load (score/review/cap delta + strengths/weaknesses summary).

## v1.8 — Annotation search & filtered export

Frontend-only; no API changes.

- **`?q=`** — History search query (attempt id, cap reason, next-task focus, note
  text). Empty `q` omitted from URL; restored on load. Combines with filters.
- **Note-aware filters** — `has_notes` and `no_notes` extend History filters.
  Search + filter together; keyboard nav uses the visible searched/filtered list.
- **Filtered notes export** — export visible notes only
  (`sourcelab_attempt_notes_<run_id>_filtered.json`) with metadata
  (`run_id`, `filter`, `query`, `total_notes_exported`, `source=localStorage`).
- **`?preset=`** — compare presets (`first_latest`, `selected_latest`,
  `selected_best`, `previous_selected`). Explicit `from`+`to` win; invalid
  presets ignored. Quick-compare buttons write preset when not pinned.
- **Workspace summary panel** — active tab, filter, search, selected attempt,
  pinned comparison or preset, note counts (visible / total).
- **Answer preview improvements** — full/preview toggle, character counts,
  answer length delta, review/cap badges per side (no word-level diff).

## v1.9 — Create new runs from UI

- **`/runs/new`** — polished create-run form: topic, source pack chooser (installed
  / valid / eval pass rate / strict-release flag), difficulty, lesson format,
  retrieval mode (hybrid live; keyword/vector recorded in manifest), model mode
  (deterministic live; LLM backends disabled with notes).
- **`POST /lessons/`** — synchronous wrapper over `run_lesson_create` with required
  `source_pack`, structured validation errors, and a Run Studio-friendly response
  (`run_id`, `harness_status`, `proof_status`, `artifact_count`, `run_url`).
- **Shortcuts** — Console, Runs list, nav bar, and Run Studio header link to
  `/runs/new`. Optional auto-navigate to `/runs/[runId]` after creation.
- **Helpers + tests** — `lib/create-run.ts` (`validateCreateRunForm`,
  `normalizeCreateRunRequest`, `selectDefaultSourcePack`) with Vitest coverage.

## v2.0 — Batch runs & compare

- **`/batches/new`** — batch form with add/remove rows and templates (PQC migration,
  crypto inventory, AI safety eval plan).
- **`/batches`**, **`/batches/[batchId]`** — list, detail, run cards, comparison,
  markdown report download.
- **`/runs/compare`** — manual multi-run compare via `GET /runs/compare`.
- **Backend** — `POST /lessons/batch`, batch manifest artifacts under
  `artifacts/batches/<batch_id>/`, deterministic comparison engine in
  `src/sourcelab/comparison/`.
- **CLI** — `sourcelab batch create|list|show|compare`, `sourcelab runs compare`.
- See [BATCH_RUNS.md](./BATCH_RUNS.md) for full reference.

## v2.1 — Batch progress UX & answer comparison

- **`/batches/new`** — planned-run preview, estimated staged progress during the blocking POST, browser-local presets (`use-batch-presets.ts`).
- **`/batches/[batchId]`** — refresh bar (manual + auto-refresh off by default), compare generated runs vs learner answers, `BatchAnswerMatrix` with deep links to `/runs/<id>?attempt=<id>&tab=history`.
- **Backend** — `src/sourcelab/comparison/answer_compare.py`, `GET /batches/{id}/answers/compare`, `GET /runs/answers/compare`.
- **CLI** — `sourcelab batch answers`, `sourcelab runs answers-compare`.
- **Reports** — comparison markdown optionally includes learner answer matrix when attempts exist.

## v2.6 — Educational Interactive Library Theme

**Learning library vs operations layers:** Run Studio v2.6 reframes the UI as an educational research library while preserving all CLI/API names and operational features.

| Layer | UI label | Purpose |
|-------|----------|---------|
| **Library (default)** | Reading Room, Collections, Study Journal | Source-grounded lesson study — tabs for lesson, sources, claims, proof, journal, artifacts |
| **Research** | Research validation workbench | v2.6 artifact-driven validation (coverage, claims, lesson quality, gaps) |
| **Operations** | Pipeline console | Attempts, diffusion timeline, harness, forensic artifacts (formerly Overview) |
| **Detailed / Forensic** | Unchanged | Harness checks and raw JSON inspection |

**Library home (`/`):** SourceLab Research Library hero, quick actions, library shelves mapped to source packs, Study Path on latest run.

**Collections (`/source-packs`):** Sections — Validated, Starter, Strict Release, Collection Health. Badges: Strict, Validated, Starter, Needs sources, Template (hidden from ready-to-study views).

**Start study session (`/runs/new`):** Collection, study depth, lesson style; library creation stages (Opening collection…, Searching shelves…).

**Reading Room (`/runs/[runId]`):** Default mode with `LessonReader`, `EvidenceDrawer`, `ClaimReviewDesk`, `StudyJournalPanel`, `ResearchPathMap`. Deep link: `/runs/<run_id>?mode=research` or `?tab=journal`.

**Study Sets (`/batches/*`):** UI-only rename from batch — Study Set, Study Progress Matrix, Library Export Bundle.

Helpers: `apps/web/lib/library-theme.ts` (+ Vitest). Components: `LibraryCollectionCard`, `LibraryShelf`, `LessonReader`, `EvidenceDrawer`, `ClaimReviewDesk`, `StudyJournalPanel`, `ResearchPathMap`.

## v2.6 — Research Validation Dashboard

**Operations vs Research mode:** Run detail keeps **Operations** / Detailed / Forensic for pipeline operations (attempts, proof stabilization, harness). **Research** mode is a study workbench: validate grounding, claim support, lesson quality, gaps, and next actions — without replacing learner answer workflows. The default **Reading Room** layer is the educational entry point.

| Component | Purpose |
|-----------|---------|
| `ResearchOverviewPanel` | Metrics + deterministic study verdict |
| `SourceCoveragePanel` | Source/chunk coverage + trust labels |
| `ClaimValidationPanel` | Claim groups from verification artifacts |
| `LessonPlanQualityPanel` | Lesson package completeness |
| `ResearchGapsPanel` | Gaps + suggested queries (local-only) |
| `NextResearchActionsPanel` | Prioritized checklist with UI anchors |
| `BatchResearchMatrix` | Batch-level research comparison matrix |

Logic lives in `apps/web/lib/research-validation.ts` (artifact-driven, no LLM). Deep link: `/runs/<run_id>?mode=research`.

## v2.5 — Attempt-aware batch workflows

- **`CrossRunAnswerDiffPanel`** — per-run attempt history via `GET /learning/answers/{run_id}`; selectors for Latest, Best, and every attempt; detail fetch for selected attempt only.
- **`BatchAnswerSubmitPanel`** — quick presets: Submit strong/weak/unsupported to all missing (confirm + explicit Submit).
- **`BatchDemoBundleExport`** — unified browser JSON bundle (`sourcelab_batch_demo_bundle_<batch_id>.json`); optional local notes inclusion.
- **`BatchAnswerMatrix`** — shortcuts to cross-run diff (latest vs latest, best vs best, vs best run).

See [`docs/frontend/BATCH_RUNS.md`](BATCH_RUNS.md) for full reference.

## v2.4 — Batch report & compare UX

- **`BatchReportPreview`** — on `/batches/[batchId]`: `GET /batches/{id}/report` + download endpoint; rendered/raw markdown, copy/download, refresh, status pill, retry on failure.
- **`CrossRunAnswerDiffPanel`** — on batch detail and `/runs/compare` answers tab; compares two runs' attempts via `GET /learning/answers/{run_id}/{attempt_id}`; delta cards for score/rubric/uncapped/review/length.
- **`BatchAnswerSubmitPanel`** — **Submit missing only** (selects `attempt_count === 0` runs); per-run **Custom text** textarea with validation; pre-submit summary counts custom rows.
- **Export/copy** — report markdown from backend; matrix markdown/JSON from frontend helpers (`lib/batch-run.ts`).

See [`docs/frontend/BATCH_RUNS.md`](BATCH_RUNS.md) for full reference.

## v2.3 — Batch answer workflows polish

- **`/batches/[batchId]`** — unified refresh (batch + run comparison + answer matrix); auto-refresh also updates answer matrix; combined last-updated timestamp; cached matrix on error.
- **`BatchAnswerSubmitPanel`** — Global vs per-run profile modes; Strong / Weak / Unsupported / Custom / Skip; pre-submit summary with expected submission count.
- **`BatchAnswerMatrix`** — Export JSON/Markdown from browser; grouped recommendations (Coverage, Weak latest, Review/cap, Regression, Best performer, Next action).
- **`/runs/compare`** — deep-link `?run_ids=…&tab=answers|artifacts`; auto-load on mount; Copy comparison link.
- **CLI parity unchanged** — `sourcelab batch answers … --markdown`, `sourcelab runs answers-compare … --markdown`.

See also [`apps/web/README.md`](../../apps/web/README.md).

## v2.2 — Answer-aware batch workflows

- **`/batches/[batchId]`** — auto-loads answer matrix on page load; header badges (answers, avg latest/best, review-heavy); `BatchAnswerSubmitPanel` for explicit sample-answer submission across selected runs; cached matrix on API error.
- **`/runs/compare`** — **Run artifacts** | **Learner answers** tabs; learner tab uses `GET /runs/answers/compare`.
- **`BatchAnswerMatrix`** — status pills for No attempts, Weak latest, Needs review, Capped, Regression; deterministic recommendation bullets.
- **CLI** — `--markdown` on `sourcelab batch answers` and `sourcelab runs answers-compare` (table + recommendations).
- **Reports** — answer section includes matrix, no-attempts count, weak/review warnings, best/latest summary; does not fail when no attempts exist.

See also [`apps/web/README.md`](../../apps/web/README.md).

## SourceLab Library Builder v1

The Research dashboard surfaces thin-evidence signals (low retrieval count, weak grounding). When the backend pipeline detects thin evidence, it writes `source_expansion_suggestions.json` under the run artifacts directory. Operators can feed those hints into the CLI library pipeline:

```bash
sourcelab library collect-local --path . --domain user_project_library
sourcelab library stats
sourcelab library promote --domain user_project_library --target-pack agentic_engineering_v1 --dry-run
```

Library data lives under `data/library/` (bronze raw, silver cards/chunks/quality, gold promotion candidates). Promotion defaults to dry-run proposals in `data/library/promotion/`.

## Library-Aware Research Engine v1

Lesson create runs the research engine before generation: pack-aware **research plan**, **library-aware retrieval** (source pack + silver library + promoted candidates with origin labels), **source coverage** with weak labels (`insufficient_evidence`, `thin_lesson`, `needs_source_expansion`), **evidence-bound lesson plan**, **genericness report**, **topic profile update** (applied on answer submit), and **expansion suggestions**.

Research mode surfaces these artifacts in `ResearchEnginePanels` alongside existing validation panels. CLI:

```bash
sourcelab research plan --topic "..." --source-pack agentic_engineering_v1
sourcelab research coverage --run latest
sourcelab research genericness --run latest
sourcelab research profile --topic "..." --source-pack agentic_engineering_v1
sourcelab research expansion --run latest
```

Topic profiles: `artifacts/research/topic_profiles/<pack>/<topic_slug>.json`.

## Adaptive Research Loop v1

Follow-up lesson runs apply persisted topic profiles to the research plan (prerequisite review, gap repair, weak concept reinforcement, next-step challenge when applicable). Each run writes `lesson_evolution_report.json` + `.md` with verdict (`improved|unchanged|worse|insufficient_history`), quality deltas, and recorded plan changes — no fake adaptation.

Run Studio Research mode panels: `TopicMemoryPanel`, `LessonEvolutionPanel`, `LibraryExpansionPlanPanel` (wired in `ResearchEnginePanels.tsx`).

```bash
sourcelab research evolution --run latest
sourcelab research evolution --topic "..." --source-pack agentic_engineering_v1
sourcelab research expansion --run latest
```

Additional artifacts: `lesson_evolution_report.json`, `library_expansion_plan.json`.

## Research Gap Closure Loop v1

Execute expansion plans, measure library improvement, propose/force-promote matching source cards, and compare baseline vs follow-up runs with an honest gap closure verdict (`improved|unchanged|worse|insufficient_data`).

Run Studio Research mode panels: `ExpansionExecutionPanel`, `LibraryImprovementPanel`, `SourcePromotionPanel`, `GapClosurePanel` (wired in `ResearchEnginePanels.tsx`).

```bash
sourcelab research expansion run --run latest --dry-run
sourcelab research expansion run --run latest --execute
sourcelab research expansion promote --run latest --dry-run
sourcelab research expansion promote --run latest --force
sourcelab research gap-closure --run latest
```

Additional artifacts: `library_expansion_execution.json`, `library_improvement_report.json`, `source_promotion_report.json`, `gap_closure_report.json`.

## Guided Gap Closure Orchestration v1.1

Single orchestration command plans or executes expansion → promotion → optional manifest repair → follow-up lesson suggestion:

```bash
sourcelab research gap-closure run --run latest --dry-run
sourcelab research gap-closure run --run latest --execute --promote-force --repair-manifests
sourcelab research gap-closure run --run latest --execute --create-followup
```

Artifact: `gap_closure_orchestration.json` (companion `.md`). Run Studio **Gap closure** panel shows orchestration summary and copy-to-clipboard workflow commands.

## Adaptive Research Loop v1.2 — Answer-Submit Bridge + Orchestration Replay

Answer-submit bridge (optional `--answer-text` / `--answer-file`; `--skip-answer-submit` to suppress):

```bash
sourcelab research gap-closure run --run latest --dry-run --answer-text "A strong answer should define the objective, evidence, risks, and validation path."
sourcelab research gap-closure replay --run latest
```

Run Studio adds copy buttons for answer-bridge workflow, replay command, and next safe command. Panels show answer submitted yes/no, topic profile updated, followup run id, gap closure verdict, and suggested next command (copy-only; no UI execution). Multi-hop topic evolution is tracked via orchestration `followup_run_id` and topic profile `followup_chain`.
