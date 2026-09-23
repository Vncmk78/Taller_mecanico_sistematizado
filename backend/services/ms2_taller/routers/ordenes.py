"""Router de creación, listado y detalle inicial de órdenes de trabajo."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from services.ms2_taller.db import get_db
from services.ms2_taller.dependencies import obtener_principal_actual
from services.ms2_taller.models.orden_trabajo import OrdenTrabajo
from services.ms2_taller.schemas.orden import OrdenCrear, OrdenRespuesta
from services.ms2_taller.services.ordenes import (
    OrdenNoEncontradaError,
    PersistenciaOrdenError,
    VehiculoNoEncontradoError,
    crear_orden,
    listar_ordenes,
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
