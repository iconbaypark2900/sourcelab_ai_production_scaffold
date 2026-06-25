# Threat Model

## Assets

- Approved source library
- User answers
- Skill profile
- Proof bundles
- Model traces
- Generated lessons
- Verification reports
- Human review queues

## Threats

| Threat | Mitigation |
|---|---|
| Prompt injection in source text | Treat source text as data, not instructions |
| Unsupported claims | Claim verifier + harness gate + verification v2 |
| Stale sources | Freshness metadata and review queue |
| Weak sources | Trust-tier weighting and warnings |
| Cross-user data leak | Workspace isolation |
| Hallucinated answer keys | No-source/no-claim policy |
| Hidden model failure | Proof bundle and trace logs |
| Contradictory claims | Conflict detector + human review |
| Low citation resolution | Citation resolution gate |
| High-risk unsupported claims | Release gate blocks on high-risk unsupported |

## High-risk topic policy

For cybersecurity, medicine, law, finance, and safety-critical engineering:

- Label output educational.
- Require expert review for operational decisions.
- Fail closed on unsupported high-risk claims.
- Block release if citation resolution rate < 80%.
- Flag contradictions for human review.

## Verification v2 security

Verification v2 adds:
- Atomic claim extraction with severity assessment
- Evidence matching with trust tier weighting
- Citation resolution rate calculation
- Conflict detection for contradictions
- Human review queue for uncertain items
- Release gate with citation and high-risk checks
