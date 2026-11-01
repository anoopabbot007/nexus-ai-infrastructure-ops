# MCP architecture

The observability boundary is a separate Python MCP server using the Streamable HTTP transport at `http://mcp-server:8001/mcp` inside Compose. The agent service runs an MCP client session for each investigation.

## Tool discovery and call sequence

1. The client connects and calls `tools/list`.
2. It records the advertised tool names, descriptions and input schemas, then checks that all required tools are present.
3. It selects three Prometheus metrics based on the alert scenario and calls the logs, service-health and resource-usage tools.
4. Tool results are mapped to timestamped evidence IDs and returned in the same `IncidentState` used by the RCA and recommendation agents.
5. The client records per-call status, elapsed milliseconds, row count and error. The API report persists the catalog, trace and full tool responses.

## Read-only tools

| Tool | Main inputs | Implementation |
|---|---|---|
| `query_prometheus_metrics` | service, environment, allowlisted metric, ISO start/end, step | Prometheus `/api/v1/query_range` |
| `query_application_logs` | service, environment, ISO start/end, optional severity/keyword, bounded limit | Loki `/loki/api/v1/query_range` |
| `get_service_health` | service, environment | Instant Prometheus queries for CPU, memory, errors and p95 latency |
| `get_resource_usage` | service, environment, ISO start/end, step | CPU/memory ranges with min/max/average |

Prometheus metric names and Loki search terms are fixed allowlists. Service and environment values use a strict label pattern. Query windows require timezone-aware ISO-8601 timestamps and cannot exceed 24 hours. Step is bounded from 5 to 300 seconds. The tool service never executes writes or accepts arbitrary PromQL/LogQL.

## Error semantics

Telemetry mode defaults to `real`; missing credentials are irrelevant to the telemetry APIs. HTTP failures, source unavailability, invalid API responses and timeouts become explicit tool errors. Successful queries with no matching data remain distinguishable from an unreachable source, and an investigation with no usable metrics or logs fails instead of silently inserting fixtures. `TELEMETRY_MODE=mock` explicitly enables fixture-backed tool responses for local repeatability.

## Security boundary

The Compose MCP server is bound to loopback on host port 8001 and uses the internal Compose network. The HTTP data sources are read-only Prometheus/Loki APIs. Do not point them at production until authentication, TLS, network policies, tenant isolation, query budgets and data-retention rules have been designed and reviewed.
