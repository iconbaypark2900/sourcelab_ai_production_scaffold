# SourceLab Local — Offline Install Guide

Install and verify SourceLab Local without internet access after obtaining a source checkout or release bundle.

## Prerequisites

- Python 3.10+
- Local clone or extracted release bundle
- Optional: GPG for signature verification

## 1. Local clone install

From the project root (`sourcelab_ai_production/`):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev,api,ui,ingest,retrieval,models]"
sourcelab init-local
sourcelab doctor
```

## 2. Lock file usage

For reproducible installs, use the pinned lock file:

```bash
python -m pip install -r requirements/lock-local-v1.txt
python -m pip install -e .
```

Verify the lock file has not drifted:

```bash
make freeze-check
```

If drift is detected, regenerate on a connected machine with `make freeze` and commit the updated lock file.

## 3. SHA256SUMS verification

After building or extracting release artifacts:

```bash
cd artifacts/release
sha256sum -c SHA256SUMS
```

Or inspect checksums manually:

```bash
sourcelab release checksums
cat artifacts/release/SHA256SUMS
```

## 4. SBOM and attestation inspection

```bash
sourcelab release sbom
sourcelab release attest
cat artifacts/release/sbom-local-v1.json
cat artifacts/release/release_attestation.json
```

The attestation includes hashes for the bundle zip, checksums file, and SBOM, plus source pack and eval summary references.

## 5. Optional signature verification

Dry-run signing (default, no GPG required):

```bash
sourcelab release sign --mode dry-run
sourcelab release verify-signature
```

If a signed `SHA256SUMS.sig` is present and GPG is installed:

```bash
gpg --verify artifacts/release/SHA256SUMS.sig artifacts/release/SHA256SUMS
```

## 6. Run without internet

SourceLab Local is designed for offline operation:

```bash
sourcelab source-pack install pqc_v1
sourcelab local-demo
sourcelab evals run --pack pqc_v1
sourcelab verify-release --strict
```

No live web search, hosted databases, or external APIs are required for the default deterministic path.

## 7. Optional extras

| Extra | Purpose | Offline note |
|---|---|---|
| `api` | FastAPI server | Works offline |
| `ui` | Streamlit dashboard | Works offline |
| `ingest` | PDF/URL ingestion | URL ingest needs network |
| `retrieval` | Neural embeddings | Models may need prior download |
| `models` | Local LLM routing | External LLM endpoints need network |

## 8. Publish dry-run (no upload)

Plan a release upload without network access:

```bash
sourcelab release publish --dry-run
cat artifacts/release/publish_plan.json
```

## Troubleshooting

- **Lock drift:** run `make freeze` on a connected machine, then copy `requirements/lock-local-v1.txt`.
- **Missing bundle artifacts:** run `sourcelab release bundle`, then `checksums`, `sbom`, and `attest`.
- **Strict release fails:** ensure `pqc_v1` golden evals pass: `sourcelab evals run --pack pqc_v1`.
