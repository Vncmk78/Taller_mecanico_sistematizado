"""Errores, transferencias interrumpidas y limpieza del servicio multimedia (Semana 10).

SCRUM-580 (probar errores y transferencias de MS4) y SCRUM-584 (validar limpieza
y respuesta segura). Complementa `test_ms4_errores_carga.py` (Semana 6) con los
casos de **transferencia**: lo que pasa cuando la subida se corta a mitad de
camino, en cualquiera de los dos tramos:

    navegador/app ──(1)──► Gateway ──► MS4 ──(2)──► MinIO/S3

(1) Cliente → MS4: el multipart llega truncado o el cliente se desconecta.
    MS4 no alcanza a ejecutar el endpoint: no sube nada ni crea filas.
(2) MS4 → MinIO: la transferencia falla. Caso nuevo cubierto en la Semana 10:
    MinIO **sí guardó** el objeto, pero la confirmación se perdió (timeout de
    lectura o conexión cortada). Antes quedaba un archivo huérfano; ahora
    `recibir_evidencia` borra la clave antes de propagar el error.

En todos los casos la respuesta es segura: mensaje genérico, sin bucket, clave,
endpoint interno ni traza, y con `X-Request-ID` para rastrear el fallo.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
from datetime import datetime, timedelta, timezone

import pytest
from botocore.exceptions import EndpointConnectionError, ReadTimeoutError
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.ms4_evidencias.dependencies import obtener_s3
from services.ms4_evidencias.main import app
from services.ms4_evidencias.services.huerfanos import conciliar
from shared.auth import NombreRol

from archivos_muestra import JPEG_VALIDO
from test_ms4_api_evidencias import (  # noqa: F401  (fixtures reutilizados)
    BUCKET,
    _contar_filas,
    _subir,
    _token,
    api,
    s3,
    s3_publico,
    sesion,
)
from test_ms4_recepcion import FakeS3

MSG_ALMACENAMIENTO = "El almacenamiento de evidencias no está disponible"
ENDPOINT_INTERNO = "http://minio-interno:9000"


class FakeS3RespuestaPerdida(FakeS3):
    """MinIO guarda el objeto, pero la confirmación nunca llega a MS4.

    Reproduce un `ReadTimeoutError` de botocore después de una subida
    completa: el caso que dejaba archivos huérfanos antes de la Semana 10.
    """

    def __init__(self, *, borrado_falla: bool = False) -> None:
        super().__init__()
        self.borrado_falla = borrado_falla
        self.borrados: list[str] = []

    def upload_fileobj(self, fileobj, bucket, clave, ExtraArgs=None, Config=None):
        super().upload_fileobj(fileobj, bucket, clave, ExtraArgs=ExtraArgs, Config=Config)
        self.objetos[clave]["modificado"] = datetime.now(timezone.utc) - timedelta(hours=2)
        raise ReadTimeoutError(endpoint_url=f"{ENDPOINT_INTERNO}/{bucket}/{clave}")

    def delete_object(self, Bucket, Key):
        self.borrados.append(Key)
        if self.borrado_falla:
            raise EndpointConnectionError(endpoint_url=ENDPOINT_INTERNO)
        super().delete_object(Bucket, Key)

    def list_objects_v2(self, Bucket, Prefix="", ContinuationToken=None, MaxKeys=None):
        return {
            "Contents": [
                {"Key": clave, "LastModified": datos["modificado"]}
                for clave, datos in self.objetos.items()
                if clave.startswith(Prefix)
            ],
            "IsTruncated": False,
        }


class FakeS3ConexionCaida(FakeS3):
    """MinIO no responde: la conexión falla antes de transferir nada."""

    def upload_fileobj(self, fileobj, bucket, clave, ExtraArgs=None, Config=None):
        raise EndpointConnectionError(endpoint_url=ENDPOINT_INTERNO)


class _CapturaMS4(logging.Handler):
    """El logger de MS4 no propaga a la raíz: se captura con un handler propio."""

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.lineas: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lineas.append(record.getMessage())


@pytest.fixture
def logs_ms4():
    captura = _CapturaMS4()
    logger = logging.getLogger("ms4.evidencias")
    # Otras suites pueden dejar el logger deshabilitado o con otro nivel.
    nivel, deshabilitado = logger.level, logger.disabled
    logger.setLevel(logging.DEBUG)
    logger.disabled = False
    logger.addHandler(captura)
    try:
        yield captura
    finally:
        logger.removeHandler(captura)
        logger.setLevel(nivel)
        logger.disabled = deshabilitado


def _mecanico() -> str:
    return _token(7, NombreRol.MECANICO)


def _respuesta_segura(respuesta) -> None:
    """Ningún dato interno del almacenamiento llega al cliente."""
    for prohibido in (
        "minio",
        "bucket",
        "ordenes/",
        "Traceback",
        "ReadTimeout",
        "EndpointConnection",
        "http://",
    ):
        assert prohibido not in respuesta.text, prohibido


def _usar_s3(fake: FakeS3) -> None:
    app.dependency_overrides[obtener_s3] = lambda: fake


# --------------------------------------------------------------------------- #
# Tramo 2: MS4 -> MinIO                                                       #
# --------------------------------------------------------------------------- #

def test_respuesta_perdida_de_minio_no_deja_archivo_huerfano(
    api: TestClient, sesion: Session
) -> None:
    roto = FakeS3RespuestaPerdida()
    _usar_s3(roto)

    respuesta = api.post(
        "/evidencias",
        headers={"Authorization": f"Bearer {_mecanico()}", "X-Request-ID": "trf-1"},
        data={"orden_id": "1", "contexto": "diagnostico"},
        files={"archivo": ("foto.jpg", JPEG_VALIDO, "image/jpeg")},
    )

    assert respuesta.status_code == 503
    assert respuesta.json() == {"detail": MSG_ALMACENAMIENTO}
    assert respuesta.headers["x-request-id"] == "trf-1"
    _respuesta_segura(respuesta)
    # Se intentó borrar exactamente la clave subida, y ya no existe.
    assert len(roto.borrados) == 1
    assert not roto.objetos
    assert _contar_filas(sesion) == 0


def test_si_el_borrado_tambien_falla_queda_marcado_y_la_conciliacion_lo_encuentra(
    api: TestClient, sesion: Session, logs_ms4: _CapturaMS4
) -> None:
    roto = FakeS3RespuestaPerdida(borrado_falla=True)
    _usar_s3(roto)

    respuesta = _subir(api, _mecanico())

    # El cliente recibe el mismo 503 genérico (no se entera de la compensación).
    assert respuesta.status_code == 503
    assert respuesta.json() == {"detail": MSG_ALMACENAMIENTO}
    _respuesta_segura(respuesta)
    assert _contar_filas(sesion) == 0

    # El log marca la limpieza pendiente sin revelar la clave del objeto.
    [linea] = [l for l in logs_ms4.lineas if "evento=compensacion_fallida" in l]
    assert "pendiente_limpieza=True" in linea
    assert "motivo=subida_interrumpida" in linea
    assert "ordenes/" not in linea and "minio" not in linea

    # La conciliación de huérfanos (Semana 6) detecta y limpia ese objeto.
    [clave] = list(roto.objetos)
    roto.borrado_falla = False
    resultado = conciliar(sesion, roto, BUCKET, eliminar=True)
    assert resultado.huerfanos == [clave]
    assert resultado.eliminados == [clave]
    assert not roto.objetos


def test_minio_inalcanzable_responde_503_sin_residuos(
    api: TestClient, sesion: Session, logs_ms4: _CapturaMS4
) -> None:
    roto = FakeS3ConexionCaida()
    _usar_s3(roto)

    respuesta = _subir(api, _mecanico())

    assert respuesta.status_code == 503
    assert respuesta.json() == {"detail": MSG_ALMACENAMIENTO}
    _respuesta_segura(respuesta)
    assert _contar_filas(sesion) == 0
    # El borrado de compensación fue inocuo (no había objeto) y no se marcó nada.
    assert not any("compensacion_fallida" in l for l in logs_ms4.lineas)
    [fallo] = [l for l in logs_ms4.lineas if "evento=subida_fallida" in l]
    assert "error=EndpointConnectionError" in fallo


def test_la_subida_correcta_no_borra_nada(api: TestClient, s3: FakeS3, sesion: Session) -> None:
    respuesta = _subir(api, _mecanico())

    assert respuesta.status_code == 201
    assert len(s3.objetos) == 1
    assert _contar_filas(sesion) == 1


# --------------------------------------------------------------------------- #
# Tramo 1: cliente -> MS4                                                     #
# --------------------------------------------------------------------------- #

def test_multipart_truncado_se_rechaza_sin_subir_nada(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    frontera = "frontera-sgtm"
    cuerpo = (
        f"--{frontera}\r\n"
        'Content-Disposition: form-data; name="orden_id"\r\n\r\n1\r\n'
        f"--{frontera}\r\n"
        'Content-Disposition: form-data; name="contexto"\r\n\r\ndiagnostico\r\n'
        f"--{frontera}\r\n"
        'Content-Disposition: form-data; name="archivo"; filename="foto.jpg"\r\n'
        "Content-Type: image/jpeg\r\n\r\n"
    ).encode() + JPEG_VALIDO[: len(JPEG_VALIDO) // 2]  # sin la frontera de cierre

    respuesta = api.post(
        "/evidencias",
        headers={
            "Authorization": f"Bearer {_mecanico()}",
            "Content-Type": f"multipart/form-data; boundary={frontera}",
            "X-Request-ID": "trf-truncado",
        },
        content=cuerpo,
    )

    assert 400 <= respuesta.status_code < 500
    assert respuesta.headers["x-request-id"] == "trf-truncado"
    _respuesta_segura(respuesta)
    assert not s3.objetos
    assert _contar_filas(sesion) == 0


def test_desconexion_del_cliente_a_mitad_de_la_subida_no_deja_residuos(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    """ASGI directo: el cliente manda un trozo del multipart y se desconecta."""
    frontera = b"frontera-sgtm"
    primer_trozo = (
        b"--" + frontera + b"\r\n"
        b'Content-Disposition: form-data; name="archivo"; filename="foto.jpg"\r\n'
        b"Content-Type: image/jpeg\r\n\r\n" + JPEG_VALIDO[:64]
    )
    entregados: list[int] = []

    async def recibir():
        if not entregados:
            entregados.append(1)
            return {"type": "http.request", "body": primer_trozo, "more_body": True}
        return {"type": "http.disconnect"}

    enviados: list[dict] = []

    async def enviar(mensaje):
        enviados.append(mensaje)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/evidencias",
        "raw_path": b"/evidencias",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"ms4"),
            (b"authorization", f"Bearer {_mecanico()}".encode()),
            (b"content-type", b"multipart/form-data; boundary=" + frontera),
            (b"x-request-id", b"trf-desconexion"),
        ],
        "client": ("10.0.0.9", 5000),
        "server": ("ms4", 80),
    }

    try:
        asyncio.run(app(scope, recibir, enviar))
    except Exception:  # noqa: BLE001  (Starlette puede relanzar ClientDisconnect)
        pass

    assert not s3.objetos
    assert _contar_filas(sesion) == 0
    cuerpos = b"".join(m.get("body", b"") for m in enviados if m["type"] == "http.response.body")
    assert b"minio" not in cuerpos and b"Traceback" not in cuerpos


# --------------------------------------------------------------------------- #
# A través de la Gateway                                                      #
# --------------------------------------------------------------------------- #

def test_respuesta_perdida_llega_por_la_gateway_como_503_de_ms4(
    api: TestClient, sesion: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El 503 JSON de MS4 pasa tal cual por la Gateway, con el mismo ID."""
    import httpx

    import gateway.cliente_http as cliente_http
    import gateway.rutas as rutas
    from gateway.main import app as app_gateway

    roto = FakeS3RespuestaPerdida()
    _usar_s3(roto)
    monkeypatch.setitem(rutas.RUTAS, "evidencias", "http://ms4")

    def transporte_a_ms4() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app))

    monkeypatch.setattr("gateway.routers.proxy.obtener_cliente", transporte_a_ms4)
    try:
        respuesta = TestClient(app_gateway).post(
            "/api/evidencias",
            headers={"Authorization": f"Bearer {_mecanico()}", "X-Request-ID": "trf-gw"},
            data={"orden_id": "1", "contexto": "diagnostico"},
            files={"archivo": ("foto.jpg", JPEG_VALIDO, "image/jpeg")},
        )
    finally:
        cliente_http.reset_cliente()

    assert respuesta.status_code == 503
    assert respuesta.json() == {"detail": MSG_ALMACENAMIENTO}
    assert respuesta.headers["x-request-id"] == "trf-gw"
    _respuesta_segura(respuesta)
    assert not roto.objetos
    assert _contar_filas(sesion) == 0
