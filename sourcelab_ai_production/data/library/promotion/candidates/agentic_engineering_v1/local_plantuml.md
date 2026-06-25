---
source_id: local_plantuml
title: PlantUML Diagrams
domain: user_project_library
trust_tier: B
version: 1.0
created_at: 2026-06-21T04:49:31.629065+00:00
---

# PlantUML Diagrams

## Summary

plantuml
@startuml
package "SourceLab AI" {
  Source Registry -- Chunker
  Chunker -- Retrieval Index
  Retrieval Index -- Lesson Generator
  Lesson Generator -- Claim Verifier
  Claim Verifier -- Proof Bundle
  Proof Bundle -- Answer Scorer
  Answer Scorer -- Skill Profile
  Skill Profile -- Next Task Selector
}
@enduml

## Key Terms

- fastapi
- proof
- plantuml
- answer
- bundle
- bundles
- chunker
- chunks
- claim
- dashboard
- database
- diagram

## Source Quality Note

Promoted by SourceLab Library Builder v1 from silver source cards.
