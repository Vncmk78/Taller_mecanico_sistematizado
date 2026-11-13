"""Simulación de fallos reales de un microservicio detrás de la Gateway (Semana 10).

SCRUM-583 (y verificación de SCRUM-579). A diferencia de
`test_gateway_errores_proxy.py`, que simula las excepciones de HTTPX con
`respx`, aquí la Gateway habla por red con **servidores de verdad** levantados
en la propia prueba (127.0.0.1, puertos efímeros):

| Escenario | Cómo se simula | Respuesta esperada de la Gateway |
|---|---|---|
| Servicio caído | Puerto sin nadie escuchando | `502 MICROSERVICIO_INALCANZABLE` |
| Timeout | Servidor que tarda 2 s; timeout del servicio 0,3 s | `504 TIEMPO_AGOTADO` |
| Respuesta inválida (HTTP roto) | Socket que contesta texto que no es HTTP | `502 RESPUESTA_INVALIDA` |
| Respuesta inválida (JSON roto) | `200` con `Content-Type: application/json` y body roto | `502 RESPUESTA_INVALIDA` |
| Error 5xx sin JSON | `500` en texto plano con una traza | `500 ERROR_MICROSERVICIO` |
| Error 5xx con JSON | `503 {"detail": ...}` del servicio | pasa tal cual + `X-Request-ID` |
| Servicio sano | `200` JSON | pasa tal cual |

En todos los errores generados por la Gateway se comprueba además que: el body
trae el formato común con `request_id`; la cabecera `X-Request-ID` coincide; los
502/503/504 traen `Retry-After`; ni la URL interna ni el contenido recibido del
servicio llegan al cliente; y el log de la Gateway nombra el servicio y el
`request_id` sin la URL interna.
"""
from __future__ import annotations

import json
import logging
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

import gateway.cliente_http as cliente_http
import gateway.rutas as rutas
from gateway.config import settings
from gateway.errores import (
    ERROR_MICROSERVICIO,
    MENSAJE_RESPUESTA_INVALIDA,
    MENSAJE_SERVICIO_CAIDO,
    MENSAJE_TIEMPO_AGOTADO,
    MICROSERVICIO_INALCANZABLE,
    RESPUESTA_INVALIDA,
    TIEMPO_AGOTADO,
)
from gateway.main import app

PREFIJO = "vehiculos"  # lo atiende MS2 (ms2_taller)
TRAZA_INTERNA = 'Traceback: File "/srv/ms2/db.py", line 9, psycopg.OperationalError'


class _MicroservicioFalso(BaseHTTPRequestHandler):
    """MS2 de mentira: el comportamiento depende del último segmento de la ruta."""

    recibidos: list[dict] = []

    def log_message(self, *_args) -> None:  # silencio en la salida de pytest
        pass

    def _responder(self, estado: int, cuerpo: bytes, tipo: str) -> None:
        self.send_response(estado)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self) -> None:  # noqa: N802 (nombre de BaseHTTPRequestHandler)
        type(self).recibidos.append(
            {"ruta": self.path, "request_id": self.headers.get("X-Request-ID")}
        )
        escenario = self.path.rsplit("/", 1)[-1]
        if escenario == "lento":
            time.sleep(2)
            self._responder(200, b'{"ok": true}', "application/json")
        elif escenario == "json-roto":
            self._responder(200, b'{"vehiculos": [ {"patente": "AB', "application/json")
        elif escenario == "500-texto":
            self._responder(500, TRAZA_INTERNA.encode(), "text/plain")
        elif escenario == "503-json":
            cuerpo = json.dumps({"detail": "La base de MS2 no responde"}).encode()
            self._responder(503, cuerpo, "application/json")
        else:
            self._responder(200, b'[{"vehiculo_id": 1}]', "application/json")


@contextmanager
def _servidor_http() -> Iterator[str]:
    _MicroservicioFalso.recibidos = []
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), _MicroservicioFalso)
    servidor.daemon_threads = True
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        yield f"http://127.0.0.1:{servidor.server_address[1]}"
    finally:
        servidor.shutdown()
        servidor.server_close()


@contextmanager
def _servidor_que_no_habla_http() -> Iterator[str]:
    """Acepta la conexión y contesta bytes que no son una respuesta HTTP."""
    oyente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    oyente.bind(("127.0.0.1", 0))
    oyente.listen()
    activo = threading.Event()
    activo.set()

    def atender() -> None:
        oyente.settimeout(0.2)
        while activo.is_set():
            try:
                conexion, _ = oyente.accept()
            except OSError:
                continue
            with conexion:
                try:
                    conexion.recv(65536)
                    conexion.sendall(b"ESTO NO ES HTTP\r\n\r\n")
                except OSError:
                    pass

    hilo = threading.Thread(target=atender, daemon=True)
    hilo.start()
    try:
        yield f"http://127.0.0.1:{oyente.getsockname()[1]}"
    finally:
        activo.clear()
        hilo.join(timeout=2)
        oyente.close()


