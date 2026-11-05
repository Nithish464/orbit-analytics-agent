
import logging
import os
import time
from datetime import datetime, timezone
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .database import initialize_database, get_schema
from .schemas import AskRequest
from .agents import execute_workflow, EXAMPLES
from .ollama_client import check_ollama, close_ollama_client


logger = logging.getLogger(__name__)


app = FastAPI(
    title="ORBIT Analytics Agent API",
    description=(
        "Local-first natural-language analytics workflow "
        "with read-only SQL execution and local AI support."
    ),
    version="1.3.0",
)


# ============================================================
# CORS CONFIGURATION
# ============================================================

_DEFAULT_ORIGINS = (
    "http://localhost:5173,"
    "http://127.0.0.1:5173,"
    "http://localhost:5174,"
    "http://127.0.0.1:5174"
)

_allowed_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "ORBIT_CORS_ORIGINS",
        _DEFAULT_ORIGINS,
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)


# ============================================================
# REQUEST HISTORY
# ============================================================

_history: list[dict] = []
_history_lock = Lock()

MAX_HISTORY_ITEMS = 100
HISTORY_RESPONSE_ITEMS = 12


# ============================================================
# PERFORMANCE METRICS
# ============================================================

_performance_records: list[dict] = []
_performance_lock = Lock()

MAX_PERFORMANCE_RECORDS = 500
PERFORMANCE_TREND_ITEMS = 20


def _record_performance(
    *,
    status: str,
    api_duration_ms: float,
    workflow_result: dict | None = None,
) -> None:
    """Store bounded, thread-safe API performance measurements."""

    result = workflow_result or {}

    ai_duration = result.get("ai_duration_ms", 0.0)
    sql_duration = result.get("sql_duration_ms", 0.0)

    cache_hit = result.get("cache_hit")

    # Count a cache miss only when AI generation was attempted.
    # Deterministic fallback and skipped AI are not cache misses.
    ai_attempted = (
        isinstance(ai_duration, (int, float))
        and ai_duration > 0
    )

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "api_duration_ms": round(api_duration_ms, 2),
        "workflow_duration_ms": result.get("duration_ms", 0.0),
        "sql_duration_ms": sql_duration,
        "ai_duration_ms": ai_duration,
        "cache_hit": (
            bool(cache_hit)
            if cache_hit is not None
            else None
        ),
        "ai_attempted": ai_attempted,
        "row_count": result.get("row_count", 0),
    }

    with _performance_lock:
        _performance_records.append(record)

        if len(_performance_records) > MAX_PERFORMANCE_RECORDS:
            del _performance_records[
                :-MAX_PERFORMANCE_RECORDS
            ]


def _average(values: list[float]) -> float:
    """Calculate a safe arithmetic average."""

    if not values:
        return 0.0

    return round(sum(values) / len(values), 2)


def _percentile_95(values: list[float]) -> float:
    """Calculate the nearest-rank 95th percentile."""

    if not values:
        return 0.0

    ordered = sorted(values)

    index = max(
        0,
        int(len(ordered) * 0.95 + 0.999999) - 1,
    )

    return round(ordered[index], 2)


def get_performance_snapshot() -> dict:
    """Build an aggregate snapshot from recorded API requests."""

    with _performance_lock:
        records = [
            record.copy()
            for record in _performance_records
        ]

    successful = [
        record
        for record in records
        if record["status"] == "success"
    ]

    failed = [
        record
        for record in records
        if record["status"] == "error"
    ]

    api_times = [
        record["api_duration_ms"]
        for record in records
    ]

    sql_times = [
        record["sql_duration_ms"]
        for record in successful
        if isinstance(record["sql_duration_ms"], (int, float))
    ]

    ai_times = [
        record["ai_duration_ms"]
        for record in successful
        if isinstance(record["ai_duration_ms"], (int, float))
        and record["ai_attempted"]
    ]

    cache_hits = sum(
        1
        for record in successful
        if record["cache_hit"] is True
    )

    cache_misses = sum(
        1
        for record in successful
        if record["cache_hit"] is False
        and record["ai_attempted"]
    )

    cache_total = cache_hits + cache_misses

    cache_hit_rate = (
        round((cache_hits / cache_total) * 100, 2)
        if cache_total
        else 0.0
    )

    return {
        "requests_total": len(records),
        "successful_requests": len(successful),
        "failed_requests": len(failed),
        "success_rate": (
            round((len(successful) / len(records)) * 100, 2)
            if records
            else 0.0
        ),
        "average_api_duration_ms": _average(api_times),
        "p95_api_duration_ms": _percentile_95(api_times),
        "average_sql_duration_ms": _average(sql_times),
        "average_ai_duration_ms": _average(ai_times),
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "cache_hit_rate": cache_hit_rate,
        "sample_size": len(records),
        "max_sample_size": MAX_PERFORMANCE_RECORDS,
        "trend": records[-PERFORMANCE_TREND_ITEMS:],
    }


