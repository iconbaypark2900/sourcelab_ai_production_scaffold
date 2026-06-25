# Cloud Security, CSPM, and Cloud-Native Defense

## Purpose

Source pack for cloud security posture management, Kubernetes security, zero trust, supply chain security, and cloud-native defense workflows.

## Domain

`cloud_security`

## Topics

- cloud security posture management
- CSPM
- Kubernetes security
- zero trust
- supply chain security
- container security
- IAM hardening
- cloud-native defense
- SBOM

## Example Lessons

- `cloud security posture management review`
- `Kubernetes security hardening workflow`
- `zero trust architecture review`
- `software supply chain security gates`

## Starter Sources

- `cloud_security_posture_001` — Cloud Security Posture Management Workflow
- `cloud_security_supply_chain_002` — Supply Chain and Cloud-Native Runtime Defense

## Validation

From the SourceLab project root:

```bash
sourcelab source-pack doctor cloud_security_v1
sourcelab evals run --pack cloud_security_v1
sourcelab lesson create --topic "cloud security posture management review" --source-pack cloud_security_v1 --difficulty 2
```

## Notes

This pack was scaffolded from the user's recurring project and research themes. Replace or extend starter sources with stronger project notes, official docs, papers, or internal architecture records over time.
