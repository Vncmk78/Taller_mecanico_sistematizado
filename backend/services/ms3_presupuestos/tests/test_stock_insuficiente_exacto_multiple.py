"""Pruebas de stock insuficiente, stock exacto y consumo de múltiples unidades (§4.6).

Para cada forma de usar stock se prueba el LÍMITE:
- stock exacto  → se acepta y deja el stock (o lo disponible) en 0;
- una unidad más → 409 con `faltantes` (faltan = 1) y no cambia nada.

Y el consumo de varias unidades: en un solo movimiento, en varios pasos hasta
agotar, repartido entre lo reservado y lo libre, y varios repuestos a la vez
(también en paralelo y en orden cruzado, sin interbloqueos).
"""
from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Iterator
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from services.ms3_presupuestos import datos_prueba as datos
from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import get_db
from services.ms3_presupuestos.main import app
from services.ms3_presupuestos.models import ItemPresupuesto, MovimientoInventario, Repuesto
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo
from services.ms3_presupuestos.persistencia.repositorios import RepositorioMovimientos
from services.ms3_presupuestos.services import presupuestos as casos_presupuestos
from services.ms3_presupuestos.services import reservas
from services.ms3_presupuestos.services.inventario import StockInsuficiente
from services.ms3_presupuestos.tests import fabricas
from services.ms3_presupuestos.tests.test_rollback_consistencia import (  # noqa: F401
    esquema_aislado,
)
from shared.auth import NombreRol, crear_token_acceso


def _cabecera(rol: NombreRol, usuario_id: int) -> dict[str, str]:
    return {"Authorization": "Bearer " + crear_token_acceso(
        usuario_id=usuario_id, roles=[rol],
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(), algoritmo="HS256")}


ADMIN = _cabecera(NombreRol.ADMINISTRADOR, datos.ADMIN_ID)
MECANICO = _cabecera(NombreRol.MECANICO, datos.MECANICO_ID)


