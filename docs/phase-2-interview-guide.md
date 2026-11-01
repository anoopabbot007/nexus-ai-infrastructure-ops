# Phase 2 interview guide

## Short explanation

NEXUS AI accepts an incident through a React dashboard and Spring Boot API, persists it in PostgreSQL, and sends it to a Python LangGraph workflow. The Investigation Agent discovers and calls read-only observability tools through MCP Streamable HTTP. The MCP server uses allowlisted Prometheus and Loki queries. A local demo app exports metrics and structured logs, while Grafana Alloy ships logs to Loki. The report returns the evidence, tool trace and RCA, and is persisted for review.

## Points to explain

- LangGraph routes one centralized incident state through alert analysis, investigation, RCA and recommendations; a node failure conditionally ends the graph.
- MCP provides service discovery, structured tool arguments and a separate integration boundary. The report captures tool schemas, durations, statuses and counts.
- Telemetry mode and LLM provider are separate. The shipped default calls real local Prometheus/Loki APIs while using deterministic mock LLM responses.
- Empty telemetry and source failures are explicit errors. Real mode does not fall back to fixtures.
- Evidence IDs are generated from actual telemetry records and checked at RCA time. Lexical checks are conservative validation, not proof of causation.
- Recommendations are advisory; no infrastructure write operation exists.

## Be precise about the demo

The demo telemetry app is not a production integration. It performs bounded thread and memory workloads and emits synthetic pool, database-latency and dependency scenarios. Production use would require safe exporter and Alloy deployment, secure backend access, tenant isolation, redaction, authn/authz, query budgets, and an operator approval model. Those are outside Phase 2.
