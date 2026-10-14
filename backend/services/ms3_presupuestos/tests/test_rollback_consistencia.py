"""Rollback y consistencia ante errores durante la modificación del presupuesto.

Dos bloques (PostgreSQL migrado; se omiten si no hay base):

A) ROLLBACK: se provoca un fallo en mitad de cada operación que modifica un
   presupuesto (después de que ya escribió algo en la base) y se comprueba,
   leyendo con SQL directo, que la base quedó EXACTAMENTE como antes y que la
   sesión sigue usable para la siguiente operación.

B) CONCURRENCIA: dos peticiones reales (conexiones distintas, cada una con su
   propio COMMIT) sobre el mismo presupuesto a la vez. Corre en un ESQUEMA
   TEMPORAL creado y migrado para la prueba y borrado al final (las decisiones
   y versiones enviadas no se pueden borrar: así no queda basura en la base).
"""
from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Iterator
from decimal import Decimal
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from services.ms3_presupuestos import datos_prueba as datos
from services.ms3_presupuestos.models import ItemPresupuesto, Presupuesto
from services.ms3_presupuestos.persistencia import (
    ConflictoDeDatos,
    ReglaDeDatosViolada,
    UnidadDeTrabajo,
)
from services.ms3_presupuestos.schemas.presupuesto import ItemEntrada
from services.ms3_presupuestos.services import presupuestos as casos
from services.ms3_presupuestos.tests import fabricas

UBICACION_MIGRACIONES = "services/ms3_presupuestos/alembic"


class FallaSimulada(RuntimeError):
    """Error inyectado a propósito en mitad de una operación."""


# ============================================================ utilidades ==

def _foto(db: Session, presupuesto_id: int) -> list[tuple]:
    """Estado exacto en la base del presupuesto: versiones, ítems y decisiones."""
    return [tuple(f) for f in db.execute(text("""
        select p.orden_id, v.version_id, v.numero, v.creado_por_id, v.creado_en,
               v.enviado_en, v.bloqueada_en, v.es_modificacion,
               i.item_id, i.tipo, i.repuesto_id, i.descripcion, i.cantidad,
               i.precio_unitario, d.decision, d.motivo, d.fecha_hora
        from presupuesto p
        join version_presupuesto v on v.presupuesto_id = p.presupuesto_id
        left join item_presupuesto i on i.version_id = v.version_id
        left join decision_presupuesto d on d.version_id = v.version_id
        where p.presupuesto_id = :p
        order by v.numero, i.item_id
    """), {"p": presupuesto_id})]


def _item(descripcion: str = "Mano de obra", precio: str = "10000", **extra: Any) -> ItemEntrada:
    return ItemEntrada(tipo="mano_de_obra", descripcion=descripcion, cantidad=Decimal("1"),
                       precio_unitario=Decimal(precio), **extra)


def _item_que_viola_la_base() -> ItemEntrada:
    """Pasa por alto Pydantic (model_construct) para que la regla la aplique la base."""
    return ItemEntrada.model_construct(tipo="mano_de_obra", descripcion="Cantidad cero",
                                       cantidad=Decimal("0"), precio_unitario=Decimal("1"),
                                       repuesto_id=None)


def _sesion_sigue_usable(uow: UnidadDeTrabajo) -> None:
    """Tras el rollback la sesión no queda 'abortada': otra operación funciona."""
    nuevo = casos.crear_presupuesto(uow, orden_id=fabricas.nuevo_orden_id(),
                                    items=[_item()], creado_por_id=datos.MECANICO_ID)
    assert nuevo.presupuesto_id is not None


@pytest.fixture
def confirmado(db: Session) -> Callable[[Presupuesto], Presupuesto]:
    """Confirma (SAVEPOINT) los datos de la fixture para que el rollback de la
    operación probada no se los lleve: así se distingue 'deshizo la operación'
    de 'deshizo también lo que ya existía'."""
    def _confirmar(presupuesto: Presupuesto) -> Presupuesto:
        db.commit()
        return presupuesto
    return _confirmar


# =============================================== A) ROLLBACK POR OPERACIÓN ==

