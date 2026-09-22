"""Configuración del microservicio MS1: Autenticación y Usuarios.

Las variables se leen con el prefijo MS1_ para que los cuatro servicios
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
        env_prefix="MS1_",
        extra="ignore",
    )

    SERVICE_NAME: str = "MS1 — Autenticación y Usuarios"
    DATABASE_URL: str = (
        "postgresql+psycopg://taller:taller@localhost:5433/taller_ms1"
    )

    # El secreto es obligatorio y solo se obtiene del entorno; nunca del código.
    JWT_SECRET_KEY: SecretStr = Field(min_length=32)
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    JWT_EXPIRE_MINUTES: int = Field(default=60, gt=0)


settings = Settings()
