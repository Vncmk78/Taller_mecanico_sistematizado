"""Casos de uso de proveedores y repuestos (MS3, §4.6, RF-13/14/15).

Reglas:
- Proveedor: nombre único sin distinguir mayúsculas (409). No se borra si
  todavía tiene repuestos (409): primero se reasignan o se eliminan.
- Repuesto: nombre único dentro de su proveedor (409; la base lo asegura con
  `uq_repuesto_proveedor_nombre`). El stock NO se edita a mano: el alta con
  stock inicial deja un movimiento de "ingreso" y los cambios posteriores
  van por movimientos de inventario.
- Cambiar el umbral particular deja una fila en historial_umbral con el valor
  anterior, el nuevo, el administrador y la observación.
- Un repuesto con historial (movimientos, ítems de presupuesto o cambios de
  umbral) no se borra (409): es auditoría.
- Trazabilidad Repuesto–Proveedor (0007_ms3): el alta y cada cambio de
  proveedor quedan en historial_proveedor_repuesto con el administrador y la
  observación; un proveedor que ya abasteció repuestos (historial o ingresos)
  no se borra (409).

Cada escritura es una transacción (`with uow.transaccion()`).
"""
from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from sqlalchemy import exists, select

from services.ms3_presupuestos.models import (
    HistorialProveedorRepuesto,
    HistorialUmbral,
    MovimientoInventario,
    Proveedor,
    Repuesto,
)
from services.ms3_presupuestos.persistencia import ConflictoDeDatos, UnidadDeTrabajo
from services.ms3_presupuestos.persistencia.repositorios import FiltroRepuestos, OrdenRepuestos
from services.ms3_presupuestos.schemas.catalogo import (
    ProveedorActualizar,
    ProveedorDetalle,
    ProveedorSalida,
    RepuestoActualizar,
    RepuestoCrear,
    RepuestoSalida,
)

# ---------------------------------------------------------------- proveedores --


def crear_proveedor(uow: UnidadDeTrabajo, *, nombre: str, contacto: str,
                    tipo_distribuidor: str = "generico") -> Proveedor:
    with uow.transaccion():
        _exigir_proveedor_libre(uow, nombre)
        return uow.proveedores.agregar(Proveedor(nombre=nombre, contacto=contacto,
                                                 tipo_distribuidor=tipo_distribuidor))


def actualizar_proveedor(
    uow: UnidadDeTrabajo, proveedor_id: int, cambios: ProveedorActualizar
) -> Proveedor:
    with uow.transaccion():
        proveedor = uow.proveedores.obtener_o_error(proveedor_id)
        if cambios.nombre is not None:
            _exigir_proveedor_libre(uow, cambios.nombre, excepto=proveedor_id)
            proveedor.nombre = cambios.nombre
        if cambios.contacto is not None:
            proveedor.contacto = cambios.contacto
        if cambios.tipo_distribuidor is not None:
            proveedor.tipo_distribuidor = cambios.tipo_distribuidor
        uow.sesion.flush()
    return proveedor


def eliminar_proveedor(uow: UnidadDeTrabajo, proveedor_id: int) -> None:
    with uow.transaccion():
        proveedor = uow.proveedores.obtener_o_error(proveedor_id)
        if proveedor.repuestos:
            raise ConflictoDeDatos(
                f"El proveedor {proveedor.nombre!r} tiene {len(proveedor.repuestos)} "
                "repuesto(s); reasígnelos a otro proveedor antes de eliminarlo"
            )
        if _abastecio_repuestos(uow, proveedor_id):
            raise ConflictoDeDatos(
                f"El proveedor {proveedor.nombre!r} figura en la trazabilidad de repuestos "
                "(historial de proveedores o ingresos de stock); no se elimina para conservarla"
            )
        uow.sesion.delete(proveedor)
        uow.sesion.flush()


