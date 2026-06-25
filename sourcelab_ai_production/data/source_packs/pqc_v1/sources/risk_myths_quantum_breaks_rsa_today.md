---
source_id: risk_myths_quantum_breaks_rsa_today
title: Quantum Computing Risk Assessment and Common Myths
publisher: SourceLab (local analysis)
source_type: risk_analysis
trust_tier: C
approval_status: approved
status: active
retrieved_at: 2026-01-15T00:00:00Z
last_checked_at: 2026-06-20T00:00:00Z
---

# Quantum Computing Risk Assessment and Common Myths

## Current State of Quantum Computing (2026)

### What Quantum Computers Can Do

- Demonstrate quantum advantage for specific problems
- Run small-scale quantum algorithms
- Perform research and experimentation
- Show progress toward fault tolerance

### What Quantum Computers Cannot Do Yet

- Break RSA-2048 or other widely-used public key algorithms
- Perform cryptographically relevant attacks at scale
- Replace classical computers for general computing
- Run Shor's algorithm on practical problem sizes

## Common Myths

### Myth 1: "Quantum computers can break RSA-2048 today"

**Reality**: Current quantum computers have approximately 1000-2000 noisy qubits. Breaking RSA-2048 would require approximately 4000 logical qubits (millions of physical qubits with error correction). This is decades away from current capabilities.

### Myth 2: "All cryptography will be broken by quantum computers"

**Reality**: Symmetric algorithms (AES) and hash functions (SHA-256) are believed to be quantum-resistant. Only public key cryptography (RSA, ECC, DH) is vulnerable to Shor's algorithm.

### Myth 3: "PQC migration can wait until quantum computers arrive"

**Reality**: "Harvest now, decrypt later" attacks mean encrypted data captured today could be decrypted in the future. Migration should begin now for long-lived sensitive data.

### Myth 4: "PQC algorithms are untested and risky"

**Reality**: NIST PQC algorithms have undergone years of public scrutiny, cryptanalysis, and standardization. They are more thoroughly vetted than many classical algorithms were at deployment.

### Myth 5: "PQC will destroy performance"

**Reality**: While PQC algorithms have larger key/signature sizes, performance is comparable to classical algorithms for most applications. Hybrid approaches add overhead but are manageable.

## Risk Assessment

### High Risk (Act Now)

- Long-lived sensitive data (medical, financial, government)
- Data with extended confidentiality requirements
- Systems with long deployment lifecycles

### Medium Risk (Plan Now)

- General web traffic (TLS)
- Code signing certificates
- Software updates and firmware

### Low Risk (Monitor)

- Short-lived session keys
- Symmetric encryption (AES)
- Hash-based operations

## Recommendations

1. **Start with inventory**: Know what cryptography you use
2. **Prioritize by data lifetime**: Long-lived data first
3. **Consider hybrid approaches**: Balance security and compatibility
4. **Monitor standards**: NIST algorithms are still evolving
5. **Test before deploying**: Validate PQC in non-production environments
