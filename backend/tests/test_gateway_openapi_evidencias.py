"""Los ejemplos de Evidencias del OpenAPI de la Gateway son respuestas reales.

Cada ejemplo publicado para `/api/evidencias*` se compara con lo que responde
de verdad MS4 (con base SQLite en memoria, almacenamiento y MS2 falsos) o la
propia Gateway (413), para que la documentación no pueda divergir del código.
"""
from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from gateway.config import settings as gateway_settings
from gateway.main import app as gateway_app
from services.ms4_evidencias.db import get_db
from services.ms4_evidencias.dependencies import obtener_s3, obtener_s3_publico
from services.ms4_evidencias.integracion_ms2 import (
    OrdenNoVisible,
    ServicioOrdenesNoDisponible,
    obtener_verificador_ordenes,
)
from services.ms4_evidencias.main import app as ms4_app
from services.ms4_evidencias.models import Base
from services.ms4_evidencias.schemas.evidencia import EvidenciaLeida, UrlDescarga
from shared.auth import NombreRol, crear_token_acceso

SECRETO = "clave-secreta-exclusiva-para-pruebas-de-ms4-123456"
_JSON = "application/json"


class _S3:
    def __init__(self, falla: bool = False) -> None:
        self.falla = falla

    def upload_fileobj(self, fileobj, bucket, clave, ExtraArgs=None, Config=None):
        if self.falla:
            from botocore.exceptions import EndpointConnectionError

            raise EndpointConnectionError(endpoint_url="http://almacenamiento")

    def delete_object(self, Bucket, Key):
        return None


class _MS2:
    def __init__(self, modo: str = "ok") -> None:
        self.modo = modo

    def verificar_acceso(self, orden_id: int, token: str) -> None:
        if self.modo == "ajena":
            raise OrdenNoVisible(orden_id)
        if self.modo == "caido":
            raise ServicioOrdenesNoDisponible("caído")


@pytest.fixture(scope="module")
def esquema() -> dict:
    gateway_app.openapi_schema = None
    try:
        return gateway_app.openapi()
    finally:
        gateway_app.openapi_schema = None


def _ejemplo(esquema: dict, ruta: str, metodo: str, codigo: str, nombre: str):
    media = esquema["paths"][ruta][metodo]["responses"][codigo]["content"][_JSON]
    ejemplo = media["examples"][nombre]
    if "$ref" in ejemplo:
        ejemplo = esquema["components"]["examples"][ejemplo["$ref"].rsplit("/", 1)[-1]]
    return ejemplo["value"]


