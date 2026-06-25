# Component Build Guide

## Source Registry

The source registry is the source of truth for approved sources.

### Key files

- `src/sourcelab/sources/registry.py` - Registry class with load/save/validate
- `src/sourcelab/sources/schemas.py` - Pydantic schemas for ingestion
- `src/sourcelab/sources/ingest_local.py` - Local file ingestion (MD, TXT, PDF)
- `src/sourcelab/sources/ingest_url.py` - URL ingestion
- `src/sourcelab/sources/freshness.py` - Source freshness checks
- `src/sourcelab/sources/quality.py` - Source quality reports
- `data/source_registry.json` - Persistent registry storage
- `src/sourcelab/sources/chunker.py` - Source chunking

### Adding new sources

```bash
# Via CLI - Local files
sourcelab ingest-local ./path/to/sources --trust-tier C --publisher "Publisher" --source-type type

# Via CLI - URLs
sourcelab ingest-url "https://example.com/page" --trust-tier C --publisher "Publisher" --source-type web_page

# Via Python
from sourcelab.sources.registry import SourceRegistry
from sourcelab.core.models import SourceRecord
from datetime import datetime, timezone

registry = SourceRegistry.load_from_json(Path("data/source_registry.json"))
record = SourceRecord(
    source_id="my_source",
    title="My Source",
    path="path/to/file.md",
    publisher="Publisher",
    source_type="type",
    trust_tier="C",
    retrieved_at=datetime.now(timezone.utc),
    hash_sha256="...",
    status="active",
    approval_status="approved",
)
registry.add_source(record)
registry.save_to_json(Path("data/source_registry.json"))
```

### Source statuses

- `active` - Source is active and available for retrieval
- `pending_review` - Source is pending review (excluded from retrieval by default)
- `rejected` - Source is rejected (never used for retrieval)
- `stale` - Source is stale (>180 days old)
- `archived` - Source is archived (excluded from retrieval by default)

### Approval statuses

- `approved` - Source is approved for use
- `needs_review` - Source needs review
- `rejected` - Source is rejected

### Approval workflow

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

### Freshness checks

```bash
# Check source freshness
sourcelab sources freshness
```

Thresholds:
- Fresh: <= 90 days
- Aging: 91-180 days
- Stale: > 180 days

### Quality reports

```bash
# Generate quality report
sourcelab sources quality
```

Reports include:
- Missing metadata
- Low-trust sources
- Stale sources
- Duplicate hashes
- Missing path/URL

### Trust tiers

- `A` - Highly trusted (standards bodies, official documentation)
- `B` - Trusted (peer-reviewed, established sources)
- `C` - Moderate trust (internal documentation, community sources)
- `D` - Low trust (unverified, experimental)
- `E` - Untrusted (known unreliable)

### Source ID normalization

Source IDs are normalized:
1. Lowercase
2. Replace spaces with underscores
3. Remove unsafe characters (keep alphanumeric, underscore, hyphen)
4. Collapse multiple underscores
5. Append numeric suffix if ID already exists

### Validation

Run `sourcelab sources validate` to check:
- All required fields are present
- Trust tiers are valid
- Source files exist
- No duplicate IDs

## Retrieval Layer

The retrieval layer provides three search modes with diagnostics.

### Key files

- `src/sourcelab/retrieval/index.py` - PocketIndex (vector search)
- `src/sourcelab/retrieval/bm25.py` - BM25Index (keyword search)
- `src/sourcelab/retrieval/hybrid_search.py` - HybridSearch (combined)
- `src/sourcelab/retrieval/embeddings.py` - Hashed embeddings
- `src/sourcelab/retrieval/compression.py` - int8 compression

### Vector search

```python
from sourcelab.retrieval.index import PocketIndex
from sourcelab.sources.registry import SourceRegistry

registry = SourceRegistry.bootstrap_demo(Path.cwd())
index = PocketIndex.from_registry(registry)
results = index.search("crypto inventory", top_k=4)
```

### Keyword search (BM25)

```python
from sourcelab.retrieval.bm25 import BM25Index
from sourcelab.sources.chunker import simple_chunk_source

chunks = []
titles = {}
for source in registry.sources:
    titles[source.source_id] = source.title
    chunks.extend(simple_chunk_source(source))

bm25 = BM25Index(chunks=chunks, titles=titles)
results = bm25.search("crypto inventory", top_k=4)
```

### Hybrid search

```python
from sourcelab.retrieval.hybrid_search import HybridSearch

hybrid = HybridSearch.from_registry(registry)
results, diagnostics = hybrid.search("crypto inventory", top_k=4)

# Diagnostics contain:
# - keyword_scores: normalized BM25 scores
# - vector_scores: normalized vector scores
# - trust_weights: trust-tier weights applied
# - source_ids, chunk_ids, trust_tiers: citation info
```

### CLI usage

```bash
sourcelab search "crypto inventory" --mode vector
sourcelab search "crypto inventory" --mode keyword
sourcelab search "crypto inventory" --mode hybrid
```

## Generation v2 Layer

Generation v2 creates complete lesson packages from retrieved sources.

### Key files

- `src/sourcelab/generation/schemas.py` - Pydantic schemas for lesson packages
- `src/sourcelab/generation/lesson_generator.py` - Main lesson generator
- `src/sourcelab/generation/scenario_generator.py` - Scenario generation
- `src/sourcelab/generation/rubric_generator.py` - Rubric generation
- `src/sourcelab/generation/answer_key_generator.py` - Answer key generation
- `src/sourcelab/generation/trace.py` - Generation trace logging

