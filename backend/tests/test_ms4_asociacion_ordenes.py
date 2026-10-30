"""Asociación de evidencias con órdenes y presupuestos (MS4, Semana 6).

Al subir una evidencia, además de que la orden exista y sea visible (MS2):

- La orden no puede estar entregada (7) ni cancelada (8): responde 409 y no
  se lee ni se sube el archivo.
- Si el contexto es `presupuesto`, MS4 pregunta a MS3 (mismo JWT) a qué orden
  pertenece ese presupuesto: inexistente → 422, de otra orden → 422, MS3 sin
  responder → 503. Así una foto no queda asociada al presupuesto de otra orden.

También se prueban, sin levantar MS2 ni MS3, los clientes HTTP
`VerificadorOrdenesHttp` (ahora devuelve el estado) y
`VerificadorPresupuestosHttp`.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.ms4_evidencias import integracion_ms2, integracion_ms3
from services.ms4_evidencias.integracion_ms2 import (
    ESTADOS_ORDEN_CERRADA,
    VerificadorOrdenesHttp,
    obtener_verificador_ordenes,
)
from services.ms4_evidencias.integracion_ms3 import (
    PresupuestoNoEncontrado,
    ServicioPresupuestosNoDisponible,
    VerificadorPresupuestosHttp,
    obtener_verificador_presupuestos,
)
from services.ms4_evidencias.main import app
from shared.auth import NombreRol

from test_ms4_api_evidencias import (  # noqa: F401  (fixtures reutilizados)
    _contar_filas,
    _subir,
    _token,
    api,
    s3,
    s3_publico,
    sesion,
)
from test_ms4_recepcion import FakeS3

ORDEN = 1  # la orden que usa `_subir` por defecto


class OrdenConEstado:
    """Falso MS2: la orden es visible y está en el estado indicado."""

    def __init__(self, estado: int | None) -> None:
        self.estado = estado

    def verificar_acceso(self, orden_id: int, token: str) -> int | None:
        return self.estado


class PresupuestosFalsos:
    """Falso MS3: `ordenes` mapea presupuesto_id → orden_id."""

    def __init__(self, ordenes: dict[int, int] | None = None, *, caido: bool = False):
        self.ordenes = ordenes or {}
        self.caido = caido
        self.llamadas: list[tuple[int, str]] = []

    def orden_del_presupuesto(self, presupuesto_id: int, token: str) -> int:
        self.llamadas.append((presupuesto_id, token))
        if self.caido:
            raise ServicioPresupuestosNoDisponible("MS3 caído")
        if presupuesto_id not in self.ordenes:
            raise PresupuestoNoEncontrado(presupuesto_id)
        return self.ordenes[presupuesto_id]


def _mecanico() -> str:
    return _token(7, NombreRol.MECANICO)


def _usar_orden(estado: int | None) -> None:
    app.dependency_overrides[obtener_verificador_ordenes] = lambda: OrdenConEstado(estado)


def _usar_presupuestos(falso: PresupuestosFalsos) -> PresupuestosFalsos:
    app.dependency_overrides[obtener_verificador_presupuestos] = lambda: falso
    return falso


def _sin_residuos(s3: FakeS3, sesion: Session) -> None:
    assert not s3.objetos
    assert _contar_filas(sesion) == 0


def _subir_presupuesto(api: TestClient, presupuesto_id: int, **extra):
    return _subir(
        api, _mecanico(), contexto="presupuesto", presupuesto_id=presupuesto_id, **extra
    )


# --------------------------------------------------------------------------- #
# 1) Estado de la orden                                                       #
# --------------------------------------------------------------------------- #

def test_los_estados_cerrados_son_entregado_y_cancelado() -> None:
    assert ESTADOS_ORDEN_CERRADA == {7, 8}


@pytest.mark.parametrize("estado", sorted(ESTADOS_ORDEN_CERRADA))
def test_orden_entregada_o_cancelada_responde_409_sin_residuos(
    api: TestClient, s3: FakeS3, sesion: Session, estado: int
) -> None:
    _usar_orden(estado)

    respuesta = _subir(api, _mecanico())

    assert respuesta.status_code == 409
    assert respuesta.json() == {
        "detail": "La orden está entregada o cancelada y no admite nuevas evidencias"
    }
    _sin_residuos(s3, sesion)


@pytest.mark.parametrize("estado", [1, 2, 3, 4, 5, 6, None])
def test_orden_abierta_o_sin_estado_informado_admite_evidencias(
    api: TestClient, s3: FakeS3, estado: int | None
) -> None:
    _usar_orden(estado)

    respuesta = _subir(api, _mecanico())

    assert respuesta.status_code == 201, respuesta.text
    assert len(s3.objetos) == 1


def test_la_orden_cerrada_se_rechaza_antes_de_mirar_el_archivo(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    _usar_orden(7)

    # El archivo además es inválido: manda el 409 de la orden, no el 415.
    respuesta = _subir(api, _mecanico(), archivo=b"<html>", content_type="text/html")

    assert respuesta.status_code == 409
    _sin_residuos(s3, sesion)


# --------------------------------------------------------------------------- #
# 2) Presupuesto ↔ orden (MS3)                                                #
# --------------------------------------------------------------------------- #

def test_presupuesto_de_la_misma_orden_se_asocia(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    falso = _usar_presupuestos(PresupuestosFalsos({42: ORDEN}))

    respuesta = _subir_presupuesto(api, 42)

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["presupuesto_id"] == 42
    assert cuerpo["orden_id"] == ORDEN
    assert cuerpo["visible_cliente"] is True
    # MS4 reenvía el MISMO JWT del usuario a MS3.
    assert falso.llamadas == [(42, _mecanico())]


def test_presupuesto_de_otra_orden_responde_422_sin_residuos(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    _usar_presupuestos(PresupuestosFalsos({42: ORDEN + 1}))

    respuesta = _subir_presupuesto(api, 42)

    assert respuesta.status_code == 422
    assert respuesta.json() == {
        "detail": "El presupuesto indicado no pertenece a la orden"
    }
    _sin_residuos(s3, sesion)


def test_presupuesto_inexistente_responde_422_sin_residuos(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    _usar_presupuestos(PresupuestosFalsos({}))

    respuesta = _subir_presupuesto(api, 999)

    assert respuesta.status_code == 422
    assert respuesta.json() == {"detail": "El presupuesto indicado no existe"}
    _sin_residuos(s3, sesion)


def test_ms3_caido_responde_503_sin_residuos(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    _usar_presupuestos(PresupuestosFalsos(caido=True))

    respuesta = _subir_presupuesto(api, 42)

    assert respuesta.status_code == 503
    assert respuesta.json() == {
        "detail": "El servicio de presupuestos no está disponible"
    }
    _sin_residuos(s3, sesion)


@pytest.mark.parametrize("contexto", ["diagnostico", "reparacion", "resultado_final"])
def test_sin_presupuesto_no_se_consulta_a_ms3(
    api: TestClient, contexto: str
) -> None:
    falso = _usar_presupuestos(PresupuestosFalsos(caido=True))

    respuesta = _subir(api, _mecanico(), contexto=contexto)

    assert respuesta.status_code == 201, respuesta.text
    assert falso.llamadas == []


def test_el_presupuesto_se_valida_antes_que_el_archivo(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    _usar_presupuestos(PresupuestosFalsos({42: ORDEN + 1}))

    respuesta = _subir_presupuesto(
        api, 42, archivo=b"<html>", content_type="text/html"
    )

    assert respuesta.status_code == 422
    assert "no pertenece" in respuesta.json()["detail"]
    _sin_residuos(s3, sesion)


def test_reglas_del_schema_se_aplican_antes_de_consultar_a_ms3(
    api: TestClient,
) -> None:
    falso = _usar_presupuestos(PresupuestosFalsos({42: ORDEN}))

    # presupuesto_id con contexto diagnostico: regla 6, sin llamar a MS3.
    respuesta = _subir(api, _mecanico(), contexto="diagnostico", presupuesto_id=42)

    assert respuesta.status_code == 422
    assert falso.llamadas == []


# --------------------------------------------------------------------------- #
# 3) Clientes HTTP (httpx simulado, no se levanta MS2 ni MS3)                 #
# --------------------------------------------------------------------------- #

def _simular(monkeypatch: pytest.MonkeyPatch, modulo, respuesta, cuerpo=None) -> list:
    llamadas: list[dict] = []

    def falso_get(url: str, *, headers: dict, timeout: float):
        llamadas.append({"url": url, "headers": headers, "timeout": timeout})
        if isinstance(respuesta, Exception):
            raise respuesta
        peticion = httpx.Request("GET", url)
        if isinstance(cuerpo, (bytes, str)):
            return httpx.Response(respuesta, content=cuerpo, request=peticion)
        return httpx.Response(respuesta, json=cuerpo, request=peticion)

    monkeypatch.setattr(modulo.httpx, "get", falso_get)
    return llamadas


@pytest.mark.parametrize(
    ("cuerpo", "esperado"),
    [
        ({"orden_id": 31, "estado_codigo": 7}, 7),
        ({"orden_id": 31, "estado_codigo": 3}, 3),
        ({"orden_id": 31}, None),
        ({"estado_codigo": "7"}, None),
        ({"estado_codigo": True}, None),
        ([1, 2], None),
        (b"no es json", None),
    ],
)
def test_verificador_de_ordenes_devuelve_el_estado(
    monkeypatch: pytest.MonkeyPatch, cuerpo, esperado
) -> None:
    _simular(monkeypatch, integracion_ms2, 200, cuerpo)

    estado = VerificadorOrdenesHttp("http://ms2", 1).verificar_acceso(31, "t")

    assert estado == esperado


def test_verificador_de_presupuestos_reenvia_el_mismo_jwt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llamadas = _simular(
        monkeypatch, integracion_ms3, 200, {"presupuesto_id": 42, "orden_id": 31}
    )

    orden = VerificadorPresupuestosHttp("http://ms3:8003/", 2.5).orden_del_presupuesto(
        42, "token-del-mecanico"
    )

    assert orden == 31
    assert llamadas == [
        {
            "url": "http://ms3:8003/presupuestos/42",
            "headers": {"Authorization": "Bearer token-del-mecanico"},
            "timeout": 2.5,
        }
    ]


@pytest.mark.parametrize("codigo", [403, 404])
def test_verificador_de_presupuestos_inexistente_o_ajeno(
    monkeypatch: pytest.MonkeyPatch, codigo: int
) -> None:
    _simular(monkeypatch, integracion_ms3, codigo, {"detail": "x"})

    with pytest.raises(PresupuestoNoEncontrado):
        VerificadorPresupuestosHttp("http://ms3", 1).orden_del_presupuesto(42, "t")


@pytest.mark.parametrize(
    ("respuesta", "cuerpo"),
    [
        (500, {"detail": "x"}),
        (401, {"detail": "x"}),
        (httpx.ConnectError("caído"), None),
        (httpx.ReadTimeout("lento"), None),
        (200, b"no es json"),
        (200, {"presupuesto_id": 42}),
        (200, {"orden_id": "31"}),
    ],
)
def test_verificador_de_presupuestos_ms3_no_disponible(
    monkeypatch: pytest.MonkeyPatch, respuesta, cuerpo
) -> None:
    _simular(monkeypatch, integracion_ms3, respuesta, cuerpo)

    with pytest.raises(ServicioPresupuestosNoDisponible):
        VerificadorPresupuestosHttp("http://ms3", 1).orden_del_presupuesto(42, "t")


def test_verificador_de_presupuestos_usa_la_configuracion() -> None:
    verificador = integracion_ms3.obtener_verificador_presupuestos()

    assert verificador.url_base == integracion_ms3.settings.MS3_URL.rstrip("/")
    assert verificador.timeout == integracion_ms3.settings.MS3_TIMEOUT_SEGUNDOS
