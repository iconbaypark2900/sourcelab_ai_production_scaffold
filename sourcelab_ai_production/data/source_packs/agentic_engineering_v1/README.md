# Agentic Engineering and Multi-Agent Software Workflows

## Purpose

Source pack for local-first multi-agent engineering, coding agents, QA, DevOps, compliance, and human-in-the-loop orchestration.

## Domain

`agentic_engineering`

## Topics

- multi-agent software engineering
- coding agents
- human-in-the-loop orchestration
- agent QA
- DevOps automation
- compliance gates
- release validation

## Example Lessons

- `multi-agent software engineering control plane`
- `agent QA workflow`
- `human-in-the-loop release gates`
- `independent coding agent orchestration`

## Starter Sources

- `agentic_engineering_liaison_architecture_001` — Local-First Multi-Agent Engineering Architecture
- `agentic_engineering_quality_gates_002` — Evidence-Based Quality Gates

## Validation

From the SourceLab project root:

```bash
sourcelab source-pack doctor agentic_engineering_v1
sourcelab evals run --pack agentic_engineering_v1
sourcelab lesson create --topic "multi-agent software engineering control plane" --source-pack agentic_engineering_v1 --difficulty 2
```

## Notes

This pack was scaffolded from the user's recurring project and research themes. Replace or extend starter sources with stronger project notes, official docs, papers, or internal architecture records over time.
