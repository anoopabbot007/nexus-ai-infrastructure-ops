from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from ...config import Settings
from .prometheus_tools import query_prometheus_instant
from .prometheus_tools import query_prometheus_metrics


HEALTH_METRICS = ("cpu_utilization", "memory_utilization", "http_error_rate", "http_response_latency")


async def get_service_health(settings: Settings, service_name: str, environment: str) -> dict[str, Any]:
    results = await asyncio.gather(*[
        query_prometheus_instant(settings, service_name, environment, metric)
        for metric in HEALTH_METRICS
    ])
    values: dict[str, float | None] = {}
    timestamps: list[str] = []
    for metric, result in zip(HEALTH_METRICS, results, strict=True):
        records = result["records"]
        latest = max(records, key=lambda row: row["timestamp"]) if records else None
        values[metric] = latest["value"] if latest else None
        if latest:
            timestamps.append(latest["timestamp"])

    available_values = [value for value in values.values() if value is not None]
    if not available_values:
        status = "UNKNOWN"
    elif (
        (values["cpu_utilization"] is not None and values["cpu_utilization"] >= 90)
        or (values["memory_utilization"] is not None and values["memory_utilization"] >= 90)
        or (values["http_error_rate"] is not None and values["http_error_rate"] >= 5)
        or (values["http_response_latency"] is not None and values["http_response_latency"] >= 1)
    ):
        status = "DEGRADED"
    else:
        status = "HEALTHY"

    return {
        "available": True,
        "dataAvailable": bool(available_values),
        "serviceName": service_name,
        "environment": environment,
        "status": status,
        "latestCpuUtilization": values["cpu_utilization"],
        "latestMemoryUtilization": values["memory_utilization"],
        "errorRatePercent": values["http_error_rate"],
        "p95ResponseLatencySeconds": values["http_response_latency"],
        "missingMetrics": [name for name, value in values.items() if value is None],
        "telemetryTimestamp": max(timestamps) if timestamps else None,
        "recordCount": len(available_values),
    }


async def get_resource_usage(
    settings: Settings,
    service_name: str,
    environment: str,
    start_time: str,
    end_time: str,
    step: str,
) -> dict[str, Any]:
    metrics = ("cpu_utilization", "memory_utilization")
    results = await asyncio.gather(*[
        query_prometheus_metrics(settings, service_name, environment, metric, start_time, end_time, step)
        for metric in metrics
    ])
    series: dict[str, list[dict[str, Any]]] = {}
    summary: dict[str, dict[str, float | None]] = {}
    for metric, result in zip(metrics, results, strict=True):
        records = result["records"]
        series[metric] = records
        values = [row["value"] for row in records]
        summary[metric] = {
            "minimum": min(values) if values else None,
            "maximum": max(values) if values else None,
            "average": sum(values) / len(values) if values else None,
        }
    return {
        "available": True,
        "dataAvailable": any(series.values()),
        "serviceName": service_name,
        "environment": environment,
        "series": series,
        "summary": summary,
        "recordCount": sum(len(rows) for rows in series.values()),
    }
