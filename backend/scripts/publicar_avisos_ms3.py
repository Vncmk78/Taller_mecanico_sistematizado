"""Publicar hechos pendientes de MS3 fuera del servidor HTTP.

    SGTM_ENV_FILE=.env.pruebas python scripts/publicar_avisos_ms3.py --una-vez

Un cron puede invocar --una-vez; sin esa opción se ejecuta el worker continuo.
No imprime secretos, cuerpos ni identificadores de destinatarios.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.services.publicador_avisos import ejecutar_worker, publicar_siguiente


async def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--una-vez", action="store_true")
    args = p.parse_args()
    if args.una_vez:
        async with httpx.AsyncClient(timeout=settings.EVENT_TIMEOUT_SECONDS) as c:
            hubo = await publicar_siguiente(c)
        print(
            "Hecho procesado; consulte el resultado en la outbox."
            if hubo
            else "Sin trabajo procesable."
        )
    else:
        await ejecutar_worker()


if __name__ == "__main__":
    asyncio.run(main())
