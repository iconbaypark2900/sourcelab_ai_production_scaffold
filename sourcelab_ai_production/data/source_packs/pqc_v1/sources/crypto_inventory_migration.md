---
source_id: crypto_inventory_migration
title: Cryptographic Inventory and Migration Planning
publisher: SourceLab (local guidance)
source_type: migration_guide
trust_tier: B
approval_status: approved
status: active
retrieved_at: 2026-01-15T00:00:00Z
last_checked_at: 2026-06-20T00:00:00Z
---

# Cryptographic Inventory and Migration Planning

## Why Inventory Matters

Organizations cannot migrate what they don't know they have. A cryptographic inventory identifies all locations where cryptography is used, enabling informed migration decisions.

## Inventory Scope

### What to Inventory

1. **Algorithms**: RSA, ECC, AES, 3DES, SHA-1, SHA-2, etc.
2. **Key Types**: Signing keys, encryption keys, key exchange keys
3. **Protocols**: TLS, SSH, VPN, S/MIME, code signing
4. **Libraries**: OpenSSL, BoringSSL, AWS KMS, Azure Key Vault
5. **Applications**: Web servers, databases, APIs, mobile apps
6. **Hardware**: HSMs, TPMs, smart cards

### Inventory Attributes

For each cryptographic usage, record:
- Algorithm and key size
- Purpose (encryption, signing, key exchange)
- Data sensitivity classification
- Certificate/key expiration
- Dependencies and affected systems
- Owner and contact information

## Migration Strategy

### Phase 1: Discovery (Months 1-3)

1. Deploy discovery tools across infrastructure
2. Scan source code for cryptographic APIs
3. Review certificate inventories
4. Interview application owners
5. Document findings in centralized database

### Phase 2: Assessment (Months 3-6)

1. Classify data by sensitivity and retention requirements
2. Identify quantum-vulnerable algorithms
3. Prioritize based on risk (long-lived data first)
4. Estimate migration effort and cost

### Phase 3: Planning (Months 6-9)

1. Select PQC algorithms for each use case
2. Design hybrid implementation approach
3. Create testing and validation plans
4. Establish rollback procedures

### Phase 4: Execution (Months 9-24)

1. Begin with low-risk systems
2. Implement hybrid cryptography
3. Test thoroughly before production
4. Monitor and adjust as needed

## Common Challenges

- Legacy systems with hard-coded algorithms
- Third-party dependencies with unknown cryptographic usage
- Regulatory compliance requirements
- Performance implications of larger key sizes
- Interoperability with external partners
