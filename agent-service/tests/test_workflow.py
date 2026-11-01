import pytest

from agent_service.agents import rca_agent
from agent_service.config import Settings
from agent_service.graph.workflow import build_workflow
from agent_service.models import IncidentAlert, InvestigationResponse
from agent_service.tools.metrics_tool import SCENARIOS, collect_scenario

SCENARIO_ALERTS = {
    "threads": ("HIGH_CPU", "CPU utilization exceeded 80% for 10 minutes"),
    "memory": ("HIGH_MEMORY", "Memory utilization is above 90% with repeated long GC pauses"),
    "pool": ("DB_POOL_EXHAUSTION", "Database connection pool exhausted with acquisition timeouts"),
    "database_latency": ("DATABASE_LATENCY", "Increased API latency caused by database delays"),
    "dependency": ("DEPENDENCY_FAILURE", "Application errors caused by downstream dependency failures"),
}

def make_alert(alert_type: str, description: str) -> dict:
    return IncidentAlert(incidentId="INC-TEST-1", serviceName="payment-service", environment="production", alertType=alert_type, severity="CRITICAL", description=description, cpuUtilization=94, threshold=80).model_dump(by_alias=True)

@pytest.mark.parametrize("scenario", SCENARIOS)
def test_complete_workflow_for_all_scenarios(scenario):
    alert_type, description = SCENARIO_ALERTS[scenario]
    result = build_workflow(Settings(llm_provider="mock", telemetry_mode="mock")).invoke({"incident_id": "INC-TEST-1", "alert_details": make_alert(alert_type, description), "execution_status": "RUNNING", "errors": [], "execution_trace": []}, {"recursion_limit": 8})
    assert result["execution_status"] == "COMPLETED"
    assert result["scenario"] == scenario
    assert len(result["execution_trace"]) == 4
    assert all(step["status"] == "COMPLETED" for step in result["execution_trace"])
    assert result["recommended_actions"]
    assert 0 <= result["confidence_score"] <= 1
    returned_ids = {item["id"] for item in result["infrastructure_metrics"] + result["application_logs"]}
    assert set(result["rca_evidence_ids"]) <= returned_ids
    assert result["confidence_score"] == round(len(set(result["rca_evidence_ids"])) / len(returned_ids), 2)
    assert SCENARIOS[scenario]["cause"] == result["probable_root_cause"]


def test_rca_explicitly_rejects_missing_logs():
    alert_type, description = SCENARIO_ALERTS["threads"]
    alert = make_alert(alert_type, description)
    state = {"alert_details": alert, **collect_scenario(alert)}
    state["application_logs"] = []

    with pytest.raises(ValueError, match="no application logs"):
        rca_agent.analyze_root_cause(state, Settings(llm_provider="mock"))


def test_rca_explicitly_rejects_missing_findings():
    alert_type, description = SCENARIO_ALERTS["threads"]
    alert = make_alert(alert_type, description)
    state = {"alert_details": alert, **collect_scenario(alert)}
    state["investigation_findings"] = []

    with pytest.raises(ValueError, match="no findings"):
        rca_agent.analyze_root_cause(state, Settings(llm_provider="mock"))


def test_rca_flags_unsupported_cause_even_when_ids_exist(monkeypatch):
    alert_type, description = SCENARIO_ALERTS["threads"]
    alert = make_alert(alert_type, description)
    state = {"alert_details": alert, **collect_scenario(alert)}
    result = rca_agent.RootCauseResult(
        probable_root_cause="An unrelated network cable failure caused this alert.",
        evidence_ids=["cpu-1", "log-1"],
        reasoning="The cause is asserted without matching evidence.",
    )
    monkeypatch.setattr(rca_agent, "structured_model", lambda *_args: object())
    monkeypatch.setattr(rca_agent, "invoke_structured", lambda *_args: (result, None))

    with pytest.raises(ValueError, match="Unsupported RCA conclusion"):
        rca_agent.analyze_root_cause(state, Settings(llm_provider="openai", openai_api_key="test"))


def test_workflow_flags_unsupported_rca_and_stops_before_recommendations(monkeypatch):
    alert_type, description = SCENARIO_ALERTS["threads"]
    alert = make_alert(alert_type, description)
    result = rca_agent.RootCauseResult(
        probable_root_cause="An unrelated network cable failure caused this alert.",
        evidence_ids=["cpu-1", "log-1"],
        reasoning="The cause is asserted without matching evidence.",
    )
    monkeypatch.setattr(rca_agent, "structured_model", lambda *_args: object())
    monkeypatch.setattr(rca_agent, "invoke_structured", lambda *_args: (result, None))

    workflow_result = build_workflow(
        Settings(llm_provider="mock", telemetry_mode="mock")
    ).invoke(
        {
            "incident_id": "INC-UNSUPPORTED-RCA",
            "alert_details": alert,
            "execution_status": "RUNNING",
            "errors": [],
            "execution_trace": [],
        },
        {"recursion_limit": 8},
    )

    assert workflow_result["execution_status"] == "FAILED"
    assert any("Unsupported RCA conclusion" in error for error in workflow_result["errors"])
    assert workflow_result["execution_trace"][-1]["status"] == "FAILED"
    assert "recommended_actions" not in workflow_result


