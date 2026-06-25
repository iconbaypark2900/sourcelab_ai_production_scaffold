# API Contracts

## Health and Readiness

### Health Check

```http
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

### Readiness Check

```http
GET /ready
```

Response:

```json
{
  "status": "ready",
  "components": {
    "source_registry": "ok",
    "runs_directory": "ok"
  }
}
```

### Version

```http
GET /version
```

## Models

### Get Model Configuration

```http
GET /models/config
```

Response:

```json
{
  "mode": "deterministic",
  "backend": "deterministic",
  "model_name": "",
  "base_url": "",
  "timeout_seconds": 60,
  "fallback": "deterministic"
}
```

### Check Model Health

```http
GET /models/health
```

Response:

```json
{
  "backend": "deterministic",
  "available": true,
  "model_name": "deterministic",
  "latency_ms": 0.0,
  "error": null
}
```

### Test Model Backend

```http
POST /models/test
```

Request:

```json
{
  "mode": "deterministic",
  "backend": "deterministic",
  "model_name": "",
  "base_url": "",
  "prompt": "What is post-quantum cryptography?"
}
```

Response:

```json
{
  "text": "This response was generated deterministically without a model.",
  "backend": "deterministic",
  "model_name": "deterministic",
  "route": "general",
  "latency_ms": 0.0,
  "deterministic_fallback_used": false,
  "warnings": []
}
```
```

Response:

```json
{
  "version": "0.1.0",
  "api_version": "v1"
}
```

## Sources

### List Sources

```http
GET /sources/
```

Response:

```json
{
  "sources": [
    {
      "source_id": "nist_pqc",
      "title": "NIST Post-Quantum Cryptography",
      "path": "data/demo_sources/nist_pqc.md",
      "publisher": "NIST/local demo",
      "source_type": "local_demo_source",
      "trust_tier": "A",
      "retrieved_at": "2025-01-01T00:00:00Z",
      "hash_sha256": "...",
      "status": "active",
      "approval_status": "approved"
    }
  ],
  "total": 1
}
```

### Get Source

```http
GET /sources/{source_id}
```

Response:

```json
{
  "source_id": "nist_pqc",
  "title": "NIST Post-Quantum Cryptography",
  "path": "data/demo_sources/nist_pqc.md",
  "publisher": "NIST/local demo",
  "source_type": "local_demo_source",
  "trust_tier": "A",
  "retrieved_at": "2025-01-01T00:00:00Z",
  "hash_sha256": "...",
  "status": "active",
  "approval_status": "approved"
}
```

### Validate Sources

```http
GET /sources/validate
```

Response:

```json
{
  "status": "PASS",
  "source_count": 5,
  "errors": [],
  "warnings": []
}
```

### Approve Source

```http
POST /sources/{source_id}/approve
```

Response:

```json
{
  "source_id": "nist_pqc",
  "action": "approve",
  "success": true,
  "message": "Source 'nist_pqc' approved"
}
```

### Reject Source

```http
POST /sources/{source_id}/reject
```

Request:

```json
{
  "reason": "Duplicate source"
}
```

Response:

```json
{
  "source_id": "nist_pqc",
  "action": "reject",
  "success": true,
  "message": "Source 'nist_pqc' rejected"
}
```

### Archive Source

```http
POST /sources/{source_id}/archive
```

Response:

```json
{
  "source_id": "nist_pqc",
  "action": "archive",
  "success": true,
  "message": "Source 'nist_pqc' archived"
}
```

### Ingest Source

```http
POST /sources/ingest
```

Request:

```json
{
  "source_id": "new_source",
  "title": "New Source",
  "path": "/path/to/source.md",
  "publisher": "local",
  "source_type": "local_file",
  "trust_tier": "C"
}
```

Response:

```json
{
  "source_id": "new_source",
  "status": "pending",
  "message": "Source 'new_source' ingestion queued"
}
```

