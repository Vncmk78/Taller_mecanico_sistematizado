"""Configuración del microservicio MS2: Vehículos y Órdenes de Trabajo.

Las variables se leen con el prefijo MS2_ para que los cuatro servicios
puedan convivir en un mismo archivo .env sin pisarse.
"""
from __future__ import annotations

from pydantic_settings import SettingsConfigDict

from shared.config import ServiceSettings


class Settings(ServiceSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MS2_",
        extra="ignore",
    )

    SERVICE_NAME: str = "MS2 — Vehículos y Órdenes de Trabajo"
    DATABASE_URL: str = (
        "postgresql+psycopg://taller:taller@localhost:5434/taller_ms2"
    )


settings = Settings()
