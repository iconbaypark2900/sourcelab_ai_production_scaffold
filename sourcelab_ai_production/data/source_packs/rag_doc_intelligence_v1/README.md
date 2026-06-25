# RAG and Document Intelligence

## Purpose

Source pack for adaptive graph RAG, source-grounded generation, document intelligence, deduplication, and proof-bundle workflows.

## Domain

`rag_doc_intelligence`

## Topics

- adaptive graph RAG
- document AI
- source-grounded generation
- document deduplication
- knowledge graphs
- semantic retrieval
- proof bundles

## Example Lessons

- `source-grounded document assistant`
- `adaptive graph RAG architecture`
- `document deduplication review workflow`
- `proof bundle design for RAG outputs`

## Starter Sources

- `rag_doc_intelligence_grounding_001` — Source-Grounded Document Intelligence
- `rag_doc_intelligence_dedup_002` — Document Deduplication and Review

## Validation

From the SourceLab project root:

```bash
sourcelab source-pack doctor rag_doc_intelligence_v1
sourcelab evals run --pack rag_doc_intelligence_v1
sourcelab lesson create --topic "source-grounded document assistant" --source-pack rag_doc_intelligence_v1 --difficulty 2
```

## Notes

This pack was scaffolded from the user's recurring project and research themes. Replace or extend starter sources with stronger project notes, official docs, papers, or internal architecture records over time.
