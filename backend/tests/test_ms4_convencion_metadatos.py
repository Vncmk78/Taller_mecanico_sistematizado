"""Pruebas de la convención de claves de objeto y los metadatos de MS4.

Sin MinIO ni red: reutilizan el FakeS3 de `test_ms4_recepcion.py` (extendido
para registrar `Metadata`) y una base SQLite en memoria. Se verifica la
convención `ordenes/{orden}/[0-9a-f]{32}.{ext}` (el UUID de la clave ==
`evidencia_id`), que dos recepciones de la misma orden no comparten clave, que
el objeto lleva `x-amz-meta-*` con solo evidencia-id/orden-id/sha256/autor-id
(sin nombre original ni datos personales), la normalización del X-Request-ID y
la validación de claves externas con `es_clave_valida` (checklist 1.4, 2.5 y
3.5).
"""
from __future__ import annotations

import io
import uuid

import pytest

from services.ms4_evidencias.models.evidencia import ContextoEvidencia
from services.ms4_evidencias.schemas.evidencia import DatosRecepcion
from services.ms4_evidencias.services.almacenamiento import metadatos_objeto
from services.ms4_evidencias.services.contexto import (
    CABECERA_REQUEST_ID,
    normalizar_request_id,
)
from services.ms4_evidencias.services.evidencias import (
    PATRON_CLAVE_OBJETO,
    es_clave_valida,
    generar_clave_objeto,
    recibir_evidencia,
)
from test_ms4_recepcion import BUCKET, FakeS3, sesion

_UUID_EJEMPLO = "9f2c1d7a4b6e4a1c8f3d0b5e6a7c9d2e"


@pytest.fixture
def s3() -> FakeS3:
    return FakeS3()


def _recibir(
    sesion,
    s3: FakeS3,
    *,
    archivo: bytes = b"datos-de-foto",
    content_type: str = "image/jpeg",
    autor: int = 7,
    request_id: str | None = "req-1",
    datos: DatosRecepcion | None = None,
):
    if datos is None:
        datos = DatosRecepcion(orden_id=1, contexto=ContextoEvidencia.DIAGNOSTICO)
    return recibir_evidencia(
        sesion,
        s3,
        BUCKET,
        datos,
        io.BytesIO(archivo),
        "foto.jpg",
        content_type,
        autor,
        request_id,
    )


# --------------------------------------------------------------------------- #
# 1) Convención de claves (checklist 2.5 y 3.5)                                #
# --------------------------------------------------------------------------- #

def test_la_clave_cumple_el_patron_y_su_uuid_es_el_evidencia_id(
    sesion, s3: FakeS3
) -> None:
    evidencia = _recibir(sesion, s3)

    assert PATRON_CLAVE_OBJETO.fullmatch(evidencia.clave_objeto)
    uuid_en_clave = evidencia.clave_objeto.split("/")[2].split(".")[0]
    assert uuid_en_clave == evidencia.evidencia_id.hex
    assert evidencia.clave_objeto in s3.objetos


def test_dos_recepciones_de_la_misma_orden_no_comparten_clave(
    sesion, s3: FakeS3
) -> None:
    base = DatosRecepcion(orden_id=3, contexto=ContextoEvidencia.DIAGNOSTICO)
    a = _recibir(sesion, s3, datos=base)
    b = _recibir(
        sesion, s3, datos=DatosRecepcion(orden_id=3, contexto=ContextoEvidencia.REPARACION)
    )

    assert a.clave_objeto != b.clave_objeto
    assert a.clave_objeto.startswith("ordenes/3/")
    assert b.clave_objeto.startswith("ordenes/3/")


def test_generar_clave_objeto_rechaza_orden_no_positiva() -> None:
    with pytest.raises(ValueError):
        generar_clave_objeto(0, "image/jpeg")
    with pytest.raises(ValueError):
        generar_clave_objeto(-5, "image/jpeg")


def test_generar_clave_objeto_usa_el_evidencia_id_explicito() -> None:
    eid = uuid.uuid4()
    clave = generar_clave_objeto(7, "video/mp4", evidencia_id=eid)

    assert eid.hex in clave
    assert clave.endswith(".mp4")
    assert es_clave_valida(clave)


