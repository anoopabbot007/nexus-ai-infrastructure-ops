from __future__ import annotations

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import add_token_usage, invoke_structured, structured_model
from ..tools.metrics_tool import SCENARIOS


class RootCauseResult(BaseModel):
    probable_root_cause: str = Field(min_length=10)
    evidence_ids: list[str] = Field(min_length=1)
    reasoning: str = Field(min_length=1)


# These checks are intentionally conservative lexical guards for the five
# supported deterministic scenarios. They catch missing or contradictory
# evidence; they are not a substitute for expert semantic review.
SCENARIO_SUPPORT = {
    "threads": {
        "cause": (("thread", "executor"), ("cpu",), ("queue", "backlog")),
        "evidence": (("thread",), ("cpu",), ("queue", "latency")),
    },
    "memory": {
        "cause": (("memory", "heap"), ("gc", "garbage collection")),
        "evidence": (("memory", "heap"), ("gc", "garbage collection")),
    },
    "pool": {
        "cause": (("connection",), ("pool",), ("exhaust", "timeout", "wait")),
        "evidence": (("connection",), ("pool",), ("timeout", "waiter")),
    },
    "database_latency": {
        "cause": (("database", "db "), ("query",), ("latency", "delay")),
        "evidence": (("query",), ("database", "latency"), ("slow", "duration")),
    },
    "dependency": {
        "cause": (("dependency", "downstream"), ("failure", "error"), ("latency", "timeout")),
        "evidence": (("dependency", "downstream"), ("503", "error"), ("circuit", "latency")),
    },
}


