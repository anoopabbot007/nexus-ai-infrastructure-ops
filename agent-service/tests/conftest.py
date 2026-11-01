import pytest

from agent_service.tools.metrics_tool import collect_scenario


@pytest.fixture(autouse=True)
def use_explicit_mock_telemetry(monkeypatch):
    """Keep workflow unit tests isolated from the external Streamable HTTP service."""
    import agent_service.agents.investigation_agent as investigation_agent

    def collect(_settings, alert):
        return {
            **collect_scenario(alert),
            "telemetry_mode": "mock",
            "telemetry_window": {},
            "telemetry_evidence": {},
            "mcp_tool_trace": [],
            "mcp_tool_catalog": [],
        }

    monkeypatch.setattr(investigation_agent, "collect_via_mcp", collect)
