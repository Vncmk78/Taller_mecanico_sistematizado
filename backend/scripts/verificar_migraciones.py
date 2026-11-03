"""Comprueba, sin modificar tablas, las revisiones de las cuatro bases.

Uso: python scripts/verificar_migraciones.py (desde cualquier directorio).
Lee backend/.env; las variables del proceso tienen prioridad. No imprime DSN.
Salida: 0 = todas al día, 1 = faltan migraciones, 2 = error o revisión desconocida.
La comparación corresponde al checkout actual, no a otra rama o despliegue.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from dotenv import dotenv_values
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.pool import NullPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
SERVICIOS = {
    "MS1": "ms1_auth",
    "MS2": "ms2_taller",
    "MS3": "ms3_presupuestos",
    "MS4": "ms4_evidencias",
}


@dataclass(frozen=True)
class Resultado:
    servicio: str
    estado: str
    actuales: frozenset[str]
    esperadas: frozenset[str]
    detalle: str = ""

    @property
    def codigo(self) -> int:
        return 0 if self.estado == "OK" else 1 if self.estado == "ATRASADA" else 2


def configuracion(servicio: str) -> Config:
    carpeta = BACKEND_DIR / "services" / SERVICIOS[servicio]
    config = Config(str(carpeta / "alembic.ini"))
    config.set_main_option("script_location", str(carpeta / "alembic").replace("%", "%%"))
    return config


def comparar(servicio: str, actuales: frozenset[str], scripts: ScriptDirectory) -> Resultado:
    esperadas = frozenset(scripts.get_heads())
    conocidas = {revision.revision for revision in scripts.walk_revisions()}
    if not esperadas:
        return Resultado(servicio, "ERROR", actuales, esperadas, "El código no tiene revisiones")
    if actuales - conocidas:
        return Resultado(
            servicio, "INCOMPATIBLE", actuales, esperadas,
            "Hay revisiones que no existen en este checkout; revisar rama e historial",
        )
    estado = "OK" if actuales == esperadas else "ATRASADA"
    return Resultado(servicio, estado, actuales, esperadas)


def leer_revisiones(conexion: Connection) -> frozenset[str]:
    # get_current_heads() consulta alembic_version; no crea la tabla si falta.
    return frozenset(MigrationContext.configure(conexion).get_current_heads())


def verificar(servicio: str, entorno: dict[str, str | None]) -> Resultado:
    esperadas: frozenset[str] = frozenset()
    try:
        scripts = ScriptDirectory.from_config(configuracion(servicio))
        esperadas = frozenset(scripts.get_heads())
        dsn = entorno.get(f"{servicio}_DATABASE_URL")
        if not dsn:
            return Resultado(servicio, "ERROR", frozenset(), esperadas, "Falta DATABASE_URL explícita")
        url = make_url(dsn)
        if url.drivername != "postgresql+psycopg":
            return Resultado(
                servicio, "ERROR", frozenset(), esperadas,
                "Se requiere un DSN postgresql+psycopg://",
            )
        engine = create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 5})
        try:
            with engine.connect() as conexion:
                conexion.exec_driver_sql("SET TRANSACTION READ ONLY")
                conexion.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
                actuales = leer_revisiones(conexion)
        finally:
            engine.dispose()
        return comparar(servicio, actuales, scripts)
    except Exception as exc:
        # Los errores de conexión/configuración pueden contener credenciales.
        return Resultado(
            servicio, "ERROR", frozenset(), esperadas,
            f"No fue posible verificar ({type(exc).__name__}); revisar conexión y configuración",
        )


def verificar_todas() -> list[Resultado]:
    entorno = {**dotenv_values(BACKEND_DIR / ".env"), **os.environ}
    resultados = [verificar(servicio, entorno) for servicio in SERVICIOS]
    destinos: dict[tuple, list[int]] = {}
    for indice, servicio in enumerate(SERVICIOS):
        try:
            url = make_url(entorno.get(f"{servicio}_DATABASE_URL") or "")
            destino = (url.host, url.port or 5432, url.database)
        except Exception:
            continue  # El error de DSN ya aparece en el resultado individual.
        destinos.setdefault(destino, []).append(indice)
    for indices in destinos.values():
        if len(indices) > 1:
            for indice in indices:
                previo = resultados[indice]
                resultados[indice] = Resultado(
                    previo.servicio, "ERROR", previo.actuales, previo.esperadas,
                    "Dos servicios apuntan a la misma base; se requieren bases independientes",
                )
    return resultados


def mostrar(resultados: list[Resultado]) -> int:
    for resultado in resultados:
        actuales = ", ".join(sorted(resultado.actuales)) or "sin versión"
        esperadas = ", ".join(sorted(resultado.esperadas)) or "sin head"
        print(f"{resultado.servicio}: {resultado.estado} | BD: {actuales} | código: {esperadas}")
        if resultado.detalle:
            print(f"  {resultado.detalle}")
    return max((resultado.codigo for resultado in resultados), default=2)


if __name__ == "__main__":
    raise SystemExit(mostrar(verificar_todas()))
