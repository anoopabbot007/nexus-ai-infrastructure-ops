from __future__ import annotations

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import add_token_usage, invoke_structured, structured_model
from ..models import RecommendedAction


class RecommendationResult(BaseModel):
    actions: list[RecommendedAction] = Field(min_length=1, max_length=5)


RECOMMENDATIONS = {
    "threads": [RecommendedAction(title="Review thread-pool sizing", description="Inspect thread creation and executor configuration, then cap concurrency and queue growth through the normal change process.", expectedImpact="Reduce CPU contention and request queue pressure.", risk="MEDIUM", verificationSteps=["Compare live thread count to the service baseline.", "Confirm CPU and p95 latency return toward baseline."])],
    "memory": [RecommendedAction(title="Review JVM heap and allocation behavior", description="Inspect heap sizing and allocation hot paths; validate any configuration change in a controlled environment.", expectedImpact="Reduce full-GC frequency and pause duration.", risk="MEDIUM", verificationSteps=["Track old-generation occupancy and GC pause percentiles.", "Check memory headroom after representative load."])],
    "pool": [RecommendedAction(title="Investigate database pool saturation", description="Review connection leaks, query duration, and pool sizing before considering a capacity change.", expectedImpact="Reduce connection wait timeouts and restore request throughput.", risk="HIGH", verificationSteps=["Confirm active connections and waiters decline.", "Verify database capacity and error rate remain healthy."])],
    "database_latency": [RecommendedAction(title="Analyze slow database queries", description="Review the slow order lookup query plan and database load; validate an index or query change before release.", expectedImpact="Lower database query duration and API response latency.", risk="MEDIUM", verificationSteps=["Compare query p95 to its baseline.", "Confirm API p95 improves without increasing database load."])],
    "dependency": [RecommendedAction(title="Review downstream dependency health", description="Coordinate with the fraud-check dependency owner and verify timeout and circuit-breaker behavior; do not bypass safeguards without review.", expectedImpact="Reduce downstream-related application errors and latency.", risk="MEDIUM", verificationSteps=["Confirm dependency 5xx rate returns toward baseline.", "Verify circuit-breaker state and application error rate."])],
}


def recommend(state: dict, settings) -> dict:
    model = structured_model(settings, RecommendationResult)
    if model:
        result, usage = invoke_structured(model, [
            SystemMessage(content="Recommend safe, human-approved operational actions. Never execute changes. Include impact, risk, and verification steps."),
            HumanMessage(content=str({"root_cause": state["probable_root_cause"], "reasoning": state["reasoning"], "evidence_ids": state["rca_evidence_ids"], "metrics": state["infrastructure_metrics"]})),
        ])
    else:
        usage = None
        root_cause = state.get("probable_root_cause", "")
        actions = RECOMMENDATIONS[state["scenario"]]
        if root_cause:
            actions = [
                action.model_copy(update={
                    "description": f"{action.description} This recommendation addresses the RCA: {root_cause}"
                })
                for action in actions
            ]
        result = RecommendationResult(actions=actions)
    return {"recommended_actions": [action.model_dump(by_alias=True) for action in result.actions], "token_usage": add_token_usage(state.get("token_usage"), usage)}

