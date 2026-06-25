# AI Safety Source Pack v1

## Overview

Curated local summaries for AI safety topics: risk taxonomy, grounding and hallucination control, red-team testing, model evaluation benchmarks, and governance practices.

## Contents

### Sources

1. **ai_risk_taxonomy.md** - Categories of AI risk (capability, misuse, alignment, systemic)
2. **evals_and_benchmarks.md** - Model evaluation benchmarks and limitations
3. **model_governance_notes.md** - Governance controls for model deployment
4. **hallucination_and_grounding.md** - Grounding strategies and hallucination mitigation
5. **red_team_testing_notes.md** - Red-team testing methodology for LLM systems

### Golden Evals

- **retrieval_gold.json** - Retrieval test cases
- **claim_gold.json** - Claim verification test cases
- **answer_gold.json** - Answer scoring test cases
- **lesson_gold.json** - Lesson generation test cases

## Usage

```bash
sourcelab source-pack doctor ai_safety_v1
sourcelab source-pack install ai_safety_v1
sourcelab evals run --pack ai_safety_v1
```
