"""Configuración del API Gateway.

La Gateway es el único punto de entrada al backend: el frontend (React) y la
app móvil nunca hablan directo con los microservicios. Cada microservicio se
referencia con una variable de entorno `GATEWAY_MS< n>_URL`; si no se define,
se usan los valores por defecto del desarrollo local (puertos 8001-8004).
"""
from __future__ import annotations

import json
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from shared.entorno import archivo_entorno


class GatewaySettings(BaseSettings):
    """Configuración del API Gateway."""

    model_config = SettingsConfigDict(
        env_prefix="GATEWAY_",
        env_file=archivo_entorno(),
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

    # Timeouts hacia los microservicios, por fase (ver estudio-httpx-proxy.md):
    # conectar rápido (3 s) y leer/escribir con margen (15 s). No es un "tiempo
    # total": cada fase de HTTPX tiene su techo y su excepción (Read/WriteTimeout
    # generan 504, ConnectTimeout 502).
    TIMEOUT_CONNECT_SECONDS: float = 3.0
    TIMEOUT_READ_SECONDS: float = 15.0
    TIMEOUT_WRITE_SECONDS: float = 15.0
    TIMEOUT_POOL_SECONDS: float = 5.0
    # Prefijo "evidencias": read/write ampliados porque sube archivos (fotos).
    TIMEOUT_ARCHIVOS_SECONDS: float = 60.0
    # Timeout de lectura/escritura POR SERVICIO (Semana 7, decisión R1 de
    # estudio-resiliencia-timeouts-retries.md). Opcionales: si no se definen,
    # rigen los generales de arriba (y 60 s para "evidencias"). Regla: el de un
    # servicio debe superar la suma de los timeouts de ese servicio hacia sus
    # dependencias (p. ej. MS3 -> MS2 = 3 s). connect y pool siguen globales.
    # env: GATEWAY_MS1_TIMEOUT_SECONDS ... GATEWAY_MS4_TIMEOUT_SECONDS
    MS1_TIMEOUT_SECONDS: float | None = Field(default=None, gt=0, le=300)
    MS2_TIMEOUT_SECONDS: float | None = Field(default=None, gt=0, le=300)
    MS3_TIMEOUT_SECONDS: float | None = Field(default=None, gt=0, le=300)
    MS4_TIMEOUT_SECONDS: float | None = Field(default=None, gt=0, le=300)
    # Segundos que la Gateway sugiere esperar (cabecera Retry-After) en sus
    # 502, 503 y 504 (decisión R3).
    RETRY_AFTER_SECONDS: int = Field(default=5, ge=1, le=3600)
    # Timeout por servicio del health check (GET /api/health/servicios). Corto
    # a propósito: un servicio caído no debe bloquear la respuesta agregada.
    HEALTH_TIMEOUT_SECONDS: float = 2.0

    # Límites de tamaño de body de la Gateway (checklist 4.2 y
    # estudio-almacenamiento-objetos.md §6). La Gateway rechaza con 413 los
    # bodies mayores antes de leerlos o llamar al microservicio.
    # 1 MiB para los prefijos JSON (MS1/MS2/MS3): una búsqueda en el repo
    # (Semana 5) no encontró ningún endpoint de esos servicios ni del frontend
    # que reciba bodies grandes; sus bodies son JSON de tamaño acotado.
    MAX_BODY_BYTES: int = Field(default=1 * 1024 * 1024, gt=0)
    # 12 MiB para "evidencias" (MS4): un multipart con una foto de hasta 10 MB
    # (checklist 1.3) más el margen de la frontera y metadatos del multipart.
    MAX_BODY_ARCHIVOS_BYTES: int = Field(default=12 * 1024 * 1024, gt=0)

    # CORS: orígenes desde los que se permite consumir la Gateway (web, móvil,
    # herramientas de prueba). En desarrollo el frontend corre en localhost:5173.
    # En el entorno se acepta JSON (["http://a","http://b"]) o comas separadas.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:8000",
    ]
    CORS_ALLOW_CREDENTIALS: bool = True
    # Además de la lista, se aceptan los previews de Vercel (*.vercel.app).
    # Vacío desactiva la regex (env: GATEWAY_CORS_ORIGIN_REGEX).
    CORS_ORIGIN_REGEX: str | None = r"https://[a-z0-9-]+\.vercel\.app"

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