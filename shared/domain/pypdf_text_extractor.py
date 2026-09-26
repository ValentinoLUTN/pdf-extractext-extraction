"""Extracción de texto con pypdf, compartida entre monolith y microservicios."""

import asyncio
from io import BytesIO

from pypdf import PdfReader

from shared.domain.exceptions import PdfExtractionError


class PyPdfTextExtractor:
    """Procesa el PDF en memoria con BytesIO, sin crear archivos temporales."""

    async def extract_text_from_bytes(self, pdf_bytes: bytes) -> str:
        """Extrae texto de todas las páginas, o vacío si no hay texto extraíble."""
        if not pdf_bytes:
            raise ValueError("Los bytes del PDF no pueden estar vacíos")

        try:
            return await asyncio.to_thread(self._extract_text, pdf_bytes)
        except Exception as error:
            raise PdfExtractionError(
                message=f"Error al extraer texto con pypdf: {error!s}",
                original_error=error,
            ) from error

    def _extract_text(self, pdf_bytes: bytes) -> str:
        """Parseo síncrono de pypdf; corre en un thread para no bloquear el event loop."""
        reader = PdfReader(BytesIO(pdf_bytes))

        extracted_texts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                extracted_texts.append(page_text)

        return "\n".join(extracted_texts)
