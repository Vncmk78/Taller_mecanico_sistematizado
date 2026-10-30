"""Logs útiles de MS4 sin contenido sensible (Semana 6, checklist 5.5).

Se verifica que:

- cada subida deja un evento `evidencia_subida` con request_id, orden,
  tipo, tamaño y usuario, y cada solicitud una línea `solicitud` con estado
  y duración;
- cada rechazo deja `subida_rechazada` con un `motivo` corto, y las fallas de
  dependencias (MS2, MS3, S3, base) dejan su evento con el tipo de error;
- NUNCA aparecen en los logs: el JWT, la URL prefirmada, la clave del objeto,
  el nombre original del archivo ni su contenido;
- `registrar` aplica una lista blanca de campos y neutraliza saltos de línea.
"""
from __future__ import annotations

import logging
from collections.abc import Generator
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.ms4_evidencias.dependencies import obtener_s3
from services.ms4_evidencias.integracion_ms2 import (
    ServicioOrdenesNoDisponible,
    obtener_verificador_ordenes,
)
from services.ms4_evidencias.integracion_ms3 import obtener_verificador_presupuestos
from services.ms4_evidencias.main import app
from services.ms4_evidencias.routers import evidencias as router_evidencias
from services.ms4_evidencias.services import registro
from services.ms4_evidencias.services.registro import configurar_logs, formatear
from shared.auth import NombreRol

from archivos_muestra import jpeg_con, png
from test_ms4_api_evidencias import (  # noqa: F401  (fixtures reutilizados)
    _subir,
    _token,
    api,
    s3,
    s3_publico,
    sesion,
)
from test_ms4_asociacion_ordenes import OrdenConEstado, PresupuestosFalsos
from test_ms4_errores_carga import FakeS3SinBorrado

CONTENIDO_SECRETO = b"contenido-que-jamas-debe-loguearse"
NOMBRE_PERSONAL = "patente-AB1234-juan-perez.jpg"


