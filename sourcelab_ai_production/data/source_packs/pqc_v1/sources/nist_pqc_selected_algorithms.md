---
source_id: nist_pqc_selected_algorithms
title: NIST PQC Selected Algorithm Families
publisher: NIST (local summary)
source_type: standard_summary
trust_tier: A
approval_status: approved
status: active
retrieved_at: 2026-01-15T00:00:00Z
last_checked_at: 2026-06-20T00:00:00Z
---

# NIST PQC Selected Algorithm Families

## ML-KEM (Module-Lattice-Based Key Encapsulation)

Formerly known as CRYSTALS-Kyber. Selected for key encapsulation/distribution.

- Security based on Module Learning With Errors (MLWE) problem
- Key sizes: 800-1568 bytes depending on security level
- Ciphertext sizes: 768-1568 bytes
- Performance: Comparable to RSA for key generation, faster for encapsulation/decapsulation

### Security Levels

- ML-KEM-512: NIST Security Level 1 (equivalent to AES-128)
- ML-KEM-768: NIST Security Level 3 (equivalent to AES-192)
- ML-KEM-1024: NIST Security Level 5 (equivalent to AES-256)

## ML-DSA (Module-Lattice-Based Digital Signature)

Formerly known as CRYSTALS-Dilithium. Selected for digital signatures.

- Security based on Module LWE and Module SIS problems
- Signature sizes: 2420-4595 bytes
- Public key sizes: 1312-2592 bytes
- Primary signature scheme for most applications

## SLH-DSA (Stateless Hash-Based Digital Signature)

Formerly known as SPHINCS+. Selected as a backup signature scheme.

- Security based on hash function properties
- Conservative security assumptions
- Larger signatures but minimal security assumptions
- Useful for applications requiring long-term security

## Comparison

| Algorithm | Type | Key Size | Signature Size | Performance |
|-----------|------|----------|----------------|-------------|
| ML-KEM | KEM | 800-1568 B | N/A | Fast |
| ML-DSA | Signature | 1312-2592 B | 2420-4595 B | Moderate |
| SLH-DSA | Signature | 32-64 B | 7857-49856 B | Slow |
