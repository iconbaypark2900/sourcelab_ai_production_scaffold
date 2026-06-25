# Creating Source Packs

Guide for authoring new SourceLab source packs after the reference `pqc_v1` pack.

## Overview

A source pack is a directory under `data/source_packs/<pack_name>/` containing:

- `manifest.json` — pack metadata, source list, eval file names
- `README.md` — human-readable pack overview
- `sources/*.md` — curated markdown sources with YAML frontmatter
- `evals/*.json` — golden eval cases (retrieval, claim, answer, lesson)

Use `data/source_packs/TEMPLATE/` as a starting scaffold.

## 1. Copy the template

```bash
cp -r data/source_packs/TEMPLATE data/source_packs/my_pack_v1
```

Rename fields in `manifest.json`:

- `pack_name` must match the directory name (`my_pack_v1`)
- `title`, `description`, `version`, `created_at`
- Replace `sources[]` entries with your source metadata
- List eval filenames under `evals[]`

## 2. Author sources

Each file in `sources/` must:

- Use YAML frontmatter starting with `---`
- Include `source_id`, `title`, `publisher`, `source_type`, `trust_tier`
- Match a `source_id` and `filename` entry in `manifest.json`

Follow the style of `data/source_packs/pqc_v1/sources/` for trust tiers and metadata.

## 3. Add golden evals

Minimum eval files (referenced in manifest):

| File | Purpose |
|---|---|
| `retrieval_gold.json` | Query → expected source hits and terms |
| `claim_gold.json` | Claim → expected verification status |
| `answer_gold.json` | Learner answer → minimum rubric score |
| `lesson_gold.json` | Topic → expected lesson structure |

See `pqc_v1/evals/` for full examples with 45 total cases.

## 4. Validate and install

```bash
sourcelab source-pack list
sourcelab source-pack validate my_pack_v1
sourcelab source-pack install my_pack_v1
sourcelab sources validate
```

## 5. Run golden evals

```bash
sourcelab evals run --pack my_pack_v1
sourcelab evals latest --pack my_pack_v1
```

Aim for **≥ 80% pass rate** before including the pack in strict release verification.

## 6. Release integration

After install and evals pass:

```bash
sourcelab local-demo
sourcelab verify-release --strict
```

The release manifest records installed pack status and golden eval pass rates.

## Checklist

- [ ] `manifest.json` `pack_name` matches directory name
- [ ] Every manifest source has a matching `sources/<filename>`
- [ ] Every source file has valid YAML frontmatter
- [ ] Every eval file listed in manifest exists and parses as JSON
- [ ] `sourcelab source-pack validate <pack>` returns `valid: true`
- [ ] Golden eval pass rate ≥ 80%

## Related docs

- `data/source_packs/pqc_v1/README.md` — reference pack
- `data/source_packs/TEMPLATE/README.md` — scaffold README
- `docs/testing/TEST_PLAN.md` — eval expectations
