"""Aprobación/rechazo de presupuestos y conexión con órdenes (SCRUM-525).

MS3 lee la orden en MS2 (visibilidad por rol y `estado_codigo`) antes de
escribir:
- crear el presupuesto exige una orden visible para quien presupuesta;
- una orden Entregada (7) o Cancelada (8) no admite presupuesto, versiones,
  envío ni decisión (409) y libera lo que aún tenía reservado;
- la PRIMERA decisión exige la orden en "Esperando aprobación de presupuesto" (3);
  una modificación posterior se decide con la orden en curso (4, 5…);
- si MS2 no informa el estado, MS3 no inventa reglas (MS2 valida al aplicar).
"""
from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.ms3_presupuestos import integracion_ms2
from services.ms3_presupuestos.integracion_ms2 import OrdenVisible, VerificadorOrdenesHttp
from services.ms3_presupuestos.models import ItemPresupuesto, Presupuesto, Repuesto
from services.ms3_presupuestos.persistencia.repositorios import RepositorioMovimientos
from services.ms3_presupuestos.tests import fabricas
from services.ms3_presupuestos.tests.test_operaciones_presupuesto import (  # noqa: F401
    ADMIN,
    CLIENTE,
    MECANICO,
    VerificadorFalso,
    _decisiones,
    _del_cliente,
    _ruta,
    api,
    ms2,
)

RECIBIDO, DIAGNOSTICO, ESPERANDO, REPUESTOS, REPARACION, LISTO, ENTREGADO, CANCELADO = range(1, 9)


def _item(repuesto: Repuesto, cantidad: str = "2") -> ItemPresupuesto:
    return ItemPresupuesto(tipo="repuesto", descripcion=repuesto.nombre, cantidad=Decimal(cantidad),
                           precio_unitario=Decimal("1000"), repuesto=repuesto)


def _aprobar(api: TestClient, presupuesto: Presupuesto, numero: int = 1):
    return api.post(_ruta(presupuesto, numero, "decision"), headers=CLIENTE,
                    json={"decision": "aprobado"})


def _crear(api: TestClient, orden_id: int):
    return api.post("/presupuestos", headers=MECANICO, json={"orden_id": orden_id, "items": [
        {"tipo": "mano_de_obra", "descripcion": "Diagnóstico", "cantidad": "1",
         "precio_unitario": "15000"}]})


# ================================================================ crear ==

def test_crear_presupuesto_verifica_la_orden_con_el_jwt_del_mecanico(
    api: TestClient, ms2: VerificadorFalso
) -> None:
    orden = fabricas.nuevo_orden_id()
    ms2.estados[orden] = DIAGNOSTICO
    r = _crear(api, orden)
    assert r.status_code == 201, r.text
    assert ms2.consultas == [(orden, MECANICO["Authorization"][7:])]


