"""Extraction service: endpoints HTTP delegando en extractor y lógica de aplicación."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel

from app import compute_checksum, save_to_persistence
from shared.domain import (
    MAX_PDF_SIZE_BYTES,
    PdfExtractionError,
    PyPdfTextExtractor,
    has_pdf_extension,
)

router = APIRouter()

CHUNK_SIZE = 1024 * 1024


class ExtractionResponse(BaseModel):
    id: str
    content: str
    checksum: str
    text: str


def get_extractor() -> PyPdfTextExtractor:
    return PyPdfTextExtractor()


async def _read_limited(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(CHUNK_SIZE):
        total += len(chunk)
        if total > MAX_PDF_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="El archivo excede el tamaño máximo permitido",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/extract", response_model=ExtractionResponse)
async def extract_text(
    file: UploadFile,
    extractor: Annotated[PyPdfTextExtractor, Depends(get_extractor)],
) -> ExtractionResponse:
    if not has_pdf_extension(file.filename):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="El archivo debe tener extensión .pdf",
        )

    try:
        content = await _read_limited(file)
        text = await extractor.extract_text_from_bytes(content)

        checksum = compute_checksum(content)
        persistence_response = await save_to_persistence(text, checksum)

        return ExtractionResponse(
            id=persistence_response.get("id"),
            content=persistence_response.get("content") or text,
            checksum=persistence_response.get("checksum") or checksum,
            text=text,
        )
    except PdfExtractionError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e!s}") from e