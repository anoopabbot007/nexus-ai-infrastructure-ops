"""Opt-in live Compose test. Requires a running local NEXUS Phase 2 stack."""

import json
import os
import time
import urllib.error
import urllib.request
import uuid

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("NEXUS_LIVE_INTEGRATION") != "1",
    reason="Set NEXUS_LIVE_INTEGRATION=1 to exercise the running Docker Compose stack",
)

BACKEND = os.getenv("NEXUS_BACKEND_URL", "http://localhost:8080")
DEMO = os.getenv("NEXUS_DEMO_URL", "http://localhost:8002")

SCENARIOS = [
    ("threads", "HIGH_CPU", "CPU utilization is high and the thread queue is growing."),
    ("memory", "HIGH_MEMORY", "Memory heap pressure is high with repeated GC pauses."),
    ("pool", "DB_POOL_EXHAUSTION", "Database connection pool exhaustion and acquisition timeouts."),
    ("database_latency", "DATABASE_LATENCY", "Database query latency is delaying requests."),
    ("dependency", "DEPENDENCY_FAILURE", "Downstream dependency errors and HTTP 503 responses."),
]


def _request(url: str, payload: dict | None = None, timeout: int = 180, method: str | None = None):
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method=method or ("POST" if body is not None else "GET"),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode())


@pytest.mark.parametrize(("scenario", "alert_type", "description"), SCENARIOS)
def test_live_demo_to_prometheus_loki_mcp_langgraph_spring_and_postgres(
    scenario: str, alert_type: str, description: str
):
    status, demo_response = _request(f"{DEMO}/demo/scenarios/{scenario}", method="POST")
    assert status in {200, 503}, demo_response
    if scenario == "dependency":
        assert status == 503
    else:
        assert status == 200

    # Prometheus scrapes every five seconds and Alloy tails the emitted JSONL.
    time.sleep(8)
    incident_id = "INC-P2-" + uuid.uuid4().hex[:10].upper()
    status, incident = _request(f"{BACKEND}/api/v1/incidents", {
        "incidentId": incident_id,
        "serviceName": "payment-service",
        "environment": "production",
        "alertType": alert_type,
        "severity": "HIGH",
        "description": description,
    })
    assert status == 201, incident
    report = incident["investigation"]
    assert report["telemetryMode"] == "real"
    assert report["executionStatus"] == "COMPLETED"
    assert [step["status"] for step in report["executionTrace"]] == ["COMPLETED"] * 4
    tool_names = {call["toolName"] for call in report["mcpToolTrace"]}
    assert {"tools/list", "query_prometheus_metrics", "query_application_logs"} <= tool_names
    assert any(row["id"].startswith("prom-") for row in report["infrastructureMetrics"])
    assert any(row["id"].startswith("loki-") for row in report["applicationLogs"])

    status, saved_report = _request(f"{BACKEND}/api/v1/incidents/{incident_id}/report", timeout=30)
    assert status == 200
    assert saved_report["mcpToolTrace"] == report["mcpToolTrace"]
    assert saved_report["telemetryMode"] == "real"
