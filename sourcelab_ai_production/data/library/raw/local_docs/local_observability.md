# Observability

Every run should log:

- run_id
- user/workspace
- topic
- sources retrieved
- model backend
- prompt version
- generated artifacts
- claim verification result
- answer score
- next task decision
- latency
- errors

Production tools may include:

- OpenTelemetry
- Sentry
- Prometheus/Grafana
- Langfuse/Phoenix-style LLM tracing