### Generating a lesson package

```python
from sourcelab.generation.lesson_generator import SourceGroundedLessonGenerator

generator = SourceGroundedLessonGenerator()
package = generator.generate_package(
    topic="post-quantum cryptography migration",
    search_results=search_results,
    difficulty=3,
    task_format="architecture_review",
    audience="engineer",
)
```

### CLI usage

```bash
sourcelab lesson create --topic "post-quantum cryptography migration" --difficulty 3 --format architecture_review
sourcelab lesson show --latest
```

### Task formats

- `executive_explanation` - Explain to executive audience
- `architecture_review` - Review architectural decisions
- `debugging` - Diagnose technical problems
- `hands_on_lab` - Practical exercises
- `risk_review` - Assess risks and mitigations

### Rubric criteria

The rubric includes weighted criteria:
- topic_relevance (0.20)
- source_grounding (0.25)
- practical_reasoning (0.20)
- uncertainty_control (0.15)
- trap_avoidance (0.10)
- clarity (0.05)
- citation_use_of_evidence (0.05)

## Verification v2 Layer

Verification v2 provides advanced claim verification with citation gates.

### Key files

- `src/sourcelab/verification/schemas.py` - Pydantic schemas for verification
- `src/sourcelab/verification/claim_extractor.py` - Atomic claim extraction
- `src/sourcelab/verification/evidence_matcher.py` - Claim-to-chunk matching
- `src/sourcelab/verification/claim_verifier.py` - Claim verification
- `src/sourcelab/verification/citation_checker.py` - Citation resolution
- `src/sourcelab/verification/conflict_detector.py` - Contradiction detection
- `src/sourcelab/verification/human_review.py` - Review queue builder
- `src/sourcelab/verification/grounding_report.py` - Grounding report generator

### Claim types

- `definition` - Definitions and explanations
- `recommendation` - Recommendations and best practices
- `risk_statement` - Risk assessments and warnings
- `process_step` - Process steps and procedures
- `warning` - Warnings and cautions
- `fact` - Factual statements
- `unsupported_example` - Examples without source support

### Evidence matching

Claims are matched to source chunks using:
- Token overlap scoring
- Phrase matching (3-grams)
- Trust tier weighting (A=1.0, B=0.85, C=0.7, D=0.4, E=0.2)
- Claim type weighting

### Citation resolution

The citation resolution rate is calculated as:
```
resolution_rate = supported_claims / total_claims
```

A minimum resolution rate of 0.3 is required for the release gate (production should use 0.8).

### Conflict detection

The system detects:
- Must/must-not contradictions
- Safe/unsafe contradictions
- RSA-related contradictions (quantum-safe vs vulnerable)

### CLI usage

```bash
sourcelab verify latest
sourcelab verify run <run_id>
sourcelab verify claims --latest
sourcelab review queue --latest
```

## Dashboard v1

The dashboard provides a visual interface for inspecting SourceLab runs.

### Key files

- `src/sourcelab/ui/dashboard.py` - Streamlit dashboard with tabbed interface
- `src/sourcelab/ui/run_loader.py` - Run loading utilities
- `src/sourcelab/ui/terminal.py` - Terminal run explorer
- `src/sourcelab/ui/export.py` - Markdown/HTML report export

### Dashboard tabs

1. **Overview** - Run ID, topic, harness status, proof bundle status, answer score, citation resolution
2. **Lesson** - Generated lesson markdown, rubric table, answer key
3. **Sources & Retrieval** - Source registry snapshot, retrieved chunks, compression report
4. **Verification** - Grounding report, claim map, citation resolution, human review queue
5. **Harness & Proof** - Harness report, proof summary, proof bundle manifest, run manifest
6. **Learning** - Answer submission, answer review, mastery update, skill profile, learning report, next task
7. **Artifacts** - Full artifact inventory table with existence, validation, and SHA256

### Run loader utilities

```python
from sourcelab.ui.run_loader import list_runs, get_latest_run, load_json_artifact, summarize_run
from pathlib import Path

# List all runs
runs = list_runs(Path.cwd())

# Get latest run summary
latest = get_latest_run(Path.cwd())

# Load a specific artifact
data = load_json_artifact(run_dir, "proof_summary.json")
```

### Terminal explorer

```python
from sourcelab.ui.terminal import print_run_summary, print_run_list

# Print a single run summary
print_run_summary(summary)

# Print a list of runs
print_run_list(summaries)
```

### Report export

```python
from sourcelab.ui.export import export_run

# Export as markdown
path = export_run(project_root, run_id="latest", fmt="markdown")

# Export as HTML
path = export_run(project_root, run_id="latest", fmt="html")
```

### CLI usage

```bash
# Launch dashboard
sourcelab dashboard
sourcelab dashboard --launch

# List runs
sourcelab runs list

# Show latest run
sourcelab runs latest

# Explore a specific run
sourcelab runs show latest
sourcelab runs show <run_id>

# Export reports
sourcelab export latest --format markdown
sourcelab export latest --format html
sourcelab export <run_id> --format markdown
```

### Installation

```bash
# Install with UI extras
pip install -e ".[ui]"

# Launch dashboard
streamlit run src/sourcelab/ui/dashboard.py
```
