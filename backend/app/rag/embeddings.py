
"""
ORBIT RAG - Embedding Service

Generates document and query embeddings using Ollama
with the nomic-embed-text model.
"""

import os
from typing import List, Sequence

import httpx


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
).rstrip("/")

EMBEDDING_MODEL = os.getenv(
    "ORBIT_EMBEDDING_MODEL",
    "nomic-embed-text",
)

EMBEDDING_TIMEOUT = float(
    os.getenv("ORBIT_EMBEDDING_TIMEOUT", "60")
)

BATCH_SIZE = 32


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
    Generates embeddings using Ollama's embedding API.

    Supports:
    - Single query embedding
    - Multiple document embeddings
    - Batch processing
    - Nomic retrieval prefixes
    """

    def __init__(
        self,
        model: str = EMBEDDING_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        timeout: float = EMBEDDING_TIMEOUT,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # -----------------------------------------------------
    # INTERNAL API REQUEST
    # -----------------------------------------------------

    def _request_embeddings(
        self,
        texts: Sequence[str],
    ) -> List[List[float]]:

        if not texts:
            return []

        url = f"{self.base_url}/api/embed"

        payload = {
            "model": self.model,
            "input": list(texts),
            "truncate": True,
        }

        try:
            with httpx.Client(
                timeout=self.timeout
            ) as client:

                response = client.post(
                    url,
                    json=payload,
                )

                response.raise_for_status()

                data = response.json()

        except httpx.TimeoutException as exc:
            raise EmbeddingError(
                "Ollama embedding request timed out."
            ) from exc

        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]

            raise EmbeddingError(
                f"Ollama returned HTTP "
                f"{exc.response.status_code}: {detail}"
            ) from exc

        except httpx.RequestError as exc:
            raise EmbeddingError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Check whether Ollama is running."
            ) from exc

        except ValueError as exc:
            raise EmbeddingError(
                "Ollama returned invalid JSON."
            ) from exc

        embeddings = data.get("embeddings")

        if not isinstance(embeddings, list):
            raise EmbeddingError(
                "Ollama response does not contain embeddings."
            )

        if len(embeddings) != len(texts):
            raise EmbeddingError(
                "Embedding count does not match input count."
            )

        validated_embeddings = []

        expected_dimension = None

        for embedding in embeddings:

            if not isinstance(embedding, list) or not embedding:
                raise EmbeddingError(
                    "Ollama returned an empty or invalid embedding."
                )

            try:
                vector = [float(value) for value in embedding]
            except (TypeError, ValueError) as exc:
                raise EmbeddingError(
                    "Embedding contains invalid numeric values."
                ) from exc

            if not all(
                __import__("math").isfinite(value)
                for value in vector
            ):
                raise EmbeddingError(
                    "Embedding contains non-finite values."
                )

            if expected_dimension is None:
                expected_dimension = len(vector)

            elif len(vector) != expected_dimension:
                raise EmbeddingError(
                    "Inconsistent embedding dimensions."
                )

            validated_embeddings.append(vector)

        return validated_embeddings

    # -----------------------------------------------------
    # SINGLE QUERY EMBEDDING
    # -----------------------------------------------------

    def embed_query(self, text: str) -> List[float]:
        """
        Generate an embedding for a search query.
        """

        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                "Query text cannot be empty."
            )

        prefixed_text = f"search_query: {text.strip()}"

        embeddings = self._request_embeddings(
            [prefixed_text]
        )

        return embeddings[0]

    # -----------------------------------------------------
    # DOCUMENT EMBEDDINGS
    # -----------------------------------------------------

    def embed_documents(
        self,
        documents: Sequence[str],
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple documents.

        Processes documents in batches to control memory
        and request size.
        """

        if not documents:
            return []

        if any(
            not isinstance(document, str)
            or not document.strip()
            for document in documents
        ):
            raise ValueError(
                "All documents must contain non-empty text."
            )

        prefixed_documents = [
            f"search_document: {document.strip()}"
            for document in documents
        ]

        all_embeddings = []

        for start in range(
            0,
            len(prefixed_documents),
            BATCH_SIZE,
        ):

            batch = prefixed_documents[
                start:start + BATCH_SIZE
            ]

            batch_embeddings = self._request_embeddings(
                batch
            )

            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    # -----------------------------------------------------
    # HEALTH CHECK
    # -----------------------------------------------------

    def health_check(self) -> bool:
        """
        Check whether Ollama and the embedding model
        are available.
        """

        try:
            url = f"{self.base_url}/api/tags"

            with httpx.Client(
                timeout=10
            ) as client:

                response = client.get(url)
                response.raise_for_status()

                models = response.json().get(
                    "models",
                    [],
                )

            return any(
                item.get("name", "").split(":")[0]
                == self.model.split(":")[0]
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
    """Check embedding model availability."""

    return embedding_service.health_check()
