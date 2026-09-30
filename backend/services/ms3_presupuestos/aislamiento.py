"""Verificación de aislamiento de la base de datos de MS3 (Sistematización §8).

Regla: cada microservicio tiene SU base. MS3 no comparte tablas con MS1, MS2
ni MS4, no tiene claves foráneas físicas hacia ellas y no las alcanza por
extensiones como dblink o postgres_fdw. Las relaciones con otros servicios
(orden de trabajo, usuarios) son REFERENCIAS LÓGICAS: un id sin FK que se
valida por contrato de API.

Cada función devuelve una lista de problemas en texto; lista vacía = aislado.
La usan las pruebas (tests/test_ms3_aislamiento.py y
ms3_presupuestos/tests/test_aislamiento_bd.py) y el script
scripts/verificar_aislamiento_ms3.py, que revisa una base real (local o Neon).
"""
from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import MetaData, text
from sqlalchemy.engine import Connection, make_url

# Columnas que apuntan a datos de OTROS servicios. Deben existir como enteros
# y NO pueden tener clave foránea (la tabla destino vive en otra base).
REFERENCIAS_LOGICAS: dict[str, dict[str, str]] = {
    "presupuesto": {"orden_id": "MS2.orden_trabajo"},
    "version_presupuesto": {"creado_por_id": "MS1.usuario"},
    "decision_presupuesto": {"cliente_usuario_id": "MS1.usuario"},
    "movimiento_inventario": {"orden_id": "MS2.orden_trabajo",
                              "registrado_por_id": "MS1.usuario"},
    "parametro_inventario": {"actualizado_por_id": "MS1.usuario"},
    "historial_umbral": {"administrador_id": "MS1.usuario"},
}

# Tablas técnicas que pueden existir en la base además de las del modelo.
TABLAS_TECNICAS = frozenset({"alembic_version"})

# Extensiones que permitirían leer otras bases desde MS3.
EXTENSIONES_PROHIBIDAS = frozenset({"dblink", "postgres_fdw"})


# ------------------------------------------------------------------- modelo --

def problemas_de_metadata(
    propia: MetaData, ajenas: Mapping[str, MetaData] | None = None
) -> list[str]:
    """Revisa el modelo ORM de MS3 sin conectarse a ninguna base."""
    problemas: list[str] = []
    tablas = set(propia.tables)

    for tabla in propia.tables.values():
        for fk in tabla.foreign_keys:
            destino = fk.target_fullname.split(".")[-2]
            if destino not in tablas:
                problemas.append(
                    f"FK {tabla.name}.{fk.parent.name} -> {fk.target_fullname} "
                    "apunta fuera de MS3"
                )

    for nombre_tabla, columnas in REFERENCIAS_LOGICAS.items():
        tabla = propia.tables.get(nombre_tabla)
        if tabla is None:
            problemas.append(f"falta la tabla {nombre_tabla} en el modelo de MS3")
            continue
        for columna, destino in columnas.items():
            if columna not in tabla.c:
                problemas.append(f"falta la referencia lógica {nombre_tabla}.{columna}")
            elif tabla.c[columna].foreign_keys:
                problemas.append(
                    f"{nombre_tabla}.{columna} es referencia lógica a {destino} "
                    "y no puede tener FK"
                )

    for servicio, metadata in (ajenas or {}).items():
        if metadata is propia:
            problemas.append(f"MS3 comparte el MetaData con {servicio}")
            continue
        repetidas = tablas & set(metadata.tables)
        if repetidas:
            problemas.append(f"tablas compartidas con {servicio}: {sorted(repetidas)}")
    return problemas


# --------------------------------------------------------------- conexiones --

def _destino(url: str) -> tuple[str | None, int | None, str | None]:
    u = make_url(url)
    return (u.host, u.port, u.database)


def problemas_de_urls(propia: str, ajenas: Mapping[str, str]) -> list[str]:
    """MS3 no puede apuntar a la misma base (host, puerto, nombre) que otro servicio.

    Compartir servidor está permitido (Neon: un host, varias bases); compartir
    base no.
    """
    destino = _destino(propia)
    problemas = []
    if not destino[2]:
        problemas.append("MS3_DATABASE_URL no indica el nombre de la base")
    for servicio, url in ajenas.items():
        if url and _destino(url) == destino:
            problemas.append(f"MS3 usa la misma base que {servicio}: {destino[2]}")
    return problemas


# --------------------------------------------------------------- base real --

_SQL_TABLAS = text("""
    select table_name from information_schema.tables
    where table_schema = current_schema() and table_type = 'BASE TABLE'
""")

_SQL_FKS = text("""
    select con.conname, origen.relname as tabla, destino.relname as destino,
           nsp_destino.nspname as esquema_destino
    from pg_constraint con
    join pg_class origen on origen.oid = con.conrelid
    join pg_class destino on destino.oid = con.confrelid
    join pg_namespace nsp_destino on nsp_destino.oid = destino.relnamespace
    where con.contype = 'f'
      and origen.relnamespace = current_schema()::regnamespace
""")

_SQL_EXTENSIONES = text("select extname from pg_extension")
_SQL_TABLAS_FORANEAS = text("select count(*) from information_schema.foreign_tables")


def problemas_en_base(conexion: Connection, propia: MetaData) -> list[str]:
    """Revisa la base a la que está conectada MS3 (local o Neon)."""
    problemas: list[str] = []
    esperadas = set(propia.tables)
    presentes = set(conexion.execute(_SQL_TABLAS).scalars())

    extra = presentes - esperadas - TABLAS_TECNICAS
    if extra:
        problemas.append(f"tablas que no son de MS3 en su base: {sorted(extra)}")
    faltan = esperadas - presentes
    if faltan:
        problemas.append(f"faltan tablas de MS3 (¿migraciones?): {sorted(faltan)}")

    for fk in conexion.execute(_SQL_FKS).mappings():
        if fk["destino"] not in esperadas:
            problemas.append(
                f"FK {fk['conname']} ({fk['tabla']} -> "
                f"{fk['esquema_destino']}.{fk['destino']}) apunta fuera de MS3"
            )

    extensiones = set(conexion.execute(_SQL_EXTENSIONES).scalars())
    for ext in sorted(extensiones & EXTENSIONES_PROHIBIDAS):
        problemas.append(f"extensión {ext} instalada: permite leer otras bases")

    foraneas = conexion.execute(_SQL_TABLAS_FORANEAS).scalar()
    if foraneas:
        problemas.append(f"hay {foraneas} tablas foráneas (FDW) en la base de MS3")
    return problemas
