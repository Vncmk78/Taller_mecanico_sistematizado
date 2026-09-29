"""Integración mínima MS4 ↔ MinIO (S3) como test de pytest.

Mismo flujo que ``scripts/prueba_minio.py``: con el usuario de mínimo
privilegio de MS4 sube un archivo de 256 KB, consulta metadatos, lo descarga
(por S3 y por URL prefirmada) y compara el SHA-256, verifica que el acceso
anónimo responde 403, y borra el objeto.

Si MinIO no está levantado el test se omite (skip) en lugar de fallar, para no
romper la suite en un equipo sin Docker.
"""
from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
import uuid

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import (
    ConnectTimeoutError,
    ConnectionClosedError,
    EndpointConnectionError,
    ReadTimeoutError,
)

from services.ms4_evidencias.config import Settings

TAMANO_PRUEBA = 256 * 1024

_ERRORES_MINIO_APAGADO = (
    EndpointConnectionError,
    ConnectTimeoutError,
    ReadTimeoutError,
    ConnectionClosedError,
    ConnectionRefusedError,
    TimeoutError,
)


def _crear_cliente(cfg: Settings):
    return boto3.client(
        "s3",
        endpoint_url=cfg.S3_ENDPOINT,
        aws_access_key_id=cfg.S3_ACCESS_KEY,
        aws_secret_access_key=cfg.S3_SECRET_KEY,
        region_name=cfg.S3_REGION,
        use_ssl=cfg.S3_SECURE,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=15,
            retries={"max_attempts": 1},
        ),
    )


@pytest.fixture
def cliente_minio():
    cfg = Settings()
    cliente = _crear_cliente(cfg)
    try:
        # Comprobación de conectividad con un permiso que el usuario mínimo
        # sí tiene: listar su propio bucket.
        cliente.list_objects_v2(Bucket=cfg.S3_BUCKET, MaxKeys=1)
    except _ERRORES_MINIO_APAGADO:
        pytest.skip("MinIO no está disponible (docker compose up -d minio minio_init)")
    return cfg, cliente


def test_guardado_y_recuperacion_con_usuario_ms4(cliente_minio):
    cfg, cliente = cliente_minio
    datos = (bytes(range(256)) * (TAMANO_PRUEBA // 256))[:TAMANO_PRUEBA]
    checksum = hashlib.sha256(datos).hexdigest()
    clave = f"pruebas/{uuid.uuid4().hex}.bin"

    try:
        # 3. Subida con clave UUID (checklist 1.4 y 2.5).
        cliente.put_object(
            Bucket=cfg.S3_BUCKET, Key=clave, Body=datos, ContentType="application/octet-stream"
        )

        # 4. Metadatos: tamaño y tipo del objeto guardado.
        meta = cliente.head_object(Bucket=cfg.S3_BUCKET, Key=clave)
        assert meta["ContentLength"] == len(datos)
        assert meta.get("ContentType", "application/octet-stream") == "application/octet-stream"

        # 5. Descarga con el usuario de MS4 e integridad SHA-256 (2.4).
        cuerpo = cliente.get_object(Bucket=cfg.S3_BUCKET, Key=clave)["Body"].read()
        assert hashlib.sha256(cuerpo).hexdigest() == checksum, "El archivo descargado no es idéntico"

        # 6. URL prefirmada de 5 minutos descarga el mismo contenido (3.3).
        url_firmada = cliente.generate_presigned_url(
            "get_object",
            Params={"Bucket": cfg.S3_BUCKET, "Key": clave},
            ExpiresIn=5 * 60,
        )
        with urllib.request.urlopen(url_firmada, timeout=30) as respuesta:
            cuerpo_firmado = respuesta.read()
        assert hashlib.sha256(cuerpo_firmado).hexdigest() == checksum

        # 7. GET anónimo al objeto responde 403: bucket privado (2.1).
        url_objeto = f"{cfg.S3_ENDPOINT.rstrip('/')}/{cfg.S3_BUCKET}/{clave}"
        with pytest.raises(urllib.error.HTTPError) as capturado:
            urllib.request.urlopen(url_objeto, timeout=10)
        assert capturado.value.code == 403
    finally:
        try:
            cliente.delete_object(Bucket=cfg.S3_BUCKET, Key=clave)
        except Exception:
            pass