# --------------------------------------------------------------------------- #
# 2) Metadatos del objeto (x-amz-meta-*): solo datos de soporte                #
# --------------------------------------------------------------------------- #

def test_el_objeto_lleva_metadatos_y_jamas_el_nombre_original(
    sesion, s3: FakeS3
) -> None:
    evidencia = _recibir(sesion, s3, archivo=b"contenido-x", autor=9)

    guardado = s3.objetos[evidencia.clave_objeto]
    meta = guardado["metadata"]

    assert meta["evidencia-id"] == evidencia.evidencia_id.hex
    assert meta["orden-id"] == str(evidencia.orden_id)
    assert meta["sha256"] == evidencia.sha256
    assert meta["autor-id"] == "9"
    # Exactamente esos cuatro: nunca el nombre original ni datos personales.
    assert set(meta) == {"evidencia-id", "orden-id", "sha256", "autor-id"}
    assert all(
        caracter.isascii() for valor in meta.values() for caracter in valor
    )


def test_metadatos_objeto_es_puro_y_solo_ascii() -> None:
    eid = uuid.UUID("9f2c1d7a-4b6e-4a1c-8f3d-0b5e6a7c9d2e")
    meta = metadatos_objeto(eid, 42, "ab" * 32, 314)

    assert meta == {
        "evidencia-id": eid.hex,
        "orden-id": "42",
        "sha256": "ab" * 32,
        "autor-id": "314",
    }
    assert all(valor == valor.encode("ascii").decode("ascii") for valor in meta.values())


# --------------------------------------------------------------------------- #
# 3) Normalización del X-Request-ID                                           #
# --------------------------------------------------------------------------- #

def test_cabecera_request_id_es_la_de_la_gateway() -> None:
    assert CABECERA_REQUEST_ID == "X-Request-ID"


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("req-1", "req-1"),
        ("a._-b09", "a._-b09"),
        ("0" * 64, "0" * 64),
        (None, None),
        ("", None),
        ("con espacio", None),
        ("req/con/barra", None),
        ("req\u00e9", None),
        ("x" * 65, None),
    ],
)
def test_normalizar_request_id(valor: str | None, esperado: str | None) -> None:
    assert normalizar_request_id(valor) == esperado


def test_recibir_guarda_request_id_normalizado(sesion, s3: FakeS3) -> None:
    valido = _recibir(sesion, s3, request_id="cabeza-7.1")
    assert valido.request_id == "cabeza-7.1"

    invalido = _recibir(sesion, s3, request_id="request/con/datos")
    assert invalido.request_id is None

    largo = _recibir(sesion, s3, request_id="a" * 100)
    assert largo.request_id is None


# --------------------------------------------------------------------------- #
# 4) Validación de claves externas (para búsqueda/limpieza, Semana 6)         #
# --------------------------------------------------------------------------- #

def _clave_con_uuid(prefijo: str = "ordenes/1", ext: str = "jpg") -> str:
    return f"{prefijo}/{_UUID_EJEMPLO}.{ext}"


def test_es_clave_valida_acepta_la_convencion() -> None:
    assert es_clave_valida(_clave_con_uuid()) is True
    assert es_clave_valida("ordenes/999/" + "a" * 32 + ".mp4") is True
    assert es_clave_valida(generar_clave_objeto(1, "image/png")) is True


def test_es_clave_valida_rechaza_cualquier_desviacion() -> None:
    for invalida in [
        "",
        "ordenes/1/../9f2c1d7a4b6e4a1c8f3d0b5e6a7c9d2e.jpg",
        "ordenes/1/abc.jpg",
        "otra/1/9f2c1d7a4b6e4a1c8f3d0b5e6a7c9d2e.jpg",
        "ordenes/01/9f2c1d7a4b6e4a1c8f3d0b5e6a7c9d2e.jpg",
        "ordenes/1/9f2c1d7a4b6e4A1c8f3d0b5e6a7c9d2e.jpg",
        "ordenes/1/9f2c1d7a4b6e4a1c8f3d0b5e6a7c9d2e." + "x" * 6,
        "ordenes/1/9f2c1d7a4b6e4a1c8f3d0b5e6a7c9d2e.jpg/",
    ]:
        assert es_clave_valida(invalida) is False