class _Captura(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.registros: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.registros.append(record)

    @property
    def lineas(self) -> list[str]:
        return [r.getMessage() for r in self.registros]

    def eventos(self, nombre: str) -> list[str]:
        return [l for l in self.lineas if l.startswith(f"evento={nombre} ")]

    def texto(self) -> str:
        return "\n".join(self.lineas)


@pytest.fixture
def logs() -> Generator[_Captura, None, None]:
    captura = _Captura()
    registro.logger.addHandler(captura)
    nivel_anterior = registro.logger.level
    deshabilitado_antes = registro.logger.disabled
    registro.logger.setLevel(logging.DEBUG)
    # Las pruebas de migraciones cargan alembic.ini con fileConfig, que
    # deshabilita los loggers ya creados; aquí se reactiva solo durante la prueba.
    registro.logger.disabled = False
    try:
        yield captura
    finally:
        registro.logger.removeHandler(captura)
        registro.logger.setLevel(nivel_anterior)
        registro.logger.disabled = deshabilitado_antes


def _mecanico() -> str:
    return _token(7, NombreRol.MECANICO)


def _campos(linea: str) -> dict[str, str]:
    return dict(parte.split("=", 1) for parte in linea.split(" "))


def _sin_datos_sensibles(captura: _Captura, *extra: str) -> None:
    texto = captura.texto()
    for prohibido in (
        _mecanico(),
        "Bearer",
        "ordenes/",
        "X-Amz-Signature",
        "http://",
        NOMBRE_PERSONAL,
        CONTENIDO_SECRETO.decode(),
        *extra,
    ):
        assert prohibido not in texto, prohibido


# --------------------------------------------------------------------------- #
# 1) Subida exitosa y consultas                                               #
# --------------------------------------------------------------------------- #

def test_la_subida_deja_un_evento_util_y_sin_datos_sensibles(
    api: TestClient, logs: _Captura
) -> None:
    respuesta = api.post(
        "/evidencias",
        headers={"Authorization": f"Bearer {_mecanico()}", "X-Request-ID": "req-log-001"},
        data={"orden_id": "31", "contexto": "diagnostico"},
        files={"archivo": (NOMBRE_PERSONAL, jpeg_con(CONTENIDO_SECRETO), "image/jpeg")},
    )
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()

    [subida] = logs.eventos("evidencia_subida")
    campos = _campos(subida)
    assert campos["request_id"] == "req-log-001"
    assert campos["evidencia_id"] == cuerpo["evidencia_id"]
    assert campos["orden_id"] == "31"
    assert campos["tipo_archivo"] == "foto"
    assert campos["content_type"] == "image/jpeg"
    assert campos["tamano_bytes"] == str(cuerpo["tamano_bytes"])
    assert campos["usuario_id"] == "7"

    [solicitud] = logs.eventos("solicitud")
    campos = _campos(solicitud)
    assert campos["metodo"] == "POST"
    assert campos["ruta"] == "/evidencias"
    assert campos["estado_http"] == "201"
    assert campos["usuario_id"] == "7"
    assert int(campos["duracion_ms"]) >= 0
    _sin_datos_sensibles(logs)


def test_la_descarga_se_registra_sin_la_url_firmada(
    api: TestClient, logs: _Captura
) -> None:
    subida = _subir(api, _mecanico(), nombre=NOMBRE_PERSONAL)
    evidencia_id = subida.json()["evidencia_id"]

    descarga = api.get(
        f"/evidencias/{evidencia_id}/descarga",
        headers={"Authorization": f"Bearer {_mecanico()}"},
    )
    assert descarga.status_code == 200
    url = descarga.json()["url"]

    [evento] = logs.eventos("descarga_autorizada")
    assert _campos(evento)["evidencia_id"] == evidencia_id
    _sin_datos_sensibles(logs, url, urlsplit(url).query)


def test_la_query_string_no_se_registra(api: TestClient, logs: _Captura) -> None:
    api.get(
        "/evidencias",
        params={"orden_id": 1, "token": "secreto-en-query"},
        headers={"Authorization": f"Bearer {_mecanico()}"},
    )

    [solicitud] = logs.eventos("solicitud")
    assert _campos(solicitud)["ruta"] == "/evidencias"
    assert "secreto-en-query" not in logs.texto()


# --------------------------------------------------------------------------- #
# 2) Rechazos con motivo                                                      #
# --------------------------------------------------------------------------- #

def _motivo(captura: _Captura) -> str:
    [rechazo] = captura.eventos("subida_rechazada")
    return _campos(rechazo)["motivo"]


@pytest.mark.parametrize(
    ("cambios", "estado", "motivo"),
    [
        ({"archivo": b"<html></html>", "content_type": "text/html"}, 415, "tipo_no_permitido"),
        ({"archivo": png(), "content_type": "image/jpeg"}, 415, "contenido_no_coincide"),
        ({"archivo": jpeg_con(b"x")[:-2]}, 422, "archivo_danado"),
        ({"archivo": b""}, 422, "archivo_invalido"),
        ({"contexto": "presupuesto"}, 422, "formulario_invalido"),
    ],
)
def test_cada_rechazo_de_archivo_registra_su_motivo(
    api: TestClient, logs: _Captura, cambios: dict, estado: int, motivo: str
) -> None:
    respuesta = _subir(api, _mecanico(), nombre=NOMBRE_PERSONAL, **cambios)

    assert respuesta.status_code == estado
    assert _motivo(logs) == motivo
    [rechazo] = logs.eventos("subida_rechazada")
    assert logs.registros[logs.lineas.index(rechazo)].levelno == logging.WARNING
    _sin_datos_sensibles(logs)


def test_el_archivo_demasiado_grande_registra_su_motivo(
    api: TestClient, logs: _Captura
) -> None:
    from services.ms4_evidencias.routers.evidencias import obtener_politica_archivos
    from test_ms4_limites_archivos import _politica

    app.dependency_overrides[obtener_politica_archivos] = lambda: _politica(max_bytes_foto=100)

    respuesta = _subir(api, _mecanico(), archivo=jpeg_con(b"x" * 200))

    assert respuesta.status_code == 413
    assert _motivo(logs) == "demasiado_grande"


def test_rol_sin_permiso_y_orden_cerrada_registran_su_motivo(
    api: TestClient, logs: _Captura
) -> None:
    assert _subir(api, _token(9, NombreRol.CLIENTE)).status_code == 403
    assert _motivo(logs) == "rol_sin_permiso"

    logs.registros.clear()
    app.dependency_overrides[obtener_verificador_ordenes] = lambda: OrdenConEstado(7)
    assert _subir(api, _mecanico()).status_code == 409
    assert _motivo(logs) == "orden_cerrada"


def test_presupuesto_de_otra_orden_registra_su_motivo(
    api: TestClient, logs: _Captura
) -> None:
    app.dependency_overrides[obtener_verificador_presupuestos] = lambda: PresupuestosFalsos(
        {42: 99}
    )

    respuesta = _subir(api, _mecanico(), contexto="presupuesto", presupuesto_id=42)

    assert respuesta.status_code == 422
    assert _motivo(logs) == "presupuesto_de_otra_orden"


# --------------------------------------------------------------------------- #
# 3) Fallas de dependencias                                                   #
# --------------------------------------------------------------------------- #

class _MS2Caido:
    def verificar_acceso(self, orden_id: int, token: str):
        try:
            raise ConnectionError("http://ms2-interno:8002/ordenes/1 rechazó la conexión")
        except ConnectionError as exc:
            raise ServicioOrdenesNoDisponible(str(exc)) from exc


def test_ms2_caido_registra_el_servicio_sin_su_url(api: TestClient, logs: _Captura) -> None:
    app.dependency_overrides[obtener_verificador_ordenes] = lambda: _MS2Caido()

    assert _subir(api, _mecanico()).status_code == 503

    [evento] = logs.eventos("dependencia_no_disponible")
    campos = _campos(evento)
    assert campos["servicio"] == "ms2"
    assert campos["error"] == "ConnectionError"
    assert logs.registros[logs.lineas.index(evento)].levelno == logging.ERROR
    _sin_datos_sensibles(logs, "ms2-interno")


def test_falla_de_la_base_marca_el_objeto_pendiente_de_limpieza(
    api: TestClient, sesion: Session, logs: _Captura, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.dependency_overrides[obtener_s3] = lambda: FakeS3SinBorrado()

    def commit_que_falla(*args, **kwargs) -> None:
        raise RuntimeError("password=supersecreta en la cadena de conexión")

    monkeypatch.setattr(sesion, "commit", commit_que_falla)

    assert _subir(api, _mecanico()).status_code == 503

    [evento] = logs.eventos("subida_fallida")
    campos = _campos(evento)
    assert campos["motivo"] == "base_no_disponible"
    assert campos["pendiente_limpieza"] == "True"
    assert campos["error"] == "RuntimeError"
    assert len(campos["evidencia_id"]) == 36
    _sin_datos_sensibles(logs, "supersecreta")


def test_falla_del_almacenamiento_registra_s3(api: TestClient, logs: _Captura) -> None:
    from test_ms4_api_evidencias import FakeS3ConError

    roto = FakeS3ConError()
    roto.fallar_subida = True
    app.dependency_overrides[obtener_s3] = lambda: roto

    assert _subir(api, _mecanico()).status_code == 503

    [evento] = logs.eventos("subida_fallida")
    assert _campos(evento)["servicio"] == "s3"
    assert _campos(evento)["error"] == "ClientError"


def test_error_no_controlado_se_registra_sin_su_mensaje(
    api: TestClient, logs: _Captura, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explota(*args, **kwargs):
        raise KeyError("dato-interno-secreto")

    monkeypatch.setattr(router_evidencias, "listar_por_orden", explota)
    cliente = TestClient(app, raise_server_exceptions=False)

    respuesta = cliente.get(
        "/evidencias",
        params={"orden_id": 1},
        headers={"Authorization": f"Bearer {_mecanico()}"},
    )

    assert respuesta.status_code == 500
    [evento] = logs.eventos("error_no_controlado")
    assert _campos(evento)["error"] == "KeyError"
    [solicitud] = logs.eventos("solicitud")
    assert _campos(solicitud)["estado_http"] == "500"
    # El mensaje solo aparece en el traceback de nivel DEBUG, nunca en INFO+.
    visibles = [r.getMessage() for r in logs.registros if r.levelno >= logging.INFO]
    assert not any("dato-interno-secreto" in linea for linea in visibles)


# --------------------------------------------------------------------------- #
# 4) Formato, lista blanca y configuración                                    #
# --------------------------------------------------------------------------- #

def test_la_lista_blanca_descarta_campos_no_permitidos_sin_su_valor() -> None:
    linea = formatear("prueba", {"orden_id": 3, "token": "eyJ-secreto", "url": "http://x"})

    assert linea == "evento=prueba orden_id=3 campos_descartados=token,url"
    assert "eyJ-secreto" not in linea


def test_los_saltos_de_linea_no_permiten_inyectar_eventos() -> None:
    linea = formatear("prueba", {"motivo": "x\nevento=falso usuario_id=1"})

    assert "\n" not in linea
    assert linea.count("evento=") == 2  # el inyectado queda dentro del valor
    assert linea.startswith("evento=prueba motivo=x_evento=falso_usuario_id=1")


def test_los_valores_se_truncan_a_80_caracteres() -> None:
    linea = formatear("prueba", {"motivo": "m" * 500})

    assert linea == "evento=prueba motivo=" + "m" * 80


def test_los_valores_nulos_se_omiten() -> None:
    assert formatear("prueba", {"orden_id": None, "motivo": "ok"}) == "evento=prueba motivo=ok"


def test_un_request_id_invalido_no_se_registra(api: TestClient, logs: _Captura) -> None:
    api.get("/health", headers={"X-Request-ID": "malo con espacios"})

    [solicitud] = logs.eventos("solicitud")
    assert "request_id" not in _campos(solicitud)


def test_los_healthchecks_van_en_debug(api: TestClient, logs: _Captura) -> None:
    api.get("/health", headers={"X-Request-ID": "req-health"})

    [solicitud] = logs.eventos("solicitud")
    assert logs.registros[logs.lineas.index(solicitud)].levelno == logging.DEBUG
    assert _campos(solicitud)["request_id"] == "req-health"


def test_configurar_logs_no_duplica_el_handler() -> None:
    configurar_logs("INFO")
    configurar_logs("WARNING")

    propios = [h for h in registro.logger.handlers if getattr(h, "_ms4", False)]
    assert len(propios) == 1
    assert registro.logger.level == logging.WARNING
    assert registro.logger.propagate is False
    configurar_logs("INFO")


def test_fuera_de_una_solicitud_no_hay_request_id() -> None:
    assert registro.request_id_actual() is None
    assert formatear("prueba", {}) == "evento=prueba"
