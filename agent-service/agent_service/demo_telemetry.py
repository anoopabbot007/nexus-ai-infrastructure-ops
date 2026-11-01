from __future__ import annotations

import asyncio
import gc
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app


SERVICE = os.getenv("DEMO_SERVICE_NAME", "payment-service")
ENVIRONMENT = os.getenv("DEMO_ENVIRONMENT", "production")
LOG_FILE = Path(os.getenv("NEXUS_LOG_FILE", "/var/log/nexus/demo.jsonl"))
MEMORY_BUDGET_BYTES = max(8, int(os.getenv("DEMO_MEMORY_BUDGET_MB", "64"))) * 1024 * 1024
_memory_payloads: list[bytearray] = []
_log_lock = threading.Lock()

REQUESTS = Counter(
    "nexus_http_requests", "Observed demo HTTP requests", ["service", "environment", "route"]
)
ERRORS = Counter(
    "nexus_http_errors", "Observed demo HTTP error responses", ["service", "environment", "route"]
)
REQUEST_DURATION = Histogram(
    "nexus_http_request_duration_seconds",
    "Observed demo HTTP request duration",
    ["service", "environment", "route"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)
CPU_UTILIZATION = Gauge(
    "nexus_cpu_utilization_percent", "Measured demo process CPU busy percentage", ["service", "environment"]
)
MEMORY_UTILIZATION = Gauge(
    "nexus_memory_utilization_percent", "Demo process allocation versus configured demo memory budget", ["service", "environment"]
)
JVM_HEAP_UTILIZATION = Gauge(
    "nexus_jvm_heap_utilization_percent", "JVM heap utilization when a JVM exporter is configured", ["service", "environment"]
)
ACTIVE_THREADS = Gauge(
    "nexus_active_threads", "Observed active worker threads in the demo process", ["service", "environment"]
)
GC_PAUSE = Gauge(
    "nexus_gc_pause_seconds", "Measured Python garbage collection duration for the demo process", ["service", "environment"]
)
DB_POOL_UTILIZATION = Gauge(
    "nexus_db_pool_utilization_percent", "Observed demo database-pool utilization peak", ["service", "environment"]
)
DB_POOL_WAITERS = Gauge(
    "nexus_db_pool_waiters", "Observed peak number of waiting demo database requests", ["service", "environment"]
)
DATABASE_QUERY_DURATION = Histogram(
    "nexus_database_query_duration_seconds", "Observed demo database query duration", ["service", "environment"]
)
DOWNSTREAM_DURATION = Histogram(
    "nexus_downstream_request_duration_seconds", "Observed demo downstream call duration", ["service", "environment"]
)

app = FastAPI(title="NEXUS Demo Telemetry Application", version="1.0.0")
app.mount("/metrics", make_asgi_app())


def _labels():
    return {"service": SERVICE, "environment": ENVIRONMENT}


def _emit_log(level: str, message: str) -> dict[str, Any]:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "service": SERVICE,
        "environment": ENVIRONMENT,
        "level": level.upper(),
        "message": message,
    }
    line = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _log_lock:
        with LOG_FILE.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
            stream.flush()
    print(line, flush=True)
    return event


@app.middleware("http")
async def record_http_metrics(request: Request, call_next):
    path = request.url.path
    if path in {"/health", "/metrics", "/metrics/"}:
        return await call_next(request)
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    route = getattr(request.scope.get("route"), "path", path)
    REQUESTS.labels(SERVICE, ENVIRONMENT, route).inc()
    REQUEST_DURATION.labels(SERVICE, ENVIRONMENT, route).observe(elapsed)
    if response.status_code >= 400:
        ERRORS.labels(SERVICE, ENVIRONMENT, route).inc()
    return response


@app.get("/health")
async def health():
    return {"status": "UP", "service": SERVICE, "environment": ENVIRONMENT}


def _burn_cpu(until: float) -> None:
    ACTIVE_THREADS.labels(SERVICE, ENVIRONMENT).set(threading.active_count())
    value = 0.0
    while time.perf_counter() < until:
        value = (value + 1.61803398875) % 1000.0
    if value < 0:
        raise RuntimeError("unreachable")


