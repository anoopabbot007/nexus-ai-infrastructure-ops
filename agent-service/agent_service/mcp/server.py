from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from mcp.server import MCPServer

from ..config import get_settings
from ..tools.metrics_tool import SCENARIOS, collect_scenario
from .tools.common import TelemetryIntegrationError, validate_label, validate_step, validate_window
from .tools.health_tools import get_resource_usage as query_resource_usage
from .tools.health_tools import get_service_health as query_service_health
from .tools.loki_tools import ALLOWED_SEARCH_KEYWORDS, query_application_logs as query_loki_logs
from .tools.prometheus_tools import build_promql, query_prometheus_metrics as query_prometheus


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("nexus.mcp")
settings = get_settings()
mcp = MCPServer(
    "NEXUS Observability MCP",
    instructions="Read-only tools for querying allowlisted Prometheus metrics and Grafana Loki logs.",
)


def _scenario(value: str) -> str:
    if value not in SCENARIOS:
        raise ValueError(f"Unsupported scenario: {value}")
    return value


def _mock_data(scenario: str, service_name: str, environment: str) -> dict[str, Any]:
    description = {
        "threads": "high CPU thread pool queue",
        "memory": "memory heap GC",
        "pool": "database connection pool timeout",
        "database_latency": "database slow query latency",
        "dependency": "downstream dependency 503",
    }[scenario]
    return collect_scenario({
        "alertType": scenario,
        "description": description,
        "serviceName": service_name,
        "environment": environment,
    })


def _mock_metric_matches(scenario: str, metric_name: str, service_name: str, environment: str) -> list[dict[str, Any]]:
    case = SCENARIOS[scenario]
    names = [str(item["name"]).casefold() for item in case["metrics"]]
    aliases = {
        "cpu_utilization": ("cpu_utilization",),
        "memory_utilization": ("memory_utilization",),
        "jvm_heap_utilization": ("memory_utilization", "heap"),
        "http_request_rate": ("request_rate",),
        "http_error_rate": ("error_rate", "dependency_error_rate"),
        "http_response_latency": ("latency", "p95"),
        "thread_activity": ("thread",),
        "gc_pause_seconds": ("gc_",),
        "db_pool_utilization": ("db_pool_active",),
        "db_pool_waiters": ("db_pool_waiters",),
        "database_query_latency": ("database_query_p95",),
        "downstream_request_duration": ("downstream_duration",),
    }
    terms = aliases.get(metric_name, ())
    now = datetime.now(timezone.utc).isoformat()
    output = []
    for item, name in zip(case["metrics"], names, strict=True):
        if terms and any(term in name for term in terms):
            output.append({
                **item,
                "source": "mock",
                "timestamp": now,
                "labels": {"service": service_name, "environment": environment},
            })
    return output


async def _safe_telemetry_call(source: str, operation):
    try:
        return await operation
    except TelemetryIntegrationError as exc:
        logger.warning("%s query unavailable: %s", source, exc)
        return {
            "available": False,
            "dataAvailable": False,
            "error": str(exc),
            "source": source,
            "records": [],
            "recordCount": 0,
            "telemetryMode": "real",
        }

@mcp.tool()
async def query_prometheus_metrics(
    service_name: str,
    environment: str,
    metric_name: str,
    start_time: str,
    end_time: str,
    step: str = "30s",
    scenario: str = "threads",
) -> dict[str, Any]:
    """Query one allowlisted Prometheus metric over the incident time window."""
    service = validate_label(service_name, "service_name")
    env = validate_label(environment, "environment")
    scenario = _scenario(scenario)
    query = build_promql(metric_name, service, env)
    if settings.telemetry_mode == "mock":
        validate_window(start_time, end_time)
        validate_step(step)
        rows = _mock_metric_matches(scenario, metric_name, service, env)
        return {
            "available": True,
            "dataAvailable": bool(rows),
            "metricName": metric_name,
            "query": f"MOCK:{metric_name}",
            "records": rows,
            "recordCount": len(rows),
            "telemetryMode": "mock",
        }
    result = await _safe_telemetry_call("Prometheus", query_prometheus(settings, service, env, metric_name, start_time, end_time, step))
    result["telemetryMode"] = "real"
    return result


