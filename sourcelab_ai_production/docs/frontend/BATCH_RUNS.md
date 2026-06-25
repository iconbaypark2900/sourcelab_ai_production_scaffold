# Batch Runs & Compare — Run Studio v2.5

Run Studio v2.5 adds **attempt-aware cross-run diff**, **batch quick submit presets**, **unified demo bundle export**, and **matrix shortcuts to cross-run diff**. v2.4 (report preview, submit missing only, per-run custom text, export/copy) and v2.3 polish are preserved. Everything remains local-first, filesystem-backed, and synchronous — no auth, database, Redis, workers, or WebSockets.

## CLI

```bash
# Create a batch from JSON config
sourcelab batch create --name "PQC migration comparison" --config examples/batch_pqc.json

# List / show / compare runs
sourcelab batch list
sourcelab batch show <batch_id>
sourcelab batch compare <batch_id>

# Compare learner answers (compact table, JSON, or markdown)
sourcelab batch answers <batch_id>
sourcelab batch answers <batch_id> --json
sourcelab batch answers <batch_id> --markdown

# Compare arbitrary runs
sourcelab runs compare <run_id_1> <run_id_2>
sourcelab runs answers-compare <run_id_1> <run_id_2>
sourcelab runs answers-compare <run_id_1> <run_id_2> --markdown
```

## API

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/lessons/batch` | Synchronous batch creation |
| GET | `/batches/` | List batches |
| GET | `/batches/{batch_id}` | Batch detail |
| GET | `/batches/{batch_id}/compare` | Compare batch runs |
| GET | `/batches/{batch_id}/answers/compare` | Compare learner answers in batch |
| GET | `/batches/{batch_id}/report` | Comparison report JSON + markdown |
| GET | `/batches/{batch_id}/report/download` | Download markdown report |
| GET | `/runs/compare?run_ids=id1,id2` | Compare 2+ runs |
| GET | `/runs/answers/compare?run_ids=id1,id2` | Compare learner answers across runs |
| POST | `/learning/answers` | Submit learner answer (batch sample panel uses this) |

404 when batch/run missing. Manual answer compare requires 2+ runs (422). Runs without attempts are included with `attempt_count=0`.

## Artifacts

Each batch writes under `artifacts/batches/<batch_id>/`:

- `batch_manifest.json` — input items, run IDs, failures, version (`v2.3`)
- `batch_summary.json` — totals, topics, source packs, artifact counts
- `comparison_report.json` — full run comparison payload (when ≥2 runs)
- `comparison_report.md` — human-readable export; includes learner answer matrix, weak/review warnings, and recommendations when attempts exist (graceful no-attempts section otherwise)

## Run Studio pages

| Route | Purpose |
| --- | --- |
| `/batches` | List batches |
| `/batches/new` | Batch form, planned-run preview, staged progress during POST, presets |
| `/batches/[batchId]` | Detail, unified refresh bar, run cards, answer matrix, attempt-aware cross-run diff, demo bundle export, sample-answer submit, run + answer comparison, batch report preview |
| `/runs/compare?run_ids=…&tab=answers\|artifacts` | Multi-run compare with deep-link tab selection |

### Batch report preview (v2.4)

`BatchReportPreview` on batch detail (after Compare, before debug):

- Loads `GET /batches/{batch_id}/report` — no direct filesystem reads from Next.js
- Status pill: available / empty / not generated / load failed
- Rendered markdown preview + raw markdown toggle
- **Copy report markdown**, **Download report markdown** (`GET …/report/download`)
- **Refresh report** + loaded timestamp; retries on failure via connection card
- Unified batch refresh also triggers report reload

### Cross-run answer diff (v2.4 / v2.5)

`CrossRunAnswerDiffPanel` on batch detail and `/runs/compare` (answers tab):

- Compare attempts across **two runs** via `GET /learning/answers/{run_id}/{attempt_id}`
- Run A/B selectors; attempt selectors: **Latest**, **Best**, and every attempt from `GET /learning/answers/{run_id}` (label: `attempt_… | score X | clear/review`)
- Per-run attempt history cached on error; detail fetched only for the selected attempt
- Side-by-side: topic, run/attempt IDs, scores, rubric, uncapped, review, cap reason, focus, answer preview/full, strengths/weaknesses
- Delta cards: score, rubric, uncapped, review changed, answer length
- Frontend-driven — no proof artifact mutation

### Matrix shortcuts to cross-run diff (v2.5)

`BatchAnswerMatrix` shortcuts (batch detail):

- **Compare latest vs latest** — first two runs with attempts, both latest
- **Compare best vs best** — first two runs with attempts, both best
- **vs best run** (per row) — this run's latest vs batch best run's best attempt
- Scrolls to `#cross-run-answer-diff` with preselected runs/attempts

### Batch quick submit presets (v2.5)

`BatchAnswerSubmitPanel`:

- **Submit strong/weak/unsupported to all missing** — selects runs with `attempt_count === 0`, sets global profile, requires confirm dialog + explicit Submit click
- When all runs have attempts: **All runs already have attempts.**
- Per-run profile mode unchanged

### Unified demo bundle export (v2.5)

