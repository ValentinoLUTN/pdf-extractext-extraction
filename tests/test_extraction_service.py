from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi.testclient import TestClient

import routes
from main import app

client = TestClient(app)

PDF = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R >>
endobj
5 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Hello World) Tj ET
endstream
endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000115 00000 n 
0000000266 00000 n 
trailer
<< /Size 4 /Root 1 0 R >>
startxref
0000
%%EOF"""

PERSISTED = {"id": "doc-1", "content": "", "checksum": "abc"}


def _persistence_post(response):
    return patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response))


def _http_response(status_code, payload=None):
    request = httpx.Request("POST", "http://persistence-service:8000/documents")
    return httpx.Response(status_code, json=payload, request=request)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "extraction-service"


def test_extract_valid_pdf_returns_document_and_text():
    post = AsyncMock(
        return_value=MagicMock(
            status_code=201, json=lambda: PERSISTED, raise_for_status=lambda: None
        )
    )
    with patch("httpx.AsyncClient.post", new=post):
        response = client.post("/extract", files={"file": ("doc.pdf", PDF, "application/pdf")})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "content", "checksum", "text"}
    assert body["id"] == "doc-1"
    assert body["checksum"] == "abc"
    assert isinstance(body["text"], str)


def test_extract_duplicate_pdf_returns_existing_document():
    post = AsyncMock(return_value=_http_response(409))
    existing = {"id": "doc-42", "content": "texto previo", "checksum": "abc"}
    get = AsyncMock(return_value=_http_response(200, existing))

    with patch("httpx.AsyncClient.post", new=post), patch("httpx.AsyncClient.get", new=get):
        response = client.post("/extract", files={"file": ("doc.pdf", PDF, "application/pdf")})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "doc-42"
    assert body["content"] == "texto previo"
    assert body["checksum"] == "abc"
    assert isinstance(body["text"], str)


def test_extract_non_pdf_returns_415():
    response = client.post("/extract", files={"file": ("doc.txt", b"not a pdf", "text/plain")})

    assert response.status_code == 415


def test_extract_oversized_file_returns_413(monkeypatch):
    monkeypatch.setattr(routes, "MAX_PDF_SIZE_BYTES", 100)

    response = client.post(
        "/extract", files={"file": ("doc.pdf", b"x" * (200 * 1024), "application/pdf")}
    )

    assert response.status_code == 413