def listar_proveedores(
    uow: UnidadDeTrabajo, *, texto: str | None, con_repuestos: bool | None = None,
    desde: int, limite: int, tipo_distribuidor: str | None = None,
) -> tuple[int, Sequence[Proveedor]]:
    filtros = dict(texto=texto, con_repuestos=con_repuestos, tipo_distribuidor=tipo_distribuidor)
    return (uow.proveedores.contar_busqueda(**filtros),
            uow.proveedores.buscar(**filtros, desde=desde, limite=limite))


def _abastecio_repuestos(uow: UnidadDeTrabajo, proveedor_id: int) -> bool:
    en_historial = select(HistorialProveedorRepuesto.historial_id).where(
        (HistorialProveedorRepuesto.proveedor_nuevo_id == proveedor_id)
        | (HistorialProveedorRepuesto.proveedor_anterior_id == proveedor_id))
    en_ingresos = select(MovimientoInventario.movimiento_id).where(
        MovimientoInventario.proveedor_id == proveedor_id)
    return uow.sesion.scalar(select(exists(en_historial) | exists(en_ingresos))) or False


def _exigir_proveedor_libre(uow: UnidadDeTrabajo, nombre: str, *, excepto: int | None = None) -> None:
    existente = uow.proveedores.con_nombre_similar(nombre, excepto=excepto)
    if existente is not None:
        raise ConflictoDeDatos(f"Ya existe el proveedor {existente.nombre!r}")


# ------------------------------------------------------------------ repuestos --


def crear_repuesto(uow: UnidadDeTrabajo, datos: RepuestoCrear, *, administrador_id: int) -> Repuesto:
    with uow.transaccion():
        proveedor = uow.proveedores.obtener_o_error(datos.proveedor_id)
        _exigir_repuesto_libre(uow, proveedor.proveedor_id, datos.nombre)
        nuevo = Repuesto(
            proveedor=proveedor, nombre=datos.nombre, stock=datos.stock_inicial,
            umbral_particular=datos.umbral_particular,
        )
        # Para el historial de proveedores (alta).
        nuevo.registrado_por_id_traza = administrador_id
        nuevo.observacion_traza = "Alta del repuesto"
        repuesto = uow.repuestos.agregar(nuevo)
        if datos.stock_inicial > 0:
            uow.movimientos.agregar(MovimientoInventario(
                clave_operacion=f"alta-{repuesto.repuesto_id}-{uuid4().hex[:12]}",
                repuesto=repuesto, tipo="ingreso", cantidad=datos.stock_inicial,
                registrado_por_id=administrador_id,
            ))
        if datos.umbral_particular is not None:
            uow.sesion.add(HistorialUmbral(
                repuesto_id=repuesto.repuesto_id, valor_anterior=None,
                valor_nuevo=datos.umbral_particular, administrador_id=administrador_id,
                observacion="Umbral particular inicial",
            ))
            uow.sesion.flush()
    return repuesto


def actualizar_repuesto(
    uow: UnidadDeTrabajo, repuesto_id: int, cambios: RepuestoActualizar, *, administrador_id: int
) -> Repuesto:
    enviados = cambios.model_fields_set
    with uow.transaccion():
        repuesto = uow.repuestos.obtener_para_actualizar(repuesto_id)
        proveedor_id = repuesto.proveedor_id
        if "proveedor_id" in enviados and cambios.proveedor_id is not None:
            proveedor_id = uow.proveedores.obtener_o_error(cambios.proveedor_id).proveedor_id
        nombre = cambios.nombre if cambios.nombre is not None else repuesto.nombre
        if proveedor_id != repuesto.proveedor_id or nombre != repuesto.nombre:
            _exigir_repuesto_libre(uow, proveedor_id, nombre, excepto=repuesto_id)
            # Un cambio de proveedor queda en el historial (evento del modelo).
            repuesto.registrado_por_id_traza = administrador_id
            repuesto.observacion_traza = cambios.observacion
            repuesto.proveedor_id = proveedor_id
            repuesto.nombre = nombre

        if "umbral_particular" in enviados and cambios.umbral_particular != repuesto.umbral_particular:
            uow.sesion.add(HistorialUmbral(
                repuesto_id=repuesto_id, valor_anterior=repuesto.umbral_particular,
                valor_nuevo=cambios.umbral_particular, administrador_id=administrador_id,
                observacion=cambios.observacion,
            ))
            repuesto.umbral_particular = cambios.umbral_particular
        uow.sesion.flush()
        uow.sesion.refresh(repuesto)
    return repuesto