`BatchDemoBundleExport` on batch detail:

- **Download demo bundle JSON** — `sourcelab_batch_demo_bundle_<batch_id>.json`
- Includes: batch summary, run comparison (if loaded), answer comparison (if loaded), report markdown (if loaded), answer matrix md/json, frontend metadata
- Optional **Include local attempt notes** checkbox — browser-local notes only, not proof artifacts
- Does not mutate proof artifacts

### Submit missing only (v2.4)

`BatchAnswerSubmitPanel`:

- **Submit missing only** selects runs with `attempt_count === 0` from the answer matrix
- When all runs have attempts: **All runs already have attempts.**
- Still requires explicit profile selection + Submit click — no auto-submit

### Per-run custom answer text (v2.4)

In **Per-run profile** mode:

- **Custom text** profile shows a compact textarea per selected row
- Empty custom text blocks submit with a per-row validation message
- Global custom mode unchanged; pre-submit summary counts custom rows

### Export / copy controls (v2.4)

Near report and matrix:

| Control | Source |
| --- | --- |
| Copy report markdown | `GET /batches/{id}/report` payload |
| Download report markdown | `GET /batches/{id}/report/download` |
| Copy answer matrix markdown | Frontend payload (`buildAnswerMatrixExportMarkdown`) |
| Download answer matrix JSON/MD | Frontend payload |

Does not mutate proof artifacts or answer history.

### Batch detail refresh + answer matrix (v2.3)

- **Manual Refresh** — reloads batch detail, run comparison (when ≥2 runs), and answer matrix
- **Auto-refresh** (when enabled) — also refreshes the answer matrix on each batch poll
- **Combined last-updated** — refresh bar shows the most recent of batch or answer matrix timestamps
- **Cached matrix on error** — prior answer comparison stays visible; connection card + retry
- **Compare learner answers** — manual button only; refreshes matrix and scrolls to `#answer-matrix`

### Batch sample-answer submission (v2.3)

`BatchAnswerSubmitPanel` on batch detail:

- **Profile modes:** Global profile (default) | Per-run profile
- **Profiles:** Strong, Weak, Unsupported, Custom text (global only), Skip (no submit)
- **Per-run mode:** each selected run picks its own profile; Skip = excluded from submission
- **Pre-submit summary:** selected count, skipped count, profile counts, expected submissions
- POST `/learning/answers` per run sequentially (same path as Run Studio)
- Per-run result: submitted, skipped, score, needs review, or failed
- Refreshes answer matrix after completion
- Explicit user action only — no auto-submit

### Answer matrix browser export (v2.3)

`BatchAnswerMatrix` export buttons:

- **Export JSON** — current comparison payload + grouped recommendations + artifact reminder
- **Export Markdown** — frontend-generated table and grouped recommendations
- Filenames: `sourcelab_batch_answers_<batch_id>.json|.md`
- Does not mutate proof artifacts or answer history

### `/runs/compare` deep-linking (v2.3)

- URL: `/runs/compare?run_ids=id1,id2&tab=answers|artifacts`
- Valid `run_ids` pre-fill the form and auto-load comparison on mount
- `tab=answers` → Learner answers tab; `tab=artifacts` → Run artifacts; invalid tab → artifacts
- Tab and run ID changes update the URL via `router.replace` (unrelated query params preserved)
- **Copy comparison link** copies the full workspace URL

### Grouped recommendations (v2.3)

`BatchAnswerMatrix` groups recommendations into:

- **Coverage** — runs without attempts
- **Weak latest** — weakest run and sub-threshold scores
- **Review / cap risk** — review-heavy and capped runs
- **Regression** — best >> latest delta
- **Best performer** — highest best score
- **Next action** — combined follow-up from backend recommendation

### Batch progress UX (`/batches/new`)

- **Before submit:** planned run rows in the side panel
- **During submit:** estimated pipeline stages while the single blocking POST runs
- **After response:** staged view replaced with actual run statuses, then navigation to batch detail

### Batch presets (localStorage)

Built-in starters on `/batches/new`:

- PQC migration comparison
- AI safety policy comparison
- Crypto inventory readiness

Users can save/delete custom presets in `localStorage` (browser-local only).

## Comparison dimensions

### Run comparison (v2.0)

1. **Retrieval** — source IDs, chunk IDs, pairwise Jaccard
2. **Claims** — totals, supported/unsupported, citation resolution
3. **Proof/harness** — gate status, artifact count
4. **Lesson** — topic, format, pack, difficulty, length

### Answer comparison (v2.1 / v2.2 / v2.3)

Artifact-driven from `artifacts/runs/<run_id>/answer_attempts/`:

- Per run: latest/best attempt ID + score, attempt count, review/cap counts, next-task focus
- Batch summary: averages, best/weakest runs, review-heavy runs
- **Labels:** No attempts, Weak latest (&lt;60% default), Needs review, Capped, Regression (best >> latest)
- **Grouped recommendations** (v2.3): frontend grouping into coverage, weak, review/cap, regression, best, next action

## Example config

See [`examples/batch_pqc.json`](../../examples/batch_pqc.json).
