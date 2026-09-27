"""Pruebas del modelo Evidencia (MS4) en SQLite en memoria.

Verifican las reglas de negocio del modelo de metadatos: los CHECK de la tabla,
los valores por defecto (incluido `visible_cliente` según contexto) y la clave
de objeto única. No tocan MinIO ni la base PostgreSQL.
"""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from services.ms4_evidencias.models import Base
from services.ms4_evidencias.models.evidencia import (
    ContextoEvidencia,
    EstadoEvidencia,
    Evidencia,
    TipoArchivo,
)


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


def construir(**cambios) -> Evidencia:
    """Evidencia mínima válida (contexto diagnostico, sin sha256 ni presupuesto)."""
    datos = {
        "orden_id": 1,
        "autor_usuario_id": 7,
        "contexto": ContextoEvidencia.DIAGNOSTICO,
        "tipo_archivo": TipoArchivo.FOTO,
        "clave_objeto": f"ordenes/1/{uuid.uuid4().hex}.bin",
        "nombre_original": "foto.jpg",
        "content_type": "image/jpeg",
        "tamano_bytes": 2048,
    }
    datos.update(cambios)
    return Evidencia(**datos)


def test_insertar_evidencia_valida(sesion: Session) -> None:
    evidencia = construir()
    sesion.add(evidencia)
    sesion.commit()

    assert isinstance(evidencia.evidencia_id, uuid.UUID)
    assert evidencia.creada_en is not None
    assert evidencia.estado == EstadoEvidencia.PENDIENTE
    assert evidencia.visible_cliente is False
    assert evidencia.presupuesto_id is None
    assert evidencia.sha256 is None


@pytest.mark.parametrize(
    ("contexto", "presupuesto_id", "esperado"),
    [
        (ContextoEvidencia.DIAGNOSTICO, None, False),
        (ContextoEvidencia.REPARACION, None, False),
        (ContextoEvidencia.RESULTADO_FINAL, None, True),
        (ContextoEvidencia.PRESUPUESTO, 42, True),
    ],
)
def test_visible_cliente_por_defecto_segun_contexto(
    sesion: Session, contexto: ContextoEvidencia, presupuesto_id: int | None, esperado: bool
) -> None:
    evidencia = construir(contexto=contexto, presupuesto_id=presupuesto_id)
    sesion.add(evidencia)
    sesion.commit()
    assert evidencia.visible_cliente is esperado


@pytest.mark.parametrize(
    ("descripcion", "cambios"),
    [
        ("contexto fuera de los 4 valores del MER", {"contexto": "otro_contexto"}),
        ("tipo_archivo que no es foto ni video", {"tipo_archivo": "documento"}),
        ("tamano en cero", {"tamano_bytes": 0}),
        ("estado fuera del flujo C", {"estado": "borrada"}),
        ("sha256 de largo inválido", {"sha256": "abc"}),
    ],
)
def test_constraints_rechazan_datos_invalidos(
    sesion: Session, descripcion: str, cambios: dict
) -> None:
    sesion.add(construir(**cambios))
    with pytest.raises(IntegrityError):
        sesion.commit()


def test_presupuesto_sin_presupuesto_id(sesion: Session) -> None:
    sesion.add(
        construir(
            contexto=ContextoEvidencia.PRESUPUESTO,
            presupuesto_id=None,
        )
    )
    with pytest.raises(IntegrityError):
        sesion.commit()


def test_presupuesto_con_presupuesto_id_cuando_no_aplica(sesion: Session) -> None:
    sesion.add(construir(contexto=ContextoEvidencia.REPARACION, presupuesto_id=42))
    with pytest.raises(IntegrityError):
        sesion.commit()


def test_presupuesto_oculto_al_cliente(sesion: Session) -> None:
    sesion.add(
        construir(
            contexto=ContextoEvidencia.PRESUPUESTO,
            presupuesto_id=42,
            visible_cliente=False,
        )
    )
    with pytest.raises(IntegrityError):
        sesion.commit()


def test_confirmada_sin_sha256(sesion: Session) -> None:
    sesion.add(construir(estado=EstadoEvidencia.CONFIRMADA, confirmada_en=datetime.now(timezone.utc)))
    with pytest.raises(IntegrityError):
        sesion.commit()


def test_eliminada_sin_responsable(sesion: Session) -> None:
    sesion.add(construir(eliminada_en=datetime.now(timezone.utc)))
    with pytest.raises(IntegrityError):
        sesion.commit()


def test_clave_objeto_duplicada(sesion: Session) -> None:
    clave = "ordenes/1/duplicada.bin"
    sesion.add(construir(clave_objeto=clave))
    sesion.add(construir(clave_objeto=clave))
    with pytest.raises(IntegrityError):
        sesion.commit()


def test_confirmada_completa_y_eliminada_completa(sesion: Session) -> None:
    """La fila completa (confirmada + eliminada con responsable) es válida."""
    evidencia = construir(
        estado=EstadoEvidencia.CONFIRMADA,
        confirmada_en=datetime.now(timezone.utc),
        sha256="a" * 64,
        eliminada_en=datetime.now(timezone.utc),
        eliminada_por_usuario_id=2,
    )
    sesion.add(evidencia)
    sesion.commit()
    assert evidencia.sha256 == "a" * 64
    assert evidencia.eliminada_por_usuario_id == 2
