"""Tests de la capa de aplicación: checksum, reintentos y duplicados ante persistence-service."""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import HTTPException

from app import compute_checksum, save_to_persistence, settings

URL = f"{settings.persistence_service_url}/documents"
BY_CHECKSUM_URL = f"{URL}/by-checksum/abc123"
REQUEST = httpx.Request("POST", URL)

TEXT = "texto extraido del pdf"
CHECKSUM = "abc123"
PAYLOAD = {"id": "doc-1", "content": TEXT, "checksum": CHECKSUM}
EXISTING = {"id": "doc-42", "content": "texto previo", "checksum": CHECKSUM}


def _response(status_code: int, payload: dict | None = None) -> httpx.Response:
    return httpx.Response(status_code, json=payload, request=REQUEST)


def _connect_error() -> httpx.ConnectError:
    return httpx.ConnectError("connection refused", request=REQUEST)


def test_compute_checksum_matches_known_sha256_digest():
    assert compute_checksum(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_compute_checksum_is_stable_for_the_same_input():
    content = b"%PDF-1.4 contenido identico"

    assert compute_checksum(content) == compute_checksum(content)


def test_compute_checksum_differs_for_different_input():
    assert compute_checksum(b"documento a") != compute_checksum(b"documento b")


def test_save_to_persistence_returns_response_on_first_attempt():
    post = AsyncMock(return_value=_response(201, PAYLOAD))

    with patch("httpx.AsyncClient.post", new=post):
        result = asyncio.run(save_to_persistence(TEXT, CHECKSUM))

    assert result == PAYLOAD
    post.assert_called_once_with(URL, json={"content": TEXT, "checksum": CHECKSUM})


def test_save_to_persistence_retries_until_success():
    post = AsyncMock(side_effect=[_connect_error(), _connect_error(), _response(201, PAYLOAD)])

    with patch("httpx.AsyncClient.post", new=post):
        result = asyncio.run(save_to_persistence(TEXT, CHECKSUM))

    assert result == PAYLOAD
    assert post.await_count == 3


@pytest.mark.parametrize("failure", [_connect_error(), _response(500)])
def test_save_to_persistence_raises_502_after_three_failed_attempts(failure):
    post = AsyncMock(side_effect=[failure] * 3)

    with patch("httpx.AsyncClient.post", new=post), pytest.raises(HTTPException) as exc_info:
        asyncio.run(save_to_persistence(TEXT, CHECKSUM))

    assert exc_info.value.status_code == 502
    assert "persistence-service" in exc_info.value.detail
    assert post.await_count == 3


def test_save_to_persistence_returns_existing_document_on_conflict():
    post = AsyncMock(return_value=_response(409))
    get = AsyncMock(return_value=_response(200, EXISTING))

    with patch("httpx.AsyncClient.post", new=post), patch("httpx.AsyncClient.get", new=get):
        result = asyncio.run(save_to_persistence(TEXT, CHECKSUM))

    assert result == EXISTING
    post.assert_awaited_once_with(URL, json={"content": TEXT, "checksum": CHECKSUM})
    get.assert_awaited_once_with(BY_CHECKSUM_URL)


def test_save_to_persistence_skips_conflict_lookup_without_conflict():
    post = AsyncMock(return_value=_response(201, PAYLOAD))
    get = AsyncMock()

    with patch("httpx.AsyncClient.post", new=post), patch("httpx.AsyncClient.get", new=get):
        result = asyncio.run(save_to_persistence(TEXT, CHECKSUM))

    assert result == PAYLOAD
    get.assert_not_awaited()


@pytest.mark.parametrize("lookup_failure", [_connect_error(), _response(404)])
def test_save_to_persistence_raises_502_when_conflict_lookup_fails(lookup_failure):
    post = AsyncMock(side_effect=[_response(409)] * 3)
    get = AsyncMock(side_effect=[lookup_failure] * 3)

    with (
        patch("httpx.AsyncClient.post", new=post),
        patch("httpx.AsyncClient.get", new=get),
        pytest.raises(HTTPException) as exc_info,
    ):
        asyncio.run(save_to_persistence(TEXT, CHECKSUM))

    assert exc_info.value.status_code == 502
    assert post.await_count == 3
    assert get.await_count == 3
