import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from app import ollama_client


def test_eight_concurrent_identical_requests_use_one_generation():
    """
    Eight identical concurrent requests should trigger
    exactly one underlying AI generation.
    """

    ollama_client.clear_insight_cache()

    generation_started = threading.Event()
    allow_generation_to_finish = threading.Event()

    call_count = 0
    call_count_lock = threading.Lock()

    worker_count = 8
    start_barrier = threading.Barrier(worker_count)

    def fake_generation(question, rows, deterministic_answer):
        nonlocal call_count

        with call_count_lock:
            call_count += 1

        generation_started.set()

        if not allow_generation_to_finish.wait(timeout=10):
            raise TimeoutError("Test generation was not released.")

        return {
            "status": "accepted",
            "answer": (
                "Pulse Headphones generated revenue of 1250."
            ),
            "reason": "Mock validation successful.",
            "unsupported_numbers": [],
            "unsupported_claims": [],
            "cache_hit": False,
            "ai_duration_ms": 100.0,
        }

    question = "Summarize Pulse Headphones revenue."

    rows = [
        {
            "product": "Pulse Headphones",
            "revenue": 1250,
        }
    ]

    deterministic_answer = (
        "Pulse Headphones generated revenue of 1250."
    )

    def send_request():
        start_barrier.wait(timeout=10)

        return ollama_client.generate_business_insight(
            question,
            rows,
            deterministic_answer,
        )

    try:
        with patch.object(
            ollama_client,
            "_generate_business_insight_uncached",
            side_effect=fake_generation,
        ):
            with ThreadPoolExecutor(
                max_workers=worker_count
            ) as executor:

                futures = [
                    executor.submit(send_request)
                    for _ in range(worker_count)
                ]

                # Wait until the first generation starts.
                assert generation_started.wait(timeout=5), (
                    "The first AI generation did not start."
                )

                # Give the other concurrent requests time to join.
                time.sleep(0.3)

                assert (
                    ollama_client.get_inflight_insight_count() == 1
                ), "Expected exactly one in-flight generation."

                # Allow the single generation to finish.
                allow_generation_to_finish.set()

                results = [
                    future.result(timeout=10)
                    for future in futures
                ]

        # Exactly one underlying generation must have occurred.
        assert call_count == 1

        # All eight callers must receive accepted responses.
        assert len(results) == worker_count

        assert all(
            result["status"] == "accepted"
            for result in results
        )

        assert all(
            result["answer"]
            == "Pulse Headphones generated revenue of 1250."
            for result in results
        )

        # One caller is the generation leader; seven are waiters.
        assert sum(
            not result["cache_hit"]
            for result in results
        ) == 1

        assert sum(
            result["cache_hit"]
            for result in results
        ) == worker_count - 1

        # No in-flight request should remain.
        assert (
            ollama_client.get_inflight_insight_count() == 0
        )

        # A later identical request should use the accepted cache.
        cached_result = ollama_client.generate_business_insight(
            question,
            rows,
            deterministic_answer,
        )

        assert cached_result["status"] == "accepted"
        assert cached_result["cache_hit"] is True

        # Cache lookup must not trigger another generation.
        assert call_count == 1

    finally:
        allow_generation_to_finish.set()
        ollama_client.clear_insight_cache()