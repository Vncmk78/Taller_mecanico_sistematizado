"""Router para registro, consulta y actualización de vehículos."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from services.ms2_taller.db import get_db
from services.ms2_taller.models.cliente import Cliente
from services.ms2_taller.models.vehiculo import Vehiculo
from services.ms2_taller.schemas.vehiculo import (
    VehiculoActualizar,
    VehiculoCrear,
    VehiculoRespuesta,
)
from services.ms2_taller.services.vehiculos import (
    PatenteDuplicadaError,
    PersistenciaVehiculoError,
    VehiculoNoEncontradoError,
    actualizar_vehiculo_propio,
    crear_vehiculo,
    listar_vehiculos,
    obtener_vehiculo_propio,
)

ResolverClienteActual = Callable[..., Cliente]


def crear_router_vehiculos(
    resolver_cliente_actual: ResolverClienteActual,
) -> APIRouter:
    """Construye el router usando una resolución de identidad real y externa."""

    router = APIRouter(prefix="/vehiculos", tags=["vehículos"])

    @router.post(
        "",
        response_model=VehiculoRespuesta,
        status_code=status.HTTP_201_CREATED,
        summary="Registrar un vehículo",
        responses={
            status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
            status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Cliente"},
            status.HTTP_404_NOT_FOUND: {
                "description": "No existe el perfil Cliente local"
            },
            status.HTTP_409_CONFLICT: {
                "description": "La patente exacta ya está registrada"
            },
            status.HTTP_500_INTERNAL_SERVER_ERROR: {
                "description": "No fue posible completar la persistencia"
            },
        },
    )
    def registrar_vehiculo(
        body: VehiculoCrear,
        db: Session = Depends(get_db),
        cliente: Cliente = Depends(resolver_cliente_actual),
    ) -> Vehiculo:
        try:
            return crear_vehiculo(db, cliente, body)
        except PatenteDuplicadaError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except PersistenciaVehiculoError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No fue posible registrar el vehículo",
            ) from exc

    @router.get(
        "",
        response_model=list[VehiculoRespuesta],
        summary="Listar vehículos",
        responses={
            status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
            status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Cliente"},
            status.HTTP_404_NOT_FOUND: {
                "description": "No existe el perfil Cliente local"
            },
            status.HTTP_500_INTERNAL_SERVER_ERROR: {
                "description": "No fue posible completar la consulta"
            }
        },
    )
    def consultar_vehiculos(
        db: Session = Depends(get_db),
        cliente: Cliente = Depends(resolver_cliente_actual),
    ) -> list[Vehiculo]:
        try:
            return listar_vehiculos(db, cliente)
        except PersistenciaVehiculoError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No fue posible consultar los vehículos",
            ) from exc

    @router.get(
        "/{vehiculo_id}",
        response_model=VehiculoRespuesta,
        summary="Consultar un vehículo",
        responses={
            status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
            status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Cliente"},
            status.HTTP_404_NOT_FOUND: {"description": "Vehículo no encontrado"},
            status.HTTP_500_INTERNAL_SERVER_ERROR: {
                "description": "No fue posible completar la consulta"
            },
        },
    )
    def consultar_vehiculo(
        vehiculo_id: int,
        db: Session = Depends(get_db),
        cliente: Cliente = Depends(resolver_cliente_actual),
    ) -> Vehiculo:
        try:
            return obtener_vehiculo_propio(db, cliente, vehiculo_id)
        except VehiculoNoEncontradoError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehículo no encontrado",
            ) from exc
        except PersistenciaVehiculoError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No fue posible consultar el vehículo",
            ) from exc

    @router.patch(
        "/{vehiculo_id}",
        response_model=VehiculoRespuesta,
        summary="Actualizar parcialmente un vehículo",
        responses={
            status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
            status.HTTP_403_FORBIDDEN: {"description": "Se requiere rol Cliente"},
            status.HTTP_404_NOT_FOUND: {"description": "Vehículo no encontrado"},
            status.HTTP_500_INTERNAL_SERVER_ERROR: {
                "description": "No fue posible completar la actualización"
            },
        },
    )
    def actualizar_vehiculo(
        vehiculo_id: int,
        body: VehiculoActualizar,
        db: Session = Depends(get_db),
        cliente: Cliente = Depends(resolver_cliente_actual),
    ) -> Vehiculo:
        try:
            return actualizar_vehiculo_propio(db, cliente, vehiculo_id, body)
        except VehiculoNoEncontradoError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehículo no encontrado",
            ) from exc
        except PersistenciaVehiculoError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No fue posible actualizar el vehículo",
            ) from exc

    return router