@pytest.fixture
def ms4() -> Generator[dict, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sesion: Session = sessionmaker(bind=engine, expire_on_commit=False)()
    estado = {"s3": _S3(), "ms2": _MS2()}

    def db():
        yield sesion

    ms4_app.dependency_overrides[get_db] = db
    ms4_app.dependency_overrides[obtener_s3] = lambda: estado["s3"]
    ms4_app.dependency_overrides[obtener_s3_publico] = lambda: None
    ms4_app.dependency_overrides[obtener_verificador_ordenes] = lambda: estado["ms2"]
    with TestClient(ms4_app) as cliente:
        estado["cliente"] = cliente
        yield estado
    ms4_app.dependency_overrides.clear()
    sesion.close()
    engine.dispose()


def _cabeceras(*roles: NombreRol) -> dict[str, str]:
    token = crear_token_acceso(21, frozenset(roles), clave_secreta=SECRETO)
    return {"Authorization": f"Bearer {token}"}


def _subir(cliente: TestClient, cabeceras: dict, datos: bytes = b"foto", tipo: str = "image/jpeg"):
    return cliente.post(
        "/evidencias",
        headers=cabeceras,
        data={"orden_id": "31", "contexto": "diagnostico"},
        files={"archivo": ("foto.jpg", datos, tipo)},
    )


def test_ejemplos_de_error_de_la_subida_son_los_reales(esquema: dict, ms4: dict) -> None:
    cliente = ms4["cliente"]
    mecanico = _cabeceras(NombreRol.MECANICO)
    ruta, metodo = "/api/evidencias", "post"

    casos = [
        ("401", "token_ausente", lambda: _subir(cliente, {})),
        (
            "401",
            "token_invalido",
            lambda: _subir(cliente, {"Authorization": "Bearer invalido"}),
        ),
        ("403", "rol_insuficiente", lambda: _subir(cliente, _cabeceras(NombreRol.CLIENTE))),
        ("422", "tipo_no_permitido", lambda: _subir(cliente, mecanico, tipo="text/plain")),
        ("422", "archivo_vacio", lambda: _subir(cliente, mecanico, datos=b"")),
    ]
    for codigo, nombre, llamada in casos:
        respuesta = llamada()
        assert respuesta.status_code == int(codigo), (nombre, respuesta.text)
        assert respuesta.json() == _ejemplo(esquema, ruta, metodo, codigo, nombre), nombre

    ms4["ms2"].modo = "ajena"
    respuesta = _subir(cliente, mecanico)
    assert respuesta.status_code == 404
    assert respuesta.json() == _ejemplo(esquema, ruta, metodo, "404", "orden_no_encontrada")

    ms4["ms2"].modo = "caido"
    respuesta = _subir(cliente, mecanico)
    assert respuesta.status_code == 503
    assert respuesta.json() == _ejemplo(esquema, ruta, metodo, "503", "ordenes_no_disponible")

    ms4["ms2"].modo = "ok"
    ms4["s3"].falla = True
    respuesta = _subir(cliente, mecanico)
    assert respuesta.status_code == 503
    assert respuesta.json() == _ejemplo(
        esquema, ruta, metodo, "503", "almacenamiento_no_disponible"
    )


def test_ejemplos_404_de_consulta_son_los_reales(esquema: dict, ms4: dict) -> None:
    cliente = ms4["cliente"]
    cabeceras = _cabeceras(NombreRol.MECANICO)
    inexistente = uuid.uuid4()

    for ruta in ("/api/evidencias/{evidencia_id}", "/api/evidencias/{evidencia_id}/descarga"):
        url = ruta.removeprefix("/api").replace("{evidencia_id}", str(inexistente))
        respuesta = cliente.get(url, headers=cabeceras)
        assert respuesta.status_code == 404
        assert respuesta.json() == _ejemplo(esquema, ruta, "get", "404", "evidencia_no_encontrada")

    ms4["ms2"].modo = "ajena"
    respuesta = cliente.get("/evidencias", params={"orden_id": 31}, headers=cabeceras)
    assert respuesta.status_code == 404
    assert respuesta.json() == _ejemplo(
        esquema, "/api/evidencias", "get", "404", "orden_no_encontrada"
    )


def test_ejemplos_exitosos_cumplen_los_esquemas_de_ms4(esquema: dict) -> None:
    EvidenciaLeida.model_validate(
        _ejemplo(esquema, "/api/evidencias", "post", "201", "evidencia_guardada")
    )
    EvidenciaLeida.model_validate(
        _ejemplo(esquema, "/api/evidencias/{evidencia_id}", "get", "200", "evidencia")
    )
    for nombre in ("vista_mecanico", "vista_cliente", "sin_evidencias"):
        for evidencia in _ejemplo(esquema, "/api/evidencias", "get", "200", nombre):
            EvidenciaLeida.model_validate(evidencia)
    url = UrlDescarga.model_validate(
        _ejemplo(
            esquema, "/api/evidencias/{evidencia_id}/descarga", "get", "200", "url_prefirmada"
        )
    )
    assert url.expira_en == 300
    assert url.url.startswith("https://")


def test_ejemplo_413_es_el_de_la_gateway(
    esquema: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gateway_settings, "MAX_BODY_ARCHIVOS_BYTES", 16)
    with TestClient(gateway_app) as cliente:
        respuesta = cliente.post(
            "/api/evidencias", content=b"x" * 64, headers={"Content-Type": "image/jpeg"}
        )
    assert respuesta.status_code == 413
    ejemplo = _ejemplo(esquema, "/api/evidencias", "post", "413", "cuerpo_demasiado_grande")
    cuerpo = respuesta.json()
    assert cuerpo["detail"] == ejemplo["detail"]
    assert cuerpo["error"]["codigo"] == ejemplo["error"]["codigo"]
    assert cuerpo["error"]["estado"] == ejemplo["error"]["estado"] == 413
    assert cuerpo["error"]["ruta"] == ejemplo["error"]["ruta"] == "/api/evidencias"
