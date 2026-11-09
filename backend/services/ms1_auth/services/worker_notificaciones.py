"""Publicación periódica y cancelable, fuera de las transacciones de negocio."""

import asyncio
import logging
from services.ms1_auth.config import settings
from services.ms1_auth.services.entregas_notificaciones import procesar_siguiente

logger = logging.getLogger(__name__)


async def ejecutar_worker():
    while True:
        try:
            hubo = await asyncio.to_thread(procesar_siguiente)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Los errores de base se reintentan; no volcar credenciales/payloads.
            logger.error("No se pudo procesar la cola de canales de MS1")
            hubo = False
        if not hubo:
            await asyncio.sleep(settings.NOTIFICATION_POLL_SECONDS)