@app.post("/demo/scenarios/{scenario}")
async def trigger_scenario(scenario: str):
    supported = {"threads", "memory", "pool", "database_latency", "dependency"}
    if scenario not in supported:
        raise HTTPException(status_code=400, detail=f"Unsupported scenario. Choose one of: {', '.join(sorted(supported))}")

    labels = _labels()
    observed: dict[str, Any] = {"scenario": scenario, "service": SERVICE, "environment": ENVIRONMENT}

    if scenario == "threads":
        wall_start = time.perf_counter()
        cpu_start = time.process_time()
        end = wall_start + 1.5
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="nexus-demo-worker") as pool:
            await asyncio.gather(*[
                loop.run_in_executor(pool, _burn_cpu, end)
                for _ in range(4)
            ])
        elapsed_wall = max(time.perf_counter() - wall_start, 0.001)
        measured_cpu = time.process_time() - cpu_start
        cpu_percent = min(100.0, max(0.0, measured_cpu / elapsed_wall * 100.0))
        CPU_UTILIZATION.labels(**labels).set(cpu_percent)
        # Keep the measured peak available long enough for a normal scrape cycle
        # and subsequent incident investigation to observe it.
        peak_threads = max(5, threading.active_count())
        ACTIVE_THREADS.labels(**labels).set(peak_threads)
        observed.update({"cpuUtilizationPercent": cpu_percent, "activeThreads": peak_threads})
        _emit_log("WARN", f"Thread pool saturation observed during CPU workload; measured CPU utilization {cpu_percent:.1f}%.")
        _emit_log("WARN", "Request queue depth increased while demo worker threads were busy.")
        asyncio.create_task(_reset_thread_signal(labels, 120))

    elif scenario == "memory":
        allocated = sum(len(payload) for payload in _memory_payloads)
        target_bytes = int(MEMORY_BUDGET_BYTES * 0.92)
        additional = max(0, target_bytes - allocated)
        payload = bytearray(additional)
        for offset in range(0, len(payload), 4096):
            payload[offset] = 1
        _memory_payloads.append(payload)
        utilization = min(100.0, sum(len(item) for item in _memory_payloads) / MEMORY_BUDGET_BYTES * 100.0)
        MEMORY_UTILIZATION.labels(**labels).set(utilization)
        gc_started = time.perf_counter()
        gc.collect()
        gc_pause = time.perf_counter() - gc_started
        GC_PAUSE.labels(**labels).set(gc_pause)
        observed.update({"memoryUtilizationPercent": utilization, "gcPauseSeconds": gc_pause})
        _emit_log("WARN", f"Demo memory pressure reached {utilization:.1f}% of its configured allocation budget.")
        _emit_log("WARN", f"Python GC (garbage collection) completed; measured pause was {gc_pause:.6f} seconds.")
        asyncio.create_task(_release_memory(payload, 120))

    elif scenario == "pool":
        capacity = 1
        semaphore = asyncio.Semaphore(capacity)
        active = 0
        waiting = 0
        max_waiting = 0
        max_utilization = 0.0

        async def acquire_demo_connection() -> None:
            nonlocal active, waiting, max_waiting, max_utilization
            waiting += 1
            max_waiting = max(max_waiting, waiting)
            DB_POOL_WAITERS.labels(**labels).set(max_waiting)
            try:
                await asyncio.wait_for(semaphore.acquire(), timeout=0.08)
            except TimeoutError:
                _emit_log("ERROR", "Database connection acquisition timed out while the demo pool was saturated.")
                return
            waiting -= 1
            active += 1
            max_utilization = max(max_utilization, active / capacity * 100.0)
            DB_POOL_UTILIZATION.labels(**labels).set(max_utilization)
            try:
                await asyncio.sleep(0.25)
            finally:
                active -= 1
                semaphore.release()

        await asyncio.gather(*(acquire_demo_connection() for _ in range(5)))
        observed.update({"poolUtilizationPercent": max_utilization, "peakWaiters": max_waiting})
        _emit_log("WARN", f"Database connection pool pressure observed with {max_waiting} waiting requests.")

    elif scenario == "database_latency":
        started = time.perf_counter()
        await asyncio.sleep(0.8)
        elapsed = time.perf_counter() - started
        DATABASE_QUERY_DURATION.labels(**labels).observe(elapsed)
        DOWNSTREAM_DURATION.labels(**labels).observe(elapsed)
        observed["databaseQueryDurationSeconds"] = elapsed
        _emit_log("WARN", f"Slow database query observed; measured duration was {elapsed:.3f} seconds.")
        _emit_log("WARN", "Database response time dominated the demo request span.")

    elif scenario == "dependency":
        started = time.perf_counter()
        await asyncio.sleep(0.15)
        elapsed = time.perf_counter() - started
        DOWNSTREAM_DURATION.labels(**labels).observe(elapsed)
        observed["downstreamDurationSeconds"] = elapsed
        _emit_log("ERROR", "Connection refused by the demo downstream dependency.")
        _emit_log("ERROR", "Downstream dependency returned HTTP 503; demo circuit breaker opened.")
        return JSONResponse(status_code=503, content={**observed, "status": "DEPENDENCY_UNAVAILABLE"})

    return {"status": "SCENARIO_SIGNAL_EMITTED", **observed}


async def _release_memory(payload: bytearray, delay_seconds: int) -> None:
    await asyncio.sleep(delay_seconds)
    try:
        _memory_payloads.remove(payload)
    except ValueError:
        return
    utilization = min(100.0, sum(len(item) for item in _memory_payloads) / MEMORY_BUDGET_BYTES * 100.0)
    MEMORY_UTILIZATION.labels(SERVICE, ENVIRONMENT).set(utilization)


async def _reset_thread_signal(labels: dict[str, str], delay_seconds: int) -> None:
    await asyncio.sleep(delay_seconds)
    CPU_UTILIZATION.labels(**labels).set(0)
    ACTIVE_THREADS.labels(**labels).set(1)
