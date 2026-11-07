
"""
ORBIT RAG - Document Ingestion Pipeline

Workflow:
1. Validate source document.
2. Extract text from PDF, TXT or CSV.
3. Split extracted text into chunks.
4. Generate document embeddings.
5. Store vectors and metadata in ChromaDB.

Supports:
- Single document ingestion
- Multiple document ingestion
- Duplicate-safe chunk IDs
- Source metadata
- Ingestion statistics
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .document_loader import (
    DocumentLoader,
    DocumentLoaderError,
    document_loader,
)
from .vector_store import (
    OrbitVectorStore,
    VectorStoreError,
    vector_store,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

DEFAULT_BATCH_SIZE = 32
MAX_INGESTION_BATCH_SIZE = 100


# ---------------------------------------------------------
# CUSTOM EXCEPTION
# ---------------------------------------------------------

class IngestionError(Exception):
    """Raised when document ingestion fails."""


# ---------------------------------------------------------
# INGESTION SERVICE
# ---------------------------------------------------------

class OrbitIngestionService:
    """
    End-to-end document ingestion service.

    Converts business documents into vector embeddings
    and stores them in the ORBIT ChromaDB collection.
    """

    def __init__(
        self,
        loader: Optional[DocumentLoader] = None,
        store: Optional[OrbitVectorStore] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):

        if (
            not isinstance(batch_size, int)
            or isinstance(batch_size, bool)
            or not 1 <= batch_size <= MAX_INGESTION_BATCH_SIZE
        ):
            raise ValueError(
                "batch_size must be between 1 and 100."
            )

        self.loader = loader or document_loader
        self.store = store or vector_store
        self.batch_size = batch_size

    # -----------------------------------------------------
    # INGEST ONE DOCUMENT
    # -----------------------------------------------------

    def ingest_document(
        self,
        file_path: str,
        source_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process and store one document.

        Returns ingestion details and document statistics.
        """

        path = Path(file_path).expanduser()

        if not path.exists() or not path.is_file():
            raise IngestionError(
                f"Document not found: {path}"
            )

        try:
            chunks = self.loader.process_document(
                str(path),
                source_name=source_name,
            )

            stored_count = 0

            for start in range(
                0,
                len(chunks),
                self.batch_size,
            ):

                batch = chunks[
                    start:start + self.batch_size
                ]

                documents = [
                    item["text"]
                    for item in batch
                ]

                ids = [
                    item["id"]
                    for item in batch
                ]

                metadatas = [
                    item["metadata"]
                    for item in batch
                ]

                result = self.store.add_documents(
                    documents=documents,
                    ids=ids,
                    metadatas=metadatas,
                )

                stored_count += result["documents_added"]

            logger.info(
                "Ingested %s chunks from %s",
                stored_count,
                path.name,
            )

            return {
                "success": True,
                "source": source_name or path.name,
                "file_type": path.suffix.lower(),
                "chunks_created": len(chunks),
                "chunks_stored": stored_count,
                "document_hash": chunks[0]["metadata"][
                    "document_hash"
                ],
                "collection": self.store.collection_name,
                "message": "Document ingested successfully.",
            }

        except (
            DocumentLoaderError,
            VectorStoreError,
            ValueError,
        ) as exc:

            logger.exception(
                "Document ingestion failed: %s",
                path,
            )

            raise IngestionError(
                f"Could not ingest {path.name}: {exc}"
            ) from exc

        except Exception as exc:

            logger.exception(
                "Unexpected ingestion error: %s",
                path,
            )

            raise IngestionError(
                f"Unexpected ingestion failure: {exc}"
            ) from exc

    # -----------------------------------------------------
    # INGEST MULTIPLE DOCUMENTS
    # -----------------------------------------------------

    def ingest_multiple_documents(
        self,
        file_paths: Sequence[str],
    ) -> Dict[str, Any]:
        """
        Ingest multiple documents independently.

        One failed document does not stop other documents.
        """

        if not file_paths:
            raise ValueError(
                "At least one file path is required."
            )

        results = []
        failures = []

        for file_path in file_paths:

            try:
                result = self.ingest_document(
                    file_path
                )

                results.append(result)

            except IngestionError as exc:

                failures.append({
                    "file": str(file_path),
                    "error": str(exc),
                })

        total_chunks = sum(
            result["chunks_stored"]
            for result in results
        )

        return {
            "success": len(failures) == 0,
            "total_files": len(file_paths),
            "successful_files": len(results),
            "failed_files": len(failures),
            "total_chunks_stored": total_chunks,
            "results": results,
            "failures": failures,
        }

    # -----------------------------------------------------
    # INGESTION STATISTICS
    # -----------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return current ingestion storage statistics."""

        try:
            stats = self.store.get_stats()

            return {
                "service": "ORBIT Document Ingestion",
                "batch_size": self.batch_size,
                "vector_store": stats,
            }

        except VectorStoreError as exc:

            raise IngestionError(
                f"Unable to retrieve ingestion statistics: {exc}"
            ) from exc


# ---------------------------------------------------------
# SHARED INGESTION INSTANCE
# ---------------------------------------------------------

ingestion_service = OrbitIngestionService()


# ---------------------------------------------------------
# CONVENIENCE FUNCTIONS
# ---------------------------------------------------------

def ingest_document(
    file_path: str,
    source_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Ingest one document into ORBIT RAG."""

    return ingestion_service.ingest_document(
        file_path=file_path,
        source_name=source_name,
    )


def ingest_multiple_documents(
    file_paths: Sequence[str],
) -> Dict[str, Any]:
    """Ingest multiple documents into ORBIT RAG."""

    return ingestion_service.ingest_multiple_documents(
        file_paths=file_paths,
    )


def get_ingestion_stats() -> Dict[str, Any]:
    """Get current vector storage statistics."""

    return ingestion_service.get_stats()
