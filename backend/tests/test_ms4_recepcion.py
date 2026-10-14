"""Pruebas del flujo de recepción de evidencias (MS4) sin Docker.

Usan SQLite en memoria para la base y un FakeS3 en memoria para el almacenamiento
de objetos: verifican la recepción de una foto válida, los rechazos (formato,
archivo vacío, presupuesto incoherente), la compensación cuando falla la base o
MinIO, los filtros de visibilidad de `listar_por_orden` y la regla RF18.
"""
from __future__ import annotations

import hashlib
import io
import re
import uuid
from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from services.ms4_evidencias.models import Base
from services.ms4_evidencias.models.evidencia import (
    ContextoEvidencia,
    EstadoEvidencia,
    Evidencia,
    TipoArchivo,
)
from services.ms4_evidencias.schemas.evidencia import DatosRecepcion
from services.ms4_evidencias.services.evidencias import (
    EvidenciaInvalidaError,
    listar_por_orden,
    presupuesto_tiene_evidencia,
    recibir_evidencia,
)

BUCKET = "evidencias"


class FakeS3:
    """Mínimo cliente S3 en memoria para no depender de Docker en estos tests."""

    def __init__(self) -> None:
        self.objetos: dict[str, dict] = {}
        self.fallar_subida = False

    def upload_fileobj(self, fileobj, bucket, clave, ExtraArgs=None, Config=None):
        if self.fallar_subida:
            raise RuntimeError("MinIO caído")
        self.objetos[clave] = {
            "data": fileobj.read(),
            "content_type": (ExtraArgs or {}).get("ContentType"),
            "metadata": (ExtraArgs or {}).get("Metadata"),
        }

    def get_object(self, Bucket, Key):
        objeto = self.objetos[Key]
        return {"Body": io.BytesIO(objeto["data"]), "ContentLength": len(objeto["data"])}

    def delete_object(self, Bucket, Key):
        self.objetos.pop(Key, None)


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


@pytest.fixture
def s3() -> FakeS3:
    return FakeS3()


def _contar_filas(sesion: Session) -> int:
    return sesion.scalar(select(func.count()).select_from(Evidencia)) or 0


def _recibir(
    sesion: Session,
    s3: FakeS3,
    *,
    archivo: bytes = b"datos-de-foto",
    nombre: str = "foto.jpg",
    content_type: str = "image/jpeg",
    autor: int = 7,
    request_id: str | None = "req-1",
    datos: DatosRecepcion | None = None,
) -> Evidencia:
    if datos is None:
        datos = DatosRecepcion(orden_id=1, contexto=ContextoEvidencia.DIAGNOSTICO)
    return recibir_evidencia(
        sesion,
        s3,
        BUCKET,
        datos,
        io.BytesIO(archivo),
        nombre,
        content_type,
        autor,
        request_id,
    )


def _nueva(**cambios) -> Evidencia:
    """Evidencia mínima válida para armar escenarios (contexto por defecto)."""
    datos = {
        "orden_id": 10,
        "autor_usuario_id": 7,
        "contexto": ContextoEvidencia.DIAGNOSTICO,
        "tipo_archivo": TipoArchivo.FOTO,
        "clave_objeto": f"ordenes/10/{uuid.uuid4().hex}.bin",
        "nombre_original": "foto.jpg",
        "content_type": "image/jpeg",
        "tamano_bytes": 2048,
    }
    datos.update(cambios)
    return Evidencia(**datos)


# --------------------------------------------------------------------------- #
# 1) Recepción de una foto válida                                             #
# --------------------------------------------------------------------------- #

def test_foto_valida_queda_guardada_y_confirmada(sesion: Session, s3: FakeS3) -> None:
    contenido = b"datos-de-foto-jpeg"
    evidencia = _recibir(sesion, s3, archivo=contenido)

    # Fila confirmada con metadatos de integridad (control 2.4).
    assert evidencia.estado == EstadoEvidencia.CONFIRMADA
    assert evidencia.confirmada_en is not None
    assert evidencia.sha256 == hashlib.sha256(contenido).hexdigest()
    assert evidencia.tamano_bytes == len(contenido)
    assert evidencia.tipo_archivo == TipoArchivo.FOTO
    # Diagnóstico: la evidencia interna del taller no es visible para el cliente.
    assert evidencia.visible_cliente is False

    # Clave por convención (2.5) y objeto efectivamente en el almacenamiento.
    assert re.fullmatch(r"ordenes/1/[0-9a-f]{32}\.jpg", evidencia.clave_objeto)
    assert evidencia.clave_objeto in s3.objetos
    guardado = s3.objetos[evidencia.clave_objeto]
    assert guardado["data"] == contenido
    assert guardado["content_type"] == "image/jpeg"


