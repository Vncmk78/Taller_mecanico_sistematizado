"""Cliente S3 y verificación del bucket para MS4 (control 2.1).

El archivo de la evidencia vive en MinIO/S3; este módulo construye el cliente
con la configuración MS4_S3_* (settings) y comprueba que el bucket responde.
La firma es s3v4 y el direccionamiento es por path (misma configuración que ya
probó scripts/prueba_minio.py contra MinIO local).
"""
from __future__ import annotations

import boto3
from botocore.config import Config

from services.ms4_evidencias.config import Settings


def crear_cliente_s3(settings: Settings) -> object:
    """Cliente boto3 de S3 configurado para MinIO (firma v4, path-style)."""
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        use_ssl=settings.S3_SECURE,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=15,
            retries={"max_attempts": 1},
        ),
    )


def verificar_bucket(cliente: object, bucket: str) -> bool:
    """Devuelve True si el bucket existe y responde al usuario de MS4.

    Nunca expone detalles del error ni del bucket: el healthcheck responde 503
    con un mensaje genérico cuando esto devuelve False.
    """
    try:
        cliente.head_bucket(Bucket=bucket)
    except Exception:  # noqa: BLE001  (cualquier fallo = almacenamiento caído)
        return False
    return True
