"""Lógica de registro, consulta y actualización de vehículos.

Este módulo no conoce JWT, headers ni FastAPI. Recibe un ``Cliente`` que ya
fue resuelto internamente y concentra las operaciones de persistencia para que
la futura integración de autenticación no obligue a reescribirlas.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from services.ms2_taller.models.cliente import Cliente
from services.ms2_taller.models.vehiculo import Vehiculo
from services.ms2_taller.schemas.vehiculo import VehiculoActualizar, VehiculoCrear

_RESTRICCION_PATENTE_UNICA = "uq_vehiculo_patente"


class PatenteDuplicadaError(Exception):
    """La patente exacta ya se encuentra registrada."""


class PersistenciaVehiculoError(Exception):
    """La operación de persistencia no pudo completarse de forma segura."""


class VehiculoNoEncontradoError(Exception):
    """No existe un vehículo propio que coincida con el identificador."""


def crear_vehiculo(
    db: Session,
    cliente: Cliente,
    datos: VehiculoCrear,
) -> Vehiculo:
    """Registra un vehículo para un ``Cliente`` ya resuelto internamente."""

    try:
        patente_existente = db.scalar(
            select(Vehiculo.vehiculo_id)
            .where(Vehiculo.patente == datos.patente)
            .limit(1)
        )
        if patente_existente is not None:
            raise PatenteDuplicadaError("La patente ya está registrada")

        vehiculo = Vehiculo(
            cliente_id=cliente.cliente_id,
            patente=datos.patente,
            marca=datos.marca,
            modelo=datos.modelo,
            anio=datos.anio,
            kilometraje=datos.kilometraje,
        )
        db.add(vehiculo)
        db.flush()
        db.refresh(vehiculo)
        db.commit()
        return vehiculo
    except PatenteDuplicadaError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        if _es_conflicto_patente(exc):
            raise PatenteDuplicadaError("La patente ya está registrada") from exc
        raise PersistenciaVehiculoError(
            "No fue posible registrar el vehículo"
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaVehiculoError(
            "No fue posible registrar el vehículo"
        ) from exc


def listar_vehiculos(db: Session, cliente: Cliente) -> list[Vehiculo]:
    """Lista únicamente los vehículos del ``Cliente`` recibido."""

    try:
        consulta = (
            select(Vehiculo)
            .where(Vehiculo.cliente_id == cliente.cliente_id)
            .order_by(Vehiculo.vehiculo_id)
        )
        return list(db.scalars(consulta).all())
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaVehiculoError(
            "No fue posible consultar los vehículos"
        ) from exc


def obtener_vehiculo_propio(
    db: Session,
    cliente: Cliente,
    vehiculo_id: int,
) -> Vehiculo:
    """Obtiene un vehículo solo si pertenece al Cliente recibido."""

    try:
        vehiculo = db.scalar(
            select(Vehiculo).where(
                Vehiculo.vehiculo_id == vehiculo_id,
                Vehiculo.cliente_id == cliente.cliente_id,
            )
        )
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaVehiculoError(
            "No fue posible consultar el vehículo"
        ) from exc

    if vehiculo is None:
        raise VehiculoNoEncontradoError("Vehículo no encontrado")
    return vehiculo


def actualizar_vehiculo_propio(
    db: Session,
    cliente: Cliente,
    vehiculo_id: int,
    datos: VehiculoActualizar,
) -> Vehiculo:
    """Actualiza únicamente los campos enviados de un vehículo propio."""

    vehiculo = obtener_vehiculo_propio(db, cliente, vehiculo_id)
    try:
        for campo, valor in datos.model_dump(exclude_unset=True).items():
            setattr(vehiculo, campo, valor)

        db.flush()
        db.refresh(vehiculo)
        db.commit()
        return vehiculo
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaVehiculoError(
            "No fue posible actualizar el vehículo"
        ) from exc


def _es_conflicto_patente(exc: IntegrityError) -> bool:
    """Reconoce la restricción de patente sin clasificar otras fallas como 409."""

    error_original = exc.orig
    diagnostico = getattr(error_original, "diag", None)
    nombre_restriccion = getattr(diagnostico, "constraint_name", None)
    return (
        nombre_restriccion == _RESTRICCION_PATENTE_UNICA
        or _RESTRICCION_PATENTE_UNICA in str(error_original)
    )
