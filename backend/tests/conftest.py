import pytest

from app import ollama_client


@pytest.fixture(autouse=True)
def reset_ollama_client():
    """
    Ensure every test starts with an open Ollama HTTP client.
    Prevents failures when another test closes the shared client.
    """

    ollama_client.close_ollama_client()
    ollama_client._http_client = ollama_client.httpx.Client(
        timeout=ollama_client.OLLAMA_TIMEOUT
    )

    yield

    ollama_client.close_ollama_client()