"""Inicialización de bases y datos de demostración, sin bases externas.

La validación contra PostgreSQL real está en docs/validacion-despliegue-limpio.md.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts import datos_demo, iniciar_servicio
from scripts import inicializar_bd as ini

CLAVE = "Xk3_largaYsegura-123456"


def _entorno(**cambios: str) -> dict[str, str]:
    entorno = {
        f"MS{i}_DATABASE_URL": f"postgresql+psycopg://sgtm_ms{i}:{CLAVE}@db:5432/sgtm_ms{i}"
        for i in range(1, 5)
    }
    entorno.update(cambios)
    return entorno


def test_configuracion_valida_respeta_el_orden_de_migracion():
    bases = ini.validar_configuracion(_entorno(), perfil="despliegue", exigir_tls=False)
    assert [b.servicio for b in bases] == ["MS1", "MS2", "MS3", "MS4"]
    assert all(not b.avisos for b in bases)


@pytest.mark.parametrize("cambio,mensaje", [
    ({"MS3_DATABASE_URL": ""}, "falta MS3_DATABASE_URL"),
    ({"MS2_DATABASE_URL": f"postgresql://sgtm_ms2:{CLAVE}@db/sgtm_ms2"}, "postgresql+psycopg"),
    ({"MS2_DATABASE_URL": f"postgresql+psycopg://sgtm_ms1:{CLAVE}@db:5432/sgtm_ms1"}, "misma base"),
    ({"MS4_DATABASE_URL": "postgresql+psycopg://taller:taller@db:5432/sgtm_ms4"}, "clave de base"),
    ({"MS1_DATABASE_URL": f"postgresql+psycopg://postgres:{CLAVE}@db:5432/sgtm_ms1"}, "propio rol"),
])
def test_configuracion_invalida_se_rechaza_sin_exponer_claves(cambio, mensaje):
    with pytest.raises(ini.ErrorPaso) as error:
        ini.validar_configuracion(_entorno(**cambio), perfil="despliegue", exigir_tls=False)
    assert mensaje in str(error.value)
    assert CLAVE not in str(error.value) and "taller:taller" not in str(error.value)


def test_perfil_local_admite_credenciales_de_desarrollo_como_aviso():
    entorno = {f"MS{i}_DATABASE_URL": f"postgresql+psycopg://taller:taller@localhost:543{2+i}/taller_ms{i}"
               for i in range(1, 5)}
    bases = ini.validar_configuracion(entorno, perfil="local", exigir_tls=False)
    assert all(b.avisos for b in bases)


def test_exigir_tls_requiere_sslmode_seguro():
    with pytest.raises(ini.ErrorPaso, match="sslmode"):
        ini.validar_configuracion(_entorno(), perfil="despliegue", exigir_tls=True)
    seguras = {k: v + "?sslmode=require" for k, v in _entorno().items()}
    assert len(ini.validar_configuracion(seguras, perfil="despliegue", exigir_tls=True)) == 4


def test_configurar_genera_claves_distintas_y_no_reemplaza(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(ini, "BACKEND_DIR", tmp_path)
    destino = tmp_path / ".env.despliegue"
    assert ini.configurar(destino) == 0
    texto = destino.read_text(encoding="utf-8")
    assert "__GENERAR__" not in texto and "${" not in texto
    valores = dict(linea.split("=", 1) for linea in texto.splitlines() if "=" in linea and not linea.startswith("#"))
    claves = [valores[f"SGTM_MS{i}_BD_CLAVE"] for i in range(1, 5)]
    assert len(set(claves)) == 4 and all(len(c) >= 32 for c in claves)
    assert claves[0] in valores["MS1_DATABASE_URL"]
    ini.validar_configuracion(valores, perfil="despliegue", exigir_tls=False)
    antes = destino.read_text(encoding="utf-8")
    assert ini.configurar(destino) == 0
    assert destino.read_text(encoding="utf-8") == antes


def test_contenedor_ejecuta_las_migraciones_y_termina():
    argumentos = iniciar_servicio.comando({"SGTM_SERVICIO": "migraciones"})
    assert argumentos[-1].endswith("inicializar_bd.py")
    assert "uvicorn" not in argumentos


def test_limpiar_exige_confirmacion_antes_de_conectar(capsys):
    assert datos_demo.main(["limpiar"]) == 2
    assert datos_demo.main(["reiniciar", "--confirmar", "si"]) == 2
    assert "LIMPIAR-DEMO" in capsys.readouterr().err


def test_datos_controlados_esperados_son_coherentes():
    datos = datos_demo.esperado()
    assert len(datos["correos"]) == 7 and len(set(datos["correos"])) == 7
    assert len(datos["clientes"]) == 4
    assert datos["escenarios"]["DEMO09"] is None
    assert datos["escenarios"]["DEMO07"] == 8 and datos["escenarios"]["DEMO04"] == 5


def test_initdb_no_contiene_claves_y_lee_el_entorno():
    sql = (Path(ini.BACKEND_DIR) / "despliegue/initdb/10-crear-bases-servicios.sql").read_text(encoding="utf-8")
    for i in range(1, 5):
        assert f"\\getenv clave_ms{i} SGTM_MS{i}_BD_CLAVE" in sql
    assert "REVOKE ALL ON DATABASE" in sql and "NOSUPERUSER" in sql
    assert "\r" not in sql
