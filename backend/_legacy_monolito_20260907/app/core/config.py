"""Configuración central del backend.

Lee las variables de entorno (o el archivo .env) usando pydantic-settings,
tal como exige la validación con Pydantic definida en el stack del proyecto.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Cadena de conexión a PostgreSQL usando el driver psycopg (v3).
    DATABASE_URL: str = "postgresql+psycopg://taller:taller@localhost:5432/taller"

    # Si es True, SQLAlchemy imprime el SQL que ejecuta (útil al depurar).
    DB_ECHO: bool = False


# Instancia única que importa el resto de la aplicación.
settings = Settings()
