"""Configuración del microservicio MS2: Vehículos y Órdenes de Trabajo.

Las variables se leen con el prefijo MS2_ para que los cuatro servicios
puedan convivir en un mismo archivo .env sin pisarse.
"""
from __future__ import annotations

from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
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

    # MS2 valida nuevamente el JWT sin consultar la base de datos de MS1.
    # Con HS256 debe recibir el mismo secreto configurado en el emisor (MS1).
    JWT_SECRET_KEY: SecretStr = Field(min_length=32)
    JWT_ALGORITHM: Literal["HS256"] = "HS256"

    MS3_URL: str = "http://localhost:8003"
    MS3_TIMEOUT_SEGUNDOS: float = Field(default=3.0, gt=0, le=30)
    TIMEZONE: str = "America/Santiago"

    @field_validator("TIMEZONE")
    @classmethod
    def validar_zona_horaria(cls, valor: str) -> str:
        try:
            ZoneInfo(valor)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("MS2_TIMEZONE debe ser una zona IANA válida") from exc
        return valor


settings = Settings()
