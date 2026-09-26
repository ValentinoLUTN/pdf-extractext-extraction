"""Extraction service: capa de aplicación, lógica de negocio encapsulada."""

import hashlib

import httpx
from fastapi import HTTPException
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    persistence_service_url: str = "http://persistence-service:8000"


settings = Settings()


def compute_checksum(content: bytes) -> str:
    """Checksum SHA-256 del contenido binario; identifica duplicados de forma inequívoca."""
    return hashlib.sha256(content).hexdigest()


async def save_to_persistence(content: str, checksum: str) -> dict:
    base_url = settings.persistence_service_url
    url = f"{base_url}/documents"
    payload = {
        "content": content,
        "checksum": checksum,
    }

    retries = 3
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code == 409:
                    return await _fetch_existing_document(client, base_url, checksum)
                response.raise_for_status()
                return response.json()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            if attempt == retries - 1:
                raise HTTPException(
                    status_code=502,
                    detail=f"Error communicating with persistence-service: {e!s}",
                ) from e
    return {}


async def _fetch_existing_document(client: httpx.AsyncClient, base_url: str, checksum: str) -> dict:
    """Un 409 significa que el checksum ya existe; el documento previo es el resultado válido."""
    response = await client.get(f"{base_url}/documents/by-checksum/{checksum}")
    response.raise_for_status()
    return response.json()
