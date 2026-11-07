"""
ORBIT RAG - Embedding Service

Generates document and query embeddings using an Ollama-compatible
embedding API (local Ollama or a hosted Ollama endpoint).

Environment variables:
    OLLAMA_BASE_URL          Base URL, e.g. http://localhost:11434
    OLLAMA_API_KEY            Optional bearer token for hosted endpoints
    ORBIT_EMBEDDING_MODEL     Embedding model (default: nomic-embed-text)
    ORBIT_EMBEDDING_TIMEOUT   Request timeout in seconds (default: 60)
    ORBIT_EMBEDDING_BATCH_SIZE Documents per embedding request (default: 32)
"""

import math
import os
from typing import List, Sequence

import httpx


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
).strip().rstrip("/")

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "").strip()

EMBEDDING_MODEL = os.getenv(
    "ORBIT_EMBEDDING_MODEL",
    "nomic-embed-text",
).strip()

try:
    EMBEDDING_TIMEOUT = float(
        os.getenv("ORBIT_EMBEDDING_TIMEOUT", "60")
    )
except (TypeError, ValueError):
    EMBEDDING_TIMEOUT = 60.0

if EMBEDDING_TIMEOUT <= 0:
    EMBEDDING_TIMEOUT = 60.0

try:
    BATCH_SIZE = int(os.getenv("ORBIT_EMBEDDING_BATCH_SIZE", "32"))
except (TypeError, ValueError):
    BATCH_SIZE = 32

if BATCH_SIZE < 1:
    BATCH_SIZE = 32

if not OLLAMA_BASE_URL:
    raise RuntimeError("OLLAMA_BASE_URL cannot be empty.")

if not EMBEDDING_MODEL:
    raise RuntimeError("ORBIT_EMBEDDING_MODEL cannot be empty.")


# ---------------------------------------------------------
# CUSTOM EXCEPTION
# ---------------------------------------------------------

class EmbeddingError(Exception):
    """Raised when embedding generation fails."""


# ---------------------------------------------------------
# EMBEDDING SERVICE
# ---------------------------------------------------------

