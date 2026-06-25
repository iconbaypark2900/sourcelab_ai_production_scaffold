# Screenshot Checklist — SourceLab Local v1.0 RC

Capture these for release review, docs, or stakeholder demos.

## Install & health

- [ ] Terminal: `sourcelab version` showing `1.0.0-rc1`
- [ ] Terminal: `sourcelab doctor` JSON with `"status": "PASS"`
- [ ] Terminal: `sourcelab init-local` success output and next commands

## Sources & pack

- [ ] Terminal: `sourcelab source-pack status pqc_v1` — installed sources listed
- [ ] Terminal: `sourcelab sources list` — PQC sources with trust tiers

## Lesson & verification

- [ ] Terminal: `sourcelab runs show latest` — harness passed, topic visible
- [ ] File browser: `artifacts/runs/<run_id>/generated_lesson.md` excerpt
- [ ] Terminal or file: `claim_map.json` with claim types
- [ ] Terminal or file: `citation_resolution.json` — resolution rate 100%

## Learning

- [ ] Terminal: answer submit with overall score
- [ ] Terminal: `sourcelab profile show` — mastery updated

## Evals & release

- [ ] Terminal: `sourcelab evals latest --pack pqc_v1` — 45/45 or 100% pass rate
- [ ] Terminal: `sourcelab verify-release --strict` — `"status": "PASS"`
- [ ] Terminal: `sourcelab release manifest` — version, doctor, golden eval fields

## Export

- [ ] Exported markdown report (header + harness + eval sections)
- [ ] `artifacts/release/local_v1_release_report.md`

## Dashboard

- [ ] Streamlit home / latest run summary tab
- [ ] Release status tab (if present)
- [ ] Run explorer with artifact list

## API

- [ ] Browser: `http://localhost:8000/docs` — OpenAPI UI
- [ ] Terminal: `curl localhost:8000/version` — full metadata JSON
- [ ] Terminal: `curl localhost:8000/ready` — components ok

## Docker (optional)

- [ ] Terminal: `docker compose up sourcelab-api` startup logs
- [ ] Terminal: `curl localhost:8000/health` from host

## Tests

- [ ] Terminal: `pytest -q` — all passed summary line