def test_la_clave_jamas_usa_el_nombre_original(sesion: Session, s3: FakeS3) -> None:
    evidencia = _recibir(sesion, s3, nombre="../../etc/passwd.jpg")

    clave = evidencia.clave_objeto
    assert re.fullmatch(r"ordenes/1/[0-9a-f]{32}\.jpg", clave)
    assert ".." not in clave
    # El nombre original se guarda limpio (solo basename), como metadato (1.4).
    assert evidencia.nombre_original == "passwd.jpg"


# --------------------------------------------------------------------------- #
# 2) Rechazos antes de tocar la base o MinIO                                  #
# --------------------------------------------------------------------------- #

def test_content_type_no_permitido_se_rechaza(sesion: Session, s3: FakeS3) -> None:
    with pytest.raises(EvidenciaInvalidaError):
        _recibir(sesion, s3, content_type="text/plain")
    assert not s3.objetos
    assert _contar_filas(sesion) == 0


def test_archivo_vacio_se_rechaza(sesion: Session, s3: FakeS3) -> None:
    with pytest.raises(EvidenciaInvalidaError):
        _recibir(sesion, s3, archivo=b"")
    assert not s3.objetos
    assert _contar_filas(sesion) == 0


def test_presupuesto_sin_presupuesto_id_se_rechaza_en_el_schema() -> None:
    with pytest.raises(ValidationError):
        DatosRecepcion(orden_id=1, contexto=ContextoEvidencia.PRESUPUESTO)


def test_presupuesto_id_fuera_de_contexto_presupuesto_se_rechaza() -> None:
    with pytest.raises(ValidationError):
        DatosRecepcion(
            orden_id=1,
            contexto=ContextoEvidencia.REPARACION,
            presupuesto_id=42,
        )


def test_presupuesto_oculto_al_cliente_se_rechaza_en_el_schema() -> None:
    with pytest.raises(ValidationError):
        DatosRecepcion(
            orden_id=1,
            contexto=ContextoEvidencia.PRESUPUESTO,
            presupuesto_id=42,
            visible_cliente=False,
        )


def test_presupuesto_aprueba_visible_cliente_true_implicito() -> None:
    datos = DatosRecepcion(
        orden_id=1, contexto=ContextoEvidencia.PRESUPUESTO, presupuesto_id=42
    )
    assert datos.visible_cliente is True


# --------------------------------------------------------------------------- #
# 3) Compensación cuando las dependencias fallan                              #
# --------------------------------------------------------------------------- #

def test_si_la_base_falla_se_borra_el_objeto_recien_subido(
    sesion: Session, s3: FakeS3, monkeypatch
) -> None:
    def _commit_falla(*args, **kwargs) -> None:
        raise RuntimeError("base de datos caída")

    monkeypatch.setattr(sesion, "commit", _commit_falla)

    with pytest.raises(RuntimeError):
        _recibir(sesion, s3)

    # Compensación: no quedan archivos huérfanos ni filas.
    assert not s3.objetos
    assert _contar_filas(sesion) == 0


def test_si_minio_falla_no_queda_ninguna_fila(sesion: Session, s3: FakeS3) -> None:
    s3.fallar_subida = True

    with pytest.raises(RuntimeError):
        _recibir(sesion, s3)

    assert not s3.objetos
    assert _contar_filas(sesion) == 0


# --------------------------------------------------------------------------- #
# 4) Consulta y visibilidad                                                   #
# --------------------------------------------------------------------------- #

