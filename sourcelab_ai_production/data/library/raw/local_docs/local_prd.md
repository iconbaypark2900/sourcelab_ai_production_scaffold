# Product Requirements Document: SourceLab AI

## Product summary

SourceLab AI is a source-grounded adaptive technical lab generator. It helps technical learners practice advanced subjects using trusted sources, visible rubrics, and adaptive next tasks.

## Target users

1. AI/ML learners studying agents, RAG, and model optimization.
2. Cybersecurity learners studying post-quantum migration and secure engineering.
3. Developer-tool builders who want reproducible labs.
4. Research-heavy students and founders who need paper-to-practice workflows.

## Primary use case

A learner chooses a topic such as "post-quantum cryptography migration." The system retrieves approved sources, generates a practical scenario, verifies claim grounding, scores the learner response, and adapts the next task.

## Core requirements

- R1: Ingest approved sources with metadata.
- R2: Chunk and index sources while preserving source IDs.
- R3: Search trusted sources with source and trust metadata.
- R4: Generate lessons only from retrieved sources.
- R5: Verify important claims against sources.
- R6: Fail closed when no adequate source support exists.
- R7: Score user answers with visible rubric.
- R8: Update learner skill profile.
- R9: Select next task with an explainable reason.
- R10: Produce a proof bundle for every run.

## Non-goals for v1

- Replacing experts.
- Giving legal, medical, financial, or professional security advice.
- Fully autonomous code editing.
- Guaranteeing perfect factual correctness.
- Full TurboQuant implementation.
- Full DiffusionGemma serving stack.

## Success metrics

- 99%+ lesson schema validity.
- 99%+ citation resolution.
- 0 unsupported high-risk claims in final answer keys.
- 100% source metadata completeness.
- 95%+ full-flow integration pass rate.
- 80%+ human-rated lesson usefulness in the first review set.

## Local v1 Release Candidate

The local v1 release candidate provides a self-contained demonstration of SourceLab AI capabilities:

### Requirements

- R11: One-command local demonstration pipeline (`sourcelab local-demo`).
- R12: Release manifest with version, status, and verification results.
- R13: Release checklist with 12 individual readiness checks.
- R14: Strict release verification with 15 checks for production readiness.
- R15: Dashboard with release status visibility.
- R16: Export reports with release, golden eval, proof, and harness sections.

### Success criteria

- All 387+ tests passing.
- `sourcelab local-demo` completes without errors.
- `sourcelab release check` reports status correctly.
- Dashboard Release tab displays release information.
- Export reports include all required sections.
