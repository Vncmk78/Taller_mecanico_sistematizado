"""Recepción de eventos internos y bandeja personal de notificaciones."""
from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from services.ms1_auth.config import settings
from services.ms1_auth.db import get_db
from services.ms1_auth.dependencies import obtener_principal_actual
from services.ms1_auth.schemas.notificacion import (
    EventoEstadoOrden,
    EventoRecibidoRespuesta,
    NotificacionRespuesta,
)
from services.ms1_auth.services.notificaciones import (
    DestinatarioNotificacionInvalidoError,
    PersistenciaNotificacionError,
    listar_notificaciones,
    recibir_evento_estado_orden,
)
from shared.auth import PrincipalAutenticado

router_notificaciones = APIRouter(tags=["notificaciones"])


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
    secreto = settings.EVENT_SHARED_SECRET
    if secreto is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La recepción interna de eventos no está configurada",
        )
    if x_service_token is None or not hmac.compare_digest(
        x_service_token, secreto.get_secret_value()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencial de servicio inválida",
            headers={"WWW-Authenticate": "Service"},
        )
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


@router_notificaciones.get(
    "/notificaciones",
    response_model=list[NotificacionRespuesta],
    summary="Consultar las notificaciones del usuario autenticado",
)
def consultar_notificaciones(
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    limite: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[NotificacionRespuesta]:
    try:
        return listar_notificaciones(
            db,
            destinatario_id=principal.usuario_id,
            limite=limite,
            offset=offset,
        )
    except PersistenciaNotificacionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible consultar las notificaciones",
        ) from exc
