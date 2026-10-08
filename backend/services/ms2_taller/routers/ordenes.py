"""Router de creación, listado y detalle inicial de órdenes de trabajo."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.orm import Session

from services.ms2_taller.db import get_db
from services.ms2_taller.dependencies import obtener_principal_actual, obtener_token_bearer
from services.ms2_taller.integracion_ms3 import (
    DecisionNoAplicableError, DecisionNoVisibleError, ServicioPresupuestosNoDisponibleError,
    VerificadorDecisiones, obtener_verificador_decisiones,
)
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
    OrdenObservacionInvalidaError,
    OrdenTerminalError,
    OrdenTransicionNoPermitidaError,
    PersistenciaOrdenError,
    VehiculoNoEncontradoError,
    asignar_mecanico,
    aplicar_decision_presupuesto,
    cambiar_estado_orden,
    crear_orden,
    listar_ordenes,
    obtener_historial_orden,
    obtener_orden_visible,
)
from shared.auth import NombreRol, PrincipalAutenticado
from shared.contratos_decisiones import AplicacionDecisionRespuesta, DecisionOrdenSolicitud

router_ordenes = APIRouter(prefix="/ordenes", tags=["órdenes"])


@router_ordenes.post(
    "/{orden_id}/decisiones-presupuesto", response_model=AplicacionDecisionRespuesta,
    summary="Aplicar una decisión inicial de presupuesto verificada en MS3",
    responses={
        401: {"description": "JWT ausente o inválido"},
        403: {"description": "Se requiere rol Cliente"},
        404: {"description": "Orden o decisión inexistente o ajena"},
        409: {"description": "Estado/evento incompatible o decisión no aplicable"},
        422: {"description": "Referencia inválida o cancelación sin motivo"},
        500: {"description": "Error de persistencia local"},
        503: {"description": "No fue posible verificar la decisión en MS3"},
    },
)
def aplicar_decision(
    body: DecisionOrdenSolicitud, orden_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    token: str = Depends(obtener_token_bearer),
    verificador: VerificadorDecisiones = Depends(obtener_verificador_decisiones),
) -> AplicacionDecisionRespuesta:
    try:
        return aplicar_decision_presupuesto(
            db, orden_id=orden_id, decision_id=body.decision_id,
            principal=principal, token=token, verificador=verificador,
        )
    except (OrdenNoEncontradaError, DecisionNoVisibleError) as exc:
        raise HTTPException(404, "Orden o decisión no encontrada") from exc
    except OrdenEstadoNoAutorizadoError as exc:
        raise HTTPException(403, str(exc)) from exc
    except (OrdenTransicionNoPermitidaError, DecisionNoAplicableError) as exc:
        raise HTTPException(409, str(exc)) from exc
    except OrdenObservacionInvalidaError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ServicioPresupuestosNoDisponibleError as exc:
        raise HTTPException(503, "No fue posible verificar la decisión en MS3") from exc
    except PersistenciaOrdenError as exc:
        raise HTTPException(500, "No fue posible aplicar la decisión") from exc


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
    response: Response,
    solo_propietario: bool = Query(
        default=False, description="Verificar propiedad del cliente, incluso con otros roles.",
    ),
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
) -> OrdenTrabajo:
    try:
        if solo_propietario:
            if NombreRol.CLIENTE not in principal.roles:
                raise OrdenNoEncontradaError("Orden no encontrada")
            # La visibilidad como personal no autoriza a decidir como cliente.
            principal = PrincipalAutenticado(
                principal.usuario_id, frozenset({NombreRol.CLIENTE}),
            )
        orden = obtener_orden_visible(db, principal, orden_id)
        if solo_propietario:
            response.headers["X-Orden-Propiedad-Verificada"] = "true"
        return orden
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
    description=(
        "La primera asignación (1 → 2) y la primera aprobación de presupuesto "
        "(3 → 4/5) requieren sus operaciones específicas y no admiten PATCH directo. "
        "Los demás pares conservan su comportamiento; este endpoint no garantiza "
        "las precondiciones pendientes de envío, repuestos, finalización, entrega o cancelación."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "JWT ausente o inválido"},
        status.HTTP_403_FORBIDDEN: {
            "description": "Se requiere rol Administrador o ser el mecánico asignado"
        },
        status.HTTP_404_NOT_FOUND: {"description": "Orden no encontrada"},
        status.HTTP_409_CONFLICT: {
            "description": "Transición no permitida, terminal o reservada a una operación específica"
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Estado de destino desconocido, cancelación sin motivo o datos inválidos"
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
    except (OrdenEstadoInvalidoError, OrdenObservacionInvalidaError) as exc:
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
