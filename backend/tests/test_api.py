
from fastapi.testclient import TestClient

from app.main import app
from app import main


client = TestClient(app)


def test_sql_timeout_returns_http_408(monkeypatch):
    def mock_timeout(question):
        raise TimeoutError("Query execution exceeded 5.0 seconds.")

    monkeypatch.setattr(main, "execute_workflow", mock_timeout)

    response = client.post(
        "/api/ask",
        json={"question": "What is our total revenue?"},
    )

    assert response.status_code == 408
    assert response.json()["detail"] == (
        "Query execution exceeded 5.0 seconds."
    )


def test_invalid_question_returns_http_400(monkeypatch):
    def mock_invalid_question(question):
        raise ValueError("Invalid question")

    monkeypatch.setattr(
        main,
        "execute_workflow",
        mock_invalid_question,
    )

    response = client.post(
        "/api/ask",
        json={"question": "test"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid question"


def test_unexpected_error_returns_http_500(monkeypatch):
    def mock_error(question):
        raise RuntimeError("Unexpected server error")

    monkeypatch.setattr(
        main,
        "execute_workflow",
        mock_error,
    )

    response = client.post(
        "/api/ask",
        json={"question": "What is our total revenue?"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Analysis failed. Check API logs."
    )


def test_successful_analysis_returns_http_200(monkeypatch):
    expected_result = {
        "question": "What is our total revenue?",
        "answer": "Total revenue is $150,000.",
        "sql": "SELECT SUM(total) AS revenue FROM orders LIMIT 100",
        "columns": ["revenue"],
        "rows": [{"revenue": 150000}],
        "row_count": 1,
        "chart": None,
        "steps": [],
        "duration_ms": 125.5,
        "mode": "deterministic-demo",
    }

    def mock_success(question):
        return expected_result

    monkeypatch.setattr(
        main,
        "execute_workflow",
        mock_success,
    )

    response = client.post(
        "/api/ask",
        json={"question": "What is our total revenue?"},
    )

    assert response.status_code == 200
    assert response.json() == expected_result
    assert response.json()["answer"] == "Total revenue is $150,000."
    assert response.json()["row_count"] == 1


def test_rate_limit_returns_http_429(monkeypatch):
    monkeypatch.setattr(
        main,
        "rate_limiter",
        main.InMemoryRateLimiter(
            max_requests=1,
            window_seconds=60,
        ),
    )

    def mock_success(question):
        return {
            "question": question,
            "answer": "Total revenue is $150,000.",
            "sql": "SELECT 1 LIMIT 100",
            "columns": ["revenue"],
            "rows": [{"revenue": 150000}],
            "row_count": 1,
            "chart": None,
            "steps": [],
            "duration_ms": 10.0,
            "mode": "deterministic-demo",
        }

    monkeypatch.setattr(
        main,
        "execute_workflow",
        mock_success,
    )

    payload = {
        "question": "What is our total revenue?"
    }

    first_response = client.post("/api/ask", json=payload)
    second_response = client.post("/api/ask", json=payload)

    assert first_response.status_code == 200

    assert second_response.status_code == 429
    assert second_response.json()["detail"] == (
        "Too many requests. Please try again later."
    )

    assert second_response.headers["retry-after"] == "60"
    assert second_response.headers["x-ratelimit-remaining"] == "0"