def test_listar_por_orden_filtra_segun_la_vista(sesion: Session) -> None:
    t1 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 1, 10, 1, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 1, 10, 2, tzinfo=timezone.utc)
    t4 = datetime(2026, 9, 1, 10, 3, tzinfo=timezone.utc)
    t5 = datetime(2026, 9, 1, 10, 4, tzinfo=timezone.utc)

    pendiente = _nueva(
        estado=EstadoEvidencia.PENDIENTE,
        creada_en=t1,
    )
    confirmada_no_visible = _nueva(
        estado=EstadoEvidencia.CONFIRMADA,
        confirmada_en=t2,
        sha256="a" * 64,
        visible_cliente=False,
        creada_en=t2,
    )
    resultado_visible = _nueva(
        contexto=ContextoEvidencia.RESULTADO_FINAL,
        estado=EstadoEvidencia.CONFIRMADA,
        confirmada_en=t3,
        sha256="b" * 64,
        visible_cliente=True,
        creada_en=t3,
    )
    eliminada = _nueva(
        contexto=ContextoEvidencia.REPARACION,
        estado=EstadoEvidencia.CONFIRMADA,
        confirmada_en=t4,
        sha256="c" * 64,
        visible_cliente=True,
        eliminada_en=t4,
        eliminada_por_usuario_id=2,
        creada_en=t4,
    )
    anulada = _nueva(
        contexto=ContextoEvidencia.REPARACION,
        estado=EstadoEvidencia.ANULADA,
        visible_cliente=True,
        creada_en=t5,
    )
    otras = [pendiente, confirmada_no_visible, resultado_visible, eliminada, anulada]
    sesion.add_all(otras)
    sesion.commit()

    # Vista del cliente: solo confirmadas, visibles y no eliminadas.
    ids_cliente = [e.evidencia_id for e in listar_por_orden(sesion, 10, vista_cliente=True)]
    assert ids_cliente == [resultado_visible.evidencia_id]

    # Vista del mecánico: todas las no eliminadas, en orden de creada_en.
    ids_mecanico = [e.evidencia_id for e in listar_por_orden(sesion, 10, vista_cliente=False)]
    assert ids_mecanico == [
        pendiente.evidencia_id,
        confirmada_no_visible.evidencia_id,
        resultado_visible.evidencia_id,
        anulada.evidencia_id,
    ]


def test_presupuesto_tiene_evidencia(sesion: Session) -> None:
    sesion.add(
        _nueva(
            orden_id=20,
            presupuesto_id=50,
            contexto=ContextoEvidencia.PRESUPUESTO,
            estado=EstadoEvidencia.CONFIRMADA,
            confirmada_en=datetime.now(timezone.utc),
            sha256="d" * 64,
        )
    )
    # Confirmada pero eliminada lógicamente: NO cuenta (regla de RF18).
    sesion.add(
        _nueva(
            orden_id=21,
            presupuesto_id=51,
            contexto=ContextoEvidencia.PRESUPUESTO,
            estado=EstadoEvidencia.CONFIRMADA,
            confirmada_en=datetime.now(timezone.utc),
            sha256="e" * 64,
            eliminada_en=datetime.now(timezone.utc),
            eliminada_por_usuario_id=2,
        )
    )
    sesion.commit()

    assert presupuesto_tiene_evidencia(sesion, 50) is True
    assert presupuesto_tiene_evidencia(sesion, 51) is False
    assert presupuesto_tiene_evidencia(sesion, 52) is False


def test_content_type_manipulado_no_altera_la_clave() -> None:
    from services.ms4_evidencias.services.evidencias import generar_clave_objeto

    clave = generar_clave_objeto(1, "image/../../otra-orden")
    assert re.fullmatch(r"ordenes/1/[0-9a-f]{32}\.bin", clave)


def test_content_type_con_parametros_se_normaliza() -> None:
    from services.ms4_evidencias.services.evidencias import generar_clave_objeto

    assert generar_clave_objeto(1, "Image/JPEG; charset=binary").endswith(".jpg")


@pytest.mark.parametrize("nombre", ["", "..", "C:\\fotos\\", "a" * 400 + ".jpg"])
def test_nombre_original_raro_se_limpia(nombre: str) -> None:
    from services.ms4_evidencias.services.evidencias import nombre_limpio

    limpio = nombre_limpio(nombre)
    assert limpio and "/" not in limpio and "\\" not in limpio
    assert len(limpio) <= 255
