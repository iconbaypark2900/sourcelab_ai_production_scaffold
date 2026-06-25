# SourceLab Local v1.0 GA — Release Notes

**Version:** 1.0.0  
**Release label:** SourceLab Local v1.0 GA  
**Date:** 2026-06-20

## Product claim

SourceLab Local v1.0 is a reproducible local-first source-grounded learning/proof system that can be installed, tested, demoed, verified, exported, and inspected from CLI, API, dashboard, and release artifacts.

## Changes since RC (1.0.0-rc1)

- **Dependency lock files** under `requirements/` (`base`, `dev`, `api`, `ui`, `ingest`, `retrieval`, `models`, `all`) plus `scripts/freeze_requirements.sh` → `requirements/lock-local-v1.txt`
- **`sourcelab release bundle`** — distributable artifact bundle (`sourcelab_local_v1_ga_bundle/` + zip)
- **`sourcelab release checksums`** — `artifacts/release/SHA256SUMS`
- **`sourcelab release sbom`** — lightweight `sbom-local-v1.json`
- **`sourcelab release attest`** — unsigned `release_attestation.json`
- **`make freeze`** — reproducible `requirements/lock-local-v1.txt`
- **Strengthened `sourcelab doctor`** — Docker/make availability, bundle status, strict release, golden eval, recommended next command
- **Dashboard polish** — release overview landing, bundle/export paths, graceful missing-artifact handling
- **Optional Docker dashboard** — `docker compose --profile dashboard up sourcelab-dashboard`
- **`make ga-check`** — full GA acceptance pipeline
- **Release process doc** — `docs/operations/RELEASE_PROCESS.md`

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev,api,ui,ingest,retrieval,models]"
```

Optional reproducible install (after freezing):

```bash
bash scripts/freeze_requirements.sh
pip install -r requirements/lock-local-v1.txt
pip install -e .
```

## Demo and verify

```bash
sourcelab init-local
sourcelab doctor
sourcelab local-demo
sourcelab verify-release --strict
sourcelab release bundle
sourcelab release checksums
sourcelab release sbom
sourcelab release attest
sourcelab release manifest
sourcelab release report
sourcelab export latest --format markdown
```

Or one shot:

```bash
make ga-check
```

## Acceptance commands

```bash
pytest -q
sourcelab doctor
sourcelab init-local
sourcelab local-demo
sourcelab verify-release --strict
sourcelab release bundle
sourcelab release checksums
sourcelab release sbom
sourcelab release attest
sourcelab release manifest
sourcelab release report
```

## Known limitations

- No authentication or multi-user support
- No persistent database, Redis, or background workers
- No live web search
- Deterministic fallbacks for generation, embeddings, and scoring (no paid APIs required)
- Docker dashboard is optional (`--profile dashboard`); API container does not require Streamlit at runtime unless dashboard profile is used
- Release bundle excludes `.venv`, caches, and files larger than 5 MiB

## Next milestones

- Hosted deployment profile (beyond local-first)
- Additional source packs beyond PQC v1
- Optional neural retrieval as default when extras installed
- Signed release artifacts and SBOM

## Walkthrough

See `docs/demo/LOCAL_V1_WALKTHROUGH.md` and `docs/operations/RELEASE_PROCESS.md`.
