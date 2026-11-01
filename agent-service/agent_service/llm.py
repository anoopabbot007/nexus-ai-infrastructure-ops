from __future__ import annotations

from typing import TypeVar, Type

from pydantic import BaseModel

from .config import Settings

T = TypeVar("T", bound=BaseModel)


def structured_model(settings: Settings, schema: Type[T]):
    """Return a provider-bound structured model; None means deterministic mock mode."""
    provider = settings.provider
    if provider == "mock":
        return None
    from langchain_openai import AzureChatOpenAI, ChatOpenAI

    if provider == "openai":
        model = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
        )
    else:
        model = AzureChatOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            azure_deployment=settings.azure_openai_deployment,
            api_version=settings.azure_openai_api_version,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
        )
    return model.with_structured_output(schema, include_raw=True)


def invoke_structured(model, messages):
    """Return a parsed schema and provider token counts when exposed by the message."""
    result = model.invoke(messages)
    if not isinstance(result, dict):
        return result, None
    if result.get("parsing_error"):
        raise ValueError("LLM response did not match the required structured schema") from result["parsing_error"]
    raw = result.get("raw")
    usage = getattr(raw, "usage_metadata", None)
    token_usage = None
    if usage:
        token_usage = {
            "inputTokens": int(usage.get("input_tokens", 0)),
            "outputTokens": int(usage.get("output_tokens", 0)),
        }
    return result.get("parsed"), token_usage


def add_token_usage(previous: dict[str, int] | None, current: dict[str, int] | None):
    if not current:
        return previous
    previous = previous or {"inputTokens": 0, "outputTokens": 0}
    return {
        "inputTokens": previous.get("inputTokens", 0) + current.get("inputTokens", 0),
        "outputTokens": previous.get("outputTokens", 0) + current.get("outputTokens", 0),
    }

