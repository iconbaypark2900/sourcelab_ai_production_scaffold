# Changelog

All notable changes to SourceLab AI are documented in this file.

## [1.0.0] - 2026-06-20 (GA)

### Added
- **SourceLab Local v1.0 GA** release stabilization
- `requirements/` split files: `base.txt`, `dev.txt`, `api.txt`, `ui.txt`, `ingest.txt`, `retrieval.txt`, `models.txt`, `all.txt`
- `scripts/freeze_requirements.sh` → `requirements/lock-local-v1.txt` for reproducible installs
- `sourcelab release bundle` — distributable release artifact bundle (directory + zip)
- `sourcelab release checksums` — `artifacts/release/SHA256SUMS`
- `make ga-check` — pytest, doctor, init-local, local-demo, verify-release, bundle, checksums
- Optional `sourcelab-dashboard` Docker Compose service (`--profile dashboard`)
- `docs/operations/RELEASE_PROCESS.md` — GA tag guidance
- `RELEASE_NOTES_LOCAL_V1_GA.md`
- Dashboard release overview landing and strengthened doctor output

### Changed
- Package version set to `1.0.0` (GA)
- Release label: **SourceLab Local v1.0 GA**
- Docker image includes `ui` extra for optional dashboard profile
- Release bundle renamed to `sourcelab_local_v1_ga_bundle` (legacy RC name detected with migration warning)
- `sourcelab release sbom` and `sourcelab release attest` for SBOM and unsigned attestation artifacts
- Extended `sourcelab release checksums` to cover manifest, report, SBOM, and attestation
- `make freeze` target and improved `scripts/freeze_requirements.sh` (Python version header, excludes editable installs)
- Doctor reports `dependency_lock_exists` and `dependency_lock_path`
- CI workflow `.github/workflows/local-v1-release.yml`
- Source pack template at `data/source_packs/TEMPLATE/` and `docs/source_packs/CREATING_SOURCE_PACKS.md`

## [1.0.0-rc1] - 2026-06-20

### Added
- **SourceLab Local v1.0 RC** packaging and demo kit
- `sourcelab version` — package version, release label, Python version, project root, artifacts directory
- `sourcelab doctor` — environment readiness checks (JSON)
- `sourcelab init-local` — idempotent first-run setup
- Demo scripts: `scripts/local_v1_demo.sh`, `scripts/local_v1_smoke.sh`, `scripts/start_api.sh`, `scripts/start_dashboard.sh`
- Makefile targets: `install`, `install-all`, `test`, `smoke`, `demo`, `api`, `dashboard`, `release-check`, `clean-artifacts`
- Docker-lite packaging (`Dockerfile`, `docker-compose.yml`) for API-only deployment
- Demo documentation under `docs/demo/`
- Integration smoke tests in `tests/integration/test_local_v1_smoke.py`
- Release manifest fields: doctor status, init status, smoke status, package extras, Docker note, demo script paths

### Changed
- Package version set to `1.0.0-rc1`
- `GET /version` returns full version metadata aligned with CLI
- `sourcelab api --serve` starts the FastAPI server (without `--serve`, prints launch instructions)
- README updated for Local v1 quickstart and product claims

### Fixed
- Golden eval integration verified at 45/45 pass rate for `pqc_v1`

## [0.1.0] - prior scaffold

- Initial production scaffold with source-grounded pipeline, verification, harness, learning, API, and dashboard placeholders
