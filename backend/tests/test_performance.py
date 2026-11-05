import pytest

from app import ollama_client


@pytest.fixture(autouse=True)
def clear_cache_before_test():
    """Clear cache before and after every test."""
    ollama_client.clear_insight_cache()
    yield
    ollama_client.clear_insight_cache()


def test_cache_key_is_consistent():
    """Same inputs should generate the same cache key."""

    question = "What is total revenue?"
    rows = [{"total_revenue": 100}]
    summary = "Total revenue is 100."

    first_key = ollama_client._make_cache_key(
        question, rows, summary
    )

    second_key = ollama_client._make_cache_key(
        question, rows, summary
    )

    assert first_key == second_key


def test_cache_key_changes_when_data_changes():
    """Different data should generate different cache keys."""

    first_key = ollama_client._make_cache_key(
        "What is total revenue?",
        [{"total_revenue": 100}],
        "Total revenue is 100.",
    )

    second_key = ollama_client._make_cache_key(
        "What is total revenue?",
        [{"total_revenue": 200}],
        "Total revenue is 200.",
    )

    assert first_key != second_key


def test_accepted_insight_is_cached():
    """Accepted insights should be stored."""

    key = "accepted-test-key"

    result = {
        "status": "accepted",
        "answer": "Revenue is 100.",
        "reason": "Validation passed.",
        "cache_hit": False,
    }

    ollama_client._store_cached_insight(key, result)

    cached = ollama_client._get_cached_insight(key)

    assert cached is not None
    assert cached["status"] == "accepted"
    assert cached["answer"] == "Revenue is 100."
    assert cached["cache_hit"] is True


def test_rejected_insight_is_not_cached():
    """Rejected insights must not be cached."""

    key = "rejected-test-key"

    result = {
        "status": "rejected",
        "answer": None,
        "reason": "Unsupported numerical claims.",
        "cache_hit": False,
    }

    ollama_client._store_cached_insight(key, result)

    cached = ollama_client._get_cached_insight(key)

    assert cached is None
    assert key not in ollama_client._insight_cache


def test_cache_miss_returns_none():
    """Unknown cache keys should return None."""

    cached = ollama_client._get_cached_insight(
        "non-existent-key"
    )

    assert cached is None


def test_clear_cache_removes_entries():
    """Clearing the cache should remove all entries."""

    ollama_client._store_cached_insight(
        "clear-key-1",
        {
            "status": "accepted",
            "answer": "Answer one.",
        },
    )

    ollama_client._store_cached_insight(
        "clear-key-2",
        {
            "status": "accepted",
            "answer": "Answer two.",
        },
    )

    assert len(ollama_client._insight_cache) == 2

    ollama_client.clear_insight_cache()

    assert len(ollama_client._insight_cache) == 0


def test_cache_expires_after_ttl(monkeypatch):
    """Expired cache entries should not be returned."""

    fake_time = [1000.0]

    monkeypatch.setattr(
        ollama_client.time,
        "monotonic",
        lambda: fake_time[0],
    )

    key = "ttl-test-key"

    ollama_client._store_cached_insight(
        key,
        {
            "status": "accepted",
            "answer": "Cached answer.",
        },
    )

    cached = ollama_client._get_cached_insight(key)

    assert cached is not None

    fake_time[0] += ollama_client.CACHE_TTL_SECONDS + 1

    expired = ollama_client._get_cached_insight(key)

    assert expired is None
    assert key not in ollama_client._insight_cache


def test_cache_respects_maximum_entries():
    """Cache should evict the oldest entry when full."""

    original_max = ollama_client.CACHE_MAX_ENTRIES

    try:
        ollama_client.CACHE_MAX_ENTRIES = 2

        for index in range(1, 4):
            ollama_client._store_cached_insight(
                f"key-{index}",
                {
                    "status": "accepted",
                    "answer": f"Answer {index}.",
                },
            )

        assert len(ollama_client._insight_cache) == 2
        assert "key-1" not in ollama_client._insight_cache
        assert "key-2" in ollama_client._insight_cache
        assert "key-3" in ollama_client._insight_cache

    finally:
        ollama_client.CACHE_MAX_ENTRIES = original_max


def test_cache_hit_does_not_modify_original_result():
    """Cache hits must not mutate the stored result."""

    key = "test-copy-key"

    result = {
        "status": "accepted",
        "answer": "Revenue is 15173.",
        "reason": "Validation passed.",
        "cache_hit": False,
    }

    ollama_client._store_cached_insight(key, result)

    cached = ollama_client._get_cached_insight(key)

    assert cached is not None
    assert cached["cache_hit"] is True

    # Tuple structure: (timestamp, cached_result)
    stored = ollama_client._insight_cache[key][1]

    assert stored["cache_hit"] is False
    assert stored["answer"] == "Revenue is 15173."
    assert cached is not stored

    cached["answer"] = "Modified answer."

    assert stored["answer"] == "Revenue is 15173."