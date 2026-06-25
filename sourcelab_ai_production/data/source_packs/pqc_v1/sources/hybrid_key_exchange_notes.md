---
source_id: hybrid_key_exchange_notes
title: Hybrid Key Exchange Patterns for PQC Transition
publisher: SourceLab (local guidance)
source_type: technical_notes
trust_tier: B
approval_status: approved
status: active
retrieved_at: 2026-01-15T00:00:00Z
last_checked_at: 2026-06-20T00:00:00Z
---

# Hybrid Key Exchange Patterns for PQC Transition

## What is Hybrid Key Exchange?

Hybrid key exchange combines classical (e.g., ECDH) and post-quantum (e.g., ML-KEM) algorithms to provide security against both classical and quantum attacks.

## Why Hybrid?

1. **Transitional Security**: Protects against "harvest now, decrypt later" attacks
2. **Fallback Safety**: If PQC algorithm has weakness, classical algorithm provides backup
3. **Interoperability**: Works with existing infrastructure during transition
4. **Confidence Building**: Allows gradual deployment with real-world testing

## Implementation Patterns

### Pattern 1: Concatenation

Combine shared secrets from both algorithms:

```
hybrid_secret = classical_secret || pqc_secret
```

- Simple to implement
- Security relies on both algorithms
- Used in TLS 1.3 hybrid key exchange drafts

### Pattern 2: KDF Derivation

Use a key derivation function to combine secrets:

```
hybrid_secret = KDF(classical_secret, pqc_secret, context)
```

- More flexible than concatenation
- Can adjust output length
- Better for different security levels

### Pattern 3: Nested Encryption

Encrypt with classical, then PQC:

```
encrypted = PQ_Encrypt(Classical_Encrypt(message))
```

- Highest security assurance
- Performance overhead
- Used in high-security applications

## Protocol Considerations

### TLS Integration

- Hybrid key exchange in TLS 1.3
- Requires client and server support
- Negotiation via supported_groups extension
- Backward compatibility with classical-only clients

### SSH Integration

- Hybrid key exchange in SSH
- Custom algorithm negotiation
- Backward compatibility challenges

## Performance Impact

| Operation | Classical | Hybrid | Overhead |
|-----------|-----------|--------|----------|
| Key Generation | 1ms | 2ms | +100% |
| Key Exchange | 0.5ms | 1ms | +100% |
| Bandwidth | 32 bytes | 1200 bytes | +37x |

## Recommendations

1. Start with hybrid for new deployments
2. Prioritize high-value, long-lived connections
3. Test thoroughly in staging environments
4. Monitor performance and adjust as needed
