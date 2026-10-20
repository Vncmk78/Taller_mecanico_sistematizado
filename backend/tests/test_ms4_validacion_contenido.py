"""Validación del archivo por su contenido (MS4, Semana 6).

Controles del checklist de seguridad de evidencias:

- 1.2 El tipo se valida por los primeros bytes (firma o *magic bytes*), no por
  el nombre ni por el `Content-Type` que manda el cliente: un HTML renombrado
  a `.jpg` o un PNG declarado como `image/jpeg` responde 415.
- 1.6 Un archivo con la firma correcta pero incompleto (JPEG sin marcador de
  fin, PNG sin IEND, WEBP o MP4/MOV truncados, video sin `moov`) responde 422.

El content_type que se guarda (y con el que se firma la descarga, control 3.4)
es el detectado por el servidor. Ningún rechazo deja objetos ni filas.
"""
from __future__ import annotations

import io
import struct
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.ms4_evidencias.main import app
from services.ms4_evidencias.models.evidencia import ContextoEvidencia, Evidencia
from services.ms4_evidencias.routers.evidencias import obtener_politica_archivos
from services.ms4_evidencias.schemas.evidencia import DatosRecepcion
from services.ms4_evidencias.services.evidencias import (
    ArchivoDanadoError,
    ContenidoNoCoincideError,
    recibir_evidencia,
)
from services.ms4_evidencias.services.validacion_archivos import (
    PoliticaArchivos,
    _contiene,
    detectar_formato,
    validar_contenido,
)
from shared.auth import NombreRol

import archivos_muestra
from archivos_muestra import jpeg, jpeg_con, mov, mp4, png, webp
from test_ms4_api_evidencias import (  # noqa: F401  (fixtures reutilizados)
    _contar_filas,
    _subir,
    _token,
    api,
    s3,
    s3_publico,
    sesion,
)
from test_ms4_recepcion import BUCKET, FakeS3

POLITICA = PoliticaArchivos(
    tipos_permitidos=frozenset(archivos_muestra.POR_CONTENT_TYPE),
    max_bytes_foto=10 * 1024 * 1024,
    max_bytes_video=100 * 1024 * 1024,
)

HTML = b"<!DOCTYPE html><html><script>alert(1)</script></html>"
SVG = b"<?xml version='1.0'?><svg xmlns='http://www.w3.org/2000/svg'></svg>"


def _mecanico() -> str:
    return _token(7, NombreRol.MECANICO)


def _sin_residuos(s3: FakeS3, sesion: Session) -> None:
    assert not s3.objetos
    assert _contar_filas(sesion) == 0


def _heic() -> bytes:
    ftyp = b"ftypheic" + struct.pack(">I", 0) + b"mif1heic"
    return struct.pack(">I", 8 + len(ftyp) - 4) + ftyp + b"\x00" * 64


# --------------------------------------------------------------------------- #
# 1) Detección por firma (unidad)                                             #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("contenido", "esperado"),
    [
        (jpeg(), "image/jpeg"),
        (png(), "image/png"),
        (webp(), "image/webp"),
        (mp4(), "video/mp4"),
        (mov(), "video/quicktime"),
        (struct.pack(">I", 16) + b"moov" + b"\x00" * 8, "video/quicktime"),
    ],
)
def test_la_firma_identifica_cada_formato_permitido(
    contenido: bytes, esperado: str
) -> None:
    assert detectar_formato(contenido[:16]) == esperado


@pytest.mark.parametrize(
    "contenido",
    [
        HTML,
        SVG,
        b"%PDF-1.7\n%\xe2\xe3",
        b"PK\x03\x04" + b"\x00" * 12,
        b"MZ\x90\x00" + b"\x00" * 12,
        b"GIF89a" + b"\x00" * 10,
        b"BM" + b"\x00" * 14,
        b"RIFF\x00\x00\x00\x00WAVEfmt ",
        _heic(),
        b"datos-de-foto",
        b"",
    ],
)
def test_firmas_no_soportadas_no_se_reconocen(contenido: bytes) -> None:
    assert detectar_formato(contenido[:16]) is None


