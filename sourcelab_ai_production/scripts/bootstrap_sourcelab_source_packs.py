#!/usr/bin/env python3
"""
bootstrap_sourcelab_source_packs.py

Create SourceLab source-pack scaffolds from the user's recurring topic backlog.

What this does:
- Creates data/source_packs/<pack_name>/
- Writes pack.json, manifest.json, README.md, sources/*.md, evals/*_gold.json
- Avoids overwriting files unless --force is used
- Optionally runs SourceLab validation/eval commands
- Writes a summary report to artifacts/source_pack_bootstrap_report.md

Run from the SourceLab project root:

    python scripts/bootstrap_sourcelab_source_packs.py --packs core --validate
    python scripts/bootstrap_sourcelab_source_packs.py --packs all --validate --run-evals

Recommended first run:

    python scripts/bootstrap_sourcelab_source_packs.py --packs core --validate

Pack groups:
- core: agentic_engineering_v1, local_ai_infra_v1, rag_doc_intelligence_v1
- research: biomedical_ai_v1, materials_ai_v1, quantum_finance_v1
- business: trading_research_v1, blockchain_provenance_v1, logistics_earth_v1, grantops_business_v1
- all: all packs in this script

Notes:
- Existing pqc_v1 and ai_safety_v1 are not recreated by default.
- Generated sources are starter, grounded-by-design markdown seeds. Replace/expand them with stronger citations and docs over time.
- This script is local-first and does not use the network.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_MARKERS = [
    "pyproject.toml",
    "src/sourcelab",
    "data/source_packs",
]


@dataclass(frozen=True)
class SourceSeed:
    source_id: str
    title: str
    summary: str
    key_claims: list[str]
    use_cases: list[str]
    extra_sections: list[tuple[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class PackSeed:
    name: str
    title: str
    domain: str
    description: str
    topics: list[str]
    example_lessons: list[str]
    sources: list[SourceSeed] = field(default_factory=list)


PACKS: dict[str, PackSeed] = {
    "agentic_engineering_v1": PackSeed(
        name="agentic_engineering_v1",
        title="Agentic Engineering and Multi-Agent Software Workflows",
        domain="agentic_engineering",
        description="Source pack for local-first multi-agent engineering, coding agents, QA, DevOps, compliance, and human-in-the-loop orchestration.",
        topics=[
            "multi-agent software engineering",
            "coding agents",
            "human-in-the-loop orchestration",
            "agent QA",
            "DevOps automation",
            "compliance gates",
            "release validation",
        ],
        example_lessons=[
            "multi-agent software engineering control plane",
            "agent QA workflow",
            "human-in-the-loop release gates",
            "independent coding agent orchestration",
        ],
        sources=[
            SourceSeed(
                "agentic_engineering_liaison_architecture_001",
                "Local-First Multi-Agent Engineering Architecture",
                "A local-first control plane coordinates independent implementation, QA, DevOps, security, compliance, and research agents through explicit task packets and evidence artifacts.",
                [
                    "Independent agents should be coordinated by a control plane rather than nested inside one another.",
                    "Human approval gates should control production, customer, live-risk, and release transitions.",
                    "Each agent run should leave durable evidence so future operators can audit decisions and outputs.",
                ],
                [
                    "software task routing",
                    "multi-agent QA validation",
                    "release candidate checks",
                    "agent evidence review",
                ],
            ),
            SourceSeed(
                "agentic_engineering_quality_gates_002",
                "Evidence-Based Quality Gates",
                "Quality gates turn agent outputs into inspectable decisions by requiring tests, logs, proof artifacts, and explicit status before promotion.",
                [
                    "A gate should fail closed when required evidence is missing.",
                    "Validation artifacts should be linked to the exact task or run they support.",
                    "A human review state is safer than silently passing uncertain work.",
                ],
                [
                    "release validation",
                    "security review",
                    "compliance checks",
                    "production readiness review",
                ],
            ),
        ],
    ),
    "local_ai_infra_v1": PackSeed(
        name="local_ai_infra_v1",
        title="Local AI Infrastructure and Model Routing",
        domain="local_ai_infra",
        description="Source pack for DGX/EVO local AI infrastructure, inference servers, model routing, gateways, and local-first AI development.",
        topics=[
            "DGX Spark",
            "EVO-X2",
            "Ollama",
            "vLLM",
            "SGLang",
            "TensorRT-LLM",
            "LiteLLM",
            "local model routing",
            "OpenAI-compatible endpoints",
        ],
        example_lessons=[
            "local AI inference stack design",
            "DGX Spark model routing",
            "LiteLLM gateway for coding agents",
            "local model fallback architecture",
        ],
        sources=[
            SourceSeed(
                "local_ai_infra_routing_001",
                "Local Model Routing Architecture",
                "A local AI stack can route requests across deterministic fallback, local model servers, and OpenAI-compatible endpoints while preserving traceability. DGX Spark systems are common targets for local GPU inference clusters and coding-agent model routing.",
                [
                    "A model router should record backend, model, fallback, and prompt metadata.",
                    "Deterministic fallback is useful for testing and stable local demos.",
                    "Gateway layers such as LiteLLM can normalize multiple model providers behind one interface.",
                    "Router configuration should map DGX Spark workloads to appropriate local model backends.",
                ],
                [
                    "local model orchestration",
                    "coding agent model routing",
                    "offline-first AI workflows",
                ],
            ),
            SourceSeed(
                "local_ai_infra_observability_002",
                "Local AI Observability",
                "Local inference workflows need health checks, model call traces, latency records, and fallback indicators to be trustworthy. EVO-X2 edge workstations benefit from the same observability signals as rack-scale DGX deployments.",
                [
                    "Model call traces help distinguish deterministic output from LLM-generated output.",
                    "Health checks should make unavailable model backends visible rather than silently falling back.",
                    "Run artifacts should identify which model mode created each output.",
                    "Observability dashboards should surface EVO-class GPU utilization and fallback events.",
                ],
                [
                    "debugging local models",
                    "run trace inspection",
                    "demo readiness",
                ],
            ),
        ],
    ),
    "rag_doc_intelligence_v1": PackSeed(
        name="rag_doc_intelligence_v1",
        title="RAG and Document Intelligence",
        domain="rag_doc_intelligence",
        description="Source pack for adaptive graph RAG, source-grounded generation, document intelligence, deduplication, and proof-bundle workflows.",
        topics=[
            "adaptive graph RAG",
            "document AI",
            "source-grounded generation",
            "document deduplication",
            "knowledge graphs",
            "semantic retrieval",
            "proof bundles",
        ],
        example_lessons=[
            "source-grounded document assistant",
            "adaptive graph RAG architecture",
            "document deduplication review workflow",
            "proof bundle design for RAG outputs",
        ],
        sources=[
            SourceSeed(
                "rag_doc_intelligence_grounding_001",
                "Source-Grounded Document Intelligence",
                "A document intelligence system should retrieve evidence, generate grounded outputs, extract claims, and verify citations before presenting final answers.",
                [
                    "Generated answers should cite source chunks used to support claims.",
                    "Claim extraction makes it possible to verify factual statements after generation.",
                    "Proof bundles should contain retrieval, generation, verification, and export artifacts.",
                ],
                [
                    "document QA",
                    "audit-ready RAG",
                    "source-grounded lesson generation",
                ],
            ),
            SourceSeed(
                "rag_doc_intelligence_dedup_002",
                "Document Deduplication and Review",
                "Deduplication workflows combine exact matching, fuzzy matching, embeddings, and human review to reduce duplicate documents without losing important evidence.",
                [
                    "Exact hashes catch byte-identical documents.",
                    "Near-duplicate detection should route uncertain matches to a reviewer.",
                    "Reviewer decisions should be stored as durable evidence.",
                ],
                [
                    "medical document review",
                    "legal document cleanup",
                    "enterprise evidence repositories",
                ],
            ),
        ],
    ),
    "biomedical_ai_v1": PackSeed(
        name="biomedical_ai_v1",
        title="Biomedical AI and Evidence Graphs",
        domain="biomedical_ai",
        description="Source pack for biomedical prediction, clinical evidence graphs, AlphaFold/OpenFold-style workflows, drug discovery, and hybrid quantum/ML research.",
        topics=[
            "biomedical prediction",
            "clinical evidence graphs",
            "AlphaFold",
            "OpenFold",
            "Hetionet",
            "drug discovery",
            "hybrid QML biomedical workflows",
        ],
        example_lessons=[
            "hybrid QML knowledge graph biomedical prediction",
            "clinical evidence graph assistant",
            "AlphaFold-assisted biomedical workflow",
            "biomedical evidence graph validation",
        ],
        sources=[
            SourceSeed(
                "biomedical_ai_evidence_graphs_001",
                "Biomedical Evidence Graph Workflows",
                "Biomedical AI workflows benefit from explicit evidence graphs that link entities such as genes, diseases, compounds, papers, and clinical outcomes.",
                [
                    "Biomedical predictions should preserve provenance from source evidence to model output.",
                    "Knowledge graphs can represent relationships among biomedical entities for downstream reasoning.",
                    "High-stakes biomedical outputs should include uncertainty and human review gates.",
                ],
                [
                    "clinical evidence review",
                    "drug repurposing hypotheses",
                    "biomedical QA",
                ],
            ),
            SourceSeed(
                "biomedical_ai_structure_prediction_002",
                "Protein Structure and Downstream Biomedical Workflows",
                "Structure-prediction systems can support biomedical research when their outputs are connected to evidence, assumptions, and validation workflows.",
                [
                    "Predicted structures should not be treated as clinical truth without validation.",
                    "Structure outputs can become features in broader biomedical pipelines.",
                    "Evidence traceability is important when combining structure models with knowledge graphs.",
                ],
                [
                    "protein-target analysis",
                    "biomedical feature generation",
                    "research triage",
                ],
            ),
        ],
    ),
    "materials_ai_v1": PackSeed(
        name="materials_ai_v1",
        title="Materials AI and Quantum Chemistry Workflows",
        domain="materials_ai",
        description="Source pack for materials discovery, quantum chemistry, CUDA-Q/VQE-style methods, surrogate models, and generative materials workflows.",
        topics=[
            "materials discovery",
            "quantum chemistry",
            "CUDA-Q",
            "VQE",
            "ADAPT-VQE",
            "surrogate modeling",
            "MatterGen-style workflows",
        ],
        example_lessons=[
            "materials discovery with quantum AI",
            "ADAPT-VQE materials workflow",
            "surrogate model for materials screening",
            "quantum chemistry evidence workflow",
        ],
        sources=[
            SourceSeed(
                "materials_ai_screening_001",
                "Materials Discovery Screening Pipeline",
                "A materials AI workflow can combine candidate generation, surrogate screening, simulation, and validation gates to prioritize promising materials.",
                [
                    "Surrogate models can reduce the cost of exploring a large candidate space.",
                    "Simulation outputs should be tracked with configuration and provenance.",
                    "Candidate ranking should be separated from final validation.",
                ],
                [
                    "materials screening",
                    "simulation triage",
                    "candidate prioritization",
                ],
            ),
            SourceSeed(
                "materials_ai_quantum_methods_002",
                "Quantum Methods for Materials Workflows",
                "Quantum algorithms such as VQE-style methods can be explored as part of materials workflows when benchmarked against classical baselines.",
                [
                    "Hybrid quantum methods require careful benchmarking and reproducible configurations.",
                    "Near-term quantum workflows should avoid overstating advantage without evidence.",
                    "Classical surrogate and baseline methods remain necessary for comparison.",
                ],
                [
                    "VQE experiments",
                    "hybrid quantum-classical research",
                    "materials benchmarking",
                ],
            ),
        ],
    ),
    "quantum_finance_v1": PackSeed(
        name="quantum_finance_v1",
        title="Quantum Finance and Portfolio Optimization",
        domain="quantum_finance",
        description="Source pack for quantum and hybrid portfolio optimization, QAOA/QUBO formulation, risk modeling, and finance backtesting workflows.",
        topics=[
            "quantum portfolio optimization",
            "QAOA",
            "VQE",
            "HRP",
            "Markowitz optimization",
            "QUBO",
            "risk models",
            "backtesting",
        ],
        example_lessons=[
            "quantum hybrid portfolio optimizer",
            "QAOA portfolio selection",
            "risk-aware portfolio backtesting",
            "QUBO formulation for asset selection",
        ],
        sources=[
            SourceSeed(
                "quantum_finance_portfolio_001",
                "Hybrid Portfolio Optimization Workflow",
                "A hybrid portfolio workflow can combine classical risk models, discrete optimization formulations, and quantum-inspired or quantum optimizers.",
                [
                    "Portfolio optimization should separate data ingestion, risk estimation, optimization, and backtesting.",
                    "QUBO formulations can encode discrete asset selection constraints.",
                    "Backtests should include costs, turnover, and out-of-sample validation.",
                ],
                [
                    "portfolio construction",
                    "risk-aware optimization",
                    "QAOA experiments",
                ],
            ),
            SourceSeed(
                "quantum_finance_risk_002",
                "Risk and Validation for Finance Models",
                "Finance models require careful validation because small backtest errors can produce misleading expectations of profit.",
                [
                    "QAOA and other quantum optimizers should be validated out-of-sample before portfolio promotion.",
                    "A strategy should be evaluated out-of-sample before promotion.",
                    "Transaction costs and slippage should be included in performance estimates.",
                    "Live deployment should require human approval and monitoring gates.",
                ],
                [
                    "strategy validation",
                    "risk controls",
                    "promotion gates",
                ],
                extra_sections=[
                    (
                        "QAOA Validation Methodology",
                        "The Quantum Approximate Optimization Algorithm (QAOA) is a variational quantum algorithm that approximates solutions to combinatorial optimization problems by alternating between problem-defining and mixing Hamiltonians. In finance applications, QAOA is applied to portfolio optimization, asset selection, and risk scenario reduction problems that can be encoded as quadratic unconstrained binary optimization (QUBO) or higher-order polynomial unconstrained binary optimization (PUBO) formulations. Validation of QAOA results requires a structured methodology that accounts for both quantum-specific and financial domain considerations.\n\nThe validation pipeline should include: (1) classical baseline comparison using the same QUBO formulation solved via classical heuristics such as simulated annealing or Gurobi, establishing a performance floor; (2) solution quality metrics including approximation ratio relative to the known optimum for small problem instances, variance across repeated runs to assess algorithmic stability, and scaling behavior as problem size increases; (3) out-of-sample testing where the QAOA-selected portfolio is evaluated on data not used during optimization, measuring realized Sharpe ratio, turnover, and maximum drawdown against the classical baseline; (4) noise sensitivity analysis that simulates the QAOA circuit under varying noise levels to identify the error threshold below which the quantum solution degrades below the classical baseline. Without this structured validation, a QAOA-generated portfolio may appear optimal in-sample while underperforming classical alternatives in live deployment.",
                    ),
                ],
            ),
        ],
    ),
    "trading_research_v1": PackSeed(
        name="trading_research_v1",
        title="Trading Research and Market Strategy Validation",
        domain="trading_research",
        description="Source pack for event markets, equities factors, crypto meta-labeling, options/forex strategy testing, and settlement verification workflows.",
        topics=[
            "event markets",
            "Kalshi",
            "Polymarket",
            "crypto meta-labeling",
            "triple-barrier labeling",
            "equities factors",
            "options strategies",
            "forex regimes",
            "settlement verification",
        ],
        example_lessons=[
            "factor ranking equity strategy",
            "event market settlement verification",
            "crypto triple-barrier meta-labeling",
            "options flow validation workflow",
        ],
        sources=[
            SourceSeed(
                "trading_research_validation_001",
                "Trading Strategy Validation Gates",
                "Trading systems need validation gates that separate research signals from promotion-ready strategies.",
                [
                    "Factor ranking equity strategies should pass validation gates before promotion.",
                    "Event markets require settlement verification before backtest results are trusted.",
                    "Backtests should account for costs, slippage, and data leakage.",
                    "Promotion should require clean resolved examples and calibrated confidence.",
                    "Synthetic examples can test mechanics but should not replace real historical validation.",
                ],
                [
                    "strategy research",
                    "promotion gating",
                    "settlement verification",
                ],
                extra_sections=[
                    (
                        "Factor Ranking for Equity Strategies",
                        "Factor ranking is a systematic approach to evaluating and selecting equity factors \u2014 such as value, momentum, quality, size, low volatility, and growth \u2014 based on their forecasted risk-adjusted returns. A factor ranking model scores each candidate factor on predictive power, persistence, capacity, and orthogonalization against known factors. The ranking process typically involves rolling-window cross-sectional regressions (Fama-MacBeth or panel regression) to estimate factor premia, followed by a rank aggregation step that combines signal strength, turnover costs, and diversification benefits into a composite ranking score. The top-ranked factors are then combined into a multi-factor portfolio with weights proportional to their ranking scores, subject to risk budget constraints and sector concentration limits.\n\nValidation gates for factor ranking strategies require at least three independent implementation checks: (1) replication of publicly documented factor returns from academic literature to ensure the factor construction methodology is correct; (2) out-of-sample testing on a time period not used during factor discovery, with explicit documentation of any data snooping biases; (3) a turnover and cost analysis that estimates the net return after transaction costs, market impact, and shorting fees. A factor ranking strategy should not be promoted to live trading until all three gates pass, the strategy survives a walk-forward optimization with expanding windows, and the composite portfolio's information ratio exceeds a pre-defined threshold over a statistically significant sample.",
                    ),
                    (
                        "Event Market Settlement Verification",
                        "Event markets (also called prediction markets) allow participants to trade contracts whose payoff depends on the outcome of a specified future event, such as an election result, economic indicator release, or regulatory decision. Settlement verification is the process of confirming that the market's declared outcome matches an authoritative source and that all contracts are settled at the correct price. Kalshi, PredictIt, and CFTC-regulated event markets require a settlement verification workflow that checks each market's outcome against a designated source document (such as the FOMC statement, Bureau of Labor Statistics release, or state election certification) and records the verification result as an on-chain or database entry.\n\nA robust settlement verification pipeline includes: (1) automated source fetching from the designated authoritative API or publication feed at the scheduled settlement time; (2) deterministic outcome mapping that translates the source data into the market's predefined outcome categories; (3) a manual verification step for high-stakes markets where the settlement value exceeds a configurable threshold; (4) an audit log that records the source URL, fetched content hash, mapped outcome, verifier identity, and timestamp for each settlement event. Settlement discrepancies \u2014 where the market's declared outcome differs from the authoritative source \u2014 must trigger an immediate trading halt and a structured dispute resolution process before any contracts are settled. Backtesters that use historical event market data should verify that each historical market in the sample has a resolved settlement row with a verifiable source reference; unresolved or self-reported outcomes should be excluded from backtest datasets to prevent look-ahead bias.",
                    ),
                ],
            ),
            SourceSeed(
                "trading_research_meta_labeling_002",
                "Meta-Labeling and Outcome Verification",
                "Meta-labeling workflows estimate whether a candidate trade is worth taking, while settlement verification connects predictions to resolved outcomes.",
                [
                    "Kalshi and similar event markets need resolved outcome rows for reliable calibration.",
                    "Triple-barrier labeling can define outcomes using profit, loss, and time boundaries.",
                    "A model should learn when to skip weak candidates.",
                    "Resolved outcome rows are required for reliable calibration.",
                ],
                [
                    "crypto strategy testing",
                    "event market verification",
                    "trade selection models",
                ],
                extra_sections=[
                    (
                        "Kalshi Settlement Workflow",
                        "Kalshi is a CFTC-regulated event exchange that offers markets on economic, climate, health, and political outcomes with standard binary contract settlements. Each Kalshi market has a defined resolution source (e.g., a specific government agency report), a resolution date, and settlement instructions that map possible outcomes to contract payoff values. Settlement verification for Kalshi markets follows a deterministic workflow: a verification agent fetches the resolution source document at the scheduled resolution time, extracts the relevant value or category using a predefined parsing rule, maps the extracted value to the market's outcome definitions, and submits the settlement transaction to the exchange's settlement contract.\n\nThe verification agent logs each step including the source URL, the raw fetched content, the parsed value, the mapped outcome, and the settlement transaction hash. For backtesting, historical Kalshi market data must include a verified settlement record for every market in the sample. Markets that were not resolved at the time of dataset creation \u2014 or that were resolved using self-reported outcomes without an authoritative source \u2014 should be excluded from backtest datasets to prevent look-ahead or verification bias. The settlement verification pipeline also produces a daily audit report that lists all markets settled, their resolution sources, any verification discrepancies encountered, and the subset of markets that required manual intervention due to ambiguous source data.",
                    ),
                ],
            ),
        ],
    ),
    "blockchain_provenance_v1": PackSeed(
        name="blockchain_provenance_v1",
        title="Blockchain Provenance and Verifiable Systems",
        domain="blockchain_provenance",
        description="Source pack for smart contracts, DID, ZK proofs, proof-of-human, provenance, audit trails, and AI-output verification.",
        topics=[
            "smart contracts",
            "DID",
            "ZK proofs",
            "proof of human",
            "dApps",
            "provenance",
            "blockchain audit trails",
            "AI output verification",
        ],
        example_lessons=[
            "proof of human stack",
            "blockchain provenance for AI outputs",
            "ZK identity for agentic web",
            "smart contract audit trail design",
        ],
        sources=[
            SourceSeed(
                "blockchain_provenance_ai_outputs_001",
                "Provenance for AI Outputs",
                "A provenance workflow can record metadata, evidence, hashes, and review status for generated outputs without claiming that blockchain alone guarantees truth.",
                [
                    "Smart contracts can anchor provenance metadata on-chain but do not replace evidence review.",
                    "Provenance should identify what was generated, from which sources, and under which configuration.",
                    "Hashes can support integrity checks but do not validate factual correctness.",
                    "Human review and evidence validation remain necessary for high-stakes claims.",
                ],
                [
                    "AI output audit trails",
                    "document provenance",
                    "proof bundle integrity",
                ],
                extra_sections=[
                    (
                        "Smart Contracts Provenance Anchoring",
                        "Smart contracts can anchor provenance metadata on-chain by registering content hashes, timestamps, and authorship claims as immutable events. A provenance anchoring workflow writes a cryptographic digest of each generated output into a smart contract's event log or state variable, producing an on-chain receipt that can be independently verified without revealing the underlying content. This pattern is used in document timestamping services, academic publishing registries, and supply chain audit trails where multiple parties need a shared, tamper-evident record of when a piece of content existed and who created it.\n\nThe anchoring contract typically stores a mapping from content hash to a struct containing the submitter address, block timestamp, and an optional metadata URI. Verification clients recompute the hash and check its presence on-chain via a read-only contract call. To preserve privacy, the raw content is never stored on-chain; only the hash and metadata reference are recorded. This design separates the proof of existence (on-chain) from the content itself (off-chain), aligning with regulatory frameworks that require evidentiary chains of custody without exposing sensitive data.",
                    ),
                ],
            ),
            SourceSeed(
                "blockchain_provenance_identity_002",
                "Identity and Verification Layers",
                "DID and ZK-style identity systems can support selective disclosure and verification workflows when designed around concrete trust assumptions.",
                [
                    "Identity systems should define issuer, subject, verifier, and revocation assumptions.",
                    "Zero-knowledge proofs can hide details while proving selected statements.",
                    "Operational risk remains even when cryptographic primitives are sound.",
                ],
                [
                    "proof of human",
                    "credential verification",
                    "agent identity",
                ],
                extra_sections=[
                    (
                        "Provenance Anchoring in Identity Systems",
                        "Provenance anchoring for identity systems extends the on-chain hash registration pattern to cover credential issuance, revocation, and verification events. A decentralized identity (DID) controller can anchor a credential schema hash and each issued credential's digest to a smart contract, creating an auditable issuance log. Verifiers inspect the on-chain receipt to confirm that a credential was issued by a known DID controller at a specific point in time, without requiring a connection to the issuer at verification time. This pattern supports selective disclosure: the holder presents only the relevant credential fields plus the on-chain receipt, and the verifier confirms the receipt matches the presented data without accessing the full credential store.\n\nRevocation registries can be implemented as on-chain allow-lists or accumulator contracts that anchor the current revocation state. Each revocation event produces an on-chain event, enabling third-party monitors to detect unexpected revocation activity. The combination of issuance anchoring and revocation anchoring creates a complete provenance trail for the credential lifecycle, supporting audit requirements in regulated industries such as finance, healthcare, and defense supply chains.",
                    ),
                ],
            ),
        ],
    ),
    "logistics_earth_v1": PackSeed(
        name="logistics_earth_v1",
        title="Logistics, Earth Observation, and Digital Twins",
        domain="logistics_earth",
        description="Source pack for warehouse digital twins, satellite-informed logistics, supply chain optimization, Earth observation, climate, and routing workflows.",
        topics=[
            "warehouse digital twins",
            "satellite-informed logistics",
            "supply chain optimization",
            "Earth observation",
            "climate workflows",
            "routing optimization",
        ],
        example_lessons=[
            "warehouse digital twin optimization",
            "satellite-informed logistics planning",
            "quantum logistics routing",
            "supply chain visibility workflow",
        ],
        sources=[
            SourceSeed(
                "logistics_earth_digital_twins_001",
                "Warehouse Digital Twin Workflow",
                "A warehouse digital twin connects operational data, layout constraints, simulation, and optimization to improve logistics decisions.",
                [
                    "Digital twin outputs depend on the quality and freshness of operational data.",
                    "Optimization recommendations should be tested against constraints and edge cases.",
                    "Human operators should review high-impact operational changes.",
                ],
                [
                    "warehouse optimization",
                    "simulation planning",
                    "routing workflow",
                ],
            ),
            SourceSeed(
                "logistics_earth_satellite_002",
                "Satellite-Informed Logistics",
                "Satellite and Earth observation data can support logistics planning when fused with ground-truth operational sources.",
                [
                    "Remote sensing signals should be validated against local context.",
                    "Environmental or infrastructure signals can inform routing and risk planning.",
                    "Data provenance is important when combining open-source geospatial inputs.",
                ],
                [
                    "supply chain visibility",
                    "geospatial risk planning",
                    "route optimization",
                ],
            ),
        ],
    ),
    "grantops_business_v1": PackSeed(
        name="grantops_business_v1",
        title="GrantOps, Startup Funding, and Technical Business Strategy",
        domain="grantops_business",
        description="Source pack for SBIR/STTR, regional incentives, hackathons, fellowships, startup grant strategy, and hardware/business planning.",
        topics=[
            "SBIR",
            "STTR",
            "Florida High Tech Corridor",
            "Miami incentives",
            "startup grants",
            "hackathons",
            "fellowships",
            "hardware tax strategy",
        ],
        example_lessons=[
            "SBIR proposal map for quantum AI",
            "grant strategy for local AI hardware",
            "hackathon business concept selection",
            "startup funding evidence checklist",
        ],
        sources=[
            SourceSeed(
                "grantops_business_funding_map_001",
                "Funding Strategy Map",
                "A funding strategy should map project evidence, eligibility, timeline, budget, and expected deliverables before applying.",
                [
                    "SBIR proposals should map technical milestones to phase I and phase II deliverables.",
                    "Grant applications should align technical objectives with funder priorities.",
                    "A strong application needs evidence of feasibility and execution plan.",
                    "Hardware and compute costs should be justified through project outcomes.",
                ],
                [
                    "grant planning",
                    "hackathon project selection",
                    "startup funding roadmap",
                ],
                extra_sections=[
                    (
                        "SBIR and STTR Proposal Strategy",
                        "SBIR (Small Business Innovation Research) and STTR (Small Business Technology Transfer) programs provide non-dilutive funding for early-stage R&D across multiple federal agencies including NSF, NIH, DOD, DOE, NASA, and DHS. Each agency publishes quarterly or annual solicitations that specify technical topics aligned with agency mission needs. A competitive SBIR proposal maps the company's technical approach to the solicitation topic's problem statement, defines measurable phase I feasibility milestones (typically 6-12 months, $50K-$250K), and outlines a phase II development path (typically 18-24 months, $500K-$1.5M).\n\nPhase I proposals should demonstrate that the team understands the technical challenge, has a credible approach, and can deliver a proof-of-concept by phase I end. Phase II proposals build on phase I results with a more detailed work plan, commercialization strategy, and team expansion plan. STTR proposals differ from SBIR in requiring a qualified research institution partner and a joint work plan that allocates at least 30% of the work to the research institution. The STTR format is particularly well-suited for deep-tech proposals where the small business commercializes a technology originally developed at a university or federal lab.\n\nBoth SBIR and STTR proposals benefit from including preliminary data or demonstrations, a clear differentiation from prior work, a realistic budget that justifies hardware and compute costs through project outcomes, and letters of commitment from potential phase II commercialization partners. Agency-specific proposal guides (such as NSF SBIR/STTR Proposal Preparation Checklist or DOD SBIR BAA instructions) provide detailed formatting and content requirements that should be followed precisely.",
                    ),
                ],
            ),
            SourceSeed(
                "grantops_business_demo_evidence_002",
                "Demo Evidence for Funding and Interviews",
                "A strong demo package connects problem, workflow, validation results, proof artifacts, and next milestones into a coherent story.",
                [
                    "STTR applications require a qualified research partner and joint work-plan evidence.",
                    "A demo should show working software rather than only describing architecture.",
                    "Validation results and tests increase credibility.",
                    "Clear limitations make the project more trustworthy.",
                ],
                [
                    "demo preparation",
                    "interview portfolio",
                    "grant evidence package",
                ],
            ),
        ],
    ),
    "emerging_tech_watchlist_v1": PackSeed(
        name="emerging_tech_watchlist_v1",
        title="Emerging Technology Watchlist",
        domain="emerging_tech_watchlist",
        description="Source pack for tracking emerging technology domains including quantum, fusion, advanced nuclear, drones, defense, satellite ISR, and cybersecurity.",
        topics=[
            "quantum technology",
            "fusion",
            "advanced nuclear",
            "eVTOL",
            "drones",
            "orbital defense",
            "satellite ISR",
            "cybersecurity companies",
        ],
        example_lessons=[
            "quantum AI defense technology map",
            "fusion and advanced nuclear watchlist",
            "orbital defense and satellite ISR",
            "emerging cybersecurity company thesis",
        ],
        sources=[
            SourceSeed(
                "emerging_tech_watchlist_evaluation_001",
                "Emerging Technology Evaluation",
                "Emerging technology watchlists should separate hype, technical readiness, market adoption, regulatory risk, and evidence quality.",
                [
                    "A watchlist should track evidence and uncertainty, not only attractive narratives.",
                    "Technical readiness and adoption readiness are different dimensions.",
                    "Investment or product decisions should require updated source validation.",
                ],
                [
                    "market scanning",
                    "technology thesis building",
                    "risk assessment",
                ],
            ),
            SourceSeed(
                "emerging_tech_watchlist_defense_002",
                "Defense and Space Technology Mapping",
                "Defense and space technology analysis should connect mission need, technical capability, procurement pathway, and risk.",
                [
                    "Fusion and advanced nuclear programs require distinct readiness and procurement assessments.",
                    "Defense technology claims require careful source quality assessment.",
                    "Satellite and ISR workflows involve technical, policy, and operational constraints.",
                    "Dual-use technology requires legal and ethical review.",
                ],
                [
                    "defense tech mapping",
                    "space market analysis",
                    "dual-use risk review",
                ],
                extra_sections=[
                    (
                        "Fusion Readiness Assessment",
                        "Fusion energy readiness is evaluated across multiple distinct tracks: plasma confinement physics, tritium breeding and fuel cycle, high-field magnet engineering, first-wall materials, and balance-of-plant integration. Each track has its own technology readiness level (TRL) trajectory that must be assessed independently because progress in one area does not guarantee readiness in others. For example, a company may demonstrate a TRL-5 plasma confinement concept while its tritium breeding blanket remains at TRL-3, making a system-level deployment timeline uncertain.\n\nThe defense and space sectors track fusion readiness through three specific lenses: portable power for forward operating bases (requiring MW-scale output in transportable form factors), spacecraft propulsion (requiring high specific impulse with low mass-to-power ratios), and hard-to-decarbonize installation energy (requiring continuous baseload output with high reliability). Each use case imposes different weightings on the fusion technology parameters \u2014 portability matters most for defense logistics, while specific impulse dominates propulsion assessments. Procurement pathways differ as well: defense fusion investments flow through DARPA and DIU contracts, space applications through NASA and Space Force SBIRs, and installation energy through DOE ARPA-E and INFUSE programs. Understanding these distinct readiness and acquisition tracks is essential for maintaining an accurate watchlist position on fusion technologies.",
                    ),
                ],
            ),
        ],
    ),
    "career_learning_v1": PackSeed(
        name="career_learning_v1",
        title="Career Learning, Portfolio Evidence, and Technical Growth",
        domain="career_learning",
        description="Source pack for resume evidence, MDC/CodePath, Qiskit Advocate, NVIDIA Inception, learning plans, and interview/demo preparation.",
        topics=[
            "resume evidence",
            "MDC CodePath",
            "Qiskit Advocate",
            "NVIDIA Inception",
            "technical learning plans",
            "portfolio proof bundles",
            "interview demos",
        ],
        example_lessons=[
            "technical resume project evidence",
            "AI quantum learning roadmap",
            "portfolio proof bundle for interviews",
            "project-based interview demo plan",
        ],
        sources=[
            SourceSeed(
                "career_learning_portfolio_001",
                "Portfolio Evidence Workflow",
                "A technical portfolio is stronger when each project has a clear problem, architecture, implementation evidence, tests, and demo path.",
                [
                    "Resume claims should map to concrete artifacts such as repos, tests, docs, and demos.",
                    "Project evidence should show both technical depth and user-facing value.",
                    "A proof bundle can help convert project work into interview-ready evidence.",
                ],
                [
                    "resume improvement",
                    "interview preparation",
                    "portfolio review",
                ],
            ),
            SourceSeed(
                "career_learning_roadmap_002",
                "Technical Learning Roadmap",
                "A learning roadmap should connect topics, projects, credentials, and demos into a sequence that produces evidence over time.",
                [
                    "MDC CodePath and similar credential programs should be paired with portfolio projects.",
                    "Learning is more valuable when it produces usable artifacts.",
                    "Certifications should be supported by project evidence.",
                    "Recurring review helps update priorities as goals change.",
                ],
                [
                    "learning plans",
                    "credential strategy",
                    "project sequencing",
                ],
                extra_sections=[
                    (
                        "MDC CodePath Credential Pathway",
                        "The MDC CodePath credential pathway provides a structured sequence of project-based certifications that build from core software engineering fundamentals into specialized AI and infrastructure roles. Each credential tier requires the learner to submit a portfolio project that demonstrates the specific competencies covered in the pathway module. The pathway progresses through four tiers: Foundation (algorithms, data structures, system design), Application (full-stack development, API design, testing), Specialization (machine learning operations, distributed systems, security engineering), and Capstone (a mentored open-source or industry-sponsored project with documented evidence of technical decisions, trade-offs, and validation results).\n\nCredential candidates compile a portfolio artifact for each tier that includes the project repository, a technical design document, test coverage reports, and a demo walkthrough. Portfolio evidence is reviewed against a rubric that evaluates technical depth, user-facing value, testing rigor, and documentation quality. Successful completion of a tier unlocks the next pathway module and contributes to a verifiable credential that can be shared with employers through standard digital wallet formats. The pathway is designed to produce concrete, interview-ready evidence at each stage rather than relying on multiple-choice assessments or time-based completion metrics.",
                    ),
                ],
            ),
        ],
    ),
    "ml_safety_v1": PackSeed(
        name="ml_safety_v1",
        title="Machine Learning Safety, Alignment, and Robustness",
        domain="ml_safety",
        description="Source pack for ML safety, alignment, robustness, evaluation, red-teaming, monitoring, and responsible deployment guardrails.",
        topics=[
            "ML safety",
            "alignment",
            "robustness",
            "adversarial robustness",
            "red-teaming",
            "evaluation harness",
            "model monitoring",
            "responsible deployment",
            "safety evals",
        ],
        example_lessons=[
            "ML safety evaluation harness design",
            "adversarial robustness review workflow",
            "red-team triage and remediation",
            "responsible deployment guardrails",
        ],
        sources=[
            SourceSeed(
                "ml_safety_evaluation_001",
                "ML Safety Evaluation and Red-Teaming",
                "An ML safety evaluation workflow should combine automated evals, adversarial probes, red-team findings, and human review before deployment promotion.",
                [
                    "Safety evals should run before deployment promotion and fail closed on missing evidence.",
                    "Red-team findings should be triaged by severity and tracked to remediation.",
                    "Robustness tests should cover distribution shift, adversarial inputs, and edge cases.",
                    "Safety claims should cite the eval cases and thresholds that support them.",
                ],
                [
                    "safety evaluation",
                    "red-team triage",
                    "deployment gating",
                ],
            ),
            SourceSeed(
                "ml_safety_alignment_002",
                "Alignment and Monitoring Guardrails",
                "Alignment and monitoring guardrails connect model behavior, telemetry, human review, and rollback into a deployment safety loop.",
                [
                    "Monitoring should surface drift, regressions, and unsafe outputs for review.",
                    "Rollback paths should be tested before deployment rather than assumed available.",
                    "Alignment claims should distinguish tested behavior from aspirational goals.",
                    "High-stakes actions should require human approval gates.",
                ],
                [
                    "deployment monitoring",
                    "alignment review",
                    "rollback planning",
                ],
            ),
        ],
    ),
    "cloud_security_v1": PackSeed(
        name="cloud_security_v1",
        title="Cloud Security, CSPM, and Cloud-Native Defense",
        domain="cloud_security",
        description="Source pack for cloud security posture management, Kubernetes security, zero trust, supply chain security, and cloud-native defense workflows.",
        topics=[
            "cloud security posture management",
            "CSPM",
            "Kubernetes security",
            "zero trust",
            "supply chain security",
            "container security",
            "IAM hardening",
            "cloud-native defense",
            "SBOM",
        ],
        example_lessons=[
            "cloud security posture management review",
            "Kubernetes security hardening workflow",
            "zero trust architecture review",
            "software supply chain security gates",
        ],
        sources=[
            SourceSeed(
                "cloud_security_posture_001",
                "Cloud Security Posture Management Workflow",
                "A CSPM workflow continuously discovers cloud assets, evaluates configuration against benchmarks, prioritizes findings by exposure, and tracks remediation to closure.",
                [
                    "CSPM findings should be prioritized by exposure and blast radius rather than only severity.",
                    "Configuration checks should map to a recognized benchmark such as CIS or NIST.",
                    "Remediation should be tracked to closure with evidence rather than marked resolved on dismissal.",
                    "Least-privilege IAM should be verified continuously, not only at initial setup.",
                ],
                [
                    "posture management",
                    "configuration drift review",
                    "IAM hardening",
                ],
            ),
            SourceSeed(
                "cloud_security_supply_chain_002",
                "Supply Chain and Cloud-Native Runtime Defense",
                "Software supply chain security combines SBOMs, signed artifacts, admission control, and runtime threat detection for cloud-native workloads.",
                [
                    "Container images should be scanned and signed before admission to production.",
                    "SBOMs should be generated and stored as evidence for every released artifact.",
                    "Admission controllers should fail closed on unsigned or vulnerable images.",
                    "Runtime detection should complement, not replace, build-time supply chain gates.",
                ],
                [
                    "supply chain gating",
                    "container admission control",
                    "runtime threat review",
                ],
            ),
        ],
    ),
}

GROUPS: dict[str, list[str]] = {
    "core": ["agentic_engineering_v1", "local_ai_infra_v1", "rag_doc_intelligence_v1"],
    "research": ["biomedical_ai_v1", "materials_ai_v1", "quantum_finance_v1"],
    "business": [
        "trading_research_v1",
        "blockchain_provenance_v1",
        "logistics_earth_v1",
        "grantops_business_v1",
    ],
    "watchlist": ["emerging_tech_watchlist_v1", "career_learning_v1"],
    "safety": ["ml_safety_v1", "cloud_security_v1"],
}
GROUPS["all"] = list(PACKS.keys())

GOLD_EVAL_FILES = (
    "retrieval_gold.json",
    "claim_gold.json",
    "answer_gold.json",
    "lesson_gold.json",
)
LEGACY_EVAL_RENAMES = {
    "retrieval_eval.json": "retrieval_gold.json",
    "claim_eval.json": "claim_gold.json",
    "answer_eval.json": "answer_gold.json",
    "lesson_eval.json": "lesson_gold.json",
}
LEGACY_EVAL_FILE_NAMES = (
    "retrieval_eval.json",
    "lesson_eval.json",
    "answer_eval.json",
)
PROTECTED_PACKS = frozenset({"pqc_v1", "ai_safety_v1"})


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def now_iso_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def find_project_root(start: Path) -> Path:
    cur = start.resolve()
    for candidate in [cur, *cur.parents]:
        if all((candidate / marker).exists() for marker in PROJECT_MARKERS):
            return candidate
    raise SystemExit(
        "Could not find SourceLab project root. Run this from the project root or a subdirectory."
    )


def slugify(value: str) -> str:
    return (
        value.lower()
        .replace("/", " ")
        .replace("&", " and ")
        .replace("-", " ")
        .replace("_", " ")
        .strip()
        .replace(" ", "_")
    )


def write_file(path: Path, content: str, force: bool, dry_run: bool) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return "skipped_existing"
    if dry_run:
        return "would_write"
    path.write_text(content, encoding="utf-8")
    return "written"


def source_trust_tier(index: int) -> str:
    return "B" if index == 0 else "C"


def source_manifest_entry(pack: PackSeed, source: SourceSeed, index: int) -> dict[str, Any]:
    trust_tier = source_trust_tier(index)
    if trust_tier == "B":
        publisher = "SourceLab (local guidance)"
        source_type = "technical_notes"
    else:
        publisher = "SourceLab (local analysis)"
        source_type = "project_seed"
    return {
        "source_id": source.source_id,
        "filename": f"{source.source_id}.md",
        "trust_tier": trust_tier,
        "publisher": publisher,
        "source_type": source_type,
        "title": source.title,
    }


def manifest_json(pack: PackSeed) -> str:
    payload: dict[str, Any] = {
        "pack_name": pack.name,
        "version": "1.0.0",
        "title": pack.title,
        "description": pack.description,
        "created_at": now_iso_z(),
        "sources": [
            source_manifest_entry(pack, source, index)
            for index, source in enumerate(pack.sources)
        ],
        "evals": list(GOLD_EVAL_FILES),
    }
    return json.dumps(payload, indent=2) + "\n"


def pack_json(pack: PackSeed) -> str:
    payload: dict[str, Any] = {
        "name": pack.name,
        "title": pack.title,
        "version": "1.0.0",
        "description": pack.description,
        "domain": pack.domain,
        "required_for_strict_release": False,
        "sources_dir": "sources",
        "evals_dir": "evals",
        "topics": pack.topics,
        "example_lessons": pack.example_lessons,
        "created_by": "bootstrap_sourcelab_source_packs.py",
        "created_at": now_iso(),
    }
    return json.dumps(payload, indent=2) + "\n"


def readme_md(pack: PackSeed) -> str:
    topics = "\n".join(f"- {topic}" for topic in pack.topics)
    lessons = "\n".join(f"- `{lesson}`" for lesson in pack.example_lessons)
    sources = "\n".join(f"- `{source.source_id}` — {source.title}" for source in pack.sources)

    return f"""# {pack.title}

