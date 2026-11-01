# Interview explanation

NEXUS AI is a read-only infrastructure incident investigation demo. React handles incident intake and reports; Spring Boot owns the API and persists data in PostgreSQL; Python FastAPI runs a LangGraph workflow. For observability, the investigation agent is an MCP client. It discovers read-only tools on a separate Streamable HTTP MCP server, which queries Prometheus metrics and Loki logs. Prometheus scrapes a local demo app and Grafana Alloy ships the app's JSON logs to Loki.

## Why LangGraph and separate agents

The workflow is one `StateGraph` over a shared `IncidentState`, not four unrelated prompt calls. Alert analysis classifies the incoming context, investigation gathers tool evidence, RCA correlates that evidence, and recommendations propose safe follow-up. A failed node is recorded and conditional routing ends the graph, so downstream agents do not pretend to have completed.

## Why MCP

MCP provides tool discovery and a standard client/server boundary between the investigation agent and observability data. The client checks the catalog and records calls. The server exposes four narrow read-only tools. PromQL metrics, LogQL search choices, labels, result limits and time windows are bounded. The API response persists both human-readable evidence and the MCP trace.

## Real telemetry versus mock telemetry

`TELEMETRY_MODE=real` is the default and makes actual HTTP API requests to Prometheus and Loki. The sources in the provided Compose stack are fed by a local demo workload generator; they are not connected to production. `TELEMETRY_MODE=mock` explicitly chooses fixtures. Separately, `LLM_PROVIDER=mock` is the default model mode and keeps the demo credential-free. A report displays both modes so “OpenAI model” cannot be confused with “real telemetry.”

The demo's thread and memory workloads produce measured local process metrics. Pool pressure, database latency and dependency failure are controlled simulations. A real organization would need to deploy supported exporters and Alloy/agents beside its own services, configure access to its telemetry backends, and then validate service labels and access controls. No such production connection is included here.

## Evidence and confidence

RCA IDs must exist in actual investigation tool output, cite both metric and log data, and pass conservative scenario-specific checks. The compatibility field called `confidenceScore` is only the ratio of cited evidence rows to returned rows. It is not calibrated confidence, and lexical checks cannot establish that an explanation is semantically or causally true. An operator still reviews the complete evidence.

## Current limits

The stack is synchronous and single-tenant, uses local demonstration credentials, and has no auth, secret manager, queue, production SLO policy, or write-capable remediation. Recommendations remain human-reviewed. Phase 2 does not add Kubernetes, Terraform, cloud writes, ITSM or production integrations.
