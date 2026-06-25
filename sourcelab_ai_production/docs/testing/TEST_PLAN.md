# Test Plan

## Unit tests

- Source registry creates metadata.
- Chunker preserves source IDs.
- Retriever returns source-linked chunks.
- BM25 keyword search returns expected source for crypto inventory.
- Vector search returns source-linked chunks.
- Hybrid search returns source-linked chunks with diagnostics.
- Trust-tier weighting affects ranking.
- Empty queries return clean empty responses.
- All results preserve citations (source_id, chunk_id, trust_tier).
- Lesson generator refuses missing sources.
- Claim verifier outputs claim map.
- Harness detects missing artifacts.
- Answer scorer returns visible rubric breakdown.
- Next-task selector explains decision.
- Lesson package schema validates.
- Generation fails when no sources are provided.
- Rubric weights sum to 1.0.
- Answer key includes source IDs and chunk IDs.
- Generation trace includes source IDs and chunk IDs.
- Pipeline writes all new artifacts.
- Claim verifier reads generated claims.
- Harness fails if generation trace is missing.
- Harness fails if answer key has no source references.
- `sourcelab lesson create` works.
- `sourcelab demo --topic "post-quantum cryptography migration"` still passes.
- `sourcelab verify-release` still passes.

## Source ingestion v2 unit tests

- IngestionRequest schema validates with required fields.
- IngestionResult schema validates with required fields.
- IngestedFile schema validates with required fields.
- URLIngestionRecord schema validates with required fields.
- SourceApprovalRecord schema validates with required fields.
- FreshnessCheckResult schema validates with required fields.
- SourceQualityReport schema validates with required fields.
- discover_local_files finds .md, .txt, and .pdf files.
- extract_pdf_text returns error when pypdf is not installed.
- save_extracted_text saves text to extracted directory.
- SUPPORTED_EXTENSIONS includes .pdf.
- fetch_url_content returns error when requests is not installed.
- parse_html_to_text returns error when beautifulsoup4 is not installed.
- parse_html_to_text extracts text from HTML.
- save_url_content saves text to web directory.
- ingest_url_source returns None when dependencies are missing.
- approve_source changes source status to active and approved.
- approve_source returns False when source not found.
- reject_source changes source status to rejected.
- reject_source returns False when source not found.
- archive_source changes source status to archived.
- archive_source returns False when source not found.
- get_pending_sources returns sources with pending_review status.
- get_active_approved_sources returns only active and approved sources.
- filter_for_retrieval excludes rejected sources by default.
- check_source_freshness classifies recent sources as fresh.
- check_source_freshness classifies medium-age sources as aging.
- check_source_freshness classifies old sources as stale.
- check_source_freshness returns unknown when no retrieved_at.
- check_all_sources_freshness returns results for all sources.
- format_freshness_report returns a formatted report.
- generate_quality_report detects issues in source registry.
- generate_quality_report detects duplicate hashes.
- generate_quality_report detects missing path and URL.
- format_quality_report returns a formatted report.
- Pending sources are excluded from default retrieval.
- Rejected sources are excluded from retrieval.

## Verification v2 unit tests

- AtomicClaim schema validates with required fields.
- EvidenceMatch schema validates with required fields.
- VerificationReport schema validates with required fields.
- Extract atomic claims from lesson.
- Extract atomic claims from answer key.
- Extract atomic claims from scenario.
- Extract all atomic claims from lesson package.
- Legacy claim extraction still works.
- Match claim to source chunks.
- Match all claims to source chunks.
- Get best match from evidence matches.
- Claim verifier verifies single claim.
- Claim verifier verifies all claims.
- Claim verifier maintains backward compatibility.
- Citation resolution rate calculates correctly.
- Compute citation resolution from verification results.
- Check citation resolution meets requirements.
- Detect must/must-not contradictions.
- Detect RSA-related contradictions.
- Detect all types of conflicts.
- Build review items from verification results.
- Build review items from conflicts.
- Build complete human review queue.
- Write review queue to file.
- Generate verification report.
- Generate markdown grounding report.
- Write grounding report to files.
- Harness runner validates verification v2 artifacts.

