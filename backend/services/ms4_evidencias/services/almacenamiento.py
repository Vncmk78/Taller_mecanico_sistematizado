"""Cliente S3 y operaciones de almacenamiento para MS4.

El archivo de la evidencia vive en MinIO/S3; este módulo construye el cliente
con la configuración MS4_S3_* (settings) y provee las operaciones de subida,
cálculo de integridad y borrado. La firma es s3v4 y el direccionamiento es por
path (misma configuración que ya probó scripts/prueba_minio.py contra MinIO).
"""
from __future__ import annotations

import hashlib

import boto3
from botocore.config import Config
from boto3.s3.transfer import TransferConfig

from services.ms4_evidencias.config import Settings

# Lectura del archivo en bloques de 1 MiB para no cargarlo entero en memoria.
TAMANO_BLOQUE = 1024 * 1024

# Multipart desde 8 MiB (decisión 3 del estudio de almacenamiento).
UPLOAD_TRANSFER = TransferConfig(multipart_threshold=8 * 1024 * 1024)


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


def calcular_sha256_y_tamano(archivo) -> tuple[str, int]:
    """SHA-256 y tamaño del archivo leyéndolo en bloques de 1 MiB.

    Al terminar deja el archivo al inicio (`seek(0)`) para que la subida
    posterior lea el contenido completo.
    """
    digest = hashlib.sha256()
    tamano = 0
    while True:
        bloque = archivo.read(TAMANO_BLOQUE)
        if not bloque:
            break
        digest.update(bloque)
        tamano += len(bloque)
    archivo.seek(0)
    return digest.hexdigest(), tamano


def subir_objeto(cliente: object, bucket: str, clave: str, archivo, content_type: str) -> None:
    """Sube el archivo a MinIO/S3 con multipart desde 8 MiB (decisión 3)."""
    cliente.upload_fileobj(
        archivo,
        bucket,
        clave,
        ExtraArgs={"ContentType": content_type},
        Config=UPLOAD_TRANSFER,
    )


def eliminar_objeto(cliente: object, bucket: str, clave: str) -> None:
    """Borra el objeto; se usa para deshacer la subida si la base falla."""
    cliente.delete_object(Bucket=bucket, Key=clave)
