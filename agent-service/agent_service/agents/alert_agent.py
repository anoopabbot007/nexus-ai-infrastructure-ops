from __future__ import annotations

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import add_token_usage, invoke_structured, structured_model
from ..models import IncidentAlert, Severity


class AlertAnalysis(BaseModel):
    affected_service: str
    severity: Severity
    investigation_parameters: list[str] = Field(min_length=1)
    summary: str


def analyze_alert(state: dict, settings) -> dict:
    alert = IncidentAlert.model_validate(state["alert_details"])
    model = structured_model(settings, AlertAnalysis)
    if model:
        result, usage = invoke_structured(model, [
            SystemMessage(content="Analyze the alert. Use only details in the input; choose practical investigation parameters. Return the requested structured fields."),
            HumanMessage(content=alert.model_dump_json()),
        ])
    else:
        usage = None
        result = AlertAnalysis(
            affected_service=alert.serviceName,
            severity=alert.severity,
            investigation_parameters=["cpu", "memory", "response_latency", "application_logs", "service_health"],
            summary=f"{alert.severity} {alert.alertType} alert for {alert.serviceName} in {alert.environment}.",
        )
    return {
        "affected_service": result.affected_service,
        "severity": result.severity,
        "investigation_parameters": result.investigation_parameters,
        "alert_summary": result.summary,
        "token_usage": add_token_usage(state.get("token_usage"), usage),
    }