def test_editar_items_falla_despues_de_borrar_los_anteriores(
    db: Session, uow: UnidadDeTrabajo, presupuesto_borrador: Presupuesto,
    confirmado, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """reemplazar_items borra los ítems (flush) y luego falla al construir los nuevos."""
    pid = confirmado(presupuesto_borrador).presupuesto_id
    antes = _foto(db, pid)

    def falla(*_: Any) -> list[ItemPresupuesto]:
        # En este punto los ítems viejos YA se borraron en la transacción.
        assert db.execute(text(
            "select count(*) from item_presupuesto i join version_presupuesto v "
            "using (version_id) where v.presupuesto_id = :p"), {"p": pid}).scalar() == 0
        raise FallaSimulada("después del DELETE de los ítems")

    monkeypatch.setattr(casos, "_construir_items", falla)
    with pytest.raises(FallaSimulada):
        casos.reemplazar_items(uow, presupuesto_id=pid, numero=1, items=[_item()])

    assert _foto(db, pid) == antes
    monkeypatch.undo()
    _sesion_sigue_usable(uow)


def test_editar_items_con_un_item_que_la_base_rechaza(
    db: Session, uow: UnidadDeTrabajo, presupuesto_borrador: Presupuesto, confirmado,
) -> None:
    """El primer ítem es válido, el segundo viola un CHECK: no queda ninguno de los dos."""
    pid = confirmado(presupuesto_borrador).presupuesto_id
    antes = _foto(db, pid)
    with pytest.raises(ReglaDeDatosViolada) as error:
        casos.reemplazar_items(uow, presupuesto_id=pid, numero=1,
                               items=[_item("Válido"), _item_que_viola_la_base()])
    assert error.value.restriccion == "ck_item_presupuesto_cantidad_positiva"
    assert _foto(db, pid) == antes
    _sesion_sigue_usable(uow)


def test_crear_presupuesto_con_item_invalido_no_deja_presupuesto_huerfano(
    db: Session, uow: UnidadDeTrabajo,
) -> None:
    orden = fabricas.nuevo_orden_id()
    db.commit()
    with pytest.raises(ReglaDeDatosViolada):
        casos.crear_presupuesto(uow, orden_id=orden, creado_por_id=datos.MECANICO_ID,
                                items=[_item(), _item_que_viola_la_base()])
    assert db.execute(text("select count(*) from presupuesto where orden_id = :o"),
                      {"o": orden}).scalar() == 0
    _sesion_sigue_usable(uow)


def test_crear_version_con_item_invalido_no_deja_version_a_medias(
    db: Session, uow: UnidadDeTrabajo, presupuesto_enviado: Presupuesto, confirmado,
) -> None:
    """INSERT de la versión 2 + ítems; el último ítem falla → no existe la versión 2."""
    pid = confirmado(presupuesto_enviado).presupuesto_id
    antes = _foto(db, pid)
    with pytest.raises(ReglaDeDatosViolada):
        casos.crear_version(uow, presupuesto_id=pid, creado_por_id=datos.MECANICO_ID,
                            items=[_item(), _item_que_viola_la_base()])
    assert _foto(db, pid) == antes
    # Y el número 2 sigue libre: la siguiente versión correcta es la 2, no la 3.
    nueva = casos.crear_version(uow, presupuesto_id=pid, creado_por_id=datos.MECANICO_ID)
    assert nueva.numero == 2


def test_crear_version_falla_al_copiar_items(
    db: Session, uow: UnidadDeTrabajo, presupuesto_ejemplo: Presupuesto,
    confirmado, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pid = confirmado(presupuesto_ejemplo).presupuesto_id
    antes = _foto(db, pid)
    copiados = []

    def copia_y_falla(item: ItemPresupuesto) -> ItemPresupuesto:
        copiados.append(item.item_id)
        if len(copiados) == 2:
            raise FallaSimulada("a mitad de la copia de ítems")
        return casos.ItemPresupuesto(tipo=item.tipo, descripcion=item.descripcion,
                                     cantidad=item.cantidad,
                                     precio_unitario=item.precio_unitario,
                                     repuesto_id=item.repuesto_id)

    monkeypatch.setattr(casos, "_copiar_item", copia_y_falla)
    with pytest.raises(FallaSimulada):
        casos.crear_version(uow, presupuesto_id=pid, creado_por_id=datos.MECANICO_ID)
    assert _foto(db, pid) == antes


def test_enviar_falla_despues_de_marcar_el_envio(
    db: Session, uow: UnidadDeTrabajo, presupuesto_borrador: Presupuesto,
    confirmado, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """enviado_en ya se escribió (flush); si algo falla después, la versión sigue en borrador."""
    pid = confirmado(presupuesto_borrador).presupuesto_id
    antes = _foto(db, pid)
    refresh_original = db.refresh

    def refresh_que_falla(objeto: Any, *a: Any, **k: Any) -> None:
        refresh_original(objeto, *a, **k)
        assert objeto.enviado_en is not None      # el UPDATE ya ocurrió
        raise FallaSimulada("después del UPDATE de enviado_en")

    monkeypatch.setattr(db, "refresh", refresh_que_falla)
    with pytest.raises(FallaSimulada):
        casos.enviar_version(uow, presupuesto_id=pid, numero=1)
    monkeypatch.undo()

    assert _foto(db, pid) == antes
    # La versión sigue editable: se puede corregir y luego enviar sin problema.
    casos.reemplazar_items(uow, presupuesto_id=pid, numero=1, items=[_item("Corregido")])
    resultado = casos.enviar_version(uow, presupuesto_id=pid, numero=1)
    assert resultado.presupuesto.versiones[0].estado == "enviada"


def test_decidir_falla_despues_del_bloqueo_por_trigger(
    db: Session, uow: UnidadDeTrabajo, presupuesto_enviado: Presupuesto,
    confirmado, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INSERT de la decisión + trigger que bloquea la versión; luego falla → nada queda."""
    pid = confirmado(presupuesto_enviado).presupuesto_id
    antes = _foto(db, pid)

    refresh_original = db.refresh

    def falla(version: Any, *a: Any, **k: Any) -> None:
        refresh_original(version, *a, **k)
        assert version.bloqueada_en is not None   # el trigger ya bloqueó
        raise FallaSimulada("después de la decisión y el bloqueo")

    # La evaluación de stock ahora ocurre antes del INSERT para conservarla
    # en la decisión. Inyectar después de refresh mantiene esta prueba de rollback.
    monkeypatch.setattr(db, "refresh", falla)
    with pytest.raises(FallaSimulada):
        casos.decidir_version(uow, presupuesto_id=pid, numero=1,
                              cliente_usuario_id=datos.CLIENTE_ID, decision="aprobado",
                              motivo=None, confirmar_cancelacion=False)
    monkeypatch.undo()
    assert _foto(db, pid) == antes

    # La decisión se puede registrar después, una sola vez.
    casos.decidir_version(uow, presupuesto_id=pid, numero=1,
                          cliente_usuario_id=datos.CLIENTE_ID, decision="aprobado",
                          motivo=None, confirmar_cancelacion=False)
    with pytest.raises(ConflictoDeDatos):
        casos.decidir_version(uow, presupuesto_id=pid, numero=1,
                              cliente_usuario_id=datos.CLIENTE_ID, decision="aprobado",
                              motivo=None, confirmar_cancelacion=False)


def test_un_error_no_deshace_operaciones_ya_confirmadas(
    db: Session, uow: UnidadDeTrabajo, presupuesto_enviado: Presupuesto, confirmado,
) -> None:
    """Cada operación es su propia transacción: el fallo de la 2.ª no borra la 1.ª."""
    pid = confirmado(presupuesto_enviado).presupuesto_id
    casos.crear_version(uow, presupuesto_id=pid, creado_por_id=datos.MECANICO_ID)
    despues_de_crear = _foto(db, pid)

    with pytest.raises(ReglaDeDatosViolada):
        casos.reemplazar_items(uow, presupuesto_id=pid, numero=2,
                               items=[_item_que_viola_la_base()])
    assert _foto(db, pid) == despues_de_crear
    assert [n for (_, _, n, *_) in despues_de_crear].count(2) >= 1


def test_operacion_rechazada_por_regla_no_escribe_nada(
    db: Session, uow: UnidadDeTrabajo, presupuesto_aprobado: Presupuesto, confirmado,
) -> None:
    """Editar/enviar/decidir sobre una versión aprobada: 409 y la foto no cambia."""
    pid = confirmado(presupuesto_aprobado).presupuesto_id
    antes = _foto(db, pid)
    with pytest.raises(ConflictoDeDatos):
        casos.reemplazar_items(uow, presupuesto_id=pid, numero=1, items=[])
    with pytest.raises(ConflictoDeDatos):
        casos.enviar_version(uow, presupuesto_id=pid, numero=1)
    with pytest.raises(ConflictoDeDatos):
        casos.decidir_version(uow, presupuesto_id=pid, numero=1,
                              cliente_usuario_id=datos.CLIENTE_ID, decision="rechazado",
                              motivo="x", confirmar_cancelacion=True)
    assert _foto(db, pid) == antes


def test_sql_directo_tampoco_rompe_la_version_aprobada(
    db: Session, presupuesto_aprobado: Presupuesto, confirmado,
) -> None:
    """Aunque alguien salte la API, la base rechaza y la transacción se revierte."""
    pid = confirmado(presupuesto_aprobado).presupuesto_id
    antes = _foto(db, pid)
    sentencias = [
        "update item_presupuesto set precio_unitario = 1 where version_id = :v",
        "delete from item_presupuesto where version_id = :v",
        "update version_presupuesto set bloqueada_en = null where version_id = :v",
        "delete from decision_presupuesto where version_id = :v",
        "update decision_presupuesto set decision = 'rechazado', motivo = 'x' where version_id = :v",
    ]
    version_id = presupuesto_aprobado.versiones[0].version_id
    for sql in sentencias:
        with pytest.raises(Exception), db.begin_nested():
            db.execute(text(sql), {"v": version_id})
    assert _foto(db, pid) == antes


# ============================================== B) CONCURRENCIA REAL ==

@pytest.fixture(scope="module")
def esquema_aislado(engine: Engine) -> Iterator[sessionmaker[Session]]:
    """Esquema temporal migrado a head: commits reales sin tocar la base de pruebas."""
    esquema = f"prueba_concurrencia_{uuid.uuid4().hex[:8]}"
    with engine.begin() as conexion:
        conexion.execute(text(f'create schema "{esquema}"'))
        conexion.execute(text(f'set local search_path to "{esquema}"'))
        # Config SIN archivo .ini: así env.py no ejecuta fileConfig(), que
        # reconfiguraría el logging y apagaría los loggers de otras pruebas.
        configuracion = Config()
        configuracion.set_main_option("script_location", UBICACION_MIGRACIONES)
        configuracion.attributes["connection"] = conexion
        command.upgrade(configuracion, "head")

    motor = create_engine(engine.url, pool_size=6)

    @event.listens_for(motor, "connect")
    def _usar_esquema(conexion_dbapi, _):  # noqa: ANN001
        with conexion_dbapi.cursor() as cursor:
            cursor.execute(f'set search_path to "{esquema}"')
        conexion_dbapi.commit()

    try:
        yield sessionmaker(bind=motor, expire_on_commit=False)
    finally:
        motor.dispose()
        with engine.begin() as conexion:
            conexion.execute(text(f'drop schema "{esquema}" cascade'))


def _en_paralelo(fabrica: sessionmaker[Session], operaciones: list[Callable[[UnidadDeTrabajo], Any]],
                 *, bloquear_presupuesto: int) -> list[Any]:
    """Lanza las operaciones a la vez, cada una con su sesión/conexión.

    Un tercer participante mantiene el bloqueo del presupuesto mientras todas
    arrancan: así quedan esperando en el mismo FOR UPDATE y compiten de verdad.
    """
    resultados: list[Any] = [None] * len(operaciones)
    listas = threading.Barrier(len(operaciones) + 1)

    def correr(indice: int, operacion: Callable[[UnidadDeTrabajo], Any]) -> None:
        with fabrica() as sesion:
            listas.wait()
            try:
                resultados[indice] = operacion(UnidadDeTrabajo(sesion))
            except Exception as exc:  # noqa: BLE001  (se analiza en la prueba)
                resultados[indice] = exc

    with fabrica() as bloqueador:
        bloqueador.execute(text("select 1 from presupuesto where presupuesto_id = :p for update"),
                           {"p": bloquear_presupuesto})
        hilos = [threading.Thread(target=correr, args=(i, op)) for i, op in enumerate(operaciones)]
        for hilo in hilos:
            hilo.start()
        listas.wait()
        # Damos tiempo a que todas lleguen al FOR UPDATE y queden esperando.
        threading.Event().wait(0.3)
        bloqueador.rollback()
        for hilo in hilos:
            hilo.join(timeout=20)
    return resultados


def _presupuesto_real(fabrica: sessionmaker[Session], *, enviar: bool) -> int:
    with fabrica() as sesion:
        uow = UnidadDeTrabajo(sesion)
        presupuesto = casos.crear_presupuesto(uow, orden_id=fabricas.nuevo_orden_id(),
                                              items=[_item()], creado_por_id=datos.MECANICO_ID)
        if enviar:
            casos.enviar_version(uow, presupuesto_id=presupuesto.presupuesto_id, numero=1)
        return presupuesto.presupuesto_id


def _contar(fabrica: sessionmaker[Session], sql: str, pid: int) -> int:
    with fabrica() as sesion:
        return sesion.execute(text(sql), {"p": pid}).scalar()


def test_dos_decisiones_simultaneas_solo_registra_una(esquema_aislado) -> None:
    pid = _presupuesto_real(esquema_aislado, enviar=True)

    def decidir(decision: str, motivo: str | None) -> Callable[[UnidadDeTrabajo], Any]:
        return lambda uow: casos.decidir_version(
            uow, presupuesto_id=pid, numero=1, cliente_usuario_id=datos.CLIENTE_ID,
            decision=decision, motivo=motivo, confirmar_cancelacion=True)

    resultados = _en_paralelo(esquema_aislado, [decidir("aprobado", None),
                                                decidir("rechazado", "Muy caro")],
                              bloquear_presupuesto=pid)
    errores = [r for r in resultados if isinstance(r, Exception)]
    exitos = [r for r in resultados if not isinstance(r, Exception)]
    assert len(exitos) == 1 and len(errores) == 1
    assert isinstance(errores[0], ConflictoDeDatos)
    assert "ya tiene una decisión" in errores[0].mensaje
    assert _contar(esquema_aislado, """
        select count(*) from decision_presupuesto d join version_presupuesto v using (version_id)
        where v.presupuesto_id = :p""", pid) == 1


def test_dos_nuevas_versiones_simultaneas_no_duplican_numero(esquema_aislado) -> None:
    pid = _presupuesto_real(esquema_aislado, enviar=True)
    crear = lambda uow: casos.crear_version(  # noqa: E731
        uow, presupuesto_id=pid, creado_por_id=datos.MECANICO_ID)

    resultados = _en_paralelo(esquema_aislado, [crear, crear, crear], bloquear_presupuesto=pid)
    exitos = [r for r in resultados if not isinstance(r, Exception)]
    errores = [r for r in resultados if isinstance(r, Exception)]
    assert len(exitos) == 1 and exitos[0].numero == 2
    assert len(errores) == 2 and all(isinstance(e, ConflictoDeDatos) for e in errores)
    assert _contar(esquema_aislado,
                   "select count(*) from version_presupuesto where presupuesto_id = :p", pid) == 2


def test_editar_y_enviar_a_la_vez_nunca_cambia_una_version_enviada(esquema_aislado) -> None:
    pid = _presupuesto_real(esquema_aislado, enviar=False)
    editar = lambda uow: casos.reemplazar_items(  # noqa: E731
        uow, presupuesto_id=pid, numero=1, items=[_item("Editado", "55555")])
    enviar = lambda uow: casos.enviar_version(uow, presupuesto_id=pid, numero=1)  # noqa: E731

    with esquema_aislado() as sesion:
        version_id = sesion.execute(text(
            "select version_id from version_presupuesto where presupuesto_id = :p"),
            {"p": pid}).scalar()
    resultados = _en_paralelo(esquema_aislado, [editar, enviar], bloquear_presupuesto=pid)
    assert not isinstance(resultados[1], Exception), resultados[1]

    with esquema_aislado() as sesion:
        enviado_en, precios = sesion.execute(text("""
            select v.enviado_en, array_agg(i.precio_unitario order by i.item_id)
            from version_presupuesto v join item_presupuesto i using (version_id)
            where v.version_id = :v group by v.enviado_en"""), {"v": version_id}).one()
    assert enviado_en is not None
    if isinstance(resultados[0], Exception):
        # La edición llegó tarde: 409 (ya enviada) y los ítems son los originales.
        assert isinstance(resultados[0], ConflictoDeDatos), resultados[0]
        assert "ya fue enviada" in resultados[0].mensaje
        assert precios == [Decimal("10000.00")]
    else:
        # La edición ganó: se envió el contenido editado (nunca editado después).
        assert precios == [Decimal("55555.00")]
