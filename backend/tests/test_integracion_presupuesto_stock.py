"""Integración presupuesto aprobado → validación de stock (SCRUM-529).

Flujo HTTP real entre MS3 (presupuestos e inventario) y MS2 (órdenes), cada uno
con su base, usando el mismo arnés que las pruebas de decisiones
(`preparar_flujo`): la orden está en "Esperando aprobación de presupuesto" y su
presupuesto pide 2 unidades de un repuesto.

Se comprueba de punta a punta que lo que decide el cliente y lo que hay en
bodega quedan consistentes en los dos servicios:

    aprobar con stock      → MS2 "En reparación" (5) y MS3 reserva las 2 unidades
    aprobar sin stock      → MS2 "Esperando repuestos" (4) y MS3 no reserva nada
    llega stock            → MS3 reserva al reintentar; la orden ya puede seguir
    usar los repuestos     → se descuenta lo reservado; otra orden no puede tomarlo
    rechazar               → MS2 "Cancelado" (8) y el stock queda intacto
    modificar lo aprobado  → la reserva se ajusta a la nueva versión aprobada
    reintentos             → no reservan dos veces

Corre con SQLite siempre y, si están las variables SCRUM397438_MS2_TEST_URL /
SCRUM397438_MS3_TEST_URL, también con PostgreSQL real (triggers y bloqueos).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text

from services.ms2_taller.models.estado_orden import (
    CANCELADO,
    EN_REPARACION,
    ESPERANDO_APROBACION_PRESUPUESTO,
    ESPERANDO_REPUESTOS,
)
from services.ms3_presupuestos.models import MovimientoInventario, Repuesto
from shared.auth import NombreRol
from test_decisiones_presupuesto_integracion import (  # noqa: F401  (fixture)
    _decidir,
    _estado_y_historial,
    _headers,
    flujo,
)
from test_decisiones_presupuesto_postgresql import bases_pg, flujo_pg  # noqa: F401  (fixtures)

ADMIN = _headers(99, NombreRol.ADMINISTRADOR)
MECANICO = _headers(77, NombreRol.MECANICO)
REQUERIDO = 2  # unidades del repuesto en el presupuesto de la fixture


# En PostgreSQL, aprobar bloquea la versión con un trigger de 0003_ms3 y así queda
# vigente. SQLite no tiene esos triggers: se replica solo ese efecto.
_TRIGGER_APROBACION_SQLITE = """
CREATE TRIGGER IF NOT EXISTS trg_prueba_bloquear_aprobada AFTER INSERT ON decision_presupuesto
WHEN NEW.decision = 'aprobado'
BEGIN
    UPDATE version_presupuesto SET bloqueada_en = CURRENT_TIMESTAMP
    WHERE version_id = NEW.version_id;
