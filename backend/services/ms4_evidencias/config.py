"""Configuración del microservicio MS4: Evidencia Multimedia.

Las variables se leen con el prefijo MS4_ para que los cuatro servicios
puedan convivir en un mismo archivo .env sin pisarse.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import SettingsConfigDict

from shared.config import ServiceSettings

# Formatos cuya firma (magic bytes) MS4 sabe reconocer. La lista blanca
# configurable (TIPOS_PERMITIDOS) solo puede usar valores de aquí: habilitar un
# tipo que el servicio no sabe verificar abriría la puerta a archivos
# disfrazados (checklist 1.1 y 1.2).
FORMATOS_SOPORTADOS: frozenset[str] = frozenset(
    {"image/jpeg", "image/png", "image/webp", "video/mp4", "video/quicktime"}
)

MIB = 1024 * 1024


class Settings(ServiceSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MS4_",
        extra="ignore",
    )

    SERVICE_NAME: str = "MS4 — Evidencia Multimedia"
    DATABASE_URL: str = (
        "postgresql+psycopg://taller:taller@localhost:5436/taller_ms4"
    )

    # Almacenamiento de objetos S3-compatible (MinIO en desarrollo, 2.1).
    # Los valores por defecto coinciden con .env.example y son solo para
    # desarrollo local; en cada entorno se definen vía MS4_S3_*.
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "ms4-evidencias"
    S3_SECRET_KEY: str = "cambia-esta-clave-ms4"
    S3_BUCKET: str = "evidencias"
    S3_REGION: str = "us-east-1"
    S3_SECURE: bool = False

    # Endpoint público con el que se firman las URLs de descarga. La firma
    # SigV4 incluye el Host, así que una URL firmada contra el endpoint interno
    # (http://minio:9000) no sirve fuera de esa red. Si se deja vacío se usa
    # S3_ENDPOINT (válido en desarrollo local, donde ambos hosts coinciden).
    S3_PUBLIC_ENDPOINT: str | None = None

    # Vigencia de la URL prefirmada de descarga, en segundos (checklist 3.3).
    URL_DESCARGA_TTL_SECONDS: int = Field(default=300, ge=30, le=3600)

    # Lista blanca de formatos (checklist 1.1). En .env se escribe como JSON:
    # MS4_TIPOS_PERMITIDOS='["image/jpeg","image/png"]'.
    TIPOS_PERMITIDOS: list[str] = Field(
        default_factory=lambda: sorted(FORMATOS_SOPORTADOS), min_length=1
    )

    # Tamaño máximo por tipo de archivo (checklist 1.3): fotos 10 MiB y videos
    # 100 MiB. Por la Gateway nunca entra más de GATEWAY_MAX_BODY_ARCHIVOS_BYTES
    # (12 MiB); el límite de video aplica a la subida directa a MS4.
    MAX_BYTES_FOTO: int = Field(default=10 * MIB, gt=0)
    MAX_BYTES_VIDEO: int = Field(default=100 * MIB, gt=0)

    # MS4 valida nuevamente el JWT sin consultar la base de datos de MS1.
    # Con HS256 debe recibir el mismo secreto configurado en el emisor (MS1).
    JWT_SECRET_KEY: SecretStr = Field(min_length=32)
    JWT_ALGORITHM: Literal["HS256"] = "HS256"

    # MS2 (órdenes): MS4 le pregunta si la orden es visible para quien llama
    # (p. ej. si el cliente es su dueño o el mecánico la atiende) reenviando su
    # mismo JWT. Es la única forma de validar la referencia lógica orden_id sin
    # compartir base (§8). Mismo contrato que MS3.
    MS2_URL: str = "http://localhost:8002"
    MS2_TIMEOUT_SEGUNDOS: float = Field(default=3.0, gt=0, le=30)

    @field_validator("TIPOS_PERMITIDOS")
    @classmethod
    def _solo_formatos_soportados(cls, tipos: list[str]) -> list[str]:
        normalizados = [tipo.strip().lower() for tipo in tipos]
        desconocidos = sorted(set(normalizados) - FORMATOS_SOPORTADOS)
        if desconocidos:
            raise ValueError(
                "TIPOS_PERMITIDOS solo admite "
                f"{sorted(FORMATOS_SOPORTADOS)}; no se reconoce: {desconocidos}"
            )
        return normalizados


settings = Settings()
