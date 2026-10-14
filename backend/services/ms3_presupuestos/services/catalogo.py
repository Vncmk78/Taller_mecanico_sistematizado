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

Cada escritura es una transacción (`with uow.transaccion()`).
"""
from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from services.ms3_presupuestos.models import (
    HistorialUmbral,
    MovimientoInventario,
    Proveedor,
    Repuesto,
)
from services.ms3_presupuestos.persistencia import ConflictoDeDatos, UnidadDeTrabajo
from services.ms3_presupuestos.schemas.catalogo import (
    ProveedorActualizar,
    ProveedorDetalle,
    ProveedorSalida,
    RepuestoActualizar,
    RepuestoCrear,
    RepuestoSalida,
)

# ---------------------------------------------------------------- proveedores --


def crear_proveedor(uow: UnidadDeTrabajo, *, nombre: str, contacto: str) -> Proveedor:
    with uow.transaccion():
        _exigir_proveedor_libre(uow, nombre)
        return uow.proveedores.agregar(Proveedor(nombre=nombre, contacto=contacto))


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
        uow.sesion.delete(proveedor)
        uow.sesion.flush()


def listar_proveedores(
    uow: UnidadDeTrabajo, *, texto: str | None, desde: int, limite: int
) -> tuple[int, Sequence[Proveedor]]:
    return (uow.proveedores.contar_busqueda(texto=texto),
            uow.proveedores.buscar(texto=texto, desde=desde, limite=limite))


def _exigir_proveedor_libre(uow: UnidadDeTrabajo, nombre: str, *, excepto: int | None = None) -> None:
    existente = uow.proveedores.con_nombre_similar(nombre, excepto=excepto)
    if existente is not None:
        raise ConflictoDeDatos(f"Ya existe el proveedor {existente.nombre!r}")


# ------------------------------------------------------------------ repuestos --


def crear_repuesto(uow: UnidadDeTrabajo, datos: RepuestoCrear, *, administrador_id: int) -> Repuesto:
    with uow.transaccion():
        proveedor = uow.proveedores.obtener_o_error(datos.proveedor_id)
        _exigir_repuesto_libre(uow, proveedor.proveedor_id, datos.nombre)
        repuesto = uow.repuestos.agregar(Repuesto(
            proveedor=proveedor, nombre=datos.nombre, stock=datos.stock_inicial,
            umbral_particular=datos.umbral_particular,
        ))
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
        uow.sesion.delete(repuesto)
        uow.sesion.flush()


def umbral_general(uow: UnidadDeTrabajo) -> int | None:
    vigente = uow.parametros.vigente()
    return vigente.umbral_general if vigente else None


def listar_repuestos(
    uow: UnidadDeTrabajo, *, proveedor_id: int | None, texto: str | None,
    solo_bajo_umbral: bool, desde: int, limite: int,
) -> tuple[int, int | None, Sequence[Repuesto]]:
    general = umbral_general(uow)
    filtros = dict(proveedor_id=proveedor_id, texto=texto,
                   solo_bajo_umbral=solo_bajo_umbral, umbral_general=general)
    return (uow.repuestos.contar_busqueda(**filtros), general,
            uow.repuestos.buscar(**filtros, desde=desde, limite=limite))


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
        stock=repuesto.stock, umbral_particular=repuesto.umbral_particular,
        umbral_efectivo=efectivo,
        bajo_umbral=efectivo is not None and repuesto.stock < efectivo,
    )


def a_proveedor(proveedor: Proveedor) -> ProveedorSalida:
    return ProveedorSalida(proveedor_id=proveedor.proveedor_id, nombre=proveedor.nombre,
                           contacto=proveedor.contacto,
                           cantidad_repuestos=len(proveedor.repuestos))


def a_proveedor_detalle(proveedor: Proveedor, general: int | None) -> ProveedorDetalle:
    repuestos = sorted(proveedor.repuestos, key=lambda r: (r.nombre.lower(), r.repuesto_id))
    return ProveedorDetalle(**a_proveedor(proveedor).model_dump(),
                            repuestos=[a_repuesto(r, general) for r in repuestos])
