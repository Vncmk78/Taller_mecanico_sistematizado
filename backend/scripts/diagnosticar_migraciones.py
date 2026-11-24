"""Diagnóstico de migraciones de MS1-MS4 sobre bases descartables (semana 11).

Uso, desde backend/, con el ambiente de pruebas levantado
(python scripts/ambiente_pruebas.py infra):

    python scripts/diagnosticar_migraciones.py                 # los cuatro
    python scripts/diagnosticar_migraciones.py ms2_taller      # uno

Para cada servicio, en una base nueva `diag_migraciones_<servicio>_<id>`:
  1. heads del árbol de revisiones (más de uno = falta un merge);
  2. alembic upgrade head;
  3. drift modelo ORM ↔ migraciones con compare_metadata (tipos y server_default);
  4. alembic check (lo que propondría `revision --autogenerate`);
  5. alembic downgrade base y upgrade head de nuevo (las migraciones se pueden revertir).
La base se borra al terminar. Solo usa el PostgreSQL de pruebas (puerto 5444);
no toca las bases del ambiente ni imprime credenciales.
Salida: 0 sin hallazgos, 1 con hallazgos.
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
import uuid
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

RAIZ = Path(__file__).resolve().parents[1]
SERVICIOS = {"ms1_auth": "MS1", "ms2_taller": "MS2", "ms3_presupuestos": "MS3", "ms4_evidencias": "MS4"}
# Índices que viven solo en la migración 0006_ms3 (pg_trgm). Ver la revisión de
# integridad referencial; su paso al modelo es parte de la tarea de migraciones.
ACEPTADAS = {"ms3_presupuestos": {"ix_repuesto_nombre_trgm", "ix_proveedor_nombre_trgm",
                                  "ix_proveedor_contacto_trgm"}}


def _alembic(servicio: str, entorno: dict[str, str], *args: str) -> tuple[int, str]:
    # utf-8 explícito: los mensajes de Alembic traen los títulos de las
    # migraciones (con tildes) y en Windows el valor por omisión es cp1252.
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", f"services/{servicio}/alembic.ini", *args],
        cwd=RAIZ, env=entorno, capture_output=True, encoding="utf-8", errors="replace", timeout=300)
    return r.returncode, r.stdout + r.stderr


def _ultima_linea_de_error(salida: str) -> str:
    lineas = [l for l in salida.strip().splitlines() if l.strip()]
    for linea in reversed(lineas):
        if "Error" in linea or "ERROR" in linea:
            return linea.strip()[:400]
    return lineas[-1][:400] if lineas else "(sin salida)"


def diagnosticar(servicio: str, admin) -> list[str]:
    prefijo = SERVICIOS[servicio]
    hallazgos: list[str] = []
    heads = ScriptDirectory.from_config(Config(str(RAIZ / f"services/{servicio}/alembic.ini"))).get_heads()
    print(f"\n== {servicio}\n  heads: {', '.join(heads)}")
    if len(heads) > 1:
        hallazgos.append(f"{servicio}: {len(heads)} heads (falta una migración de merge)")

    nombre = f"diag_migraciones_{servicio}_{uuid.uuid4().hex[:6]}"
    with admin.connect() as c:
        c.execute(text(f'create database "{nombre}"'))
    url = admin.url.set(database=nombre)
    entorno = {k: v for k, v in os.environ.items() if not k.startswith(("MS1_", "MS2_", "MS3_", "MS4_", "SGTM_"))}
    entorno.update({
        f"{prefijo}_DATABASE_URL": url.render_as_string(hide_password=False),
        f"{prefijo}_JWT_SECRET_KEY": "clave-local-diagnostico-migraciones-1234567890",
        "SGTM_ENV_FILE": os.devnull, "PYTHONIOENCODING": "utf-8",
    })
    motor = create_engine(url)
    try:
        rc, salida = _alembic(servicio, entorno, "upgrade", "head")
        print("  upgrade head:", "OK" if rc == 0 else "FALLA")
        if rc:
            hallazgos.append(f"{servicio}: upgrade head falla: {_ultima_linea_de_error(salida)}")
            return hallazgos

        os.environ.update({k: v for k, v in entorno.items() if k.startswith(prefijo + "_")})
        importlib.import_module(f"services.{servicio}.models")
        metadata = importlib.import_module(f"services.{servicio}.db").Base.metadata
        with motor.connect() as c:
            diferencias = compare_metadata(MigrationContext.configure(
                c, opts={"compare_type": True, "compare_server_default": True}), metadata)
        for d in diferencias:
            if isinstance(d, tuple) and d[0] == "remove_index" and d[1].name in ACEPTADAS.get(servicio, ()):
                print(f"  drift aceptado: {d[0]} {d[1].name}")
                continue
            print(f"  DRIFT: {d}")
            hallazgos.append(f"{servicio}: drift {d}")
        if not diferencias:
            print("  drift: ninguno")

        rc, salida = _alembic(servicio, entorno, "check")
        print("  alembic check:", "OK" if rc == 0 else "propone cambios (ver drift)")

        rc, salida = _alembic(servicio, entorno, "downgrade", "base")
        print("  downgrade base:", "OK" if rc == 0 else "FALLA")
        if rc:
            hallazgos.append(f"{servicio}: downgrade base falla: {_ultima_linea_de_error(salida)}")
        else:
            rc, salida = _alembic(servicio, entorno, "upgrade", "head")
            print("  upgrade head (de nuevo):", "OK" if rc == 0 else "FALLA")
            if rc:
                hallazgos.append(f"{servicio}: re-upgrade falla: {_ultima_linea_de_error(salida)}")
    finally:
        motor.dispose()
        with admin.connect() as c:
            c.execute(text(f'drop database if exists "{nombre}" with (force)'))
    return hallazgos


def main() -> int:
    sys.path.insert(0, str(RAIZ))
    config = dotenv_values(RAIZ / ".env.pruebas")
    admin_url = make_url(config["MS2_DATABASE_URL"]).set(database="postgres")
    assert admin_url.host in ("127.0.0.1", "localhost") and admin_url.port == 5444, \
        "Solo el PostgreSQL local del ambiente de pruebas"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    servicios = sys.argv[1:] or list(SERVICIOS)
    hallazgos = [h for s in servicios for h in diagnosticar(s, admin)]
    admin.dispose()
    print("\nHallazgos:" if hallazgos else "\nSin hallazgos.")
    for h in hallazgos:
        print("  -", h)
    return 1 if hallazgos else 0


if __name__ == "__main__":
    raise SystemExit(main())