## Retrieval

### Search

```http
POST /retrieval/search
```

Request:

```json
{
  "query": "post-quantum cryptography",
  "top_k": 5,
  "mode": "hybrid"
}
```

Response:

```json
{
  "query": "post-quantum cryptography",
  "mode": "hybrid",
  "results": [
    {
      "chunk_id": "nist_pqc_chunk_1",
      "source_id": "nist_pqc",
      "title": "NIST Post-Quantum Cryptography",
      "score": 0.85,
      "trust_tier": "A",
      "text_preview": "NIST recommends..."
    }
  ],
  "total": 1
}
```

### Build Index

```http
POST /retrieval/index
```

Response:

```json
{
  "status": "ok",
  "chunk_count": 100,
  "source_count": 10
}
```

### Retrieval Diagnostics

```http
GET /retrieval/diagnostics
```

Response:

```json
{
  "query": "",
  "mode": "hybrid",
  "result_count": 0,
  "total_chunks": 0,
  "weights": {
    "keyword": 0.35,
    "vector": 0.45,
    "trust": 0.15,
    "freshness": 0.05
  }
}
```

## Lessons

### Create Lesson

```http
POST /lessons/
```

Request:

```json
{
  "topic": "post-quantum cryptography migration",
  "level": "intermediate",
  "source_policy": "approved_only",
  "difficulty": 3,
  "task_format": "architecture_review",
  "audience": "engineer",
  "model_mode": "deterministic",
  "model_backend": "deterministic",
  "model_name": "",
  "model_base_url": ""
}
```

Response:

```json
{
  "lesson_id": "run_20250101_120000",
  "run_id": "run_20250101_120000",
  "status": "generated",
  "topic": "post-quantum cryptography migration"
}
```

### Show Lesson

```http
GET /lessons/{run_id}
```

Response:

```json
{
  "run_id": "run_20250101_120000",
  "topic": "post-quantum cryptography migration",
  "lesson_markdown": "# Source-grounded lab: post-quantum cryptography migration\n...",
  "answer_key_markdown": "# Answer Key\n...",
  "sources": ["nist_pqc", "cloudflare_pqc"]
}
```

### Show Latest Lesson

```http
GET /lessons/
```

Response:

```json
{
  "run_id": "run_20250101_120000",
  "topic": "post-quantum cryptography migration",
  "lesson_markdown": "# Source-grounded lab: post-quantum cryptography migration\n...",
  "answer_key_markdown": "# Answer Key\n...",
  "sources": ["nist_pqc", "cloudflare_pqc"]
}
```

## Runs

### List Runs

```http
GET /runs/
```

Response:

```json
{
  "runs": [
    {
      "run_id": "run_20250101_120000",
      "run_dir": "/path/to/run",
      "topic": "post-quantum cryptography migration",
      "harness_passed": true,
      "proof_bundle_status": "PASS",
      "answer_score": 0.85,
      "citation_resolution_rate": 0.9,
      "unsupported_high_risk_claims": 0,
      "human_review_count": 0,
      "artifact_count": 15,
      "created_at": "2025-01-01T12:00:00",
      "next_task_focus": "source_grounding"
    }
  ],
  "total": 1
}
```

### Get Latest Run

```http
GET /runs/latest
```

Response:

```json
{
  "run_id": "run_20250101_120000",
  "run_dir": "/path/to/run",
  "topic": "post-quantum cryptography migration",
  "harness_passed": true,
  "proof_bundle_status": "PASS",
  "answer_score": 0.85,
  "citation_resolution_rate": 0.9,
  "unsupported_high_risk_claims": 0,
  "human_review_count": 0,
  "artifact_count": 15,
  "created_at": "2025-01-01T12:00:00",
  "next_task_focus": "source_grounding"
}
```

### Get Run

```http
GET /runs/{run_id}
```

Response:

