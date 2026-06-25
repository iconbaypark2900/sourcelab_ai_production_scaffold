# SourceLab Run Studio (Next.js 16 frontend)

A dark **diffusion-console** for SourceLab AI. It visualizes every run as a
progressive, source-grounded pipeline:

> approved sources → retrieval signal → generated lesson → claim denoising →
> citation locking → proof stabilization → answer scoring → learning update → next task

> **Note on vocabulary.** The "generation field / denoising / locking /
> stabilization" language is an **aesthetic metaphor only**. SourceLab is a
> deterministic, source-grounded pipeline — it is *not* a diffusion model.

## Stack

- Next.js 16 (App Router) · React 19 · TypeScript
- Tailwind CSS v4 (+ hand-written diffusion CSS in `styles/globals.css`)
- No auth, no database, no external services. All data is fetched **client-side**
  from the SourceLab FastAPI backend, so the production build never depends on
  the backend being up.

## Prerequisites

- Node.js ≥ 20.9
- The SourceLab FastAPI backend (the Python project in the repository root)

## 1. Start the backend (FastAPI)

From the **project root** (`sourcelab_ai_production`):

```bash
source .venv/bin/activate
sourcelab api --serve          # serves http://127.0.0.1:8000
# inspect routes:  sourcelab api routes
```

## 2. Start the frontend (Next.js)

```bash
cd apps/web
cp .env.example .env.local      # sets NEXT_PUBLIC_SOURCELAB_API_URL
npm install
npm run dev                     # http://localhost:3000
```

If the backend is offline, every page renders a clear **connection card** with
the command to start it — the UI never crashes.

## Scripts

| Command | Description |
| --- | --- |
| `npm run dev` | Start the dev server on `:3000` |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run typecheck` | `tsc --noEmit` type check |
| `npm run test` | Vitest unit tests (attempt-summary, etc.) |
| `npm run test:watch` | Vitest in watch mode |

From the project root you can also use the Makefile:

```bash
make web-install
make web-dev
make web-build
```

## Configuration

| Env var | Default | Description |
| --- | --- | --- |
| `NEXT_PUBLIC_SOURCELAB_API_URL` | `http://127.0.0.1:8000` | Base URL of the FastAPI backend |

## Pages

| Route | Purpose |
| --- | --- |
| `/` | Console landing — API status, latest run, strict release & golden-eval status |
| `/runs` | All runs (id, topic, harness, answer score, citations, artifacts, created) |
| `/runs/new` | **Create run** — topic, source pack, lesson format; synchronous local pipeline |
| `/runs/compare` | **Compare runs** — deep-link `?run_ids=…&tab=answers\|artifacts`, copy link (v2.3) |
| `/batches` | **Batch list** — filesystem-backed batches (v2.0) |
| `/batches/new` | **Create batch** — form, planned-run preview, staged progress, localStorage presets (v2.1) |
| `/batches/[batchId]` | **Batch detail** — unified refresh + answer matrix, attempt-aware cross-run diff, demo bundle export, report preview, per-run sample submit, export/copy (v2.5) |
| `/runs/[runId]` | **Run Studio** — the main 3-column generation console (Overview / Detailed / Forensic) |
| `/source-packs` | Curated packs, installed status, eval pass rates, strict-release flag |
| `/release` | Release readiness composed from live API signals |
| `/api-health` | API liveness/readiness + version + model router detail |

## Architecture

- `lib/sourcelab-api.ts` — centralized fetch client; every function maps to a
  **verified** FastAPI route (see the endpoint map at the top of the file).
- `lib/types.ts` — TypeScript contracts mirroring the backend schemas and the
  run-artifact JSON shapes.
- `lib/format.ts` — pure, dependency-free formatting helpers.
- `lib/use-api.ts` — a small client hook for loading/error/data with retry.
- `lib/use-run-refresh.ts` — polling hook for the Run Studio: manual refresh,
  auto-refresh toggle (default 5s), pause-on-error, tab-visibility pausing, and
  last-updated tracking. Retains cached data across failed refreshes.
- `lib/use-answer-history.ts` — shared attempt history hook (list + detail +
  timeline summary) used by Run Studio v1.5; dedupes history fetches.
