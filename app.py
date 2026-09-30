"""Extraction service: capa de aplicación, lógica de negocio encapsulada."""

import hashlib
import logging

import httpx
from fastapi import HTTPException
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

SAFE_PERSISTENCE_ERROR = "No se pudo guardar el documento en persistence-service"


class Settings(BaseSettings):
    persistence_service_url: str = "http://persistence-service:8000"


settings = Settings()


def compute_checksum(content: bytes) -> str:
    """Checksum SHA-256 del contenido binario; identifica duplicados de forma inequívoca."""
    return hashlib.sha256(content).hexdigest()


async def _post_document(content: str, checksum: str) -> dict:
    """POST a /documents; ante un 409 el checksum ya existe y el documento previo
    es el resultado válido (deduplicación idempotente por checksum)."""
    url = f"{settings.persistence_service_url}/documents"
    payload = {"content": content, "checksum": checksum}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        if response.status_code == 409:
            return await _fetch_existing_document(client, checksum)
        response.raise_for_status()
        return response.json()


async def _fetch_existing_document(client: httpx.AsyncClient, checksum: str) -> dict:
    """Recupera el documento ya persistido; ante cualquier fallo responde 502 sin reintentos.

    El POST que la precedió llegó a persistir, así que reintentar aquí solo repetiría
    el mismo error; el cliente que recibe el 502 re-envía el PDF y el ciclo empieza de nuevo.
    """
    url = f"{settings.persistence_service_url}/documents/by-checksum/{checksum}"
    try:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
    except (httpx.RequestError, httpx.HTTPStatusError) as error:
        logger.error(
            "no se pudo recuperar el documento duplicado (checksum=%s): %s", checksum, error
        )
        raise HTTPException(status_code=502, detail=SAFE_PERSISTENCE_ERROR) from error


async def save_to_persistence(content: str, checksum: str) -> dict:
    """Persiste el documento; un 409 por checksum es éxito.

    Solo se reintenta sobre errores transitorios (RequestError y 5xx). Los 4xx se
    reenvían tal cual y los 3 intentos agotados terminan en 502 sin filtrar internos.
    """
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return await _post_document(content, checksum)
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            if 400 <= status_code < 500:
                logger.error("persistence-service rechazó el documento (%s)", status_code)
                raise HTTPException(
                    status_code=status_code, detail=SAFE_PERSISTENCE_ERROR
                ) from error
            last_error = error
        except httpx.RequestError as error:
            last_error = error
        except HTTPException:
            raise
    logger.error("persistence-service no disponible tras reintentos: %s", last_error)
    raise HTTPException(status_code=502, detail=SAFE_PERSISTENCE_ERROR) from last_error