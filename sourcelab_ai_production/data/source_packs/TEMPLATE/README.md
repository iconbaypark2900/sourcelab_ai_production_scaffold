# Source Pack Template

Scaffold for creating a new SourceLab source pack after `pqc_v1`.

## Steps

1. Copy this `TEMPLATE/` directory to `data/source_packs/<your_pack_name>/`.
2. Rename `pack_name` in `manifest.json` to match the directory name.
3. Replace `sources/example_source.md` with your curated markdown sources (YAML frontmatter required).
4. Add golden eval JSON files under `evals/` and list them in `manifest.json`.
5. Validate and install:

```bash
sourcelab source-pack validate <your_pack_name>
sourcelab source-pack install <your_pack_name>
sourcelab evals run --pack <your_pack_name>
```

See `docs/source_packs/CREATING_SOURCE_PACKS.md` for the full guide.
