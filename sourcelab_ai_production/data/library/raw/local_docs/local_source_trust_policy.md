# Source Trust Policy

## Trust tiers

- A: Official standards, official docs, laws, regulations, primary source material.
- B: Peer-reviewed papers and authoritative institutional reports.
- C: Preprints, technical reports, reputable research blogs.
- D: Community evidence such as GitHub issues, discussions, and Stack Overflow.
- E: General web summaries, opinion posts, and low-confidence material.

## Lesson generation policy

- Use tier A/B sources where possible.
- Use tier C sources for research exploration with labels.
- Use tier D/E only as implementation context, not authoritative truth.
- High-risk lessons must not rely only on D/E sources.

## Source approval workflow

Sources must be approved before use in lesson generation:

- `active` + `approved`: Available for retrieval and lesson generation
- `pending_review`: Excluded from retrieval by default
- `rejected`: Never used for retrieval
- `archived`: Excluded from retrieval by default

### Approval commands

```bash
sourcelab sources approve <source_id>
sourcelab sources reject <source_id> --reason "..."
sourcelab sources archive <source_id>
sourcelab sources pending
```

## Source freshness policy

Sources are checked for freshness based on `retrieved_at`:

- Fresh: <= 90 days
- Aging: 91-180 days (warning)
- Stale: > 180 days (excluded by default)

### Freshness commands

```bash
sourcelab sources freshness
```

## Source quality policy

Quality reports check for:

- Missing metadata (title, publisher, source_type)
- Low-trust sources (D/E)
- Stale sources
- Duplicate hashes
- Missing path/URL

### Quality commands

```bash
sourcelab sources quality
```

## Safe retrieval filtering

By default, retrieval only uses sources with:

- `status = active`
- `approval_status = approved`

This ensures:
- Rejected sources are never used
- Pending sources require explicit approval
- Archived sources are excluded
