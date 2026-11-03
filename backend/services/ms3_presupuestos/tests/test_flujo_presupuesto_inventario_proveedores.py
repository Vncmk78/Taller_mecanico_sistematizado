"""Pruebas de presupuestos, inventario, stock y proveedores juntas (SCRUM-526).

Las pruebas de cada módulo viven en su archivo. Aquí se recorre el TALLER
COMPLETO por la API de MS3, como lo usarían el administrador, el mecánico y el
cliente, y después de cada paso se comprueba que los cuatro dominios cuadran
entre sí:

    proveedor y repuesto → stock con su ingreso → presupuesto con ese repuesto
    → envío → aprobación (reserva) → uso en la orden (descuento) → alerta de
    stock bajo → trazabilidad del repuesto y del proveedor → reposición.

MS2 se reemplaza por los dobles de test_operaciones_presupuesto.py.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.ms3_presupuestos.models import MovimientoInventario, Presupuesto
from services.ms3_presupuestos.semilla_integracion import verificar_existencias
from services.ms3_presupuestos.tests import fabricas
from services.ms3_presupuestos.tests.test_operaciones_presupuesto import (  # noqa: F401
    ADMIN,
    CLIENTE,
    MECANICO,
    VerificadorFalso,
    api,
    ms2,
)

ESPERANDO_APROBACION = 3


def _clave() -> str:
    return f"taller-{uuid.uuid4().hex[:20]}"


@pytest.fixture
def taller(api: TestClient, db: Session, ms2: VerificadorFalso) -> dict:
    """Catálogo armado por el administrador: un distribuidor oficial con un repuesto."""
    marca = uuid.uuid4().hex[:6]
    proveedor = api.post("/proveedores", headers=ADMIN, json={
        "nombre": f"Distribuidora Oficial {marca}", "contacto": "ventas@oficial.cl",
        "tipo_distribuidor": "oficial"}).json()
    repuesto = api.post("/repuestos", headers=ADMIN, json={
        "proveedor_id": proveedor["proveedor_id"], "nombre": f"Kit de distribución {marca}",
        "stock_inicial": 5, "umbral_particular": 3}).json()
    orden = fabricas.nuevo_orden_id()
    ms2.propias.add(orden)
    ms2.estados[orden] = ESPERANDO_APROBACION
    return {"proveedor": proveedor, "repuesto": repuesto, "orden": orden}


def _presupuestar(api: TestClient, orden: int, repuesto_id: int, cantidad: int) -> dict:
    r = api.post("/presupuestos", headers=MECANICO, json={"orden_id": orden, "items": [
        {"tipo": "repuesto", "descripcion": "Kit", "cantidad": str(cantidad),
         "precio_unitario": "85000", "repuesto_id": repuesto_id},
        {"tipo": "mano_de_obra", "descripcion": "Cambio de kit", "cantidad": "2",
         "precio_unitario": "20000"}]})
    assert r.status_code == 201, r.text
    return r.json()


def _stock(api: TestClient, repuesto_id: int) -> dict:
    return api.get(f"/inventario/stock/{repuesto_id}", headers=MECANICO).json()


# ============================================================ flujo completo ==

def test_flujo_completo_del_taller(api: TestClient, db: Session, taller: dict) -> None:
    rid, pid = taller["repuesto"]["repuesto_id"], taller["proveedor"]["proveedor_id"]
    orden = taller["orden"]

    # 1. El mecánico presupuesta 4 kits; el administrador envía.
    p = _presupuestar(api, orden, rid, 4)
    assert p["versiones"][0]["total"] == "380000.00"
    envio = api.post(f"/presupuestos/{p['presupuesto_id']}/versiones/1/envio", headers=ADMIN)
    assert envio.status_code == 200 and envio.json()["efecto_en_orden"] == "esperando_aprobacion"

    # 2. El cliente ve solo lo enviado y aprueba: se reservan los 4 kits.
    visto = api.get(f"/presupuestos/{p['presupuesto_id']}", headers=CLIENTE).json()
    assert [v["estado"] for v in visto["versiones"]] == ["enviada"]
    decision = api.post(f"/presupuestos/{p['presupuesto_id']}/versiones/1/decision",
                        headers=CLIENTE, json={"decision": "aprobado"})
    assert decision.status_code == 201, decision.text
    assert decision.json()["efecto_en_orden"] == "en_reparacion"
    assert decision.json()["repuestos_reservados"] == {str(rid): 4}
    stock = _stock(api, rid)
    assert (stock["stock"], stock["comprometido"], stock["disponible"]) == (5, 4, 1)

    # 3. El mecánico usa 4 kits en la orden: el stock baja a 1 y salta la alerta.
    uso = api.post(f"/inventario/ordenes/{orden}/consumos", headers=MECANICO, json={
        "clave_operacion": _clave(), "items": [{"repuesto_id": rid, "cantidad": 4}]})
    assert uso.status_code == 201, uso.text
    stock = _stock(api, rid)
    assert (stock["stock"], stock["comprometido"], stock["bajo_umbral"]) == (1, 0, True)
    alertas = api.get("/inventario/alertas", headers=MECANICO).json()["alertas"]
    assert rid in [a["repuesto_id"] for a in alertas]
    assert api.get(f"/inventario/ordenes/{orden}/disponibilidad",
                   headers=MECANICO).json()["repuestos"][0]["requerido"] == 0

    # 4. Trazabilidad: quién lo abasteció y en qué orden se usó.
    traza = api.get(f"/repuestos/{rid}/trazabilidad", headers=MECANICO).json()
    assert traza["proveedor_actual"] == {"proveedor_id": pid, "nombre": taller["proveedor"]["nombre"],
                                         "tipo_distribuidor": "oficial"}
    assert [(i["proveedor"]["proveedor_id"], i["unidades"]) for i in traza["ingresos_por_proveedor"]] \
        == [(pid, 5)]
    assert traza["uso_por_orden"] == [{"orden_id": orden, "reservado": 0, "consumido": 4}]

    # 5. El administrador repone: se apaga la alerta y el proveedor suma unidades.
    repone = api.post("/inventario/movimientos", headers=ADMIN, json={
        "clave_operacion": _clave(), "repuesto_id": rid, "tipo": "ingreso", "cantidad": 10})
    assert repone.json()["alerta"] == {"activa": False, "nueva": False}
    assert api.get(f"/proveedores/{pid}/trazabilidad",
                   headers=MECANICO).json()["unidades_ingresadas"] == 15

    # 6. El stock siempre coincide con el historial de movimientos.
    nombre = taller["repuesto"]["nombre"]
    assert verificar_existencias(db, nombres=[nombre]) == []
    tipos = [m.tipo for m in db.scalars(select(MovimientoInventario)
                                         .where(MovimientoInventario.repuesto_id == rid)
                                         .order_by(MovimientoInventario.movimiento_id))]
    assert tipos == ["ingreso", "compromiso", "consumo", "ingreso"]


def test_aprobar_sin_stock_suficiente_y_reponer(api: TestClient, taller: dict) -> None:
    rid, orden = taller["repuesto"]["repuesto_id"], taller["orden"]
    p = _presupuestar(api, orden, rid, 8)
    api.post(f"/presupuestos/{p['presupuesto_id']}/versiones/1/envio", headers=ADMIN)

    decision = api.post(f"/presupuestos/{p['presupuesto_id']}/versiones/1/decision",
                        headers=CLIENTE, json={"decision": "aprobado"}).json()
    assert decision["efecto_en_orden"] == "esperando_repuestos"
    assert decision["repuestos_faltantes"][0]["disponible"] == 5
    assert _stock(api, rid)["comprometido"] == 0

    api.post("/inventario/movimientos", headers=ADMIN, json={
        "clave_operacion": _clave(), "repuesto_id": rid, "tipo": "ingreso", "cantidad": 3})
    reserva = api.post(f"/inventario/ordenes/{orden}/reserva", headers=MECANICO).json()
    assert reserva["reservado"] is True
    stock = _stock(api, rid)
    assert (stock["stock"], stock["comprometido"], stock["disponible"]) == (8, 8, 0)


def test_dos_ordenes_compiten_por_el_mismo_repuesto(
    api: TestClient, db: Session, taller: dict, ms2: VerificadorFalso
) -> None:
    rid = taller["repuesto"]["repuesto_id"]
    segunda = fabricas.nuevo_orden_id()
    ms2.propias.add(segunda)
    ms2.estados[segunda] = ESPERANDO_APROBACION

    resultados = []
    for orden in (taller["orden"], segunda):
        p = _presupuestar(api, orden, rid, 3)
        api.post(f"/presupuestos/{p['presupuesto_id']}/versiones/1/envio", headers=ADMIN)
        resultados.append(api.post(f"/presupuestos/{p['presupuesto_id']}/versiones/1/decision",
                                   headers=CLIENTE, json={"decision": "aprobado"}).json())

    # Hay 5: la primera reserva 3; a la segunda solo le quedan 2.
    assert [r["efecto_en_orden"] for r in resultados] == ["en_reparacion", "esperando_repuestos"]
    assert resultados[1]["repuestos_faltantes"][0]["disponible"] == 2
    db.commit()
    rechazo = api.post(f"/inventario/ordenes/{segunda}/consumos", headers=MECANICO, json={
        "clave_operacion": _clave(), "items": [{"repuesto_id": rid, "cantidad": 3}]})
    assert rechazo.status_code == 409 and rechazo.json()["faltantes"][0]["faltan"] == 1


def test_el_repuesto_presupuestado_no_se_puede_borrar_y_el_proveedor_tampoco(
    api: TestClient, db: Session, taller: dict
) -> None:
    rid, pid = taller["repuesto"]["repuesto_id"], taller["proveedor"]["proveedor_id"]
    _presupuestar(api, taller["orden"], rid, 1)
    db.commit()
    assert api.delete(f"/repuestos/{rid}", headers=ADMIN).status_code == 409
    assert api.delete(f"/proveedores/{pid}", headers=ADMIN).status_code == 409


def test_cambiar_de_proveedor_no_borra_lo_que_entrego_el_anterior(api: TestClient, taller: dict) -> None:
    rid, anterior = taller["repuesto"]["repuesto_id"], taller["proveedor"]["proveedor_id"]
    nuevo = api.post("/proveedores", headers=ADMIN, json={
        "nombre": f"Genérico {uuid.uuid4().hex[:6]}", "contacto": "x"}).json()
    api.patch(f"/repuestos/{rid}", headers=ADMIN, json={
        "proveedor_id": nuevo["proveedor_id"], "observacion": "Mejor precio"})
    api.post("/inventario/movimientos", headers=ADMIN, json={
        "clave_operacion": _clave(), "repuesto_id": rid, "tipo": "ingreso", "cantidad": 2})

    traza = api.get(f"/repuestos/{rid}/trazabilidad", headers=MECANICO).json()
    assert {(i["proveedor"]["proveedor_id"], i["unidades"]) for i in traza["ingresos_por_proveedor"]} \
        == {(anterior, 5), (nuevo["proveedor_id"], 2)}
    assert traza["historial_proveedores"][-1]["observacion"] == "Mejor precio"


def test_el_presupuesto_no_acepta_un_repuesto_inexistente(api: TestClient, taller: dict) -> None:
    r = api.post("/presupuestos", headers=MECANICO, json={"orden_id": taller["orden"], "items": [
        {"tipo": "repuesto", "descripcion": "x", "cantidad": "1", "precio_unitario": "1",
         "repuesto_id": 999_999_995}]})
    assert r.status_code == 422


def test_el_cliente_no_entra_al_inventario_ni_al_catalogo(api: TestClient, taller: dict) -> None:
    rid = taller["repuesto"]["repuesto_id"]
    for ruta in (f"/repuestos/{rid}", "/proveedores", f"/inventario/stock/{rid}",
                 f"/repuestos/{rid}/trazabilidad", f"/inventario/ordenes/{taller['orden']}/disponibilidad"):
        assert api.get(ruta, headers=CLIENTE).status_code == 403, ruta


def test_lo_presupuestado_por_otra_version_no_queda_reservado(
    api: TestClient, db: Session, taller: dict
) -> None:
    """Corregir una versión enviada (antes de decidir) no reserva nada: solo aprobar reserva."""
    rid, orden = taller["repuesto"]["repuesto_id"], taller["orden"]
    p = _presupuestar(api, orden, rid, 2)
    api.post(f"/presupuestos/{p['presupuesto_id']}/versiones/1/envio", headers=ADMIN)
    api.post(f"/presupuestos/{p['presupuesto_id']}/versiones", headers=MECANICO, json={})
    assert _stock(api, rid)["comprometido"] == 0
    presupuesto = db.get(Presupuesto, p["presupuesto_id"])
    assert [v.numero for v in presupuesto.versiones] == [1, 2]
