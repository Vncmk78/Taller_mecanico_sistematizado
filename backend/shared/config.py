"""Configuración base compartida por los cuatro microservicios.

Cada servicio define su propia subclase con su prefijo de variables de entorno,
de modo que un mismo archivo .env pueda contener las cuatro cadenas de conexión
sin que un servicio lea por error la base de otro.

Fuente: Sistematización final §1.2 (una base PostgreSQL independiente por
microservicio) y §8 (aislamiento de datos: sin dependencias entre esquemas).
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    """Configuración mínima que necesita un servicio para hablar con su base."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Nombre del servicio; se usa en logs y en el healthcheck.
    SERVICE_NAME: str = "servicio"

    # Cadena de conexión a SU base.
    # Formato: postgresql+psycopg://USUARIO:PASSWORD@HOST:PUERTO/NOMBRE_BD
    DATABASE_URL: str = ""

    # Imprime en consola el SQL que ejecuta SQLAlchemy (solo para depurar).
    DB_ECHO: bool = False

    # Tamaño del pool de conexiones.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
