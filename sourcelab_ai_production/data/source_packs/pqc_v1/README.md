# PQC Source Pack v1

## Overview

This source pack provides curated content for post-quantum cryptography (PQC) migration and quantum cybersecurity topics. It is designed for testing and validating SourceLab's retrieval, generation, verification, and scoring capabilities.

## Contents

### Sources

1. **nist_pqc_overview.md** - NIST Post-Quantum Cryptography standardization overview
2. **nist_pqc_selected_algorithms.md** - Selected algorithm families (ML-KEM, ML-DSA, SLH-DSA)
3. **crypto_inventory_migration.md** - Cryptographic inventory and migration planning
4. **hybrid_key_exchange_notes.md** - Hybrid key exchange patterns for transition
5. **crypto_agility_notes.md** - Crypto agility concepts and implementation
6. **oqs_implementation_notes.md** - Open Quantum Safe implementation considerations
7. **risk_myths_quantum_breaks_rsa_today.md** - Common myths and risk assessment

### Golden Evals

- **retrieval_gold.json** - 10 retrieval test cases
- **claim_gold.json** - 15 claim verification test cases
- **answer_gold.json** - 15 answer scoring test cases
- **lesson_gold.json** - 5 lesson generation test cases

## Trust Tiers

- Tier A: NIST-related content
- Tier B: Implementation guidance
- Tier C: General educational content

## Usage

```bash
sourcelab source-pack list
sourcelab source-pack validate pqc_v1
sourcelab source-pack install pqc_v1
sourcelab evals run --pack pqc_v1
```
