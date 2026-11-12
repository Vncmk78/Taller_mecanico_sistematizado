"""Cuántas consultas SQL hace cada endpoint de lectura de MS3 (semana 9).

"Identificar consultas innecesarias o lentas y proponer ajustes de índices":
detalle en backend/docs/consultas-lentas-y-ajustes-indices.md.

Dos garantías por endpoint:

- El número de consultas NO crece con los datos (sin N+1): se mide con pocos
  y con muchos registros y debe ser el mismo.
- No supera el presupuesto medido. Si un cambio agrega consultas, la prueba
  falla y obliga a revisar si son necesarias (o a subir el presupuesto con
  una razón).
"""
from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from services.ms3_presupuestos.models import ItemPresupuesto, Presupuesto, Repuesto
from services.ms3_presupuestos.tests import fabricas
from services.ms3_presupuestos.tests.test_operaciones_presupuesto import (  # noqa: F401
    CLIENTE,
    MECANICO,
    VerificadorFalso,
    api,
    ms2,
)


def _contar(db: Session, accion: Callable[[], object]) -> int:
    motor = db.get_bind().engine
    sentencias: list[str] = []

    def anotar(_c, _cursor, sentencia, *_args) -> None:
        if sentencia.lstrip().upper().startswith("SELECT"):
            sentencias.append(sentencia)

    db.expire_all()
    event.listen(motor, "before_cursor_execute", anotar)
    try:
        respuesta = accion()
    finally:
        event.remove(motor, "before_cursor_execute", anotar)
    assert respuesta.status_code == 200, respuesta.text
    return len(sentencias)


def _escenario(db: Session, ms2: VerificadorFalso, n: int) -> tuple[Presupuesto, Repuesto]:
    """n proveedores con repuestos, movimientos y n presupuestos de n ítems."""
    repuestos = [fabricas.nuevo_repuesto(db, stock=3, umbral_particular=5) for _ in range(n)]
    for r in repuestos:
        fabricas.nuevo_movimiento(db, r, tipo="ingreso", cantidad=1)
        fabricas.nuevo_movimiento(db, r, tipo="compromiso", cantidad=1, orden_id=fabricas.nuevo_orden_id())
    presupuesto = None
    for _ in range(n):
        items = [ItemPresupuesto(tipo="repuesto", repuesto=r, descripcion=r.nombre,
                                 cantidad=Decimal(1), precio_unitario=Decimal(500)) for r in repuestos]
        presupuesto = fabricas.nuevo_presupuesto(db, estado="enviado", items=items)
        ms2.propias.add(presupuesto.orden_id)
    db.commit()
    return presupuesto, repuestos[0]


# endpoint -> (ruta según el escenario, cabecera, presupuesto de consultas)
ENDPOINTS: dict[str, tuple[Callable[[Presupuesto, Repuesto], str], dict, int]] = {
    "listar presupuestos": (lambda p, r: "/presupuestos?limite=50", MECANICO, 5),
    "detalle de presupuesto": (lambda p, r: f"/presupuestos/{p.presupuesto_id}", MECANICO, 6),
    "presupuesto de su orden (cliente)": (lambda p, r: f"/presupuestos?orden_id={p.orden_id}", CLIENTE, 5),
    "listar repuestos": (lambda p, r: "/repuestos?limite=50", MECANICO, 4),
    "repuestos bajo umbral": (lambda p, r: "/repuestos?solo_bajo_umbral=true&limite=50", MECANICO, 4),
    "listar proveedores": (lambda p, r: "/proveedores?limite=50", MECANICO, 3),
    "detalle de proveedor": (lambda p, r: f"/proveedores/{r.proveedor_id}", MECANICO, 3),
    "alertas de stock": (lambda p, r: "/inventario/alertas", MECANICO, 3),
    "historial de movimientos": (lambda p, r: "/inventario/movimientos?limite=50", MECANICO, 2),
    "stock de un repuesto": (lambda p, r: f"/inventario/stock/{r.repuesto_id}", MECANICO, 4),
    "trazabilidad de un repuesto": (lambda p, r: f"/repuestos/{r.repuesto_id}/trazabilidad", MECANICO, 8),
}


@pytest.mark.parametrize("nombre", list(ENDPOINTS))
def test_las_consultas_no_crecen_con_los_datos(
    api: TestClient, db: Session, ms2: VerificadorFalso, nombre: str,
) -> None:
    ruta, cabecera, presupuesto_de_consultas = ENDPOINTS[nombre]
    medidas = []
    for n in (2, 8):
        presupuesto, repuesto = _escenario(db, ms2, n)
        url = ruta(presupuesto, repuesto)  # antes de medir: solo cuenta el endpoint
        medidas.append(_contar(db, lambda: api.get(url, headers=cabecera)))
    assert medidas[0] == medidas[1], f"{nombre}: N+1 ({medidas[0]} con 2 filas, {medidas[1]} con 8)"
    assert medidas[1] <= presupuesto_de_consultas, (
        f"{nombre}: {medidas[1]} consultas (presupuesto {presupuesto_de_consultas})")
