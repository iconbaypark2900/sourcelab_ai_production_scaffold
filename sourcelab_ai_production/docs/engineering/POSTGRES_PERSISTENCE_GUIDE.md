# Postgres Persistence Guide

## Objective

Implement Postgres-backed persistence for source registry (Epic 1) and skill profiles (Epic 5), while preserving the local-first filesystem fallback.

## Current State

- `src/sourcelab/storage/repositories.py` contains placeholder `SourceRepository` with `NotImplementedError`
- Source registry currently uses `data/source_registry.json` (filesystem)
- Skill profiles currently use `artifacts/profiles/<profile_id>.json` (filesystem)
- `docs/engineering/DATA_MODEL.md` defines the table schema

## Target Tables

```sql
-- Source registry
CREATE TABLE sources (
    source_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    publisher TEXT,
    source_type TEXT NOT NULL,
    trust_tier TEXT NOT NULL DEFAULT 'C',
    url TEXT,
    local_path TEXT,
    retrieved_at TIMESTAMPTZ,
    hash_sha256 TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE source_chunks (
    chunk_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Skill profiles
CREATE TABLE skill_profiles (
    profile_id TEXT PRIMARY KEY,
    topic TEXT,
    mastery JSONB NOT NULL DEFAULT '{}',
    criterion_mastery JSONB NOT NULL DEFAULT '{}',
    strengths JSONB NOT NULL DEFAULT '[]',
    weaknesses JSONB NOT NULL DEFAULT '[]',
    source_grounding_history JSONB NOT NULL DEFAULT '[]',
    preferred_next_difficulty INTEGER NOT NULL DEFAULT 3,
    preferred_guidance_level INTEGER NOT NULL DEFAULT 2,
    last_practiced TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE skill_attempts (
    attempt_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES skill_profiles(profile_id),
    topic TEXT NOT NULL,
    run_id TEXT NOT NULL,
    score REAL NOT NULL,
    difficulty INTEGER NOT NULL,
    task_format TEXT,
    source_grounding_score REAL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## Implementation Plan

### Step 1: Add Postgres dependency (optional)

```bash
pip install psycopg[binary]
```

Add to `pyproject.toml` as an optional extra:
```toml
[project.optional-dependencies]
postgres = ["psycopg[binary]>=3.1"]
```

### Step 2: Implement repository interfaces

File: `src/sourcelab/storage/repositories.py`

```python
class SourceRepository:
    """Source persistence with filesystem and Postgres backends."""
    
    def __init__(self, backend: str = "filesystem"):
        self._backend = backend
    
    def save(self, source: Source) -> str: ...
    def get(self, source_id: str) -> Source | None: ...
    def list(self, status: str | None = None) -> list[Source]: ...
    def update_status(self, source_id: str, status: str) -> None: ...

class SkillProfileRepository:
    """Skill profile persistence with filesystem and Postgres backends."""
    
    def __init__(self, backend: str = "filesystem"):
        self._backend = backend
    
    def save(self, profile: SkillProfileV2) -> str: ...
    def get(self, profile_id: str) -> SkillProfileV2 | None: ...
    def list(self) -> list[SkillProfileV2]: ...
```

### Step 3: Implement Postgres backend

File: `src/sourcelab/storage/postgres_backend.py`

- Use `psycopg` connection pool
- Map JSONB fields to Pydantic schemas
- Connection string from `SOURCELAB_DATABASE_URL` env var
- Fall back to filesystem when env var is not set

### Step 4: Wire into existing code

- `src/sourcelab/sources/registry.py` — accept `SourceRepository` instance
- `src/sourcelab/learning/skill_profile.py` — accept `SkillProfileRepository` instance
- Default to filesystem backend; switch to Postgres when `SOURCELAB_DATABASE_URL` is set

### Step 5: Migration script

File: `scripts/migrate_to_postgres.py`

- Read existing filesystem JSON files
- Insert into Postgres tables
- Verify row counts match
- Support `--dry-run` flag

### Step 6: Tests

File: `tests/unit/test_postgres_repositories.py`

- Test repository interface with mock Postgres
- Test filesystem fallback when `SOURCELAB_DATABASE_URL` not set
- Test migration script with temp database

## Verification

```bash
# Without Postgres (filesystem fallback)
source .venv/bin/activate && python -m pytest tests/unit/test_postgres_repositories.py -q

# With Postgres (requires running Postgres)
export SOURCELAB_DATABASE_URL="postgresql://localhost/sourcelab_test"
python scripts/migrate_to_postgres.py --dry-run
python -m pytest tests/unit/test_postgres_repositories.py -q

# Full suite
python -m pytest -q
sourcelab local-demo
sourcelab verify-release --strict
```

## Scope Notes

- Postgres is optional; the system must work fully without it
- Do not add Redis, workers, or external message queues
- Connection pooling should be lightweight (psycopg pool)
- Keep filesystem as the default backend for local-first usage