```json
{
  "run_id": "run_20250101_120000",
  "run_dir": "/path/to/run",
  "topic": "post-quantum cryptography migration",
  "harness_passed": true,
  "proof_bundle_status": "PASS",
  "answer_score": 0.85,
  "citation_resolution_rate": 0.9,
  "unsupported_high_risk_claims": 0,
  "human_review_count": 0,
  "artifact_count": 15,
  "created_at": "2025-01-01T12:00:00",
  "next_task_focus": "source_grounding"
}
```

### Get Run Artifacts

```http
GET /runs/{run_id}/artifacts
```

Response:

```json
{
  "artifacts": [
    {
      "name": "run_manifest.json",
      "artifact_type": "json",
      "required": true,
      "exists": true,
      "validated": true,
      "sha256": "...",
      "size": 1024
    }
  ],
  "total": 15
}
```

### Get Proof Bundle

```http
GET /runs/{run_id}/proof
```

Response:

```json
{
  "run_id": "run_20250101_120000",
  "status": "PASS",
  "manifest": {
    "version": "2.0",
    "run_id": "run_20250101_120000"
  },
  "summary": {
    "release_gate_status": "PASS",
    "answer_score": 0.85
  }
}
```

### Get Harness Report

```http
GET /runs/{run_id}/harness
```

Response:

```json
{
  "run_id": "run_20250101_120000",
  "passed": true,
  "checks": [
    {
      "check_name": "required_artifacts_exist",
      "passed": true,
      "message": "All required artifacts present"
    }
  ],
  "blocking_failures": [],
  "warnings": [],
  "artifact_count": 15
}
```

## Learning

### Submit Answer

```http
POST /learning/answers
```

Request:

```json
{
  "run_id": "run_20250101_120000",
  "answer_text": "My answer to the lesson..."
}
```

Response:

```json
{
  "run_id": "run_20250101_120000",
  "topic": "post-quantum cryptography migration",
  "score": 0.85,
  "feedback": "Good answer with strong source grounding.",
  "next_task_id": "task_456",
  "breakdown": {
    "topic_relevance": 0.9,
    "source_grounding": 0.8,
    "practical_reasoning": 0.85
  }
}
```

### Get Skill Profile

```http
GET /learning/profile
```

Response:

```json
{
  "profile_id": "profile_123",
  "topic": "post-quantum cryptography",
  "attempts": [
    {
      "run_id": "run_20250101_120000",
      "score": 0.85,
      "timestamp": "2025-01-01T12:00:00"
    }
  ],
  "mastery": {
    "topic_relevance": 0.8,
    "source_grounding": 0.75
  },
  "strengths": ["topic_relevance"],
  "weaknesses": ["source_grounding"],
  "source_grounding_history": []
}
```

### Get Learning Report

```http
GET /learning/reports/{run_id}
```

Response:

```json
{
  "run_id": "run_20250101_120000",
  "topic": "post-quantum cryptography migration",
  "report_markdown": "# Learning Report\n...",
  "report_json": {
    "score": 0.85,
    "mastery_updates": {}
  }
}
```

### Get Next Task

```http
GET /learning/next-task/{run_id}
```

Response:

```json
{
  "topic": "post-quantum cryptography migration",
  "focus": "source_grounding",
  "task_format": "architecture_review",
  "difficulty": 3,
  "guidance_level": 3,
  "reason": "Focus on improving source grounding based on recent performance."
}
```

## Error Responses

All error responses follow this structure:

```json
{
  "error": "Not found",
  "detail": "Source 'nonexistent' not found",
  "code": "NOT_FOUND"
}
```

Error codes:
- `NOT_FOUND` - Resource not found
- `VALIDATION_ERROR` - Request validation failed
- `INTERNAL_ERROR` - Internal server error
- `RESOURCE_CONFLICT` - Resource conflict
- `BAD_REQUEST` - Invalid request
- `SERVICE_UNAVAILABLE` - Service unavailable
