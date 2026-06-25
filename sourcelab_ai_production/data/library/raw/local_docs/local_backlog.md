# Backlog

## Epic 1: Source Registry

- [ ] Add Postgres source tables.
- [x] Add PDF ingestion.
- [x] Add URL ingestion.
- [x] Add source hash verification.
- [x] Add source freshness scanner.
- [x] Add trust-tier admin workflow.
- [x] Add source approval workflow.
- [x] Add source quality reports.

## Epic 2: Retrieval

- [ ] Add tokenizer-aware chunking.
- [ ] Add real embedding model.
- [ ] Add Qdrant.
- [ ] Add BM25 search.
- [ ] Add hybrid score fusion.
- [ ] Add reranker.
- [ ] Add compression adapter interface.
- [ ] Add product quantization baseline.
- [ ] Add TurboQuant research adapter stub.

## Epic 3: Generation

- [x] Add scenario generator schemas.
- [x] Add lesson generator schemas.
- [x] Add answer key generator.
- [x] Add rubric generator.
- [ ] Add DiffusionGemma backend.
- [ ] Add fallback model backend.
- [x] Add generation trace logging.

## Epic 4: Verification v2

- [x] Add verification schemas (AtomicClaim, EvidenceMatch, ClaimVerificationResult, CitationResolutionResult, VerificationReport, ConflictRecord, HumanReviewItem).
- [x] Add atomic claim extractor with claim types.
- [x] Add evidence matcher with token/phrase overlap and trust tier weighting.
- [x] Add claim verifier with support status determination.
- [x] Add citation resolution rate calculation.
- [x] Add conflict detector (must/must-not, safe/unsafe, RSA contradictions).
- [x] Add human review queue builder.
- [x] Add comprehensive grounding report generator.
- [x] Add harness validation for verification artifacts.
- [x] Add CLI commands for verify and review.
- [ ] Add real LLM entailment scoring.
- [ ] Add grounding report UI.

## Epic 5: Learning v2

- [x] Add learning schemas (AnswerSubmission, RubricCriterionScore, AnswerScoreBreakdown, AnswerReviewV2, SkillAttempt, SkillProfileV2, MasteryUpdate, WeaknessRecord, NextTaskRationale, LearningReport, SourceGroundingReview).
- [x] Add answer scorer v2 with rubric-based scoring.
- [x] Add source grounding checker comparing learner answers against sources.
- [x] Add skill profile v2 with criterion-level mastery and persistence.
- [x] Add deterministic mastery update with difficulty multipliers.
- [x] Add profile-aware next-task selector with weakness-driven focus.
- [x] Add learning report generator with markdown output.
- [x] Add harness validation for learning v2 artifacts.
- [x] Add CLI commands (answer submit, profile show, profile topic, learning report).
- [ ] Add skill profile persistence to Postgres.
- [ ] Add rubric-based LLM judge for production scoring.
- [ ] Add curriculum dashboard UI.

## Epic 6: Product UI

- [x] Add run loader utilities (list_runs, get_latest_run, load_artifact, summarize_run).
- [x] Add terminal run explorer.
- [x] Add markdown/HTML report export.
- [x] Add Streamlit dashboard with tabbed interface.
- [x] Add CLI commands (dashboard, runs list/latest/show, export).
- [x] Add FastAPI routes.
- [ ] Add Next.js dashboard.
- [ ] Add auth.
- [ ] Add workspace isolation.
- [ ] Add audit logs.
- [ ] Add deployment config.

## Epic 7: Domain Source Packs & Golden Evals

- [x] Add source pack format (manifest.json + sources/ + evals/).
- [x] Add PQC v1 source pack with 7 curated sources.
- [x] Add source pack loader (list, validate, install, status).
- [x] Add CLI commands for source packs.
- [x] Add golden eval schemas (retrieval, claim, answer, lesson).
- [x] Add golden eval fixtures (10 retrieval, 15 claims, 15 answers, 5 lessons).
- [x] Add golden eval runners with mock pipelines.
- [x] Add eval runner with summary and markdown reports.
- [x] Add CLI commands for evals (run, latest).
- [x] Add API endpoints for source-packs and evals.
- [x] Add golden_eval_summary.json to proof bundle.
- [x] Add --strict mode to verify-release with golden eval checks.
- [ ] Add dashboard Evals tab for viewing golden eval results.
- [ ] Add more domain packs (e.g., ML safety, cloud security).
- [ ] Add eval threshold configuration per pack.
- [ ] Add eval trend tracking across versions.

## Epic 8: Local v1 Release Candidate Hardening

- [x] Add release manifest schema (Pydantic model).
- [x] Add release checklist (12 individual checks).
- [x] Add release thresholds (configurable pass rates).
- [x] Add local-demo CLI command (13-step pipeline).
- [x] Add release CLI commands (check, manifest, report).
- [x] Add strict release verification (15 checks).
- [x] Add Dashboard Release tab.
- [x] Add export report enhancements.
- [ ] Add more domain packs (e.g., ML safety, cloud security).
- [ ] Add release versioning strategy.
- [ ] Add release changelog generation.
- [ ] Add release automation (CI/CD integration).
