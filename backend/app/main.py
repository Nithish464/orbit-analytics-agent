
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env before importing application modules that read
# environment variables during import (including the Gemini client).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from math import ceil
from threading import Lock

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .database import initialize_database, get_schema
from .schemas import AskRequest
from .agents import execute_workflow, EXAMPLES
from .auth_routes import router as auth_router
from .rag.routes import router as rag_router
from .rag.answer_generator import close_rag_http_client
from .ollama_client import check_ollama, close_ollama_client


logger = logging.getLogger(__name__)


# ============================================================
# RATE LIMITING CONFIGURATION
# ============================================================

RATE_LIMIT_REQUESTS = int(
    os.getenv("ORBIT_RATE_LIMIT_REQUESTS", "20")
)

RATE_LIMIT_WINDOW_SECONDS = float(
    os.getenv("ORBIT_RATE_LIMIT_WINDOW_SECONDS", "60")
)

MAX_TRACKED_CLIENTS = 10000


class InMemoryRateLimiter:
    """Thread-safe, per-client sliding-window rate limiter."""

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
    ):
        if max_requests < 1:
            raise ValueError("Rate limit must be at least 1.")

        if window_seconds <= 0:
            raise ValueError("Rate limit window must be positive.")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = {}
        self._lock = Lock()

    def is_allowed(
        self,
        client_id: str,
    ) -> tuple[bool, int, int]:

        now = time.monotonic()

        with self._lock:
            bucket = self._requests.get(client_id)

            if bucket is None:
                if len(self._requests) >= MAX_TRACKED_CLIENTS:
                    self._remove_expired_clients(now)

                if len(self._requests) >= MAX_TRACKED_CLIENTS:
                    return False, 1, 0

                bucket = deque()
                self._requests[client_id] = bucket

            while (
                bucket
                and now - bucket[0] >= self.window_seconds
            ):
                bucket.popleft()

            if len(bucket) >= self.max_requests:
                retry_after = max(
                    1,
                    ceil(
                        self.window_seconds
                        - (now - bucket[0])
                    ),
                )

                return False, retry_after, 0

            bucket.append(now)

            remaining = self.max_requests - len(bucket)

            return True, 0, remaining

    def _remove_expired_clients(self, now: float) -> None:
        """Remove inactive clients when tracking limit is reached."""

        expired_clients = [
            client_id
            for client_id, timestamps in self._requests.items()
            if (
                not timestamps
                or now - timestamps[-1] >= self.window_seconds
            )
        ]

        for client_id in expired_clients:
            self._requests.pop(client_id, None)


rate_limiter = InMemoryRateLimiter(
    max_requests=RATE_LIMIT_REQUESTS,
    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
)


def _get_client_identifier(request: Request) -> str:
    """Get direct client IP without trusting forwarded headers."""

    if request.client is None:
        return "unknown"

    return request.client.host


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown resources."""

    initialize_database()
    logger.info("ORBIT API startup completed.")

    try:
        yield

    finally:
        # Close analytics Ollama HTTP client.
        try:
            close_ollama_client()
            logger.info(
                "Analytics Ollama HTTP client closed successfully."
            )

        except Exception:
            logger.exception(
                "Failed to close the analytics Ollama HTTP client."
            )

        # Close RAG Ollama HTTP client independently.
        try:
            close_rag_http_client()
            logger.info(
                "RAG HTTP client closed successfully."
            )

        except Exception:
            logger.exception(
                "Failed to close the RAG HTTP client."
            )


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="ORBIT Analytics Agent API",
    description=(
        "Local-first natural-language analytics workflow "
        "with read-only SQL execution, local AI and "
        "retrieval-augmented generation."
    ),
    version="1.4.0",
    lifespan=lifespan,
)


# ============================================================
# ROUTER REGISTRATION
# ============================================================

# Authentication endpoints
app.include_router(auth_router)

# Retrieval-Augmented Generation endpoints
app.include_router(rag_router)


# ============================================================
# CORS CONFIGURATION
# ============================================================

_DEFAULT_ORIGINS = (
    "http://localhost:5173,"
    "http://127.0.0.1:5173,"
    "http://localhost:5174,"
    "http://127.0.0.1:5174,"
    "http://localhost:5175,"
    "http://127.0.0.1:5175"
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
    allow_headers=[
        "Content-Type",
        "Accept",
        "Authorization",
    ],
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
            del _performance_records[:-MAX_PERFORMANCE_RECORDS]


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
        "authentication": "/api/auth",
        "rag": "/api/rag",
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
    """Return aggregate API, SQL, AI and cache metrics."""

    return get_performance_snapshot()


# ============================================================
# ANALYTICS QUESTION ROUTE
# ============================================================

@app.post("/api/ask")
def ask(
    req: AskRequest,
    request: Request,
    response: Response,
):
    """Accept and execute a rate-limited analytics question."""

    client_id = _get_client_identifier(request)

    allowed, retry_after, remaining = rate_limiter.is_allowed(
        client_id
    )

    if not allowed:
        logger.warning(
            "Rate limit exceeded for client %s.",
            client_id,
        )

        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(RATE_LIMIT_REQUESTS),
                "X-RateLimit-Remaining": "0",
            },
        )

    response.headers["X-RateLimit-Limit"] = str(
        RATE_LIMIT_REQUESTS
    )
    response.headers["X-RateLimit-Remaining"] = str(remaining)

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

    except TimeoutError as error:
        api_duration_ms = (
            time.perf_counter() - request_started
        ) * 1000

        _record_performance(
            status="error",
            api_duration_ms=api_duration_ms,
        )

        logger.warning(
            "ORBIT SQL query timed out: %s",
            error,
        )

        raise HTTPException(
            status_code=408,
            detail=str(error),
        ) from error

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
