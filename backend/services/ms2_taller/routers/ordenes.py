"""Router de creación, listado y detalle inicial de órdenes de trabajo."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from services.ms2_taller.db import get_db
from services.ms2_taller.dependencies import obtener_principal_actual
from services.ms2_taller.models.historial_estado import HistorialEstado
from services.ms2_taller.models.orden_trabajo import OrdenTrabajo
from services.ms2_taller.schemas.orden import (
    AsignacionMecanicoActualizar,
    CambioEstadoSolicitud,
    HistorialEstadoRespuesta,
    OrdenCrear,
    OrdenRespuesta,
)
from services.ms2_taller.services.ordenes import (
    OrdenEstadoInvalidoError,
    OrdenEstadoNoAutorizadoError,
    OrdenNoEncontradaError,
    OrdenTerminalError,
    OrdenTransicionNoPermitidaError,
    PersistenciaOrdenError,
    VehiculoNoEncontradoError,
    asignar_mecanico,
    cambiar_estado_orden,
    crear_orden,
    listar_ordenes,
    obtener_historial_orden,
    obtener_orden_visible,
)
from shared.auth import NombreRol, PrincipalAutenticado

router_ordenes = APIRouter(prefix="/ordenes", tags=["órdenes"])


@router_ordenes.post(
    "",
    response_model=OrdenRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una orden de trabajo",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Administrador"},
        status.HTTP_404_NOT_FOUND: {"description": "Vehículo no encontrado"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la persistencia"
        },
    },
)
def registrar_orden(
    body: OrdenCrear,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> OrdenTrabajo:
    if NombreRol.ADMINISTRADOR not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para realizar esta operación",
        )

    try:
        return crear_orden(db, body.vehiculo_id, principal.usuario_id)
    except VehiculoNoEncontradoError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehículo no encontrado",
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible crear la orden",
        ) from exc


@router_ordenes.get(
    "",
    response_model=list[OrdenRespuesta],
    summary="Listar órdenes visibles",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la consulta"
        },
    },
)
def consultar_ordenes(
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> list[OrdenTrabajo]:
    try:
        return listar_ordenes(db, principal)
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible consultar las órdenes",
        ) from exc


@router_ordenes.get(
    "/{orden_id}",
    response_model=OrdenRespuesta,
    summary="Consultar una orden visible",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la consulta"
        },
    },
)
def consultar_orden(
    orden_id: int,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> OrdenTrabajo:
    try:
        return obtener_orden_visible(db, principal, orden_id)
    except OrdenNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada",
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible consultar la orden",
        ) from exc


@router_ordenes.get(
    "/{orden_id}/historial",
    response_model=list[HistorialEstadoRespuesta],
    summary="Consultar el historial de estados de una orden",
    description=(
        "Devuelve todos los registros por fecha/hora e identificador ascendente. "
        "Aplica la misma visibilidad del detalle; sin registros devuelve []."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la consulta"
        },
    },
)
def consultar_historial_orden(
    orden_id: int,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> list[HistorialEstado]:
    try:
        return obtener_historial_orden(db, principal, orden_id)
    except OrdenNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada",
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible consultar el historial de la orden",
        ) from exc


@router_ordenes.patch(
    "/{orden_id}/estado",
    response_model=OrdenRespuesta,
    summary="Cambiar el estado de una orden",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_403_FORBIDDEN: {
            "description": "Se requiere rol Administrador o ser el mecánico asignado"
        },
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada"},
        status.HTTP_409_CONFLICT: {
            "description": "La transición solicitada no está permitida o la orden es terminal"
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Estado de destino desconocido o datos inválidos"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la persistencia"
        },
    },
)
def cambiar_estado(
    orden_id: int,
    body: CambioEstadoSolicitud,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> OrdenTrabajo:
    try:
        return cambiar_estado_orden(
            db,
            orden_id=orden_id,
            estado_destino=body.estado_destino,
            principal=principal,
            observacion=body.observacion,
        )
    except OrdenNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada",
        ) from exc
    except OrdenEstadoNoAutorizadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except OrdenEstadoInvalidoError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except OrdenTransicionNoPermitidaError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible cambiar el estado de la orden",
        ) from exc


@router_ordenes.put(
    "/{orden_id}/mecanico",
    response_model=OrdenRespuesta,
    summary="Asignar o reasignar el mecánico responsable",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Administrador"},
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada"},
        status.HTTP_409_CONFLICT: {
            "description": (
                "Un administrador-mecánico no puede autoasignarse o la orden "
                "se encuentra en un estado terminal"
            )
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "No fue posible completar la persistencia"
        },
    },
)
def actualizar_mecanico_responsable(
    orden_id: int,
    body: AsignacionMecanicoActualizar,
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> OrdenTrabajo:
    if NombreRol.ADMINISTRADOR not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para realizar esta operación",
        )
    if (
        NombreRol.MECANICO in principal.roles
        and body.mecanico_id == principal.usuario_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un mecánico no puede autoasignarse una orden",
        )

    try:
        return asignar_mecanico(
            db,
            orden_id=orden_id,
            mecanico_id=body.mecanico_id,
            administrador_id=principal.usuario_id,
            observacion=body.observacion,
        )
    except OrdenNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada",
        ) from exc
    except OrdenTerminalError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible asignar el mecánico",
        ) from exc
