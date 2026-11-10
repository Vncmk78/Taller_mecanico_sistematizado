"""Casos de cierre de presupuestos e inventario que no tenían prueba propia.

Corren contra PostgreSQL real (fixtures `db` y `esquema_aislado`): sin la base,
se omiten, y una omisión NO cuenta como aprobada (ver
docs/evidencia-presupuestos-inventario.md).

  1. Dos aprobaciones SIMULTÁNEAS de órdenes distintas que compiten por las
     últimas unidades: solo una reserva; la otra queda esperando repuestos, sin
     reserva parcial y sin tocar el stock físico.
  2. Un consumo conserva orden, repuesto, cantidad, responsable y fecha, y
     repetirlo con la misma clave no agrega otro movimiento.
  3. Alertas con umbral GENERAL: igual al umbral no alerta; una unidad menos sí
     (comparación estricta stock < umbral), también vía API.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from services.ms3_presupuestos import datos_prueba as datos
from services.ms3_presupuestos.models import ItemPresupuesto, MovimientoInventario, Repuesto
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo
from services.ms3_presupuestos.persistencia.repositorios import RepositorioMovimientos
from services.ms3_presupuestos.schemas.inventario import MovimientoCrear
from services.ms3_presupuestos.services import inventario as casos_inventario
from services.ms3_presupuestos.services import presupuestos as casos_presupuestos
from services.ms3_presupuestos.tests import fabricas
from services.ms3_presupuestos.tests.test_rollback_consistencia import (  # noqa: F401
    esquema_aislado,
)


def _item(repuesto: Repuesto, cantidad: str) -> ItemPresupuesto:
    return ItemPresupuesto(tipo="repuesto", descripcion=repuesto.nombre, cantidad=Decimal(cantidad),
                           precio_unitario=Decimal("1000"), repuesto=repuesto)


def _a_la_vez(fabrica: sessionmaker[Session], operaciones: list[Callable[[UnidadDeTrabajo], Any]]) -> list[Any]:
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


def _aprobar(presupuesto_id: int):
    return lambda uow: casos_presupuestos.decidir_version(
        uow, presupuesto_id=presupuesto_id, numero=1, cliente_usuario_id=datos.CLIENTE_ID,
        decision="aprobado", motivo=None, confirmar_cancelacion=False)


def test_aprobaciones_simultaneas_no_reservan_unidades_de_otra_orden(esquema_aislado) -> None:  # noqa: F811
    with esquema_aislado() as sesion:
        repuesto = fabricas.nuevo_repuesto(sesion, stock=3)
        p1 = fabricas.nuevo_presupuesto(sesion, estado="enviado", items=[_item(repuesto, "2")])
        p2 = fabricas.nuevo_presupuesto(sesion, estado="enviado", items=[_item(repuesto, "2")])
        rid, ids, ordenes = repuesto.repuesto_id, (p1.presupuesto_id, p2.presupuesto_id), (p1.orden_id, p2.orden_id)
        sesion.commit()

    resultados = _a_la_vez(esquema_aislado, [_aprobar(ids[0]), _aprobar(ids[1])])

    assert not any(isinstance(r, Exception) for r in resultados), resultados
    assert sorted(r.efecto_en_orden for r in resultados) == ["en_reparacion", "esperando_repuestos"]
    with esquema_aislado() as sesion:
        reservas = RepositorioMovimientos(sesion).comprometido_por_orden(rid)
        assert sorted(reservas.get(o, 0) for o in ordenes) == [0, 2]  # sin reserva parcial
        assert sesion.get(Repuesto, rid).stock == 3  # aprobar no toca el stock físico


def test_consumo_conserva_orden_repuesto_cantidad_responsable_y_fecha(db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=6)
    orden_id = fabricas.nuevo_orden_id()
    clave = f"cierre-{uuid.uuid4().hex[:12]}"
    entrada = MovimientoCrear(clave_operacion=clave, repuesto_id=repuesto.repuesto_id,
                              tipo="consumo", cantidad=2, orden_id=orden_id)
    antes = datetime.now(timezone.utc) - timedelta(minutes=5)

    primero = casos_inventario.registrar_movimiento(UnidadDeTrabajo(db), entrada, usuario_id=datos.MECANICO_ID)
    repetido = casos_inventario.registrar_movimiento(UnidadDeTrabajo(db), entrada, usuario_id=datos.MECANICO_ID)

    assert repetido.repetido is True and primero.repetido is False
    movimientos = db.scalars(select(MovimientoInventario).where(
        MovimientoInventario.clave_operacion == clave)).all()
    assert len(movimientos) == 1
    m = movimientos[0]
    assert (m.orden_id, m.repuesto_id, m.cantidad, m.tipo, m.registrado_por_id) == (
        orden_id, repuesto.repuesto_id, 2, "consumo", datos.MECANICO_ID)
    assert m.fecha_hora.tzinfo is not None and m.fecha_hora >= antes
    db.expire_all()
    assert db.get(Repuesto, repuesto.repuesto_id).stock == 4


def test_alerta_con_umbral_general_es_estricta(db: Session) -> None:
    fabricas.umbral_general_vigente(db, 5)
    igual = fabricas.nuevo_repuesto(db, stock=5)
    debajo = fabricas.nuevo_repuesto(db, stock=4)
    particular = fabricas.nuevo_repuesto(db, stock=5, umbral_particular=6)  # particular prevalece

    general, alertas = casos_inventario.alertas(UnidadDeTrabajo(db))

    ids = {a.repuesto_id for a in alertas}
    assert general == 5
    assert igual.repuesto_id not in ids
    assert debajo.repuesto_id in ids
    assert particular.repuesto_id in ids
    assert casos_inventario.esta_bajo_umbral(5, 5) is False
    assert casos_inventario.esta_bajo_umbral(4, 5) is True
    assert casos_inventario.esta_bajo_umbral(10, None) is False
