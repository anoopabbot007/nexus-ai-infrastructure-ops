# API documentation

Base URL through the dashboard proxy: `http://localhost:3000/api/v1`. Direct Spring Boot URL: `http://localhost:8080/api/v1`.

## `POST /incidents`

Creates an incident, synchronously runs the four-agent investigation, persists the incident and report, then returns HTTP 201 with the incident and its `investigation` object. `incidentId` is optional; Spring generates one if omitted. Severity must be `LOW`, `MEDIUM`, `HIGH` or `CRITICAL`.

```json
{
  "incidentId": "INC-1001",
  "serviceName": "payment-service",
  "environment": "production",
  "alertType": "HIGH_CPU",
  "cpuUtilization": 94,
  "threshold": 80,
  "severity": "CRITICAL",
  "description": "CPU utilization exceeded 80% for 10 minutes"
}
```

Report fields include metrics, logs, findings, root cause, `rcaEvidenceIds`, reasoning, recommendations, execution status/trace, errors, LLM provider and telemetry metadata. `telemetryMode` is `real` or `mock`. `telemetryWindow` records the query interval. `mcpToolTrace` records discovery/calls, server URL, status, duration, row count and errors. `mcpToolCatalog` contains names, descriptions and input schemas. `telemetryEvidence` holds the full responses returned by each MCP tool.

The legacy `confidenceScore` field is retained for compatibility; it is the fraction of returned metric/log evidence cited by RCA, not a calibrated probability. The RCA guard verifies that IDs came from the tool outputs and applies conservative scenario-specific lexical checks; it does not prove semantic causality.

## `GET /incidents`

Returns incident summaries with their stored report when available.

## `GET /incidents/{incidentId}`

Returns one incident and its complete stored report. Unknown IDs return 404.

## `GET /incidents/{incidentId}/report`

Returns the complete persisted report, including telemetry evidence and the MCP trace. Returns 404 until the agent service has returned a report.

## Health endpoints

- Spring Boot: `GET http://localhost:8080/api/v1/health`
- FastAPI agent: `GET http://localhost:8000/health` (loopback only in Compose)
- Demo telemetry: `GET http://localhost:8002/health`
- Prometheus: `GET http://localhost:9090/-/ready`
- Loki: `GET http://localhost:3100/ready`

The MCP endpoint is Streamable HTTP at `http://localhost:8001/mcp`. Use the SDK or live integration suite for protocol calls; an ordinary GET is not its health check. Validation errors use the backend's standard error response. Agent connection failures return 502 and preserve the incident with failed status.