## Purpose

{pack.description}

## Domain

`{pack.domain}`

## Topics

{topics}

## Example Lessons

{lessons}

## Starter Sources

{sources}

## Validation

From the SourceLab project root:

```bash
sourcelab source-pack doctor {pack.name}
sourcelab evals run --pack {pack.name}
sourcelab lesson create --topic "{pack.example_lessons[0]}" --source-pack {pack.name} --difficulty 2
```

## Notes

This pack was scaffolded from the user's recurring project and research themes. Replace or extend starter sources with stronger project notes, official docs, papers, or internal architecture records over time.
"""


def source_md(pack: PackSeed, source: SourceSeed, index: int = 0) -> str:
    claims = "\n".join(f"- {claim}" for claim in source.key_claims)
    use_cases = "\n".join(f"- {case}" for case in source.use_cases)
    trust_tier = source_trust_tier(index)
    extra = ""
    for heading, body in source.extra_sections:
        extra += f"\n## {heading}\n\n{body}\n"

    return f"""---
source_id: {source.source_id}
title: {source.title}
domain: {pack.domain}
trust_tier: {trust_tier}
version: 1.0
created_at: {now_iso()}
---

# {source.title}

## Summary

{source.summary}

## Key Claims

{claims}

## Use Cases

{use_cases}
{extra}
## Source Quality Note

