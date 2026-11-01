# NEXUS AI – Infrastructure Operations Platform

NEXUS AI is a read-only incident investigation demo. A React dashboard sends alerts to Spring Boot, which persists incidents and calls the Python LangGraph service. The Investigation Agent uses a Streamable HTTP MCP client to query Prometheus and Loki. A local telemetry application emits bounded demo workloads for five scenarios; Grafana Alloy ships its JSON logs to Loki.

The default telemetry mode is `real`: MCP makes actual HTTP queries to the local Prometheus and Loki services. The default LLM provider is `mock`, so no model key is needed. Telemetry mode and LLM provider are separate settings. `TELEMETRY_MODE=mock` explicitly selects deterministic fixture telemetry. The demo workloads are synthetic and local; this stack does not connect to production services or execute changes.

## Start the stack

Requirements: Docker Desktop with the Docker Compose v2 plugin.

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

Open [http://localhost:3000](http://localhost:3000). To inspect health, run:

```powershell
Invoke-RestMethod http://localhost:8080/api/v1/health
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8002/health
Invoke-RestMethod http://localhost:9090/-/ready
Invoke-RestMethod http://localhost:3100/ready
```

## Run one real telemetry investigation

First trigger a scenario on the local demo application. Wait for the 5-second Prometheus scrape and Alloy log tail, then submit the matching alert in the dashboard:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8002/demo/scenarios/threads
Start-Sleep -Seconds 8
```

Use **Investigate alert** with service `payment-service`, environment `production`, and the **High CPU · excessive threads** scenario. In the report, the telemetry badge should say **REAL PROMETHEUS / LOKI TELEMETRY**. Open **MCP tool execution** and **Complete telemetry tool responses** for the tool trace and raw query results. The dashboard keeps the LLM provider badge separate from telemetry mode.

The remaining workloads are `/demo/scenarios/memory`, `/demo/scenarios/pool`, `/demo/scenarios/database_latency`, and `/demo/scenarios/dependency`. The dependency scenario intentionally returns HTTP 503 while emitting error metrics and logs.

For exact commands, live integration tests, and limitations, see [Phase 2 setup](docs/phase-2-setup.md). The complete API contract is in [API documentation](docs/api-documentation.md).

## Components

```text
frontend/       React + TypeScript dashboard
backend/        Java 21 / Spring Boot REST API and PostgreSQL persistence
agent-service/  FastAPI, four LangGraph agents, MCP client/server and demo app
observability/  Prometheus, Loki and Grafana Alloy configuration
docs/           Architecture, integration guides, setup and interview notes
docker-compose.yml
.env.example
```

## Test suites

Python unit tests run from `agent-service` with `python -m pytest -q`. The live end-to-end suite is opt-in and requires the running Compose stack; instructions are in [Phase 2 setup](docs/phase-2-setup.md). Java tests are in `backend`. Docker validation requires Docker Desktop and the Compose CLI.

## Current boundaries

- The local demo service generates synthetic but measured workload signals. Database-pool, database-latency and dependency scenarios are controlled simulations, not observations of an external database or dependency.
- Real telemetry mode reads only the configured Prometheus and Loki endpoints. Missing data or unreachable endpoints fail the investigation; there is no telemetry fallback.
- Recommendations are advisory and never executed. No Kubernetes, cloud, Terraform, ITSM, production service, or write-capable infrastructure integration is configured.
- RCA evidence IDs are checked against tool output and conservative scenario indicators; this lexical guard does not prove full semantic causality.
- `.env` contains local configuration and must not be committed. Keep credentials out of source control.
