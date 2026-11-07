
"""
ORBIT RAG - Document Loader

Supports:
- PDF files
- TXT files
- CSV files
- Text cleaning
- Configurable chunking
- Document metadata
- Batch processing

Extracted chunks are ready for embedding and ChromaDB.
"""

import csv
import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pypdf import PdfReader


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".csv",
}

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

MAX_FILES_PER_BATCH = 50


# ---------------------------------------------------------
# CUSTOM EXCEPTION
# ---------------------------------------------------------

class DocumentLoaderError(Exception):
    """Raised when document loading or processing fails."""


# ---------------------------------------------------------
# DOCUMENT LOADER
# ---------------------------------------------------------

class DocumentLoader:
    """
    Loads business documents and converts them into
    metadata-rich text chunks.
    """

    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
    ):

        if chunk_size < 100:
            raise ValueError(
                "Chunk size must be at least 100."
            )

        if chunk_overlap < 0:
            raise ValueError(
                "Chunk overlap cannot be negative."
            )

        if chunk_overlap >= chunk_size:
            raise ValueError(
                "Chunk overlap must be smaller than chunk size."
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    # -----------------------------------------------------
    # FILE VALIDATION
    # -----------------------------------------------------

    @staticmethod
    def validate_file(
        file_path: str,
    ) -> Path:

        path = Path(file_path).expanduser()

        if not path.exists():
            raise DocumentLoaderError(
                f"File does not exist: {path}"
            )

        if not path.is_file():
            raise DocumentLoaderError(
                "Provided path is not a file."
            )

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise DocumentLoaderError(
                f"Unsupported file type: {path.suffix}"
            )

        if path.stat().st_size > MAX_FILE_SIZE:
            raise DocumentLoaderError(
                "File exceeds the maximum allowed size of 20 MB."
            )

        if path.stat().st_size == 0:
            raise DocumentLoaderError(
                "File is empty."
            )

        return path

    # -----------------------------------------------------
    # TEXT CLEANING
    # -----------------------------------------------------

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Normalize whitespace while preserving paragraphs.
        """

        if not isinstance(text, str):
            return ""

        text = text.replace("\x00", " ")

        text = text.replace("\r\n", "\n")
        text = text.replace("\r", "\n")

        text = re.sub(
            r"[ \t]+",
            " ",
            text,
        )

        text = re.sub(
            r"\n[ \t]+",
            "\n",
            text,
        )

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        return text.strip()

    # -----------------------------------------------------
    # PDF EXTRACTION
    # -----------------------------------------------------

    def load_pdf(
        self,
        path: Path,
    ) -> List[Dict[str, Any]]:
        """
        Extract text page by page from a PDF.
        """

        pages = []

        try:
            reader = PdfReader(str(path))

            if reader.is_encrypted:
                raise DocumentLoaderError(
                    "Encrypted PDFs are not supported."
                )

            if len(reader.pages) > 500:
                raise DocumentLoaderError(
                    "PDF exceeds the maximum page limit of 500."
                )

            for page_number, page in enumerate(
                reader.pages,
                start=1,
            ):

                extracted = page.extract_text() or ""

                cleaned = self.clean_text(extracted)

                if not cleaned:
                    logger.warning(
                        "No extractable text on PDF page %s: %s",
                        page_number,
                        path.name,
                    )
                    continue

                pages.append({
                    "text": cleaned,
                    "page": page_number,
                })

            if not pages:
                raise DocumentLoaderError(
                    "No extractable text found in PDF."
                )

            return pages

        except DocumentLoaderError:
            raise

        except Exception as exc:
            raise DocumentLoaderError(
                f"Failed to read PDF: {exc}"
            ) from exc

    # -----------------------------------------------------
    # TXT EXTRACTION
    # -----------------------------------------------------

    def load_txt(
        self,
        path: Path,
    ) -> List[Dict[str, Any]]:
        """
        Read a UTF-8 text file.
        """

        try:
            text = path.read_text(
                encoding="utf-8-sig",
            )

            cleaned = self.clean_text(text)

            if not cleaned:
                raise DocumentLoaderError(
                    "Text file contains no readable content."
                )

            return [{
                "text": cleaned,
                "page": None,
            }]

        except DocumentLoaderError:
            raise

        except UnicodeDecodeError as exc:
            raise DocumentLoaderError(
                "TXT file must use UTF-8 encoding."
            ) from exc

        except OSError as exc:
            raise DocumentLoaderError(
                f"Failed to read TXT file: {exc}"
            ) from exc

    # -----------------------------------------------------
    # CSV EXTRACTION
    # -----------------------------------------------------

    def load_csv(
        self,
        path: Path,
    ) -> List[Dict[str, Any]]:
        """
        Convert CSV rows into readable text records.

        Each row is represented using column names
        so the embedding model receives context.
        """

        records = []

        try:
            with path.open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as csv_file:

                reader = csv.DictReader(csv_file)

                if not reader.fieldnames:
                    raise DocumentLoaderError(
                        "CSV file does not contain headers."
                    )

                headers = [
                    header.strip()
                    if header
                    else ""
                    for header in reader.fieldnames
                ]

                if not any(headers):
                    raise DocumentLoaderError(
                        "CSV headers are empty."
                    )

                for row_number, row in enumerate(
                    reader,
                    start=1,
                ):

                    values = []

                    for original_key, value in row.items():

                        if original_key is None:
                            continue

                        key = original_key.strip()
                        value = (value or "").strip()

                        if not key or not value:
                            continue

                        values.append(
                            f"{key}: {value}"
                        )

                    if not values:
                        continue

                    records.append({
                        "text": " | ".join(values),
                        "page": None,
                        "row": row_number,
                    })

                    if len(records) > 100_000:
                        raise DocumentLoaderError(
                            "CSV exceeds the maximum row limit."
                        )

            if not records:
                raise DocumentLoaderError(
                    "CSV file contains no usable records."
                )

            return records

        except DocumentLoaderError:
            raise

        except (UnicodeDecodeError, csv.Error, OSError) as exc:
            raise DocumentLoaderError(
                f"Failed to read CSV: {exc}"
            ) from exc

    # -----------------------------------------------------
    # FILE EXTRACTION ROUTER
    # -----------------------------------------------------

    def extract_text(
        self,
        file_path: str,
    ) -> List[Dict[str, Any]]:
        """
        Detect file type and extract its content.
        """

        path = self.validate_file(file_path)

        extension = path.suffix.lower()

        if extension == ".pdf":
            extracted = self.load_pdf(path)

        elif extension == ".txt":
            extracted = self.load_txt(path)

        elif extension == ".csv":
            extracted = self.load_csv(path)

        else:
            raise DocumentLoaderError(
                "Unsupported document format."
            )

        return extracted

    # -----------------------------------------------------
    # TEXT CHUNKING
    # -----------------------------------------------------

    def split_text(
        self,
        text: str,
    ) -> List[str]:
        """
        Split text into overlapping chunks.

        Attempts to split at paragraph or sentence
        boundaries before falling back to word boundaries.
        """

        text = self.clean_text(text)

        if not text:
            return []

        if len(text) <= self.chunk_size:
            return [text]

        chunks = []

        start = 0
        text_length = len(text)

        while start < text_length:

            end = min(
                start + self.chunk_size,
                text_length,
            )

            if end < text_length:

                minimum_end = start + int(
                    self.chunk_size * 0.7
                )

                candidates = [
                    text.rfind("\n\n", minimum_end, end),
                    text.rfind(". ", minimum_end, end),
                    text.rfind("? ", minimum_end, end),
                    text.rfind("! ", minimum_end, end),
                    text.rfind(" ", minimum_end, end),
                ]

                valid_candidates = [
                    position
                    for position in candidates
                    if position >= minimum_end
                ]

                if valid_candidates:
                    end = max(valid_candidates) + 1

            chunk = text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            if end >= text_length:
                break

            next_start = end - self.chunk_overlap

            if next_start <= start:
                next_start = end

            start = next_start

        return chunks

    # -----------------------------------------------------
    # DOCUMENT PROCESSING
    # -----------------------------------------------------

    def process_document(
        self,
        file_path: str,
        source_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract and chunk a document.

        Returns chunks ready for vector storage.
        """

        path = self.validate_file(file_path)

        source = source_name or path.name

        extracted_sections = self.extract_text(
            str(path)
        )

        processed_chunks = []

        document_hash = self._file_hash(path)

        # Detect the primary reporting year from document content.
        # Counting occurrences is more reliable than taking the first year,
        # because reports may mention prior-year comparisons in passing.
        full_document_text = "\n".join(
            section.get("text", "") for section in extracted_sections
        )
        year_matches = re.findall(
            r"\b(?:19|20)\d{2}\b",
            full_document_text,
        )
        year_counts = {year: year_matches.count(year) for year in year_matches}
        document_year = (
            int(max(year_counts, key=year_counts.get))
            if year_counts
            else None
        )

        for section_index, section in enumerate(
            extracted_sections,
            start=1,
        ):

            text_chunks = self.split_text(
                section["text"]
            )

            for chunk_index, chunk in enumerate(
                text_chunks,
                start=1,
            ):

                chunk_id = self._generate_chunk_id(
                    document_hash=document_hash,
                    section_index=section_index,
                    chunk_index=chunk_index,
                )

                metadata = {
                    "source": source,
                    "file_name": path.name,
                    "file_type": path.suffix.lower(),
                    "chunk_index": chunk_index,
                    "section_index": section_index,
                    "document_hash": document_hash,
                }

                if document_year is not None:
                    metadata["year"] = document_year

                if section.get("page") is not None:
                    metadata["page"] = section["page"]

                if section.get("row") is not None:
                    metadata["row"] = section["row"]

                processed_chunks.append({
                    "id": chunk_id,
                    "text": chunk,
                    "metadata": metadata,
                })

        if not processed_chunks:
            raise DocumentLoaderError(
                "Document processing produced no chunks."
            )

        return processed_chunks

    # -----------------------------------------------------
    # FILE HASH
    # -----------------------------------------------------

    @staticmethod
    def _file_hash(
        path: Path,
    ) -> str:
        """
        Generate a SHA-256 hash of the source file.
        """

        sha256 = hashlib.sha256()

        with path.open("rb") as file:
            for block in iter(
                lambda: file.read(1024 * 1024),
                b"",
            ):
                sha256.update(block)

        return sha256.hexdigest()

    # -----------------------------------------------------
    # CHUNK ID GENERATION
    # -----------------------------------------------------

    @staticmethod
    def _generate_chunk_id(
        document_hash: str,
        section_index: int,
        chunk_index: int,
    ) -> str:

        return (
            f"{document_hash[:16]}_"
            f"{section_index}_"
            f"{chunk_index}"
        )

    # -----------------------------------------------------
    # BATCH PROCESSING
    # -----------------------------------------------------

    def process_multiple_documents(
        self,
        file_paths: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Process multiple files.

        Individual file errors are reported without
        stopping the remaining files.
        """

        if not file_paths:
            raise ValueError(
                "At least one file path is required."
            )

        if len(file_paths) > MAX_FILES_PER_BATCH:
            raise ValueError(
                f"Maximum {MAX_FILES_PER_BATCH} files allowed."
            )

        all_chunks = []
        failures = []

        for file_path in file_paths:

            try:
                chunks = self.process_document(
                    file_path
                )

                all_chunks.extend(chunks)

            except (
                DocumentLoaderError,
                OSError,
                ValueError,
            ) as exc:

                logger.exception(
                    "Failed to process document: %s",
                    file_path,
                )

                failures.append({
                    "file": str(file_path),
                    "error": str(exc),
                })

        if not all_chunks and failures:
            raise DocumentLoaderError(
                f"All document processing failed: {failures}"
            )

        return all_chunks


# ---------------------------------------------------------
# SHARED DOCUMENT LOADER
# ---------------------------------------------------------

document_loader = DocumentLoader()


# ---------------------------------------------------------
# CONVENIENCE FUNCTION
# ---------------------------------------------------------

def load_and_split_document(
    file_path: str,
) -> List[Dict[str, Any]]:
    """
    Convenience function for processing one document.
    """

    return document_loader.process_document(
        file_path
    )
