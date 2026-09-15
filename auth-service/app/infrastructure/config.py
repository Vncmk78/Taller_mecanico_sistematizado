"""Configuración centralizada del microservicio, leída desde variables de entorno (.env)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Base de datos propia del MS1 (Autenticación y Usuarios) - ver 01-arquitectura.png
    database_url: str = "postgresql+psycopg2://auth_user:auth_pass@localhost:5432/auth_service_db"

    # JWT (RF-02, RNF-07)
    jwt_secret_key: str = "CAMBIA_ESTA_CLAVE_EN_.env_NUNCA_EN_PRODUCCION"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # CORS: dominio del frontend (Vite dev server por defecto)
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
