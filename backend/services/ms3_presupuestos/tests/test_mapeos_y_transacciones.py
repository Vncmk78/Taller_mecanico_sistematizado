"""Mapeos ORM y límites transaccionales corregidos (semana 9).

Hallazgos de las pruebas y su corrección:

1. Llamadas a MS2 con una transacción abierta: el router leía el presupuesto
   (autobegin) y luego llamaba a MS2; la conexión quedaba "idle in transaction"
   mientras MS2 respondía, y MS2 vuelve a consultar a MS3 para verificar
   decisiones y envíos. Ahora `UnidadDeTrabajo.liberar_conexion()` la cierra
   antes de cada llamada.
2. Repuesto.proveedor e ItemPresupuesto.repuesto se cargaban uno por uno (N+1).
3. Leer el proveedor de un repuesto traía TODOS los repuestos de ese proveedor.
4. Cada movimiento hacía INSERT + SELECT de su fecha (refresh innecesario).
5. ix_orden_mecanico_estado (MS2) existía en la base pero no en el modelo
   (lo verifica tests/test_integridad_referencial_servicios.py).
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from services.ms3_presupuestos.integracion_ms2 import (
    obtener_coordinador_envios_presupuesto,
    obtener_coordinador_ordenes,
)
from services.ms3_presupuestos.main import app
from services.ms3_presupuestos.models import (
    ItemPresupuesto,
    MovimientoInventario,
    Proveedor,
    Repuesto,
    VersionPresupuesto,
)
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo
from services.ms3_presupuestos.tests import fabricas
from services.ms3_presupuestos.tests.test_operaciones_presupuesto import (  # noqa: F401
    ADMIN,
    CLIENTE,
    MECANICO,
    VerificadorFalso,
    _del_cliente,
    _ruta,
    api,
    ms2,
)
from shared.contratos_decisiones import (
    AplicacionDecisionRespuesta,
    AplicacionEnvioPresupuestoRespuesta,
)


class _Sentencias:
    """Cuenta las sentencias SQL que llegan a la base mientras está activo."""

    def __init__(self, db: Session) -> None:
        self.motor = db.get_bind().engine
        self.lista: list[str] = []

    def _anotar(self, _c, _cursor, sentencia, *_args) -> None:
        self.lista.append(" ".join(sentencia.split()))

    def __enter__(self) -> _Sentencias:
        event.listen(self.motor, "before_cursor_execute", self._anotar)
        return self

    def __exit__(self, *_exc) -> None:
        event.remove(self.motor, "before_cursor_execute", self._anotar)

    def con(self, texto: str) -> list[str]:
        return [s for s in self.lista if texto in s]


def _items(repuestos: list[Repuesto]) -> list[ItemPresupuesto]:
    return [ItemPresupuesto(tipo="repuesto", repuesto=r, descripcion=r.nombre,
                            cantidad=Decimal(1), precio_unitario=Decimal(1000)) for r in repuestos]


def _repuestos(db: Session, n: int) -> list[Repuesto]:
    """n repuestos de n proveedores distintos, con stock."""
    return [fabricas.nuevo_repuesto(db, stock=50) for _ in range(n)]


# ======================================== 1. sin transacción mientras habla MS2 ==

@pytest.fixture
def transacciones_al_llamar_ms2(api: TestClient, db: Session, ms2: VerificadorFalso):
    """Anota si la sesión tenía una transacción abierta en cada llamada a MS2."""
    anotadas: list[tuple[str, bool]] = []
    verificar = ms2.verificar_acceso

    def espia(orden_id: int, token: str):
        anotadas.append(("verificar", db.in_transaction()))
        return verificar(orden_id, token)

    ms2.verificar_acceso = espia
    ms2.verificar_propiedad = espia

    class Decisiones:
        def aplicar(self, orden_id, decision_id, token):
            anotadas.append(("aplicar decision", db.in_transaction()))
            return AplicacionDecisionRespuesta(decision_id=decision_id, orden_id=orden_id,
                                               estado_aplicado=5, historial_id=1)

    class Envios:
        def aplicar(self, orden_id, presupuesto_id, token):
            anotadas.append(("aplicar envio", db.in_transaction()))
            return AplicacionEnvioPresupuestoRespuesta(presupuesto_id=presupuesto_id,
                                                       orden_id=orden_id, estado_aplicado=3,
                                                       historial_id=1)

    app.dependency_overrides[obtener_coordinador_ordenes] = Decisiones
    app.dependency_overrides[obtener_coordinador_envios_presupuesto] = Envios
    return anotadas


def test_ninguna_llamada_a_ms2_ocurre_con_una_transaccion_abierta(
    api: TestClient, db: Session, ms2: VerificadorFalso, transacciones_al_llamar_ms2,
) -> None:
    p = _del_cliente(ms2, fabricas.nuevo_presupuesto(db, items=_items(_repuestos(db, 2))))
    ms2.estados[p.orden_id] = 2
    db.commit()

    assert api.get(f"/presupuestos/{p.presupuesto_id}", headers=MECANICO).status_code == 200
    assert api.put(_ruta(p, 1, "items"), headers=MECANICO, json={"items": [
        {"tipo": "mano_de_obra", "descripcion": "Revisión", "cantidad": "1", "precio_unitario": "9000"},
    ]}).status_code == 200
    assert api.post(_ruta(p, 1, "envio"), headers=ADMIN).status_code == 200
    ms2.estados[p.orden_id] = 3
    assert api.get(f"/presupuestos/{p.presupuesto_id}", headers=CLIENTE).status_code == 200
    r = api.post(_ruta(p, 1, "decision"), headers=CLIENTE, json={"decision": "aprobado"})
    assert r.status_code == 201, r.text

    llamadas = {nombre for nombre, _ in transacciones_al_llamar_ms2}
    assert {"verificar", "aplicar envio", "aplicar decision"} <= llamadas
    assert [n for n, abierta in transacciones_al_llamar_ms2 if abierta] == []


def test_liberar_conexion_no_pierde_lo_leido(db: Session) -> None:
    p = fabricas.nuevo_presupuesto(db, items=_items(_repuestos(db, 1)))
    db.commit()
    uow = UnidadDeTrabajo(db)
    leido = uow.presupuestos.obtener_o_error(p.presupuesto_id)
    uow.liberar_conexion()
    assert not db.in_transaction()
    with _Sentencias(db) as sql:
        assert leido.versiones[0].items[0].repuesto.proveedor.nombre  # sin recargar
    assert sql.lista == []


def test_liberar_conexion_no_confirma_cambios_por_accidente(db: Session) -> None:
    uow = UnidadDeTrabajo(db)
    db.add(Proveedor(nombre="Pendiente sin confirmar", contacto="x"))
    with pytest.raises(RuntimeError, match="cambios sin confirmar"):
        uow.liberar_conexion()
    db.rollback()
    with pytest.raises(RuntimeError, match="transaccion"), uow.transaccion():
        uow.liberar_conexion()


# ============================================================ 2-3. carga ORM ==

def test_el_detalle_no_consulta_un_repuesto_ni_un_proveedor_por_item(
    api: TestClient, db: Session,
) -> None:
    def consultas_del_detalle(n: int) -> int:
        p = fabricas.nuevo_presupuesto(db, items=_items(_repuestos(db, n)))
        db.commit()
        db.expire_all()
        with _Sentencias(db) as sql:
            assert api.get(f"/presupuestos/{p.presupuesto_id}", headers=MECANICO).status_code == 200
        return len(sql.lista)

    assert consultas_del_detalle(2) == consultas_del_detalle(12)


def test_leer_el_proveedor_de_un_repuesto_no_carga_sus_otros_repuestos(db: Session) -> None:
    proveedor = fabricas.nuevo_proveedor(db)  # con varios repuestos
    repuesto_id = proveedor.repuestos[0].repuesto_id
    db.commit()
    db.expunge_all()
    repuesto = db.get(Repuesto, repuesto_id)
    assert repuesto.proveedor.nombre == proveedor.nombre
    assert "repuestos" in inspect(repuesto.proveedor).unloaded


def test_el_listado_de_proveedores_cuenta_repuestos_sin_n_mas_1(
    api: TestClient, db: Session,
) -> None:
    for _ in range(6):
        fabricas.nuevo_proveedor(db)
    db.commit()
    db.expire_all()
    with _Sentencias(db) as sql:
        r = api.get("/proveedores?limite=50", headers=MECANICO)
    assert r.status_code == 200
    assert len(sql.con("FROM repuesto")) <= 1


# ================================================ 4. movimientos sin refresh ==

def test_el_movimiento_trae_su_fecha_en_el_mismo_insert(db: Session) -> None:
    repuesto = fabricas.nuevo_repuesto(db, stock=5)
    with _Sentencias(db) as sql:
        movimiento = UnidadDeTrabajo(db).movimientos.agregar(MovimientoInventario(
            clave_operacion="fecha-returning-1", repuesto=repuesto, tipo="ajuste", cantidad=1,
            registrado_por_id=1))
        assert movimiento.fecha_hora is not None
    (insert,) = sql.con("INSERT INTO movimiento_inventario")
    assert "RETURNING" in insert and "fecha_hora" in insert.split("RETURNING")[1]
    assert sql.con("SELECT") == []


def test_aprobar_reserva_sin_un_select_por_movimiento(
    api: TestClient, db: Session, ms2: VerificadorFalso,
) -> None:
    p = _del_cliente(ms2, fabricas.nuevo_presupuesto(db, estado="enviado",
                                                     items=_items(_repuestos(db, 8))))
    ms2.estados[p.orden_id] = 3
    db.commit()
    with _Sentencias(db) as sql:
        r = api.post(_ruta(p, 1, "decision"), headers=CLIENTE, json={"decision": "aprobado"})
    assert r.status_code == 201, r.text
    assert len(sql.con("INSERT INTO movimiento_inventario")) == 8
    assert sql.con("SELECT movimiento_inventario.fecha_hora") == []
    assert sql.con("FROM proveedor WHERE proveedor.proveedor_id = ") == []


def test_la_carga_de_repuestos_de_los_items_es_por_lote(db: Session) -> None:
    p = fabricas.nuevo_presupuesto(db, items=_items(_repuestos(db, 5)))
    db.commit()
    db.expunge_all()
    with _Sentencias(db) as sql:
        version = db.scalars(select(VersionPresupuesto)
                             .where(VersionPresupuesto.presupuesto_id == p.presupuesto_id)).one()
        nombres = [i.repuesto.proveedor.nombre for i in version.items]
    assert len(nombres) == 5
    assert len(sql.con("FROM repuesto")) == 1 and len(sql.con("FROM proveedor")) == 1
