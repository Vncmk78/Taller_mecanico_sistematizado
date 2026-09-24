"""Configuración del API Gateway.

La Gateway es el único punto de entrada al backend: el frontend (React) y la
app móvil nunca hablan directo con los microservicios. Cada microservicio se
referencia con una variable de entorno `GATEWAY_MS< n>_URL`; si no se define,
se usan los valores por defecto del desarrollo local (puertos 8001-8004).
"""
from __future__ import annotations

import json

from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    """URLs de los cuatro microservicios que la Gateway enruta."""

    model_config = SettingsConfigDict(
        env_prefix="GATEWAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Nombre del servicio; se usa en logs y en el healthcheck.
    SERVICE_NAME: str = "gateway"

    # Microservicios de backend (env: GATEWAY_MS1_URL, GATEWAY_MS2_URL, ...)
    MS1_URL: str = "http://localhost:8001"
    MS2_URL: str = "http://localhost:8002"
    MS3_URL: str = "http://localhost:8003"
    MS4_URL: str = "http://localhost:8004"

    # Tiempo máximo de espera a un microservicio antes de responder 504.
    REQUEST_TIMEOUT_SECONDS: float = 30.0

    # Orígenes permitidos por CORS (env: GATEWAY_CORS_ORIGINS, lista separada
    # por comas o JSON). El frontend desplegado en Vercel y el Vite de desarrollo
    # siempre deben figurar; sin esto el navegador bloquea el preflight por
    # "CORS policy". Además se permite por regex cualquier dominio *.vercel.app.
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8000"

    @property
    def cors_origins_list(self) -> list[str]:
        """Lista de orígenes CORS, tolerando CSV y JSON de entorno.

        pydantic-settings no convierte aut na list[str] desde un valor CSV
        (espera JSON), por lo que se recibe como str y se normaliza aquí.
        """
        valor = self.CORS_ORIGINS.strip()
        if not valor:
            return []
        if valor.startswith("[") and valor.endswith("]"):
            try:
                items = json.loads(valor)
                if isinstance(items, list):
                    return [str(x) for x in items]
            except ValueError:
                pass
        return [o.strip() for o in valor.split(",") if o.strip()]


settings = GatewaySettings()