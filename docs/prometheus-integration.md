# Prometheus integration

Prometheus scrapes the local demo service every five seconds from `observability/prometheus.yml`. The agent-facing MCP server calls Prometheus HTTP APIs; agents do not construct arbitrary queries. Configure `PROMETHEUS_URL` for the MCP server and `DEMO_SERVICE_NAME` / `DEMO_ENVIRONMENT` for matching labels.

## Exported series

| Prometheus metric | Meaning in the demo |
|---|---|
| `nexus_cpu_utilization_percent` | measured CPU use during the bounded thread workload |
| `nexus_memory_utilization_percent` | allocated bytes as a fraction of the configured demo budget |
| `nexus_jvm_heap_utilization_percent` | reserved for a JVM exporter; the Python demo does not emit it |
| `nexus_http_requests_total`, `nexus_http_errors_total` | demo HTTP request and error counters |
| `nexus_http_request_duration_seconds_bucket` | HTTP duration histogram |
| `nexus_active_threads` | active demo process threads during the thread workload |
| `nexus_gc_pause_seconds` | measured Python collection duration in the demo |
| `nexus_db_pool_utilization_percent`, `nexus_db_pool_waiters` | controlled semaphore-pool scenario signals |
| `nexus_database_query_duration_seconds_bucket` | controlled database-latency scenario histogram; it does not call a database |
| `nexus_downstream_request_duration_seconds_bucket` | controlled downstream latency histogram |

Series have `service` and `environment` labels. HTTP counters/histograms also use `route`. The controlled pool, database-latency and dependency scenarios are synthetic test workloads. Their series are useful for testing the observability path, not for asserting behavior of a real database or dependency.

## Allowlisted queries

The tool module maps names such as `cpu_utilization`, `memory_utilization`, `thread_activity`, `http_request_rate`, `http_error_rate`, `http_response_latency`, `db_pool_waiters`, `database_query_latency` and `downstream_request_duration` to fixed PromQL. It calls `/api/v1/query_range` for time series and `/api/v1/query` for the health summary. Each returned sample has a stable hash-based ID, timestamp, value, source and labels.

Example read-only query generated for the demo CPU series:

```promql
nexus_cpu_utilization_percent{service="payment-service",environment="production"}
```

An unknown metric name or malformed label is rejected before an HTTP request. An empty result does not become a fabricated zero.

## Verify locally

```powershell
Invoke-RestMethod http://localhost:9090/-/ready
Invoke-RestMethod -Method Post -Uri http://localhost:8002/demo/scenarios/threads
Start-Sleep -Seconds 8
Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=nexus_cpu_utilization_percent%7Bservice%3D%22payment-service%22%2Cenvironment%3D%22production%22%7D'
```

Inspect the MCP response and complete Prometheus samples in the incident report dashboard after submitting the matching alert.