- `lib/attempt-summary.ts` — pure attempt timeline metrics (first/latest/best,
  deltas, review/capped counts, score trend, filter-aware nav helpers).
- `lib/attempt-url.ts` — parse/build/clear `?attempt=` / `?from=` / `?to=` / `?tab=`
  / `?filter=` / `?q=` / `?preset=` query params for deep links and workspace restore.
- `lib/attempt-filters.ts` — History filter + search helpers (note-aware filters,
  visible attempt list for keyboard nav and filtered export).
- `lib/use-attempt-notes.ts` — browser-only private attempt notes (localStorage).
- `components/*` — the diffusion-console panels (including
  `AnswerSubmissionPanel`, `RunRefreshBar`, and `ArtifactViewer`).

## Live updates & in-UI answer submission

The Run Studio (`/runs/[runId]`) polls the backend (HTTP only — **no
WebSockets**) and lets you submit a learner answer without leaving the page:

- The **Submit answer** panel posts to `POST /learning/answers`
  (`submitAnswer(runId, answerText)`), which scores deterministically via the
  same path as the `sourcelab answer submit` CLI and returns the transparent
  learning metrics. Strong / Weak / Unsupported sample buttons fill the textarea.
- After a successful submit the page refreshes, so the diffusion timeline,
  learning update, and artifact matrix move `MISSING → PASS/REVIEW`.
- A top control strip (`RunRefreshBar`) shows a **Refresh** button, an
  **auto-refresh** toggle, the last-updated time, and an API connection status.
  If the backend goes offline, cached data stays on screen.
- In **Forensic** mode, an artifact loader fetches raw artifact content via
  `getRunArtifact` (`GET /runs/{run_id}/artifacts/{artifact_name}`).

Run frontend unit tests: `npm run test` (Vitest — attempt-summary, attempt-url,
attempt-filters, use-attempt-notes).

## Run Studio v1.8 — annotation search & filtered export

On `/runs/[runId]`:

- **History search** — `Search attempts / notes…` matches attempt id, cap reason,
  next-task focus, and local note text (case-insensitive). Empty search = all
  visible under current filter. No matches = clear empty state with reset button.
- **URL search state** — `?tab=history&filter=has_notes&q=grounding` restores
  tab, filter, and search box. Empty `q` omitted. `clearAttemptQuery` preserves
  tab, filter, and `q`.
- **Note-aware filters** — **Has notes** / **No notes** alongside All, Needs review,
  Passed, Capped. Keyboard nav (↑↓ Home/End) uses the searched/filtered list.
- **Filtered notes export** — **Export visible notes** downloads
  `sourcelab_attempt_notes_<run_id>_filtered.json` with metadata
  (`run_id`, `exported_at`, `filter`, `query`, `total_notes_exported`,
  `source=localStorage`). **Export all notes** unchanged. Browser-only — not proof artifacts.
- **Compare presets in URL** — `?preset=first_latest|selected_latest|selected_best|previous_selected`.
  Explicit `from`+`to` win over preset. Quick-compare buttons write preset when
  comparison is not pinned; **Pin comparison** writes explicit `from`/`to`.
- **Workspace summary panel** — in the annotations toolbar: tab, filter, search,
  selected attempt, compare (pinned pair or preset), note counts (visible/total).
- **Answer preview improvements** (Diff tab) — Preview/Full text toggle, character
  counts per side, answer length delta, REVIEW/CLEAR/CAPPED badges per side.

Run frontend unit tests: `npm run test` (Vitest — attempt-url, attempt-filters,
attempt-summary, use-attempt-notes).

See v1.7 below for notes export/import, workspace URL restore, and answer text comparison.

## Run Studio v1.6 — compare pinning, notes & filter-aware keyboard

On `/runs/[runId]`:

- **Compare deep links** — `?attempt=<id>&from=<id>&to=<id>` opens Run Studio
  with attempt detail/overlay plus a pinned diff comparison. Invalid `from`/`to`
  ids show an amber warning and fall back to selected/latest defaults. Pinned
  dropdown changes sync to the URL via `router.replace` (other query params
  preserved).
- **Compare pinning UI** (Diff tab) — **Pin comparison**, **Copy comparison
  link**, and **Clear comparison**. Pinned comparisons survive refresh; changing
  the selected attempt does not overwrite a pinned pair unless you use a
  quick-compare preset (Selected→latest, First→latest, etc.).
