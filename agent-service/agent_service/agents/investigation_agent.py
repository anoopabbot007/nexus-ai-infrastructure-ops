from __future__ import annotations

from ..mcp.client import collect_via_mcp


def investigate(state: dict, settings) -> dict:
    """Discover and invoke telemetry tools through the NEXUS MCP server."""
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            return collect_via_mcp(settings, state["alert_details"])
        except Exception as exc:
            last_error = exc
            if attempt == 1:
                raise
    assert last_error is not None
    raise last_error
