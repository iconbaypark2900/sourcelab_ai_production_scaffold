# SourceLab Local v1.0 — Release Process

Step-by-step guide for tagging **SourceLab Local v1.0 GA**. Do not run `git tag` until all steps pass.

## Prerequisites

- Python 3.10+
- Project root with editable install: `pip install -e ".[dev,api,ui,ingest,retrieval,models]"`

## Release checklist

Run from the project root (`sourcelab_ai_production/`):

### 1. Unit and integration tests

```bash
pytest -q
```

Expected: all tests pass (1 skipped acceptable if marked slow and not run).

### 2. Environment and setup

```bash
sourcelab doctor
sourcelab init-local
```

Expected: doctor `status` is `PASS` for core checks; init-local `passed` is `true`.

### 3. Full local demo

```bash
sourcelab local-demo
```

Expected: `passed: true`, strict release status `PASS`.

### 4. Strict release verification

```bash
sourcelab verify-release --strict
```

Expected: `status: PASS`, no blocking failures.

### 5. Release artifact bundle

```bash
sourcelab release bundle
```

Expected: creates:

- `artifacts/release/sourcelab_local_v1_ga_bundle/`
- `artifacts/release/sourcelab_local_v1_ga_bundle.zip`

Legacy RC bundles (`sourcelab_local_v1_rc_bundle`) are detected with a migration warning; re-run `release bundle` to produce GA artifacts.

### 6. Release checksums

```bash
sourcelab release checksums
```

Expected: writes `artifacts/release/SHA256SUMS` covering the GA bundle, manifest, report, and SBOM/attestation when present.

### 7. SBOM and attestation

```bash
sourcelab release sbom
sourcelab release attest
```

Expected:

- `artifacts/release/sbom-local-v1.json`
- `artifacts/release/release_attestation.json` (`unsigned: true`)

### 8. Manifest and report

```bash
sourcelab release manifest
sourcelab release report
```

Expected: JSON manifest and Markdown report on stdout (or paths under `artifacts/release/`).

### 9. Optional dependency lock

```bash
make freeze
# or: bash scripts/freeze_requirements.sh
```

Expected: writes `requirements/lock-local-v1.txt` with Python version header (editable local project lines excluded).

### 10. Optional GA Makefile target

```bash
make ga-check
```

Runs steps 1–7 in sequence (includes full `local-demo`, SBOM, and attestation).

### 11. Git hygiene (manual)

```bash
git status
```

Ensure working tree is clean and release notes / changelog are updated.

### 12. Tag (manual — do not automate)

When all steps pass:

```bash
git tag -a local-v1.0.0 -m "SourceLab Local v1.0 GA"
```

Push tag only when ready:

```bash
git push origin local-v1.0.0
```

## Optional verification

```bash
docker compose config
docker compose --profile dashboard config
make smoke
make release-check
```

## Rollback

If strict verification fails after demo:

1. Inspect `artifacts/release/local_v1_release_report.md`
2. Fix blocking items from `sourcelab verify-release --strict`
3. Re-run `sourcelab local-demo` and bundle steps

## Related docs

- `RELEASE_NOTES_LOCAL_V1_GA.md`
- `RELEASE_NOTES_LOCAL_V1_RC.md`
- `docs/demo/LOCAL_V1_WALKTHROUGH.md`
- `docs/operations/RUNBOOK.md`
