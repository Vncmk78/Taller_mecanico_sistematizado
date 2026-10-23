"""Worker HTTP para publicar y reintentar los eventos de la outbox MS2."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select

from services.ms2_taller.config import settings
from services.ms2_taller.db import SessionLocal
from services.ms2_taller.models.evento_outbox import EventoOutbox

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EventoReclamado:
    outbox_id: int
    evento_id: str
    payload: dict[str, Any]
    intentos: int


def segundos_espera_reintento(intento: int, maximo: int) -> int:
    """Espera exponencial acotada: 1, 2, 4… hasta el máximo configurado."""

    return min(2 ** max(0, intento - 1), maximo)


def _reclamar_evento() -> EventoReclamado | None:
    """Reclama una fila con lock y lease antes de salir a la red."""

    ahora = datetime.now(timezone.utc)
    with SessionLocal() as db:
        evento = db.scalar(
            select(EventoOutbox)
            .where(
                EventoOutbox.publicado_en.is_(None),
                EventoOutbox.proxima_tentativa_en <= ahora,
            )
            .order_by(EventoOutbox.proxima_tentativa_en, EventoOutbox.outbox_id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if evento is None:
            db.rollback()
            return None
        evento.intentos += 1
        # Lease superior al timeout HTTP para tolerar la caída del worker en vuelo.
        evento.proxima_tentativa_en = ahora + timedelta(
            seconds=settings.EVENT_TIMEOUT_SECONDS + 30
        )
        reclamado = EventoReclamado(
            outbox_id=evento.outbox_id,
            evento_id=str(evento.evento_id),
            payload=dict(evento.payload),
            intentos=evento.intentos,
        )
        db.commit()
        return reclamado


def _marcar_publicado(outbox_id: int) -> None:
    with SessionLocal() as db:
        evento = db.get(EventoOutbox, outbox_id)
        if evento is None or evento.publicado_en is not None:
            return
        evento.publicado_en = datetime.now(timezone.utc)
        evento.ultimo_error = None
        db.commit()


def _programar_reintento(evento: EventoReclamado, error: str) -> None:
    espera = segundos_espera_reintento(
        evento.intentos, settings.EVENT_RETRY_MAX_SECONDS
    )
    with SessionLocal() as db:
        fila = db.get(EventoOutbox, evento.outbox_id)
        if fila is None or fila.publicado_en is not None:
            return
        fila.ultimo_error = error[:300]
        fila.proxima_tentativa_en = datetime.now(timezone.utc) + timedelta(
            seconds=espera
        )
        db.commit()


async def publicar_siguiente_evento(cliente_http: httpx.AsyncClient) -> bool:
    """Publica un evento vencido; retorna si encontró trabajo."""

    if settings.EVENT_SHARED_SECRET is None:
        return False
    evento = await asyncio.to_thread(_reclamar_evento)
    if evento is None:
        return False

    url = f"{settings.MS1_URL.rstrip('/')}/interno/eventos/ordenes/estado"
    try:
        respuesta = await cliente_http.post(
            url,
            json=evento.payload,
            headers={
                "X-Service-Token": settings.EVENT_SHARED_SECRET.get_secret_value()
            },
        )
        respuesta.raise_for_status()
        recibo = respuesta.json()
        if not isinstance(recibo, dict) or recibo.get("evento_id") != evento.evento_id:
            raise ValueError("MS1 no confirmó la misma clave de evento")
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        error = f"{type(exc).__name__}: {str(exc)[:240]}"
        await asyncio.to_thread(_programar_reintento, evento, error)
        logger.warning(
            "No se pudo publicar evento MS2 %s; reintento %s programado",
            evento.evento_id,
            evento.intentos,
        )
        return True

    await asyncio.to_thread(_marcar_publicado, evento.outbox_id)
    return True


async def ejecutar_worker_eventos() -> None:
    """Consulta la outbox periódicamente hasta que se detenga MS2."""

    if settings.EVENT_SHARED_SECRET is None:
        logger.warning("Worker de eventos detenido: falta MS2_EVENT_SHARED_SECRET")
        return
    async with httpx.AsyncClient(timeout=settings.EVENT_TIMEOUT_SECONDS) as cliente:
        while True:
            try:
                encontro_evento = await publicar_siguiente_evento(cliente)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error al procesar la outbox de eventos de MS2")
                encontro_evento = False
            if not encontro_evento:
                await asyncio.sleep(settings.EVENT_POLL_SECONDS)
