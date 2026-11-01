# Agent workflow

LangGraph `StateGraph` carries one centralized `IncidentState` through four specialist agents. It contains the alert, scenario, metrics, logs, findings, RCA, recommendations, telemetry mode/window/evidence, MCP catalog and tool trace, errors and agent execution trace.

```text
START → alert_analysis → investigation → root_cause_analysis → recommendation → report → END
              └──────────── any node failure → record FAILED and route to END
```

Each node adds its state updates and an execution-trace entry. The conditional edge checks `execution_status`: continue to the next node unless a prior node set `FAILED`. The report node is reached only after all four agents complete. The Investigation Agent retries one failed MCP collection once; if it still fails, the graph records an error and stops before RCA and recommendations.

## Agents

1. **Alert Analysis Agent** normalizes service, severity, scenario and investigation parameters.
2. **Investigation Agent** discovers MCP tools and queries scenario-selected Prometheus series, Loki logs, service health and CPU/memory resource history. It returns actual evidence rows plus raw MCP responses and per-call trace. `TELEMETRY_MODE=real` is the default; `mock` fixture telemetry must be selected explicitly.
3. **Root Cause Analysis Agent** uses the alert and returned evidence. It rejects citations not present in tool results, requires metric and log citations, checks findings and scenario indicators, and computes the legacy confidence field as evidence coverage. The check is intentionally lexical and is not a causal proof.
4. **Remediation Recommendation Agent** reads the RCA and supporting observations, then returns advisory actions with impact, risk and verification steps. It never executes a change.

The Python HTTP request timeout and Spring agent-client timeout bound the synchronous workflow. A live telemetry outage, unsupported metric, empty Prometheus result, or unmatched Loki logs fails clearly; there is no hidden fixture fallback.

## MCP tools

| MCP tool | Source | Result |
|---|---|---|
| `query_prometheus_metrics` | Prometheus range API | Allowlisted metric, timestamped samples and evidence IDs |
| `query_application_logs` | Loki range API | Bounded structured logs and evidence IDs |
| `get_service_health` | Prometheus instant API | Latest health indicators, missing metrics and status |
| `get_resource_usage` | Prometheus range API | CPU/memory samples and min/max/average |

The MCP server is a separate Streamable HTTP process at `/mcp`. The client first invokes `tools/list`, checks the four required names, and records each call's duration, count and status. PromQL metric identifiers and Loki severity/search values are allowlisted; service/environment labels and time bounds are validated.

## Five demo scenarios

The demo app emits actual local process metrics and structured logs. Thread and memory workloads are measured; pool contention, database latency and dependency failure are bounded synthetic scenarios. These are not measurements of an external production service.

| Scenario | Demo endpoint | Evidence examples |
|---|---|---|
| Threads | `/demo/scenarios/threads` | measured CPU, active threads, HTTP latency, queue/thread logs |
| Memory | `/demo/scenarios/memory` | allocation budget, GC duration and memory/GC logs |
| Pool | `/demo/scenarios/pool` | semaphore pool use/waiters and connection timeout logs |
| Database latency | `/demo/scenarios/database_latency` | controlled latency histogram and database delay logs |
| Dependency | `/demo/scenarios/dependency` | 503 error counter, downstream duration and circuit-breaker logs |

See [MCP architecture](mcp-architecture.md), [Prometheus integration](prometheus-integration.md), [Loki integration](loki-integration.md), and [Phase 2 setup](phase-2-setup.md) for run details.
