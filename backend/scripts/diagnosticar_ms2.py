"""Diagnóstico de solo lectura del esquema usado al consultar órdenes en MS2.

Desde backend/: python scripts/diagnosticar_ms2.py
Lee MS2_DATABASE_URL del proceso o backend/.env. No necesita JWT ni imprime DSN.
Debe ejecutarse desde el mismo commit que MS2 tiene desplegado.
Salida: 0 = comprobaciones correctas; 1 = diferencias; 2 = error/incompatibilidad.
No ejecuta Alembic env.py, migraciones, seeds ni consultas de datos personales.
"""
from __future__ import annotations

import os
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.pool import NullPool

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Comprobaciones dirigidas a los modelos que carga GET /ordenes y a capacidad.
# No sustituyen la validación completa de tipos, restricciones ni datos.
COLUMNAS = {
    "solicitud_nueva_atencion": frozenset(
        "solicitud_id orden_cancelada_id vehiculo_id cliente_usuario_id descripcion "
        "solicitada_en situacion respuesta revisor_id revisada_en orden_generada_id".split()
    ),
    "orden_trabajo": frozenset(
        "orden_id vehiculo_id ingreso_id estado_codigo mecanico_actual_id "
        "creado_por_id creado_en actualizado_en diagnostico_texto fecha_diagnostico "
        "diagnostico_autor_id entregado_en entregado_por_id devuelto_en devuelto_por_id".split()
    ),
    "estado_orden": frozenset({"estado_codigo", "nombre"}),
    "historial_estado": frozenset(
        "historial_id orden_id estado_anterior estado_nuevo actor_usuario_id origen "
        "fecha_hora observacion decision_presupuesto_id envio_presupuesto_id "
        "disponibilidad_repuestos_clave_operacion".split()
    ),
    "historial_asignacion": frozenset(
        "asignacion_id orden_id mecanico_anterior_id mecanico_nuevo_id administrador_id "
        "fecha_hora observacion".split()
    ),
    "bitacora_orden": frozenset(
        "bitacora_id orden_id autor_usuario_id tipo descripcion creado_en".split()
    ),
    "bitacora_repuesto": frozenset(
        "repuesto_bitacora_id bitacora_id nombre cantidad".split()
    ),
    "configuracion_capacidad_mecanico": frozenset(
        "configuracion_id max_ordenes_activas actualizado_por_id actualizado_en".split()
    ),
    "configuracion_cupo_ingresos": frozenset(
        "configuracion_id max_ingresos_diarios actualizado_por_id actualizado_en".split()
    ),
}


class EntornoMS2(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MS2_", env_file=BACKEND_DIR / (os.environ.get("SGTM_ENV_FILE") or ".env"), extra="ignore",
        hide_input_in_errors=True,
    )
    database_url: SecretStr


def revisiones_codigo() -> ScriptDirectory:
    carpeta = BACKEND_DIR / "services" / "ms2_taller"
    config = Config(str(carpeta / "alembic.ini"))
    config.set_main_option("script_location", str(carpeta / "alembic").replace("%", "%%"))
    return ScriptDirectory.from_config(config)


def comprobar(conexion: Connection, scripts: ScriptDirectory) -> tuple[int, list[str]]:
    # Primeras instrucciones: impedir escrituras y acotar cada consulta.
    conexion.exec_driver_sql("SET TRANSACTION READ ONLY")
    conexion.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
    actuales = frozenset(MigrationContext.configure(conexion).get_current_heads())
    esperadas = frozenset(scripts.get_heads())
    conocidas = {revision.revision for revision in scripts.walk_revisions()}
    lineas = [
        "Revisiones de esta base: " + (", ".join(sorted(actuales)) or "sin versión"),
        "Heads del código usado: " + (", ".join(sorted(esperadas)) or "sin head"),
    ]
    if not esperadas or actuales - conocidas:
        return 2, lineas + ["INCOMPATIBLE: revisar el commit y el historial antes de migrar."]

    codigo = 0 if actuales == esperadas else 1
    if codigo:
        lineas.append("DIFERENCIA: las revisiones de la base no coinciden con este código.")
    inspector = inspect(conexion)
    tablas = set(inspector.get_table_names())
    for tabla, requeridas in COLUMNAS.items():
        if tabla not in tablas:
            codigo = 1
            lineas.append(f"FALTA TABLA: {tabla}")
            continue
        presentes = {columna["name"] for columna in inspector.get_columns(tabla)}
        faltantes = requeridas - presentes
        if faltantes:
            codigo = 1
            lineas.append(f"FALTAN COLUMNAS: {tabla}: {', '.join(sorted(faltantes))}")
        else:
            lineas.append(f"OK: {tabla}")
    if codigo == 0:
        lineas.append("Las comprobaciones de revisiones y columnas pasaron; falta verificar la API.")
    return codigo, lineas


def main() -> int:
    engine = None
    try:
        url = make_url(EntornoMS2().database_url.get_secret_value())
        if url.drivername != "postgresql+psycopg":
            print("CONFIGURACIÓN: se requiere MS2_DATABASE_URL con postgresql+psycopg://.")
            return 2
        engine = create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 5})
        with engine.connect() as conexion:
            codigo, lineas = comprobar(conexion, revisiones_codigo())
        print("\n".join(lineas))
        return codigo
    except Exception as exc:
        # La excepción original puede incluir credenciales, SQL o parámetros.
        print(f"No se pudo completar el diagnóstico ({type(exc).__name__}).")
        print("Revisar MS2_DATABASE_URL, conectividad y dependencias. No se aplicaron migraciones.")
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
