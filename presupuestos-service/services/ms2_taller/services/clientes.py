"""Ciclo de vida local del perfil ``Cliente`` de MS2.

El ``usuario_id`` debe provenir de una identidad ya verificada por el contrato
de autenticación. Este módulo no conoce JWT ni publica endpoints: ofrece
operaciones explícitas para que el futuro flujo de registro/integración cree o
resuelva el perfil local sin acoplarlo al registro de vehículos.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from services.ms2_taller.models.cliente import Cliente

_RESTRICCION_USUARIO_UNICO = "uq_cliente_usuario_id"


class ClienteDuplicadoError(Exception):
    """Ya existe un perfil local para el ``usuario_id`` recibido."""


class PersistenciaClienteError(Exception):
    """La operación de persistencia del perfil no pudo completarse."""


def buscar_cliente_por_usuario_id(db: Session, usuario_id: int) -> Cliente | None:
    """Busca el perfil local de una identidad previamente verificada."""

    try:
        return db.scalar(select(Cliente).where(Cliente.usuario_id == usuario_id))
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaClienteError(
            "No fue posible resolver el perfil de cliente"
        ) from exc


def crear_cliente(
    db: Session,
    usuario_id: int,
    telefono: str | None = None,
) -> Cliente:
    """Crea explícitamente el perfil local para una identidad verificada."""

    try:
        cliente_existente = buscar_cliente_por_usuario_id(db, usuario_id)
        if cliente_existente is not None:
            raise ClienteDuplicadoError(
                "Ya existe un perfil de cliente para el usuario"
            )

        cliente = Cliente(usuario_id=usuario_id, telefono=telefono)
        db.add(cliente)
        db.flush()
        db.refresh(cliente)
        db.commit()
        return cliente
    except ClienteDuplicadoError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        if _es_conflicto_usuario_id(exc):
            raise ClienteDuplicadoError(
                "Ya existe un perfil de cliente para el usuario"
            ) from exc
        raise PersistenciaClienteError(
            "No fue posible crear el perfil de cliente"
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaClienteError(
            "No fue posible crear el perfil de cliente"
        ) from exc


def asegurar_cliente(
    db: Session,
    usuario_id: int,
    telefono: str | None = None,
) -> Cliente:
    """Obtiene el perfil existente o lo crea mediante una llamada explícita.

    Si dos procesos intentan crearlo simultáneamente, la restricción única
    decide el ganador y el segundo proceso recupera el perfil ya confirmado.
    La función no actualiza silenciosamente los datos de un perfil existente.
    """

    cliente = buscar_cliente_por_usuario_id(db, usuario_id)
    if cliente is not None:
        return cliente

    try:
        return crear_cliente(db, usuario_id, telefono)
    except ClienteDuplicadoError:
        cliente = buscar_cliente_por_usuario_id(db, usuario_id)
        if cliente is not None:
            return cliente
        raise


def _es_conflicto_usuario_id(exc: IntegrityError) -> bool:
    """Reconoce únicamente la restricción del usuario lógico de MS2."""

    error_original = exc.orig
    diagnostico = getattr(error_original, "diag", None)
    nombre_restriccion = getattr(diagnostico, "constraint_name", None)
    return (
        nombre_restriccion == _RESTRICCION_USUARIO_UNICO
        or _RESTRICCION_USUARIO_UNICO in str(error_original)
    )