## Integration tests

- End-to-end demo creates proof bundle.
- Demo pipeline writes all Generation v2 artifacts.
- `sourcelab lesson create` produces valid output.
- Citation resolution works.
- Unsupported high-risk claims fail release.
- Skill profile updates after answer scoring.

## Learning v2 unit tests

- Learning schemas validate with required fields.
- Answer scorer v2 returns rubric-based breakdown with 7 criteria.
- Answer scorer v2 identifies strengths and weaknesses.
- Answer scorer v2 detects high-risk statements.
- Answer scorer v2 maintains backward compatibility with v1.
- Source grounding checker matches terms against sources.
- Source grounding checker identifies unsupported phrases.
- Skill profile v2 loads and saves correctly.
- Skill profile v2 updates from answer review.
- Skill profile v2 tracks criterion-level mastery.
- Mastery update computes difficulty multiplier correctly.
- Mastery update applies correct weight based on difficulty and score.
- Next-task selector v2 returns rationale with focus area.
- Next-task selector v2 responds to weak source grounding.
- Next-task selector v2 responds to weak uncertainty control.
- Next-task selector v2 responds to weak trap avoidance.
- Learning report generator creates complete report.
- Learning report renders as markdown.
- Learning report writes all artifacts.
- Harness validates answer review criterion scores and ranges.
- Harness validates source grounding review score range.
- Harness validates mastery update ranges.
- Harness validates skill profile snapshot structure.
- Harness validates learning report completeness.
- Harness validates learning report markdown exists.
- Harness validates next task decision has reason.

## Learning v2 CLI tests

```bash
# Submit an answer
sourcelab answer submit --topic "post-quantum cryptography migration" --text "A safe plan starts with a cryptographic inventory..."

# Submit answer from file
sourcelab answer submit --topic "post-quantum cryptography migration" --file examples/strong_answer.md

# Show skill profile
sourcelab profile show

# Show topic mastery
sourcelab profile topic "post-quantum cryptography migration"

# Show learning report
sourcelab learning report
```

## Golden tests

Fixed topic:
- post-quantum cryptography migration

Expected:
- lesson generated
- grounding report created
- harness passes
- answer review created
- next task selected
- verification report created
- citation resolution calculated
- human review queue generated (if needed)

## Negative tests

- No sources available.
- Missing source metadata.
- Unsupported high-risk claim.
- Broken citation.
- Empty user answer.
- Prompt injection inside source text.
- Empty search query returns empty results.

## Search mode tests

```bash
# Keyword search
sourcelab search "crypto inventory" --mode keyword

# Vector search
sourcelab search "crypto inventory" --mode vector

# Hybrid search
sourcelab search "crypto inventory" --mode hybrid
```

## Verification v2 CLI tests

```bash
# Verify latest run
sourcelab verify latest

# Verify specific run
sourcelab verify run <run_id>

# View claims from latest run
sourcelab verify claims --latest

# View human review queue
sourcelab review queue --latest
```

## Release gate

Run:

```bash
sourcelab verify-release
pytest -q
```

## Local v1 Release Candidate tests

### Unit tests

- ReleaseThresholds default values are reasonable.
- ReleaseThresholds custom values can be set.
- ReleaseThresholds to_dict returns correct structure.
- ReleaseManifest can be created with version field.
- ReleaseManifest JSON roundtrip works.
- build_release_manifest returns ReleaseManifest.
- build_release_manifest checks for various files.
- build_release_manifest with minimal project state.
- run_release_checklist returns dict with status, checks, blocking, warnings.
- run_release_checklist includes all 12 checks.
- run_release_checklist reports missing files correctly.

### CLI tests

```bash
# Run full local demonstration pipeline
sourcelab local-demo

# Check release readiness
sourcelab release check

# View release manifest
sourcelab release manifest

# View release report
sourcelab release report

# View release report to file
sourcelab release report --output report.md
```

### Integration tests

- Local demo creates release manifest JSON.
- Local demo creates release report markdown.
- Release check reports status correctly.
- Strict release verification includes all 15 checks.
- Dashboard Release tab displays release status.
- Export report includes release, golden eval, proof, harness sections.
