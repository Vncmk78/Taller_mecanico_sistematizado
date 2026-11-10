"""Ejecutar canales de MS1 fuera del servidor HTTP (worker o cron).

    SGTM_ENV_FILE=.env.pruebas python scripts/procesar_notificaciones.py --una-vez

Sin proveedores configurados se registra sin_configuracion, sin falso envío.
No reencola avisos históricos. No imprime destinatarios, tokens ni claves.
"""

import argparse, asyncio, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.ms1_auth.services.entregas_notificaciones import procesar_siguiente
from services.ms1_auth.services.worker_notificaciones import ejecutar_worker

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--una-vez", action="store_true")
args = p.parse_args()
if args.una_vez:
    print("Trabajo procesado." if procesar_siguiente() else "Sin trabajo pendiente.")
else:
    asyncio.run(ejecutar_worker())
