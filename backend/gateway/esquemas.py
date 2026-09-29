"""Esquemas Pydantic del formato común de la API Gateway.

Se reutilizan en la documentación OpenAPI/Swagger (tarea 2) para describir
las respuestas de error en cada endpoint.
"""
from __future__ import annotations

from pydantic import BaseModel


class DetalleError(BaseModel):
    """Bloque de detalle de todo error generado por la propia Gateway."""

    codigo: str
    estado: int
    ruta: str
    request_id: str


class ErrorRespuesta(BaseModel):
    """Cuerpo común de error de la Gateway.

    `detail` se mantiene como string de primer nivel porque el frontend lee
    `response.data.detail` para mostrar los mensajes de error.
    """

    detail: str
    error: DetalleError