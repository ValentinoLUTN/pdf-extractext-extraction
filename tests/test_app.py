"""Tests de la capa de aplicación: checksum y reintentos contra persistence-service."""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import HTTPException

from app import compute_checksum, save_to_persistence, settings

URL = f"{settings.persistence_service_url}/documents"
REQUEST = httpx.Request("POST", URL)

TEXT = "texto extraido del pdf"
CHECKSUM = "abc123"
PAYLOAD = {"id": "doc-1", "content": TEXT, "checksum": CHECKSUM}


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
