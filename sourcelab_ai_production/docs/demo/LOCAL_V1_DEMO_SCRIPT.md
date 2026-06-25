# SourceLab Local v1 Demo Script

Presenter script for a 15–20 minute live demo of **SourceLab Local v1.0 RC**.

## Setup (before the demo)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,api,ui,ingest,retrieval,models]"
sourcelab init-local
```

## Act 1 — What SourceLab is (2 min)

> SourceLab generates adaptive technical lessons from **approved sources**, verifies that claims are grounded in those sources, scores learner answers with a visible rubric, and adapts the next task from a saved skill profile. It fails closed when sources are missing or high-risk claims are unsupported.

Show project tree briefly:

```bash
sourcelab version
sourcelab doctor
```

## Act 2 — PQC source pack (3 min)

```bash
sourcelab source-pack validate pqc_v1
sourcelab source-pack status pqc_v1
sourcelab sources list
```

Point out trust tiers, hashes, and approved PQC migration sources.

## Act 3 — Grounded lesson workflow (5 min)

```bash
sourcelab demo --topic "post-quantum cryptography migration"
# or full pipeline:
sourcelab local-demo
```

Open latest run:

```bash
sourcelab runs show latest
sourcelab verify claims --latest
sourcelab proof latest
```

Highlight: generated lesson, claim map, citation resolution, harness report.

## Act 4 — Answer scoring (2 min)

```bash
sourcelab answer submit --topic "post-quantum cryptography migration" \
  --text "Start with a cryptographic inventory and avoid unsupported quantum-break claims."
sourcelab learning report
sourcelab profile show
```

## Act 5 — Golden evals & strict release (3 min)

```bash
sourcelab evals run --pack pqc_v1
sourcelab evals latest --pack pqc_v1
sourcelab verify-release --strict
sourcelab release check
sourcelab release manifest
```

## Act 6 — Export & dashboard (3 min)

```bash
sourcelab export latest --format markdown
sourcelab release report
sourcelab dashboard --launch   # separate terminal
sourcelab api --serve          # separate terminal, show /version and /docs
```

## One-command demo

```bash
bash scripts/local_v1_demo.sh
```

## Closing line

> SourceLab Local v1.0 RC is installable, reproducible, and verifiable — every lesson run produces a proof bundle you can review, export, and gate on before shipping.
