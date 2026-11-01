from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from mcp import Client

from ..config import Settings
from ..tools.metrics_tool import SCENARIOS, _scenario
from .tools.common import TelemetryIntegrationError


SCENARIO_METRICS = {
    "threads": ("cpu_utilization", "http_response_latency", "thread_activity"),
    "memory": ("memory_utilization", "jvm_heap_utilization", "gc_pause_seconds"),
    "pool": ("db_pool_utilization", "db_pool_waiters", "http_response_latency"),
    "database_latency": ("database_query_latency", "http_response_latency", "http_request_rate"),
    "dependency": ("http_error_rate", "http_request_rate", "http_response_latency"),
}
SCENARIO_LOG_FILTER = {
    "threads": (None, "thread"),
    "memory": (None, "gc"),
    "pool": (None, "connection"),
    "database_latency": (None, "database"),
    "dependency": (None, "dependency"),
}
EXPECTED_TOOLS = {
    "query_prometheus_metrics",
    "query_application_logs",
    "get_service_health",
    "get_resource_usage",
}
METRIC_UNITS = {
    "cpu_utilization": "%",
    "memory_utilization": "%",
    "jvm_heap_utilization": "%",
    "http_request_rate": "requests/s",
    "http_error_rate": "%",
    "http_response_latency": "seconds",
    "thread_activity": "threads",
    "gc_pause_seconds": "seconds",
    "db_pool_utilization": "%",
    "db_pool_waiters": "connections",
    "database_query_latency": "seconds",
    "downstream_request_duration": "seconds",
}


