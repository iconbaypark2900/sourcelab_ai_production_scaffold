## Learned User Preferences

- Prefer small, scoped patches over new milestones for follow-up fixes (e.g. parking-lot items as v1.0.2 patches).
- Do not lower eval or release thresholds to hide failures; fix underlying behavior instead.
- After wiring CLI flags or behavior changes, add regression tests for those flags and commands.
- Expect end-to-end verification: `pytest -q`, `sourcelab local-demo`, and `sourcelab verify-release --strict`; for Run Studio frontend changes also run `cd apps/web && npm run build` and `npm run test`.
- Prefer transparent learning metrics in artifacts (`uncapped_score`, `cap_reason`, `rubric_alignment_score`, `final_score`, `human_review_reason`).
- Avoid large new subsystems for polish or incremental fixes; preserve existing commands and keep tests deterministic.
- Do not rewrite the Run Studio frontend or remove Streamlit for incremental milestones; extend in place.
- For Run Studio work, do not add auth, databases, Redis, workers, WebSockets, or hosted deployment unless explicitly scoped; batch workflows stay local-first, filesystem-backed, and synchronous/polling-based.
- Frontend-only Run Studio milestones should avoid backend persistence; use URL state and localStorage for session restore.
- Bootstrap source-pack scaffolding is non-destructive by default; use `--force` only when explicitly required to overwrite existing pack files.

## Learned Workspace Facts

- AnswerScorer's high-risk detector (`_check_high_risk` + `_citation_spans` + `_overlaps_any` in `src/sourcelab/learning/answer_scorer.py`) skips high-risk matches that fall inside single-quoted source titles (`'Title'`) or bracketed source IDs (`[source_id]`), so citing a source whose title contains a risky phrase (e.g. `'Risk Myths Quantum Breaks Rsa Today'`) is not penalized. Negation check remains first-match `.search` semantics with a 24-char window; do not switch to `finditer` without widening that window.

- Scaffold repo root is `sourcelab_ai_production_scaffold`; application code lives in `sourcelab_ai_production`.
- Run sourcelab CLI workflows from `sourcelab_ai_production` with `.venv` activated (`source .venv/bin/activate`).
- SourceLab Local is at version **1.0.2** (`SourceLab Local v1.0.2`), including the Learning Metrics Consistency patch.
- Strict release verification (`sourcelab verify-release --strict`) requires `pqc_v1` golden evals; `ai_safety_v1` is an additional curated pack.
- First-run setup uses `sourcelab init-local`; health checks use `sourcelab doctor`.
- Release bundle naming uses `sourcelab_local_v1_ga_bundle` under `artifacts/release/`.
- Answer scoring exposes two grounding metrics: rubric-facing `source_grounding_score` in `answer_review.json`, and concept-overlap evidence in `source_grounding_review.json`.
- Run artifacts live under `artifacts/runs/<RUN_ID>/`; `artifacts/runs/latest` is not a symlink—resolve the run ID via `sourcelab runs latest`.
- Next.js 16 Run Studio frontend lives at `sourcelab_ai_production/apps/web/`; FastAPI is the source of truth, Streamlit is preserved; run locally with `sourcelab api --serve` and `cd apps/web && npm run dev`.
- Immutable answer attempts live under `artifacts/runs/<RUN_ID>/answer_attempts/` with latest-answer snapshot files for backward compatibility; answer history CLI: `sourcelab answer history`, `sourcelab answer show`, and `sourcelab answer diff`.
- Source pack bootstrap lives at `scripts/bootstrap_sourcelab_source_packs.py`: writes `manifest.json` and gold evals (`retrieval_gold.json`, `claim_gold.json`, `answer_gold.json`, `lesson_gold.json`); `--repair-manifests` repairs existing packs; 12 bootstrapped packs (3 core + 9 extension) sit alongside `pqc_v1` and `ai_safety_v1`.
- Batch run artifacts live under `artifacts/batches/<batch_id>/`; batch CLI includes `sourcelab batch create`, `batch list`, `batch compare`, and `batch answers`; Run Studio v2.0–v2.5 batch/answer workflows are complete.