def test_el_patron_partido_entre_dos_bloques_se_encuentra() -> None:
    # El fin del JPEG (FF D9) queda justo en el límite de 1 MiB.
    contenido = b"\x00" * (1024 * 1024 - 1) + b"\xff\xd9"

    assert _contiene(io.BytesIO(contenido), b"\xff\xd9", desde=0)
    assert not _contiene(io.BytesIO(contenido[:-1]), b"\xff\xd9", desde=0)


def test_validar_contenido_devuelve_el_tipo_detectado_y_deja_el_archivo_al_inicio() -> None:
    archivo = io.BytesIO(mov())

    detectado = validar_contenido(archivo, "video/mp4", len(mov()), POLITICA)

    assert detectado == "video/quicktime"
    assert archivo.tell() == 0


# --------------------------------------------------------------------------- #
# 2) API: contenido que no corresponde al formato declarado → 415             #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("nombre", "contenido", "declarado"),
    [
        ("foto.jpg", HTML, "image/jpeg"),  # HTML renombrado (checklist 1.2)
        ("foto.png", SVG, "image/png"),
        ("foto.jpg", b"MZ\x90\x00" + b"\x00" * 64, "image/jpeg"),
        ("foto.jpg", png(), "image/jpeg"),  # formato permitido, pero otro
        ("foto.webp", jpeg(), "image/webp"),
        ("video.mp4", jpeg(), "video/mp4"),
        ("foto.jpg", mp4(), "image/jpeg"),
        ("foto.jpg", _heic(), "image/jpeg"),
    ],
)
def test_contenido_distinto_al_declarado_responde_415_sin_residuos(
    api: TestClient,
    s3: FakeS3,
    sesion: Session,
    nombre: str,
    contenido: bytes,
    declarado: str,
) -> None:
    respuesta = _subir(
        api, _mecanico(), archivo=contenido, nombre=nombre, content_type=declarado
    )

    assert respuesta.status_code == 415
    assert respuesta.json() == {
        "detail": "El contenido del archivo no corresponde al formato declarado"
    }
    _sin_residuos(s3, sesion)