END
"""


@pytest.fixture(params=["sqlite", "postgresql"])
def entorno(request):
    if request.param == "postgresql":
        return request.getfixturevalue("flujo_pg")
    entorno = request.getfixturevalue("flujo")
    with entorno.db3() as db:
        db.execute(text(_TRIGGER_APROBACION_SQLITE))
        db.commit()
    return entorno


def _stock(entorno) -> int:
    with entorno.db3() as db:
        return db.get(Repuesto, entorno.repuesto_id).stock


def _movimientos(entorno) -> list[tuple[str, int, int | None]]:
    with entorno.db3() as db:
        return [(m.tipo, m.cantidad, m.orden_id) for m in db.scalars(
            select(MovimientoInventario).where(MovimientoInventario.repuesto_id == entorno.repuesto_id)
            .order_by(MovimientoInventario.movimiento_id))]


def _disponibilidad(entorno) -> dict:
    r = entorno.ms3.get(f"/inventario/ordenes/{entorno.orden_id}/disponibilidad", headers=MECANICO)
    assert r.status_code == 200, r.text
    return r.json()


def _ingreso(entorno, cantidad: int) -> None:
    r = entorno.ms3.post("/inventario/movimientos", headers=ADMIN, json={
        "clave_operacion": f"ingreso-{uuid.uuid4().hex}", "repuesto_id": entorno.repuesto_id,
        "tipo": "ingreso", "cantidad": cantidad})
    assert r.status_code == 201, r.text


def _consumir(entorno, orden_id: int, cantidad: int):
    return entorno.ms3.post(f"/inventario/ordenes/{orden_id}/consumos", headers=MECANICO, json={
        "clave_operacion": f"uso-{uuid.uuid4().hex[:20]}",
        "items": [{"repuesto_id": entorno.repuesto_id, "cantidad": cantidad}]})


# ===================================================== aprobación con stock ==

def test_aprobar_con_stock_pone_la_orden_en_reparacion_y_reserva(entorno) -> None:
    r = _decidir(entorno, "aprobado", stock=10)

    assert r.status_code == 201, r.text
    assert r.json()["efecto_en_orden"] == "en_reparacion"
    assert r.json()["repuestos_reservados"] == {str(entorno.repuesto_id): REQUERIDO}
    assert _estado_y_historial(entorno)[0] == EN_REPARACION
    assert _movimientos(entorno) == [("compromiso", REQUERIDO, entorno.orden_id)]
    assert _stock(entorno) == 10  # reservar no descuenta el stock físico

    d = _disponibilidad(entorno)
    assert d["disponible"] is True and d["presupuesto_id"] == entorno.presupuesto_id
    assert (d["repuestos"][0]["requerido"], d["repuestos"][0]["reservado_para_orden"]) == (2, 2)


def test_aprobar_con_el_stock_exacto(entorno) -> None:
    r = _decidir(entorno, "aprobado", stock=REQUERIDO)
    assert r.json()["efecto_en_orden"] == "en_reparacion"
    assert _estado_y_historial(entorno)[0] == EN_REPARACION

    # Todo lo que hay quedó para esta orden: otra no puede tomarlo.
    otra = _consumir(entorno, entorno.orden_id + 1000, 1)
    assert otra.status_code == 409
    assert otra.json()["faltantes"][0]["disponible"] == 0


def test_usar_los_repuestos_aprobados_descuenta_lo_reservado(entorno) -> None:
    _decidir(entorno, "aprobado", stock=5)

    r = _consumir(entorno, entorno.orden_id, REQUERIDO)

    assert r.status_code == 201, r.text
    assert _stock(entorno) == 3
    d = _disponibilidad(entorno)
    assert d["disponible"] is True and d["repuestos"][0]["requerido"] == 0  # ya no falta nada
    assert d["repuestos"][0]["reservado_para_orden"] == 0


# ===================================================== aprobación sin stock ==

def test_aprobar_sin_stock_deja_la_orden_esperando_repuestos_sin_reservar(entorno) -> None:
    r = _decidir(entorno, "aprobado", stock=1)

    assert r.status_code == 201, r.text
    assert r.json()["efecto_en_orden"] == "esperando_repuestos"
    assert r.json()["repuestos_reservados"] == {}
    assert [(f["repuesto_id"], f["disponible"]) for f in r.json()["repuestos_faltantes"]] == [
        (entorno.repuesto_id, 1)]
    assert _estado_y_historial(entorno)[0] == ESPERANDO_REPUESTOS
    assert _movimientos(entorno) == []

    d = _disponibilidad(entorno)
    assert d["disponible"] is False and d["repuestos"][0]["faltan"] == 1


def test_cuando_llega_stock_la_reserva_se_completa(entorno) -> None:
    _decidir(entorno, "aprobado", stock=0)
    assert _estado_y_historial(entorno)[0] == ESPERANDO_REPUESTOS

    sin = entorno.ms3.post(f"/inventario/ordenes/{entorno.orden_id}/reserva", headers=MECANICO).json()
    assert sin["reservado"] is False and sin["faltantes"][0]["faltan"] == REQUERIDO

    _ingreso(entorno, 3)
    con = entorno.ms3.post(f"/inventario/ordenes/{entorno.orden_id}/reserva", headers=MECANICO).json()
    assert con["reservado"] is True
    assert _disponibilidad(entorno)["disponible"] is True
    # MS3 no mueve la orden a "En reparación": ese evento es de MS2 (pendiente de contrato).
    assert _estado_y_historial(entorno)[0] == ESPERANDO_REPUESTOS


def test_otra_orden_que_reservo_antes_deja_a_esta_esperando(entorno) -> None:
    with entorno.db3() as db:
        db.get(Repuesto, entorno.repuesto_id).stock = 3
        db.add(MovimientoInventario(clave_operacion=f"otra-{uuid.uuid4().hex}",
                                    repuesto_id=entorno.repuesto_id, tipo="compromiso",
                                    cantidad=2, orden_id=entorno.orden_id + 500,
                                    registrado_por_id=77))
        db.commit()
    body = {"decision": "aprobado"}
    r = entorno.ms3.post(f"/presupuestos/{entorno.presupuesto_id}/versiones/1/decision",
                         json=body, headers=_headers())
    assert r.status_code == 201, r.text
    assert r.json()["efecto_en_orden"] == "esperando_repuestos"
    assert r.json()["repuestos_faltantes"][0]["disponible"] == 1
    assert _estado_y_historial(entorno)[0] == ESPERANDO_REPUESTOS


# ==================================================================== rechazo ==

def test_rechazar_cancela_la_orden_y_no_toca_el_stock(entorno) -> None:
    r = _decidir(entorno, "rechazado", stock=10)
    assert r.status_code == 201, r.text
    assert _estado_y_historial(entorno)[0] == CANCELADO
    assert _movimientos(entorno) == [] and _stock(entorno) == 10
    assert entorno.ms3.get(f"/inventario/ordenes/{entorno.orden_id}/disponibilidad",
                           headers=MECANICO).status_code == 409


# ==================================================== modificación aprobada ==

def _modificar_y_aprobar(entorno, cantidad: int):
    items = [{"tipo": "repuesto", "descripcion": "Repuesto", "cantidad": str(cantidad),
              "precio_unitario": "10", "repuesto_id": entorno.repuesto_id}]
    r = entorno.ms3.post(f"/presupuestos/{entorno.presupuesto_id}/modificacion",
                         headers=ADMIN, json={"items": items})
    assert r.status_code == 201, r.text
    assert entorno.ms3.post(f"/presupuestos/{entorno.presupuesto_id}/versiones/2/envio",
                            headers=ADMIN).status_code == 200
    return entorno.ms3.post(f"/presupuestos/{entorno.presupuesto_id}/versiones/2/decision",
                            json={"decision": "aprobado"}, headers=_headers())


def test_modificacion_aprobada_ajusta_la_reserva(entorno) -> None:
    _decidir(entorno, "aprobado", stock=10)

    r = _modificar_y_aprobar(entorno, 5)

    assert r.status_code == 201, r.text
    assert r.json()["repuestos_reservados"] == {str(entorno.repuesto_id): 5}
    assert _movimientos(entorno) == [("compromiso", 2, entorno.orden_id),
                                     ("compromiso", 3, entorno.orden_id)]
    # La modificación no reaplica la transición inicial: la orden sigue en reparación.
    assert _estado_y_historial(entorno)[0] == EN_REPARACION
    assert _disponibilidad(entorno)["version"] == 2


def test_modificacion_sin_stock_conserva_la_reserva_anterior(entorno) -> None:
    _decidir(entorno, "aprobado", stock=3)

    r = _modificar_y_aprobar(entorno, 6)

    assert r.status_code == 201, r.text
    assert r.json()["repuestos_reservados"] == {}
    assert r.json()["repuestos_faltantes"][0]["disponible"] == 3
    assert _movimientos(entorno) == [("compromiso", 2, entorno.orden_id)]
    d = _disponibilidad(entorno)
    assert (d["disponible"], d["repuestos"][0]["faltan"]) == (False, 3)


# ================================================================ reintentos ==

def test_reintentar_la_aplicacion_no_reserva_dos_veces(entorno) -> None:
    entorno.fallo["modo"] = "antes"  # MS2 no responde al aplicar
    r = _decidir(entorno, "aprobado", stock=10)
    assert r.status_code == 503
    assert _estado_y_historial(entorno)[0] == ESPERANDO_APROBACION_PRESUPUESTO
    # La decisión y su reserva ya quedaron guardadas juntas en MS3.
    assert _movimientos(entorno) == [("compromiso", 2, entorno.orden_id)]

    entorno.fallo["modo"] = None
    reintento = entorno.ms3.post(f"/presupuestos/decisiones/{r.json()['decision_id']}/aplicacion",
                                 headers=_headers())
    assert reintento.status_code == 200, reintento.text
    assert _estado_y_historial(entorno)[0] == EN_REPARACION
    assert _movimientos(entorno) == [("compromiso", 2, entorno.orden_id)]
