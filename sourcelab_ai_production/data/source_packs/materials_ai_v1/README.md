# Materials AI and Quantum Chemistry Workflows

## Purpose

Source pack for materials discovery, quantum chemistry, CUDA-Q/VQE-style methods, surrogate models, and generative materials workflows.

## Domain

`materials_ai`

## Topics

- materials discovery
- quantum chemistry
- CUDA-Q
- VQE
- ADAPT-VQE
- surrogate modeling
- MatterGen-style workflows

## Example Lessons

- `materials discovery with quantum AI`
- `ADAPT-VQE materials workflow`
- `surrogate model for materials screening`
- `quantum chemistry evidence workflow`

## Starter Sources

- `materials_ai_screening_001` — Materials Discovery Screening Pipeline
- `materials_ai_quantum_methods_002` — Quantum Methods for Materials Workflows

## Validation

From the SourceLab project root:

```bash
sourcelab source-pack doctor materials_ai_v1
sourcelab evals run --pack materials_ai_v1
sourcelab lesson create --topic "materials discovery with quantum AI" --source-pack materials_ai_v1 --difficulty 2
```

## Notes

This pack was scaffolded from the user's recurring project and research themes. Replace or extend starter sources with stronger project notes, official docs, papers, or internal architecture records over time.