- **Private attempt notes** — per-attempt textarea in attempt detail; saved to
  `localStorage` (`sourcelab:run:<run_id>:attempt-notes`). Browser-only — not
  synced, not proof artifacts. History rows show a ✎ indicator when a note
  exists.
- **Filter-aware keyboard** (History tab) — arrow keys move through the
  **filtered visible** attempt list; Home/End jump to first/latest in that
  filter; no-op when the filter is empty. Escape clears selection to latest
  snapshot. Skipped while focus is in input/textarea/select.
- **Sparkline hit targets** — larger invisible tap/click circles on score
  markers (visible styling unchanged).

See v1.5 below for attempt deep links, shared history state, and baseline keyboard
shortcuts.

## Run Studio v1.7 — annotations export & session restore

On `/runs/[runId]`:

- **Workspace URL params** — `?attempt=<id>&from=<id>&to=<id>&tab=history&filter=needs_review`
  restores Attempts tab, History filter, attempt selection, and pinned compare
  state. Invalid `tab`/`filter` values fall back safely (`submit` / `all`).
  Tab and filter changes update the URL via `router.replace` without dropping
  unrelated query params.
- **Restore defaults** — `from`+`to` without `tab` → Diff tab; `attempt` only →
  History tab; empty attempt state → Submit (current default).
- **Notes export/import** — History panel tools export
  `sourcelab_attempt_notes_<run_id>.json`, import with validation + merge
  (newer `updated_at` wins), and clear all local notes (confirm dialog).
  Annotations stay in `localStorage` — browser-only, not synced, not proof artifacts.
- **Copy workspace link** — copies the full workspace URL (attempt, compare,
  tab, filter). **Copy attempt link** remains on attempt detail.
- **Answer text comparison** (Diff tab) — side-by-side from/to answer preview when
  both attempt details load, plus score/review/cap deltas and strengths/weaknesses
  change summary (no word-level diff engine).

Run frontend unit tests: `npm run test` (Vitest — attempt-url, attempt-summary,
use-attempt-notes).

See v1.6 below for compare pinning, private notes, and filter-aware keyboard.

## Run Studio v2.6 — Educational Interactive Library Theme

**Learning library vs operations:** The default experience is the **Reading Room** — an educational layout with tabs (Reading Room, Sources, Claims, Proof, Study Journal, Artifacts). **Operations** and **Research** modes remain for pipeline control and artifact validation.

- **Library home (`/`)** — SourceLab Research Library hero, quick actions, shelves (`LibraryShelf` + `LibraryCollectionCard`), Study Path (`ResearchPathMap`).
- **Collections (`/source-packs`)** — Validated / Starter / Strict Release / Collection Health sections; template packs hidden from ready-to-study views.
- **Start study session (`/runs/new`)** — library creation stages; Collection / study depth / lesson style labels.
- **Components** — `LessonReader`, `EvidenceDrawer`, `ClaimReviewDesk` (wraps `ClaimValidationPanel`), `StudyJournalPanel`, `ResearchPathMap`.
- **Study Sets (`/batches/*`)** — UI-only batch → Study Set vocabulary; routes and API unchanged.
- **Helpers** — `lib/library-theme.ts` (+ Vitest): collection grouping, readiness badges, evidence mapping, study journal summary, study set terminology.
- **Styling** — dark academic library in `styles/globals.css` (glass cards, parchment/ink accents).

## Run Studio v2.6 — Research Validation Dashboard

**Operations vs Research mode:** Operations / Detailed / Forensic remain the operations workbench (attempts, proof, harness). **Research** is a separate display mode on `/runs/[runId]` for study-readiness — grounding, claim support, lesson quality, gaps, and next actions. It does not replace answer submission or batch comparison. Default entry is **Reading Room** (library mode).

