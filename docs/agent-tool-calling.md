# Agent tool calling

The Investigation Agent is the LangGraph node that calls external telemetry tools. It passes the normalized alert's service, environment and scenario to `collect_via_mcp`. The client opens a Streamable HTTP session, discovers the server catalog, then invokes named tools with structured arguments.

For a thread alert, the client requests `cpu_utilization`, `http_response_latency` and `thread_activity`, plus logs matching the allowlisted `thread` keyword, health, and CPU/memory resource history. Other scenarios select metric/log pairs listed in [Agent workflow](agent-workflow.md).

Representative MCP arguments:

```json
{
  "service_name": "payment-service",
  "environment": "production",
  "metric_name": "cpu_utilization",
  "start_time": "2026-11-01T10:00:00+00:00",
  "end_time": "2026-11-01T10:15:00+00:00",
  "step": "30s",
  "scenario": "threads"
}
```

A successful result contains `available`, `dataAvailable`, the safe query description, timestamped records, evidence IDs and a count. An unreachable source is an explicit error. A reachable source with no samples is reported as empty and prevents an unsupported RCA. The Investigation Agent retries collection once after an exception, then LangGraph records a failed step and stops routing.

The collected data becomes `IncidentState.infrastructure_metrics`, `application_logs`, `investigation_findings`, `telemetry_evidence`, `mcp_tool_trace` and `mcp_tool_catalog`. RCA reads those exact metrics/logs and checks its IDs against them. Recommendations receive the RCA result, reasoning, evidence IDs and metrics. The React report displays the evidence and complete MCP response, and Spring stores the raw report JSON in PostgreSQL.
