# Strong Answer: Post-Quantum Cryptography Migration

## Step 1: Cryptographic Inventory

The first critical step is conducting a comprehensive cryptographic inventory. This involves cataloging all systems that use public-key cryptography, including TLS endpoints, VPN concentrators, code signing infrastructure, and certificate authorities. The inventory should capture algorithm usage, key sizes, and protocol versions.

## Step 2: Risk Assessment

Separate immediate operational risk from long-term confidentiality risk. RSA-2048 and ECDH are vulnerable to "harvest now, decrypt later" attacks where adversaries collect encrypted traffic today to decrypt with future quantum computers. This is a risk_statement that requires careful assessment.

## Step 3: Migration Strategy

Based on NIST SP 800-208 guidance, prioritize migrating to CRYSTALS-Kyber for key encapsulation and CRYSTALS-Dilithium for digital signatures. The migration should follow a phased approach: inventory, assess, plan, pilot, and rollout.

## Important Caveats

- Current quantum computers cannot break RSA-2048 today (this is an assumption, not a fact)
- The timeline for cryptographically relevant quantum computers remains uncertain
- Organizations should avoid claiming specific timelines without evidence

## Source References

- NIST PQC Migration Guide (nist_pqc_notes)
- Post-quantum cryptography standards (nist_pqc_notes)

## Uncertainty Labels

I am uncertain about the exact timeline for quantum threats. The risk is real but the timeline is speculative. Organizations should plan for migration without making claims about when quantum computers will break current encryption.
