from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any


class TelemetryIntegrationError(RuntimeError):
    """A configured telemetry endpoint could not provide usable data."""


_LABEL_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
_STEP_VALUE = re.compile(r"^(?:[5-9]|[1-9][0-9]|[1-2][0-9]{2}|300)(?:s|)$")


def validate_label(value: str, label: str) -> str:
    if not isinstance(value, str) or not _LABEL_VALUE.fullmatch(value):
        raise ValueError(f"Invalid {label}; use 1-63 letters, digits, dots, underscores or hyphens")
    return value


def validate_window(start_time: str, end_time: str, maximum_hours: int = 24) -> tuple[datetime, datetime]:
    def parse(value: str, name: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
        if parsed.tzinfo is None:
            raise ValueError(f"{name} must include a timezone")
        return parsed.astimezone(timezone.utc)

    start = parse(start_time, "start_time")
    end = parse(end_time, "end_time")
    if end <= start:
        raise ValueError("end_time must be later than start_time")
    if end - start > timedelta(hours=maximum_hours):
        raise ValueError(f"Time window may not exceed {maximum_hours} hours")
    return start, end


def validate_step(step: str) -> str:
    if not isinstance(step, str) or not _STEP_VALUE.fullmatch(step):
        raise ValueError("step must be between 5s and 300s")
    return step if step.endswith("s") else f"{step}s"


async def request_json(
    base_url: str,
    path: str,
    params: dict[str, Any],
    timeout_seconds: float,
    source_name: str,
) -> dict[str, Any]:
    query = urllib.parse.urlencode({key: value for key, value in params.items() if value is not None})
    url = f"{base_url.rstrip('/')}{path}?{query}"

    def load() -> dict[str, Any]:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise TelemetryIntegrationError(f"{source_name} returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TelemetryIntegrationError(f"{source_name} is unavailable: {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TelemetryIntegrationError(f"{source_name} returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise TelemetryIntegrationError(f"{source_name} returned an unexpected response")
        if payload.get("status") == "error":
            raise TelemetryIntegrationError(f"{source_name} query failed: {payload.get('errorType', 'query error')}")
        return payload

    try:
        return await asyncio.wait_for(asyncio.to_thread(load), timeout=timeout_seconds + 1)
    except TimeoutError as exc:
        raise TelemetryIntegrationError(f"{source_name} request exceeded {timeout_seconds:g}s timeout") from exc


def iso_timestamp(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()


def unix_seconds(value: datetime) -> str:
    return f"{value.timestamp():.3f}"


def unix_nanoseconds(value: datetime) -> str:
    return str(int(value.timestamp() * 1_000_000_000))
