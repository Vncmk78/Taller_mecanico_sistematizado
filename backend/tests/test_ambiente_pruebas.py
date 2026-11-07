"""Aislamiento del ambiente de pruebas separado (scripts/ambiente_pruebas.py).

Comprueba sin Docker ni bases: que el Compose de pruebas no comparte nombres,
puertos, volúmenes, red ni bucket con el existente; que la verificación rechaza
cualquier destino del ambiente local existente (también los valores por defecto
del código que se usarían si faltara una variable); que los procesos hijos no
heredan variables de servicio de la terminal; que los servicios leen el archivo
indicado en SGTM_ENV_FILE en vez de `.env`; y que eliminar volúmenes exige la
confirmación y nombra siempre el proyecto y el archivo de pruebas.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from scripts import ambiente_pruebas as amb  # noqa: E402

COMPOSE_EXISTENTE = (BACKEND / "docker-compose.yml").read_text(encoding="utf-8")
COMPOSE_PRUEBAS = (BACKEND / "docker-compose.pruebas.yml").read_text(encoding="utf-8")


def _valores(patron: str, texto: str) -> set[str]:
    return set(re.findall(patron, texto, flags=re.MULTILINE))


def _puertos_host(texto: str) -> set[int]:
    return {int(p) for p in re.findall(r'"(?:127\.0\.0\.1:)?(\d+):\d+"', texto)}


# ── Compose ────────────────────────────────────────────────────────────────


def test_compose_de_pruebas_no_comparte_recursos_con_el_existente():
    contenedores_existentes = _valores(r"container_name:\s*(\S+)", COMPOSE_EXISTENTE)
    contenedores_pruebas = _valores(r"container_name:\s*(\S+)", COMPOSE_PRUEBAS)
    assert len(contenedores_pruebas) == 6
    assert all(c.startswith("sgtm_pruebas_") for c in contenedores_pruebas)
    assert not contenedores_pruebas & contenedores_existentes

    assert _puertos_host(COMPOSE_PRUEBAS) == {5443, 5444, 5445, 5446, 9010, 9011}
    assert not _puertos_host(COMPOSE_PRUEBAS) & _puertos_host(COMPOSE_EXISTENTE)
    assert not _puertos_host(COMPOSE_PRUEBAS) & amb.PUERTOS_EXISTENTES
    # Solo escuchan en este equipo.
    assert re.findall(r'"(\d+:\d+)"', COMPOSE_PRUEBAS) == []

    volumenes = _valores(r"^\s+name:\s*(sgtm_pruebas_\S+)", COMPOSE_PRUEBAS)
    assert volumenes == {f"sgtm_pruebas_pg_ms{n}" for n in range(1, 5)} | {
        "sgtm_pruebas_minio", "sgtm_pruebas_red"}
    assert re.search(r"^name: sgtm_pruebas$", COMPOSE_PRUEBAS, flags=re.MULTILINE)
    assert _valores(r"POSTGRES_DB:\s*(\S+)", COMPOSE_PRUEBAS) == {
        f"taller_ms{n}_pruebas" for n in range(1, 5)}


def test_compose_de_pruebas_no_tiene_credenciales_por_defecto():
    # `$${X}` es una variable del shell del contenedor, no una interpolación de Compose.
    variables = re.findall(r"(?<!\$)\$\{([A-Z0-9_]+)([^}]*)\}", COMPOSE_PRUEBAS)
    assert variables
    assert all(resto.startswith(":?") for _, resto in variables), variables
    assert "cambia-esta-clave" not in COMPOSE_PRUEBAS


def test_bucket_y_politica_de_pruebas_son_propios():
    assert "sgtm/evidencias-pruebas" in COMPOSE_PRUEBAS
    assert "sgtm/evidencias " not in COMPOSE_PRUEBAS
    assert 'tag set sgtm/evidencias-pruebas "ambiente=sgtm-pruebas"' in COMPOSE_PRUEBAS
    politica = json.loads((BACKEND / "minio/politica-ms4-pruebas.json").read_text("utf-8"))
    recursos = {r for s in politica["Statement"] for r in s["Resource"]}
    assert recursos == {"arn:aws:s3:::evidencias-pruebas", "arn:aws:s3:::evidencias-pruebas/*"}


def test_las_bases_nuevas_quedan_marcadas_al_inicializarse():
    script = (BACKEND / "pruebas/initdb/01-marcar-ambiente.sh").read_text("utf-8")
    assert f"IS '{amb.MARCA_BASE}'" in script
    assert "./pruebas/initdb:/docker-entrypoint-initdb.d:ro" in COMPOSE_PRUEBAS


# ── configuración ──────────────────────────────────────────────────────────


@pytest.fixture
def archivos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(amb, "ARCHIVO", tmp_path / ".env.pruebas")
    monkeypatch.setattr(amb, "ARCHIVO_EXISTENTE", tmp_path / ".env")
    (tmp_path / ".env").write_text(
        "MS1_JWT_SECRET_KEY=secreto-del-ambiente-existente-0123456789\n"
        "MS2_DATABASE_URL=postgresql+psycopg://taller:taller@localhost:5434/taller_ms2\n",
        encoding="utf-8",
    )
    assert amb.configurar() == 0
    return tmp_path


def _entorno_modificado(archivos: Path, **cambios: str | None) -> dict[str, str]:
    ruta = archivos / ".env.pruebas"
    lineas = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        clave = linea.split("=", 1)[0]
        if clave in cambios:
            if cambios[clave] is not None:
                lineas.append(f"{clave}={cambios[clave]}")
            continue
        lineas.append(linea)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return amb.entorno_pruebas()


def test_configurar_genera_secretos_propios_y_no_sobrescribe(archivos: Path, capsys):
    texto = (archivos / ".env.pruebas").read_text(encoding="utf-8")
    assert "<" not in texto
    assert amb.configurar() == 0
    assert (archivos / ".env.pruebas").read_text(encoding="utf-8") == texto
    salida = capsys.readouterr().out
    secretos = [linea.split("=", 1)[1] for linea in texto.splitlines()
                if linea.startswith(("PRUEBAS_PG_CLAVE=", "MS1_JWT_SECRET_KEY=", "MS4_S3_SECRET_KEY="))]
    assert len(secretos) == 3 and all(s and s not in salida for s in secretos)


def test_la_configuracion_generada_apunta_solo_al_ambiente_de_pruebas(archivos: Path):
    assert amb.verificar_configuracion(amb.entorno_pruebas()) == []


@pytest.mark.parametrize(
    ("cambios", "esperado"),
    [
        ({"MS2_DATABASE_URL": "postgresql+psycopg://sgtm_pruebas:x@localhost:5434/taller_ms2"},
         "MS2_DATABASE_URL debe ser 127.0.0.1:5444/taller_ms2_pruebas"),
        ({"GATEWAY_MS2_URL": "http://localhost:8002"}, "GATEWAY_MS2_URL debe apuntar"),
        ({"MS4_S3_BUCKET": "evidencias"}, "MS4_S3_BUCKET debe ser evidencias-pruebas"),
        ({"MS4_S3_ENDPOINT": "http://localhost:9000"}, "MS4_S3_ENDPOINT debe apuntar"),
        ({"GATEWAY_CORS_ORIGINS": "http://localhost:5173"}, "GATEWAY_CORS_ORIGINS solo admite"),
        ({"GATEWAY_CORS_ORIGIN_REGEX": r"https://.*\.vercel\.app"}, "debe quedar vacía"),
        ({"SGTM_AMBIENTE": "local"}, "SGTM_AMBIENTE debe ser 'pruebas'"),
    ],
)
def test_rechaza_destinos_ajenos(archivos: Path, cambios: dict, esperado: str):
    errores = amb.verificar_configuracion(_entorno_modificado(archivos, **cambios))
    assert any(esperado in e for e in errores), errores


def test_rechaza_secretos_del_ambiente_existente(archivos: Path):
    secreto = "secreto-del-ambiente-existente-0123456789"
    entorno = _entorno_modificado(
        archivos, **{f"MS{n}_JWT_SECRET_KEY": secreto for n in range(1, 5)}
    )
    errores = amb.verificar_configuracion(entorno)
    assert any("igual a la del .env existente" in e for e in errores), errores
    assert all(secreto not in e for e in errores)


def test_una_variable_faltante_se_detecta_tambien_por_su_valor_por_defecto(archivos: Path):
    """Sin MS3_MS2_URL, MS3 usaría http://localhost:8002 (el MS2 existente)."""

    errores = amb.verificar_configuracion(_entorno_modificado(archivos, MS3_MS2_URL=None))
    assert "MS3_MS2_URL: falta o está vacía" in errores
    assert any("ms3.MS2_URL apunta al ambiente existente (puerto 8002)" in e for e in errores)