def test_no_se_presupuesta_una_orden_que_el_mecanico_no_ve(
    api: TestClient, ms2: VerificadorFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    orden = fabricas.nuevo_orden_id()
    original = ms2.verificar_acceso

    def solo_asignadas(orden_id: int, token: str):
        if token == MECANICO["Authorization"][7:]:
            raise integracion_ms2.OrdenNoVisible(orden_id)
        return original(orden_id, token)

    monkeypatch.setattr(ms2, "verificar_acceso", solo_asignadas)
    r = _crear(api, orden)
    assert r.status_code == 404 and str(orden) in r.json()["detail"]


def test_ms2_caido_al_crear_es_503(api: TestClient, ms2: VerificadorFalso) -> None:
    ms2.caido = True
    assert _crear(api, fabricas.nuevo_orden_id()).status_code == 503


@pytest.mark.parametrize(("estado", "nombre"), [(ENTREGADO, "Entregado"), (CANCELADO, "Cancelado")])
def test_no_se_presupuesta_una_orden_cerrada(
    api: TestClient, ms2: VerificadorFalso, estado: int, nombre: str
) -> None:
    orden = fabricas.nuevo_orden_id()
    ms2.estados[orden] = estado
    r = _crear(api, orden)
    assert r.status_code == 409 and nombre in r.json()["detail"]


# ===================================================== orden cerrada después ==

@pytest.mark.parametrize("accion", ["nueva_version", "editar", "enviar"])
def test_orden_cancelada_bloquea_versiones_edicion_y_envio(
    api: TestClient, db: Session, ms2: VerificadorFalso, accion: str
) -> None:
    p = fabricas.nuevo_presupuesto(db, estado="borrador")
    ms2.estados[p.orden_id] = CANCELADO
    db.commit()
    if accion == "nueva_version":
        r = api.post(f"/presupuestos/{p.presupuesto_id}/versiones", headers=MECANICO, json={})
    elif accion == "editar":
        r = api.put(_ruta(p, 1, "items"), headers=MECANICO, json={"items": [
            {"tipo": "mano_de_obra", "descripcion": "x", "cantidad": "1", "precio_unitario": "1"}]})
    else:
        r = api.post(_ruta(p, 1, "envio"), headers=ADMIN)
    assert r.status_code == 409 and "Cancelado" in r.json()["detail"]


def test_orden_cancelada_libera_las_unidades_reservadas(
    api: TestClient, db: Session, ms2: VerificadorFalso
) -> None:
    disco = fabricas.nuevo_repuesto(db, stock=5)
    p = _del_cliente(ms2, fabricas.nuevo_presupuesto(db, estado="enviado", items=[_item(disco, "3")]))
    ms2.estados[p.orden_id] = ESPERANDO
    assert _aprobar(api, p).status_code == 201
    assert RepositorioMovimientos(db).comprometido_por_orden(disco.repuesto_id) == {p.orden_id: 3}

    # MS2 canceló la orden (p. ej. flujo de cancelación). Al intentar modificar
    # el presupuesto, MS3 responde 409 y suelta las unidades.
    ms2.estados[p.orden_id] = CANCELADO
    r = api.post(f"/presupuestos/{p.presupuesto_id}/versiones", headers=MECANICO, json={})
    assert r.status_code == 409
    assert RepositorioMovimientos(db).comprometido_por_orden(disco.repuesto_id) == {}
    # Repetirlo no libera dos veces.
    api.post(f"/presupuestos/{p.presupuesto_id}/versiones", headers=MECANICO, json={})
    movimientos = RepositorioMovimientos(db).de_orden(p.orden_id)
    assert [(m.tipo, m.cantidad) for m in movimientos] == [("compromiso", 3), ("liberacion", 3)]


# ================================================================ decidir ==

@pytest.mark.parametrize("estado", [RECIBIDO, DIAGNOSTICO, REPUESTOS, REPARACION, LISTO])
def test_primera_decision_exige_orden_esperando_aprobacion(
    api: TestClient, db: Session, ms2: VerificadorFalso, estado: int
) -> None:
    p = _del_cliente(ms2, fabricas.nuevo_presupuesto(db, estado="enviado"))
    ms2.estados[p.orden_id] = estado
    db.commit()
    r = _aprobar(api, p)
    assert r.status_code == 409 and "no está esperando la aprobación" in r.json()["detail"]
    assert _decisiones(db, p) == 0


@pytest.mark.parametrize("decision", ["aprobado", "rechazado"])
def test_primera_decision_con_orden_esperando_aprobacion(
    api: TestClient, db: Session, ms2: VerificadorFalso, decision: str
) -> None:
    p = _del_cliente(ms2, fabricas.nuevo_presupuesto(db, estado="enviado"))
    ms2.estados[p.orden_id] = ESPERANDO
    cuerpo = {"decision": decision}
    if decision == "rechazado":
        cuerpo |= {"motivo": "Muy caro", "confirmar_cancelacion": True}
    r = api.post(_ruta(p, 1, "decision"), headers=CLIENTE, json=cuerpo)
    assert r.status_code == 201, r.text
    assert r.json()["efecto_en_orden"] == ("en_reparacion" if decision == "aprobado" else "cancelado")
    assert r.json()["aplicacion_en_orden"]["estado_aplicado"] == (5 if decision == "aprobado" else 8)


def test_sin_estado_informado_ms3_no_bloquea(api: TestClient, db: Session, ms2: VerificadorFalso) -> None:
    p = _del_cliente(ms2, fabricas.nuevo_presupuesto(db, estado="enviado"))
    assert _aprobar(api, p).status_code == 201


@pytest.mark.parametrize("estado", [REPUESTOS, REPARACION])
def test_una_modificacion_se_decide_con_la_orden_en_curso(
    api: TestClient, db: Session, ms2: VerificadorFalso, estado: int
) -> None:
    p = _del_cliente(ms2, fabricas.nuevo_presupuesto(db, estado="aprobado"))
    fabricas.enviar(db, fabricas.nueva_version_siguiente(db, p))
    ms2.estados[p.orden_id] = estado
    r = _aprobar(api, p, 2)
    assert r.status_code == 201, r.text
    assert r.json()["efecto_en_orden"] == "en_reparacion" and r.json()["aplicacion_en_orden"] is None


@pytest.mark.parametrize("estado", [ENTREGADO, CANCELADO])
def test_no_se_decide_sobre_una_orden_cerrada(
    api: TestClient, db: Session, ms2: VerificadorFalso, estado: int
) -> None:
    p = _del_cliente(ms2, fabricas.nuevo_presupuesto(db, estado="aprobado"))
    fabricas.enviar(db, fabricas.nueva_version_siguiente(db, p))
    ms2.estados[p.orden_id] = estado
    db.commit()
    r = _aprobar(api, p, 2)
    assert r.status_code == 409
    assert _decisiones(db, p) == 1  # solo la aprobación original


# ====================================================== lectura de MS2 (HTTP) ==

@pytest.mark.parametrize(("cuerpo", "estado"), [
    ({"orden_id": 31, "estado_codigo": 3}, 3),
    ({"orden_id": 31, "estado_codigo": 8}, 8),
    ({"orden_id": 31}, None),
    ({"orden_id": 31, "estado_codigo": "3"}, None),
    ({"orden_id": 31, "estado_codigo": 99}, None),
    ({"orden_id": 31, "estado_codigo": True}, None),
    (None, None),
])
def test_el_verificador_lee_el_estado_de_la_orden(monkeypatch: pytest.MonkeyPatch, cuerpo, estado) -> None:
    def falso_get(url: str, *, headers: dict, timeout: float) -> httpx.Response:
        kwargs = {"json": cuerpo} if cuerpo is not None else {"text": "sin json"}
        return httpx.Response(200, request=httpx.Request("GET", url),
                              headers={"X-Orden-Propiedad-Verificada": "true"}, **kwargs)

    monkeypatch.setattr(integracion_ms2.httpx, "get", falso_get)
    verificador = VerificadorOrdenesHttp("http://ms2", 1.0)
    assert verificador.verificar_acceso(31, "t") == OrdenVisible(31, estado)
    assert verificador.verificar_propiedad(31, "t") == OrdenVisible(31, estado)
