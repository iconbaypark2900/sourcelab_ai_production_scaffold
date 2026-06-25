---
source_id: local_architecture_mermaid
title: Architecture Diagrams
domain: user_project_library
trust_tier: B
version: 1.0
created_at: 2026-06-21T04:49:31.628795+00:00
---

# Architecture Diagrams

## Summary

mermaid
flowchart TD
    AUser Topic -- BSource Registry
    B -- CChunking + Metadata
    C -- DHybrid Retrieval
    D -- ECompressed Vector Index
    D -- FSource-Grounded Lesson Generator
    F -- GClaim Verifier
    G -- HGrounding Report
    H -- IHarness Proof Bundle
    I -- JUser Answer
    J -- KAnswer Scorer
    K -- LSkill Profile
    L -- MNext Task Selector
    M -- NAdaptive Next Les

## Key Terms

- lesson
- participant
- source
- claim
- mermaid
- trust
- answer
- chunks
- claims
- flowchart
- generator
- harness

## Source Quality Note

Promoted by SourceLab Library Builder v1 from silver source cards.