@mcp.tool()
async def query_application_logs(
    service_name: str,
    environment: str,
    start_time: str,
    end_time: str,
    severity: str | None = None,
    search_keyword: str | None = None,
    limit: int = 100,
    scenario: str = "threads",
) -> dict[str, Any]:
    """Query bounded, structured application logs from Grafana Loki."""
    service = validate_label(service_name, "service_name")
    env = validate_label(environment, "environment")
    scenario = _scenario(scenario)
    if not isinstance(limit, int) or not 1 <= limit <= settings.max_log_results:
        raise ValueError(f"limit must be between 1 and {settings.max_log_results}")
    if severity and severity.upper() not in {"DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"}:
        raise ValueError(f"Unsupported severity: {severity}")
    if search_keyword and search_keyword.casefold() not in ALLOWED_SEARCH_KEYWORDS:
        raise ValueError("search_keyword is not in the supported keyword allowlist")
    if settings.telemetry_mode == "mock":
        validate_window(start_time, end_time)
        rows = _mock_data(scenario, service, env)["application_logs"]
        normalized_severity = severity.upper() if severity else None
        rows = [
            {**row, "source": "mock", "service": service, "environment": env}
            for row in rows
            if (normalized_severity is None or row["level"] == normalized_severity)
            and (search_keyword is None or search_keyword.casefold() in row["message"].casefold())
        ][:limit]
        return {
            "available": True,
            "dataAvailable": bool(rows),
            "query": "MOCK:scenario logs",
            "records": rows,
            "recordCount": len(rows),
            "telemetryMode": "mock",
        }
    result = await _safe_telemetry_call(
        "Grafana Loki",
        query_loki_logs(settings, service, env, start_time, end_time, severity, search_keyword, limit),
    )
    result["telemetryMode"] = "real"
    return result


@mcp.tool()
async def get_service_health(
    service_name: str,
    environment: str,
    scenario: str = "threads",
) -> dict[str, Any]:
    """Summarize the latest available Prometheus signals; missing values stay null."""
    service = validate_label(service_name, "service_name")
    env = validate_label(environment, "environment")
    scenario = _scenario(scenario)
    if settings.telemetry_mode == "mock":
        case = _mock_data(scenario, service, env)
        metrics = {row["name"]: row.get("value") for row in case["infrastructure_metrics"]}
        latency = metrics.get("p95_latency", metrics.get("api_p95_latency"))
        if latency is not None:
            latency /= 1000.0
        now = datetime.now(timezone.utc).isoformat()
        return {
            "available": True,
            "dataAvailable": bool(metrics),
            "serviceName": service,
            "environment": env,
            "status": case.get("health", "UNKNOWN"),
            "latestCpuUtilization": metrics.get("cpu_utilization"),
            "latestMemoryUtilization": metrics.get("memory_utilization"),
            "errorRatePercent": metrics.get("downstream_dependency_error_rate", metrics.get("error_rate")),
            "p95ResponseLatencySeconds": latency,
            "missingMetrics": [],
            "telemetryTimestamp": now,
            "recordCount": len(metrics),
            "telemetryMode": "mock",
        }
    result = await _safe_telemetry_call("Prometheus", query_service_health(settings, service, env))
    result["telemetryMode"] = "real"
    return result


@mcp.tool()
async def get_resource_usage(
    service_name: str,
    environment: str,
    start_time: str,
    end_time: str,
    step: str = "30s",
    scenario: str = "threads",
) -> dict[str, Any]:
    """Retrieve CPU and memory time series and summary statistics."""
    service = validate_label(service_name, "service_name")
    env = validate_label(environment, "environment")
    scenario = _scenario(scenario)
    if settings.telemetry_mode == "mock":
        validate_window(start_time, end_time)
        validate_step(step)
        rows = _mock_data(scenario, service, env)["infrastructure_metrics"]
        cpu = [row for row in rows if "cpu" in row.get("name", "")]
        memory = [row for row in rows if "memory" in row.get("name", "") or "heap" in row.get("name", "")]
        series = {"cpu_utilization": cpu, "memory_utilization": memory}
        summary = {
            name: {
                "minimum": min((row["value"] for row in values), default=None),
                "maximum": max((row["value"] for row in values), default=None),
                "average": (sum(row["value"] for row in values) / len(values)) if values else None,
            }
            for name, values in series.items()
        }
        return {
            "available": bool(cpu or memory),
            "dataAvailable": bool(cpu or memory),
            "serviceName": service,
            "environment": env,
            "series": series,
            "summary": summary,
            "recordCount": len(cpu) + len(memory),
            "telemetryMode": "mock",
        }
    result = await _safe_telemetry_call("Prometheus", query_resource_usage(settings, service, env, start_time, end_time, step))
    result["telemetryMode"] = "real"
    return result


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)
