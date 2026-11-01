from __future__ import annotations

from typing import Any


SCENARIOS: dict[str, dict[str, Any]] = {
    "threads": {
        "metrics": [
            {"id": "cpu-1", "name": "cpu_utilization", "value": 94.0, "unit": "%", "window": "10m"},
            {"id": "threads-1", "name": "jvm_live_threads", "value": 1840, "unit": "threads", "baseline": 220},
            {"id": "latency-1", "name": "p95_latency", "value": 1850, "unit": "ms", "baseline": 210},
        ],
        "logs": [
            {"id": "log-1", "timestamp": "2026-11-01T10:01:00Z", "level": "WARN", "message": "Thread pool active count 1840 exceeded configured target 250"},
            {"id": "log-2", "timestamp": "2026-11-01T10:02:00Z", "level": "WARN", "message": "Request queue depth increasing; worker threads repeatedly created"},
        ],
        "health": "DEGRADED",
        "cause": "Excessive application thread creation is driving CPU saturation and request queue growth.",
        "reasoning": "The live thread count is more than eight times its baseline while CPU and p95 latency are elevated. Logs independently show thread-pool oversubscription and a growing queue.",
        "evidence": ["cpu-1", "threads-1", "latency-1", "log-1", "log-2"],
    },
    "memory": {
        "metrics": [
            {"id": "mem-1", "name": "memory_utilization", "value": 93.0, "unit": "%", "window": "10m"},
            {"id": "gc-1", "name": "gc_pause_seconds", "value": 2.8, "unit": "seconds", "baseline": 0.12},
            {"id": "cpu-1", "name": "cpu_utilization", "value": 82.0, "unit": "%", "window": "10m"},
        ],
        "logs": [
            {"id": "log-1", "timestamp": "2026-11-01T10:01:00Z", "level": "WARN", "message": "Old generation occupancy 91%; repeated full garbage collection"},
            {"id": "log-2", "timestamp": "2026-11-01T10:02:00Z", "level": "ERROR", "message": "GC pause exceeded 2 seconds; request processing delayed"},
        ],
        "health": "DEGRADED",
        "cause": "High memory pressure is causing frequent long garbage-collection pauses.",
        "reasoning": "Memory utilization and old-generation occupancy are high, with full-GC pauses substantially above baseline and logs reporting delayed requests.",
        "evidence": ["mem-1", "gc-1", "cpu-1", "log-1", "log-2"],
    },
    "pool": {
        "metrics": [
            {"id": "pool-1", "name": "db_pool_active", "value": 100, "unit": "%", "maximum": 100},
            {"id": "pool-2", "name": "db_pool_waiters", "value": 46, "unit": "connections"},
            {"id": "latency-1", "name": "p95_latency", "value": 4200, "unit": "ms", "baseline": 230},
        ],
        "logs": [
            {"id": "log-1", "timestamp": "2026-11-01T10:01:00Z", "level": "ERROR", "message": "Connection acquisition timed out after 3000 ms"},
            {"id": "log-2", "timestamp": "2026-11-01T10:02:00Z", "level": "WARN", "message": "Database connection pool exhausted; 46 requests waiting"},
        ],
        "health": "DEGRADED",
        "cause": "Database connection pool exhaustion is blocking application requests.",
        "reasoning": "The pool is at its configured maximum with 46 waiters, and logs show acquisition timeouts alongside sharply increased latency.",
        "evidence": ["pool-1", "pool-2", "latency-1", "log-1", "log-2"],
    },
    "database_latency": {
        "metrics": [
            {"id": "db-lat-1", "name": "database_query_p95", "value": 1600, "unit": "ms", "baseline": 90},
            {"id": "latency-1", "name": "api_p95_latency", "value": 2400, "unit": "ms", "baseline": 180},
            {"id": "cpu-1", "name": "cpu_utilization", "value": 71.0, "unit": "%", "window": "10m"},
        ],
        "logs": [
            {"id": "log-1", "timestamp": "2026-11-01T10:01:00Z", "level": "WARN", "message": "Slow query exceeded 1500 ms on order lookup"},
            {"id": "log-2", "timestamp": "2026-11-01T10:02:00Z", "level": "WARN", "message": "Database response time dominates request span"},
        ],
        "health": "DEGRADED",
        "cause": "Database query delays are the primary contributor to increased API latency.",
        "reasoning": "Database query p95 is far above its baseline and request traces attribute most of the request duration to database work, while CPU is below the alert threshold.",
        "evidence": ["db-lat-1", "latency-1", "cpu-1", "log-1", "log-2"],
    },
    "dependency": {
        "metrics": [
            {"id": "dep-1", "name": "downstream_dependency_error_rate", "value": 38.0, "unit": "%", "baseline": 0.4},
            {"id": "latency-1", "name": "api_p95_latency", "value": 2100, "unit": "ms", "baseline": 190},
            {"id": "cpu-1", "name": "cpu_utilization", "value": 58.0, "unit": "%", "window": "10m"},
        ],
        "logs": [
            {"id": "log-1", "timestamp": "2026-11-01T10:01:00Z", "level": "ERROR", "message": "fraud-check dependency returned HTTP 503"},
            {"id": "log-2", "timestamp": "2026-11-01T10:02:00Z", "level": "ERROR", "message": "Circuit breaker opened for fraud-check after consecutive failures"},
        ],
        "health": "DEGRADED",
        "cause": "A downstream dependency failure is causing application errors and elevated request latency.",
        "reasoning": "The downstream error rate is sharply above baseline and logs show repeated HTTP 503 responses followed by circuit-breaker activation.",
        "evidence": ["dep-1", "latency-1", "cpu-1", "log-1", "log-2"],
    },
}


