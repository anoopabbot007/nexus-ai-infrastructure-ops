from __future__ import annotations

import hashlib
from typing import Any

from ...config import Settings
from .common import iso_timestamp, request_json, unix_seconds, validate_label, validate_step, validate_window


def build_promql(metric_name: str, service_name: str, environment: str) -> str:
    service = validate_label(service_name, "service_name")
    env = validate_label(environment, "environment")
    selector = f'{{service="{service}",environment="{env}"}}'
    queries = {
        "cpu_utilization": f"nexus_cpu_utilization_percent{selector}",
        "memory_utilization": f"nexus_memory_utilization_percent{selector}",
        "jvm_heap_utilization": f"nexus_jvm_heap_utilization_percent{selector}",
        "http_request_rate": f"sum by (service, environment) (rate(nexus_http_requests_total{selector}[1m]))",
        "http_error_rate": (
            f"100 * sum by (service, environment) (rate(nexus_http_errors_total{selector}[1m])) "
            f"/ clamp_min(sum by (service, environment) (rate(nexus_http_requests_total{selector}[1m])), 0.000001)"
        ),
        "http_response_latency": (
            "histogram_quantile(0.95, sum by (le, service, environment) "
            f"(rate(nexus_http_request_duration_seconds_bucket{selector}[1m])))"
        ),
        "thread_activity": f"nexus_active_threads{selector}",
        "gc_pause_seconds": f"nexus_gc_pause_seconds{selector}",
        "db_pool_utilization": f"nexus_db_pool_utilization_percent{selector}",
        "db_pool_waiters": f"nexus_db_pool_waiters{selector}",
        "database_query_latency": (
            "histogram_quantile(0.95, sum by (le, service, environment) "
            f"(rate(nexus_database_query_duration_seconds_bucket{selector}[1m])))"
        ),
        "downstream_request_duration": (
            "histogram_quantile(0.95, sum by (le, service, environment) "
            f"(rate(nexus_downstream_request_duration_seconds_bucket{selector}[1m])))"
        ),
    }
    if metric_name not in queries:
        raise ValueError(f"Unsupported metric_name: {metric_name}")
    return queries[metric_name]


async def _query(settings: Settings, query: str, start_time: str, end_time: str, step: str, metric_name: str) -> dict[str, Any]:
    start, end = validate_window(start_time, end_time)
    normalized_step = validate_step(step)
    payload = await request_json(
        settings.prometheus_url,
        "/api/v1/query_range",
        {"query": query, "start": unix_seconds(start), "end": unix_seconds(end), "step": normalized_step},
        settings.telemetry_http_timeout_seconds,
        "Prometheus",
    )
    data = payload.get("data", {})
    rows: list[dict[str, Any]] = []
    for series in data.get("result", []):
        labels = series.get("metric", {})
        for point in series.get("values", []):
            if not isinstance(point, list) or len(point) != 2:
                continue
            timestamp, raw_value = point
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                continue
            seed = f"{metric_name}|{timestamp}|{sorted(labels.items())}"
            evidence_id = "prom-" + hashlib.sha256(seed.encode()).hexdigest()[:16]
            rows.append({
                "id": evidence_id,
                "source": "prometheus",
                "name": metric_name,
                "value": value,
                "timestamp": iso_timestamp(float(timestamp)),
                "labels": labels,
            })
    return {
        "available": True,
        "dataAvailable": bool(rows),
        "metricName": metric_name,
        "query": query,
        "records": rows,
        "recordCount": len(rows),
    }


async def query_prometheus_metrics(
    settings: Settings,
    service_name: str,
    environment: str,
    metric_name: str,
    start_time: str,
    end_time: str,
    step: str,
) -> dict[str, Any]:
    query = build_promql(metric_name, service_name, environment)
    return await _query(settings, query, start_time, end_time, step, metric_name)


async def query_prometheus_instant(
    settings: Settings,
    service_name: str,
    environment: str,
    metric_name: str,
) -> dict[str, Any]:
    query = build_promql(metric_name, service_name, environment)
    payload = await request_json(
        settings.prometheus_url,
        "/api/v1/query",
        {"query": query},
        settings.telemetry_http_timeout_seconds,
        "Prometheus",
    )
    data = payload.get("data", {})
    records = []
    for series in data.get("result", []):
        point = series.get("value")
        if not isinstance(point, list) or len(point) != 2:
            continue
        try:
            value = float(point[1])
            timestamp = float(point[0])
        except (TypeError, ValueError):
            continue
        labels = series.get("metric", {})
        seed = f"{metric_name}|{timestamp}|{sorted(labels.items())}"
        records.append({
            "id": "prom-" + hashlib.sha256(seed.encode()).hexdigest()[:16],
            "source": "prometheus",
            "name": metric_name,
            "value": value,
            "timestamp": iso_timestamp(timestamp),
            "labels": labels,
        })
    return {
        "available": True,
        "dataAvailable": bool(records),
        "metricName": metric_name,
        "query": query,
        "records": records,
        "recordCount": len(records),
    }