def _puerto_cerrado() -> str:
    """URL de un puerto libre en el que nadie escucha (servicio caído)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    return f"http://127.0.0.1:{puerto}"


@pytest.fixture(autouse=True)
def _cliente_sin_estado() -> Iterator[None]:
    yield
    cliente_http.reset_cliente()


@pytest.fixture
def gateway() -> TestClient:
    return TestClient(app)


def _apuntar_ms2_a(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    monkeypatch.setitem(rutas.RUTAS, PREFIJO, url)


def _error_comun(respuesta, *, estado: int, codigo: str, detalle: str, rid: str) -> None:
    assert respuesta.status_code == estado
    cuerpo = respuesta.json()
    assert cuerpo["detail"] == detalle
    assert cuerpo["error"]["codigo"] == codigo
    assert cuerpo["error"]["estado"] == estado
    assert cuerpo["error"]["request_id"] == rid
    assert respuesta.headers["x-request-id"] == rid
    assert respuesta.headers["cache-control"] == "no-store"
    if estado in (502, 503, 504):
        assert respuesta.headers["retry-after"] == str(settings.RETRY_AFTER_SECONDS)
    assert "127.0.0.1" not in respuesta.text


def _log_gateway(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == "gateway"]


# --------------------------------------------------------------------------- #
# Servicio caído                                                              #
# --------------------------------------------------------------------------- #

def test_servicio_caido_responde_502_controlado(
    gateway: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _apuntar_ms2_a(monkeypatch, _puerto_cerrado())

    with caplog.at_level(logging.WARNING, logger="gateway"):
        inicio = time.perf_counter()
        r = gateway.get("/api/vehiculos", headers={"X-Request-ID": "sim-caido-1"})
        duracion = time.perf_counter() - inicio

    _error_comun(
        r,
        estado=502,
        codigo=MICROSERVICIO_INALCANZABLE,
        detalle=MENSAJE_SERVICIO_CAIDO,
        rid="sim-caido-1",
    )
    # Falla rápido: no espera el timeout de lectura (15 s).
    assert duracion < settings.TIMEOUT_READ_SECONDS
    linea = next(m for m in _log_gateway(caplog) if "Fallo de red" in m)
    assert "ms2_taller" in linea and "ConnectError" in linea and "sim-caido-1" in linea
    assert "127.0.0.1" not in linea


# --------------------------------------------------------------------------- #
# Timeout                                                                     #
# --------------------------------------------------------------------------- #

def test_servicio_lento_corta_por_timeout_y_responde_504(
    gateway: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(settings, "MS2_TIMEOUT_SECONDS", 0.3)
    with _servidor_http() as url:
        _apuntar_ms2_a(monkeypatch, url)
        with caplog.at_level(logging.WARNING, logger="gateway"):
            inicio = time.perf_counter()
            r = gateway.get("/api/vehiculos/lento", headers={"X-Request-ID": "sim-lento-1"})
            duracion = time.perf_counter() - inicio

        _error_comun(
            r,
            estado=504,
            codigo=TIEMPO_AGOTADO,
            detalle=MENSAJE_TIEMPO_AGOTADO,
            rid="sim-lento-1",
        )
        # Cortó en ~0,3 s, no esperó los 2 s del servicio.
        assert duracion < 1.5
        # El servicio recibió la petición con el mismo ID (correlación).
        assert _MicroservicioFalso.recibidos[0]["request_id"] == "sim-lento-1"
    linea = next(m for m in _log_gateway(caplog) if "Fallo de red" in m)
    assert "ReadTimeout" in linea and "timeout_lectura=0.3s" in linea


# --------------------------------------------------------------------------- #
# Respuesta inválida                                                          #
# --------------------------------------------------------------------------- #

def test_respuesta_que_no_es_http_responde_502_respuesta_invalida(
    gateway: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _servidor_que_no_habla_http() as url:
        _apuntar_ms2_a(monkeypatch, url)
        r = gateway.get("/api/vehiculos", headers={"X-Request-ID": "sim-http-roto"})

    _error_comun(
        r,
        estado=502,
        codigo=RESPUESTA_INVALIDA,
        detalle=MENSAJE_RESPUESTA_INVALIDA,
        rid="sim-http-roto",
    )
    assert "ESTO NO ES HTTP" not in r.text


def test_200_con_json_roto_responde_502_respuesta_invalida(
    gateway: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    with _servidor_http() as url:
        _apuntar_ms2_a(monkeypatch, url)
        with caplog.at_level(logging.WARNING, logger="gateway"):
            r = gateway.get(
                "/api/vehiculos/json-roto", headers={"X-Request-ID": "sim-json-roto"}
            )

    _error_comun(
        r,
        estado=502,
        codigo=RESPUESTA_INVALIDA,
        detalle=MENSAJE_RESPUESTA_INVALIDA,
        rid="sim-json-roto",
    )
    assert "patente" not in r.text  # el body roto no se reenvía
    linea = next(m for m in _log_gateway(caplog) if "JSON inválido" in m)
    assert "ms2_taller" in linea and "sim-json-roto" in linea
    assert "patente" not in linea  # ni se registra


def test_500_en_texto_no_filtra_la_traza_interna(
    gateway: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _servidor_http() as url:
        _apuntar_ms2_a(monkeypatch, url)
        r = gateway.get("/api/vehiculos/500-texto", headers={"X-Request-ID": "sim-500"})

    assert r.status_code == 500
    assert r.json()["error"]["codigo"] == ERROR_MICROSERVICIO
    assert r.headers["x-request-id"] == "sim-500"
    assert "Traceback" not in r.text and "psycopg" not in r.text


def test_503_json_del_servicio_pasa_tal_cual_con_su_request_id(
    gateway: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _servidor_http() as url:
        _apuntar_ms2_a(monkeypatch, url)
        r = gateway.get("/api/vehiculos/503-json", headers={"X-Request-ID": "sim-503"})

    assert r.status_code == 503
    assert r.json() == {"detail": "La base de MS2 no responde"}  # contrato intacto
    assert r.headers["x-request-id"] == "sim-503"


def test_servicio_sano_sigue_pasando_tal_cual(
    gateway: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _servidor_http() as url:
        _apuntar_ms2_a(monkeypatch, url)
        r = gateway.get("/api/vehiculos", headers={"X-Request-ID": "sim-ok"})

    assert r.status_code == 200
    assert r.json() == [{"vehiculo_id": 1}]
    assert r.headers["x-request-id"] == "sim-ok"


def test_204_vacio_con_content_type_json_no_es_respuesta_invalida(
    gateway: TestClient,
) -> None:
    import httpx
    import respx

    with respx.mock(assert_all_mocked=True) as mock:
        mock.delete(f"{settings.MS2_URL}/vehiculos/9").mock(
            return_value=httpx.Response(204, headers={"content-type": "application/json"})
        )
        r = gateway.delete("/api/vehiculos/9")
    assert r.status_code == 204


# --------------------------------------------------------------------------- #
# Subida interrumpida por el cliente                                          #
# --------------------------------------------------------------------------- #

def test_subida_interrumpida_no_llega_al_microservicio() -> None:
    """El cliente corta a mitad del body: 400 SOLICITUD_INTERRUMPIDA, sin proxy."""
    import asyncio

    import httpx
    import respx

    from gateway.errores import SOLICITUD_INTERRUMPIDA

    mensajes_enviados: list[dict] = []

    async def recibir():
        # Primer trozo del body y luego la desconexión del cliente.
        if not mensajes_enviados:
            mensajes_enviados.append({})
            return {"type": "http.request", "body": b"--frontera\r\n", "more_body": True}
        return {"type": "http.disconnect"}

    respuesta: dict = {}

    async def enviar(mensaje):
        if mensaje["type"] == "http.response.start":
            respuesta["estado"] = mensaje["status"]
        elif mensaje["type"] == "http.response.body":
            respuesta["body"] = respuesta.get("body", b"") + mensaje.get("body", b"")

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/evidencias",
        "raw_path": b"/api/evidencias",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"gateway"),
            (b"content-type", b"multipart/form-data; boundary=frontera"),
            (b"x-request-id", b"sim-cortada"),
        ],
        "client": ("10.0.0.9", 5000),
        "server": ("gateway", 80),
    }
    with respx.mock(assert_all_called=False) as mock:
        ruta = mock.post(f"{settings.MS4_URL}/evidencias").mock(
            return_value=httpx.Response(201, json={})
        )
        asyncio.run(app(scope, recibir, enviar))

    assert respuesta["estado"] == 400
    cuerpo = json.loads(respuesta["body"])
    assert cuerpo["error"]["codigo"] == SOLICITUD_INTERRUMPIDA
    assert cuerpo["error"]["request_id"] == "sim-cortada"
    assert not ruta.called  # MS4 nunca recibió un body incompleto
