from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
Risk = Literal["LOW", "MEDIUM", "HIGH"]


class IncidentAlert(BaseModel):
    incidentId: str = Field(min_length=3, max_length=80)
    serviceName: str = Field(min_length=2, max_length=120)
    environment: str = Field(min_length=2, max_length=40)
    alertType: str = Field(min_length=2, max_length=80)
    cpuUtilization: float | None = Field(default=None, ge=0, le=100)
    threshold: float | None = Field(default=None, ge=0, le=100)
    severity: Severity = "HIGH"
    description: str = Field(min_length=5, max_length=2000)


class Finding(BaseModel):
    title: str
    summary: str
    evidenceIds: list[str]


class RecommendedAction(BaseModel):
    title: str
    description: str
    expectedImpact: str
    risk: Risk
    verificationSteps: list[str]


class AgentStep(BaseModel):
    agentName: str
    status: Literal["COMPLETED", "FAILED"]
    startedAt: str
    completedAt: str
    summary: str


class InvestigationResponse(BaseModel):
    incidentId: str
    severity: Severity
    affectedService: str
    investigationParameters: list[str]
    infrastructureMetrics: list[dict[str, Any]]
    applicationLogs: list[dict[str, Any]]
    investigationFindings: list[Finding]
    probableRootCause: str
    rcaEvidenceIds: list[str] = Field(default_factory=list)
    confidenceScore: float = Field(ge=0, le=1)
    reasoning: str
    recommendedActions: list[RecommendedAction]
    executionStatus: Literal["COMPLETED", "FAILED"]
    errors: list[str]
    executionTrace: list[AgentStep]
    llmProvider: str
    tokenUsage: dict[str, int] | None = None
    telemetryMode: Literal["real", "mock"] = "mock"
    telemetryWindow: dict[str, str] = Field(default_factory=dict)
    telemetryEvidence: dict[str, Any] = Field(default_factory=dict)
    mcpToolTrace: list[dict[str, Any]] = Field(default_factory=list)
    mcpToolCatalog: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("confidenceScore")
    @classmethod
    def confidence_is_finite(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("confidenceScore must be between 0 and 1")
        return value

