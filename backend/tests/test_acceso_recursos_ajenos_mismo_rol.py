"""Acceso a recursos ajenos del mismo rol: consulta de presupuestos en MS3.

`test_acceso_indebido_roles.py` revisa la autorización **entre** roles; este
módulo prueba el eje horizontal: dos cuentas con el mismo rol (aquí, dos
Clientes) no deben leer los recursos de la otra.

El resto de la matriz "recurso ajeno" ya está probada y no se duplica aquí:
vehículos (`test_vehiculos_api.py`), órdenes con detalle, historial, bitácora y
cancelación (`test_ordenes_api.py`), la decisión del cliente
(`test_decisiones_presupuesto_integracion.py`) y las evidencias
(`test_ms4_autorizacion_evidencias.py`). Faltaban las rutas de **consulta** de
presupuestos del cliente, las únicas que no se probaban contra una orden ajena.

Se corren sobre el mismo flujo real MS3↔MS2 que usa el módulo de decisiones
(bases SQLite separadas y transporte HTTP en proceso), reutilizando
`preparar_flujo`. El contrato exigido es el de `docs/contratos-api-gateway.md`:
un recurso inexistente y uno ajeno responden igual, para no revelar la
existencia de los recursos de otros usuarios.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.ms2_taller.models import Base as BaseMS2
from services.ms3_presupuestos.models import Base as BaseMS3
from test_decisiones_presupuesto_integracion import (
    _base_aislada,
    _headers,
    preparar_flujo,
)

# Cuenta dueña del vehículo y de la orden que siembra `preparar_flujo`.
DUENO = 42
# Otra cuenta con el mismo rol Cliente: ni la orden ni el presupuesto son suyos.
OTRO_CLIENTE = 77
ORDEN_INEXISTENTE = 999_999
PRESUPUESTO_INEXISTENTE = 999_999


@pytest.fixture
def flujo(monkeypatch) -> SimpleNamespace:
    yield from preparar_flujo(
        monkeypatch, _base_aislada(BaseMS2), _base_aislada(BaseMS3)
    )


# ---------------------------------------------------------------------------
# Controles: el dueño sí ve lo suyo, para que el 404 deje claro que el filtro
# es la propiedad y no otra causa.
# ---------------------------------------------------------------------------


def test_el_dueno_lista_el_presupuesto_de_su_orden(flujo: SimpleNamespace) -> None:
    respuesta = flujo.ms3.get(
        f"/presupuestos?orden_id={flujo.orden_id}", headers=_headers(DUENO)
    )

    assert respuesta.status_code == 200
    pagina = respuesta.json()
    assert pagina["total"] == 1
    assert pagina["presupuestos"][0]["presupuesto_id"] == flujo.presupuesto_id


def test_el_dueno_consulta_el_detalle_con_sus_versiones(
    flujo: SimpleNamespace,
) -> None:
    respuesta = flujo.ms3.get(
        f"/presupuestos/{flujo.presupuesto_id}", headers=_headers(DUENO)
    )

    assert respuesta.status_code == 200
    detalle = respuesta.json()
    assert detalle["presupuesto_id"] == flujo.presupuesto_id
    assert detalle["orden_id"] == flujo.orden_id
    assert [v["numero"] for v in detalle["versiones"]] == [1]


def test_el_dueno_ve_la_version_enviada_y_sus_items(flujo: SimpleNamespace) -> None:
    respuesta = flujo.ms3.get(
        f"/presupuestos/{flujo.presupuesto_id}/versiones/1", headers=_headers(DUENO)
    )

    assert respuesta.status_code == 200
    version = respuesta.json()
    assert version["numero"] == 1
    assert [i["descripcion"] for i in version["items"]] == ["Repuesto"]


# ---------------------------------------------------------------------------
# Recurso ajeno del mismo rol: un Cliente contra los recursos de otro Cliente
# ---------------------------------------------------------------------------


def test_un_cliente_no_lista_el_presupuesto_de_la_orden_de_otro_cliente(
    flujo: SimpleNamespace,
) -> None:
    """La propiedad de la orden se confirma contra MS2 con el JWT del cliente."""

    respuesta = flujo.ms3.get(
        f"/presupuestos?orden_id={flujo.orden_id}", headers=_headers(OTRO_CLIENTE)
    )

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": f"Orden {flujo.orden_id} no existe"}


def test_un_cliente_no_consulta_el_detalle_de_un_presupuesto_ajeno(
    flujo: SimpleNamespace,
) -> None:
    """El presupuesto existe, pero su orden es de otro cliente: no se revela."""

    respuesta = flujo.ms3.get(
        f"/presupuestos/{flujo.presupuesto_id}", headers=_headers(OTRO_CLIENTE)
    )

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": f"Presupuesto {flujo.presupuesto_id} no existe"}


def test_un_cliente_no_ve_versiones_de_un_presupuesto_ajeno(
    flujo: SimpleNamespace,
) -> None:
    """La versión enviada (con sus ítems y totales) no se filtra al cliente ajeno."""

    respuesta = flujo.ms3.get(
        f"/presupuestos/{flujo.presupuesto_id}/versiones/1",
        headers=_headers(OTRO_CLIENTE),
    )

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": f"Presupuesto {flujo.presupuesto_id} no existe"}


def test_un_presupuesto_ajeno_y_otro_inexistente_responden_con_el_mismo_codigo(
    flujo: SimpleNamespace,
) -> None:
    """Sin enumeración: no se puede distinguir un presupuesto ajeno de uno ausente."""

    ajeno = flujo.ms3.get(
        f"/presupuestos/{flujo.presupuesto_id}", headers=_headers(OTRO_CLIENTE)
    )
    inexistente = flujo.ms3.get(
        f"/presupuestos/{PRESUPUESTO_INEXISTENTE}", headers=_headers(OTRO_CLIENTE)
    )

    assert ajeno.status_code == inexistente.status_code == 404
    # Ninguna de las dos respuestas entrega datos del presupuesto.
    assert set(ajeno.json()) == {"detail"}
    assert set(inexistente.json()) == {"detail"}


def test_una_orden_ajena_y_otra_inexistente_responden_con_el_mismo_codigo_en_el_listado(
    flujo: SimpleNamespace,
) -> None:
    """Lo mismo aplica al `orden_id` del listado, que es la puerta de entrada."""

    ajena = flujo.ms3.get(
        f"/presupuestos?orden_id={flujo.orden_id}", headers=_headers(OTRO_CLIENTE)
    )
    inexistente = flujo.ms3.get(
        f"/presupuestos?orden_id={ORDEN_INEXISTENTE}", headers=_headers(OTRO_CLIENTE)
    )

    assert ajena.status_code == inexistente.status_code == 404
    assert set(ajena.json()) == {"detail"}
    assert set(inexistente.json()) == {"detail"}
