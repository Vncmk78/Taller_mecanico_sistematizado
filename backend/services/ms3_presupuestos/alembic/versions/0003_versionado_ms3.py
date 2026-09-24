"""Versionado de presupuestos y bloqueo de la versión aprobada (Semana 3) — MS3

Revision ID: 0003_ms3
Revises: 0002_ms3
Create Date: 2026-09-24

Estructura de versionado (§4.3):

- version_presupuesto: columnas es_modificacion y bloqueada_en, con CHECKs
  (solo se bloquea lo enviado; la versión 1 no es modificación).
- decision_presupuesto (nueva): decisión del cliente, única por versión; el
  rechazo exige motivo.

Reglas que se hacen cumplir con TRIGGERS (un CHECK no puede mirar otras filas
ni el valor anterior de la fila):

1. Numeración correlativa: cada versión nueva es max(numero) + 1 del presupuesto.
2. Versión enviada congelada: después de enviar solo se permite registrar el
   bloqueo; no se editan sus datos ni se borra.
3. Versión bloqueada: no admite ningún cambio más.
4. Ítems: solo se agregan, cambian o borran mientras la versión es borrador.
5. Decisión: solo sobre una versión enviada; aprobar bloquea la versión
   automáticamente; la decisión no se modifica ni se borra.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# identificadores de la revisión, usados por Alembic.
revision: str = "0003_ms3"
down_revision: Union[str, None] = "0002_ms3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FUNCIONES_Y_TRIGGERS = r"""
-- 1) Numeración correlativa de versiones --------------------------------------
CREATE FUNCTION fn_version_numero_correlativo() RETURNS trigger AS $$
DECLARE
    esperado integer;
BEGIN
    -- Bloquea el presupuesto para que dos versiones simultáneas no tomen el
    -- mismo número.
    PERFORM 1 FROM presupuesto WHERE presupuesto_id = NEW.presupuesto_id FOR UPDATE;
    SELECT coalesce(max(numero), 0) + 1 INTO esperado
      FROM version_presupuesto WHERE presupuesto_id = NEW.presupuesto_id;
    IF NEW.numero <> esperado THEN
        RAISE EXCEPTION 'La nueva versión del presupuesto % debe ser la número % (se recibió %)',
            NEW.presupuesto_id, esperado, NEW.numero
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_version_numero_correlativo
    BEFORE INSERT ON version_presupuesto
    FOR EACH ROW EXECUTE FUNCTION fn_version_numero_correlativo();

-- 2) y 3) Versión enviada congelada / versión bloqueada inmutable ------------
CREATE FUNCTION fn_version_proteger() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.enviado_en IS NOT NULL THEN
            RAISE EXCEPTION 'La versión % ya fue enviada y no se puede borrar', OLD.version_id
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN OLD;
    END IF;

    IF OLD.bloqueada_en IS NOT NULL THEN
        RAISE EXCEPTION 'La versión % está aprobada y bloqueada; cree una nueva versión', OLD.version_id
            USING ERRCODE = 'check_violation';
    END IF;

    IF OLD.enviado_en IS NOT NULL THEN
        -- Enviada: lo único permitido es pasar de no bloqueada a bloqueada.
        IF (NEW.presupuesto_id, NEW.numero, NEW.creado_por_id, NEW.creado_en,
            NEW.enviado_en, NEW.es_modificacion)
           IS DISTINCT FROM
           (OLD.presupuesto_id, OLD.numero, OLD.creado_por_id, OLD.creado_en,
            OLD.enviado_en, OLD.es_modificacion)
        THEN
            RAISE EXCEPTION 'La versión % ya fue enviada; las correcciones van en una nueva versión', OLD.version_id
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_version_proteger
    BEFORE UPDATE OR DELETE ON version_presupuesto
    FOR EACH ROW EXECUTE FUNCTION fn_version_proteger();

-- 4) Ítems solo editables en borrador -----------------------------------------
CREATE FUNCTION fn_item_solo_en_borrador() RETURNS trigger AS $$
DECLARE
    v_id integer;
    v_enviado timestamptz;
BEGIN
    IF TG_OP = 'DELETE' THEN v_id := OLD.version_id; ELSE v_id := NEW.version_id; END IF;
    SELECT enviado_en INTO v_enviado FROM version_presupuesto WHERE version_id = v_id;
    IF v_enviado IS NOT NULL THEN
        RAISE EXCEPTION 'La versión % ya fue enviada; sus ítems no se pueden modificar', v_id
            USING ERRCODE = 'check_violation';
    END IF;
    -- Un ítem no puede cambiarse de versión.
    IF TG_OP = 'UPDATE' AND NEW.version_id <> OLD.version_id THEN
        RAISE EXCEPTION 'Un ítem no puede moverse a otra versión'
            USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_item_solo_en_borrador
    BEFORE INSERT OR UPDATE OR DELETE ON item_presupuesto
    FOR EACH ROW EXECUTE FUNCTION fn_item_solo_en_borrador();