- **`ResearchOverviewPanel`** — support/citation metrics + deterministic verdict (Ready to study | Needs source review | Needs claim review | Insufficient evidence).
- **`SourceCoveragePanel`** — used/unused pack sources, chunks, trust tiers, coverage labels (Strong / Thin / Single-source / Low trust / No diversity).
- **`ClaimValidationPanel`** — groups claims Supported / Needs review / Unsupported / Conflicting / Uncited from verification + evidence artifacts.
- **`LessonPlanQualityPanel`** — lesson package + learning report quality labels.
- **`ResearchGapsPanel`** — deterministic gaps with suggested search queries (no web browse).
- **`NextResearchActionsPanel`** — prioritized checklist linking to existing UI anchors.
- **`BatchResearchMatrix`** — on `/batches/[batchId]`, compares runs by source coverage, claim support, citation coverage, unsupported/review counts, lesson quality (auto-loaded with run comparison when ≥2 runs).
- **Helpers** — `lib/research-validation.ts` (+ Vitest); frontend computes from existing artifact API endpoints (no new backend required).

Deep link: `/runs/<run_id>?mode=research`.

## Run Studio v2.5 — attempt-aware batch workflows

- **`CrossRunAnswerDiffPanel`** — per-run attempt history; Latest/Best/every attempt selectors; detail fetch for selected attempt only.
- **`BatchAnswerSubmitPanel`** — quick presets (strong/weak/unsupported to all missing) with confirm + explicit Submit.
- **`BatchDemoBundleExport`** — unified browser JSON bundle; optional local notes inclusion.
- **`BatchAnswerMatrix`** — shortcuts to cross-run diff (latest vs latest, best vs best, vs best run).

See [`docs/frontend/BATCH_RUNS.md`](../docs/frontend/BATCH_RUNS.md) for full reference.

## Run Studio v2.4 — batch report & compare UX

- **`BatchReportPreview`** — API-driven comparison report preview with copy/download/refresh on `/batches/[batchId]`.
- **`CrossRunAnswerDiffPanel`** — cross-run attempt comparison on batch detail and `/runs/compare` answers tab.
- **`BatchAnswerSubmitPanel`** — Submit missing only; per-run custom text with validation.
- **Export/copy** — report markdown from backend; matrix markdown/JSON from frontend helpers.

See [`docs/frontend/BATCH_RUNS.md`](../docs/frontend/BATCH_RUNS.md) for full reference.

## Run Studio v2.3 — batch answer workflows polish

- **`/batches/[batchId]`** — manual refresh reloads batch, run comparison, and answer matrix; auto-refresh also updates answer matrix; combined last-updated; cached matrix on error.
- **`BatchAnswerSubmitPanel`** — Global vs per-run profile modes (Strong / Weak / Unsupported / Custom / Skip); pre-submit summary with expected submission count.
- **`BatchAnswerMatrix`** — browser Export JSON/Markdown (`sourcelab_batch_answers_<batch_id>.json|.md`); grouped recommendations.
- **`/runs/compare`** — `?run_ids=…&tab=answers|artifacts` deep-linking, auto-load, Copy comparison link.

See [`docs/frontend/BATCH_RUNS.md`](../docs/frontend/BATCH_RUNS.md) for full reference.

## Run Studio v2.2 — answer-aware batch workflows

- **`/batches/[batchId]`** — auto-loads `GET /batches/{id}/answers/compare` on page load; header badges for answer coverage and review-heavy runs; `BatchAnswerSubmitPanel` for explicit sample-answer submission across selected runs; cached matrix on API error.
- **`/runs/compare`** — **Run artifacts** | **Learner answers** tabs; learner tab calls `GET /runs/answers/compare?run_ids=…`.
- **`BatchAnswerMatrix`** — status pills (No attempts, Weak latest, Needs review, Capped, Regression) and deterministic recommendation bullets via `lib/batch-run.ts` helpers.
- **CLI parity** — `sourcelab batch answers … --markdown`, `sourcelab runs answers-compare … --markdown`.

See [`docs/frontend/BATCH_RUNS.md`](../docs/frontend/BATCH_RUNS.md) for full reference.

## Run Studio v1.5 — deep links & keyboard navigation

On `/runs/[runId]`:

- **Deep links** — append `?attempt=<attempt_id>` to open Run Studio with that
  attempt selected, detail loaded, Learning update overlay active, and
  TopStatusBar historical banner when the attempt is not the latest. Invalid
  attempt ids show a warning and fall back to the latest snapshot. UI selection
  updates the URL via `router.replace` (no full reload; other query params
  preserved). **Copy attempt link** appears above attempt detail.
