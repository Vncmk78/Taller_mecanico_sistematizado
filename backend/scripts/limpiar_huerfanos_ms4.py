"""Concilia el bucket de evidencias con la base de MS4 y limpia huérfanos.

Un huérfano es un archivo en MinIO/S3 sin fila en la tabla de evidencias
(por ejemplo, si la base y el borrado de compensación fallaron a la vez, o si
el proceso murió entre la subida y el commit). La lógica vive en
`services/ms4_evidencias/services/huerfanos.py`.

Por defecto es una SIMULACIÓN: solo informa. Para borrar hay que pasar
`--eliminar`. Nunca borra claves fuera de la convención `ordenes/{orden}/
{uuid}.{ext}` ni objetos más nuevos que `--antiguedad-minutos` (60 por
defecto), para no tocar subidas en curso. Usa la configuración MS4_* (.env).

Uso:
    python scripts/limpiar_huerfanos_ms4.py
    python scripts/limpiar_huerfanos_ms4.py --eliminar
    python scripts/limpiar_huerfanos_ms4.py --antiguedad-minutos 180 --eliminar

Código de salida: 0 si no quedan huérfanos pendientes, 1 si quedan (en
simulación, o porque alguno no se pudo borrar), 2 si no se pudo conectar.
"""
from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.ms4_evidencias.config import settings  # noqa: E402
from services.ms4_evidencias.db import SessionLocal  # noqa: E402
from services.ms4_evidencias.services.almacenamiento import crear_cliente_s3  # noqa: E402
from services.ms4_evidencias.services.huerfanos import (  # noqa: E402
    ResultadoConciliacion,
    conciliar,
)


def imprimir(resultado: ResultadoConciliacion) -> None:
    modo = "ELIMINACIÓN" if resultado.eliminar else "SIMULACIÓN (no se borra nada)"
    print(f"Modo: {modo}")
    print(f"Objetos revisados:            {resultado.revisados}")
    print(f"Recientes (se omiten):        {resultado.recientes}")
    print(f"Claves fuera de convención:   {len(resultado.claves_ajenas)}")
    print(f"Huérfanos encontrados:        {len(resultado.huerfanos)}")
    for clave in resultado.huerfanos:
        print(f"  - {clave}")
    if resultado.eliminar:
        print(f"Eliminados:                   {len(resultado.eliminados)}")
        print(f"No se pudieron eliminar:      {len(resultado.no_eliminados)}")
        for clave in resultado.no_eliminados:
            print(f"  ✘ {clave}")
    print(f"Filas sin archivo (revisar):  {len(resultado.filas_sin_objeto)}")
    for evidencia_id in resultado.filas_sin_objeto:
        print(f"  - evidencia {evidencia_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--eliminar", action="store_true", help="borra los huérfanos (sin esto solo informa)"
    )
    parser.add_argument(
        "--antiguedad-minutos",
        type=int,
        default=60,
        help="solo considera objetos más antiguos que esto (por defecto 60)",
    )
    args = parser.parse_args()
    if args.antiguedad_minutos < 1:
        parser.error("--antiguedad-minutos debe ser al menos 1")

    try:
        s3 = crear_cliente_s3(settings)
        with SessionLocal() as db:
            resultado = conciliar(
                db,
                s3,
                settings.S3_BUCKET,
                antiguedad_minima=timedelta(minutes=args.antiguedad_minutos),
                eliminar=args.eliminar,
            )
    except Exception as exc:  # noqa: BLE001  (sin detalles sensibles en consola)
        print(f"✘ No se pudo conciliar: {type(exc).__name__}", file=sys.stderr)
        return 2

    imprimir(resultado)
    pendientes = resultado.no_eliminados if resultado.eliminar else resultado.huerfanos
    return 1 if pendientes else 0


if __name__ == "__main__":
    raise SystemExit(main())