def test_contenido_de_un_formato_fuera_de_la_lista_configurada_responde_415(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    politica = PoliticaArchivos(
        tipos_permitidos=frozenset({"image/jpeg", "video/mp4"}),
        max_bytes_foto=POLITICA.max_bytes_foto,
        max_bytes_video=POLITICA.max_bytes_video,
    )
    app.dependency_overrides[obtener_politica_archivos] = lambda: politica

    # Declara MP4 (permitido) pero el contenido es MOV (no permitido aquí).
    respuesta = _subir(
        api, _mecanico(), archivo=mov(), nombre="v.mp4", content_type="video/mp4"
    )

    assert respuesta.status_code == 415
    _sin_residuos(s3, sesion)


def test_mov_declarado_como_mp4_se_acepta_y_guarda_el_tipo_real(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    respuesta = _subir(
        api, _mecanico(), archivo=mov(), nombre="video.mp4", content_type="video/mp4"
    )

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["content_type"] == "video/quicktime"
    [clave] = s3.objetos
    assert clave.endswith(".mov")
    assert s3.objetos[clave]["content_type"] == "video/quicktime"


def test_la_descarga_se_firma_con_el_tipo_detectado(
    api: TestClient, sesion: Session
) -> None:
    subida = _subir(
        api, _mecanico(), archivo=mp4(), nombre="video.mov", content_type="video/quicktime"
    )
    assert subida.status_code == 201, subida.text
    evidencia_id = subida.json()["evidencia_id"]

    url = api.get(
        f"/evidencias/{evidencia_id}/descarga",
        headers={"Authorization": f"Bearer {_mecanico()}"},
    ).json()["url"]

    assert parse_qs(urlsplit(url).query)["response-content-type"] == ["video/mp4"]
    assert sesion.scalar(select(Evidencia.content_type)) == "video/mp4"


# --------------------------------------------------------------------------- #
# 3) API: archivo dañado o incompleto → 422                                   #
# --------------------------------------------------------------------------- #

def _mp4_truncado() -> bytes:
    return mp4(4096)[:3000]  # la caja mdat declara más bytes de los que hay


def _mp4_sin_moov() -> bytes:
    ftyp = struct.pack(">I", 20) + b"ftypisom" + struct.pack(">I", 0) + b"isom"
    mdat = struct.pack(">I", 108) + b"mdat" + b"\x00" * 100
    return ftyp + mdat


def _png_sin_iend() -> bytes:
    return png()[:-12]


def _webp_truncado() -> bytes:
    return webp(2048)[:1500]


def _caja_invalida() -> bytes:
    # Caja de tamaño 4 (< 8 bytes de cabecera): estructura imposible.
    return mp4()[:24] + struct.pack(">I", 4) + b"moov" + b"\x00" * 32


@pytest.mark.parametrize(
    ("contenido", "declarado"),
    [
        (jpeg(4096)[:-2], "image/jpeg"),
        (_png_sin_iend(), "image/png"),
        (_webp_truncado(), "image/webp"),
        (_mp4_truncado(), "video/mp4"),
        (_mp4_sin_moov(), "video/mp4"),
        (_caja_invalida(), "video/mp4"),
        (mov(4096)[:2000], "video/quicktime"),
        (b"\xff\xd8\xff", "image/jpeg"),
    ],
)
def test_archivo_danado_responde_422_sin_residuos(
    api: TestClient,
    s3: FakeS3,
    sesion: Session,
    contenido: bytes,
    declarado: str,
) -> None:
    respuesta = _subir(api, _mecanico(), archivo=contenido, content_type=declarado)

    assert respuesta.status_code == 422
    assert respuesta.json() == {"detail": "El archivo está dañado o incompleto"}
    _sin_residuos(s3, sesion)


def test_mp4_con_caja_de_64_bits_y_caja_final_abierta_es_valido(
    api: TestClient, s3: FakeS3
) -> None:
    ftyp = struct.pack(">I", 20) + b"ftypisom" + struct.pack(">I", 0) + b"isom"
    moov = struct.pack(">I", 1) + b"moov" + struct.pack(">Q", 16 + 32) + b"\x00" * 32
    mdat_hasta_el_final = struct.pack(">I", 0) + b"mdat" + b"\x00" * 500

    respuesta = _subir(
        api,
        _mecanico(),
        archivo=ftyp + moov + mdat_hasta_el_final,
        nombre="video.mp4",
        content_type="video/mp4",
    )

    assert respuesta.status_code == 201, respuesta.text


def test_jpeg_con_datos_despues_del_fin_es_valido(api: TestClient) -> None:
    # Algunas cámaras agregan datos después del marcador FF D9.
    respuesta = _subir(api, _mecanico(), archivo=jpeg() + b"trailer-de-camara")

    assert respuesta.status_code == 201, respuesta.text


# --------------------------------------------------------------------------- #
# 4) Servicio: recibir_evidencia sin la API                                   #
# --------------------------------------------------------------------------- #

def _recibir(sesion: Session, s3: FakeS3, contenido: bytes, content_type: str):
    return recibir_evidencia(
        sesion,
        s3,
        BUCKET,
        DatosRecepcion(orden_id=1, contexto=ContextoEvidencia.DIAGNOSTICO),
        io.BytesIO(contenido),
        "foto.jpg",
        content_type,
        7,
        "req-1",
        politica=POLITICA,
    )


def test_recibir_rechaza_html_disfrazado_antes_de_subir(
    sesion: Session, s3: FakeS3
) -> None:
    with pytest.raises(ContenidoNoCoincideError):
        _recibir(sesion, s3, HTML, "image/jpeg")
    _sin_residuos(s3, sesion)


def test_recibir_rechaza_jpeg_truncado_antes_de_subir(
    sesion: Session, s3: FakeS3
) -> None:
    with pytest.raises(ArchivoDanadoError):
        _recibir(sesion, s3, jpeg()[:-2], "image/jpeg")
    _sin_residuos(s3, sesion)


def test_recibir_sube_el_archivo_completo_tras_validarlo(
    sesion: Session, s3: FakeS3
) -> None:
    contenido = jpeg_con(b"contenido-real" * 100)

    evidencia = _recibir(sesion, s3, contenido, "image/jpeg")

    assert s3.objetos[evidencia.clave_objeto]["data"] == contenido
    assert evidencia.tamano_bytes == len(contenido)
