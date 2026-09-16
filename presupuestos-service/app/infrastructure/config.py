"""Configuración centralizada del microservicio MS3, leída de variables de entorno (.env)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Base de datos propia del MS3 (Presupuestos, Repuestos y Proveedores).
    database_url: str = (
        "postgresql+psycopg2://presupuestos_user:presupuestos_pass"
        "@localhost:5435/presupuestos_service_db"
    )

    # CORS: dominio del frontend (Vite dev server por defecto).
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
