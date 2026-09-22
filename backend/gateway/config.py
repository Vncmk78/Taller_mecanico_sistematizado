"""Configuración del API Gateway.

La Gateway es el único punto de entrada al backend: el frontend (React) y la
app móvil nunca hablan directo con los microservicios. Cada microservicio se
referencia con una variable de entorno `GATEWAY_MS< n>_URL`; si no se define,
se usan los valores por defecto del desarrollo local (puertos 8001-8004).
"""
from __future__ import annotations

import json
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class GatewaySettings(BaseSettings):
    """Configuración del API Gateway."""

    model_config = SettingsConfigDict(
        env_prefix="GATEWAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Nombre del servicio; se usa en logs y en el healthcheck.
    SERVICE_NAME: str = "gateway"

    # Microservicios de backend (env: GATEWAY_MS1_URL, GATEWAY_MS2_URL, ...)
    MS1_URL: str = "http://localhost:8001"
    MS2_URL: str = "http://localhost:8002"
    MS3_URL: str = "http://localhost:8003"
    MS4_URL: str = "http://localhost:8004"

    # Tiempo máximo de espera a un microservicio antes de responder 504.
    REQUEST_TIMEOUT_SECONDS: float = 30.0

    # CORS: orígenes desde los que se permite consumir la Gateway (web, móvil,
    # herramientas de prueba). En desarrollo el frontend corre en localhost:5173.
    # En el entorno se acepta JSON (["http://a","http://b"]) o comas separadas.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    CORS_ALLOW_CREDENTIALS: bool = True

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _normalizar_origenes(cls, valor: object) -> object:
        """Acepta una lista JSON, una cadena separada por comas o una lista."""
        if isinstance(valor, str):
            texto = valor.strip()
            if texto.startswith("["):
                return json.loads(texto)
            return [origen.strip() for origen in texto.split(",") if origen.strip()]
        return valor


settings = GatewaySettings()