from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from langgraph.graph import END, START, StateGraph

from ..agents.alert_agent import analyze_alert
from ..agents.investigation_agent import investigate
from ..agents.rca_agent import analyze_root_cause
from ..agents.recommendation_agent import recommend
from ..config import Settings
from .state import IncidentState


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_workflow(settings: Settings):
    graph = StateGraph(IncidentState)
    agents: list[tuple[str, Callable]] = [
        ("Alert Analysis Agent", lambda state: analyze_alert(state, settings)),
        ("Investigation Agent", lambda state: investigate(state, settings)),
        ("Root Cause Analysis Agent", lambda state: analyze_root_cause(state, settings)),
        ("Remediation Recommendation Agent", lambda state: recommend(state, settings)),
    ]

    for index, (name, worker) in enumerate(agents):
        def node(state: IncidentState, *, _name=name, _worker=worker):
            started = _now()
            try:
                update = _worker(state)
                step = {"agentName": _name, "status": "COMPLETED", "startedAt": started, "completedAt": _now(), "summary": _summary(_name, update)}
                return {**update, "execution_trace": state.get("execution_trace", []) + [step]}
            except Exception as exc:
                step = {"agentName": _name, "status": "FAILED", "startedAt": started, "completedAt": _now(), "summary": str(exc)[:300]}
                update = {
                    "errors": state.get("errors", []) + [f"{_name}: {exc}"],
                    "execution_status": "FAILED",
                    "execution_trace": state.get("execution_trace", []) + [step],
                }
                if hasattr(exc, "mcp_tool_trace"):
                    update["mcp_tool_trace"] = exc.mcp_tool_trace
                    update["mcp_tool_catalog"] = exc.mcp_tool_catalog
                    update["telemetry_window"] = exc.telemetry_window
                return update

        graph.add_node(f"agent_{index}", node)
        if index > 0:
            graph.add_conditional_edges(f"agent_{index - 1}", _continue_or_end, {"continue": f"agent_{index}", "end": END})
    graph.add_conditional_edges("agent_3", _continue_or_end, {"continue": "report", "end": END})
    graph.add_node("report", lambda state: {"execution_status": "COMPLETED"})
    graph.add_edge(START, "agent_0")
    graph.add_edge("report", END)
    return graph.compile()


def _continue_or_end(state: IncidentState) -> str:
    return "end" if state.get("execution_status") == "FAILED" else "continue"


def _summary(name: str, update: dict) -> str:
    if name == "Alert Analysis Agent":
        return update.get("alert_summary", "Alert analyzed")
    if name == "Investigation Agent":
        mode = update.get("telemetry_mode", "mock").upper()
        return f"{mode}: collected {len(update.get('infrastructure_metrics', []))} metrics and {len(update.get('application_logs', []))} logs for {update.get('scenario')} scenario via MCP."
    if name == "Root Cause Analysis Agent":
        return update.get("probable_root_cause", "Root cause analyzed")
    return f"Prepared {len(update.get('recommended_actions', []))} recommended action(s)."

