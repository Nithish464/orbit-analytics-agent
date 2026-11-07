
"""
ORBIT RAG - Retrieval Engine

Retrieves relevant business knowledge from ChromaDB
using semantic similarity search.

Features:
- Semantic retrieval
- Metadata filtering
- Similarity threshold
- Context construction
- Source attribution
- Duplicate ID and content removal
- Retrieval statistics
"""

import logging
import re
import hashlib
from typing import Any, Dict, List, Optional, Sequence

from .vector_store import (
    OrbitVectorStore,
    VectorStoreError,
    vector_store,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

DEFAULT_TOP_K = 5
MAX_TOP_K = 20

# Retrieve additional candidates before deduplication.
CANDIDATE_MULTIPLIER = 3

# ChromaDB cosine distance:
# 0.0 = identical direction
# Higher values = less similar.
DEFAULT_MAX_DISTANCE = 0.65

MAX_CONTEXT_CHARACTERS = 12000


# ---------------------------------------------------------
# CUSTOM EXCEPTION
# ---------------------------------------------------------

class RetrievalError(Exception):
    """Raised when document retrieval fails."""


# ---------------------------------------------------------
# RETRIEVER
# ---------------------------------------------------------

class OrbitRetriever:
    """Semantic document retrieval for ORBIT Analytics Agent."""

    def __init__(
        self,
        store: Optional[OrbitVectorStore] = None,
        top_k: int = DEFAULT_TOP_K,
        max_distance: Optional[float] = DEFAULT_MAX_DISTANCE,
        max_context_characters: int = MAX_CONTEXT_CHARACTERS,
    ):

        if not isinstance(top_k, int) or isinstance(top_k, bool):
            raise ValueError("top_k must be an integer.")

        if not 1 <= top_k <= MAX_TOP_K:
            raise ValueError(
                f"top_k must be between 1 and {MAX_TOP_K}."
            )

        if max_distance is not None and not (
            isinstance(max_distance, (int, float))
            and 0.0 <= max_distance <= 2.0
        ):
            raise ValueError(
                "max_distance must be between 0 and 2."
            )

        if max_context_characters <= 0:
            raise ValueError(
                "max_context_characters must be positive."
            )

        self.store = store or vector_store
        self.top_k = top_k
        self.max_distance = max_distance
        self.max_context_characters = max_context_characters

    # -----------------------------------------------------
    # CONTENT NORMALIZATION
    # -----------------------------------------------------

    @staticmethod
    def _normalize_content(content: str) -> str:
        """
        Normalize text for exact duplicate detection.

        Does not modify the original content returned to users.
        """

        normalized = re.sub(
            r"\s+",
            " ",
            content.strip().lower(),
        )

        return normalized

    @staticmethod
    def _extract_year(query: str) -> Optional[int]:
        """Return an explicitly mentioned four-digit year as an integer."""
        match = re.search(r"\b(?:19|20)\d{2}\b", query)
        return int(match.group(0)) if match else None

    @classmethod
    def _content_hash(cls, content: str) -> str:
        """Generate a stable hash for normalized content."""

        normalized = cls._normalize_content(content)

        return hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest()

    # -----------------------------------------------------
    # RETRIEVE DOCUMENTS
    # -----------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant document chunks."""

        if not isinstance(query, str) or not query.strip():
            raise ValueError(
                "Retrieval query cannot be empty."
            )

        requested_k = self.top_k if top_k is None else top_k

        if (
            not isinstance(requested_k, int)
            or isinstance(requested_k, bool)
            or not 1 <= requested_k <= MAX_TOP_K
        ):
            raise ValueError(
                f"top_k must be between 1 and {MAX_TOP_K}."
            )

        # If the user explicitly asks about a year, restrict retrieval
        # to chunks tagged with that year. Do not mix in other years.
        requested_year = self._extract_year(query)
        effective_where = where

        if requested_year:
            year_filter = {"year": {"$eq": requested_year}}
            if effective_where:
                effective_where = {
                    "$and": [effective_where, year_filter]
                }
            else:
                effective_where = year_filter

        # Retrieve additional candidates so duplicate chunks
        # do not reduce the number of useful final results.
        candidate_k = min(
            requested_k * CANDIDATE_MULTIPLIER,
            MAX_TOP_K,
        )

        try:
            results = self.store.similarity_search(
                query=query.strip(),
                top_k=candidate_k,
                where=effective_where,
                where_document=where_document,
            )

            filtered_results = []

            seen_ids = set()
            seen_content_hashes = set()

            for result in results:

                doc_id = result.get("id")

                if not doc_id or doc_id in seen_ids:
                    continue

                seen_ids.add(doc_id)

                content = str(
                    result.get("document") or ""
                ).strip()

                if not content:
                    continue

                distance = float(
                    result.get("distance", 2.0)
                )

                if (
                    self.max_distance is not None
                    and distance > self.max_distance
                ):
                    continue

                # Remove identical text chunks even when
                # they have different ChromaDB IDs.
                content_hash = self._content_hash(content)

                if content_hash in seen_content_hashes:
                    continue

                seen_content_hashes.add(content_hash)

                filtered_results.append({
                    "id": doc_id,
                    "content": content,
                    "metadata": result.get("metadata") or {},
                    "distance": distance,
                    "similarity": result.get(
                        "similarity",
                        0.0,
                    ),
                })

                if len(filtered_results) >= requested_k:
                    break

            logger.info(
                "RAG retrieval completed: query=%r candidates=%d results=%d",
                query,
                len(results),
                len(filtered_results),
            )

            return filtered_results

        except (VectorStoreError, ValueError):
            raise

        except Exception as exc:
            logger.exception("Document retrieval failed.")

            raise RetrievalError(
                f"Unable to retrieve relevant documents: {exc}"
            ) from exc

    # -----------------------------------------------------
    # BUILD CONTEXT
    # -----------------------------------------------------

    def build_context(
        self,
        documents: Sequence[Dict[str, Any]],
        max_characters: Optional[int] = None,
    ) -> str:
        """Build structured context with source attribution."""

        if not documents:
            return ""

        character_limit = (
            self.max_context_characters
            if max_characters is None
            else max_characters
        )

        if (
            not isinstance(character_limit, int)
            or isinstance(character_limit, bool)
            or character_limit <= 0
        ):
            raise ValueError(
                "max_characters must be a positive integer."
            )

        context_parts = []
        current_length = 0

        for index, document in enumerate(
            documents,
            start=1,
        ):

            content = str(
                document.get("content", "")
            ).strip()

            if not content:
                continue

            metadata = document.get("metadata") or {}

            source = str(
                metadata.get("source")
                or metadata.get("file_name")
                or "Unknown source"
            )

            page = metadata.get("page")

            source_label = f"Source: {source}"

            if page is not None:
                source_label += f", Page: {page}"

            block = (
                f"[Document {index}]\n"
                f"{source_label}\n"
                f"Content: {content}"
            )

            remaining = character_limit - current_length

            if remaining <= 0:
                break

            if len(block) > remaining:

                if remaining < len("[Truncated]"):
                    break

                block = (
                    block[:remaining - len("[Truncated]")]
                    + "[Truncated]"
                )

            context_parts.append(block)

            current_length += len(block) + 2

        return "\n\n".join(context_parts)

    # -----------------------------------------------------
    # RETRIEVE AND BUILD CONTEXT
    # -----------------------------------------------------

    def retrieve_context(
        self,
        query: str,
        top_k: Optional[int] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Retrieve documents and construct LLM context."""

        documents = self.retrieve(
            query=query,
            top_k=top_k,
            where=where,
        )

        context = self.build_context(documents)

        sources = []

        for document in documents:

            metadata = document.get("metadata") or {}

            sources.append({
                "id": document["id"],
                "source": metadata.get(
                    "source",
                    metadata.get("file_name", "Unknown"),
                ),
                "page": metadata.get("page"),
                "year": metadata.get("year"),
                "similarity": document.get(
                    "similarity",
                    0.0,
                ),
            })

        return {
            "query": query,
            "context": context,
            "documents": documents,
            "sources": sources,
            "retrieved_count": len(documents),
            "has_context": bool(context),
        }

    # -----------------------------------------------------
    # RETRIEVAL STATISTICS
    # -----------------------------------------------------

    def get_retrieval_stats(self) -> Dict[str, Any]:
        """Return retrieval configuration and store stats."""

        try:
            store_stats = self.store.get_stats()

            return {
                "retriever": "ORBIT Semantic Retriever",
                "top_k": self.top_k,
                "candidate_multiplier": CANDIDATE_MULTIPLIER,
                "max_distance": self.max_distance,
                "max_context_characters": (
                    self.max_context_characters
                ),
                "vector_store": store_stats,
            }

        except VectorStoreError as exc:
            raise RetrievalError(
                f"Unable to retrieve statistics: {exc}"
            ) from exc


# ---------------------------------------------------------
# SHARED RETRIEVER INSTANCE
# ---------------------------------------------------------

retriever = OrbitRetriever()


# ---------------------------------------------------------
# CONVENIENCE FUNCTIONS
# ---------------------------------------------------------

def retrieve_documents(
    query: str,
    top_k: int = DEFAULT_TOP_K,
) -> List[Dict[str, Any]]:
    """Retrieve relevant document chunks."""

    return retriever.retrieve(
        query=query,
        top_k=top_k,
    )


def retrieve_context(
    query: str,
    top_k: int = DEFAULT_TOP_K,
) -> Dict[str, Any]:
    """Retrieve documents and construct LLM context."""

    return retriever.retrieve_context(
        query=query,
        top_k=top_k,
    )
