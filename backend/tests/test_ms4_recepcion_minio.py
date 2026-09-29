"""Integración real MS4 ↔ MinIO del flujo de recepción.

Usa `recibir_evidencia` con el cliente S3 real (usuario de mínimo privilegio de
MS4) y una base SQLite en memoria: sube la evidencia a MinIO, lo descarga y
compara el SHA-256 guardado en la fila. Se salta (skip) si MinIO no está
levantado, igual que `tests/test_ms4_minio_integracion.py`.
"""
from __future__ import annotations

import hashlib
import io
from collections.abc import Generator

import pytest
from botocore.exceptions import (
    ConnectTimeoutError,
    ConnectionClosedError,
    EndpointConnectionError,
    ReadTimeoutError,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from services.ms4_evidencias.config import Settings
from services.ms4_evidencias.models import Base
from services.ms4_evidencias.models.evidencia import (
    ContextoEvidencia,
    EstadoEvidencia,
)
from services.ms4_evidencias.schemas.evidencia import DatosRecepcion
from services.ms4_evidencias.services.almacenamiento import crear_cliente_s3
from services.ms4_evidencias.services.evidencias import recibir_evidencia

TAMANO_PRUEBA = 256 * 1024

_ERRORES_MINIO_APAGADO = (
    EndpointConnectionError,
    ConnectTimeoutError,
    ReadTimeoutError,
    ConnectionClosedError,
    ConnectionRefusedError,
    TimeoutError,
)


@pytest.fixture
def cliente_minio():
    cfg = Settings()
    cliente = crear_cliente_s3(cfg)
    try:
        cliente.list_objects_v2(Bucket=cfg.S3_BUCKET, MaxKeys=1)
    except _ERRORES_MINIO_APAGADO:
        pytest.skip("MinIO no está disponible (docker compose up -d minio minio_init)")
    return cfg, cliente


@pytest.fixture
def sesion() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)
    sesion = fabrica()
    try:
        yield sesion
    finally:
        sesion.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_recepcion_subida_y_sha256_con_minio_real(cliente_minio, sesion) -> None:
    cfg, cliente = cliente_minio
    datos = DatosRecepcion(orden_id=1, contexto=ContextoEvidencia.DIAGNOSTICO)
    contenido = (bytes(range(256)) * (TAMANO_PRUEBA // 256))[:TAMANO_PRUEBA]

    evidencia = recibir_evidencia(
        sesion,
        cliente,
        cfg.S3_BUCKET,
        datos,
        io.BytesIO(contenido),
        "foto.jpg",
        "image/jpeg",
        7,
        "req-integracion-minio",
    )

    try:
        cuerpo = cliente.get_object(
            Bucket=cfg.S3_BUCKET, Key=evidencia.clave_objeto
        )["Body"].read()
        assert cuerpo == contenido
        assert hashlib.sha256(cuerpo).hexdigest() == evidencia.sha256
        assert evidencia.estado == EstadoEvidencia.CONFIRMADA
        assert evidencia.clave_objeto.startswith("ordenes/1/")
        assert evidencia.clave_objeto.endswith(".jpg")
    finally:
        try:
            cliente.delete_object(Bucket=cfg.S3_BUCKET, Key=evidencia.clave_objeto)
        except Exception:  # noqa: BLE001  (limpieza best-effort)
            pass
