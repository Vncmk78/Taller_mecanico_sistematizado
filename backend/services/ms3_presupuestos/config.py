"""Configuración del microservicio MS3: Presupuestos, Repuestos y Proveedores.

Las variables se leen con el prefijo MS3_ para que los cuatro servicios
puedan convivir en un mismo archivo .env sin pisarse.
"""
from __future__ import annotations

from pydantic_settings import SettingsConfigDict

from shared.config import ServiceSettings


class Settings(ServiceSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MS3_",
        extra="ignore",
    )

    SERVICE_NAME: str = "MS3 — Presupuestos, Repuestos y Proveedores"
    DATABASE_URL: str = (
        "postgresql+psycopg://taller:taller@localhost:5435/taller_ms3"
    )


settings = Settings()
