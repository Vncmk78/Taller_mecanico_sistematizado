"""Configuración del microservicio MS4: Evidencia Multimedia.

Las variables se leen con el prefijo MS4_ para que los cuatro servicios
puedan convivir en un mismo archivo .env sin pisarse.
"""
from __future__ import annotations

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


settings = Settings()
