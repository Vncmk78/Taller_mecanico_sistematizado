"""Receptor de hechos de MS3: destinatarios por dominio, nunca por body libre."""

import hmac
from types import SimpleNamespace
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from services.ms1_auth.config import settings
from services.ms1_auth.db import get_db
from services.ms1_auth.schemas.notificacion import EventoPersonalRecibidoRespuesta
from services.ms1_auth.services.notificaciones import (
    recibir_aviso_personal,
    _recibir_aviso,
    DestinatarioNotificacionInvalidoError,
    PersistenciaNotificacionError,
)
from shared.contratos_avisos import AvisoMS3, DestinatarioOrden
from shared.direccion_notificaciones import cabeceras_notificaciones

router = APIRouter(prefix="/interno/eventos/ms3", tags=["interno"])


def resolver_destinatario(orden_id: int) -> DestinatarioOrden:
    if settings.MS2_NOTIFICATION_SECRET is None:
        raise HTTPException(status_code=503, detail="Consulta de destinatario no configurada")
    try:
        r = httpx.get(
            settings.MS2_URL.rstrip("/")
            + f"/interno/notificaciones/ordenes/{orden_id}/destinatario",
            headers=cabeceras_notificaciones(
                settings.MS2_URL, 2, settings.MS2_NOTIFICATION_SECRET.get_secret_value()
            ),
            timeout=settings.NOTIFICATION_TIMEOUT_SECONDS,
        )
        r.raise_for_status()
        destino = DestinatarioOrden.model_validate(r.json())
        if destino.orden_id != orden_id:
            raise ValueError("Orden distinta")
        return destino
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="No fue posible resolver el destinatario; reintentar el mismo evento",
        ) from exc


@router.post("/aviso", response_model=EventoPersonalRecibidoRespuesta)
def recibir(
    evento: AvisoMS3,
    x_service_token: str | None = Header(default=None, alias="X-Service-Token"),
    db: Session = Depends(get_db),
):
    secreto = settings.MS3_EVENT_SHARED_SECRET
    if secreto is None:
        raise HTTPException(status_code=503, detail="Recepción de MS3 no configurada")
    if x_service_token is None or not hmac.compare_digest(
        x_service_token, secreto.get_secret_value()
    ):
        raise HTTPException(status_code=401, detail="Credencial de servicio inválida")
    try:
        if evento.tipo == "stock.alerta":
            nuevas, existentes = recibir_aviso_personal(
                db,
                evento,
                repuesto_id=evento.repuesto_id,
                titulo="Alerta de stock bajo",
                mensaje=f"Repuesto {evento.nombre} (n° {evento.repuesto_id}): stock {evento.stock}, umbral {evento.umbral}. Revise el inventario.",
            )
        else:
            destino = resolver_destinatario(evento.orden_id)
            if evento.tipo == "presupuesto.enviado":
                e = SimpleNamespace(
                    evento_id=evento.evento_id,
                    tipo=evento.tipo,
                    ocurrido_en=evento.ocurrido_en,
                    vehiculo_id=destino.vehiculo_id,
                    cliente_usuario_id=destino.cliente_usuario_id,
                    presupuesto_id=evento.presupuesto_id,
                )
                _, duplicado = _recibir_aviso(
                    db,
                    e,
                    orden_id=destino.orden_id,
                    titulo="Presupuesto disponible para revisar",
                    mensaje=f"El taller envió el presupuesto n° {evento.presupuesto_id}, versión {evento.version}, de su orden n° {evento.orden_id}. Revíselo para aprobar o rechazar.",
                )
                nuevas, existentes = (0, 1) if duplicado else (1, 0)
            else:
                nuevas, existentes = recibir_aviso_personal(
                    db,
                    evento,
                    orden_id=destino.orden_id,
                    vehiculo_id=destino.vehiculo_id,
                    presupuesto_id=evento.presupuesto_id,
                    titulo=f"Presupuesto {evento.decision} por el Cliente",
                    mensaje=f"El Cliente decidió {evento.decision} para el presupuesto n° {evento.presupuesto_id}, versión {evento.version}, de la orden n° {evento.orden_id}.",
                )
        return EventoPersonalRecibidoRespuesta(
            evento_id=evento.evento_id, creadas=nuevas, existentes=existentes
        )
    except DestinatarioNotificacionInvalidoError as exc:
        raise HTTPException(status_code=422, detail="Destinatario no disponible") from exc
    except PersistenciaNotificacionError as exc:
        raise HTTPException(status_code=500, detail="No fue posible conservar los avisos") from exc
