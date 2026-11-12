"""Validación de disponibilidad de stock antes de utilizar un repuesto (§4.6).

`services/disponibilidad.py` y los endpoints:
    POST /inventario/disponibilidad
    GET  /inventario/ordenes/{orden_id}/disponibilidad

y su uso al aprobar un presupuesto (la orden queda en reparación o esperando
repuestos según lo que realmente está disponible para ella).
"""
from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.ms3_presupuestos import datos_prueba as datos
from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import get_db
from services.ms3_presupuestos.main import app
from services.ms3_presupuestos.models import ItemPresupuesto, Repuesto
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo
from services.ms3_presupuestos.services import disponibilidad
from services.ms3_presupuestos.services import presupuestos as casos_presupuestos
from services.ms3_presupuestos.tests import fabricas
from shared.auth import NombreRol, crear_token_acceso


def _cabecera(rol: NombreRol, usuario_id: int) -> dict[str, str]:
    return {"Authorization": "Bearer " + crear_token_acceso(
        usuario_id=usuario_id, roles=[rol],
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(), algoritmo="HS256")}


MECANICO = _cabecera(NombreRol.MECANICO, datos.MECANICO_ID)
CLIENTE = _cabecera(NombreRol.CLIENTE, datos.CLIENTE_ID)


@pytest.fixture
def api(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as cliente:
            yield cliente
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def repuesto(db: Session) -> Repuesto:
    """Stock 10: 3 reservadas por la orden A y 2 por la orden B → libres 5."""
    r = fabricas.nuevo_repuesto(db, stock=10)
    fabricas.nuevo_movimiento(db, r, tipo="compromiso", cantidad=3, orden_id=ORDEN_A)
    fabricas.nuevo_movimiento(db, r, tipo="compromiso", cantidad=2, orden_id=ORDEN_B)
    return r


ORDEN_A, ORDEN_B, ORDEN_C = 7_100_001, 7_100_002, 7_100_003


def _consulta(api: TestClient, items: list[dict], orden_id: int | None = None):
    cuerpo = {"items": items} | ({"orden_id": orden_id} if orden_id else {})
    return api.post("/inventario/disponibilidad", headers=MECANICO, json=cuerpo)


# ===================================================== cálculo de disponible ==

def test_sin_orden_solo_cuenta_lo_libre(api: TestClient, repuesto: Repuesto) -> None:
    r = _consulta(api, [{"repuesto_id": repuesto.repuesto_id, "cantidad": 5}])
    assert r.status_code == 200, r.text
    d = r.json()["repuestos"][0]
    assert (d["stock"], d["reservado_para_orden"], d["comprometido_otras_ordenes"]) == (10, 0, 5)
    assert (d["disponible"], d["alcanza"], d["faltan"]) == (5, True, 0)
    assert r.json()["disponible"] is True


def test_para_una_orden_cuenta_su_propia_reserva(api: TestClient, repuesto: Repuesto) -> None:
    r = _consulta(api, [{"repuesto_id": repuesto.repuesto_id, "cantidad": 8}], orden_id=ORDEN_A)
    d = r.json()["repuestos"][0]
    # Libres 5 + las 3 que ya reservó A = 8: alcanza justo.
    assert (d["reservado_para_orden"], d["comprometido_otras_ordenes"]) == (3, 2)
    assert (d["disponible"], d["alcanza"]) == (8, True)


def test_no_alcanza_si_hay_que_tomar_lo_reservado_por_otra_orden(
    api: TestClient, repuesto: Repuesto
) -> None:
    r = _consulta(api, [{"repuesto_id": repuesto.repuesto_id, "cantidad": 7}], orden_id=ORDEN_C)
    d = r.json()["repuestos"][0]
    assert (d["disponible"], d["alcanza"], d["faltan"]) == (5, False, 2)
    assert r.json()["disponible"] is False


def test_un_repuesto_repetido_se_suma(api: TestClient, repuesto: Repuesto) -> None:
    rid = repuesto.repuesto_id
    r = _consulta(api, [{"repuesto_id": rid, "cantidad": 3}, {"repuesto_id": rid, "cantidad": 3}])
    assert r.json()["repuestos"][0]["requerido"] == 6
    assert r.json()["disponible"] is False


def test_varios_repuestos_basta_que_falte_uno(api: TestClient, db: Session, repuesto: Repuesto) -> None:
    sobra = fabricas.nuevo_repuesto(db, stock=50)
    r = _consulta(api, [{"repuesto_id": sobra.repuesto_id, "cantidad": 10},
                        {"repuesto_id": repuesto.repuesto_id, "cantidad": 6}])
    alcanza = {d["repuesto_id"]: d["alcanza"] for d in r.json()["repuestos"]}
    assert alcanza == {sobra.repuesto_id: True, repuesto.repuesto_id: False}
    assert r.json()["disponible"] is False


def test_validar_no_mueve_stock(api: TestClient, db: Session, repuesto: Repuesto) -> None:
    antes = len(repuesto.movimientos)
    _consulta(api, [{"repuesto_id": repuesto.repuesto_id, "cantidad": 99}])
    db.expire_all()
    assert db.get(Repuesto, repuesto.repuesto_id).stock == 10
    assert len(db.get(Repuesto, repuesto.repuesto_id).movimientos) == antes


def test_repuesto_inexistente_es_404(api: TestClient, repuesto: Repuesto) -> None:
    r = _consulta(api, [{"repuesto_id": repuesto.repuesto_id, "cantidad": 1},
                        {"repuesto_id": 999_999_991, "cantidad": 1}])
    assert r.status_code == 404 and "999999991" in r.json()["detail"]


@pytest.mark.parametrize("cuerpo", [
    {"items": []},
    {"items": [{"repuesto_id": 1, "cantidad": 0}]},
    {"items": [{"repuesto_id": 0, "cantidad": 1}]},
    {"items": [{"repuesto_id": 1, "cantidad": 1}], "orden_id": 0},
    {"items": [{"repuesto_id": 1, "cantidad": 1, "precio": 5}]},
])
def test_consulta_invalida_es_422(api: TestClient, cuerpo: dict) -> None:
    assert api.post("/inventario/disponibilidad", headers=MECANICO, json=cuerpo).status_code == 422


def test_el_cliente_no_consulta_disponibilidad(api: TestClient, repuesto: Repuesto) -> None:
    cuerpo = {"items": [{"repuesto_id": repuesto.repuesto_id, "cantidad": 1}]}
    assert api.post("/inventario/disponibilidad", headers=CLIENTE, json=cuerpo).status_code == 403
    assert api.post("/inventario/disponibilidad", json=cuerpo).status_code == 401
    assert api.get(f"/inventario/ordenes/{ORDEN_A}/disponibilidad", headers=CLIENTE).status_code == 403


# ========================================= disponibilidad de una orden aprobada ==

def _item(repuesto: Repuesto, cantidad: str) -> ItemPresupuesto:
    return ItemPresupuesto(tipo="repuesto", descripcion=repuesto.nombre, cantidad=Decimal(cantidad),
                           precio_unitario=Decimal("1000"), repuesto=repuesto)


def test_orden_aprobada_descuenta_lo_ya_consumido(api: TestClient, db: Session) -> None:
    r = fabricas.nuevo_repuesto(db, stock=4)
    p = fabricas.nuevo_presupuesto(db, estado="aprobado", items=[_item(r, "6")])
    # Ya usó 3 de las 6 presupuestadas (el stock bajó de 4 a 1).
    fabricas.nuevo_movimiento(db, r, tipo="consumo", cantidad=3, orden_id=p.orden_id)
    r.stock = 1
    db.flush()

    res = api.get(f"/inventario/ordenes/{p.orden_id}/disponibilidad", headers=MECANICO).json()
    d = res["repuestos"][0]
    assert (res["presupuesto_id"], res["version"]) == (p.presupuesto_id, 1)
    assert (d["requerido"], d["disponible"], d["faltan"]) == (3, 1, 2)
    assert res["disponible"] is False


def test_orden_con_todo_consumido_ya_no_requiere_nada(api: TestClient, db: Session) -> None:
    r = fabricas.nuevo_repuesto(db, stock=0)
    p = fabricas.nuevo_presupuesto(db, estado="aprobado", items=[_item(r, "2")])
    fabricas.nuevo_movimiento(db, r, tipo="consumo", cantidad=2, orden_id=p.orden_id)

    res = api.get(f"/inventario/ordenes/{p.orden_id}/disponibilidad", headers=MECANICO).json()
    assert res["disponible"] is True and res["repuestos"][0]["requerido"] == 0


def test_cantidades_decimales_se_redondean_hacia_arriba(api: TestClient, db: Session) -> None:
    aceite = fabricas.nuevo_repuesto(db, stock=1)
    p = fabricas.nuevo_presupuesto(db, estado="aprobado", items=[_item(aceite, "1.5")])
    d = api.get(f"/inventario/ordenes/{p.orden_id}/disponibilidad",
                headers=MECANICO).json()["repuestos"][0]
    assert (d["requerido"], d["alcanza"]) == (2, False)


def test_orden_solo_con_mano_de_obra_esta_disponible(api: TestClient, db: Session) -> None:
    p = fabricas.nuevo_presupuesto(db, estado="aprobado")
    res = api.get(f"/inventario/ordenes/{p.orden_id}/disponibilidad", headers=MECANICO).json()
    assert res == {"orden_id": p.orden_id, "disponible": True, "repuestos": [],
                   "presupuesto_id": p.presupuesto_id, "version": 1}


@pytest.mark.parametrize(("estado", "codigo"), [(None, 404), ("borrador", 409), ("enviado", 409)])
def test_orden_sin_presupuesto_aprobado(api: TestClient, db: Session, estado, codigo) -> None:
    orden = fabricas.nuevo_orden_id()
    if estado:
        fabricas.nuevo_presupuesto(db, estado=estado, orden_id=orden)
    assert api.get(f"/inventario/ordenes/{orden}/disponibilidad", headers=MECANICO).status_code == codigo


# =========================================== uso al aprobar un presupuesto ==

def test_aprobar_usa_la_misma_validacion(db: Session) -> None:
    r = fabricas.nuevo_repuesto(db, stock=5)
    otra = fabricas.nuevo_orden_id()
    fabricas.nuevo_movimiento(db, r, tipo="compromiso", cantidad=3, orden_id=otra)
    p = fabricas.nuevo_presupuesto(db, estado="enviado", items=[_item(r, "3")])

    uow = UnidadDeTrabajo(db)
    resultado = casos_presupuestos.decidir_version(
        uow, presupuesto_id=p.presupuesto_id, numero=1, cliente_usuario_id=datos.CLIENTE_ID,
        decision="aprobado", motivo=None, confirmar_cancelacion=False)

    # Solo 2 libres (3 son de otra orden): queda esperando repuestos.
    assert resultado.efecto_en_orden == "esperando_repuestos"
    assert [(f.repuesto_id, f.disponible) for f in resultado.repuestos_faltantes] == [(r.repuesto_id, 2)]


def test_evaluar_con_bloqueo_devuelve_lo_mismo(db: Session, repuesto: Repuesto) -> None:
    uow = UnidadDeTrabajo(db)
    sin = disponibilidad.evaluar(uow, {repuesto.repuesto_id: 6}, orden_id=ORDEN_B)
    con = disponibilidad.evaluar(uow, {repuesto.repuesto_id: 6}, orden_id=ORDEN_B, bloquear=True)
    assert sin == con and con.repuestos[0].disponible == 7