# ============================================================
# APPLICATION LIFECYCLE
# ============================================================

@app.on_event("startup")
def startup():
    """Initialize the database when the API starts."""

    initialize_database()

    logger.info("ORBIT API startup completed.")


@app.on_event("shutdown")
def shutdown():
    """Close reusable HTTP resources during application shutdown."""

    try:
        close_ollama_client()
        logger.info("Ollama HTTP client closed successfully.")

    except Exception:
        logger.exception(
            "Failed to close the Ollama HTTP client."
        )


# ============================================================
# BASIC ROUTES
# ============================================================

@app.get("/")
def root():
    return {
        "name": "ORBIT API",
        "docs": "/docs",
        "health": "/api/health",
        "ai_health": "/api/ai/health",
        "performance": "/api/performance",
    }


@app.get("/api/health")
def health():
    """Return lightweight API health information."""

    return {
        "status": "healthy",
        "service": "orbit-api",
        "mode": "deterministic-demo",
        "version": app.version,
    }


@app.get("/api/ai/health")
def ai_health():
    """Check the local Ollama service and configured model."""

    return check_ollama()


@app.get("/api/schema")
def schema():
    """Return the approved static database schema."""

    return {
        "tables": get_schema(),
    }


@app.get("/api/examples")
def examples():
    """Return example analytics questions."""

    return {
        "questions": EXAMPLES,
    }


# ============================================================
# HISTORY ROUTE
# ============================================================

@app.get("/api/history")
def history():
    """Return the most recent analytics questions safely."""

    with _history_lock:
        recent_items = list(
            reversed(
                _history[-HISTORY_RESPONSE_ITEMS:]
            )
        )

    return {
        "items": recent_items,
    }


# ============================================================
# PERFORMANCE ROUTE
# ============================================================

@app.get("/api/performance")
def performance():
    """Return aggregate API, SQL, AI, and cache metrics."""

    return get_performance_snapshot()


# ============================================================
# ANALYTICS QUESTION ROUTE
# ============================================================

@app.post("/api/ask")
def ask(req: AskRequest):
    """Accept and execute a natural-language analytics question."""

    request_started = time.perf_counter()
    question = req.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    try:
        result = execute_workflow(question)

        api_duration_ms = (
            time.perf_counter() - request_started
        ) * 1000

        history_item = {
            "question": question,
            "answer": result["answer"],
            "duration_ms": result["duration_ms"],
        }

        with _history_lock:
            _history.append(history_item)

            if len(_history) > MAX_HISTORY_ITEMS:
                del _history[:-MAX_HISTORY_ITEMS]

        _record_performance(
            status="success",
            api_duration_ms=api_duration_ms,
            workflow_result=result,
        )

        return result

    except ValueError as error:
        api_duration_ms = (
            time.perf_counter() - request_started
        ) * 1000

        _record_performance(
            status="error",
            api_duration_ms=api_duration_ms,
        )

        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except HTTPException:
        raise

    except Exception as error:
        api_duration_ms = (
            time.perf_counter() - request_started
        ) * 1000

        _record_performance(
            status="error",
            api_duration_ms=api_duration_ms,
        )

        logger.exception(
            "ORBIT analysis request failed."
        )

        raise HTTPException(
            status_code=500,
            detail="Analysis failed. Check API logs.",
        ) from error
