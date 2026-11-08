"""El diagnóstico identifica desajustes sin ejecutar migraciones ni revelar DSN."""
from types import SimpleNamespace

import pytest

from scripts import diagnosticar_ms2 as diagnostico


def preparar(monkeypatch, *, actuales=("head",), faltante=None, sin_tabla=None):
    instrucciones = []
    conexion = SimpleNamespace(exec_driver_sql=instrucciones.append)
    scripts = SimpleNamespace(
        get_heads=lambda: ["head"],
        walk_revisions=lambda: [SimpleNamespace(revision=r) for r in ("anterior", "head")],
    )
    inspector = SimpleNamespace(
        get_table_names=lambda: set(diagnostico.COLUMNAS) - {sin_tabla},
        get_columns=lambda tabla: [
            {"name": c} for c in diagnostico.COLUMNAS[tabla]
            if (tabla, c) != faltante
        ],
    )
    monkeypatch.setattr(diagnostico, "inspect", lambda _: inspector)
    monkeypatch.setattr(
        diagnostico.MigrationContext, "configure",
        lambda _: SimpleNamespace(get_current_heads=lambda: actuales),
    )
    return conexion, scripts, instrucciones


def test_diagnostico_completo_solo_habilita_transaccion_de_lectura(monkeypatch):
    conexion, scripts, sql = preparar(monkeypatch)
    codigo, lineas = diagnostico.comprobar(conexion, scripts)
    assert codigo == 0
    assert sql == ["SET TRANSACTION READ ONLY", "SET LOCAL statement_timeout = '5s'"]
    assert not any("FALTA" in linea for linea in lineas)


def test_detecta_columna_que_puede_romper_el_listado(monkeypatch):
    conexion, scripts, _ = preparar(
        monkeypatch, faltante=("historial_estado", "envio_presupuesto_id"),
    )
    codigo, lineas = diagnostico.comprobar(conexion, scripts)
    assert codigo == 1
    assert "FALTAN COLUMNAS: historial_estado: envio_presupuesto_id" in lineas


def test_detecta_tabla_de_capacidad_ausente(monkeypatch):
    conexion, scripts, _ = preparar(monkeypatch, sin_tabla="configuracion_capacidad_mecanico")
    codigo, lineas = diagnostico.comprobar(conexion, scripts)
    assert codigo == 1
    assert "FALTA TABLA: configuracion_capacidad_mecanico" in lineas


@pytest.mark.parametrize("actuales", [(), ("anterior",)])
def test_reporta_base_sin_version_o_atrasada(monkeypatch, actuales):
    conexion, scripts, _ = preparar(monkeypatch, actuales=actuales)
    assert diagnostico.comprobar(conexion, scripts)[0] == 1


def test_revision_ajena_no_se_presenta_como_simple_migracion_pendiente(monkeypatch):
    conexion, scripts, _ = preparar(monkeypatch, actuales=("otra_rama",))
    codigo, lineas = diagnostico.comprobar(conexion, scripts)
    assert codigo == 2
    assert lineas[-1].startswith("INCOMPATIBLE:")


def test_error_de_configuracion_no_imprime_credenciales(monkeypatch, capsys):
    def fallar():
        raise ValueError("postgresql+psycopg://usuario:secreto@host/base")

    monkeypatch.setattr(diagnostico, "EntornoMS2", fallar)
    assert diagnostico.main() == 2
    salida = capsys.readouterr().out
    assert "secreto" not in salida
    assert "usuario" not in salida
    assert "ValueError" in salida


def test_rechaza_dsn_de_otro_motor_sin_abrir_conexion(monkeypatch):
    monkeypatch.setattr(
        diagnostico, "EntornoMS2",
        lambda: SimpleNamespace(database_url=SimpleNamespace(get_secret_value=lambda: "sqlite://")),
    )
    monkeypatch.setattr(diagnostico, "create_engine", lambda *a, **k: pytest.fail("No debe conectar"))
    assert diagnostico.main() == 2


def test_revisiones_se_leen_sin_importar_la_aplicacion():
    scripts = diagnostico.revisiones_codigo()
    assert scripts.get_heads() == ["0014_nueva_atencion_ms2"]


@pytest.mark.parametrize("tabla", tuple(diagnostico.COLUMNAS))
def test_diagnostico_cubre_las_columnas_actuales_de_cada_modelo(tabla):
    from services.ms2_taller.models import Base

    assert diagnostico.COLUMNAS[tabla] == set(Base.metadata.tables[tabla].columns.keys())


def test_detecta_clave_de_disponibilidad_ausente_aunque_alembic_diga_head(monkeypatch):
    columna = "disponibilidad_repuestos_clave_operacion"
    conexion, scripts, _ = preparar(monkeypatch, faltante=("historial_estado", columna))
    codigo, lineas = diagnostico.comprobar(conexion, scripts)
    assert codigo == 1
    assert f"FALTAN COLUMNAS: historial_estado: {columna}" in lineas
