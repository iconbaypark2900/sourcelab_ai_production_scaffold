# Grounding Report UI Guide

## Objective

Add a grounding report visualization to Run Studio (Epic 4), showing source grounding metrics for learner answers.

## Current State

- `src/sourcelab/verification/grounding_report.py` generates `grounding_report.json` with trust tier breakdown
- `src/sourcelab/learning/source_grounding.py` generates `source_grounding_review.json` with concept-overlap evidence
- `src/sourcelab/api/routes_learning.py` serves grounding data via API
- Run Studio already has a `/curriculum` page with source grounding sparkline (v1.0.2)
- Run Studio run detail page (`/runs/[runId]`) has Operations, Detailed, and Forensic views

## Implementation Plan

### Step 1: Add API endpoint for grounding report

File: `src/sourcelab/api/routes_learning.py`

Add `GET /learning/grounding/{run_id}` endpoint that returns:
```json
{
  "run_id": "...",
  "grounding_report": { ... },
  "source_grounding_review": { ... },
  "summary": {
    "overall_score": 0.72,
    "trust_tier_breakdown": { "A": 0.3, "B": 0.5, "C": 0.2 },
    "unmatched_claims": 2,
    "total_claims": 10,
    "citation_resolution_rate": 0.8
  }
}
```

### Step 2: Add TypeScript types

File: `apps/web/lib/types.ts`

```typescript
export interface GroundingReportResponse {
  run_id: string;
  grounding_report: GroundingReport;
  source_grounding_review: SourceGroundingReview;
  summary: GroundingSummary;
}

export interface GroundingSummary {
  overall_score: number;
  trust_tier_breakdown: Record<string, number>;
  unmatched_claims: number;
  total_claims: number;
  citation_resolution_rate: number;
}
```

### Step 3: Add API client function

File: `apps/web/lib/sourcelab-api.ts`

```typescript
export async function getGroundingReport(runId: string): Promise<GroundingReportResponse> {
  const res = await fetch(`${API_BASE}/learning/grounding/${runId}`);
  if (!res.ok) throw new Error(`Failed to fetch grounding report: ${res.statusText}`);
  return res.json();
}
```

### Step 4: Create GroundingReportPanel component

File: `apps/web/components/GroundingReportPanel.tsx`

Components to include:
- **GroundingScoreCard** — overall grounding score with color band
- **TrustTierBreakdown** — bar chart showing trust tier distribution
- **ClaimSupportMatrix** — table of claims and their support status
- **UnmatchedClaimsList** — list of claims that failed to find supporting evidence
- **CitationResolutionGauge** — circular progress showing citation resolution rate
- **SourceGroundingTimeline** — sparkline of grounding scores across attempts

### Step 5: Add to run detail page

File: `apps/web/app/runs/[runId]/page.tsx`

Add a "Grounding" tab or section that renders `GroundingReportPanel` when grounding data is available.

### Step 6: Tests

File: `apps/web/components/__tests__/GroundingReportPanel.test.tsx`

- Test rendering with full grounding data
- Test rendering with empty/null grounding data
- Test trust tier breakdown visualization
- Test unmatched claims list
- Test citation resolution gauge

## Verification

```bash
source .venv/bin/activate

# Backend
python -m pytest tests/unit/test_api_routes.py -q

# Frontend
cd apps/web && npm run build && npm run test

# End-to-end
sourcelab local-demo
sourcelab verify-release --strict
```

## Scope Notes

- Use existing `Panel`, `Metric`, `StatusPill`, `TrendBadge` components from Chrome.tsx
- Do not add auth, databases, or WebSockets
- Grounding data is fetched via standard REST API (synchronous, polling-based)
- UI uses URL state and localStorage for session restore (no backend persistence)
- Follow the same pattern as the curriculum dashboard page