def test_los_hijos_no_heredan_variables_de_servicio_de_la_terminal(
    archivos: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("MS2_DATABASE_URL", "postgresql+psycopg://taller:taller@localhost:5434/x")
    monkeypatch.setenv("MS3_MS2_URL", "http://localhost:8002")
    monkeypatch.setenv("VERCEL", "1")
    entorno = _entorno_modificado(archivos, MS3_MS2_URL=None)
    assert "MS3_MS2_URL" not in entorno
    assert "VERCEL" not in entorno
    assert entorno["MS2_DATABASE_URL"].endswith("@127.0.0.1:5444/taller_ms2_pruebas")
    assert entorno["SGTM_ENV_FILE"] == str(archivos / ".env.pruebas")


def test_sin_env_pruebas_no_se_ejecuta_nada(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(amb, "ARCHIVO", tmp_path / ".env.pruebas")
    with pytest.raises(amb.ErrorAmbiente, match="configurar"):
        amb.entorno_pruebas()


@pytest.mark.parametrize(("archivo", "esperado"), [(None, "existente"), (".env.pruebas", "pruebas")])
def test_los_servicios_leen_el_archivo_de_sgtm_env_file(tmp_path: Path, archivo, esperado):
    jwt = "MS2_JWT_SECRET_KEY=" + "j" * 40 + "\n"
    (tmp_path / ".env").write_text(
        jwt + "MS2_DATABASE_URL=postgresql+psycopg://u:p@localhost:5434/existente\n",
        encoding="utf-8")
    (tmp_path / ".env.pruebas").write_text(
        jwt + "MS2_DATABASE_URL=postgresql+psycopg://u:p@127.0.0.1:5444/pruebas\n",
        encoding="utf-8")
    entorno = {k: v for k, v in __import__("os").environ.items()
               if not k.startswith(("MS2_", "SGTM_"))}
    entorno["PYTHONPATH"] = str(BACKEND)
    if archivo:
        entorno["SGTM_ENV_FILE"] = archivo
    salida = subprocess.run(
        [sys.executable, "-c",
         "from services.ms2_taller.config import Settings; print(Settings().DATABASE_URL)"],
        cwd=tmp_path, env=entorno, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert salida.endswith(f"/{esperado}")


# ── eliminación de volúmenes ───────────────────────────────────────────────


def test_eliminar_exige_confirmacion_y_nombra_el_proyecto_de_pruebas(
    archivos: Path, monkeypatch: pytest.MonkeyPatch
):
    llamadas: list[list[str]] = []
    monkeypatch.setattr(amb, "detener_procesos", lambda: None)
    monkeypatch.setattr(
        amb.subprocess, "run",
        lambda comando, **_: llamadas.append(comando) or subprocess.CompletedProcess(comando, 0),
    )
    entorno = amb.entorno_pruebas()

    assert amb.eliminar(entorno, None) == 2
    assert amb.eliminar(entorno, "sgtm") == 2
    assert llamadas == []

    assert amb.eliminar(entorno, "sgtm_pruebas") == 0
    (comando,) = llamadas
    assert comando[:9] == ["docker", "compose", "-p", "sgtm_pruebas", "-f",
                           str(amb.COMPOSE), "--env-file", str(amb.ARCHIVO), "down"]
    assert amb.COMPOSE.name == "docker-compose.pruebas.yml"
    assert "--volumes" in comando


def test_pruebas_ms4_solo_entrega_el_minio_de_pruebas_a_pytest(
    archivos: Path, monkeypatch: pytest.MonkeyPatch
):
    llamadas: list[tuple[list[str], dict[str, str]]] = []
    monkeypatch.setattr(amb, "exigir", lambda *_a, **_k: None)
    monkeypatch.setattr(
        amb.subprocess, "run",
        lambda comando, env, **_: llamadas.append((comando, env))
        or subprocess.CompletedProcess(comando, 0),
    )
    monkeypatch.setenv("MS4_S3_BUCKET", "evidencias")
    monkeypatch.setenv("MS4_TEST_S3_ENDPOINT", "http://localhost:9000")
    entorno = amb.entorno_pruebas()

    assert amb.pruebas_ms4(entorno, ["-x"]) == 0

    ((comando, env),) = llamadas
    assert comando[-1] == "-x" and set(amb.PRUEBAS_MS4_REALES) <= set(comando)
    assert env["MS4_TEST_S3_ENDPOINT"] == "http://127.0.0.1:9010"
    assert env["MS4_TEST_S3_ADMIN_ACCESS_KEY"] == entorno["PRUEBAS_MINIO_ROOT_USUARIO"]
    assert env["MS4_TEST_S3_MS4_ACCESS_KEY"] == entorno["MS4_S3_ACCESS_KEY"]
    assert not any(k.startswith(("MS4_S3_", "SGTM_", "PRUEBAS_")) for k in env)