@pytest.fixture
def api(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as cliente:
            yield cliente
    finally:
        app.dependency_overrides.pop(get_db, None)


def _clave() -> str:
    return f"limite-{uuid.uuid4().hex[:16]}"


def _movimiento(api: TestClient, rid: int, tipo: str, cantidad: int, orden_id: int | None = None):
    cuerpo = {"clave_operacion": _clave(), "repuesto_id": rid, "tipo": tipo, "cantidad": cantidad}
    if orden_id is not None:
        cuerpo["orden_id"] = orden_id
    return api.post("/inventario/movimientos", json=cuerpo,
                    headers=ADMIN if tipo in ("ingreso", "ajuste") else MECANICO)


def _consumir(api: TestClient, orden_id: int, items: list[tuple[int, int]]):
    return api.post(f"/inventario/ordenes/{orden_id}/consumos", headers=MECANICO, json={
        "clave_operacion": _clave(), "items": [{"repuesto_id": r, "cantidad": n} for r, n in items]})


def _stock(db: Session, rid: int) -> int:
    db.expire_all()
    return db.get(Repuesto, rid).stock


def _movimientos(db: Session, rid: int) -> int:
    return len(db.scalars(select(MovimientoInventario).where(MovimientoInventario.repuesto_id == rid)).all())


def _reservado(db: Session, rid: int, orden_id: int) -> int:
    return RepositorioMovimientos(db).comprometido_por_orden(rid).get(orden_id, 0)


def _item(repuesto: Repuesto, cantidad: str) -> ItemPresupuesto:
    return ItemPresupuesto(tipo="repuesto", descripcion=repuesto.nombre, cantidad=Decimal(cantidad),
                           precio_unitario=Decimal("1000"), repuesto=repuesto)


# ============================================================ stock exacto ==

@pytest.mark.parametrize("stock", [1, 7, 250])
def test_consumir_exactamente_todo_el_stock(api: TestClient, db: Session, stock: int) -> None:
    rid = fabricas.nuevo_repuesto(db, stock=stock).repuesto_id
    r = _movimiento(api, rid, "consumo", stock, fabricas.nuevo_orden_id())
    assert r.status_code == 201, r.text
    assert r.json()["stock"]["stock"] == 0 and r.json()["stock"]["disponible"] == 0
    assert _stock(db, rid) == 0


def test_reservar_exactamente_lo_disponible(api: TestClient, db: Session) -> None:
    rid = fabricas.nuevo_repuesto(db, stock=5).repuesto_id
    r = _movimiento(api, rid, "compromiso", 5, fabricas.nuevo_orden_id())
    assert r.status_code == 201
    assert (r.json()["stock"]["stock"], r.json()["stock"]["disponible"]) == (5, 0)


def test_ajuste_que_deja_el_stock_exactamente_en_cero(api: TestClient, db: Session) -> None:
    rid = fabricas.nuevo_repuesto(db, stock=3).repuesto_id
    assert _movimiento(api, rid, "ajuste", -3).status_code == 201
    assert _stock(db, rid) == 0


def test_usar_exactamente_lo_libre_cuando_otra_orden_reservo(api: TestClient, db: Session) -> None:
    r = fabricas.nuevo_repuesto(db, stock=10)
    fabricas.nuevo_movimiento(db, r, tipo="compromiso", cantidad=4, orden_id=fabricas.nuevo_orden_id())
    res = _movimiento(api, r.repuesto_id, "consumo", 6, fabricas.nuevo_orden_id())
    assert res.status_code == 201
    assert (res.json()["stock"]["stock"], res.json()["stock"]["comprometido"]) == (4, 4)


def test_aprobar_con_stock_exacto_reserva_todo(db: Session) -> None:
    r = fabricas.nuevo_repuesto(db, stock=3)
    p = fabricas.nuevo_presupuesto(db, estado="enviado", items=[_item(r, "3")])
    resultado = casos_presupuestos.decidir_version(
        UnidadDeTrabajo(db), presupuesto_id=p.presupuesto_id, numero=1,
        cliente_usuario_id=datos.CLIENTE_ID, decision="aprobado", motivo=None,
        confirmar_cancelacion=False)
    assert resultado.efecto_en_orden == "en_reparacion"
    assert _reservado(db, r.repuesto_id, p.orden_id) == 3


def test_validar_stock_exacto_alcanza(api: TestClient, db: Session) -> None:
    rid = fabricas.nuevo_repuesto(db, stock=4).repuesto_id
    d = api.post("/inventario/disponibilidad", headers=MECANICO,
                 json={"items": [{"repuesto_id": rid, "cantidad": 4}]}).json()["repuestos"][0]
    assert (d["alcanza"], d["faltan"]) == (True, 0)


def test_llegar_a_cero_activa_la_alerta(api: TestClient, db: Session) -> None:
    rid = fabricas.nuevo_repuesto(db, stock=2, umbral_particular=1).repuesto_id
    alerta = _movimiento(api, rid, "consumo", 2, fabricas.nuevo_orden_id()).json()["alerta"]
    assert alerta == {"activa": True, "nueva": True}


# ===================================================== stock insuficiente ==
# Una unidad más que el límite: 409, faltan = 1 y nada cambia. Los datos se
# fijan con commit porque el rechazo hace rollback de la petición.

@pytest.mark.parametrize(("tipo", "stock", "cantidad"), [
    ("consumo", 5, 6),
    ("compromiso", 5, 6),
    ("ajuste", 5, -6),
])
def test_una_unidad_mas_que_el_stock_se_rechaza(
    api: TestClient, db: Session, tipo: str, stock: int, cantidad: int
) -> None:
    rid = fabricas.nuevo_repuesto(db, stock=stock).repuesto_id
    db.commit()
    antes = _movimientos(db, rid)
    r = _movimiento(api, rid, tipo, cantidad, None if tipo == "ajuste" else fabricas.nuevo_orden_id())
    assert r.status_code == 409
    assert r.json()["faltantes"][0]["faltan"] == 1
    assert _stock(db, rid) == stock and _movimientos(db, rid) == antes


def test_sin_stock_se_rechaza_cualquier_uso(api: TestClient, db: Session) -> None:
    rid = fabricas.nuevo_repuesto(db, stock=0).repuesto_id
    db.commit()
    for tipo in ("consumo", "compromiso"):
        r = _movimiento(api, rid, tipo, 1, fabricas.nuevo_orden_id())
        assert r.status_code == 409
        assert r.json()["faltantes"][0] | {"nombre": None, "repuesto_id": None} == {
            "repuesto_id": None, "nombre": None, "solicitado": 1, "disponible": 0, "faltan": 1}


def test_una_unidad_mas_que_lo_libre_cuando_otra_orden_reservo(api: TestClient, db: Session) -> None:
    r = fabricas.nuevo_repuesto(db, stock=10)
    fabricas.nuevo_movimiento(db, r, tipo="compromiso", cantidad=4, orden_id=fabricas.nuevo_orden_id())
    db.commit()
    res = _movimiento(api, r.repuesto_id, "consumo", 7, fabricas.nuevo_orden_id())
    assert res.status_code == 409 and res.json()["faltantes"][0]["disponible"] == 6
    assert _stock(db, r.repuesto_id) == 10


def test_aprobar_con_una_unidad_menos_no_reserva(db: Session) -> None:
    r = fabricas.nuevo_repuesto(db, stock=2)
    p = fabricas.nuevo_presupuesto(db, estado="enviado", items=[_item(r, "3")])
    resultado = casos_presupuestos.decidir_version(
        UnidadDeTrabajo(db), presupuesto_id=p.presupuesto_id, numero=1,
        cliente_usuario_id=datos.CLIENTE_ID, decision="aprobado", motivo=None,
        confirmar_cancelacion=False)
    assert resultado.efecto_en_orden == "esperando_repuestos"
    assert [(f.requerido, f.disponible) for f in resultado.repuestos_faltantes] == [(Decimal("3.00"), 2)]
    assert _reservado(db, r.repuesto_id, p.orden_id) == 0


def test_validar_una_unidad_de_mas_no_alcanza(api: TestClient, db: Session) -> None:
    rid = fabricas.nuevo_repuesto(db, stock=4).repuesto_id
    d = api.post("/inventario/disponibilidad", headers=MECANICO,
                 json={"items": [{"repuesto_id": rid, "cantidad": 5}]}).json()["repuestos"][0]
    assert (d["alcanza"], d["faltan"]) == (False, 1)


# ================================================= consumo de varias unidades ==

def test_un_consumo_de_varias_unidades_es_un_solo_movimiento(api: TestClient, db: Session) -> None:
    rid = fabricas.nuevo_repuesto(db, stock=20).repuesto_id
    antes = _movimientos(db, rid)
    r = _movimiento(api, rid, "consumo", 12, fabricas.nuevo_orden_id())
    assert r.json()["movimiento"]["cantidad"] == 12
    assert _stock(db, rid) == 8 and _movimientos(db, rid) == antes + 1


def test_consumir_en_varios_pasos_hasta_agotar_y_el_siguiente_se_rechaza(
    api: TestClient, db: Session
) -> None:
    rid = fabricas.nuevo_repuesto(db, stock=10).repuesto_id
    orden = fabricas.nuevo_orden_id()
    for cantidad, queda in [(3, 7), (4, 3), (3, 0)]:
        r = _movimiento(api, rid, "consumo", cantidad, orden)
        assert r.status_code == 201 and r.json()["stock"]["stock"] == queda
    db.commit()
    assert _movimiento(api, rid, "consumo", 1, orden).status_code == 409
    assert _stock(db, rid) == 0


def test_consumo_que_combina_lo_reservado_y_lo_libre(api: TestClient, db: Session) -> None:
    """Reservó 2; hay 3 libres → puede consumir 5 de una vez, no 6."""
    r = fabricas.nuevo_repuesto(db, stock=7)
    orden, otra = fabricas.nuevo_orden_id(), fabricas.nuevo_orden_id()
    fabricas.nuevo_movimiento(db, r, tipo="compromiso", cantidad=2, orden_id=orden)
    fabricas.nuevo_movimiento(db, r, tipo="compromiso", cantidad=2, orden_id=otra)
    db.commit()

    assert _movimiento(api, r.repuesto_id, "consumo", 6, orden).status_code == 409
    ok = _movimiento(api, r.repuesto_id, "consumo", 5, orden)
    assert ok.status_code == 201
    stock = ok.json()["stock"]
    # Quedan las 2 de la otra orden; la orden ya no tiene reserva.
    assert (stock["stock"], stock["comprometido"], stock["compromisos"]) == (
        2, 2, [{"orden_id": otra, "comprometido": 2}])


def test_descontar_varios_repuestos_con_varias_unidades(api: TestClient, db: Session) -> None:
    a = fabricas.nuevo_repuesto(db, stock=10)
    b = fabricas.nuevo_repuesto(db, stock=4)
    c = fabricas.nuevo_repuesto(db, stock=1)
    orden = fabricas.nuevo_orden_id()

    r = _consumir(api, orden, [(a.repuesto_id, 6), (b.repuesto_id, 4), (c.repuesto_id, 1)])

    assert r.status_code == 201, r.text
    assert sorted((m["repuesto_id"], m["cantidad"]) for m in r.json()["movimientos"]) == sorted(
        [(a.repuesto_id, 6), (b.repuesto_id, 4), (c.repuesto_id, 1)])
    assert (_stock(db, a.repuesto_id), _stock(db, b.repuesto_id), _stock(db, c.repuesto_id)) == (4, 0, 0)


def test_el_mismo_repuesto_dos_veces_en_un_descuento_se_suma(api: TestClient, db: Session) -> None:
    r = fabricas.nuevo_repuesto(db, stock=5)
    db.commit()
    assert _consumir(api, fabricas.nuevo_orden_id(), [(r.repuesto_id, 3), (r.repuesto_id, 3)]
                     ).status_code == 409
    res = _consumir(api, fabricas.nuevo_orden_id(), [(r.repuesto_id, 2), (r.repuesto_id, 3)])
    assert res.status_code == 201 and [m["cantidad"] for m in res.json()["movimientos"]] == [5]
    assert _stock(db, r.repuesto_id) == 0


def test_descuento_multiple_con_un_repuesto_justo_y_otro_de_mas(api: TestClient, db: Session) -> None:
    justo = fabricas.nuevo_repuesto(db, stock=3)
    de_mas = fabricas.nuevo_repuesto(db, stock=3)
    db.commit()
    r = _consumir(api, fabricas.nuevo_orden_id(), [(justo.repuesto_id, 3), (de_mas.repuesto_id, 4)])
    assert r.status_code == 409
    assert [(f["repuesto_id"], f["faltan"]) for f in r.json()["faltantes"]] == [(de_mas.repuesto_id, 1)]
    assert (_stock(db, justo.repuesto_id), _stock(db, de_mas.repuesto_id)) == (3, 3)


# ================================================== concurrencia real (§4.6) ==

def _repuestos_reales(fabrica: sessionmaker[Session], *stocks: int) -> list[int]:
    with fabrica() as sesion:
        ids = [fabricas.nuevo_repuesto(sesion, stock=s).repuesto_id for s in stocks]
        sesion.commit()
        return ids


def _a_la_vez(fabrica: sessionmaker[Session], operaciones: list[Callable[[UnidadDeTrabajo], Any]]
              ) -> list[Any]:
    resultados: list[Any] = [None] * len(operaciones)
    listas = threading.Barrier(len(operaciones))

    def correr(i: int, operacion: Callable[[UnidadDeTrabajo], Any]) -> None:
        with fabrica() as sesion:
            listas.wait()
            try:
                resultados[i] = operacion(UnidadDeTrabajo(sesion))
            except Exception as exc:  # noqa: BLE001
                resultados[i] = exc

    hilos = [threading.Thread(target=correr, args=(i, op)) for i, op in enumerate(operaciones)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)
    return resultados


def _descontar(orden_id: int, items: dict[int, int]):
    return lambda uow: reservas.consumir_para_orden(
        uow, orden_id, items, usuario_id=datos.MECANICO_ID, clave_operacion=_clave())


def test_dos_descuentos_del_stock_exacto_a_la_vez_solo_pasa_uno(esquema_aislado) -> None:  # noqa: F811
    a, b = _repuestos_reales(esquema_aislado, 3, 2)
    resultados = _a_la_vez(esquema_aislado, [
        _descontar(fabricas.nuevo_orden_id(), {a: 3, b: 2}),
        _descontar(fabricas.nuevo_orden_id(), {a: 3, b: 2}),
    ])
    errores = [r for r in resultados if isinstance(r, Exception)]
    assert len(errores) == 1 and isinstance(errores[0], StockInsuficiente), resultados
    with esquema_aislado() as sesion:
        assert (sesion.get(Repuesto, a).stock, sesion.get(Repuesto, b).stock) == (0, 0)


def test_descuentos_cruzados_no_se_bloquean_entre_si(esquema_aislado) -> None:  # noqa: F811
    """[A, B] y [B, A] a la vez: se bloquean en el mismo orden (por id), sin deadlock."""
    a, b = _repuestos_reales(esquema_aislado, 10, 10)
    resultados = _a_la_vez(esquema_aislado, [
        _descontar(fabricas.nuevo_orden_id(), {a: 2, b: 3}),
        _descontar(fabricas.nuevo_orden_id(), {b: 4, a: 1}),
        _descontar(fabricas.nuevo_orden_id(), {a: 1, b: 1}),
    ])
    assert not any(isinstance(r, Exception) for r in resultados), resultados
    with esquema_aislado() as sesion:
        assert (sesion.get(Repuesto, a).stock, sesion.get(Repuesto, b).stock) == (6, 2)
