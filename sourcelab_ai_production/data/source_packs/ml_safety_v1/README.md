# Machine Learning Safety, Alignment, and Robustness

## Purpose

Source pack for ML safety, alignment, robustness, evaluation, red-teaming, monitoring, and responsible deployment guardrails.

## Domain

`ml_safety`

## Topics

- ML safety
- alignment
- robustness
- adversarial robustness
- red-teaming
- evaluation harness
- model monitoring
- responsible deployment
- safety evals

## Example Lessons

- `ML safety evaluation harness design`
- `adversarial robustness review workflow`
- `red-team triage and remediation`
- `responsible deployment guardrails`

## Starter Sources

- `ml_safety_evaluation_001` — ML Safety Evaluation and Red-Teaming
- `ml_safety_alignment_002` — Alignment and Monitoring Guardrails

## Validation

From the SourceLab project root:

```bash
sourcelab source-pack doctor ml_safety_v1
sourcelab evals run --pack ml_safety_v1
sourcelab lesson create --topic "ML safety evaluation harness design" --source-pack ml_safety_v1 --difficulty 2
```

## Notes

This pack was scaffolded from the user's recurring project and research themes. Replace or extend starter sources with stronger project notes, official docs, papers, or internal architecture records over time.
