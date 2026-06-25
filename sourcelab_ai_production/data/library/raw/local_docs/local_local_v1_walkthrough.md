# SourceLab Local v1 Walkthrough

Step-by-step guide for evaluating **SourceLab Local v1.0 RC** on a fresh machine.

## 1. What SourceLab solves

SourceLab AI is a **source-grounded adaptive technical lab generator**. It:

1. Ingests approved technical sources (PQC pack included)
2. Retrieves relevant chunks for a topic
3. Generates a lesson with scenario, rubric, and answer key
4. Extracts and verifies claims against sources
5. Scores learner answers and updates a skill profile
6. Produces a **proof bundle** for audit and release gating

It does **not** claim perfect correctness. It is designed to **fail closed** when grounding is insufficient.

## 2. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev,api,ui,ingest,retrieval,models]"
```

## 3. First-run setup

```bash
sourcelab init-local
sourcelab doctor
```

Expected: `doctor` status `PASS` (release manifest may show `missing` until first demo).

## 4. Install PQC source pack

Handled by `init-local`. Verify:

```bash
sourcelab source-pack validate pqc_v1
sourcelab source-pack status pqc_v1
sourcelab sources validate
```

## 5. Run grounded lesson

```bash
sourcelab demo --topic "post-quantum cryptography migration"
sourcelab lesson show --latest
sourcelab runs show latest
```

Inspect artifacts under `artifacts/runs/<run_id>/`:

- `generated_lesson.md`
- `claim_map.json`
- `citation_resolution.json`
- `harness_report.json`
- `proof_bundle_manifest.json`

## 6. Claim verification

```bash
sourcelab verify latest
sourcelab verify claims --latest
sourcelab review queue --latest
```

Check citation resolution rate and unsupported high-risk claim count.

## 7. Answer scoring

```bash
sourcelab answer submit --topic "post-quantum cryptography migration" \
  --text "Begin with crypto inventory; prioritize hybrid migration; do not claim RSA is broken today without evidence."
sourcelab learning report
sourcelab profile show
```

## 8. Proof bundle

```bash
sourcelab proof latest
sourcelab harness latest
```

## 9. Golden evals

```bash
sourcelab evals run --pack pqc_v1
sourcelab evals latest --pack pqc_v1
```

Expect 45/45 cases passing for `pqc_v1`.

## 10. Strict release verification

```bash
sourcelab verify-release --strict
sourcelab release check
```

Both should report `PASS` after a successful demo run.

## 11. Full local demo (one command)

```bash
sourcelab local-demo
# or
bash scripts/local_v1_demo.sh
```

## 12. Export reviewable report

```bash
sourcelab export latest --format markdown
sourcelab release manifest
sourcelab release report
```

## 13. Dashboard & API

```bash
# Terminal 1
sourcelab dashboard --launch

# Terminal 2
sourcelab api --serve
curl http://localhost:8000/version
```

## 14. Docker (API only)

```bash
docker compose up sourcelab-api
curl http://localhost:8000/health
```

## 15. Test suite

```bash
pytest -q
pytest -q tests/integration/test_local_v1_smoke.py -m "not slow"
```

See `RELEASE_NOTES_LOCAL_V1_RC.md` for known limitations and next milestones.
