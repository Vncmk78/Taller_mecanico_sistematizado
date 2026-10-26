"""Reglas de reserva, descuento y rechazo por stock insuficiente (services/reservas.py).

- Aprobar con stock suficiente RESERVA lo que falta usar, en la misma transacción.
- Aprobar sin stock no reserva nada (todo o nada) y la orden espera repuestos;
  POST /inventario/ordenes/{id}/reserva reintenta cuando llega stock.
- Una modificación aprobada AJUSTA la reserva (reserva la diferencia o libera el sobrante).
- Descontar usa primero lo reservado; varios repuestos van juntos o ninguno.
- El rechazo es 409 con `faltantes` y no deja nada a medias.
- Cancelar libera todo lo reservado.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.ms3_presupuestos import datos_prueba as datos
from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import get_db
from services.ms3_presupuestos.main import app
from services.ms3_presupuestos.models import ItemPresupuesto, MovimientoInventario, Repuesto
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo
from services.ms3_presupuestos.persistencia.repositorios import RepositorioMovimientos
from services.ms3_presupuestos.services import presupuestos as casos_presupuestos
from services.ms3_presupuestos.tests import fabricas
from shared.auth import NombreRol, crear_token_acceso

MECANICO = {"Authorization": "Bearer " + crear_token_acceso(
    usuario_id=datos.MECANICO_ID, roles=[NombreRol.MECANICO],
    clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(), algoritmo="HS256")}


@pytest.fixture
def api(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as cliente:
            yield cliente
    finally:
        app.dependency_overrides.pop(get_db, None)


def _item(repuesto: Repuesto, cantidad: str) -> ItemPresupuesto:
    return ItemPresupuesto(tipo="repuesto", descripcion=repuesto.nombre, cantidad=Decimal(cantidad),
                           precio_unitario=Decimal("1000"), repuesto=repuesto)


def _aprobar(db: Session, presupuesto_id: int, numero: int = 1):
    return casos_presupuestos.decidir_version(
        UnidadDeTrabajo(db), presupuesto_id=presupuesto_id, numero=numero,
        cliente_usuario_id=datos.CLIENTE_ID, decision="aprobado", motivo=None,
        confirmar_cancelacion=False)


def _reservado(db: Session, repuesto: Repuesto, orden_id: int) -> int:
    return RepositorioMovimientos(db).comprometido_por_orden(repuesto.repuesto_id).get(orden_id, 0)


def _clave() -> str:
    return f"regla-{uuid.uuid4().hex[:16]}"


# ================================================================== reserva ==

def test_aprobar_con_stock_reserva_lo_presupuestado(db: Session) -> None:
    disco = fabricas.nuevo_repuesto(db, stock=5)
    pastilla = fabricas.nuevo_repuesto(db, stock=8)
    p = fabricas.nuevo_presupuesto(db, estado="enviado", items=[_item(disco, "2"), _item(pastilla, "4")])

    resultado = _aprobar(db, p.presupuesto_id)

    assert resultado.efecto_en_orden == "en_reparacion"
    assert resultado.repuestos_reservados == {disco.repuesto_id: 2, pastilla.repuesto_id: 4}
    assert (_reservado(db, disco, p.orden_id), _reservado(db, pastilla, p.orden_id)) == (2, 4)
    # Reservar no cambia el stock físico.
    assert (disco.stock, pastilla.stock) == (5, 8)


def test_aprobar_sin_stock_no_reserva_nada(db: Session) -> None:
    sobra = fabricas.nuevo_repuesto(db, stock=10)
    falta = fabricas.nuevo_repuesto(db, stock=1)
    p = fabricas.nuevo_presupuesto(db, estado="enviado", items=[_item(sobra, "3"), _item(falta, "2")])

    resultado = _aprobar(db, p.presupuesto_id)

    assert resultado.efecto_en_orden == "esperando_repuestos"
    assert resultado.repuestos_reservados == {}
    # Todo o nada: tampoco se reservó el que sí alcanzaba.
    assert (_reservado(db, sobra, p.orden_id), _reservado(db, falta, p.orden_id)) == (0, 0)


def test_lo_reservado_ya_no_lo_puede_tomar_otra_orden(db: Session) -> None:
    r = fabricas.nuevo_repuesto(db, stock=4)
    primera = fabricas.nuevo_presupuesto(db, estado="enviado", items=[_item(r, "3")])
    segunda = fabricas.nuevo_presupuesto(db, estado="enviado", items=[_item(r, "2")])

    assert _aprobar(db, primera.presupuesto_id).efecto_en_orden == "en_reparacion"
    otra = _aprobar(db, segunda.presupuesto_id)

    assert otra.efecto_en_orden == "esperando_repuestos"
    assert [(f.repuesto_id, f.disponible) for f in otra.repuestos_faltantes] == [(r.repuesto_id, 1)]


def test_reintentar_la_reserva_cuando_llega_stock(api: TestClient, db: Session) -> None:
    r = fabricas.nuevo_repuesto(db, stock=1)
    p = fabricas.nuevo_presupuesto(db, estado="enviado", items=[_item(r, "3")])
    assert _aprobar(db, p.presupuesto_id).efecto_en_orden == "esperando_repuestos"

    sin_stock = api.post(f"/inventario/ordenes/{p.orden_id}/reserva", headers=MECANICO).json()
    assert sin_stock["reservado"] is False and sin_stock["movimientos"] == []
    assert sin_stock["faltantes"] == [{"repuesto_id": r.repuesto_id, "nombre": r.nombre,
                                       "solicitado": 3, "disponible": 1, "faltan": 2}]

    fabricas.nuevo_movimiento(db, r, tipo="ingreso", cantidad=5)
    r.stock = 6
    db.flush()
    con_stock = api.post(f"/inventario/ordenes/{p.orden_id}/reserva", headers=MECANICO).json()
    assert con_stock["reservado"] is True
    assert [(m["tipo"], m["cantidad"]) for m in con_stock["movimientos"]] == [("compromiso", 3)]

    # Reintentar otra vez no reserva de más.
    otra_vez = api.post(f"/inventario/ordenes/{p.orden_id}/reserva", headers=MECANICO).json()
    assert otra_vez["reservado"] is True and otra_vez["movimientos"] == []
    assert _reservado(db, r, p.orden_id) == 3


def test_reserva_de_orden_sin_presupuesto_aprobado(api: TestClient, db: Session) -> None:
    p = fabricas.nuevo_presupuesto(db, estado="enviado")
    assert api.post(f"/inventario/ordenes/{p.orden_id}/reserva", headers=MECANICO).status_code == 409
    assert api.post(f"/inventario/ordenes/{fabricas.nuevo_orden_id()}/reserva",
                    headers=MECANICO).status_code == 404


def test_modificacion_aprobada_ajusta_la_reserva(db: Session) -> None:
    sube = fabricas.nuevo_repuesto(db, stock=10)
    baja = fabricas.nuevo_repuesto(db, stock=10)
    p = fabricas.nuevo_presupuesto(db, estado="enviado", items=[_item(sube, "2"), _item(baja, "5")])
    _aprobar(db, p.presupuesto_id)

    v2 = fabricas.nueva_version_siguiente(db, p, items=[_item(sube, "6"), _item(baja, "1")])
    fabricas.enviar(db, v2)
    resultado = _aprobar(db, p.presupuesto_id, 2)

    assert resultado.repuestos_reservados == {sube.repuesto_id: 6, baja.repuesto_id: 1}
    assert (_reservado(db, sube, p.orden_id), _reservado(db, baja, p.orden_id)) == (6, 1)
    tipos = [(m.repuesto_id, m.tipo, m.cantidad) for m in db.scalars(
        select(MovimientoInventario).where(MovimientoInventario.orden_id == p.orden_id)
        .order_by(MovimientoInventario.movimiento_id))]
    assert tipos[-2:] == [(sube.repuesto_id, "compromiso", 4), (baja.repuesto_id, "liberacion", 4)]


def test_la_reserva_descuenta_lo_ya_consumido(db: Session) -> None:
    r = fabricas.nuevo_repuesto(db, stock=10)
    p = fabricas.nuevo_presupuesto(db, estado="enviado", items=[_item(r, "4")])
    _aprobar(db, p.presupuesto_id)
    fabricas.nuevo_movimiento(db, r, tipo="consumo", cantidad=3, orden_id=p.orden_id)
    r.stock = 7
    db.flush()

    # Una modificación pide 5 en total: ya usó 3, faltan 2 por reservar (tenía 1).
    v2 = fabricas.nueva_version_siguiente(db, p, items=[_item(r, "5")])
    fabricas.enviar(db, v2)
    assert _aprobar(db, p.presupuesto_id, 2).repuestos_reservados == {r.repuesto_id: 2}
    assert _reservado(db, r, p.orden_id) == 2


def test_rechazar_no_reserva(db: Session) -> None:
    r = fabricas.nuevo_repuesto(db, stock=10)
    p = fabricas.nuevo_presupuesto(db, estado="enviado", items=[_item(r, "2")])
    casos_presupuestos.decidir_version(
        UnidadDeTrabajo(db), presupuesto_id=p.presupuesto_id, numero=1,
        cliente_usuario_id=datos.CLIENTE_ID, decision="rechazado", motivo="Caro",
        confirmar_cancelacion=True)
    assert _reservado(db, r, p.orden_id) == 0


# ================================================================ descuento ==

def _consumir(api: TestClient, orden_id: int, items: list[tuple[int, int]], clave: str | None = None):
    return api.post(f"/inventario/ordenes/{orden_id}/consumos", headers=MECANICO, json={
        "clave_operacion": clave or _clave(),
        "items": [{"repuesto_id": rid, "cantidad": n} for rid, n in items]})


def test_descontar_usa_primero_lo_reservado(api: TestClient, db: Session) -> None:
    r = fabricas.nuevo_repuesto(db, stock=6)
    p = fabricas.nuevo_presupuesto(db, estado="enviado", items=[_item(r, "4")])
    _aprobar(db, p.presupuesto_id)

    res = _consumir(api, p.orden_id, [(r.repuesto_id, 3)])
    assert res.status_code == 201, res.text
    db.expire_all()
    assert db.get(Repuesto, r.repuesto_id).stock == 3
    assert _reservado(db, r, p.orden_id) == 1  # le queda 1 reservada


def test_descontar_varios_repuestos_es_todo_o_nada(api: TestClient, db: Session) -> None:
    alcanza = fabricas.nuevo_repuesto(db, stock=5)
    no_alcanza = fabricas.nuevo_repuesto(db, stock=1)
    orden = fabricas.nuevo_orden_id()
    # Fija los datos de la prueba: el rechazo hace rollback de la petición.
    db.commit()

    r = _consumir(api, orden, [(alcanza.repuesto_id, 2), (no_alcanza.repuesto_id, 3)])

    assert r.status_code == 409
    assert r.json()["faltantes"] == [{"repuesto_id": no_alcanza.repuesto_id, "nombre": no_alcanza.nombre,
                                      "solicitado": 3, "disponible": 1, "faltan": 2}]
    db.expire_all()
    assert (db.get(Repuesto, alcanza.repuesto_id).stock, db.get(Repuesto, no_alcanza.repuesto_id).stock) \
        == (5, 1)
    assert db.scalars(select(MovimientoInventario).where(MovimientoInventario.orden_id == orden)).all() == []


def test_descontar_no_toma_lo_reservado_por_otra_orden(api: TestClient, db: Session) -> None:
    r = fabricas.nuevo_repuesto(db, stock=5)
    fabricas.nuevo_movimiento(db, r, tipo="compromiso", cantidad=4, orden_id=fabricas.nuevo_orden_id())

    rechazo = _consumir(api, fabricas.nuevo_orden_id(), [(r.repuesto_id, 2)])
    assert rechazo.status_code == 409
    assert rechazo.json()["faltantes"][0] | {"nombre": None} == {
        "repuesto_id": r.repuesto_id, "nombre": None, "solicitado": 2, "disponible": 1, "faltan": 1}


def test_misma_clave_no_descuenta_dos_veces(api: TestClient, db: Session) -> None:
    r = fabricas.nuevo_repuesto(db, stock=5)
    orden, clave = fabricas.nuevo_orden_id(), _clave()

    primera = _consumir(api, orden, [(r.repuesto_id, 2)], clave)
    segunda = _consumir(api, orden, [(r.repuesto_id, 2)], clave)
    assert (primera.status_code, segunda.status_code) == (201, 200)
    assert segunda.json()["repetido"] is True
    db.expire_all()
    assert db.get(Repuesto, r.repuesto_id).stock == 3
    assert _consumir(api, orden, [(r.repuesto_id, 1)], clave).status_code == 409  # otros datos


def test_descontar_repuesto_inexistente_es_404(api: TestClient) -> None:
    assert _consumir(api, 5, [(999_999_994, 1)]).status_code == 404


def test_el_movimiento_individual_tambien_informa_faltantes(api: TestClient, db: Session) -> None:
    r = fabricas.nuevo_repuesto(db, stock=1)
    res = api.post("/inventario/movimientos", headers=MECANICO, json={
        "clave_operacion": _clave(), "repuesto_id": r.repuesto_id, "tipo": "compromiso",
        "cantidad": 3, "orden_id": 8})
    assert res.status_code == 409
    assert res.json()["faltantes"][0]["faltan"] == 2


# =============================================================== liberación ==

def test_liberar_la_orden_devuelve_todo_lo_reservado(api: TestClient, db: Session) -> None:
    a = fabricas.nuevo_repuesto(db, stock=5)
    b = fabricas.nuevo_repuesto(db, stock=5)
    p = fabricas.nuevo_presupuesto(db, estado="enviado", items=[_item(a, "2"), _item(b, "3")])
    _aprobar(db, p.presupuesto_id)
    clave = _clave()

    r = api.post(f"/inventario/ordenes/{p.orden_id}/liberacion", headers=MECANICO,
                 json={"clave_operacion": clave})
    assert r.status_code == 200
    assert sorted((m["repuesto_id"], m["tipo"], m["cantidad"]) for m in r.json()["movimientos"]) == \
        sorted([(a.repuesto_id, "liberacion", 2), (b.repuesto_id, "liberacion", 3)])
    assert (_reservado(db, a, p.orden_id), _reservado(db, b, p.orden_id)) == (0, 0)

    otra_vez = api.post(f"/inventario/ordenes/{p.orden_id}/liberacion", headers=MECANICO,
                        json={"clave_operacion": clave}).json()
    assert otra_vez["repetido"] is True


def test_liberar_una_orden_sin_reservas_no_hace_nada(api: TestClient) -> None:
    r = api.post(f"/inventario/ordenes/{fabricas.nuevo_orden_id()}/liberacion", headers=MECANICO,
                 json={"clave_operacion": _clave()})
    assert r.status_code == 200 and r.json()["movimientos"] == []


# ==================================== saldo de reservas en orden cronológico ==

def test_consumir_sin_reserva_no_se_come_una_reserva_posterior(db: Session) -> None:
    """Antes: consumir 2 sin reserva y después reservar 3 dejaba 1 reservada."""
    r = fabricas.nuevo_repuesto(db, stock=10)
    orden = fabricas.nuevo_orden_id()
    fabricas.nuevo_movimiento(db, r, tipo="consumo", cantidad=2, orden_id=orden)
    fabricas.nuevo_movimiento(db, r, tipo="compromiso", cantidad=3, orden_id=orden)
    assert _reservado(db, r, orden) == 3
