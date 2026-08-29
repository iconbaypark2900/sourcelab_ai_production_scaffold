# SourceLab AI — Production Scaffold

**A source-grounded adaptive technical lab generator.** It turns trusted sources into
technical lessons, verifies that every claim is actually supported by those sources,
scores learner answers against a visible rubric, and adapts what comes next.

The project is deliberately modest about what it guarantees:

> SourceLab does **not** claim perfect correctness. It generates adaptive technical
> lessons from approved sources, verifies citation grounding, scores answers with
> visible rubrics, and records what it did — so the output can be checked rather
> than trusted.

That framing is the point. The engineering effort goes into making the system's
claims *falsifiable*: grounding verification, golden evaluations, strict release
gates, SBOMs and build attestation.

## Where things are

The implementation lives in [`sourcelab_ai_production/`](sourcelab_ai_production/) —
start with its [README](sourcelab_ai_production/README.md) for the full command
reference and quickstart.

| Path | What it holds |
|---|---|
| `sourcelab_ai_production/apps/web` | Run Studio — the Next.js front end |
| `sourcelab_ai_production/data/source_packs` | Curated source packs (e.g. NIST PQC) |
| `sourcelab_ai_production/docs/adr` | Architecture decision records |
| `sourcelab_ai_production/configs` | Trust tiers and local app configuration |

## Quickstart

```bash
cd sourcelab_ai_production
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
sourcelab init-local
sourcelab local-demo
```

## Release discipline

Local v1.0 GA ships with a strict verification path rather than a version number alone:

```bash
sourcelab evals run --pack pqc_v1     # 45 golden cases
sourcelab verify-release --strict     # release gate
sourcelab release sbom                # dependency inventory
sourcelab release attest              # build attestation
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
