"""DDL PostgreSQL de las migraciones aditivas de coordinación de decisiones."""
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from services.ms2_taller.models import Base as BaseMS2
from services.ms3_presupuestos.models import Base as BaseMS3


@pytest.mark.parametrize("servicio,archivo,base,columna,restriccion,revision,anterior", [
    ("ms2_taller", "0006_decisiones_presupuesto_ms2.py", BaseMS2,
     "decision_presupuesto_id", "uq_historial_estado_decision_presupuesto_id",
     "0006_ms2", "0005_ms2"),
    ("ms2_taller", "0007_envio_presupuesto_ms2.py", BaseMS2,
     "envio_presupuesto_id", "uq_historial_estado_envio_presupuesto_id",
     "0007_envio_ms2", "0006_ms2"),
    ("ms3_presupuestos", "0004_stock_decision_ms3.py", BaseMS3,
     "repuestos_disponibles", "ck_decision_presupuesto_stock_solo_aprobacion",
     "0004_ms3", "0003_ms3"),
])
def test_migracion_agrega_referencia_o_snapshot_sin_reescribir_historia(
    servicio, archivo, base, columna, restriccion, revision, anterior,
):
    script = ScriptDirectory.from_config(Config(f"services/{servicio}/alembic.ini"))
    assert revision in {rev.revision for rev in script.walk_revisions()}
    assert script.get_revision(revision).down_revision == anterior
    ruta = Path(__file__).resolve().parents[1] / "services" / servicio / "alembic" / "versions" / archivo
    spec = spec_from_file_location(f"migracion_{revision}", ruta)
    modulo = module_from_spec(spec)
    spec.loader.exec_module(modulo)

    def sql(operacion):
        buffer = StringIO()
        contexto = MigrationContext.configure(dialect_name="postgresql", opts={
            "as_sql": True, "output_buffer": buffer, "target_metadata": base.metadata,
        })
        with Operations.context(contexto):
            operacion()
        return buffer.getvalue()

    upgrade = sql(modulo.upgrade)
    assert f"ADD COLUMN {columna}" in upgrade
    assert restriccion in upgrade
    assert "NOT NULL" not in upgrade and "DEFAULT" not in upgrade
    assert "UPDATE " not in upgrade and "DELETE " not in upgrade
    assert "FOREIGN KEY" not in upgrade
    downgrade = sql(modulo.downgrade)
    assert f"DROP COLUMN {columna}" in downgrade
    assert f"DROP CONSTRAINT {restriccion}" in downgrade


def test_migracion_cupo_diario_agrega_configuracion_y_auditoria():
    script = ScriptDirectory.from_config(Config("services/ms2_taller/alembic.ini"))
    assert script.get_heads() == ["0011_ms2"]
    assert script.get_revision("0009_ms2").down_revision == "0008_ms2"
    ruta = (
        Path(__file__).resolve().parents[1]
        / "services/ms2_taller/alembic/versions/0009_cupo_diario_ingresos_ms2.py"
    )
    spec = spec_from_file_location("migracion_0009_ms2", ruta)
    modulo = module_from_spec(spec)
    spec.loader.exec_module(modulo)

    def sql(operacion):
        buffer = StringIO()
        contexto = MigrationContext.configure(
            dialect_name="postgresql",
            opts={"as_sql": True, "output_buffer": buffer, "target_metadata": BaseMS2.metadata},
        )
        with Operations.context(contexto):
            operacion()
        return buffer.getvalue()

    upgrade = sql(modulo.upgrade)
    assert "CREATE TABLE configuracion_cupo_ingresos" in upgrade
    assert "CREATE TABLE historial_configuracion_cupo_ingresos" in upgrade
    assert "CREATE TABLE historial_validacion_cupo_ingreso" in upgrade
    assert "INSERT INTO configuracion_cupo_ingresos" in upgrade
    assert "ix_ingreso_vehiculo_fecha_hora" in upgrade
    downgrade = sql(modulo.downgrade)
    assert "DROP TABLE historial_validacion_cupo_ingreso" in downgrade
    assert "DROP TABLE historial_configuracion_cupo_ingresos" in downgrade
    assert "DROP TABLE configuracion_cupo_ingresos" in downgrade
