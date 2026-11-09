"""Publicación de la outbox de MS3 con concesión temporal y reintentos."""

import asyncio
from datetime import datetime, timedelta, timezone
import logging
import httpx
from shared.direccion_notificaciones import cabeceras_notificaciones
from sqlalchemy import select
from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import SessionLocal
from services.ms3_presupuestos.models.evento_aviso_outbox import EventoAvisoOutbox

logger = logging.getLogger(__name__)


async def publicar_siguiente(cliente: httpx.AsyncClient) -> bool:
    if settings.EVENT_SHARED_SECRET is None:
        return False

    def reclamar():
        ahora = datetime.now(timezone.utc)
        with SessionLocal() as db:
            e = db.scalar(
                select(EventoAvisoOutbox)
                .where(
                    EventoAvisoOutbox.publicado_en.is_(None),
                    EventoAvisoOutbox.proxima_tentativa_en <= ahora,
                )
                .order_by(EventoAvisoOutbox.outbox_id)
                .with_for_update(skip_locked=True)
            )
            if e is None:
                return None
            e.intentos += 1
            e.proxima_tentativa_en = ahora + timedelta(seconds=90)
            d = (e.outbox_id, str(e.evento_id), e.payload, e.intentos)
            db.commit()
            return d

    evento = await asyncio.to_thread(reclamar)
    if evento is None:
        return False
    eid, uuid, payload, intentos = evento
    fallo = None
    try:
        r = await cliente.post(
            settings.MS1_URL.rstrip("/") + "/interno/eventos/ms3/aviso",
            json=payload,
            headers=cabeceras_notificaciones(
                settings.MS1_URL, 1, settings.EVENT_SHARED_SECRET.get_secret_value()
            ),
        )
        r.raise_for_status()
        recibo = r.json()
        if not isinstance(recibo, dict) or recibo.get("evento_id") != uuid:
            raise ValueError("Recibo de otro evento")
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        fallo = type(exc).__name__

    def confirmar():
        with SessionLocal() as db:
            e = db.scalar(
                select(EventoAvisoOutbox)
                .where(EventoAvisoOutbox.outbox_id == eid)
                .with_for_update()
            )
            if e is None or e.publicado_en is not None or e.intentos != intentos:
                return
            if fallo:
                e.ultimo_error = fallo
                e.proxima_tentativa_en = datetime.now(timezone.utc) + timedelta(
                    seconds=min(300, 2 ** min(intentos, 9))
                )
            else:
                e.publicado_en = datetime.now(timezone.utc)
                e.ultimo_error = None
            db.commit()

    await asyncio.to_thread(confirmar)
    return True


async def ejecutar_worker():
    if settings.EVENT_SHARED_SECRET is None:
        return
    async with httpx.AsyncClient(timeout=settings.EVENT_TIMEOUT_SECONDS) as cliente:
        while True:
            try:
                hubo = await publicar_siguiente(cliente)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.error("No se pudo procesar la outbox de avisos de MS3")
                hubo = False
            if not hubo:
                await asyncio.sleep(settings.EVENT_POLL_SECONDS)
