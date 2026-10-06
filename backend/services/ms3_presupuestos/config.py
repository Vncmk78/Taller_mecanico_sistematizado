"""Configuración del microservicio MS3: Presupuestos, Repuestos y Proveedores.

Las variables se leen con el prefijo MS3_ para que los cuatro servicios
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
        env_prefix="MS3_",
        extra="ignore",
    )

    SERVICE_NAME: str = "MS3 — Presupuestos, Repuestos y Proveedores"
    DATABASE_URL: str = (
        "postgresql+psycopg://taller:taller@localhost:5435/taller_ms3"
    )

    # MS3 valida el JWT sin consultar la base de MS1 (mismo contrato que MS2 y
    # MS4). Con HS256 debe recibir el mismo secreto configurado en MS1.
    JWT_SECRET_KEY: SecretStr = Field(min_length=32)
    JWT_ALGORITHM: Literal["HS256"] = "HS256"

    # MS2 (órdenes): MS3 le pregunta si una orden es visible para quien llama
    # (p. ej. si el cliente es su dueño) reenviando su mismo JWT. Es la única
    # forma de validar la referencia lógica orden_id sin compartir base (§8).
    MS2_URL: str = "http://localhost:8002"
    MS2_TIMEOUT_SEGUNDOS: float = Field(default=3.0, gt=0, le=30)


settings = Settings()
