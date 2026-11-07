"""Integración real MS4 ↔ MinIO del flujo de recepción.

Usa `recibir_evidencia` con un cliente S3 real sobre un bucket exclusivo y
desechable de la prueba (nunca el bucket configurado de MS4) y una base SQLite
en memoria: sube la evidencia a MinIO, la descarga y compara el SHA-256
guardado en la fila. Sin `MS4_TEST_S3_ENDPOINT` se omite indicando cómo
configurarlo (ver `tests/almacenamiento_s3_desechable.py`).
"""
from __future__ import annotations

import hashlib
import io
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from services.ms4_evidencias.models import Base
from services.ms4_evidencias.models.evidencia import (
    ContextoEvidencia,
    EstadoEvidencia,
)
from services.ms4_evidencias.schemas.evidencia import DatosRecepcion
from services.ms4_evidencias.services.evidencias import recibir_evidencia

from archivos_muestra import jpeg_con

TAMANO_PRUEBA = 256 * 1024

@pytest.fixture
def cliente_minio(s3_prueba, almacenamiento):
    """(settings, cliente) sobre un bucket exclusivo; se elimina al terminar."""

    bucket = almacenamiento.crear_bucket()
    return s3_prueba.settings(bucket), s3_prueba.cliente()


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
    contenido = jpeg_con((bytes(range(256)) * (TAMANO_PRUEBA // 256))[:TAMANO_PRUEBA])

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

    cuerpo = cliente.get_object(
        Bucket=cfg.S3_BUCKET, Key=evidencia.clave_objeto
    )["Body"].read()
    assert cuerpo == contenido
    assert hashlib.sha256(cuerpo).hexdigest() == evidencia.sha256
    assert evidencia.estado == EstadoEvidencia.CONFIRMADA
    assert evidencia.clave_objeto.startswith("ordenes/1/")
    assert evidencia.clave_objeto.endswith(".jpg")
