"""Direccionamiento completo de la Gateway hacia los cuatro microservicios.

Semana 7. Comprueba, contra los apps REALES de MS1..MS4 (su OpenAPI generado
por FastAPI, sin levantarlos ni tocar bases), que:

* cada endpoint publicado por un microservicio es alcanzable vía
  `/api/{ruta}` y la Gateway lo dirige a ESE microservicio y no a otro;
* el catálogo `gateway.rutas.MICROSERVICIOS` declara exactamente los prefijos
  que publica cada servicio (ni sobran ni faltan);
* ningún prefijo queda asignado a dos servicios;
* el proxy reenvía a la URL interna correcta con método, ruta y query intactos
  (respx, una petición por servicio y método).
"""
from __future__ import annotations

import re

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from gateway.config import settings
from gateway.main import app as gateway_app
from gateway.rutas import (
    MICROSERVICIOS,
    MICROSERVICIOS_POR_NOMBRE,
    RUTAS,
    nombre_servicio,
    resolver_microservicio,
)
from services.ms1_auth.main import app as app_ms1
from services.ms2_taller.main import app as app_ms2
from services.ms3_presupuestos.main import app as app_ms3
from services.ms4_evidencias.main import app as app_ms4

_APPS = {
    "ms1_auth": app_ms1,
    "ms2_taller": app_ms2,
    "ms3_presupuestos": app_ms3,
    "ms4_evidencias": app_ms4,
}

_URL_POR_SERVICIO = {
    "ms1_auth": settings.MS1_URL,
    "ms2_taller": settings.MS2_URL,
    "ms3_presupuestos": settings.MS3_URL,
    "ms4_evidencias": settings.MS4_URL,
}

# Rutas de infraestructura de cada servicio: no se publican bajo /api (la
# Gateway las consulta directo en /api/health/servicios).
_INFRAESTRUCTURA = re.compile(r"^/(health(/.*)?|docs|redoc|openapi\.json)$")

_METODOS = ("get", "post", "put", "patch", "delete")


def _operaciones(nombre: str) -> list[tuple[str, str]]:
    """(MÉTODO, ruta) de negocio que publica el microservicio real."""
    return [
        (metodo.upper(), ruta)
        for ruta, item in _APPS[nombre].openapi()["paths"].items()
        if not _INFRAESTRUCTURA.match(ruta)
        for metodo in _METODOS
        if metodo in item
    ]


def _ruta_concreta(ruta: str) -> str:
    """Reemplaza `{parametro}` por un valor válido (`7`, o `cliente` en `rol`)."""
    return re.sub(
        r"\{(\w+)\}",
        lambda m: "cliente" if m.group(1) == "rol" else "7",
        ruta,
    )


_TODAS = [
    pytest.param(nombre, metodo, ruta, id=f"{nombre}:{metodo} {ruta}")
    for nombre in _APPS
    for metodo, ruta in _operaciones(nombre)
]


def test_cada_servicio_publica_endpoints_de_negocio() -> None:
    for nombre in _APPS:
        assert _operaciones(nombre), f"{nombre} no publica endpoints"


def test_el_catalogo_cubre_los_cuatro_microservicios() -> None:
    assert [s.nombre for s in MICROSERVICIOS] == list(_APPS)
    for servicio in MICROSERVICIOS:
        assert servicio.url == _URL_POR_SERVICIO[servicio.nombre]


@pytest.mark.parametrize("nombre", list(_APPS))
def test_prefijos_declarados_igual_a_los_publicados(nombre: str) -> None:
    """Los prefijos del catálogo son exactamente los primeros segmentos reales."""
    publicados = {ruta.strip("/").split("/", 1)[0] for _, ruta in _operaciones(nombre)}
    assert set(MICROSERVICIOS_POR_NOMBRE[nombre].prefijos) == publicados


def test_ningun_prefijo_pertenece_a_dos_servicios() -> None:
    vistos: dict[str, str] = {}
    for servicio in MICROSERVICIOS:
        for prefijo in servicio.todos_los_prefijos:
            assert prefijo not in vistos, f"{prefijo}: {vistos.get(prefijo)} y {servicio.nombre}"
            vistos[prefijo] = servicio.nombre
    assert set(vistos) == set(RUTAS)


@pytest.mark.parametrize("nombre,metodo,ruta", _TODAS)
def test_cada_endpoint_real_resuelve_a_su_microservicio(
    nombre: str, metodo: str, ruta: str
) -> None:
    camino = _ruta_concreta(ruta).lstrip("/")
    assert resolver_microservicio(camino) == _URL_POR_SERVICIO[nombre]
    assert nombre_servicio(camino) == nombre


@pytest.mark.parametrize("prefijo", sorted(RUTAS))
def test_prefijo_ignora_mayusculas(prefijo: str) -> None:
    assert resolver_microservicio(prefijo.upper() + "/1") == RUTAS[prefijo]


def test_prefijo_desconocido_no_resuelve() -> None:
    assert resolver_microservicio("facturas/1") is None
    assert nombre_servicio("facturas/1") is None


# ---------------------------------------------------------------- reenvío --

_UNA_POR_SERVICIO_Y_METODO = sorted(
    {
        (nombre, metodo): ruta
        for nombre in _APPS
        for metodo, ruta in _operaciones(nombre)
    }.items()
)


@pytest.fixture
def gateway() -> TestClient:
    return TestClient(gateway_app)


@pytest.mark.parametrize(
    "nombre,metodo,ruta",
    [
        pytest.param(nombre, metodo, ruta, id=f"{nombre}:{metodo}")
        for (nombre, metodo), ruta in _UNA_POR_SERVICIO_Y_METODO
    ],
)
def test_proxy_reenvia_a_la_url_interna_del_servicio(
    gateway: TestClient, nombre: str, metodo: str, ruta: str
) -> None:
    camino = _ruta_concreta(ruta)
    destino = f"{_URL_POR_SERVICIO[nombre]}{camino}"
    with respx.mock(assert_all_mocked=True) as mock:
        llamada = mock.request(metodo, destino, params={"marca": "1"}).mock(
            return_value=httpx.Response(200, json={"servicio": nombre})
        )
        respuesta = gateway.request(metodo, f"/api{camino}?marca=1")

    assert respuesta.status_code == 200, respuesta.text
    assert llamada.call_count == 1
    enviada = llamada.calls.last.request
    assert enviada.method == metodo
    assert enviada.url.path == camino
    assert enviada.url.params["marca"] == "1"


@pytest.mark.parametrize(
    "servicio",
    [pytest.param(s, id=s.nombre) for s in MICROSERVICIOS if s.alias],
)
def test_alias_llegan_al_mismo_servicio(gateway: TestClient, servicio) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        for alias in servicio.alias:
            mock.get(f"{servicio.url}/{alias}/1").mock(
                return_value=httpx.Response(404, json={"detail": "Not Found"})
            )
        for alias in servicio.alias:
            respuesta = gateway.get(f"/api/{alias}/1")
            # El 404 es del microservicio (pasa tal cual), no RUTA_NO_ENCONTRADA.
            assert respuesta.status_code == 404
            assert respuesta.json() == {"detail": "Not Found"}


def test_indice_lista_los_prefijos_de_cada_servicio(gateway: TestClient) -> None:
    cuerpo = gateway.get("/").json()
    for servicio in MICROSERVICIOS:
        assert set(cuerpo["microservicios"][servicio.nombre]) == {
            f"/api/{prefijo}" for prefijo in servicio.todos_los_prefijos
        }
