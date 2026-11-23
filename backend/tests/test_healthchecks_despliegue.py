"""HEALTHCHECK de contenedores y script de verificación de salud vía Gateway."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx
import pytest

from scripts import healthcheck_contenedor as hc
from scripts import verificar_salud as vs

RAIZ = Path(__file__).resolve().parents[2]


# --- healthcheck_contenedor -------------------------------------------------

@pytest.mark.parametrize("servicio,ruta", [
    ("gateway", "/api/health"), ("ms1", "/health"), ("ms2", "/health"),
    ("ms3", "/health"), ("ms4", "/health"),
])
def test_url_por_servicio(servicio, ruta):
    assert hc.url_salud({"SGTM_SERVICIO": servicio, "PORT": "9100"}) == f"http://127.0.0.1:9100{ruta}"


def test_por_defecto_gateway_en_8000():
    assert hc.url_salud({}) == "http://127.0.0.1:8000/api/health"


def test_migraciones_no_consulta_http():
    assert hc.url_salud({"SGTM_SERVICIO": "migraciones"}) is None


@pytest.mark.parametrize("entorno", [
    {"SGTM_SERVICIO": "ms9"}, {"PORT": "abc"}, {"PORT": "0"}, {"PORT": "70000"},
])
def test_configuracion_invalida(entorno):
    with pytest.raises(ValueError):
        hc.url_salud(entorno)


class _Manejador(BaseHTTPRequestHandler):
    codigo = 200

    def do_GET(self):  # noqa: N802
        self.send_response(self.codigo)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, *args):
        pass


@pytest.fixture
def servidor():
    httpd = HTTPServer(("127.0.0.1", 0), _Manejador)
    hilo = threading.Thread(target=httpd.serve_forever, daemon=True)
    hilo.start()
    yield httpd
    httpd.shutdown()


def test_comprobar_200_es_sano(servidor):
    _Manejador.codigo = 200
    assert hc.comprobar(f"http://127.0.0.1:{servidor.server_port}/health")


def test_comprobar_500_no_es_sano(servidor):
    _Manejador.codigo = 500
    try:
        assert not hc.comprobar(f"http://127.0.0.1:{servidor.server_port}/health")
    finally:
        _Manejador.codigo = 200


def test_comprobar_sin_servidor_no_es_sano():
    assert not hc.comprobar("http://127.0.0.1:9/health", timeout=0.5)


def test_main_codigos_salida(monkeypatch):
    monkeypatch.setenv("SGTM_SERVICIO", "migraciones")
    assert hc.main() == 0
    monkeypatch.setenv("SGTM_SERVICIO", "ms9")
    assert hc.main() == 1
    monkeypatch.setenv("SGTM_SERVICIO", "ms1")
    monkeypatch.setenv("PORT", "9")
    assert hc.main() == 1


def test_dockerfiles_declaran_healthcheck():
    backend = (RAIZ / "Dockerfile").read_text(encoding="utf-8")
    frontend = (RAIZ / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    assert "HEALTHCHECK" in backend and "scripts/healthcheck_contenedor.py" in backend
    assert "HEALTHCHECK" in frontend and "/healthz" in frontend


# --- verificar_salud ----------------------------------------------------------

def _gateway_falsa(ms4_ok: bool = True) -> httpx.MockTransport:
    def responder(request: httpx.Request) -> httpx.Response:
        ruta = request.url.path
        if ruta == "/api/health":
            return httpx.Response(200, json={"status": "ok"})
        if ruta == "/api/health/servicios":
            return httpx.Response(200 if ms4_ok else 503,
                                  json={"status": "ok" if ms4_ok else "degradado"})
        servicio = ruta.rsplit("/", 1)[-1]
        sano = ms4_ok or servicio != "ms4_evidencias"
        return httpx.Response(200 if sano else 503, json={
            "estado": "ok" if sano else "degradado",
            "comprobaciones": {
                "proceso": {"estado": "ok", "latencia_ms": 3},
                "base": {"estado": "ok" if sano else "caido"},
            },
        })
    return httpx.MockTransport(responder)


@pytest.fixture
def cliente_falso(monkeypatch):
    def aplicar(ms4_ok: bool = True):
        original = httpx.Client

        def fabrica(*args, **kwargs):
            kwargs["transport"] = _gateway_falsa(ms4_ok)
            return original(*args, **kwargs)

        monkeypatch.setattr(vs.httpx, "Client", fabrica)
    return aplicar


def test_verificar_todo_ok(cliente_falso):
    cliente_falso(True)
    reporte = vs.verificar("http://gateway.test")
    assert reporte["ok"] is True
    assert len(reporte["checks"]) == 6
    assert "proceso=ok (3 ms)" in reporte["checks"][2]["detalle"]


def test_verificar_detecta_servicio_caido(cliente_falso, tmp_path, capsys):
    cliente_falso(False)
    salida = tmp_path / "salud.json"
    assert vs.main(["--base", "http://gateway.test", "--json", str(salida), "--sin-color"]) == 1
    reporte = json.loads(salida.read_text(encoding="utf-8"))
    fallidos = [c["nombre"] for c in reporte["checks"] if not c["ok"]]
    assert fallidos == ["servicios (bases)", "ms4_evidencias"]
    assert "FALLA" in capsys.readouterr().out


def test_verificar_sin_conexion():
    reporte = vs.verificar("http://127.0.0.1:9", timeout=0.5)
    assert reporte["ok"] is False
    assert all(c["codigo"] is None for c in reporte["checks"])
