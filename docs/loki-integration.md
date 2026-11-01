# Grafana Loki and Alloy integration

The demo application writes one JSON object per line to a shared `nexus-demo-logs` volume and to stdout. Grafana Alloy tails `/var/log/nexus/*.jsonl` using `loki.source.file` and pushes lines to Loki's write API. Loki stores data on the `nexus-loki-data` named volume. Alloy's position data is stored on `nexus-alloy-data`.

Each log event carries an ISO timestamp, service, environment, severity level and message. Alloy uses the `job="nexus-demo"` stream label; the MCP tool parses the JSON fields and filters by service/environment, severity and an allowlisted case-insensitive keyword.

The query builder uses a constrained LogQL query. The app chooses severity, keyword and result limit; callers cannot supply arbitrary LogQL. Result rows include source `loki`, the backend timestamp, service/environment and a stable evidence ID derived from the returned line.

## Verify locally

```powershell
Invoke-RestMethod http://localhost:3100/ready
Invoke-RestMethod -Method Post -Uri http://localhost:8002/demo/scenarios/threads
Start-Sleep -Seconds 3
docker compose logs --tail=50 alloy loki
```

The full log query and returned events appear under **Complete telemetry tool responses** in the dashboard report. If no matching records are in the requested time window, the investigation reports that condition; it does not add fixture logs.

## Production boundary

This Compose pipeline tails only the demo app's local JSONL volume. It does not install an agent on a customer application or read arbitrary host paths. Production collection requires a separately reviewed Alloy deployment, exporter instrumentation, access control, TLS, tenant labels, redaction, and retention policy.