-- 5) Decisión: sobre versión enviada, aprobar bloquea, inmutable -------------
CREATE FUNCTION fn_decision_registrar() RETURNS trigger AS $$
DECLARE
    v_enviado timestamptz;
BEGIN
    SELECT enviado_en INTO v_enviado
      FROM version_presupuesto WHERE version_id = NEW.version_id FOR UPDATE;
    IF v_enviado IS NULL THEN
        RAISE EXCEPTION 'La versión % aún no se envía al cliente; no se puede decidir sobre ella', NEW.version_id
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.fecha_hora < v_enviado THEN
        RAISE EXCEPTION 'La decisión no puede ser anterior al envío de la versión'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.decision = 'aprobado' THEN
        UPDATE version_presupuesto SET bloqueada_en = NEW.fecha_hora
         WHERE version_id = NEW.version_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_decision_registrar
    AFTER INSERT ON decision_presupuesto
    FOR EACH ROW EXECUTE FUNCTION fn_decision_registrar();

CREATE FUNCTION fn_decision_inmutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Las decisiones de presupuesto son históricas: no se modifican ni se borran'
        USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_decision_inmutable
    BEFORE UPDATE OR DELETE ON decision_presupuesto
    FOR EACH ROW EXECUTE FUNCTION fn_decision_inmutable();
"""

BORRAR_FUNCIONES_Y_TRIGGERS = """
DROP TRIGGER IF EXISTS trg_decision_inmutable ON decision_presupuesto;
DROP TRIGGER IF EXISTS trg_decision_registrar ON decision_presupuesto;
DROP TRIGGER IF EXISTS trg_item_solo_en_borrador ON item_presupuesto;
DROP TRIGGER IF EXISTS trg_version_proteger ON version_presupuesto;
DROP TRIGGER IF EXISTS trg_version_numero_correlativo ON version_presupuesto;
DROP FUNCTION IF EXISTS fn_decision_inmutable();
DROP FUNCTION IF EXISTS fn_decision_registrar();
DROP FUNCTION IF EXISTS fn_item_solo_en_borrador();
DROP FUNCTION IF EXISTS fn_version_proteger();
DROP FUNCTION IF EXISTS fn_version_numero_correlativo();
"""


def upgrade() -> None:
    # --- VERSIÓN: marca de modificación y bloqueo ---
    op.add_column(
        "version_presupuesto",
        sa.Column("es_modificacion", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "version_presupuesto",
        sa.Column("bloqueada_en", sa.DateTime(timezone=True), nullable=True),
    )
    # El nombre va sin prefijo: la convención de nombres antepone ck_<tabla>_.
    op.create_check_constraint(
        "bloqueo_requiere_envio",
        "version_presupuesto",
        "bloqueada_en is null or (enviado_en is not null and bloqueada_en >= enviado_en)",
    )
    op.create_check_constraint(
        "primera_no_es_modificacion",
        "version_presupuesto",
        "numero > 1 or not es_modificacion",
    )

    # --- DECISIÓN DEL CLIENTE ---
    # cliente_usuario_id: REF lógica a MS1, sin FK física (§8).
    op.create_table(
        "decision_presupuesto",
        sa.Column("decision_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("cliente_usuario_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=10), nullable=False),
        sa.Column("fecha_hora", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "decision in ('aprobado', 'rechazado')",
            name=op.f("ck_decision_presupuesto_decision_valida"),
        ),
        sa.CheckConstraint(
            "decision <> 'rechazado' or (motivo is not null and btrim(motivo) <> '')",
            name=op.f("ck_decision_presupuesto_rechazo_con_motivo"),
        ),
        sa.CheckConstraint(
            "cliente_usuario_id > 0",
            name=op.f("ck_decision_presupuesto_cliente_positivo"),
        ),
        sa.ForeignKeyConstraint(
            ["version_id"], ["version_presupuesto.version_id"],
            name=op.f("fk_decision_presupuesto_version_id_version_presupuesto"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("decision_id", name=op.f("pk_decision_presupuesto")),
        sa.UniqueConstraint("version_id", name=op.f("uq_decision_presupuesto_version_id")),
    )

    # --- REGLAS DE VERSIONADO Y BLOQUEO (triggers) ---
    op.execute(FUNCIONES_Y_TRIGGERS)


def downgrade() -> None:
    op.execute(BORRAR_FUNCIONES_Y_TRIGGERS)
    op.drop_table("decision_presupuesto")
    op.drop_constraint(op.f("ck_version_presupuesto_primera_no_es_modificacion"), "version_presupuesto", type_="check")
    op.drop_constraint(op.f("ck_version_presupuesto_bloqueo_requiere_envio"), "version_presupuesto", type_="check")
    op.drop_column("version_presupuesto", "bloqueada_en")
    op.drop_column("version_presupuesto", "es_modificacion")
