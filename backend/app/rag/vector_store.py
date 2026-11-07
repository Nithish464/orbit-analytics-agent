
"""
ORBIT RAG - ChromaDB Vector Store

Persistent vector storage for business documents.
Uses Ollama nomic-embed-text through the
ORBIT embedding service.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import chromadb

from .embeddings import (
    EmbeddingError,
    embedding_service,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]

# Set ORBIT_VECTOR_DB_PATH to a persistent mounted directory in production.
# Example for a Render Persistent Disk mounted at /var/data:
# ORBIT_VECTOR_DB_PATH=/var/data/orbit/chroma
#
# On local development, the default remains backend/data/chroma.
_raw_vector_db_path = os.getenv(
    "ORBIT_VECTOR_DB_PATH",
    str(BASE_DIR / "data" / "chroma"),
).strip()

if not _raw_vector_db_path:
    raise RuntimeError(
        "ORBIT_VECTOR_DB_PATH cannot be empty. "
        "Set it to a writable directory for ChromaDB persistence."
    )

VECTOR_DB_PATH = Path(_raw_vector_db_path).expanduser().resolve()

COLLECTION_NAME = os.getenv(
    "ORBIT_COLLECTION_NAME",
    "orbit_business_documents",
)

DISTANCE_METRIC = "cosine"

DEFAULT_TOP_K = 5
MAX_TOP_K = 20
MAX_BATCH_SIZE = 100


# ---------------------------------------------------------
# CUSTOM EXCEPTIONS
# ---------------------------------------------------------

class VectorStoreError(Exception):
    """Raised when vector storage operations fail."""


# ---------------------------------------------------------
# VECTOR STORE
# ---------------------------------------------------------

class OrbitVectorStore:
    """
    Persistent ChromaDB vector store.

    Features:
    - Persistent document storage
    - Ollama embedding integration
    - Document insertion and updates
    - Duplicate ID handling
    - Semantic similarity search
    - Metadata filtering
    - Document deletion
    - Collection statistics
    """

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = COLLECTION_NAME,
    ):
        configured_path = (
            persist_directory
            if persist_directory is not None
            else VECTOR_DB_PATH
        )

        self.persist_directory = Path(configured_path).expanduser().resolve()

        if not collection_name.strip():
            raise ValueError(
                "Collection name cannot be empty."
            )

        self.collection_name = collection_name

        self.client = None
        self.collection = None

        self._initialize()

    # -----------------------------------------------------
    # INITIALIZATION
    # -----------------------------------------------------

    def _initialize(self) -> None:
        """Initialize persistent ChromaDB storage."""

        try:
            self.persist_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            self.client = chromadb.PersistentClient(
                path=str(self.persist_directory),
            )

            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "description": "ORBIT business knowledge base",
                    "hnsw:space": DISTANCE_METRIC,
                },
            )

            logger.info(
                "ORBIT vector collection initialized: %s",
                self.collection_name,
            )

        except Exception as exc:
            raise VectorStoreError(
                f"Failed to initialize ChromaDB: {exc}"
            ) from exc

    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    @staticmethod
    def _validate_documents(
        documents: Sequence[str],
        ids: Sequence[str],
    ) -> None:

        if len(documents) != len(ids):
            raise ValueError(
                "Documents and IDs must have equal lengths."
            )

        if not documents:
            raise ValueError(
                "At least one document is required."
            )

        if len(documents) > MAX_BATCH_SIZE:
            raise ValueError(
                f"Maximum batch size is {MAX_BATCH_SIZE}."
            )

        if any(
            not isinstance(doc, str) or not doc.strip()
            for doc in documents
        ):
            raise ValueError(
                "Documents must contain non-empty text."
            )

        if any(
            not isinstance(doc_id, str) or not doc_id.strip()
            for doc_id in ids
        ):
            raise ValueError(
                "Every document must have a valid ID."
            )

        if len(set(ids)) != len(ids):
            raise ValueError(
                "Duplicate IDs within the same batch are not allowed."
            )

    @staticmethod
    def _validate_metadata(
        metadatas: Optional[Sequence[Dict[str, Any]]],
        expected_length: int,
    ) -> None:

        if metadatas is None:
            return

        if len(metadatas) != expected_length:
            raise ValueError(
                "Metadata count must match document count."
            )

        for metadata in metadatas:

            if not isinstance(metadata, dict):
                raise ValueError(
                    "Each metadata item must be a dictionary."
                )

            for key, value in metadata.items():

                if not isinstance(key, str) or not key.strip():
                    raise ValueError(
                        "Metadata keys must be non-empty strings."
                    )

                if isinstance(value, bool):
                    continue

                if not isinstance(
                    value,
                    (str, int, float),
                ):
                    raise ValueError(
                        f"Unsupported metadata value for '{key}'."
                    )

    # -----------------------------------------------------
    # ADD DOCUMENTS
    # -----------------------------------------------------

    def add_documents(
        self,
        documents: Sequence[str],
        ids: Sequence[str],
        metadatas: Optional[
            Sequence[Dict[str, Any]]
        ] = None,
    ) -> Dict[str, Any]:
        """
        Embed and store documents.

        Existing IDs are updated using ChromaDB upsert.
        """

        documents = list(documents)
        ids = list(ids)

        self._validate_documents(
            documents,
            ids,
        )

        self._validate_metadata(
            metadatas,
            len(documents),
        )

        try:
            embeddings = embedding_service.embed_documents(
                documents
            )

            self.collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=(
                    list(metadatas)
                    if metadatas is not None
                    else None
                ),
            )

            return {
                "success": True,
                "message": "Documents stored successfully.",
                "documents_added": len(documents),
                "ids": ids,
            }

        except EmbeddingError as exc:
            raise VectorStoreError(
                f"Document embedding failed: {exc}"
            ) from exc

        except Exception as exc:
            raise VectorStoreError(
                f"Failed to store documents: {exc}"
            ) from exc

    # -----------------------------------------------------
    # SIMILARITY SEARCH
    # -----------------------------------------------------

    def similarity_search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for semantically similar documents.
        """

        if not isinstance(query, str) or not query.strip():
            raise ValueError(
                "Search query cannot be empty."
            )

        if not isinstance(top_k, int) or isinstance(top_k, bool):
            raise ValueError(
                "top_k must be an integer."
            )

        if not 1 <= top_k <= MAX_TOP_K:
            raise ValueError(
                f"top_k must be between 1 and {MAX_TOP_K}."
            )

        try:
            collection_count = self.collection.count()

            if collection_count == 0:
                return []

            query_embedding = embedding_service.embed_query(
                query
            )

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, collection_count),
                where=where,
                where_document=where_document,
                include=[
                    "documents",
                    "metadatas",
                    "distances",
                ],
            )

            matches = []

            ids = results.get("ids", [[]])[0]
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            for index, doc_id in enumerate(ids):

                distance = distances[index]

                matches.append({
                    "id": doc_id,
                    "document": documents[index],
                    "metadata": metadatas[index] or {},
                    "distance": float(distance),
                    "similarity": max(
                        0.0,
                        min(1.0, 1.0 - float(distance)),
                    ),
                })

            return matches

        except EmbeddingError as exc:
            raise VectorStoreError(
                f"Query embedding failed: {exc}"
            ) from exc

        except Exception as exc:
            raise VectorStoreError(
                f"Similarity search failed: {exc}"
            ) from exc

    # -----------------------------------------------------
    # GET DOCUMENTS
    # -----------------------------------------------------

    def get_documents(
        self,
        ids: Optional[Sequence[str]] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Retrieve stored documents."""

        if not isinstance(limit, int) or isinstance(limit, bool):
            raise ValueError("limit must be an integer.")

        if not 1 <= limit <= 1000:
            raise ValueError(
                "limit must be between 1 and 1000."
            )

        try:
            results = self.collection.get(
                ids=list(ids) if ids is not None else None,
                limit=limit,
                include=[
                    "documents",
                    "metadatas",
                ],
            )

            return results

        except Exception as exc:
            raise VectorStoreError(
                f"Failed to retrieve documents: {exc}"
            ) from exc

    # -----------------------------------------------------
    # DELETE DOCUMENTS
    # -----------------------------------------------------

    def delete_documents(
        self,
        ids: Sequence[str],
    ) -> Dict[str, Any]:
        """Delete documents using their IDs."""

        ids = list(ids)

        if not ids:
            raise ValueError(
                "At least one document ID is required."
            )

        if any(
            not isinstance(item, str) or not item.strip()
            for item in ids
        ):
            raise ValueError(
                "Document IDs must be non-empty strings."
            )

        if len(set(ids)) != len(ids):
            raise ValueError(
                "Duplicate IDs are not allowed."
            )

        try:
            self.collection.delete(ids=ids)

            return {
                "success": True,
                "deleted_ids": ids,
                "deleted_count": len(ids),
            }

        except Exception as exc:
            raise VectorStoreError(
                f"Failed to delete documents: {exc}"
            ) from exc

    # -----------------------------------------------------
    # COLLECTION STATISTICS
    # -----------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return vector collection statistics."""

        try:
            return {
                "collection_name": self.collection_name,
                "document_count": self.collection.count(),
                "persist_directory": str(
                    self.persist_directory
                ),
                "embedding_model": (
                    embedding_service.model
                ),
                "distance_metric": DISTANCE_METRIC,
            }

        except Exception as exc:
            raise VectorStoreError(
                f"Failed to retrieve vector store statistics: {exc}"
            ) from exc

    # -----------------------------------------------------
    # COLLECTION MANAGEMENT
    # -----------------------------------------------------

    def clear_collection(self) -> Dict[str, Any]:
        """
        Delete all documents from this collection.

        Use carefully: this operation is destructive.
        """

        try:
            previous_count = self.collection.count()

            self.client.delete_collection(
                name=self.collection_name
            )

            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "description": "ORBIT business knowledge base",
                    "hnsw:space": DISTANCE_METRIC,
                },
            )

            return {
                "success": True,
                "deleted_count": previous_count,
                "message": "Collection cleared successfully.",
            }

        except Exception as exc:
            raise VectorStoreError(
                f"Failed to clear collection: {exc}"
            ) from exc


# ---------------------------------------------------------
# SHARED VECTOR STORE INSTANCE
# ---------------------------------------------------------

vector_store = OrbitVectorStore()
