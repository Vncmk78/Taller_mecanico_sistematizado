"""Subida de evidencias por la API Gateway (Semana 5, checklist 4.2/4.3/4.5).

Dos niveles:

- Límites de body de la Gateway (control 4.2): `Content-Length` mayor al límite
  → 413 sin llamar al microservicio; `Content-Length` no numérica → 400;
  petición chunked sin `Content-Length` → corte en el streaming; el body justo
  en el límite pasa; los límites son configurables. Además, unidades de
  `limite_para` y `timeout_para("evidencias")`.

- Punta a punta Gateway real → app real de MS4 (in-process vía ASGITransport,
  igual que `test_integracion_prefijos`, con SQLite en memoria, FakeS3 y
  VerificadorPermiteTodo): subida multipart (201, sin `clave_objeto`,
  `request_id` propagado, content_type correcto en el almacenamiento), listado
  200, descarga 200 con sus cabeceras de seguridad llegando al cliente, 403 del
  cliente con el body JSON de MS4 tal cual, y 503 de MS4 cuando MinIO falla.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select

import gateway.cliente_http as cliente_http
import gateway.routers.proxy as routers_proxy
from gateway.cliente_http import timeout_para
from gateway.config import settings
from gateway.errores import (
    CUERPO_DEMASIADO_GRANDE,
    ERROR_HTTP,
    MENSAJE_CUERPO_DEMASIADO_GRANDE,
)
from gateway.main import app as gateway_app
from services.ms4_evidencias.db import get_db as get_db_ms4
from services.ms4_evidencias.dependencies import obtener_s3, obtener_s3_publico
from services.ms4_evidencias.integracion_ms2 import obtener_verificador_ordenes
from services.ms4_evidencias.main import app as app_ms4
from services.ms4_evidencias.models import Base as BaseMS4
from services.ms4_evidencias.models.evidencia import (
    ContextoEvidencia,
    EstadoEvidencia,
    Evidencia,
)
from services.ms4_evidencias.services.almacenamiento import crear_cliente_s3_publico
from shared.auth import NombreRol

from test_integracion_prefijos import (
    _FUNCIONES_SQLITE,
    _clave_montaje,
    _crear_sqlite,
    _fabrica_override,
)
from test_ms4_api_evidencias import (
    ORDEN,
    _crear_settings_publico,
    _escenario_visibilidad,
    _nueva,
    _sembrar,
    _token,
    FakeS3ConError,
    VerificadorPermiteTodo,
)
from test_ms4_recepcion import FakeS3


@pytest.fixture
def gateway() -> TestClient:
    return TestClient(gateway_app)


@pytest.fixture
def api_mock() -> respx.MockRouter:
    """Mock de `httpx`: cualquier petición sin ruta definida falla sola."""
    with respx.mock(assert_all_mocked=True) as mock:
        yield mock


@pytest.fixture(autouse=True)
def cliente_http_sin_estado() -> None:
    """Descarta el cliente compartido entre tests (mismo patrón que el proxy)."""
    yield
    cliente_http.reset_cliente()


def _cuerpo_de_error(respuesta) -> dict:
    """Valida la forma mínima del formato común y devuelve el cuerpo."""
    cuerpo = respuesta.json()
    assert isinstance(cuerpo["detail"], str)
    assert isinstance(cuerpo["error"], dict)
    for clave in ("codigo", "ruta", "request_id"):
        assert isinstance(cuerpo["error"][clave], str)
    assert isinstance(cuerpo["error"]["estado"], int)
    return cuerpo


# --------------------------------------------------------------------------- #
# Límites de body (checklist 4.2): 413/400 antes de tocar al microservicio    #
# --------------------------------------------------------------------------- #


def test_evidencias_con_content_length_mayor_al_limite_responde_413_sin_llamar(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    content = b"x" * (settings.MAX_BODY_ARCHIVOS_BYTES + 1)
    respuesta = gateway.post(
        "/api/evidencias",
        content=content,
        headers={"Content-Type": "application/octet-stream"},
    )

    assert respuesta.status_code == 413
    cuerpo = _cuerpo_de_error(respuesta)
    assert cuerpo["detail"] == MENSAJE_CUERPO_DEMASIADO_GRANDE
    assert cuerpo["error"]["codigo"] == CUERPO_DEMASIADO_GRANDE
    assert cuerpo["error"]["estado"] == 413
    assert cuerpo["error"]["ruta"] == "/api/evidencias"
    assert api_mock.calls == []
    # No revela el límite exacto del prefijo.
    assert "12582912" not in str(cuerpo)
    assert "1048576" not in str(cuerpo)


def test_json_por_encima_de_1_mib_responde_413_sin_llamar(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    content = b"x" * (settings.MAX_BODY_BYTES + 1)
    respuesta = gateway.post(
        "/api/vehiculos",
        content=content,
        headers={"Content-Type": "application/json"},
    )

    assert respuesta.status_code == 413
    cuerpo = _cuerpo_de_error(respuesta)
    assert cuerpo["error"]["codigo"] == CUERPO_DEMASIADO_GRANDE
    assert api_mock.calls == []


def test_body_json_pequeno_pasa_por_la_gateway(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    api_mock.post(f"{settings.MS2_URL}/vehiculos").mock(
        return_value=httpx.Response(201, json={"id": 1})
    )
    respuesta = gateway.post(
        "/api/vehiculos",
        content=b'{"patente": "ABCD12"}',
        headers={"Content-Type": "application/json"},
    )

    assert respuesta.status_code == 201
    assert api_mock.calls


def test_body_exacto_al_limite_pasa_y_limite_mas_uno_responde_413(
    gateway: TestClient, api_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MAX_BODY_BYTES", 8)
    api_mock.post(f"{settings.MS2_URL}/vehiculos").mock(
        return_value=httpx.Response(200, json={})
    )

    en_el_limite = gateway.post(
        "/api/vehiculos",
        content=b"ABCDEFGH",
        headers={"Content-Type": "application/json"},
    )
    assert en_el_limite.status_code == 200

    un_paso_mas = gateway.post(
        "/api/vehiculos",
        content=b"ABCDEFGHI",
        headers={"Content-Type": "application/json"},
    )
    assert un_paso_mas.status_code == 413
    assert un_paso_mas.json()["error"]["codigo"] == CUERPO_DEMASIADO_GRANDE


def test_peticion_chunked_sin_content_length_que_excede_el_limite_responde_413(
    gateway: TestClient, api_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MAX_BODY_ARCHIVOS_BYTES", 1024)

    def trozos():
        for _ in range(6):
            yield b"x" * 256  # 1536 bytes en total, sin Content-Length

    respuesta = gateway.post(
        "/api/evidencias",
        content=trozos(),
        headers={"Content-Type": "application/octet-stream"},
    )

    assert respuesta.status_code == 413
    assert respuesta.json()["error"]["codigo"] == CUERPO_DEMASIADO_GRANDE
    assert api_mock.calls == []


def test_content_length_invalida_responde_400(
    gateway: TestClient, api_mock: respx.MockRouter
) -> None:
    def trozos():
        yield b"x"

    respuesta = gateway.post(
        "/api/vehiculos",
        content=trozos(),
        headers={"Content-Type": "application/json", "Content-Length": "abc"},
    )

    assert respuesta.status_code == 400
    cuerpo = _cuerpo_de_error(respuesta)
    assert cuerpo["error"]["codigo"] == ERROR_HTTP
    assert api_mock.calls == []


def test_limite_de_evidencias_configurable_modifica_el_corte(
    gateway: TestClient, api_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MAX_BODY_ARCHIVOS_BYTES", 16)
    api_mock.post(f"{settings.MS4_URL}/evidencias").mock(
        return_value=httpx.Response(201, json={})
    )

    ok = gateway.post(
        "/api/evidencias",
        content=b"y" * 16,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert ok.status_code == 201

    grande = gateway.post(
        "/api/evidencias",
        content=b"y" * 17,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert grande.status_code == 413
    assert grande.json()["error"]["codigo"] == CUERPO_DEMASIADO_GRANDE


def test_limite_para_evidencias_y_resto_de_prefijos() -> None:
    assert routers_proxy.limite_para("evidencias") == settings.MAX_BODY_ARCHIVOS_BYTES
    assert routers_proxy.limite_para("vehiculos") == settings.MAX_BODY_BYTES
    assert routers_proxy.limite_para("auth") == settings.MAX_BODY_BYTES


def test_timeout_para_evidencias_usa_timeout_de_archivos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "TIMEOUT_ARCHIVOS_SECONDS", 90.0)
    timeout = timeout_para("evidencias")

    assert timeout.read == 90.0
    assert timeout.write == 90.0
    assert timeout.connect == settings.TIMEOUT_CONNECT_SECONDS


# --------------------------------------------------------------------------- #
# Punta a punta: Gateway real -> app real de MS4 (in-process)                 #
# --------------------------------------------------------------------------- #


@pytest.fixture
def ecosistema_evidencias(monkeypatch: pytest.MonkeyPatch):
    """Gateway real conectada a la app real de MS4 sobre SQLite en memoria.

    MS4 usa un motor SQLite con `StaticPool` (btrim/char_length registradas),
    FakeS3 como almacenamiento, cliente S3 público que firma offline y un
    `VerificadorPermiteTodo` (la autorización contra MS2 la cubre
    `test_ms4_autorizacion_evidencias.py`). El cliente HTTPX de la Gateway se
    monta con `ASGITransport` sobre la URL base de MS4, como el `ecosistema`
    de `test_integracion_prefijos` pero solo para el prefijo `evidencias`.
    """
    import services.ms4_evidencias.models  # noqa: F401  (registra tablas)

    motor_ms4, sesion_ms4 = _crear_sqlite(
        BaseMS4, funciones_sqlite=_FUNCIONES_SQLITE
    )
    s3 = FakeS3()
    app_ms4.dependency_overrides[get_db_ms4] = _fabrica_override(sesion_ms4)
    app_ms4.dependency_overrides[obtener_s3] = lambda: s3
    app_ms4.dependency_overrides[obtener_s3_publico] = lambda: (
        crear_cliente_s3_publico(_crear_settings_publico())
    )
    app_ms4.dependency_overrides[obtener_verificador_ordenes] = lambda: (
        VerificadorPermiteTodo()
    )

    cliente = None

    def _obtener_cliente() -> httpx.AsyncClient:
        nonlocal cliente
        if cliente is None:
            cliente = httpx.AsyncClient(
                mounts={
                    _clave_montaje(settings.MS4_URL): httpx.ASGITransport(
                        app=app_ms4
                    ),
                }
            )
        return cliente

    # El router del proxy usa el nombre importado; parchear solo
    # gateway.cliente_http no tendría efecto.
    monkeypatch.setattr(routers_proxy, "obtener_cliente", _obtener_cliente)

    try:
        with TestClient(gateway_app) as gw:
            yield gw, s3, sesion_ms4
    finally:
        app_ms4.dependency_overrides.clear()
        sesion_ms4.close()
        BaseMS4.metadata.drop_all(motor_ms4)
        motor_ms4.dispose()


def _subir_por_gateway(
    gw: TestClient,
    token: str,
    *,
    request_id: str | None = None,
) -> httpx.Response:
    cabeceras = {"Authorization": f"Bearer {token}"}
    if request_id is not None:
        cabeceras["X-Request-ID"] = request_id
    return gw.post(
        "/api/evidencias",
        headers=cabeceras,
        data={"orden_id": str(ORDEN), "contexto": "diagnostico"},
        files={"archivo": ("foto.jpg", b"datos-de-foto", "image/jpeg")},
    )


def test_subida_multipart_por_gateway_201_sin_clave_y_request_id_propagado(
    ecosistema_evidencias,
) -> None:
    gw, s3, sesion = ecosistema_evidencias

    respuesta = _subir_por_gateway(
        gw, _token(7, NombreRol.MECANICO), request_id="evidencias-gw-1"
    )

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert "evidencia_id" in cuerpo
    assert cuerpo["estado"] == EstadoEvidencia.CONFIRMADA.value
    # Los campos internos jamás salen en el JSON, ni siquiera por la Gateway.
    assert "clave_objeto" not in cuerpo
    assert "ordenes/" not in str(cuerpo)
    # La Gateway devuelve el mismo X-Request-ID que se propagó a MS4.
    assert respuesta.headers["x-request-id"] == "evidencias-gw-1"

    fila = sesion.scalar(select(Evidencia))
    assert fila is not None
    assert fila.request_id == "evidencias-gw-1"
    assert len(s3.objetos) == 1
    guardado = next(iter(s3.objetos.values()))
    assert guardado["content_type"] == "image/jpeg"


def test_listar_por_gateway_devuelve_200_con_la_evidencia_visible(
    ecosistema_evidencias,
) -> None:
    gw, _s3, sesion = ecosistema_evidencias
    escenario = _escenario_visibilidad()
    _sembrar(sesion, *escenario)

    respuesta = gw.get(
        "/api/evidencias",
        params={"orden_id": ORDEN},
        headers={"Authorization": f"Bearer {_token(9, NombreRol.CLIENTE)}"},
    )

    assert respuesta.status_code == 200, respuesta.text
    ids_cliente = {e["evidencia_id"] for e in respuesta.json()}
    esperado = {
        str(e.evidencia_id)
        for e in escenario
        if e.visible_cliente
        and e.estado == EstadoEvidencia.CONFIRMADA
        and e.eliminada_en is None
    }
    assert ids_cliente == esperado


def test_descarga_por_gateway_lleva_url_firmada_y_cabeceras_seguras(
    ecosistema_evidencias,
) -> None:
    gw, _s3, sesion = ecosistema_evidencias
    visible = _nueva(
        contexto=ContextoEvidencia.RESULTADO_FINAL,
        estado=EstadoEvidencia.CONFIRMADA,
        confirmada_en=datetime.now(timezone.utc),
        sha256="d" * 64,
        visible_cliente=True,
        nombre_original="foto del taller.jpg",
        content_type="image/jpeg",
    )
    _sembrar(sesion, visible)

    respuesta = gw.get(
        f"/api/evidencias/{visible.evidencia_id}/descarga",
        headers={"Authorization": f"Bearer {_token(9, NombreRol.CLIENTE)}"},
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["cache-control"] == "no-store"
    assert respuesta.headers["x-content-type-options"] == "nosniff"
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"url", "expira_en"}
    assert cuerpo["expira_en"] == 300
    assert urlsplit(cuerpo["url"]).netloc == "minio.publico.test:9000"
    parametros = parse_qs(urlsplit(cuerpo["url"]).query)
    assert parametros["X-Amz-Expires"] == ["300"]
    assert "clave_objeto" not in str(cuerpo)


def test_cliente_no_puede_subir_por_gateway_y_llega_el_403_del_ms4(
    ecosistema_evidencias,
) -> None:
    gw, s3, sesion = ecosistema_evidencias

    respuesta = _subir_por_gateway(gw, _token(9, NombreRol.CLIENTE))

    assert respuesta.status_code == 403
    # El error JSON de MS4 viaja tal cual por la Gateway (decisión 3).
    assert respuesta.json() == {"detail": "No tienes permiso para realizar esta operación"}
    assert not s3.objetos
    assert sesion.scalar(select(Evidencia)) is None


def test_ms4_503_cuando_el_almacenamiento_falla_llega_a_traves_de_la_gateway(
    ecosistema_evidencias,
) -> None:
    gw, _s3, _sesion = ecosistema_evidencias
    # MS4 traduce a 503 solo los fallos que reconoce de boto3 (ClientError),
    # como en test_ms4_api_evidencias; un RuntimeError crudo sería un 500.
    s3 = FakeS3ConError()
    s3.fallar_subida = True
    app_ms4.dependency_overrides[obtener_s3] = lambda: s3

    respuesta = _subir_por_gateway(gw, _token(7, NombreRol.MECANICO))

    assert respuesta.status_code == 503
    assert respuesta.json() == {
        "detail": "El almacenamiento de evidencias no está disponible"
    }
    assert not s3.objetos