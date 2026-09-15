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


settings = Settings()
