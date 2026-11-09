"""Recepción de eventos internos y bandeja personal de notificaciones."""
from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from services.ms1_auth.config import settings
from services.ms1_auth.db import get_db
from services.ms1_auth.dependencies import obtener_principal_actual
from services.ms1_auth.schemas.notificacion import (
    EventoEstadoOrden,
    EventoRecibidoRespuesta,
    NotificacionRespuesta,
    EventoRevisionNuevaAtencion,
    EventoSolicitudNuevaAtencion,
    EventoPersonalRecibidoRespuesta,
)
from services.ms1_auth.services.notificaciones import (
    DestinatarioNotificacionInvalidoError,
    PersistenciaNotificacionError,
    listar_notificaciones,
    marcar_leida,
    contar_notificaciones,
    recibir_evento_estado_orden,
    recibir_evento_revision_nueva_atencion,
    recibir_solicitud_nueva_atencion,
)
from shared.auth import PrincipalAutenticado

router_notificaciones = APIRouter(tags=["notificaciones"])


def _validar_credencial_servicio(x_service_token: str | None) -> None:
    secreto = settings.EVENT_SHARED_SECRET
    if secreto is None:
        raise HTTPException(status_code=503, detail="La recepción interna de eventos no está configurada")
    if x_service_token is None or not hmac.compare_digest(x_service_token, secreto.get_secret_value()):
        raise HTTPException(status_code=401, detail="Credencial de servicio inválida", headers={"WWW-Authenticate": "Service"})


@router_notificaciones.post(
    "/interno/eventos/ordenes/estado",
    response_model=EventoRecibidoRespuesta,
    summary="Registrar un evento de cambio de estado de orden desde MS2",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Secreto de servicio ausente o inválido"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Destinatario o payload inválido"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Secreto interno no configurado"},
    },
)
def recibir_evento_estado(
    evento: EventoEstadoOrden,
    x_service_token: str | None = Header(default=None, alias="X-Service-Token"),
    db: Session = Depends(get_db),
) -> EventoRecibidoRespuesta:
    _validar_credencial_servicio(x_service_token)
    try:
        notificacion, duplicado = recibir_evento_estado_orden(db, evento)
        return EventoRecibidoRespuesta(
            notificacion_id=notificacion.notificacion_id,
            evento_id=notificacion.evento_id,
            duplicado=duplicado,
        )
    except DestinatarioNotificacionInvalidoError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El destinatario no es un cliente activo de MS1",
        ) from exc
    except PersistenciaNotificacionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible registrar la notificación",
        ) from exc


@router_notificaciones.post(
    "/interno/eventos/nuevas-atenciones/revision", response_model=EventoRecibidoRespuesta,
    summary="Recibir una revisión de nueva atención confirmada por MS2",
    responses={401: {"description": "Credencial de servicio inválida"},
               422: {"description": "Evento o destinatario inválido"},
               503: {"description": "Recepción interna no configurada"}},
)
def recibir_revision_nueva_atencion(
    evento: EventoRevisionNuevaAtencion,
    x_service_token: str | None = Header(default=None, alias="X-Service-Token"),
    db: Session = Depends(get_db),
) -> EventoRecibidoRespuesta:
    _validar_credencial_servicio(x_service_token)
    try:
        aviso, duplicado = recibir_evento_revision_nueva_atencion(db, evento)
        return EventoRecibidoRespuesta(notificacion_id=aviso.notificacion_id, evento_id=aviso.evento_id, duplicado=duplicado)
    except DestinatarioNotificacionInvalidoError as exc:
        raise HTTPException(status_code=422, detail="El destinatario no es un cliente activo de MS1") from exc
    except PersistenciaNotificacionError as exc:
        raise HTTPException(status_code=500, detail="No fue posible registrar la notificación") from exc


@router_notificaciones.post("/interno/eventos/nuevas-atenciones/solicitud",
    response_model=EventoPersonalRecibidoRespuesta, summary="Avisar una solicitud nueva al personal administrador")
def recibir_solicitud(evento: EventoSolicitudNuevaAtencion,
    x_service_token: str | None = Header(default=None, alias="X-Service-Token"),
    db: Session = Depends(get_db)) -> EventoPersonalRecibidoRespuesta:
    _validar_credencial_servicio(x_service_token)
    try:
        nuevas, existentes = recibir_solicitud_nueva_atencion(db, evento)
        return EventoPersonalRecibidoRespuesta(evento_id=evento.evento_id, creadas=nuevas, existentes=existentes)
    except PersistenciaNotificacionError as exc:
        raise HTTPException(status_code=500, detail="No fue posible registrar los avisos de la solicitud") from exc


@router_notificaciones.get(
    "/notificaciones",
    response_model=list[NotificacionRespuesta],
    summary="Consultar las notificaciones del usuario autenticado",
)
def consultar_notificaciones(
    response: Response,
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    limite: int = Query(default=50, ge=1, le=100),
    solo_no_leidas: bool = Query(default=False),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[NotificacionRespuesta]:
    try:
        total, no_leidas = contar_notificaciones(db, destinatario_id=principal.usuario_id)
        response.headers["X-Notificaciones-Total"] = str(no_leidas if solo_no_leidas else total)
        response.headers["X-Notificaciones-No-Leidas"] = str(no_leidas)
        return listar_notificaciones(
            db,
            destinatario_id=principal.usuario_id,
            limite=limite,
            offset=offset,
            solo_no_leidas=solo_no_leidas,
        )
    except PersistenciaNotificacionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible consultar las notificaciones",
        ) from exc


@router_notificaciones.patch("/notificaciones/leer-todas", status_code=204,
                             summary="Marcar como leídos los avisos propios")
def leer_todas(principal: PrincipalAutenticado = Depends(obtener_principal_actual),
               db: Session = Depends(get_db)) -> None:
    try:
        marcar_leida(db, destinatario_id=principal.usuario_id)
    except PersistenciaNotificacionError as exc:
        raise HTTPException(status_code=500, detail="No fue posible marcar las notificaciones") from exc


@router_notificaciones.patch("/notificaciones/{notificacion_id}/leer", status_code=204,
                             summary="Marcar un aviso propio como leído", responses={404: {"description": "Aviso inexistente o ajeno"}})
def leer_notificacion(notificacion_id: int,
                      principal: PrincipalAutenticado = Depends(obtener_principal_actual),
                      db: Session = Depends(get_db)) -> None:
    if notificacion_id <= 0:
        raise HTTPException(status_code=422, detail="Identificador inválido")
    try:
        if not marcar_leida(db, destinatario_id=principal.usuario_id, notificacion_id=notificacion_id):
            raise HTTPException(status_code=404, detail="Notificación no encontrada")
    except PersistenciaNotificacionError as exc:
        raise HTTPException(status_code=500, detail="No fue posible marcar la notificación") from exc
