# Release Automation Guide

## Objective

Add three release engineering features (Epic 8):
1. **Release versioning strategy** — semantic versioning policy and automation
2. **Release changelog generation** — auto-generate changelog from git log and release manifest
3. **Release automation (CI/CD)** — GitHub Actions workflow for test, build, release

## Current State

- `src/sourcelab/release/` has manifest, checklist, thresholds, report modules
- `src/sourcelab/version.py` has version metadata
- `sourcelab release` CLI has: check, manifest, report, bundle, checksums, sbom, attest, sign, verify-signature, publish
- `sourcelab verify-release --strict` passes with 0 blocking failures
- Release artifacts go to `artifacts/release/`

---

## 1. Release Versioning Strategy

### Policy

SourceLab uses semantic versioning (`MAJOR.MINOR.PATCH`):

| Change | Version Bump | Example |
|--------|-------------|---------|
| Breaking CLI/API change | MAJOR | 1.0.2 → 2.0.0 |
| New feature (backward compatible) | MINOR | 1.0.2 → 1.1.0 |
| Bug fix, source content fix | PATCH | 1.0.2 → 1.0.3 |

### Implementation

File: `src/sourcelab/release/versioning.py`

```python
class VersionPolicy:
    """Semantic versioning policy for SourceLab releases."""
    
    def determine_bump(self, changes: list[Change]) -> str:
        """Determine version bump type from changes."""
        if any(c.breaking for c in changes):
            return "major"
        if any(c.feature for c in changes):
            return "minor"
        return "patch"
    
    def bump_version(self, current: str, bump_type: str) -> str:
        """Calculate next version string."""
        ...
```

### Wiring

- Add `sourcelab release version --bump <type>` CLI command
- Update `version.py` with new version after bump
- Record version in release manifest

---

## 2. Release Changelog Generation

### Implementation

File: `src/sourcelab/release/changelog.py`

```python
class ChangelogGenerator:
    """Generate changelog from git log and release manifest."""
    
    def generate(
        self,
        from_version: str,
        to_version: str,
        format: str = "markdown",
    ) -> str:
        """
        Generate changelog between two versions.
        
        Sources:
        - Git log between version tags
        - Release manifest changes
        - Golden eval summary changes
        - New source packs added
        """
        ...
```

### Changelog format

```markdown
## v1.0.3 — 2026-06-25

### Added
- Extension pack eval alignment for 6 packs
- Tokenizer-aware chunking with sliding window
- Rubric-based LLM judge for answer scoring

### Changed
- Strengthened source content for blockchain_provenance_v1
- Updated bootstrap script with extra_sections field

### Fixed
- Curriculum dashboard TypeScript type errors

### Verification
- 797 Python tests passing
- 247 frontend tests passing
- sourcelab verify-release --strict: PASS
```

### Wiring

- Add `sourcelab release changelog --from <version> --to <version>` CLI command
- Write changelog to `artifacts/release/changelog_<version>.md`
- Include changelog in release bundle

---

## 3. Release Automation (CI/CD)

### Implementation

File: `.github/workflows/release.yml`

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: |
          python -m pip install -e ".[dev,api,ui,ingest,retrieval,models]"
      - run: python -m pytest -q
      - run: |
          cd apps/web && npm ci && npm run build && npm run test
      - run: sourcelab local-demo
      - run: sourcelab verify-release --strict

  release:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build release bundle
        run: |
          sourcelab release bundle
          sourcelab release checksums
          sourcelab release sbom
      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          files: artifacts/release/sourcelab_local_v1_ga_bundle/*
          body_path: artifacts/release/local_v1_release_report.md
```

### Pre-release workflow

File: `.github/workflows/ci.yml`

```yaml
name: CI

on: [push, pull_request]

jobs:
  python-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: python -m pip install -e ".[dev,api,ui,ingest,retrieval,models]"
      - run: python -m pytest -q

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: cd apps/web && npm ci && npm run build && npm run test

  release-gate:
    needs: [python-tests, frontend-tests]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: |
          python -m pip install -e ".[dev,api,ui,ingest,retrieval,models]"
          sourcelab init-local
          sourcelab local-demo
          sourcelab verify-release --strict
```

### Wiring

- Add `.github/workflows/ci.yml` for continuous integration
- Add `.github/workflows/release.yml` for release automation
- Add `scripts/prepare_release.sh` for local pre-release checks
- Document release process in `docs/operations/RELEASE_PROCESS.md` (update existing)

## Verification

```bash
source .venv/bin/activate

# Test versioning
sourcelab release version --bump patch --dry-run

# Test changelog
sourcelab release changelog --from v1.0.2 --to v1.0.3 --dry-run

# Full suite
python -m pytest -q
sourcelab local-demo
sourcelab verify-release --strict
```

## Scope Notes

- CI/CD is for automation only; do not add hosted deployment or cloud infrastructure
- GitHub Actions workflows should use caching for pip and npm
- Release artifacts should be attached to GitHub Release, not pushed to external registry
- Version bumping should be manual (not automatic from commit messages) to maintain quality control