def eliminar_repuesto(uow: UnidadDeTrabajo, repuesto_id: int) -> None:
    with uow.transaccion():
        repuesto = uow.repuestos.obtener_para_actualizar(repuesto_id)
        if uow.repuestos.tiene_historial(repuesto_id):
            raise ConflictoDeDatos(
                f"El repuesto {repuesto.nombre!r} tiene movimientos, presupuestos o cambios "
                "de umbral registrados; no se elimina para conservar la trazabilidad"
            )
        proveedor = repuesto.proveedor
        uow.sesion.delete(repuesto)
        uow.sesion.flush()
        # La base borró su historial (CASCADE): la sesión no debe recordar el repuesto.
        uow.sesion.expire(proveedor, ["repuestos"])


def umbral_general(uow: UnidadDeTrabajo) -> int | None:
    vigente = uow.parametros.vigente()
    return vigente.umbral_general if vigente else None


def listar_repuestos(
    uow: UnidadDeTrabajo, *, proveedor_id: int | None, texto: str | None,
    solo_bajo_umbral: bool, desde: int, limite: int,
    con_stock: bool | None = None, orden: OrdenRepuestos = "nombre",
) -> tuple[int, int | None, Sequence[Repuesto]]:
    general = umbral_general(uow)
    filtro = FiltroRepuestos(proveedor_id=proveedor_id, texto=texto,
                             solo_bajo_umbral=solo_bajo_umbral, umbral_general=general,
                             con_stock=con_stock, orden=orden)
    return (uow.repuestos.contar_busqueda(filtro), general,
            uow.repuestos.buscar(filtro, desde=desde, limite=limite))


def _exigir_repuesto_libre(
    uow: UnidadDeTrabajo, proveedor_id: int, nombre: str, *, excepto: int | None = None
) -> None:
    existente = uow.repuestos.con_nombre_similar(proveedor_id, nombre, excepto=excepto)
    if existente is not None:
        raise ConflictoDeDatos(
            f"El proveedor ya tiene el repuesto {existente.nombre!r} (id {existente.repuesto_id})"
        )


# ------------------------------------------------------ ORM → contrato HTTP --


def a_repuesto(repuesto: Repuesto, general: int | None) -> RepuestoSalida:
    efectivo = repuesto.umbral_particular if repuesto.umbral_particular is not None else general
    return RepuestoSalida(
        repuesto_id=repuesto.repuesto_id, nombre=repuesto.nombre,
        proveedor_id=repuesto.proveedor_id, proveedor_nombre=repuesto.proveedor.nombre,
        proveedor_tipo_distribuidor=repuesto.proveedor.tipo_distribuidor,
        stock=repuesto.stock, umbral_particular=repuesto.umbral_particular,
        umbral_efectivo=efectivo,
        bajo_umbral=efectivo is not None and repuesto.stock < efectivo,
    )


def a_proveedor(proveedor: Proveedor) -> ProveedorSalida:
    return ProveedorSalida(proveedor_id=proveedor.proveedor_id, nombre=proveedor.nombre,
                           contacto=proveedor.contacto,
                           tipo_distribuidor=proveedor.tipo_distribuidor,
                           cantidad_repuestos=len(proveedor.repuestos))


def a_proveedor_detalle(proveedor: Proveedor, general: int | None) -> ProveedorDetalle:
    repuestos = sorted(proveedor.repuestos, key=lambda r: (r.nombre.lower(), r.repuesto_id))
    return ProveedorDetalle(**a_proveedor(proveedor).model_dump(),
                            repuestos=[a_repuesto(r, general) for r in repuestos])
