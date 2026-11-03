"""Versión estable del contrato OpenAPI de la Gateway (Semana 8).

Fija tres garantías para los equipos que integran contra la Gateway (frontend
web y app móvil de Integración IV):

1. `info.version` es semver y el archivo congelado
   `docs/openapi/sgtm-gateway-<version>.json` coincide byte a byte con el
   `/openapi.json` que se publica. Cambiar el contrato sin subir la versión y
   exportar (`python scripts/exportar_openapi.py`) rompe esta prueba.
2. El archivo congelado es un OpenAPI 3 válido.
3. Los ejemplos agregados en 1.0.0 son respuestas reales de los microservicios
   (no inventadas): login 403/422/429 de MS1 y el 422 de vehículo de MS2.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openapi_spec_validator import validate as validar_openapi
from sqlalchemy import delete
from sqlalchemy.orm import Session

from gateway.main import app as gateway_app
from services.ms1_auth.models.rol import UsuarioRol
from services.ms2_taller.config import settings as ms2_settings
from services.ms2_taller.main import app as app_ms2
from shared.auth import crear_token_acceso

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_JSON = "application/json"


def _cargar_exportador():
    especificacion = importlib.util.spec_from_file_location(
        "exportar_openapi", RAIZ_BACKEND / "scripts" / "exportar_openapi.py"
    )
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)  # type: ignore[union-attr]
    return modulo


@pytest.fixture(scope="module")
def exportador():
    return _cargar_exportador()


@pytest.fixture(scope="module")
def esquema(exportador) -> dict:
    return exportador.construir_documento()


def _ejemplo(esquema: dict, ruta: str, metodo: str, codigo: str) -> dict:
    media = esquema["paths"][ruta][metodo]["responses"][codigo]["content"][_JSON]
    (ejemplo,) = media["examples"].values()
    if "$ref" in ejemplo:
        ejemplo = esquema["components"]["examples"][ejemplo["$ref"].rsplit("/", 1)[1]]
    return ejemplo["value"]


# ── versión y archivo congelado ─────────────────────────────────────────────


def test_version_es_semver_y_estable(esquema: dict) -> None:
    version = esquema["info"]["version"]
    assert _SEMVER.match(version), version
    assert int(version.split(".")[0]) >= 1, "una versión 0.x no es estable"
    assert gateway_app.version == version


def test_descripcion_publica_la_politica_de_versionado(esquema: dict) -> None:
    descripcion = esquema["info"]["description"]
    assert "## Versión del contrato" in descripcion
    assert f"sgtm-gateway-{esquema['info']['version']}.json" in descripcion
    assert "docs/versionado-contrato-openapi.md" in descripcion
    assert (RAIZ_BACKEND / "docs" / "versionado-contrato-openapi.md").exists()


def test_archivo_congelado_coincide_con_el_publicado(exportador, esquema: dict) -> None:
    archivo = exportador.ruta_contrato(esquema["info"]["version"])
    assert archivo.exists(), (
        f"Falta {archivo.name}: ejecuta `python scripts/exportar_openapi.py`"
    )
    assert archivo.read_text(encoding="utf-8") == exportador.serializar(esquema), (
        "El contrato publicado cambió y el archivo congelado no. Sube la versión "
        "en gateway/openapi.py y vuelve a exportar."
    )


def test_archivo_congelado_es_openapi_valido(exportador, esquema: dict) -> None:
    archivo = exportador.ruta_contrato(esquema["info"]["version"])
    validar_openapi(json.loads(archivo.read_text(encoding="utf-8")))


def test_archivo_congelado_no_publica_direcciones_internas(exportador, esquema) -> None:
    contenido = exportador.ruta_contrato(esquema["info"]["version"]).read_text(
        encoding="utf-8"
    )
    for interna in ("localhost:800", "127.0.0.1", "ms1_auth:", "ms2_taller:"):
        assert interna not in contenido, interna


# ── ejemplos nuevos de 1.0.0 contra respuestas reales ──────────────────────

_REGISTRO = {
    "email": "estable@correo.cl",
    "password": "ClaveSegura123!",
    "full_name": "Contrato Estable",
}


def test_login_429_real_coincide_con_el_publicado(api: TestClient, esquema: dict) -> None:
    assert api.post("/auth/register", json=_REGISTRO).status_code == 201
    incorrecta = {"email": _REGISTRO["email"], "password": "incorrecta"}
    for _ in range(5):
        assert api.post("/auth/login", json=incorrecta).status_code == 401
    bloqueado = api.post("/auth/login", json=incorrecta)

    assert bloqueado.status_code == 429
    assert bloqueado.json() == _ejemplo(esquema, "/api/auth/login", "post", "429")
    respuesta = esquema["paths"]["/api/auth/login"]["post"]["responses"]["429"]
    assert "Retry-After" in respuesta["headers"]
    assert int(bloqueado.headers["retry-after"]) > 0


def test_login_403_real_coincide_con_el_publicado(
    api: TestClient, db: Session, esquema: dict
) -> None:
    usuario_id = api.post("/auth/register", json=_REGISTRO).json()["id"]
    db.execute(delete(UsuarioRol).where(UsuarioRol.usuario_id == usuario_id))
    db.commit()

    login = api.post(
        "/auth/login",
        json={"email": _REGISTRO["email"], "password": _REGISTRO["password"]},
    )

    assert login.status_code == 403
    assert login.json() == _ejemplo(esquema, "/api/auth/login", "post", "403")


def test_login_422_real_coincide_con_el_publicado(api: TestClient, esquema: dict) -> None:
    respuesta = api.post("/auth/login", json={})

    assert respuesta.status_code == 422
    assert respuesta.json() == _ejemplo(esquema, "/api/auth/login", "post", "422")


def test_vehiculo_422_real_coincide_con_el_publicado(esquema: dict) -> None:
    token = crear_token_acceso(
        50,
        ["mecanico"],
        clave_secreta=ms2_settings.JWT_SECRET_KEY.get_secret_value(),
        algoritmo=ms2_settings.JWT_ALGORITHM,
    )
    respuesta = TestClient(app_ms2).get(
        "/vehiculos/abc", headers={"Authorization": f"Bearer {token}"}
    )

    assert respuesta.status_code == 422
    assert respuesta.json() == _ejemplo(
        esquema, "/api/vehiculos/{vehiculo_id}", "get", "422"
    )
