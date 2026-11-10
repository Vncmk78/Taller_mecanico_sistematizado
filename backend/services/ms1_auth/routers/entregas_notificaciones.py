"""Registro propio de dispositivos y seguimiento/reintento de canales."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response, Path
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from services.ms1_auth.db import get_db
from services.ms1_auth.dependencies import obtener_principal_actual
from services.ms1_auth.models import (
    DispositivoPush,
    EntregaNotificacion,
    IntentoEntrega,
    Notificacion,
)
from services.ms1_auth.schemas.entrega_notificacion import (
    DispositivoRegistrar,
    DispositivoRespuesta,
    EntregaRespuesta,
    IntentoEntregaRespuesta,
)
from services.ms1_auth.services.entregas_notificaciones import (
    encolar_canales,
    registrar_dispositivo,
)
from shared.auth import PrincipalAutenticado

router = APIRouter(prefix="/notificaciones", tags=["notificaciones"])


@router.post(
    "/dispositivos",
    response_model=DispositivoRespuesta,
    status_code=201,
    responses={
        200: {"description": "Registro existente actualizado", "model": DispositivoRespuesta},
        401: {"description": "JWT requerido"},
        409: {"description": "Registro concurrente; reintentar"},
    },
)
def registrar(
    body: DispositivoRegistrar,
    response: Response,
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    db: Session = Depends(get_db),
):
    try:
        d, creado = registrar_dispositivo(
            db, principal.usuario_id, body.token.get_secret_value(), body.plataforma
        )
        if not creado:
            response.status_code = 200
        return d
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="El dispositivo se registró simultáneamente; vuelva a consultar o registrar",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500, detail="No fue posible registrar el dispositivo"
        ) from exc


@router.get("/dispositivos", response_model=list[DispositivoRespuesta])
def listar(
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    db: Session = Depends(get_db),
):
    return list(
        db.scalars(
            select(DispositivoPush)
            .where(DispositivoPush.usuario_id == principal.usuario_id)
            .order_by(DispositivoPush.creado_en)
        )
    )


@router.delete(
    "/dispositivos/{dispositivo_id}",
    status_code=204,
    responses={404: {"description": "Dispositivo inexistente o ajeno"}},
)
def desactivar(
    dispositivo_id: UUID,
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    db: Session = Depends(get_db),
) -> None:
    d = db.scalar(
        select(DispositivoPush)
        .where(
            DispositivoPush.dispositivo_id == dispositivo_id,
            DispositivoPush.usuario_id == principal.usuario_id,
        )
        .with_for_update()
    )
    if d is None:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    d.activo = False
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500, detail="No fue posible desactivar el dispositivo"
        ) from exc


def propia(db, uid, nid):
    n = db.scalar(
        select(Notificacion).where(
            Notificacion.notificacion_id == nid, Notificacion.destinatario_id == uid
        )
    )
    if n is None:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    return n


def respuestas(db, nid):
    entregas = db.scalars(
        select(EntregaNotificacion)
        .where(EntregaNotificacion.notificacion_id == nid)
        .order_by(EntregaNotificacion.entrega_id)
    )
    return [
        EntregaRespuesta(
            entrega_id=e.entrega_id,
            canal=e.canal,
            estado=e.estado,
            intentos=e.intentos,
            aceptada_en=e.aceptada_en,
            ultimo_error=e.ultimo_error,
            intentos_registrados=[
                IntentoEntregaRespuesta.model_validate(i)
                for i in db.scalars(
                    select(IntentoEntrega)
                    .where(IntentoEntrega.entrega_id == e.entrega_id)
                    .order_by(IntentoEntrega.numero)
                )
            ],
        )
        for e in entregas
    ]


@router.get(
    "/{notificacion_id}/entregas",
    response_model=list[EntregaRespuesta],
    responses={404: {"description": "Aviso inexistente o ajeno"}},
)
def consultar(
    notificacion_id: int = Path(gt=0),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    db: Session = Depends(get_db),
):
    propia(db, principal.usuario_id, notificacion_id)
    return respuestas(db, notificacion_id)


@router.post(
    "/{notificacion_id}/reintentos",
    response_model=list[EntregaRespuesta],
    responses={404: {"description": "Aviso inexistente o ajeno"}},
)
def reintentar(
    notificacion_id: int = Path(gt=0),
    principal: PrincipalAutenticado = Depends(obtener_principal_actual),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone

    n = propia(db, principal.usuario_id, notificacion_id)
    try:
        encolar_canales(db, n)
        for e in db.scalars(
            select(EntregaNotificacion)
            .where(EntregaNotificacion.notificacion_id == notificacion_id)
            .with_for_update()
        ):
            if e.estado in {"fallida", "sin_configuracion"}:
                e.estado = "pendiente"
                e.proxima_tentativa_en = datetime.now(timezone.utc)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500, detail="No fue posible registrar el reintento"
        ) from exc
    return respuestas(db, notificacion_id)
