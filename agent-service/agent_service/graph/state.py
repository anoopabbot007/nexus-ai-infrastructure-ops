from __future__ import annotations

from typing import Any, TypedDict


class IncidentState(TypedDict, total=False):
    incident_id: str
    alert_details: dict[str, Any]
    severity: str
    affected_service: str
    investigation_parameters: list[str]
    alert_summary: str
    scenario: str
    infrastructure_metrics: list[dict[str, Any]]
    application_logs: list[dict[str, Any]]
    investigation_findings: list[dict[str, Any]]
    probable_root_cause: str
    confidence_score: float
    reasoning: str
    rca_evidence_ids: list[str]
    recommended_actions: list[dict[str, Any]]
    execution_status: str
    errors: list[str]
    execution_trace: list[dict[str, str]]
    token_usage: dict[str, int]

    telemetry_mode: str
    telemetry_window: dict[str, str]
    telemetry_evidence: dict[str, Any]
    mcp_tool_trace: list[dict[str, Any]]
    mcp_tool_catalog: list[dict[str, Any]]