def test_rca_rejects_citations_not_returned_by_tools(monkeypatch):
    alert_type, description = SCENARIO_ALERTS["threads"]
    alert = make_alert(alert_type, description)
    state = {"alert_details": alert, **collect_scenario(alert)}
    result = rca_agent.RootCauseResult(
        probable_root_cause=SCENARIOS["threads"]["cause"],
        evidence_ids=["cpu-1", "log-2", "invented-1"],
        reasoning="This intentionally includes a fabricated evidence ID.",
    )
    monkeypatch.setattr(rca_agent, "structured_model", lambda *_args: object())
    monkeypatch.setattr(rca_agent, "invoke_structured", lambda *_args: (result, None))

    with pytest.raises(ValueError, match="not returned by investigation tools"):
        rca_agent.analyze_root_cause(state, Settings(llm_provider="openai", openai_api_key="test"))


def test_rca_retries_cause_when_scenario_indicators_are_omitted(monkeypatch):
    alert_type, description = SCENARIO_ALERTS["threads"]
    alert = make_alert(alert_type, description)
    state = {"alert_details": alert, **collect_scenario(alert)}
    invalid = rca_agent.RootCauseResult(
        probable_root_cause="Performance degradation followed increased resource pressure.",
        evidence_ids=["cpu-1", "log-2"],
        reasoning="The initial conclusion omitted required scenario indicators.",
    )
    corrected = rca_agent.RootCauseResult(
        probable_root_cause=(
            "JVM executor thread growth increased CPU utilization and expanded "
            "the request queue backlog."
        ),
        evidence_ids=["cpu-1", "log-2"],
        reasoning="Thread growth, CPU saturation, and queue growth are present in the cited evidence.",
    )
    responses = [
        (invalid, {"inputTokens": 5, "outputTokens": 4}),
        (corrected, {"inputTokens": 7, "outputTokens": 3}),
    ]
    calls = []

    monkeypatch.setattr(rca_agent, "structured_model", lambda *_args: object())

    def invoke_with_correction(_model, messages):
        calls.append(messages)
        return responses[len(calls) - 1]

    monkeypatch.setattr(rca_agent, "invoke_structured", invoke_with_correction)

    analyzed = rca_agent.analyze_root_cause(
        state, Settings(llm_provider="openai", openai_api_key="test")
    )

    assert len(calls) == 2
    assert "required_root_cause_indicator_groups" in calls[0][1].content
    assert "required_root_cause_indicator_groups" in calls[1][-1].content
    assert analyzed["probable_root_cause"] == corrected.probable_root_cause
    assert analyzed["rca_evidence_ids"] == ["cpu-1", "log-2"]
    assert analyzed["token_usage"] == {"inputTokens": 12, "outputTokens": 7}


def test_rca_reports_cited_evidence_coverage_not_model_confidence(monkeypatch):
    alert_type, description = SCENARIO_ALERTS["threads"]
    alert = make_alert(alert_type, description)
    state = {"alert_details": alert, **collect_scenario(alert)}
    result = rca_agent.RootCauseResult(
        probable_root_cause="Application thread growth drives CPU saturation and request queue growth.",
        evidence_ids=["cpu-1", "log-2"],
        reasoning="The cited CPU metric and thread-queue log corroborate the scenario.",
    )
    monkeypatch.setattr(rca_agent, "structured_model", lambda *_args: object())
    monkeypatch.setattr(rca_agent, "invoke_structured", lambda *_args: (result, None))

    analyzed = rca_agent.analyze_root_cause(
        state, Settings(llm_provider="openai", openai_api_key="test")
    )

    assert analyzed["rca_evidence_ids"] == ["cpu-1", "log-2"]
    assert analyzed["confidence_score"] == round(2 / 6, 2)

def test_response_schema_rejects_confidence_outside_range():
    with pytest.raises(ValueError):
        InvestigationResponse.model_validate({"incidentId": "INC-1", "severity": "HIGH", "affectedService": "orders", "investigationParameters": [], "infrastructureMetrics": [], "applicationLogs": [], "investigationFindings": [], "probableRootCause": "unknown", "confidenceScore": 1.5, "reasoning": "n/a", "recommendedActions": [], "executionStatus": "COMPLETED", "errors": [], "executionTrace": [], "llmProvider": "mock"})

def test_agent_failure_is_traced_and_workflow_stops(monkeypatch):
    import agent_service.graph.workflow as workflow_module
    def fail_alert(*_args):
        raise RuntimeError("simulated transient provider failure")
    monkeypatch.setattr(workflow_module, "analyze_alert", fail_alert)
    alert_type, description = SCENARIO_ALERTS["threads"]
    result = build_workflow(Settings(llm_provider="mock", telemetry_mode="mock")).invoke({"incident_id": "INC-TEST-2", "alert_details": make_alert(alert_type, description), "execution_status": "RUNNING", "errors": [], "execution_trace": []}, {"recursion_limit": 8})
    assert result["execution_status"] == "FAILED"
    assert "simulated transient provider failure" in result["errors"][0]
    assert len(result["execution_trace"]) == 1
    assert result["execution_trace"][0]["status"] == "FAILED"

def test_investigation_retries_a_transient_tool_failure(monkeypatch):
    import agent_service.agents.investigation_agent as investigation_module
    actual = investigation_module.collect_via_mcp
    calls = {"count": 0}
    def flaky(settings, alert):
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("temporary tool timeout")
        return actual(settings, alert)
    monkeypatch.setattr(investigation_module, "collect_via_mcp", flaky)
    alert_type, description = SCENARIO_ALERTS["threads"]
    result = build_workflow(Settings(llm_provider="mock", telemetry_mode="mock")).invoke({"incident_id": "INC-RETRY", "alert_details": make_alert(alert_type, description), "execution_status": "RUNNING", "errors": [], "execution_trace": []}, {"recursion_limit": 8})
    assert result["execution_status"] == "COMPLETED"
    assert calls["count"] == 2