class OllamaEmbeddingService:
    """
    Generates embeddings using Ollama's /api/embed endpoint.

    Supports:
    - Local Ollama and hosted Ollama-compatible endpoints
    - Optional Bearer authentication
    - Single query embeddings
    - Batched document embeddings
    - Nomic retrieval prefixes
    - Response shape, dimension and finite-number validation
    """

    def __init__(
        self,
        model: str = EMBEDDING_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        timeout: float = EMBEDDING_TIMEOUT,
        api_key: str = OLLAMA_API_KEY,
        batch_size: int = BATCH_SIZE,
    ):
        self.model = model.strip()
        self.base_url = base_url.strip().rstrip("/")
        self.timeout = float(timeout)
        self.api_key = api_key.strip()
        self.batch_size = int(batch_size)

        if not self.model:
            raise ValueError("Embedding model cannot be empty.")

        if not self.base_url:
            raise ValueError("Embedding base URL cannot be empty.")

        if self.timeout <= 0:
            raise ValueError("Embedding timeout must be positive.")

        if self.batch_size < 1:
            raise ValueError("Embedding batch size must be at least 1.")

    def _headers(self) -> dict:
        """Build request headers, including optional hosted-service auth."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # -----------------------------------------------------
    # INTERNAL API REQUEST
    # -----------------------------------------------------

    def _request_embeddings(
        self,
        texts: Sequence[str],
    ) -> List[List[float]]:
        if not texts:
            return []

        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Embedding inputs must be non-empty strings.")

        url = f"{self.base_url}/api/embed"
        payload = {
            "model": self.model,
            "input": list(texts),
            "truncate": True,
        }

        try:
            with httpx.Client(
                timeout=httpx.Timeout(self.timeout, connect=min(10.0, self.timeout)),
                headers=self._headers(),
            ) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

        except httpx.TimeoutException as exc:
            raise EmbeddingError(
                f"Embedding request timed out after {self.timeout:g} seconds."
            ) from exc

        except httpx.HTTPStatusError as exc:
            detail = (exc.response.text or "")[:500]
            raise EmbeddingError(
                f"Embedding service returned HTTP {exc.response.status_code}: {detail}"
            ) from exc

        except httpx.RequestError as exc:
            raise EmbeddingError(
                f"Cannot connect to embedding service at {self.base_url}. "
                "Check OLLAMA_BASE_URL and network connectivity."
            ) from exc

        except ValueError as exc:
            # Includes invalid JSON responses.
            raise EmbeddingError(
                "Embedding service returned invalid JSON."
            ) from exc

        if not isinstance(data, dict):
            raise EmbeddingError("Embedding service response must be a JSON object.")

        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list):
            raise EmbeddingError(
                "Embedding response does not contain a valid 'embeddings' list."
            )

        if len(embeddings) != len(texts):
            raise EmbeddingError(
                "Embedding count does not match the number of input texts."
            )

        validated_embeddings: List[List[float]] = []
        expected_dimension = None

        for index, embedding in enumerate(embeddings):
            if not isinstance(embedding, list) or not embedding:
                raise EmbeddingError(
                    f"Embedding at index {index} is empty or has an invalid format."
                )

            try:
                vector = [float(value) for value in embedding]
            except (TypeError, ValueError, OverflowError) as exc:
                raise EmbeddingError(
                    f"Embedding at index {index} contains a non-numeric value."
                ) from exc

            if not all(math.isfinite(value) for value in vector):
                raise EmbeddingError(
                    f"Embedding at index {index} contains a non-finite value."
                )

            if expected_dimension is None:
                expected_dimension = len(vector)
            elif len(vector) != expected_dimension:
                raise EmbeddingError(
                    "Embedding vectors in the same response have inconsistent dimensions."
                )

            validated_embeddings.append(vector)

        return validated_embeddings

    # -----------------------------------------------------
    # SINGLE QUERY EMBEDDING
    # -----------------------------------------------------

    def embed_query(self, text: str) -> List[float]:
        """Generate an embedding for a search query."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Query text cannot be empty.")

        prefixed_text = f"search_query: {text.strip()}"
        embeddings = self._request_embeddings([prefixed_text])
        return embeddings[0]

    # -----------------------------------------------------
    # DOCUMENT EMBEDDINGS
    # -----------------------------------------------------

    def embed_documents(
        self,
        documents: Sequence[str],
    ) -> List[List[float]]:
        """
        Generate embeddings for documents in bounded batches.
        Uses Nomic's search_document prefix for document vectors.
        """
        if not documents:
            return []

        if isinstance(documents, (str, bytes)):
            raise ValueError("Documents must be a sequence of text strings.")

        if any(
            not isinstance(document, str) or not document.strip()
            for document in documents
        ):
            raise ValueError("All documents must contain non-empty text.")

        prefixed_documents = [
            f"search_document: {document.strip()}"
            for document in documents
        ]

        all_embeddings: List[List[float]] = []
        expected_dimension = None

        for start in range(0, len(prefixed_documents), self.batch_size):
            batch = prefixed_documents[start:start + self.batch_size]
            batch_embeddings = self._request_embeddings(batch)

            for vector in batch_embeddings:
                if expected_dimension is None:
                    expected_dimension = len(vector)
                elif len(vector) != expected_dimension:
                    raise EmbeddingError(
                        "Embedding dimensions changed between document batches."
                    )

            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    # -----------------------------------------------------
    # HEALTH CHECK
    # -----------------------------------------------------

    def health_check(self) -> bool:
        """
        Check endpoint connectivity and whether the configured model
        appears in the endpoint's /api/tags response.
        """
        try:
            url = f"{self.base_url}/api/tags"
            with httpx.Client(
                timeout=httpx.Timeout(10.0, connect=5.0),
                headers=self._headers(),
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                payload = response.json()

            if not isinstance(payload, dict):
                return False

            models = payload.get("models", [])
            if not isinstance(models, list):
                return False

            configured_base_name = self.model.split(":")[0]
            return any(
                isinstance(item, dict)
                and isinstance(item.get("name"), str)
                and item["name"].split(":")[0] == configured_base_name
                for item in models
            )

        except (
            httpx.HTTPError,
            ValueError,
            TypeError,
        ):
            return False


# ---------------------------------------------------------
# SHARED SERVICE INSTANCE
# ---------------------------------------------------------

embedding_service = OllamaEmbeddingService()


# ---------------------------------------------------------
# CONVENIENCE FUNCTIONS
# ---------------------------------------------------------

def embed_query(text: str) -> List[float]:
    """Generate a query embedding."""
    return embedding_service.embed_query(text)


def embed_documents(
    documents: Sequence[str],
) -> List[List[float]]:
    """Generate document embeddings."""
    return embedding_service.embed_documents(documents)


def check_embedding_health() -> bool:
    """Check embedding endpoint and model availability."""
    return embedding_service.health_check()
