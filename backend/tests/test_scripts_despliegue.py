"""Casos de seguridad del migrador y consultas de integración sin bases externas."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from scripts import iniciar_servicio, migrar, prueba_integracion_app as app
from scripts import verificar_migraciones as vm


@pytest.fixture
def ramas(tmp_path: Path) -> ScriptDirectory:
    versiones = tmp_path / "versions"
    versiones.mkdir()
    for revision, anterior in (("base1", None), ("rama_a", "base1"), ("rama_b", "base1"), ("union", ("rama_a", "rama_b"))):
        (versiones / f"{revision}.py").write_text(f"revision = {revision!r}\ndown_revision = {anterior!r}\n", encoding="utf-8")
    return ScriptDirectory(str(tmp_path))


@pytest.mark.parametrize("actuales,estado", [
    ([], "ATRASADA"), (["rama_a"], "ATRASADA"),
    (["rama_a", "rama_b"], "ATRASADA"), (["union"], "OK"),
    (["otra_rama"], "INCOMPATIBLE"),
])
def test_comparacion_incluye_ramas_paralelas(ramas, actuales, estado):
    assert vm.comparar("MS2", frozenset(actuales), ramas).estado == estado


def test_multiples_heads_sin_merge_requieren_ambos(ramas):
    Path(ramas.dir, "versions", "union.py").unlink()
    scripts = ScriptDirectory(ramas.dir)
    assert vm.comparar("MS2", frozenset({"rama_a"}), scripts).estado == "ATRASADA"
    assert vm.comparar("MS2", frozenset({"rama_a", "rama_b"}), scripts).estado == "OK"


def test_base_vacia_no_crea_tabla_version():
    engine = create_engine("sqlite://")
    with engine.connect() as conexion:
        assert vm.leer_revisiones(conexion) == frozenset()
        assert inspect(conexion).get_table_names() == []
    engine.dispose()


def test_verificador_exige_dsn_explicito_y_no_expone_errores(monkeypatch):
    assert vm.verificar("MS1", {}).estado == "ERROR"

    def fallar(*args, **kwargs):
        raise RuntimeError("no imprimir password-secreta")

    monkeypatch.setattr(vm, "create_engine", fallar)
    resultado = vm.verificar("MS1", {"MS1_DATABASE_URL": "postgresql+psycopg://u:password-secreta@db/bd"})
    assert resultado.codigo == 2
    assert "password-secreta" not in resultado.detalle


def test_migrador_no_escribe_si_una_base_es_incompatible(monkeypatch):
    monkeypatch.setattr(migrar, "verificar_todas", lambda: [vm.Resultado("MS2", "INCOMPATIBLE", frozenset({"ajena"}), frozenset({"head"}))])
    llamadas = []
    monkeypatch.setattr(migrar.command, "upgrade", lambda *a: llamadas.append(a))
    assert migrar.main() == 2
    assert llamadas == []


def test_impide_migrar_dos_servicios_sobre_la_misma_base(monkeypatch):
    for servicio in vm.SERVICIOS:
        monkeypatch.setenv(f"{servicio}_DATABASE_URL", f"postgresql+psycopg://u:p@host/{servicio}")
    monkeypatch.setenv("MS2_DATABASE_URL", "postgresql+psycopg://otro:secreto@host/MS1")
    monkeypatch.setattr(vm, "verificar", lambda s, e: vm.Resultado(s, "ATRASADA", frozenset(), frozenset({"h"})))
    resultados = vm.verificar_todas()
    assert [r.estado for r in resultados] == ["ERROR", "ERROR", "ATRASADA", "ATRASADA"]


def test_migrador_incluye_ms4_y_verificacion_final(monkeypatch):
    atrasadas = [vm.Resultado(s, "ATRASADA", frozenset(), frozenset({"head"})) for s in vm.SERVICIOS]
    verificaciones = iter([atrasadas, atrasadas])
    monkeypatch.setattr(migrar, "verificar_todas", lambda: next(verificaciones))
    migradas = []
    monkeypatch.setattr(migrar.command, "upgrade", lambda config, destino: migradas.append((config.config_file_name, destino)))
    monkeypatch.setattr(migrar.command, "current", lambda *a, **kw: None)
    assert migrar.main() == 1  # No declara éxito si la comprobación final sigue atrasada.
    assert len(migradas) == 4
    assert all(destino == "heads" for _, destino in migradas)
    assert migradas[-1][0].endswith("ms4_evidencias/alembic.ini")


def test_migrador_aborta_al_fallar_un_servicio(monkeypatch):
    monkeypatch.setattr(migrar, "verificar_todas", lambda: [vm.Resultado("MS1", "OK", frozenset({"h"}), frozenset({"h"}))])
    llamadas = []

    def fallar(config, destino):
        llamadas.append(destino)
        raise RuntimeError("falló")

    monkeypatch.setattr(migrar.command, "upgrade", fallar)
    assert migrar.main() == 2
    assert llamadas == ["heads"]


@pytest.mark.parametrize("url", ["http://api.example", "https://u:p@api.example", "https://api.example/api", "https://api.example?token=abc"])
def test_no_envia_credenciales_por_http_o_url_ambigua(url):
    with pytest.raises(ValueError):
        app.validar_url(url)


def test_muestras_excluyen_token_y_datos_personales():
    datos = app.anonimizar({"access_token": "secreto", "email": "privado", "items": [{"patente": "ABCD12", "observacion": "privado", "orden_id": 1}, {"orden_id": 2}]})
    texto = json.dumps(datos)
    assert "secreto" not in texto and "privado" not in texto and "ABCD12" not in texto
    assert datos["items"] == [{"patente": "[omitido]", "observacion": "[omitido]", "orden_id": 1}]


def respuestas(request: httpx.Request, *, vacio=False, error_ordenes=False) -> httpx.Response:
    rol = request.headers.get("authorization", "").removeprefix("Bearer ")
    ruta = request.url.path
    if request.method == "POST":
        assert ruta == "/api/auth/login"
        return httpx.Response(200, json={"access_token": json.loads(request.content)["email"]})
    assert request.method == "GET"  # La prueba nunca intenta una escritura de negocio.
    if ruta == "/api/health":
        return httpx.Response(200, json={"status": "ok"})
    if ruta == "/openapi.json":
        return httpx.Response(200, json={"openapi": "3.1.0", "paths": {"/api/ordenes": {}}})
    if not rol:
        return httpx.Response(401, json={"detail": "No autenticado"}, headers={"WWW-Authenticate": "Bearer"})
    if ruta == "/api/auth/me":
        return httpx.Response(200, json={"roles": [rol], "is_active": True, "email": "privado"})
    if ruta in {"/api/vehiculos", "/api/vehiculos/asignados"}:
        permitido = (rol == "mecanico") == ruta.endswith("/asignados")
        return httpx.Response(200 if permitido else 403, json=[] if permitido else {"detail": "Sin permiso"})
    orden = {campo: 1 for campo in app.CAMPOS_ORDEN}
    if ruta == "/api/ordenes":
        return httpx.Response(500 if error_ordenes else 200, json=[] if vacio else [orden])
    if ruta == "/api/ordenes/1":
        return httpx.Response(200, json=orden)
    if ruta == "/api/vehiculos/1":
        return httpx.Response(200, json={campo: 1 for campo in app.CAMPOS_VEHICULO})
    if ruta in {"/api/ordenes/1/historial", "/api/evidencias"}:
        return httpx.Response(200, json=[])
    raise AssertionError(f"Ruta inesperada {ruta}")


@pytest.mark.parametrize("error_ordenes", [False, True])
def test_prueba_roles_detecta_500_y_solo_consulta(error_ordenes):
    with httpx.Client(base_url="https://api.example", transport=httpx.MockTransport(lambda r: respuestas(r, error_ordenes=error_ordenes))) as cliente:
        prueba = app.PruebaIntegracion(cliente)
        for rol in app.ROLES:
            prueba.probar_rol(rol, rol, "clave-local")
        assert (prueba.fallos > 0) == error_ordenes
        assert all("/auth/me" != m["ruta"] for m in prueba.muestras)


def test_lista_vacia_no_pasa_como_detalle_verificado():
    with httpx.Client(base_url="https://api.example", transport=httpx.MockTransport(lambda r: respuestas(r, vacio=True))) as cliente:
        prueba = app.PruebaIntegracion(cliente)
        prueba.probar_rol("cliente", "cliente", "clave-local")
        assert prueba.fallos == 0
        assert prueba.omitidas == 1


@pytest.mark.parametrize("servicio,modulo", iniciar_servicio.MODULOS.items())
def test_arranque_separa_servicios(servicio, modulo):
    args = iniciar_servicio.comando({"SGTM_SERVICIO": servicio, "PORT": "8080"})
    assert args == [sys.executable, "-m", "uvicorn", modulo, "--host", "0.0.0.0", "--port", "8080"]


@pytest.mark.parametrize("entorno", [{"SGTM_SERVICIO": "cualquier.codigo"}, {"PORT": "0"}, {"PORT": "65536"}, {"PORT": "abc"}])
def test_arranque_rechaza_configuracion_invalida(entorno):
    with pytest.raises(ValueError):
        iniciar_servicio.comando(entorno)
