# NIST PQC Migration Notes

Post-quantum cryptography migration begins with a cryptographic inventory. Teams should identify where public-key cryptography is used, including key exchange, digital signatures, certificates, long-lived encrypted data, and software dependencies.

A practical migration plan should separate immediate operational risk from long-term confidentiality risk. Current public guidance should not be summarized as proof that today's quantum computers can break RSA-2048.

For educational planning, a safe first action is to create an inventory, classify data sensitivity, identify systems with long-term confidentiality requirements, and track standards-based migration options.
