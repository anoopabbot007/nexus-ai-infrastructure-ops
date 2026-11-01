# Local setup

## Requirements

- Docker Desktop with Docker Compose v2.
- Optional for local Python work: Python 3.12 and pip.
- The default LLM is deterministic mock mode; no API key is needed.

## Configure and start

From the project root in PowerShell:

```powershell
Copy-Item .env.example .env
docker compose config
docker compose up --build -d
docker compose ps
```

The stack exposes the dashboard on `3000`, Spring API on `8080`, loopback-only agent service on `8000`, demo telemetry app on `8002`, Prometheus on `9090`, Loki on `3100`, and loopback-only MCP server on `8001`. PostgreSQL uses port `5432`. Change exposed ports in `.env` if a port is occupied.

## Verify service health

```powershell
Invoke-RestMethod http://localhost:8080/api/v1/health
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8002/health
Invoke-RestMethod http://localhost:9090/-/ready
Invoke-RestMethod http://localhost:3100/ready
docker compose ps
```

MCP uses Streamable HTTP at `http://localhost:8001/mcp`; it is validated by the opt-in live Compose tests rather than an ordinary browser GET.

## Run a real telemetry scenario

The dashboard creates an alert record and requests an investigation. It does not generate monitoring data. Trigger workload on the local demo service first so that Prometheus can scrape samples and Alloy can ship logs:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8002/demo/scenarios/threads
Start-Sleep -Seconds 8
```

Then use the dashboard at [http://localhost:3000](http://localhost:3000) to submit an alert for service `payment-service`, environment `production`, and the matching scenario. The report labels telemetry as **REAL** and shows MCP calls, timestamps, evidence IDs and raw telemetry responses. Repeat for `memory`, `pool`, `database_latency`, and `dependency`.

The dependency endpoint intentionally responds with 503 after generating error metrics/logs. PowerShell may throw for that response; the scenario still emitted the intended signals.

## Explicit fixture telemetry

Set `TELEMETRY_MODE=mock` in `.env`, then recreate the MCP and agent containers:

```powershell
docker compose up -d --force-recreate mcp-server agent-service
Invoke-RestMethod http://localhost:8000/health
```

The health response shows the telemetry mode. Fixture responses still flow through the MCP server and MCP client. Switch back to `TELEMETRY_MODE=real` and recreate both services to return to Prometheus/Loki queries.

## Model configuration

Set `LLM_PROVIDER=openai` and `OPENAI_API_KEY` to use OpenAI; or configure the Azure OpenAI variables shown in `.env.example`. This changes the model mode only. It does not change telemetry mode. The API key belongs only in `.env`; never paste it into source files or commit `.env`.

## Run Python tests

```powershell
Set-Location agent-service
python -m pip install -r requirements-dev.txt
python -m pip install -r requirements.txt
python -m pytest -q
```

The unit tests replace the external MCP client with deterministic fixture data. They do not prove live service connectivity. For that, use [Phase 2 setup and live validation](phase-2-setup.md).

## Persistence and shutdown

`docker compose down` stops the services and keeps named volumes. `docker compose down -v` deletes PostgreSQL and observability data volumes; use it only when you intend to reset local state. Check the agent, MCP, Prometheus, Loki and Alloy logs with `docker compose logs --tail=100 agent-service mcp-server prometheus loki alloy`.
