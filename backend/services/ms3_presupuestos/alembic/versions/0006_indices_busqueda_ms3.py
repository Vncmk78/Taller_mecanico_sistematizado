"""Índices de búsqueda de repuestos y proveedores — MS3.

Revision ID: 0006_ms3
Revises: 0005_ms3

Semana 5 · "Agregar índices y filtros necesarios para búsquedas de repuestos y
proveedores".

Las búsquedas de la API son "contiene el texto", sin distinguir mayúsculas ni
tildes ("bujia" encuentra "Bujía"):

    ms3_normalizar(nombre) LIKE '%' || ms3_normalizar(:texto) || '%'

Un índice B-tree no sirve para '%texto%'; se usan índices GIN de trigramas
(pg_trgm) sobre la expresión normalizada. Además:

- ms3_normalizar(text): lower(unaccent(texto)), IMMUTABLE para poder indexarla
  (unaccent() por sí sola es STABLE y PostgreSQL no permite indexarla).
- ix_repuesto_nombre_orden / ix_proveedor_nombre_orden: B-tree por
  lower(nombre) para listar ordenado y paginar sin ordenar toda la tabla.
- uq_proveedor_nombre_ci: un proveedor no se repite cambiando mayúsculas
  ("Frenos del Sur" = "FRENOS DEL SUR"); antes solo lo validaba el service.

pg_trgm y unaccent son extensiones "trusted": el dueño de la base puede
instalarlas sin superusuario (Neon: neondb_owner). Se instalan en `public` y se
referencian calificadas para que funcionen con cualquier search_path.
"""
from alembic import op

revision = "0006_ms3"
down_revision = "0005_ms3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public")
    op.execute("""
        CREATE OR REPLACE FUNCTION ms3_normalizar(texto text) RETURNS text
        LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
        AS $$ SELECT lower(public.unaccent('public.unaccent'::regdictionary, texto)) $$
    """)
    op.execute("""
        CREATE INDEX ix_repuesto_nombre_trgm ON repuesto
        USING gin (ms3_normalizar(nombre) public.gin_trgm_ops)
    """)
    op.execute("""
        CREATE INDEX ix_proveedor_nombre_trgm ON proveedor
        USING gin (ms3_normalizar(nombre) public.gin_trgm_ops)
    """)
    op.execute("""
        CREATE INDEX ix_proveedor_contacto_trgm ON proveedor
        USING gin (ms3_normalizar(contacto) public.gin_trgm_ops)
    """)
    op.execute("CREATE INDEX ix_repuesto_nombre_orden ON repuesto (lower(nombre), repuesto_id)")
    op.execute("CREATE INDEX ix_proveedor_nombre_orden ON proveedor (lower(nombre), proveedor_id)")
    op.execute("CREATE UNIQUE INDEX uq_proveedor_nombre_ci ON proveedor (lower(nombre))")


def downgrade() -> None:
    for indice in ("uq_proveedor_nombre_ci", "ix_proveedor_nombre_orden",
                   "ix_repuesto_nombre_orden", "ix_proveedor_contacto_trgm",
                   "ix_proveedor_nombre_trgm", "ix_repuesto_nombre_trgm"):
        op.execute(f"DROP INDEX IF EXISTS {indice}")
    op.execute("DROP FUNCTION IF EXISTS ms3_normalizar(text)")
    # Las extensiones se dejan instaladas: pueden usarlas otros objetos.
