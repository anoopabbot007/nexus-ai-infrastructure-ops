# Phase 2 setup and validation

## Start and check Compose

From `D:\nexus-ai` in PowerShell:

```powershell
Copy-Item .env.example .env
docker compose config
docker compose up --build -d
docker compose ps
```

Check the public service health endpoints and observability backends:

```powershell
Invoke-RestMethod http://localhost:8080/api/v1/health
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8002/health
Invoke-RestMethod http://localhost:9090/-/ready
Invoke-RestMethod http://localhost:3100/ready
```

Compose health-checks the local processes; for minimal Loki and Alloy images those process checks are separate from HTTP readiness. Verify the HTTP readiness endpoints directly as shown above. The MCP endpoint is Streamable HTTP at `http://localhost:8001/mcp`; its protocol health is exercised by integration calls, not an ordinary GET.

## Live UI walkthrough

1. Emit real local metrics and logs for a scenario:

   ```powershell
   Invoke-RestMethod -Method Post -Uri http://localhost:8002/demo/scenarios/threads
   Start-Sleep -Seconds 8
   ```

2. In the dashboard at `http://localhost:3000`, create an alert for service `payment-service`, environment `production`, and the matching scenario.
3. Open the report below the incident list. Verify the telemetry badge says **REAL PROMETHEUS / LOKI TELEMETRY** and the LLM badge independently shows `MOCK` or the configured model provider.
4. Inspect the four-agent trace, metrics/log evidence IDs, **MCP tool execution**, and **Complete telemetry tool responses**.
5. Confirm PostgreSQL persistence by refreshing the page or retrieving `GET http://localhost:8080/api/v1/incidents/{incidentId}/report`.

Repeat using `memory`, `pool`, `database_latency`, and `dependency`. For `dependency`, the demo app intentionally responds HTTP 503 while emitting telemetry; continue with the incident investigation.

## Live integration test

The opt-in test drives each demo scenario, waits for Prometheus/Alloy collection, creates an incident through Spring, checks all four LangGraph agents and real MCP evidence, and retrieves the persisted report. It does not mock the Java-to-Python or Python-to-MCP calls.

```powershell
Set-Location agent-service
python -m pip install -r requirements-dev.txt
Set-Location ..
$env:NEXUS_LIVE_INTEGRATION = "1"
python -m pytest -q agent-service/tests/integration/test_live_compose.py
Remove-Item Env:NEXUS_LIVE_INTEGRATION
```

Without `NEXUS_LIVE_INTEGRATION=1`, the live tests are skipped. A skipped test is not evidence that the stack worked. The Python unit suite uses an explicit mock collector and should not be reported as live integration validation.

## Failure behavior

The default telemetry mode is `real`. To verify graceful failure, temporarily stop the MCP service and create an incident through Spring. The incident should complete with failed investigation status and the error should identify the MCP connection problem; no fixture data should appear. Restore with `docker compose start mcp-server` and wait for its healthy status. This is a manual destructive-to-the-running-stack interruption; do it only in the local demo stack.

If a report fails because a real telemetry query returned no samples, trigger the matching demo scenario first and wait for a Prometheus scrape and Alloy tail. Check logs with:

```powershell
docker compose logs --tail=100 demo-telemetry prometheus alloy loki mcp-server agent-service backend
```

## Storage and reset

`docker compose down` preserves named data volumes, including PostgreSQL, Prometheus and Loki data. `docker compose down -v` deletes those volumes. Use it only when you intend to erase local demo data.

## What the demo does not prove

“Real telemetry” means actual queries to the local Prometheus and Loki processes. It does not mean production data. Thread/memory values are measured from bounded demo workloads. Pool contention, database latency and dependency responses are synthetic local signals. The stack has no production exporter/Alloy deployment, authentication/authorization, cloud integration, or remediation execution.
