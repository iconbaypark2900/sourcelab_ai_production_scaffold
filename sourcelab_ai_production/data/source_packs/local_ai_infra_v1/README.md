# Local AI Infrastructure and Model Routing

## Purpose

Source pack for DGX/EVO local AI infrastructure, inference servers, model routing, gateways, and local-first AI development.

## Domain

`local_ai_infra`

## Topics

- DGX Spark
- EVO-X2
- Ollama
- vLLM
- SGLang
- TensorRT-LLM
- LiteLLM
- local model routing
- OpenAI-compatible endpoints

## Example Lessons

- `local AI inference stack design`
- `DGX Spark model routing`
- `LiteLLM gateway for coding agents`
- `local model fallback architecture`

## Starter Sources

- `local_ai_infra_routing_001` — Local Model Routing Architecture
- `local_ai_infra_observability_002` — Local AI Observability

## Validation

From the SourceLab project root:

```bash
sourcelab source-pack doctor local_ai_infra_v1
sourcelab evals run --pack local_ai_infra_v1
sourcelab lesson create --topic "local AI inference stack design" --source-pack local_ai_infra_v1 --difficulty 2
```

## Notes

This pack was scaffolded from the user's recurring project and research themes. Replace or extend starter sources with stronger project notes, official docs, papers, or internal architecture records over time.
