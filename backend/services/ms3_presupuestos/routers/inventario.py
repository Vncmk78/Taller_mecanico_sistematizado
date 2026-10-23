"""Operaciones administrativas de compromiso y disponibilidad de inventario."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, status

from services.ms3_presupuestos.dependencies import (
    obtener_principal_actual,
    obtener_token_bearer,
    obtener_unidad_de_trabajo,
    requerir_roles,
)
from services.ms3_presupuestos.integracion_ms2 import (
    AplicacionDisponibilidadPendienteError,
    CoordinadorDisponibilidadRepuestos,
    ReservaRepuestosNoAplicableError,
    obtener_coordinador_disponibilidad_repuestos,
)
from services.ms3_presupuestos.persistencia import ConflictoDeDatos, UnidadDeTrabajo
from services.ms3_presupuestos.schemas.inventario import (
    DisponibilidadRepuestosRespuesta,
    DisponibilidadRepuestosVerificada,
)
from services.ms3_presupuestos.services.disponibilidad_repuestos import (
    RepuestosInsuficientesError,
    reservar_repuestos_aprobados,
    revertir_reserva_rechazada,
    verificar_reserva_confirmada,
)
from shared.auth import NombreRol, PrincipalAutenticado

router = APIRouter(prefix="/inventario", tags=["inventario"])
_solo_administrador = requerir_roles(NombreRol.ADMINISTRADOR)


@router.post(
    "/ordenes/{orden_id}/disponibilidad",
    response_model=DisponibilidadRepuestosRespuesta,
    summary="Reservar stock libre y continuar una orden",
    description=(
        "Solo Administrador. MS3 compara las cantidades enteras del alcance "
        "aprobado con el stock libre (stock físico menos compromisos de otras "
        "órdenes), registra los compromisos de forma idempotente y solicita a "
        "MS2 la transición auditada Esperando repuestos → En reparación."
    ),
    responses={
        401: {"description": "JWT ausente o inválido"},
        403: {"description": "Se requiere rol Administrador"},
        404: {"description": "Presupuesto u orden inexistente"},
        409: {"description": "Stock libre insuficiente o estado incompatible"},
        422: {"description": "Los repuestos deben estar expresados en unidades enteras"},
        503: {"description": "Reserva persistida; aplicación en MS2 pendiente de reintento"},
    },
)
def confirmar_disponibilidad(
    orden_id: int = Path(gt=0),
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
    principal: PrincipalAutenticado = Depends(_solo_administrador),
    token: str = Depends(obtener_token_bearer),
    coordinador: CoordinadorDisponibilidadRepuestos = Depends(
        obtener_coordinador_disponibilidad_repuestos
    ),
) -> DisponibilidadRepuestosRespuesta:
    try:
        reserva = reservar_repuestos_aprobados(
            uow, orden_id=orden_id, actor_usuario_id=principal.usuario_id,
        )
    except RepuestosInsuficientesError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"mensaje": exc.mensaje, "faltantes": exc.faltantes},
        ) from exc
    except ConflictoDeDatos as exc:
        raise HTTPException(status_code=exc.codigo_http, detail=exc.mensaje) from exc

    try:
        coordinador.aplicar(
            orden_id, str(reserva["clave_operacion"]), token
        )
    except ReservaRepuestosNoAplicableError as exc:
        # Un 4xx de MS2 se produce antes de confirmar su transacción, por lo que
        # el compromiso local puede liberarse con un movimiento compensatorio.
        revertir_reserva_rechazada(
            uow,
            orden_id=orden_id,
            clave_operacion=str(reserva["clave_operacion"]),
            actor_usuario_id=principal.usuario_id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MS2 rechazó el cambio de estado; la reserva se liberó con un movimiento compensatorio",
        ) from exc
    except AplicacionDisponibilidadPendienteError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "mensaje": "La reserva quedó registrada, pero MS2 no confirmó el cambio de estado",
                "orden_id": exc.orden_id,
                "clave_operacion": exc.clave_operacion,
                "reintento": f"/api/inventario/ordenes/{orden_id}/disponibilidad",
            },
        ) from exc
    return DisponibilidadRepuestosRespuesta.model_validate(reserva)


@router.get(
    "/ordenes/{orden_id}/disponibilidad/{clave_operacion}",
    response_model=DisponibilidadRepuestosVerificada,
    summary="Verificar una reserva antes de iniciar reparación en MS2",
    include_in_schema=False,
)
def verificar_disponibilidad(
    orden_id: int = Path(gt=0),
    clave_operacion: str = Path(min_length=1, max_length=100),
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
    _: PrincipalAutenticado = Depends(_solo_administrador),
) -> dict[str, object]:
    try:
        return verificar_reserva_confirmada(
            uow, orden_id=orden_id, clave_operacion=clave_operacion,
        )
    except ConflictoDeDatos as exc:
        raise HTTPException(status_code=409, detail=exc.mensaje) from exc
