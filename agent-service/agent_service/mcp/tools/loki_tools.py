from __future__ import annotations

import hashlib
import json
from typing import Any

from ...config import Settings
from .common import request_json, unix_nanoseconds, validate_label, validate_window

ALLOWED_SEVERITIES = {"DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"}
ALLOWED_SEARCH_KEYWORDS = {
    "cpu", "thread", "memory", "heap", "gc", "database", "pool", "timeout",
    "latency", "dependency", "downstream", "503", "connection", "queue", "error",
}


def build_logql(
    service_name: str,
    environment: str,
    severity: str | None,
    search_keyword: str | None,
) -> str:
    service = validate_label(service_name, "service_name")
    env = validate_label(environment, "environment")
    query = '{job="nexus-demo"} | json | service="' + service + '" | environment="' + env + '"'
    if severity:
        normalized = severity.strip().upper()
        if normalized not in ALLOWED_SEVERITIES:
            raise ValueError(f"Unsupported severity: {severity}")
        query += f' | level="{normalized}"'
    if search_keyword:
        keyword = search_keyword.strip().casefold()
        if keyword not in ALLOWED_SEARCH_KEYWORDS:
            raise ValueError(f"Unsupported search_keyword: {search_keyword}")
        # Known keywords are selected from a fixed allowlist above. Case-insensitive
        # matching is needed because real application log messages vary in casing.
        query += f' |~ "(?i){keyword}"'
    return query


async def query_application_logs(
    settings: Settings,
    service_name: str,
    environment: str,
    start_time: str,
    end_time: str,
    severity: str | None = None,
    search_keyword: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    start, end = validate_window(start_time, end_time)
    result_limit = settings.max_log_results if limit is None else limit
    if not isinstance(result_limit, int) or not 1 <= result_limit <= settings.max_log_results:
        raise ValueError(f"limit must be between 1 and {settings.max_log_results}")
    query = build_logql(service_name, environment, severity, search_keyword)
    payload = await request_json(
        settings.loki_url,
        "/loki/api/v1/query_range",
        {
            "query": query,
            "start": unix_nanoseconds(start),
            "end": unix_nanoseconds(end),
            "limit": result_limit,
            "direction": "BACKWARD",
        },
        settings.telemetry_http_timeout_seconds,
        "Grafana Loki",
    )
    data = payload.get("data", {})
    records: list[dict[str, Any]] = []
    for stream in data.get("result", []):
        stream_labels = stream.get("stream", {})
        for point in stream.get("values", []):
            if not isinstance(point, list) or len(point) != 2:
                continue
            timestamp, line = point
            try:
                event = json.loads(line)
            except (TypeError, json.JSONDecodeError):
                event = {"message": str(line)}
            if not isinstance(event, dict):
                event = {"message": str(line)}
            ts = str(event.get("timestamp") or timestamp)
            message = str(event.get("message", ""))
            level = str(event.get("level") or stream_labels.get("level") or "INFO").upper()
            service = str(event.get("service") or stream_labels.get("service") or service_name)
            env = str(event.get("environment") or stream_labels.get("environment") or environment)
            evidence_id = "loki-" + hashlib.sha256(f"{timestamp}|{line}".encode()).hexdigest()[:16]
            records.append({
                "id": evidence_id,
                "source": "loki",
                "timestamp": ts,
                "level": level,
                "service": service,
                "environment": env,
                "message": message,
            })
            if len(records) >= result_limit:
                break
        if len(records) >= result_limit:
            break
    return {
        "available": True,
        "dataAvailable": bool(records),
        "query": query,
        "records": records,
        "recordCount": len(records),
    }