This is a starter SourceLab seed document derived from recurring project context. Strengthen it by adding official references, project architecture notes, implementation evidence, experiment logs, or paper citations.
"""


def _topic_terms(topic: str, limit: int = 3) -> list[str]:
    words = [word for word in topic.lower().replace("-", " ").split() if len(word) > 2]
    return words[:limit] or [topic.lower()]


def retrieval_gold_json(pack: PackSeed) -> str:
    source_ids = [source.source_id for source in pack.sources]
    primary = source_ids[0]
    secondary = source_ids[1] if len(source_ids) > 1 else primary
    cases = [
        {
            "query": pack.example_lessons[0],
            "expected_source_ids": source_ids[:2],
            "expected_terms": _topic_terms(pack.example_lessons[0]),
            "min_hit_at_k": 1,
            "description": f"Retrieval query for {pack.example_lessons[0]}",
        },
        {
            "query": pack.topics[0],
            "expected_source_ids": [primary],
            "expected_terms": _topic_terms(pack.topics[0]),
            "min_hit_at_k": 1,
            "description": f"Retrieval query for {pack.topics[0]}",
        },
        {
            "query": pack.topics[1] if len(pack.topics) > 1 else pack.title,
            "expected_source_ids": [secondary],
            "expected_terms": _topic_terms(pack.topics[1] if len(pack.topics) > 1 else pack.title),
            "min_hit_at_k": 1,
            "description": "Secondary retrieval query for pack coverage",
        },
    ]
    return json.dumps(cases, indent=2) + "\n"


def claim_gold_json(pack: PackSeed) -> str:
    cases: list[dict[str, Any]] = []
    for source in pack.sources:
        for claim in source.key_claims[:2]:
            cases.append(
                {
                    "claim": claim.rstrip("."),
                    "expected_status": "supported",
                    "claim_type": "recommendation" if "should" in claim.lower() else "fact",
                    "severity": "medium" if "should" in claim.lower() else "low",
                    "description": f"Supported claim from {source.title}",
                }
            )
    cases.append(
        {
            "claim": (
                f"{pack.title} requires no validation and is always production safe without evidence."
            ),
            "expected_status": "unsupported",
            "claim_type": "recommendation",
            "severity": "high",
            "should_block": True,
            "description": "High-risk unsupported claim for starter pack guardrails",
        }
    )
    return json.dumps(cases, indent=2) + "\n"


def answer_gold_json(pack: PackSeed) -> str:
    primary = pack.sources[0]
    grounded_answer = (
        f"{primary.summary} Key practices include: "
        f"{'; '.join(claim.rstrip('.') for claim in primary.key_claims[:2])}."
    )
    cases = [
        {
            "answer": grounded_answer,
            "topic": pack.example_lessons[0],
            "expected_min_score": 0.5,
            "expected_max_score": 1.0,
            "expected_quality": "strong",
            "should_trigger_review": False,
            "description": "Source-grounded answer from pack seed content",
        },
        {
            "answer": (
                "This approach is guaranteed to always work in production without validation or review."
            ),
            "topic": pack.example_lessons[0],
            "expected_min_score": 0.0,
            "expected_max_score": 0.4,
            "expected_quality": "risky",
            "should_trigger_review": True,
            "description": "Risky unsupported answer for scoring guardrails",
        },
    ]
    return json.dumps(cases, indent=2) + "\n"


def lesson_gold_json(pack: PackSeed) -> str:
    source_ids = [source.source_id for source in pack.sources]
    cases = [
        {
            "topic": pack.example_lessons[0],
            "difficulty": 2,
            "task_format": "architecture_review",
            "required_source_ids": source_ids,
            "forbidden_claims": [
                "unsupported guarantee",
                "unverified production claim",
            ],
            "description": f"Lesson on {pack.example_lessons[0]}",
        },
        {
            "topic": pack.example_lessons[1] if len(pack.example_lessons) > 1 else pack.topics[0],
            "difficulty": 3,
            "task_format": "hands_on_lab",
            "required_source_ids": source_ids[:1],
            "forbidden_claims": ["production safe without validation"],
            "description": "Secondary lesson case for pack coverage",
        },
    ]
    return json.dumps(cases, indent=2) + "\n"


def gold_eval_content(pack: PackSeed, filename: str) -> str:
    generators = {
        "retrieval_gold.json": retrieval_gold_json,
        "claim_gold.json": claim_gold_json,
        "answer_gold.json": answer_gold_json,
        "lesson_gold.json": lesson_gold_json,
    }
    generator = generators.get(filename)
    if generator is None:
        raise ValueError(f"Unknown gold eval file: {filename}")
    return generator(pack)


def select_packs(selection: str) -> list[PackSeed]:
    if selection in GROUPS:
        return [PACKS[name] for name in GROUPS[selection]]
    names = [part.strip() for part in selection.split(",") if part.strip()]
    unknown = [name for name in names if name not in PACKS]
    if unknown:
        raise SystemExit(f"Unknown pack(s): {', '.join(unknown)}")
    return [PACKS[name] for name in names]


def run_command(command: list[str], cwd: Path) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return result.returncode, result.stdout
    except FileNotFoundError:
        return 127, f"Command not found: {command[0]}\n"


def scaffold_pack(root: Path, pack: PackSeed, force: bool, dry_run: bool) -> list[str]:
    results: list[str] = []
    base = root / "data" / "source_packs" / pack.name
    sources_dir = base / "sources"
    evals_dir = base / "evals"

    for directory in [base, sources_dir, evals_dir]:
        if dry_run:
            results.append(f"would_create_dir {directory}")
        else:
            directory.mkdir(parents=True, exist_ok=True)
            results.append(f"dir {directory}")

    files = {
        base / "pack.json": pack_json(pack),
        base / "manifest.json": manifest_json(pack),
        base / "README.md": readme_md(pack),
    }
    for gold_name in GOLD_EVAL_FILES:
        files[evals_dir / gold_name] = gold_eval_content(pack, gold_name)

    for index, source in enumerate(pack.sources):
        files[sources_dir / f"{source.source_id}.md"] = source_md(pack, source, index=index)

    for path, content in files.items():
        status = write_file(path, content, force=force, dry_run=dry_run)
        results.append(f"{status} {path.relative_to(root)}")

    return results


def discover_repairable_packs(root: Path) -> list[str]:
    packs_dir = root / "data" / "source_packs"
    if not packs_dir.is_dir():
        return []

    pack_names: list[str] = []
    for pack_dir in sorted(packs_dir.iterdir()):
        if not pack_dir.is_dir() or pack_dir.name in PROTECTED_PACKS:
            continue
        if (pack_dir / "pack.json").is_file():
            pack_names.append(pack_dir.name)
    return pack_names


def discover_legacy_eval_files(root: Path, *, include_builtins: bool = False) -> dict[str, list[str]]:
    """Find legacy eval JSON files grouped by pack. Never includes gold eval files."""
    packs_dir = root / "data" / "source_packs"
    if not packs_dir.is_dir():
        return {}

    grouped: dict[str, list[str]] = {}
    for pack_dir in sorted(packs_dir.iterdir()):
        if not pack_dir.is_dir():
            continue
        if pack_dir.name in PROTECTED_PACKS and not include_builtins:
            continue
        evals_dir = pack_dir / "evals"
        if not evals_dir.is_dir():
            continue
        legacy_files = [
            name
            for name in LEGACY_EVAL_FILE_NAMES
            if (evals_dir / name).is_file()
        ]
        if legacy_files:
            grouped[pack_dir.name] = legacy_files
    return grouped


def list_legacy_eval_files(root: Path, *, include_builtins: bool = False) -> None:
    """Print legacy eval files grouped by pack."""
    grouped = discover_legacy_eval_files(root, include_builtins=include_builtins)
    if not grouped:
        print("No legacy eval files found.")
        return

    for pack_name, files in grouped.items():
        print(f"{pack_name}:")
        for filename in files:
            print(f"  - evals/{filename}")


def delete_legacy_eval_files(
    root: Path,
    *,
    include_builtins: bool = False,
    dry_run: bool = False,
) -> list[str]:
    """Delete legacy eval files only. Gold eval files are never touched."""
    results: list[str] = []
    grouped = discover_legacy_eval_files(root, include_builtins=include_builtins)
    for pack_name, files in grouped.items():
        for filename in files:
            path = root / "data" / "source_packs" / pack_name / "evals" / filename
            if not path.is_file():
                continue
            if filename.endswith("_gold.json") or filename in GOLD_EVAL_FILES:
                results.append(f"skipped_gold {path.relative_to(root)}")
                continue
            if dry_run:
                results.append(f"would_delete {path.relative_to(root)}")
                continue
            path.unlink()
            results.append(f"deleted {path.relative_to(root)}")
    return results


def repair_pack_manifests(root: Path, pack_names: list[str], dry_run: bool) -> list[str]:
    results: list[str] = []
    for pack_name in pack_names:
        pack = PACKS.get(pack_name)
        if pack is None:
            results.append(f"skipped_unknown {pack_name}")
            continue

        base = root / "data" / "source_packs" / pack_name
        evals_dir = base / "evals"

        manifest_path = base / "manifest.json"
        status = write_file(manifest_path, manifest_json(pack), force=False, dry_run=dry_run)
        results.append(f"{status} {manifest_path.relative_to(root)}")

        for legacy_name, gold_name in LEGACY_EVAL_RENAMES.items():
            legacy_path = evals_dir / legacy_name
            gold_path = evals_dir / gold_name
            if gold_path.exists():
                continue
            if legacy_path.exists() and pack is not None:
                status = write_file(
                    gold_path,
                    gold_eval_content(pack, gold_name),
                    force=False,
                    dry_run=dry_run,
                )
                results.append(f"{status} {gold_path.relative_to(root)} (from legacy {legacy_name})")
                continue
            status = write_file(
                gold_path,
                gold_eval_content(pack, gold_name),
                force=False,
                dry_run=dry_run,
            )
            results.append(f"{status} {gold_path.relative_to(root)}")

    return results


def write_topic_backlog(root: Path, selected: list[PackSeed], force: bool, dry_run: bool) -> str:
    lines = [
        "# SourceLab Topic Backlog",
        "",
        "Generated by `scripts/bootstrap_sourcelab_source_packs.py`.",
        "",
        "## Packs",
        "",
    ]
    for pack in selected:
        lines.append(f"### `{pack.name}`")
        lines.append("")
        lines.append(pack.description)
        lines.append("")
        lines.append("Example lessons:")
        for lesson in pack.example_lessons:
            lines.append(f"- `{lesson}`")
        lines.append("")

    content = "\n".join(lines) + "\n"
    path = root / "docs" / "source_packs" / "TOPIC_BACKLOG.md"
    return f"{write_file(path, content, force=force, dry_run=dry_run)} {path.relative_to(root)}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap SourceLab source packs from recurring topic backlog.")
    parser.add_argument(
        "--packs",
        default="core",
        help="Pack group or comma-separated packs. Groups: core, research, business, watchlist, all. Default: core",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes without writing files.")
    parser.add_argument("--validate", action="store_true", help="Run `sourcelab source-pack doctor <pack>` after writing.")
    parser.add_argument("--run-evals", action="store_true", help="Run `sourcelab evals run --pack <pack>` after writing.")
    parser.add_argument("--skip-topic-backlog", action="store_true", help="Do not write docs/source_packs/TOPIC_BACKLOG.md.")
    parser.add_argument(
        "--repair-manifests",
        action="store_true",
        help="Repair bootstrapped packs: write manifest.json and gold eval files without touching source markdown bodies.",
    )
    parser.add_argument(
        "--list-legacy-evals",
        action="store_true",
        help="Print legacy retrieval_eval.json, lesson_eval.json, and answer_eval.json grouped by pack.",
    )
    parser.add_argument(
        "--delete-legacy-evals",
        action="store_true",
        help="Delete legacy eval files only (never gold files). Skips pqc_v1/ai_safety_v1 unless --include-builtins.",
    )
    parser.add_argument(
        "--include-builtins",
        action="store_true",
        help="Include pqc_v1 and ai_safety_v1 when listing or deleting legacy eval files.",
    )
    args = parser.parse_args()

    root = find_project_root(Path.cwd())

    if args.list_legacy_evals:
        list_legacy_eval_files(root, include_builtins=args.include_builtins)
        return 0

    if args.delete_legacy_evals:
        print(f"SourceLab root: {root}")
        for result in delete_legacy_eval_files(
            root,
            include_builtins=args.include_builtins,
            dry_run=args.dry_run,
        ):
            print(result)
        if not args.dry_run:
            print("\nLegacy eval cleanup complete.")
        else:
            print("\nDry run complete. No files were deleted.")
        return 0

    if args.repair_manifests:
        repair_names = discover_repairable_packs(root)
        print(f"SourceLab root: {root}")
        print(f"Repairing manifests for: {', '.join(repair_names) or '(none)'}")
        report_lines = [
            "# SourceLab Source Pack Manifest Repair Report",
            "",
            f"- Generated at: `{now_iso()}`",
            f"- Project root: `{root}`",
            f"- Dry run: `{args.dry_run}`",
            "",
        ]
        for result in repair_pack_manifests(root, repair_names, dry_run=args.dry_run):
            print(result)
            report_lines.append(f"- {result}")
        if not args.dry_run:
            report_path = root / "artifacts" / "source_pack_bootstrap_report.md"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
            print(f"\nReport written: {report_path}")
        return 0

    selected = select_packs(args.packs)

    report_lines = [
        "# SourceLab Source Pack Bootstrap Report",
        "",
        f"- Generated at: `{now_iso()}`",
        f"- Project root: `{root}`",
        f"- Selection: `{args.packs}`",
        f"- Dry run: `{args.dry_run}`",
        f"- Force overwrite: `{args.force}`",
        "",
    ]

    print(f"SourceLab root: {root}")
    print(f"Selected packs: {', '.join(pack.name for pack in selected)}")

    for pack in selected:
        print(f"\n==> Scaffolding {pack.name}")
        report_lines.append(f"## {pack.name}")
        report_lines.append("")
        for result in scaffold_pack(root, pack, force=args.force, dry_run=args.dry_run):
            print(result)
            report_lines.append(f"- {result}")
        report_lines.append("")

    if not args.skip_topic_backlog:
        print("\n==> Writing topic backlog")
        result = write_topic_backlog(root, selected, force=args.force, dry_run=args.dry_run)
        print(result)
        report_lines.append("## Topic Backlog")
        report_lines.append("")
        report_lines.append(f"- {result}")
        report_lines.append("")

    if args.validate and not args.dry_run:
        report_lines.append("## Validation")
        report_lines.append("")
        for pack in selected:
            command = ["sourcelab", "source-pack", "doctor", pack.name]
            print(f"\n==> Running: {' '.join(command)}")
            code, output = run_command(command, root)
            print(output)
            report_lines.append(f"### {' '.join(command)}")
            report_lines.append("")
            report_lines.append(f"Exit code: `{code}`")
            report_lines.append("")
            report_lines.append("```text")
            report_lines.append(output.strip())
            report_lines.append("```")
            report_lines.append("")
            if code != 0:
                print(f"WARNING: validation failed for {pack.name}", file=sys.stderr)

    if args.run_evals and not args.dry_run:
        report_lines.append("## Evals")
        report_lines.append("")
        for pack in selected:
            command = ["sourcelab", "evals", "run", "--pack", pack.name]
            print(f"\n==> Running: {' '.join(command)}")
            code, output = run_command(command, root)
            print(output)
            report_lines.append(f"### {' '.join(command)}")
            report_lines.append("")
            report_lines.append(f"Exit code: `{code}`")
            report_lines.append("")
            report_lines.append("```text")
            report_lines.append(output.strip())
            report_lines.append("```")
            report_lines.append("")
            if code != 0:
                print(f"WARNING: evals failed for {pack.name}", file=sys.stderr)

    if not args.dry_run:
        report_path = root / "artifacts" / "source_pack_bootstrap_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
        print(f"\nReport written: {report_path}")
    else:
        print("\nDry run complete. No files were written.")

    print("\nNext recommended commands:")
    print("  sourcelab source-pack doctor <pack_name>")
    print("  sourcelab evals run --pack <pack_name>")
    print('  sourcelab lesson create --topic "<topic>" --source-pack <pack_name> --difficulty 2')

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
