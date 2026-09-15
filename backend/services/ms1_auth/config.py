"""Configuración del microservicio MS1: Autenticación y Usuarios.

Las variables se leen con el prefijo MS1_ para que los cuatro servicios
puedan convivir en un mismo archivo .env sin pisarse.
"""
from __future__ import annotations

from pydantic_settings import SettingsConfigDict

from shared.config import ServiceSettings


class Settings(ServiceSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MS1_",
        extra="ignore",
    )

    SERVICE_NAME: str = "MS1 — Autenticación y Usuarios"
    DATABASE_URL: str = (
        "postgresql+psycopg://taller:taller@localhost:5433/taller_ms1"
    )


settings = Settings()