def _scenario(alert: dict[str, Any]) -> str:
    text = " ".join(str(alert.get(key, "")) for key in ("alertType", "description", "serviceName")).lower()
    if any(term in text for term in ("memory", "heap", "gc", "oom")):
        return "memory"
    if any(term in text for term in ("connection pool", "pool exhaustion", "pool_exhaust")):
        return "pool"
    if any(term in text for term in ("database latency", "database_latency", "slow query", "db delay", "database delay")):
        return "database_latency"
    if any(term in text for term in ("dependency", "downstream", "503", "dependency_failure")):
        return "dependency"
    if any(term in text for term in ("thread", "thread_exhaust")):
        return "threads"
    # HIGH_CPU is the demonstration default, matching the business scenario.
    return "threads"


def get_cpu_metrics(alert: dict[str, Any]) -> list[dict[str, Any]]:
    return [m for m in SCENARIOS[_scenario(alert)]["metrics"] if "cpu" in m["name"]]


def get_memory_metrics(alert: dict[str, Any]) -> list[dict[str, Any]]:
    return [m for m in SCENARIOS[_scenario(alert)]["metrics"] if "memory" in m["name"] or "gc_" in m["name"]]


def get_response_latency(alert: dict[str, Any]) -> list[dict[str, Any]]:
    return [m for m in SCENARIOS[_scenario(alert)]["metrics"] if "latency" in m["name"] or "query_p95" in m["name"]]


def get_service_health(alert: dict[str, Any]) -> dict[str, str]:
    return {"id": "health-1", "name": "service_health", "status": SCENARIOS[_scenario(alert)]["health"]}


def get_application_logs(alert: dict[str, Any]) -> list[dict[str, Any]]:
    return list(SCENARIOS[_scenario(alert)]["logs"])


def collect_scenario(alert: dict[str, Any]) -> dict[str, Any]:
    scenario = _scenario(alert)
    case = SCENARIOS[scenario]
    metric_groups = [get_cpu_metrics(alert), get_memory_metrics(alert), get_response_latency(alert)]
    metrics_by_id = {metric["id"]: metric for group in metric_groups for metric in group}
    # Scenario-specific database and thread gauges supplement the reusable metric tools.
    for metric in case["metrics"]:
        metrics_by_id.setdefault(metric["id"], metric)
    return {
        "scenario": scenario,
        "infrastructure_metrics": list(metrics_by_id.values()) + [get_service_health(alert)],
        "application_logs": get_application_logs(alert),
        "investigation_findings": [{"title": "Simulated signal correlation", "summary": case["reasoning"], "evidenceIds": case["evidence"]}],
    }

