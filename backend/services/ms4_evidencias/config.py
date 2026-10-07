"""Configuración del microservicio MS4: Evidencia Multimedia.

Las variables se leen con el prefijo MS4_ para que los cuatro servicios
puedan convivir en un mismo archivo .env sin pisarse.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from shared.config import ServiceSettings


class Settings(ServiceSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MS4_",
        extra="ignore",
    )

    SERVICE_NAME: str = "MS4 — Evidencia Multimedia"
    DATABASE_URL: str = (
        "postgresql+psycopg://taller:taller@localhost:5436/taller_ms4"
    )

    # Almacenamiento de objetos S3-compatible (MinIO en desarrollo, 2.1).
    # Los valores por defecto coinciden con .env.example y son solo para
    # desarrollo local; en cada entorno se definen vía MS4_S3_*.
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "ms4-evidencias"
    S3_SECRET_KEY: str = "cambia-esta-clave-ms4"
    S3_BUCKET: str = "evidencias"
    S3_REGION: str = "us-east-1"
    S3_SECURE: bool = False

    # Endpoint público con el que se firman las URLs de descarga. La firma
    # SigV4 incluye el Host, así que una URL firmada contra el endpoint interno
    # (http://minio:9000) no sirve fuera de esa red. Si se deja vacío se usa
    # S3_ENDPOINT (válido en desarrollo local, donde ambos hosts coinciden).
    S3_PUBLIC_ENDPOINT: str | None = None

    # Vigencia de la URL prefirmada de descarga, en segundos (checklist 3.3).
    URL_DESCARGA_TTL_SECONDS: int = Field(default=300, ge=30, le=3600)

    # MS4 valida nuevamente el JWT sin consultar la base de datos de MS1.
    # Con HS256 debe recibir el mismo secreto configurado en el emisor (MS1).
    JWT_SECRET_KEY: SecretStr = Field(min_length=32)
    JWT_ALGORITHM: Literal["HS256"] = "HS256"

    # MS2 (órdenes): MS4 le pregunta si la orden es visible para quien llama
    # (p. ej. si el cliente es su dueño o el mecánico la atiende) reenviando su
    # mismo JWT. Es la única forma de validar la referencia lógica orden_id sin
    # compartir base (§8). Mismo contrato que MS3.
    MS2_URL: str = "http://localhost:8002"
    MS2_TIMEOUT_SEGUNDOS: float = Field(default=3.0, gt=0, le=30)


settings = Settings()
