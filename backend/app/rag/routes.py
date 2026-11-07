
import logging
import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..auth import get_current_user
from .ingestion import ingestion_service, IngestionError
from .retriever import retriever
from .answer_generator import generate_rag_answer

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/rag",
    tags=["RAG"],
    dependencies=[Depends(get_current_user)],
)

MAX_UPLOAD_SIZE = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".csv"}

# Match explicit four-digit years in user queries.
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")


class RAGSearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


@router.post("/ingest")
async def ingest_document(file: UploadFile = File(...)):
    """Upload and ingest a PDF, TXT or CSV document."""

    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()

    if not filename or extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, TXT and CSV files are supported.",
        )

    content = await file.read(MAX_UPLOAD_SIZE + 1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Maximum upload size is 20 MB.",
        )

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=extension,
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)

        result = ingestion_service.ingest_document(
            str(temporary_path),
            source_name=filename,
        )

        return result

    except IngestionError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception("RAG document upload failed.")
        raise HTTPException(
            status_code=500,
            detail="Document ingestion failed.",
        ) from exc

    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)

        await file.close()


@router.post("/search")
def search_documents(request: RAGSearchRequest):
    """
    Retrieve relevant document chunks and generate
    a grounded AI answer using local Ollama.

    Supports:
    - Normal semantic search
    - Single-year filtering
    - Multi-year comparison
    - AI-generated answers
    - Source attribution
    """

    try:
        # -------------------------------------------------
        # 1. DETECT YEARS IN THE USER QUESTION
        # -------------------------------------------------

        matched_years = sorted({
            int(year)
            for year in YEAR_PATTERN.findall(request.query)
        })

        metadata_filter = None

        if len(matched_years) == 1:
            metadata_filter = {
                "year": matched_years[0],
            }

        elif len(matched_years) > 1:
            metadata_filter = {
                "year": {
                    "$in": matched_years,
                }
            }

        # -------------------------------------------------
        # 2. RETRIEVE DOCUMENTS
        # -------------------------------------------------

        result = retriever.retrieve_context(
            query=request.query,
            top_k=request.top_k,
            where=metadata_filter,
        )

        result["year_filter"] = matched_years or None

        # -------------------------------------------------
        # 3. CHECK RETRIEVED CONTEXT
        # -------------------------------------------------

        if not result.get("has_context"):
            result["answer"] = (
                "I couldn't find relevant information "
                "in the uploaded documents."
            )

            result["ai_status"] = "skipped"
            result["ai_reason"] = (
                "No relevant document context was retrieved."
            )
            result["ai_model"] = None
            result["ai_duration_ms"] = 0.0

            return result

        # -------------------------------------------------
        # 4. GENERATE AI ANSWER
        # -------------------------------------------------

        ai_result = generate_rag_answer(
            question=request.query,
            context=result["context"],
            sources=result.get("sources", []),
        )

        # -------------------------------------------------
        # 5. HANDLE AI RESPONSE
        # -------------------------------------------------

        if ai_result.get("status") == "accepted":
            result["answer"] = ai_result["answer"]

        else:
            result["answer"] = (
                "Relevant documents were found, but an AI "
                "answer could not be generated. Please review "
                "the retrieved document context."
            )

        # -------------------------------------------------
        # 6. ADD AI METADATA TO RESPONSE
        # -------------------------------------------------

        result["ai_status"] = ai_result.get("status")
        result["ai_reason"] = ai_result.get("reason")
        result["ai_model"] = ai_result.get("model")
        result["ai_duration_ms"] = ai_result.get(
            "duration_ms",
            0.0,
        )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception("RAG semantic search failed.")

        raise HTTPException(
            status_code=500,
            detail="Document search failed.",
        ) from exc


@router.get("/stats")
def rag_stats():
    """Return document ingestion and vector store statistics."""

    try:
        return ingestion_service.get_stats()

    except IngestionError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc
