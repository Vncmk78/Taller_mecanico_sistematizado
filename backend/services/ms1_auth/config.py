"""Configuración del microservicio MS1: Autenticación y Usuarios.

Las variables se leen con el prefijo MS1_ para que los cuatro servicios
puedan convivir en un mismo archivo .env sin pisarse.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from shared.config import ServiceSettings
from shared.entorno import archivo_entorno
from shared.direccion_notificaciones import url_notificaciones_por_defecto


class Settings(ServiceSettings):
    model_config = SettingsConfigDict(
        env_file=archivo_entorno(),
        env_file_encoding="utf-8",
        env_prefix="MS1_",
        extra="ignore",
    )

    NOTIFICATION_WORKER_ENABLED: bool = False
    NOTIFICATION_POLL_SECONDS: float = Field(default=2, gt=0)
    NOTIFICATION_TIMEOUT_SECONDS: float = Field(default=10, gt=0, le=30)
    SMTP_HOST: str | None = None
    SMTP_PORT: int = Field(default=587, gt=0, le=65535)
    SMTP_USUARIO: str | None = None
    SMTP_CLAVE: SecretStr | None = None
    SMTP_REMITENTE: str | None = None
    SMTP_MODO: Literal["starttls", "ssl", "sin_tls_local"] = "starttls"
    FCM_PROJECT_ID: str | None = None
    FCM_CREDENTIALS_FILE: str | None = None

    MS2_URL: str = Field(default_factory=lambda: url_notificaciones_por_defecto(2))
    MS2_NOTIFICATION_SECRET: SecretStr | None = Field(default=None, min_length=32)
    MS3_EVENT_SHARED_SECRET: SecretStr | None = Field(default=None, min_length=32)

    SERVICE_NAME: str = "MS1 — Autenticación y Usuarios"
    DATABASE_URL: str = "postgresql+psycopg://taller:taller@localhost:5433/taller_ms1"

    # El secreto es obligatorio y solo se obtiene del entorno; nunca del código.
    JWT_SECRET_KEY: SecretStr = Field(min_length=32)
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    JWT_EXPIRE_MINUTES: int = Field(default=60, gt=0)

    # Secreto independiente del JWT, compartido solo entre MS1 y MS2 para el
    # contrato interno de eventos. Si falta, la ruta interna queda deshabilitada.
    EVENT_SHARED_SECRET: SecretStr | None = Field(default=None, min_length=32)
    # Tratamiento de intentos repetidos de autenticación incorrecta: tras
    # `LOGIN_MAX_INTENTOS` fallos consecutivos, la cuenta queda bloqueada
    # temporalmente durante `LOGIN_BLOQUEO_MINUTOS` minutos.
    LOGIN_MAX_INTENTOS: int = Field(default=5, gt=0)
    LOGIN_BLOQUEO_MINUTOS: int = Field(default=15, gt=0)


settings = Settings()