- **Keyboard shortcuts** (History or Diff tab; ignored while focus is in an
  input/textarea/select):
  - `↑` / `←` — newer attempt · `↓` / `→` — older attempt
  - `Home` — first attempt · `End` — latest attempt
  - `Enter` — scroll/focus attempt detail (History tab)
  - `Escape` — back to latest run snapshot (clears `?attempt=`)
- **Shared history state** — `useAnswerHistory` feeds History, Diff, Learning
  update, TopStatusBar, and the diffusion timeline attempt lane from one fetch.

Run frontend unit tests: `npm run test` (Vitest, `lib/attempt-summary.test.ts`).

### A note on the backend

The Run Studio needs per-claim / per-chunk / per-citation detail that the run
*inventory* endpoint does not expose. This is read from the backend via the
read-only endpoint:

```
GET /runs/{run_id}/artifacts/{artifact_name}
```

There is no `/release` HTTP endpoint, so `/release` is composed client-side from
the proof bundle, golden evals, harness, version, and source-pack status. The
SBOM / attestation / checksums / bundle / publish-plan steps are produced by the
`sourcelab release …` CLI and are surfaced as a documented checklist.

## SourceLab Library Builder v1

Run detail and Research views can surface `source_expansion_suggestions.json` when a run has thin evidence. The library CLI (`sourcelab library …`) is filesystem-backed and complements the Research Library theme — collect local docs, score quality, and dry-run promotion into curated packs without changing the Run Studio frontend architecture.

## Library-Aware Research Engine v1

Research mode panels load backend artifacts via `refreshRunContext`: **Research plan**, **Retrieval strategy**, **Source coverage (engine)**, **Evidence-bound lesson**, **Genericness**, **Topic memory**, and **Expansion suggestions** (`ResearchEnginePanels.tsx`). Types live in `lib/types.ts`; artifacts are fetched from `GET /runs/{run_id}/artifacts/{name}`.

CLI: `sourcelab research plan|coverage|genericness|profile|expansion`. Lesson create (`sourcelab lesson create`) runs the research pipeline automatically and writes artifacts under `artifacts/runs/<run_id>/`.

## Adaptive Research Loop v1

Research mode adds **Topic memory** (`TopicMemoryPanel.tsx`), **Lesson evolution** (`LessonEvolutionPanel.tsx`), and **Library expansion plan** (`LibraryExpansionPlanPanel.tsx`) panels. These load `lesson_evolution_report.json`, `library_expansion_plan.json`, and profile-aware fields from `research_plan.json` via `refreshRunContext`.

CLI: `sourcelab research evolution --run latest` and `sourcelab research evolution --topic "..." --source-pack <pack>`.

## Research Gap Closure Loop v1

Research mode adds **Expansion execution** (`ExpansionExecutionPanel.tsx`), **Library improvement** (`LibraryImprovementPanel.tsx`), **Source promotion** (`SourcePromotionPanel.tsx`), and **Gap closure** (`GapClosurePanel.tsx`) panels. These load gap-closure artifacts via `refreshRunContext` (CLI-only execution; UI shows reports and collector commands).

CLI:

```bash
sourcelab research expansion run --run latest --dry-run
sourcelab research expansion run --run latest --execute
sourcelab research expansion promote --run latest --dry-run
sourcelab research expansion promote --run latest --force
sourcelab research gap-closure --run latest
sourcelab research gap-closure --topic "..." --source-pack <pack>
sourcelab research gap-closure run --run latest --dry-run
sourcelab research gap-closure run --run latest --execute --create-followup
```

Run Studio panels include **Copy command**, **Copy full workflow**, **Copy answer-bridge workflow**, **Copy replay command**, and **Copy next safe command** buttons (`GapClosureWorkflowActions.tsx`) with CLI commands from `lib/gap-closure-workflow.ts`. Orchestration artifact: `gap_closure_orchestration.json`.

### Adaptive Research Loop v1.2

```bash
sourcelab research gap-closure run --run latest --dry-run --answer-text "A strong answer should define the objective, evidence, risks, and validation path."
sourcelab research gap-closure replay --run latest
```

Gap closure and topic memory panels show answer-submit status, topic profile updated, follow-up run id, gap closure verdict, and next safe command when orchestration artifacts exist.