def _normalise(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").replace("-", " ").split())


def _matches_all_groups(text: str, groups: tuple[tuple[str, ...], ...]) -> bool:
    normalized = _normalise(text)
    return all(any(_normalise(term) in normalized for term in group) for group in groups)


def _tool_evidence(metrics: list[dict], logs: list[dict]) -> dict[str, tuple[str, dict]]:
    if not metrics:
        raise ValueError("RCA cannot run: investigation returned no infrastructure metrics")
    if not logs:
        raise ValueError("RCA cannot run: investigation returned no application logs")

    evidence: dict[str, tuple[str, dict]] = {}
    for source, rows in (("metric", metrics), ("log", logs)):
        for row in rows:
            evidence_id = row.get("id")
            if not isinstance(evidence_id, str) or not evidence_id.strip():
                raise ValueError(f"RCA cannot verify tool evidence: a {source} has no non-empty ID")
            if evidence_id in evidence:
                raise ValueError(f"RCA cannot verify tool evidence: duplicate ID {evidence_id}")
            evidence[evidence_id] = (source, row)
    return evidence


def _validate_scenario_support(scenario: str, cause: str, cited_evidence: list[tuple[str, dict]]) -> None:
    support = SCENARIO_SUPPORT.get(scenario)
    if support is None:
        raise ValueError(f"RCA cannot validate unsupported scenario: {scenario}")

    evidence_text = " ".join(
        f"{evidence_id} {row}" for evidence_id, row in cited_evidence
    )
    if not _matches_all_groups(cause, support["cause"]):
        raise ValueError(
            f"Unsupported RCA conclusion for {scenario}: the cause omits expected scenario indicators"
        )
    if not _matches_all_groups(evidence_text, support["evidence"]):
        raise ValueError(
            f"Unsupported RCA conclusion for {scenario}: cited tool evidence lacks expected indicators"
        )


def _validate_rca_result(
    scenario: str,
    result: RootCauseResult,
    evidence: dict[str, tuple[str, dict]],
) -> list[str]:
    cited_ids = list(dict.fromkeys(result.evidence_ids))
    unknown_ids = set(cited_ids) - evidence.keys()
    if unknown_ids:
        raise ValueError(
            "RCA cited evidence IDs that were not returned by investigation tools: "
            + ", ".join(sorted(unknown_ids))
        )

    cited_evidence = [(evidence_id, evidence[evidence_id][1]) for evidence_id in cited_ids]
    cited_sources = {evidence[evidence_id][0] for evidence_id in cited_ids}
    if not {"metric", "log"}.issubset(cited_sources):
        raise ValueError("RCA requires citations to both metric and application-log evidence")
    _validate_scenario_support(scenario, result.probable_root_cause, cited_evidence)
    return cited_ids

def analyze_root_cause(state: dict, settings) -> dict:
    metrics = state.get("infrastructure_metrics") or []
    logs = state.get("application_logs") or []
    evidence = _tool_evidence(metrics, logs)

    findings = state.get("investigation_findings") or []
    if not findings:
        raise ValueError("RCA cannot run: investigation returned no findings")
    for finding in findings:
        finding_ids = finding.get("evidenceIds", finding.get("evidence_ids", [])) or []
        missing_finding_ids = set(finding_ids) - evidence.keys()
        if missing_finding_ids:
            raise ValueError(
                "Investigation findings cite IDs absent from tool output: "
                + ", ".join(sorted(missing_finding_ids))
            )

    scenario = state.get("scenario", "")
    scenario_data = SCENARIOS.get(scenario)
    if scenario_data is None:
        raise ValueError(f"RCA cannot validate unsupported scenario: {scenario}")
    telemetry_mode = state.get("telemetry_mode", settings.telemetry_mode)
    if telemetry_mode == "mock":
        missing_expected = set(scenario_data["evidence"]) - evidence.keys()
        if missing_expected:
            raise ValueError(
                "RCA cannot run: required mock investigation evidence is missing: "
                + ", ".join(sorted(missing_expected))
            )

    model = structured_model(settings, RootCauseResult)
    if model:
        required_cause_indicators = [
            list(group) for group in SCENARIO_SUPPORT[scenario]["cause"]
        ]
        prompt = {
            "scenario": scenario,
            "required_root_cause_indicator_groups": required_cause_indicators,
            "alert": state["alert_details"],
            "metrics": metrics,
            "logs": logs,
            "findings": findings,
            "instruction": (
                "Return a probable cause only when the cited metric and log evidence "
                "support the scenario indicators. In probable_root_cause itself, include "
                "at least one exact term from every required_root_cause_indicator_groups "
                "group. Explain only what the supplied evidence supports. Cite IDs from "
                "the supplied tool output only. The application computes evidence "
                "coverage; do not estimate confidence."
            ),
        }
        messages = [
            SystemMessage(content=(
                "You are an infrastructure root-cause analyst. Correlate only supplied "
                "evidence. Include at least one listed scenario indicator from every "
                "required group in the root-cause statement."
            )),
            HumanMessage(content=str(prompt)),
        ]
        result, usage = invoke_structured(model, messages)
    else:
        usage = None
        evidence_ids = (
            scenario_data["evidence"]
            if telemetry_mode == "mock"
            else list(evidence.keys())
        )
        result = RootCauseResult(
            probable_root_cause=scenario_data["cause"],
            evidence_ids=evidence_ids,
            reasoning=scenario_data["reasoning"],
        )

    try:
        cited_ids = _validate_rca_result(scenario, result, evidence)
    except ValueError as exc:
        cause_indicator_error = (
            f"Unsupported RCA conclusion for {scenario}: "
            "the cause omits expected scenario indicators"
        )
        if model is None or str(exc) != cause_indicator_error:
            raise

        correction = {
            "task": (
                "Revise the RCA result because its root-cause wording omitted required "
                "scenario indicators. Keep the conclusion grounded in the same evidence."
            ),
            "scenario": scenario,
            "required_root_cause_indicator_groups": required_cause_indicators,
            "previous_result": result.model_dump(),
            "validation_error": str(exc),
            "instruction": (
                "Return a corrected structured result. Include at least one exact term "
                "from every required indicator group in probable_root_cause itself. Keep "
                "evidence IDs limited to the supplied tool outputs; do not add claims "
                "that those metrics and logs do not support."
            ),
        }
        result, retry_usage = invoke_structured(
            model,
            messages + [HumanMessage(content=str(correction))],
        )
        usage = add_token_usage(usage, retry_usage)
        cited_ids = _validate_rca_result(scenario, result, evidence)

    # Kept under confidence_score for API compatibility. This is the fraction
    # of available tool evidence cited, not a calibrated probability.
    evidence_coverage = round(len(cited_ids) / len(evidence), 2)
    return {
        "probable_root_cause": result.probable_root_cause,
        "confidence_score": evidence_coverage,
        "reasoning": result.reasoning,
        "rca_evidence_ids": cited_ids,
        "token_usage": add_token_usage(state.get("token_usage"), usage),
    }
