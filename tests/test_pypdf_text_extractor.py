"""Tests del extractor de texto con pypdf: PDFs válidos, sin texto y corruptos."""

import asyncio
from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from shared.domain.exceptions import PdfExtractionError
from shared.domain.pypdf_text_extractor import PyPdfTextExtractor

TEXT = "Informe Anual 2026"

extractor = PyPdfTextExtractor()


def _pdf_bytes(text: str | None = None) -> bytes:
    """PDF de una página armado con pypdf; sin text la página queda sin texto extraíble."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)

    if text is not None:
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 24 Tf 72 700 Td ({text}) Tj ET".encode("latin-1"))
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        page[NameObject("/Contents")] = writer._add_object(stream)

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_extract_text_from_valid_pdf():
    result = asyncio.run(extractor.extract_text_from_bytes(_pdf_bytes(TEXT)))

    assert TEXT in result


def test_extract_text_returns_empty_string_when_pdf_has_no_text():
    result = asyncio.run(extractor.extract_text_from_bytes(_pdf_bytes()))

    assert result == ""


def test_extract_text_raises_pdf_extraction_error_on_corrupt_pdf():
    truncated_pdf = _pdf_bytes(TEXT)[:200]

    with pytest.raises(PdfExtractionError) as exc_info:
        asyncio.run(extractor.extract_text_from_bytes(truncated_pdf))

    assert exc_info.value.original_error is not None
