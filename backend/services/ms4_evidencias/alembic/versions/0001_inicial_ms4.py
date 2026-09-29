"""Inicial MS4: evidencia

Revision ID: 0001_ms4
Revises:
Create Date: 2026-09-26

Crea la tabla de metadatos de evidencia multimedia según el MER (recuadro
"BD MS4") y el estudio de almacenamiento (docs/modelo-evidencias.md): la
evidencia tiene DOS piezas — el archivo vive en MinIO/S3 (`clave_objeto`,
`tamano_bytes`, `sha256`) y el METADATO vive acá, en el PostgreSQL de MS4.

`orden_id`, `presupuesto_id`, `autor_usuario_id` y `eliminada_por_usuario_id`
son referencias LÓGICAS a MS1/MS2/MS3 (sin FK física, §8): se guardan como enteros.

A diferencia de una migración autogenerada, esta tabla se escribe A MANO (regla
establecida en MS2): no importa el modelo, declara los objetos de schema
explícitamente para que la migración sea auditable e idéntica para todos. Los
CHECK se declaran INLINE dentro del CREATE TABLE (así la misma migración corre
igual en PostgreSQL y en SQLite, dialecto donde no existe ALTER de CHECK) y su
nombre se pasa SIN prefijo: la convención de nombres (shared/db.py) lo antepone
→ ck_evidencia_*, igual que declaran los modelos en __table_args__.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# identificadores de la revisión, usados por Alembic.
revision: str = "0001_ms4"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- EVIDENCIA ---
    op.create_table(
        "evidencia",
        sa.Column("evidencia_id", sa.Uuid(), nullable=False),
        # orden_id: REF lógica a Orden de Trabajo (MS2). Sin ForeignKey física.
        sa.Column("orden_id", sa.Integer(), nullable=False),
        # presupuesto_id: REF lógica a Presupuesto (MS3), solo si contexto=presupuesto.
        sa.Column("presupuesto_id", sa.Integer(), nullable=True),
        # autor_usuario_id: REF lógica a Usuario (MS1). Sin ForeignKey física.
        sa.Column("autor_usuario_id", sa.Integer(), nullable=False),
        sa.Column("contexto", sa.String(length=20), nullable=False),
        sa.Column("tipo_archivo", sa.String(length=10), nullable=False),
        sa.Column("visible_cliente", sa.Boolean(), nullable=False),
        sa.Column("estado", sa.String(length=12), nullable=False),
        # clave_objeto: única referencia al objeto en MinIO/S3 (nunca se usa el
        # nombre original para construir rutas; checklist de seguridad 2.5).
        sa.Column("clave_objeto", sa.String(length=512), nullable=False),
        sa.Column("nombre_original", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("tamano_bytes", sa.BigInteger(), nullable=False),
        # sha256 se llena cuando la evidencia pasa a confirmada (flujo C).
        sa.Column("sha256", sa.CHAR(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column(
            "creada_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("confirmada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eliminada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eliminada_por_usuario_id", sa.Integer(), nullable=True),
        # Regla 1: contexto dentro de los 4 valores del MER.
        sa.CheckConstraint(
            "contexto in ('diagnostico', 'presupuesto', 'reparacion', 'resultado_final')",
            name="contexto_valido",
        ),
        # Regla 2: tipo_archivo es foto o video.
        sa.CheckConstraint(
            "tipo_archivo in ('foto', 'video')",
            name="tipo_archivo_valido",
        ),
        # Regla 3: estado dentro de los 3 valores del flujo C.
        sa.CheckConstraint(
            "estado in ('pendiente', 'confirmada', 'anulada')",
            name="estado_valido",
        ),
        # Regla 4: un archivo de evidencia siempre pesa más que cero.
        sa.CheckConstraint("tamano_bytes > 0", name="tamano_positivo"),
        # Regla 5: si hay sha256, es un hash hex de 64 caracteres (SHA-256).
        sa.CheckConstraint(
            "sha256 is null or length(sha256) = 64",
            name="sha256_longitud_64",
        ),
        # Regla 6: contexto presupuesto ⟷ presupuesto_id, ambos juntos o ambos no.
        sa.CheckConstraint(
            "(contexto = 'presupuesto' and presupuesto_id is not null) "
            "or (contexto <> 'presupuesto' and presupuesto_id is null)",
            name="presupuesto_coherente",
        ),
        # Regla 7: la evidencia del presupuesto SIEMPRE es visible para el cliente.
        sa.CheckConstraint(
            "contexto <> 'presupuesto' or visible_cliente = true",
            name="presupuesto_siempre_visible",
        ),
        # Regla 8: confirmada exige fecha de confirmación y sha256 (control 2.4).
        sa.CheckConstraint(
            "estado <> 'confirmada' or (confirmada_en is not null and sha256 is not null)",
            name="confirmada_completa",
        ),
        # Regla 9: eliminación lógica — o están los dos campos o ninguno.
        sa.CheckConstraint(
            "(eliminada_en is null) = (eliminada_por_usuario_id is null)",
            name="eliminacion_completa",
        ),
        # Referencias lógicas a MS1/MS2/MS3: ids positivos (mismo criterio que MS2).
        sa.CheckConstraint(
            "orden_id > 0 and autor_usuario_id > 0 "
            "and (presupuesto_id is null or presupuesto_id > 0) "
            "and (eliminada_por_usuario_id is null or eliminada_por_usuario_id > 0)",
            name="referencias_positivas",
        ),
        sa.PrimaryKeyConstraint("evidencia_id", name="pk_evidencia"),
        sa.UniqueConstraint("clave_objeto", name="uq_evidencia_clave_objeto"),
    )

    # Índices del modelo (mismos nombres que en models/evidencia.py):
    # consulta principal de la recepción y soporte de RF18.
    op.create_index("ix_evidencia_orden_contexto", "evidencia", ["orden_id", "contexto"])
    op.create_index("ix_evidencia_presupuesto", "evidencia", ["presupuesto_id"])


def downgrade() -> None:
    op.drop_index("ix_evidencia_presupuesto", table_name="evidencia")
    op.drop_index("ix_evidencia_orden_contexto", table_name="evidencia")
    op.drop_table("evidencia")
