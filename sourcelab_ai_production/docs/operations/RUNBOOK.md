# Runbook

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
sourcelab demo
pytest -q
```

## Adding sources

```bash
# Ingest local markdown/text/PDF files into the registry
sourcelab ingest-local ./path/to/sources --trust-tier C --publisher "My Publisher" --source-type local_note

# Ingest a URL
sourcelab ingest-url "https://example.com/page" --trust-tier C --publisher "Publisher" --source-type web_page

# Validate the registry
sourcelab sources validate

# Export the registry
sourcelab sources export
```

## Source approval workflow

```bash
# Approve a source
sourcelab sources approve <source_id>

# Reject a source
sourcelab sources reject <source_id> --reason "Low quality"

# Archive a source
sourcelab sources archive <source_id>

# List pending sources
sourcelab sources pending
```

## Source freshness and quality

```bash
# Check source freshness
sourcelab sources freshness

# Generate quality report
sourcelab sources quality
```

## Verify release

```bash
sourcelab verify-release
pytest -q
```

## Inspect runs

```bash
# List all runs
sourcelab runs list

# Show latest run summary
sourcelab runs latest

# Explore a specific run
sourcelab runs show latest
sourcelab runs show <run_id>
```

## Dashboard

```bash
# Install UI extras
pip install -e ".[ui]"

# Launch the Streamlit dashboard
streamlit run src/sourcelab/ui/dashboard.py

# Or use the CLI shortcut
sourcelab dashboard
sourcelab dashboard --launch
```

## Export reports

```bash
# Export latest run as markdown
sourcelab export latest --format markdown

# Export latest run as HTML
sourcelab export latest --format html

# Export a specific run
sourcelab export <run_id> --format markdown
sourcelab export <run_id> --format html
```

## Common failures

### No sources found

Check `data/demo_sources/` or run `sourcelab ingest-local` to add sources.

### Harness failed

Open the latest `harness_report.json`.

### Unsupported claims

Open `claim_map.json` and `grounding_report.md`.

### Bad retrieval

Check source chunks and trust tiers.

### Registry validation fails

Run `sourcelab sources validate` to see errors.

## Local v1 Release Candidate

```bash
# Run the full local demonstration pipeline
sourcelab local-demo

# Check release readiness
sourcelab release check

# View release manifest
sourcelab release manifest

# View release report
sourcelab release report

# View release report to file
sourcelab release report --output report.md

# Run strict release verification
sourcelab verify-release --strict
```
