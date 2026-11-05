
"""
ORBIT Analytics Agent
Ollama AI Performance Benchmark

Measures:
1. Ollama connection and model availability.
2. First AI response latency.
3. AI response generation duration.
4. Repeated request cache-hit latency.
5. Cache performance improvement.

Uses the existing ollama_client.py implementation.
"""

import statistics
import time

from app.ollama_client import (
    check_ollama,
    clear_insight_cache,
    close_ollama_client,
    generate_business_insight,
)


# ============================================================
# CONFIGURATION
# ============================================================

BENCHMARK_QUESTION = (
    "Summarize the revenue performance of Pulse Headphones."
)

BENCHMARK_ROWS = [
    {
        "product": "Pulse Headphones",
        "revenue": 1250,
    }
]

DETERMINISTIC_ANSWER = (
    "Pulse Headphones generated revenue of 1250."
)

REPEATED_REQUESTS = 5


# ============================================================
# DISPLAY HELPERS
# ============================================================

def print_section(title):
    print("\n" + "=" * 65)
    print(title.center(65))
    print("=" * 65)


def print_result(label, result, elapsed_ms):
    print(f"\n{label}")
    print("-" * 50)

    print(f"Status          : {result.get('status')}")
    print(f"Cache hit       : {result.get('cache_hit')}")
    print(
        f"AI duration     : "
        f"{result.get('ai_duration_ms', 0):.2f} ms"
    )
    print(f"Total duration  : {elapsed_ms:.2f} ms")
    print(f"Reason          : {result.get('reason')}")

    answer = result.get("answer")

    if answer:
        print(f"AI answer       : {answer}")

    unsupported_numbers = result.get(
        "unsupported_numbers",
        [],
    )

    if unsupported_numbers:
        print(
            f"Unsupported numbers: {unsupported_numbers}"
        )

    unsupported_claims = result.get(
        "unsupported_claims",
        [],
    )

    if unsupported_claims:
        print(
            f"Unsupported claims: {unsupported_claims}"
        )


# ============================================================
# OLLAMA CONNECTION TEST
# ============================================================

def test_ollama_connection():
    print_section("OLLAMA CONNECTION CHECK")

    started = time.perf_counter()

    health = check_ollama()

    elapsed_ms = (
        time.perf_counter() - started
    ) * 1000

    print(f"Status          : {health.get('status')}")
    print(f"Model           : {health.get('model')}")
    print(
        f"Model available : "
        f"{health.get('model_available')}"
    )
    print(f"Health time     : {elapsed_ms:.2f} ms")

    if health.get("status") != "connected":
        raise RuntimeError(
            "Ollama is unavailable or the configured model "
            "was not found. Check Ollama and OLLAMA_MODEL."
        )

    return health


# ============================================================
# FIRST REQUEST BENCHMARK
# ============================================================

def benchmark_first_request():
    print_section("FIRST AI REQUEST - CACHE MISS")

    started = time.perf_counter()

    result = generate_business_insight(
        question=BENCHMARK_QUESTION,
        rows=BENCHMARK_ROWS,
        deterministic_answer=DETERMINISTIC_ANSWER,
    )

    elapsed_ms = (
        time.perf_counter() - started
    ) * 1000

    print_result(
        "FIRST REQUEST",
        result,
        elapsed_ms,
    )

    return result, elapsed_ms


# ============================================================
# REPEATED REQUEST BENCHMARK
# ============================================================

def benchmark_cached_requests():
    print_section("REPEATED AI REQUESTS - CACHE TEST")

    timings = []
    cache_hits = 0

    for iteration in range(1, REPEATED_REQUESTS + 1):

        started = time.perf_counter()

        result = generate_business_insight(
            question=BENCHMARK_QUESTION,
            rows=BENCHMARK_ROWS,
            deterministic_answer=DETERMINISTIC_ANSWER,
        )

        elapsed_ms = (
            time.perf_counter() - started
        ) * 1000

        timings.append(elapsed_ms)

        if result.get("cache_hit"):
            cache_hits += 1

        print(
            f"Request {iteration}: "
            f"{elapsed_ms:.4f} ms | "
            f"Status: {result.get('status')} | "
            f"Cache: {result.get('cache_hit')}"
        )

    return timings, cache_hits


# ============================================================
# PERFORMANCE SUMMARY
# ============================================================

def print_summary(
    first_result,
    first_duration,
    cached_timings,
    cache_hits,
):
    print_section("OLLAMA PERFORMANCE SUMMARY")

    print(
        f"First request time : "
        f"{first_duration:.4f} ms"
    )

    if cached_timings:
        print(
            f"Average repeat time: "
            f"{statistics.mean(cached_timings):.4f} ms"
        )

        print(
            f"Minimum repeat time: "
            f"{min(cached_timings):.4f} ms"
        )

        print(
            f"Maximum repeat time: "
            f"{max(cached_timings):.4f} ms"
        )

    print(
        f"Cache hits         : "
        f"{cache_hits}/{REPEATED_REQUESTS}"
    )

    print(
        f"First response     : "
        f"{first_result.get('status')}"
    )

    print(
        f"AI generation time : "
        f"{first_result.get('ai_duration_ms', 0):.2f} ms"
    )

    if (
        first_result.get("status") == "accepted"
        and cache_hits == REPEATED_REQUESTS
    ):
        print("\nRESULT: AI generation and cache test PASSED.")

    elif first_result.get("status") != "accepted":
        print(
            "\nRESULT: AI response was not accepted. "
            "Inspect the validation reason above."
        )

    else:
        print(
            "\nRESULT: Benchmark completed, "
            "but all repeated requests were not cache hits."
        )


# ============================================================
# MAIN BENCHMARK
# ============================================================

def run_benchmark():
    try:
        print_section("ORBIT OLLAMA PERFORMANCE BENCHMARK")

        print(f"Repeated requests : {REPEATED_REQUESTS}")
        print("Model connection  : Existing Ollama client")
        print("Cache TTL         : Existing application setting")

        # Step 1: Check Ollama.
        test_ollama_connection()

        # Step 2: Start with an empty insight cache.
        clear_insight_cache()

        # Step 3: Measure first request.
        first_result, first_duration = (
            benchmark_first_request()
        )

        # Step 4: Measure repeated requests.
        cached_timings, cache_hits = (
            benchmark_cached_requests()
        )

        # Step 5: Display final results.
        print_summary(
            first_result,
            first_duration,
            cached_timings,
            cache_hits,
        )

    finally:
        close_ollama_client()

        print("\nBenchmark HTTP client closed.")


if __name__ == "__main__":
    try:
        run_benchmark()

    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user.")

    except Exception as error:
        print("\nBENCHMARK FAILED")
        print(f"Error: {error}")
        raise
