"""Rutas de solicitud y consulta; registrar antes de /ordenes/{orden_id}."""
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.orm import Session

from services.ms2_taller.db import get_db
from services.ms2_taller.dependencies import obtener_principal_actual
from services.ms2_taller.schemas.nueva_atencion import (
    NuevaAtencionSolicitud, SituacionNuevaAtencion,
    SolicitudNuevaAtencionRespuesta, SolicitudesNuevaAtencionRespuesta,
    RevisionNuevaAtencionSolicitud, GeneracionNuevaAtencionSolicitud, GeneracionNuevaAtencionRespuesta,
)
from services.ms2_taller.services.nuevas_atenciones import (
    NuevaAtencionConflictoError, NuevaAtencionInvalidaError,
    NuevaAtencionNoAutorizadaError, NuevaAtencionNoEncontradaError,
    PersistenciaNuevaAtencionError,
    listar_nuevas_atenciones, obtener_nueva_atencion, solicitar_nueva_atencion,
    revisar_nueva_atencion, generar_orden_nueva_atencion,
)
from shared.auth import PrincipalAutenticado

router_nuevas_atenciones = APIRouter(prefix="/ordenes", tags=["Órdenes"])

_ERRORES = {
    401: {"description": "JWT ausente o inválido"},
    403: {"description": "Rol no autorizado"},
    500: {"description": "No fue posible completar la operación"},
}


def _error_http(exc: Exception) -> HTTPException:
    if isinstance(exc, NuevaAtencionNoAutorizadaError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, NuevaAtencionNoEncontradaError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, NuevaAtencionConflictoError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, NuevaAtencionInvalidaError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router_nuevas_atenciones.get(
    "/nuevas-atenciones", response_model=SolicitudesNuevaAtencionRespuesta,
    summary="Listar solicitudes de nueva atención visibles",
    description="Cliente ve las propias; Administrador todas, también si tiene varios roles.",
    responses=_ERRORES,
)
def consultar_nuevas_atenciones(
    situacion: SituacionNuevaAtencion | None = Query(default=None),
    orden_cancelada_id: int | None = Query(default=None, gt=0),
    orden_generada_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
):
    try:
        items, total = listar_nuevas_atenciones(
            db, principal=principal, situacion=situacion, orden_cancelada_id=orden_cancelada_id,
            orden_generada_id=orden_generada_id, limit=limit, offset=offset,
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}
    except (NuevaAtencionNoAutorizadaError, PersistenciaNuevaAtencionError) as exc:
        raise _error_http(exc) from exc


@router_nuevas_atenciones.get(
    "/nuevas-atenciones/{solicitud_id}", response_model=SolicitudNuevaAtencionRespuesta,
    summary="Consultar una solicitud de nueva atención visible",
    responses={**_ERRORES, 404: {"description": "Solicitud inexistente o ajena"}},
)
def consultar_nueva_atencion(
    solicitud_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
):
    try:
        return obtener_nueva_atencion(db, solicitud_id=solicitud_id, principal=principal)
    except (NuevaAtencionNoAutorizadaError, NuevaAtencionNoEncontradaError,
            PersistenciaNuevaAtencionError) as exc:
        raise _error_http(exc) from exc


@router_nuevas_atenciones.post(
    "/{orden_id}/nueva-atencion", response_model=SolicitudNuevaAtencionRespuesta, status_code=201,
    summary="Solicitar nueva atención de una orden cancelada propia",
    description=(
        "Solo Cliente propietario, incluso multirrol. 201 al crear; 200 al repetir "
        "la misma descripción de una pendiente. No crea orden, ingreso ni reserva."
    ),
    responses={**_ERRORES,
        200: {"model": SolicitudNuevaAtencionRespuesta, "description": "Pendiente idéntica ya registrada"},
        404: {"description": "Orden inexistente o ajena"},
        409: {"description": "Orden no cancelada o solicitud pendiente/aceptada existente"},
    },
)
def registrar_nueva_atencion(
    body: NuevaAtencionSolicitud,
    response: Response,
    orden_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
):
    try:
        solicitud, creada = solicitar_nueva_atencion(
            db, orden_id=orden_id, principal=principal, descripcion=body.descripcion,
        )
        response.status_code = 201 if creada else 200
        return solicitud
    except (NuevaAtencionNoAutorizadaError, NuevaAtencionNoEncontradaError,
            NuevaAtencionConflictoError, NuevaAtencionInvalidaError,
            PersistenciaNuevaAtencionError) as exc:
        raise _error_http(exc) from exc


@router_nuevas_atenciones.post(
    "/nuevas-atenciones/{solicitud_id}/revision", response_model=SolicitudNuevaAtencionRespuesta,
    summary="Confirmar revisión administrativa de nueva atención",
    description="Administrador, incluida autorrevisión multirrol. Una revisión confirmada no se edita; repetir el mismo contenido conserva fecha y revisor.",
    responses={**_ERRORES, 404: {"description": "Solicitud no encontrada"}, 409: {"description": "Revisión ya confirmada con otro contenido"}},
)
def confirmar_revision_nueva_atencion(
    body: RevisionNuevaAtencionSolicitud,
    solicitud_id: int = Path(gt=0), db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
):
    try:
        return revisar_nueva_atencion(db, solicitud_id=solicitud_id, principal=principal,
                                     decision=body.decision, respuesta=body.respuesta)
    except (NuevaAtencionNoAutorizadaError, NuevaAtencionNoEncontradaError,
            NuevaAtencionConflictoError, NuevaAtencionInvalidaError, PersistenciaNuevaAtencionError) as exc:
        raise _error_http(exc) from exc


@router_nuevas_atenciones.post(
    "/nuevas-atenciones/{solicitud_id}/orden", response_model=GeneracionNuevaAtencionRespuesta, status_code=201,
    summary="Generar la orden vinculada a una solicitud aceptada",
    description="Administrador. Body vacío obligatorio. Orden y vínculo se guardan juntos. Repetir devuelve la misma asociación sin crear otra orden.",
    responses={**_ERRORES, 200: {"model": GeneracionNuevaAtencionRespuesta, "description": "Orden ya generada"},
               404: {"description": "Solicitud no encontrada"}, 409: {"description": "Solicitud/antecedente incompatible, orden activa o rechazo de cupo"}},
)
def confirmar_orden_nueva_atencion(
    body: GeneracionNuevaAtencionSolicitud, response: Response,
    solicitud_id: int = Path(gt=0), db: Session = Depends(get_db),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
):
    try:
        solicitud, orden, creada = generar_orden_nueva_atencion(db, solicitud_id=solicitud_id, principal=principal)
        response.status_code = 201 if creada else 200
        return {"solicitud": solicitud, "orden": orden}
    except (NuevaAtencionNoAutorizadaError, NuevaAtencionNoEncontradaError,
            NuevaAtencionConflictoError, PersistenciaNuevaAtencionError) as exc:
        raise _error_http(exc) from exc
