import asyncio

import pytest

from agent_service.config import Settings
from agent_service.mcp.tools.common import validate_label, validate_step, validate_window
from agent_service.mcp.tools.loki_tools import build_logql
from agent_service.mcp.tools.prometheus_tools import build_promql, query_prometheus_metrics


def test_promql_uses_allowlisted_metric_and_validated_labels():
    query = build_promql("cpu_utilization", "payment-service", "production")
    assert query == 'nexus_cpu_utilization_percent{service="payment-service",environment="production"}'
    with pytest.raises(ValueError, match="Unsupported metric_name"):
        build_promql("up; drop database", "payment-service", "production")
    with pytest.raises(ValueError, match="Invalid service_name"):
        validate_label('svc"} or vector(1)', "service_name")


def test_logql_search_is_case_insensitive_and_allowlisted():
    query = build_logql("payment-service", "production", "warn", "thread")
    assert '| level="WARN"' in query
    assert '|~ "(?i)thread"' in query
    with pytest.raises(ValueError, match="Unsupported search_keyword"):
        build_logql("payment-service", "production", None, 'x" or {job=~".*')


def test_time_window_and_step_are_bounded():
    start, end = validate_window("2026-11-01T10:00:00Z", "2026-11-01T10:15:00+00:00")
    assert (end - start).total_seconds() == 900
    assert validate_step("300") == "300s"
    with pytest.raises(ValueError, match="timezone"):
        validate_window("2026-11-01T10:00:00", "2026-11-01T10:15:00Z")
    with pytest.raises(ValueError, match="300s"):
        validate_step("450s")


def test_prometheus_response_is_mapped_to_timestamped_evidence(monkeypatch):
    import agent_service.mcp.tools.prometheus_tools as prometheus_tools

    async def fake_request_json(*_args, **_kwargs):
        return {
            "status": "success",
            "data": {"result": [{
                "metric": {"service": "payment-service", "environment": "production"},
                "values": [[1793527200, "87.5"], [1793527230, "91"]],
            }]},
        }

    monkeypatch.setattr(prometheus_tools, "request_json", fake_request_json)
    result = asyncio.run(query_prometheus_metrics(
        Settings(telemetry_mode="real"),
        "payment-service", "production", "cpu_utilization",
        "2026-11-01T10:00:00Z", "2026-11-01T10:15:00Z", "30s",
    ))
    assert result["available"] is True
    assert result["recordCount"] == 2
    assert result["records"][-1]["value"] == 91.0
    assert result["records"][-1]["source"] == "prometheus"
    assert result["records"][-1]["id"].startswith("prom-")


def test_explicit_mock_telemetry_is_served_through_mock_tool_handlers(monkeypatch):
    import agent_service.mcp.server as mcp_server

    monkeypatch.setattr(mcp_server.settings, "telemetry_mode", "mock")
    logs = asyncio.run(mcp_server.query_application_logs(
        "payment-service", "production", "2026-11-01T10:00:00Z",
        "2026-11-01T10:15:00Z", search_keyword="thread", scenario="threads",
    ))
    health = asyncio.run(mcp_server.get_service_health(
        "payment-service", "production", scenario="threads",
    ))
    assert logs["telemetryMode"] == "mock"
    assert logs["records"] and all(row["source"] == "mock" for row in logs["records"])
    assert health["telemetryMode"] == "mock"
    assert health["p95ResponseLatencySeconds"] == pytest.approx(1.85)


def test_real_mode_tool_reports_source_failure_without_fixture_fallback(monkeypatch):
    import agent_service.mcp.server as mcp_server
    from agent_service.mcp.tools.common import TelemetryIntegrationError

    monkeypatch.setattr(mcp_server.settings, "telemetry_mode", "real")

    async def unavailable(*_args, **_kwargs):
        raise TelemetryIntegrationError("Prometheus is unavailable")

    monkeypatch.setattr(mcp_server, "query_prometheus", unavailable)
    result = asyncio.run(mcp_server.query_prometheus_metrics(
        "payment-service", "production", "cpu_utilization",
        "2026-11-01T10:00:00Z", "2026-11-01T10:15:00Z",
        scenario="threads",
    ))
    assert result["telemetryMode"] == "real"
    assert result["available"] is False
    assert "unavailable" in result["error"]
    assert result["records"] == []