class MCPIntegrationError(TelemetryIntegrationError):
    def __init__(
        self,
        message: str,
        *,
        tool_trace: list[dict[str, Any]] | None = None,
        tool_catalog: list[dict[str, Any]] | None = None,
        telemetry_window: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.mcp_tool_trace = tool_trace or []
        self.mcp_tool_catalog = tool_catalog or []
        self.telemetry_window = telemetry_window or {}


def _record_count(value: dict[str, Any]) -> int:
    if isinstance(value.get("recordCount"), int):
        return value["recordCount"]
    records = value.get("records")
    if isinstance(records, list):
        return len(records)
    return 1 if value.get("available") else 0


def _extract_structured(result: Any) -> dict[str, Any]:
    if getattr(result, "is_error", False):
        messages = [
            getattr(block, "text", "")
            for block in getattr(result, "content", [])
            if getattr(block, "text", None)
        ]
        raise MCPIntegrationError("; ".join(messages) or "MCP tool returned an error")
    content = getattr(result, "structured_content", None)
    if isinstance(content, dict):
        return content
    for block in getattr(result, "content", []):
        text = getattr(block, "text", None)
        if text:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    raise MCPIntegrationError("MCP tool returned no structured result")


def _metric_rows(metric_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for metric_name, result in metric_results.items():
        records = result.get("records") or []
        if not records:
            continue
        ordered = sorted(records, key=lambda row: str(row.get("timestamp", "")))
        latest = dict(ordered[-1])
        latest["name"] = metric_name
        latest["unit"] = METRIC_UNITS.get(metric_name)
        latest["recordCount"] = len(records)
        latest["samples"] = ordered[-20:]
        latest["source"] = "prometheus" if result.get("telemetryMode") == "real" else "mock"
        rows.append(latest)
    return rows


async def _collect(settings: Settings, alert: dict[str, Any]) -> dict[str, Any]:
    service = str(alert["serviceName"])
    environment = str(alert["environment"])
    scenario = _scenario(alert)
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=settings.investigation_lookback_minutes)
    window = {"startTime": start.isoformat(), "endTime": end.isoformat()}
    step = f"{settings.query_step_seconds}s"
    severity, keyword = SCENARIO_LOG_FILTER[scenario]
    catalog: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    metric_results: dict[str, dict[str, Any]] = {}
    all_results: dict[str, Any] = {}

    try:
        async with asyncio.timeout(settings.mcp_timeout_seconds * 5):
            async with Client(settings.mcp_server_url) as client:
                started = time.monotonic()
                listed = await asyncio.wait_for(
                    client.list_tools(), timeout=settings.mcp_timeout_seconds
                )
                tools = list(listed.tools)
                catalog = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.input_schema,
                    }
                    for tool in tools
                ]
                names = {tool.name for tool in tools}
                trace.append({
                    "toolName": "tools/list",
                    "server": settings.mcp_server_url,
                    "status": "COMPLETED",
                    "durationMs": round((time.monotonic() - started) * 1000, 2),
                    "recordCount": len(tools),
                    "error": None,
                })
                missing = EXPECTED_TOOLS - names
                if missing:
                    raise MCPIntegrationError(
                        "MCP server is missing required tools: " + ", ".join(sorted(missing)),
                        tool_trace=trace,
                        tool_catalog=catalog,
                        telemetry_window=window,
                    )

                async def call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
                    call_started = time.monotonic()
                    record = {
                        "toolName": tool_name,
                        "server": settings.mcp_server_url,
                        "status": "FAILED",
                        "durationMs": 0,
                        "recordCount": 0,
                        "error": None,
                    }
                    try:
                        raw = await asyncio.wait_for(
                            client.call_tool(tool_name, arguments),
                            timeout=settings.mcp_timeout_seconds,
                        )
                        value = _extract_structured(raw)
                        record["recordCount"] = _record_count(value)
                        if value.get("available") is False:
                            raise MCPIntegrationError(str(value.get("error") or f"{tool_name} source unavailable"))
                        record["status"] = "COMPLETED"
                        return value
                    except Exception as exc:
                        record["error"] = str(exc)[:300]
                        raise
                    finally:
                        record["durationMs"] = round((time.monotonic() - call_started) * 1000, 2)
                        trace.append(record)

                calls = [
                    ("query_prometheus_metrics", {
                        "service_name": service,
                        "environment": environment,
                        "metric_name": metric_name,
                        "start_time": window["startTime"],
                        "end_time": window["endTime"],
                        "step": step,
                        "scenario": scenario,
                    })
                    for metric_name in SCENARIO_METRICS[scenario]
                ]
                calls.extend([
                    ("query_application_logs", {
                        "service_name": service,
                        "environment": environment,
                        "start_time": window["startTime"],
                        "end_time": window["endTime"],
                        "severity": severity,
                        "search_keyword": keyword,
                        "limit": settings.max_log_results,
                        "scenario": scenario,
                    }),
                    ("get_service_health", {
                        "service_name": service,
                        "environment": environment,
                        "scenario": scenario,
                    }),
                    ("get_resource_usage", {
                        "service_name": service,
                        "environment": environment,
                        "start_time": window["startTime"],
                        "end_time": window["endTime"],
                        "step": step,
                        "scenario": scenario,
                    }),
                ])
                values = await asyncio.gather(
                    *(call(name, arguments) for name, arguments in calls),
                    return_exceptions=True,
                )
                errors = []
                for (name, _), value in zip(calls, values, strict=True):
                    if isinstance(value, BaseException):
                        errors.append(f"{name}: {value}")
                        continue
                    all_results.setdefault(name, []).append(value)
                    if name == "query_prometheus_metrics":
                        metric_results[value["metricName"]] = value
                if errors:
                    raise MCPIntegrationError(
                        "Telemetry MCP query failed: " + "; ".join(errors),
                        tool_trace=trace,
                        tool_catalog=catalog,
                        telemetry_window=window,
                    )
    except MCPIntegrationError as exc:
        if not exc.mcp_tool_trace:
            exc.mcp_tool_trace = trace
        if not exc.mcp_tool_catalog:
            exc.mcp_tool_catalog = catalog
        if not exc.telemetry_window:
            exc.telemetry_window = window
        raise
    except Exception as exc:
        trace.append({
            "toolName": "MCP connection",
            "server": settings.mcp_server_url,
            "status": "FAILED",
            "durationMs": 0,
            "recordCount": 0,
            "error": str(exc)[:300],
        })
        raise MCPIntegrationError(
            f"Could not connect to the NEXUS MCP server: {exc}",
            tool_trace=trace,
            tool_catalog=catalog,
            telemetry_window=window,
        ) from exc

    infrastructure_metrics = _metric_rows(metric_results)
    for health in all_results.get("get_service_health", []):
        timestamp = health.get("telemetryTimestamp")
        if health.get("available") and health.get("dataAvailable") and health.get("status"):
            infrastructure_metrics.append({
                "id": f"health-{scenario}-{timestamp or 'latest'}",
                "source": "prometheus-derived",
                "name": "service_health",
                "status": health["status"],
                "value": health["status"],
                "timestamp": timestamp,
                "service": service,
                "environment": environment,
            })

    logs_result = (all_results.get("query_application_logs") or [{}])[0]
    application_logs = logs_result.get("records") or []
    if not infrastructure_metrics or not application_logs:
        missing_parts = []
        if not infrastructure_metrics:
            missing_parts.append("Prometheus returned no metric samples")
        if not application_logs:
            missing_parts.append("Loki returned no matching log records")
        raise MCPIntegrationError(
            "; ".join(missing_parts) + f" for {service} in the requested time window; no absence-of-error conclusion was made",
            tool_trace=trace,
            tool_catalog=catalog,
            telemetry_window=window,
        )

    evidence_ids = [row["id"] for row in infrastructure_metrics + application_logs if row.get("id")]
    findings = [{
        "title": "Prometheus and Loki telemetry",
        "summary": (
            f"Retrieved {len(infrastructure_metrics)} metric summaries and "
            f"{len(application_logs)} log records for the {scenario} scenario."
        ),
        "evidenceIds": evidence_ids,
    }]
    return {
        "scenario": scenario,
        "infrastructure_metrics": infrastructure_metrics,
        "application_logs": application_logs,
        "investigation_findings": findings,
        "telemetry_mode": settings.telemetry_mode,
        "telemetry_window": window,
        "telemetry_evidence": all_results,
        "mcp_tool_trace": trace,
        "mcp_tool_catalog": catalog,
    }


def collect_via_mcp(settings: Settings, alert: dict[str, Any]) -> dict[str, Any]:
    """Run the asynchronous MCP client from the synchronous LangGraph node."""
    return asyncio.run(_collect(settings, alert))
