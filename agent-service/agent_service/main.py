from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .graph.workflow import build_workflow
from .models import IncidentAlert, InvestigationResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("nexus.agent")
settings = get_settings()
workflow = build_workflow(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Agent service started; provider=%s", settings.provider)
    yield


app = FastAPI(title="NEXUS AI Agent Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.allowed_origins.split(",") if x.strip()], allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Authorization"])


@app.get("/health")
async def health():
    return {"status": "UP", "service": "agent-service", "llmProvider": settings.provider, "telemetryMode": settings.telemetry_mode}


@app.post("/investigate", response_model=InvestigationResponse)
async def investigate(alert: IncidentAlert):
    initial_state = {
        "incident_id": alert.incidentId,
        "alert_details": alert.model_dump(by_alias=True),
        "execution_status": "RUNNING",
        "errors": [],
        "execution_trace": [],
    }
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(workflow.invoke, initial_state, {"recursion_limit": 8}),
            timeout=settings.workflow_timeout_seconds,
        )
    except TimeoutError as exc:
        logger.exception("Workflow timed out for incident %s", alert.incidentId)
        raise HTTPException(status_code=504, detail="Agent workflow timed out") from exc
    except Exception as exc:
        logger.exception("Workflow failed for incident %s", alert.incidentId)
        raise HTTPException(status_code=502, detail="Agent workflow failed") from exc

    response = {
        "incidentId": alert.incidentId,
        "severity": result.get("severity", alert.severity),
        "affectedService": result.get("affected_service", alert.serviceName),
        "investigationParameters": result.get("investigation_parameters", []),
        "infrastructureMetrics": result.get("infrastructure_metrics", []),
        "applicationLogs": result.get("application_logs", []),
        "investigationFindings": result.get("investigation_findings", []),
        "probableRootCause": result.get("probable_root_cause", ""),
        "rcaEvidenceIds": result.get("rca_evidence_ids", []),
        "confidenceScore": result.get("confidence_score", 0),
        "reasoning": result.get("reasoning", ""),
        "recommendedActions": result.get("recommended_actions", []),
        "executionStatus": result.get("execution_status", "FAILED"),
        "errors": result.get("errors", []),
        "executionTrace": result.get("execution_trace", []),
        "llmProvider": settings.provider,
        "tokenUsage": result.get("token_usage"),
        "telemetryMode": result.get("telemetry_mode", settings.telemetry_mode),
        "telemetryWindow": result.get("telemetry_window", {}),
        "telemetryEvidence": result.get("telemetry_evidence", {}),
        "mcpToolTrace": result.get("mcp_tool_trace", []),
        "mcpToolCatalog": result.get("mcp_tool_catalog", []),
    }
    try:
        return InvestigationResponse.model_validate(response)
    except Exception as exc:
        logger.exception("Invalid workflow output for incident %s", alert.incidentId)
        raise HTTPException(status_code=502, detail="Agent workflow returned an invalid structured report") from exc

