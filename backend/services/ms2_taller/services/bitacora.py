"""Bitácora de trabajo del mecánico: observaciones, acciones y repuestos.

A diferencia del historial de estados, cada entrada de la bitácora NO exige un
cambio de estado: documenta lo que el mecánico observa o ejecuta (RF-11). Cada
fila solo se inserta; la trazabilidad no se modifica ni se borra.

Autorización por recurso:
- Lectura: la misma visibilidad del detalle de la orden (``obtener_orden_visible``).
- Escritura: el Administrador o el mecánico asignado a esa orden. Un cliente
  propietario puede leer, pero no registrar entradas.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from services.ms2_taller.models.bitacora_orden import BitacoraOrden, BitacoraRepuesto
from services.ms2_taller.services.ordenes import (
    PersistenciaOrdenError,
    obtener_orden_visible,
)
from shared.auth import NombreRol, PrincipalAutenticado

_TIPOS_VALIDOS = ("observacion", "accion")


class BitacoraNoAutorizadaError(Exception):
    """La identidad autenticada no puede registrar entradas en esta orden."""


class BitacoraEntradaInvalidaError(Exception):
    """El tipo o la descripción de la entrada no son válidos."""


class BitacoraRepuestoInvalidoError(Exception):
    """Los repuestos declarados no son coherentes con la entrada o están vacíos."""


def listar_bitacora_orden(
    db: Session,
    principal: PrincipalAutenticado,
    orden_id: int,
) -> list[BitacoraOrden]:
    """Devuelve la bitácora cronológica de una orden visible al principal.

    Aplica la misma autorización por recurso del detalle: una orden inexistente
    o ajena responde el mismo error de recurso ausente.
    """

    obtener_orden_visible(db, principal, orden_id)
    try:
        consulta = (
            select(BitacoraOrden)
            .where(BitacoraOrden.orden_id == orden_id)
            # El id desempata filas creadas en el mismo instante.
            .order_by(BitacoraOrden.creado_en, BitacoraOrden.bitacora_id)
        )
        return list(db.scalars(consulta).all())
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaOrdenError(
            "No fue posible consultar la bitácora de la orden"
        ) from exc


def registrar_entrada_bitacora(
    db: Session,
    *,
    orden_id: int,
    principal: PrincipalAutenticado,
    tipo: str,
    descripcion: str,
    repuestos: Iterable[Mapping[str, object]] | None = None,
) -> BitacoraOrden:
    """Registra una observación o acción en la bitácora de una orden.

    La operación es atómica: la entrada y sus repuestos se confirman juntos o no
    se guarda nada. Una acción admite repuestos; una observación no. Una orden
    inexistente o ajena responde el mismo recurso ausente.
    """

    orden = obtener_orden_visible(db, principal, orden_id)
    if not _puede_registrar(orden.mecanico_actual_id, principal):
        raise BitacoraNoAutorizadaError(
            "Solo el mecánico asignado o un administrador pueden registrar la bitácora"
        )

    tipo = tipo.strip()
    if tipo not in _TIPOS_VALIDOS:
        raise BitacoraEntradaInvalidaError(
            "El tipo de entrada debe ser 'observacion' o 'accion'"
        )
    descripcion = descripcion.strip()
    if not descripcion:
        raise BitacoraEntradaInvalidaError(
            "La descripción no puede estar vacía ni contener solo espacios"
        )

    items = list(repuestos or [])
    if items and tipo != "accion":
        raise BitacoraRepuestoInvalidoError(
            "Solo una acción puede registrar repuestos utilizados"
        )
    repuestos_validados: list[BitacoraRepuesto] = []
    for item in items:
        nombre = str(item.get("nombre", "")).strip()
        cantidad = item.get("cantidad")
        if not nombre or not isinstance(cantidad, int) or cantidad <= 0:
            raise BitacoraRepuestoInvalidoError(
                "Cada repuesto requiere un nombre no vacío y una cantidad positiva"
            )
        repuestos_validados.append(BitacoraRepuesto(nombre=nombre, cantidad=cantidad))

    try:
        entrada = BitacoraOrden(
            orden_id=orden_id,
            autor_usuario_id=principal.usuario_id,
            tipo=tipo,
            descripcion=descripcion,
            repuestos=repuestos_validados,
        )
        db.add(entrada)
        db.flush()
        db.commit()
        return entrada
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaOrdenError(
            "No fue posible registrar la entrada de la bitácora"
        ) from exc


def _puede_registrar(
    mecanico_actual_id: int | None,
    principal: PrincipalAutenticado,
) -> bool:
    """El Administrador o el mecánico asignado pueden registrar la bitácora."""

    if NombreRol.ADMINISTRADOR in principal.roles:
        return True
    return (
        NombreRol.MECANICO in principal.roles
        and mecanico_actual_id == principal.usuario_id
    )
