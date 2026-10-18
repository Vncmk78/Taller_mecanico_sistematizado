"""Rechazos de la subida de evidencias, punta a punta por la Gateway (Semana 6).

Pruebas de archivo inválido, demasiado grande y orden inexistente pasando por
la Gateway real hasta la app real de MS4 (in-process, fixture
`ecosistema_evidencias`). En cada caso se comprueba que:

- el cliente recibe el código y el body que corresponde, tal como lo genera
  quien rechaza (la Gateway con su formato común, o MS4 con `{"detail": ...}`);
- la respuesta trae el `X-Request-ID` para rastrearla en los logs;
- no queda ningún objeto en el almacenamiento ni filas en la base.

Matriz:

| Caso | Quién rechaza | Código |
|---|---|---|
| Formato fuera de la lista blanca (SVG, HTML, EXE, PDF, GIF) | MS4 | 415 |
| Contenido distinto al declarado (HTML como JPG, PNG como JPG) | MS4 | 415 |
| Archivo vacío o dañado | MS4 | 422 |
| Body > 12 MiB | Gateway (sin llamar a MS4) | 413 |
| Foto > 10 MiB y ≤ 12 MiB / video sobre su límite | MS4 | 413 |
| Orden inexistente o ajena | MS4 (vía MS2) | 404 |
| `orden_id` inválido (0, negativo, texto) | MS4 (FastAPI) | 422 |
| Orden entregada o cancelada | MS4 | 409 |
| Presupuesto inexistente | MS4 (vía MS3) | 422 |
| MS2 no responde | MS4 | 503 |
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gateway.config import settings as gateway_settings
from gateway.errores import CUERPO_DEMASIADO_GRANDE
from services.ms4_evidencias.config import MIB
from services.ms4_evidencias.integracion_ms2 import obtener_verificador_ordenes
from services.ms4_evidencias.integracion_ms3 import obtener_verificador_presupuestos
from services.ms4_evidencias.main import app as app_ms4
from services.ms4_evidencias.models.evidencia import Evidencia
from services.ms4_evidencias.routers.evidencias import obtener_politica_archivos
from shared.auth import NombreRol

from archivos_muestra import jpeg, mp4, png
from test_gateway_evidencias import (  # noqa: F401  (fixtures reutilizados)
    cliente_http_sin_estado,
    ecosistema_evidencias,
)
from test_ms4_api_evidencias import ORDEN, _token
from test_ms4_asociacion_ordenes import OrdenConEstado, PresupuestosFalsos
from test_ms4_autorizacion_evidencias import FakeVerificador
from test_ms4_limites_archivos import _politica
from test_ms4_recepcion import FakeS3

MSG_TIPO = "Tipo de archivo no permitido. Formatos aceptados: JPG, PNG, WEBP, MP4 y MOV"
MSG_CONTENIDO = "El contenido del archivo no corresponde al formato declarado"
MSG_DANADO = "El archivo está dañado o incompleto"
MSG_VACIO = "El archivo no puede estar vacío"
MSG_FOTO_GRANDE = "La foto supera el tamaño máximo permitido (10 MB)"
MSG_ORDEN = "Orden no encontrada"


def _subir(
    gw: TestClient,
    *,
    archivo: bytes | None = None,
    nombre: str = "foto.jpg",
    content_type: str = "image/jpeg",
    orden_id: str = str(ORDEN),
    contexto: str = "diagnostico",
    presupuesto_id: str | None = None,
    request_id: str = "req-rechazo-1",
):
    datos = {"orden_id": orden_id, "contexto": contexto}
    if presupuesto_id is not None:
        datos["presupuesto_id"] = presupuesto_id
    return gw.post(
        "/api/evidencias",
        headers={
            "Authorization": f"Bearer {_token(7, NombreRol.MECANICO)}",
            "X-Request-ID": request_id,
        },
        data=datos,
        files={"archivo": (nombre, jpeg() if archivo is None else archivo, content_type)},
    )


def _sin_residuos(s3: FakeS3, sesion: Session) -> None:
    assert not s3.objetos
    assert (sesion.scalar(select(func.count()).select_from(Evidencia)) or 0) == 0


def _rechazo_de_ms4(respuesta, codigo: int, detalle: str) -> None:
    assert respuesta.status_code == codigo, respuesta.text
    assert respuesta.json() == {"detail": detalle}
    assert respuesta.headers["x-request-id"] == "req-rechazo-1"


# --------------------------------------------------------------------------- #
# 1) Archivo inválido                                                         #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("nombre", "archivo", "content_type", "codigo", "detalle"),
    [
        ("dibujo.svg", b"<svg onload='alert(1)'/>", "image/svg+xml", 415, MSG_TIPO),
        ("pagina.html", b"<html><script></script></html>", "text/html", 415, MSG_TIPO),
        ("programa.exe", b"MZ\x90\x00" + b"\x00" * 64, "application/x-msdownload", 415, MSG_TIPO),
        ("doc.pdf", b"%PDF-1.7\n", "application/pdf", 415, MSG_TIPO),
        ("anim.gif", b"GIF89a" + b"\x00" * 16, "image/gif", 415, MSG_TIPO),
        ("foto.jpg", b"<html><script></script></html>", "image/jpeg", 415, MSG_CONTENIDO),
        ("foto.jpg", png(), "image/jpeg", 415, MSG_CONTENIDO),
        ("foto.jpg", jpeg()[:-2], "image/jpeg", 422, MSG_DANADO),
        ("video.mp4", mp4(4096)[:2500], "video/mp4", 422, MSG_DANADO),
        ("foto.jpg", b"", "image/jpeg", 422, MSG_VACIO),
    ],
)
def test_archivo_invalido_por_la_gateway(
    ecosistema_evidencias,
    nombre: str,
    archivo: bytes,
    content_type: str,
    codigo: int,
    detalle: str,
) -> None:
    gw, s3, sesion = ecosistema_evidencias

    respuesta = _subir(gw, archivo=archivo, nombre=nombre, content_type=content_type)

    _rechazo_de_ms4(respuesta, codigo, detalle)
    _sin_residuos(s3, sesion)


# --------------------------------------------------------------------------- #
# 2) Archivo demasiado grande                                                 #
# --------------------------------------------------------------------------- #

class _VerificadorQueCuenta:
    def __init__(self) -> None:
        self.llamadas = 0

    def verificar_acceso(self, orden_id: int, token: str):
        self.llamadas += 1
        return None


def test_body_mayor_al_limite_de_la_gateway_responde_413_sin_llamar_a_ms4(
    ecosistema_evidencias,
) -> None:
    gw, s3, sesion = ecosistema_evidencias
    contador = _VerificadorQueCuenta()
    app_ms4.dependency_overrides[obtener_verificador_ordenes] = lambda: contador

    respuesta = _subir(gw, archivo=jpeg(gateway_settings.MAX_BODY_ARCHIVOS_BYTES + 1))

    assert respuesta.status_code == 413
    cuerpo = respuesta.json()
    assert cuerpo["error"]["codigo"] == CUERPO_DEMASIADO_GRANDE
    assert cuerpo["error"]["request_id"] == "req-rechazo-1"
    assert contador.llamadas == 0  # MS4 nunca recibió la petición
    _sin_residuos(s3, sesion)


def test_foto_entre_10_y_12_mib_la_rechaza_ms4_con_413(ecosistema_evidencias) -> None:
    gw, s3, sesion = ecosistema_evidencias

    respuesta = _subir(gw, archivo=jpeg(10 * MIB + 1))

    _rechazo_de_ms4(respuesta, 413, MSG_FOTO_GRANDE)
    _sin_residuos(s3, sesion)


def test_foto_exacta_de_10_mib_pasa_por_la_gateway(ecosistema_evidencias) -> None:
    gw, s3, sesion = ecosistema_evidencias

    respuesta = _subir(gw, archivo=jpeg(10 * MIB))

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["tamano_bytes"] == 10 * MIB
    assert len(s3.objetos) == 1


def test_video_sobre_su_limite_responde_413(ecosistema_evidencias) -> None:
    gw, s3, sesion = ecosistema_evidencias
    app_ms4.dependency_overrides[obtener_politica_archivos] = lambda: _politica(
        max_bytes_video=4096
    )

    respuesta = _subir(gw, archivo=mp4(4097), nombre="v.mp4", content_type="video/mp4")

    assert respuesta.status_code == 413
    assert respuesta.json()["detail"].startswith("El video supera")
    _sin_residuos(s3, sesion)


# --------------------------------------------------------------------------- #
# 3) Orden inexistente, inválida o cerrada                                    #
# --------------------------------------------------------------------------- #

def test_orden_inexistente_responde_404_sin_residuos(ecosistema_evidencias) -> None:
    gw, s3, sesion = ecosistema_evidencias
    app_ms4.dependency_overrides[obtener_verificador_ordenes] = lambda: FakeVerificador(
        visibles={ORDEN}
    )

    respuesta = _subir(gw, orden_id="999999")

    _rechazo_de_ms4(respuesta, 404, MSG_ORDEN)
    _sin_residuos(s3, sesion)


def test_orden_inexistente_con_archivo_invalido_sigue_siendo_404(
    ecosistema_evidencias,
) -> None:
    # La orden se valida antes que el archivo: un archivo inválido no permite
    # distinguir una orden inexistente de una existente (no enumeración).
    gw, s3, sesion = ecosistema_evidencias
    app_ms4.dependency_overrides[obtener_verificador_ordenes] = lambda: FakeVerificador(
        visibles={ORDEN}
    )

    respuesta = _subir(gw, orden_id="999999", archivo=b"<html>", content_type="text/html")

    _rechazo_de_ms4(respuesta, 404, MSG_ORDEN)
    _sin_residuos(s3, sesion)


def test_orden_ajena_responde_igual_que_una_inexistente(ecosistema_evidencias) -> None:
    gw, s3, sesion = ecosistema_evidencias
    app_ms4.dependency_overrides[obtener_verificador_ordenes] = lambda: FakeVerificador(
        visibles=set()
    )

    ajena = _subir(gw, orden_id=str(ORDEN))
    inexistente = _subir(gw, orden_id="999999")

    assert ajena.status_code == inexistente.status_code == 404
    assert ajena.json() == inexistente.json() == {"detail": MSG_ORDEN}
    _sin_residuos(s3, sesion)


@pytest.mark.parametrize("orden_id", ["0", "-5", "abc", ""])
def test_orden_id_invalido_responde_422(ecosistema_evidencias, orden_id: str) -> None:
    gw, s3, sesion = ecosistema_evidencias

    respuesta = _subir(gw, orden_id=orden_id)

    assert respuesta.status_code == 422
    assert isinstance(respuesta.json()["detail"], list)  # validación de FastAPI
    _sin_residuos(s3, sesion)


@pytest.mark.parametrize("estado", [7, 8])
def test_orden_cerrada_responde_409(ecosistema_evidencias, estado: int) -> None:
    gw, s3, sesion = ecosistema_evidencias
    app_ms4.dependency_overrides[obtener_verificador_ordenes] = lambda: OrdenConEstado(estado)

    respuesta = _subir(gw)

    _rechazo_de_ms4(
        respuesta, 409, "La orden está entregada o cancelada y no admite nuevas evidencias"
    )
    _sin_residuos(s3, sesion)


def test_presupuesto_inexistente_responde_422(ecosistema_evidencias) -> None:
    gw, s3, sesion = ecosistema_evidencias
    app_ms4.dependency_overrides[obtener_verificador_presupuestos] = lambda: (
        PresupuestosFalsos({})
    )

    respuesta = _subir(gw, contexto="presupuesto", presupuesto_id="777")

    _rechazo_de_ms4(respuesta, 422, "El presupuesto indicado no existe")
    _sin_residuos(s3, sesion)


def test_ms2_caido_responde_503(ecosistema_evidencias) -> None:
    gw, s3, sesion = ecosistema_evidencias
    verificador = FakeVerificador()
    verificador.caido = True
    app_ms4.dependency_overrides[obtener_verificador_ordenes] = lambda: verificador

    respuesta = _subir(gw)

    _rechazo_de_ms4(respuesta, 503, "El servicio de órdenes no está disponible")
    _sin_residuos(s3, sesion)
