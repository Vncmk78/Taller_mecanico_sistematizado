"""Semana 9: la Gateway y cada microservicio validan el JWT por separado.

Decisión de arquitectura (`docs/contratos-api-gateway.md`, «Quién valida el
token»): la Gateway **no** valida el JWT ni tiene el secreto de firma; reenvía
`Authorization` intacta, y **cada** microservicio lo valida por su cuenta con
`shared.auth.validar_token_acceso`. Así un microservicio no confía en que la
petición «ya pasó por la Gateway»: llamado directo, igual rechaza.

Estas pruebas lo verifican de punta a punta:

1. **Barrido de rutas.** Toda operación publicada por MS1–MS4 que no esté en
   la lista explícita de públicas o internas responde `401` ante siete tokens
   inválidos, llamando al microservicio **directo**, sin Gateway. Una ruta
   nueva sin protección hace fallar la prueba con su nombre.
2. **Rutas internas.** Las de servicio a servicio exigen `X-Service-Token`: un
   JWT de Administrador válido no las abre, y la Gateway no las publica.
3. **Gateway.** No tiene secreto JWT, reenvía `Authorization` byte a byte a los
   cuatro servicios y devuelve el `401` del microservicio sin decidir nada.

Resultado documentado en `docs/verificacion-jwt-independiente.md`.
"""
from __future__ import annotations

import base64
import json
import re
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from pydantic import SecretStr

import gateway.cliente_http as cliente_http
from gateway.config import GatewaySettings, settings as gateway_settings
from gateway.main import app as gateway_app
from services.ms1_auth.config import settings as ms1_settings
from services.ms1_auth.main import app as ms1_app
from services.ms2_taller.config import settings as ms2_settings
from services.ms2_taller.main import app as ms2_app
from services.ms3_presupuestos.config import settings as ms3_settings
from services.ms3_presupuestos.main import app as ms3_app
from services.ms4_evidencias.config import settings as ms4_settings
from services.ms4_evidencias.main import app as ms4_app
from shared.auth import NombreRol, crear_token_acceso
from test_notificaciones_api import _evento

SERVICIOS: dict[str, tuple[FastAPI, object]] = {
    "ms1": (ms1_app, ms1_settings),
    "ms2": (ms2_app, ms2_settings),
    "ms3": (ms3_app, ms3_settings),
    "ms4": (ms4_app, ms4_settings),
}

# Rutas que no llevan JWT a propósito. Cualquier otra debe exigirlo.
PUBLICAS: set[str] = {
    "ms1 GET /health",
    "ms1 GET /health/db",
    "ms1 POST /auth/register",
    "ms1 POST /auth/login",
    "ms2 GET /health",
    "ms2 GET /health/db",
    "ms3 GET /health",
    "ms3 GET /health/db",
    "ms4 GET /health",
    "ms4 GET /health/db",
    "ms4 GET /health/storage",
}
# Servicio a servicio: se autentican con X-Service-Token, no con JWT.
INTERNAS: set[str] = {
    "ms1 POST /interno/eventos/ordenes/estado",
    "ms1 POST /interno/eventos/nuevas-atenciones/revision",
    "ms1 POST /interno/eventos/nuevas-atenciones/solicitud",
    "ms1 POST /interno/eventos/ms3/aviso",
    "ms2 GET /interno/notificaciones/ordenes/{orden_id}/destinatario",
}

_METODOS = ("get", "post", "put", "patch", "delete")
CLAVE_AJENA = "clave-de-otro-emisor-que-no-firma-este-sistema-123456"


def _b64(datos: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(datos).encode()).rstrip(b"=").decode()


def _clave(config: object) -> str:
    return config.JWT_SECRET_KEY.get_secret_value()


def _futuro() -> int:
    return int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())


def _tokens_invalidos(config: object) -> dict[str, str | None]:
    """Siete formas de no estar autenticado, firmadas o no con la clave real."""
    clave = _clave(config)
    pasado = int((datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp())
    return {
        "sin_token": None,
        "malformado": "no.es.un-jwt",
        "firma_ajena": crear_token_acceso(
            1, [NombreRol.ADMINISTRADOR], clave_secreta=CLAVE_AJENA
        ),
        "expirado": jwt.encode(
            {"sub": "1", "roles": ["administrador"], "exp": pasado}, clave, algorithm="HS256"
        ),
        "alg_none": _b64({"alg": "none", "typ": "JWT"})
        + "."
        + _b64({"sub": "1", "roles": ["administrador"], "exp": _futuro()})
        + ".",
        "rol_inventado": jwt.encode(
            {"sub": "1", "roles": ["superusuario"], "exp": _futuro()}, clave, algorithm="HS256"
        ),
        "sub_no_numerico": jwt.encode(
            {"sub": "admin", "roles": ["administrador"], "exp": _futuro()},
            clave,
            algorithm="HS256",
        ),
    }


def _operaciones() -> Iterator[tuple[str, str, str]]:
    for nombre, (app, _) in SERVICIOS.items():
        for ruta, operaciones in app.openapi()["paths"].items():
            for metodo in operaciones:
                if metodo in _METODOS:
                    yield nombre, metodo.upper(), ruta


OPERACIONES = sorted(_operaciones())
PROTEGIDAS = [op for op in OPERACIONES if " ".join(op) not in PUBLICAS | INTERNAS]


def _url(ruta: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", ruta)


@pytest.fixture(scope="module")
def clientes() -> dict[str, TestClient]:
    # Sin `with`: no se arranca el lifespan (workers de eventos).
    return {
        nombre: TestClient(app, raise_server_exceptions=False)
        for nombre, (app, _) in SERVICIOS.items()
    }


# ── 1. Cada microservicio valida por su cuenta, llamado directo ─────────────


def test_las_listas_de_excepciones_no_tienen_rutas_inexistentes() -> None:
    publicadas = {" ".join(op) for op in OPERACIONES}

    assert PUBLICAS <= publicadas
    assert INTERNAS <= publicadas


def test_cada_microservicio_tiene_rutas_protegidas() -> None:
    por_servicio = {nombre for nombre, _, _ in PROTEGIDAS}

    assert por_servicio == set(SERVICIOS)


@pytest.mark.parametrize(
    ("servicio", "metodo", "ruta"),
    PROTEGIDAS,
    ids=[" ".join(op) for op in PROTEGIDAS],
)
def test_ruta_protegida_rechaza_todo_token_invalido_sin_pasar_por_la_gateway(
    clientes: dict[str, TestClient], servicio: str, metodo: str, ruta: str
) -> None:
    cliente = clientes[servicio]
    config = SERVICIOS[servicio][1]

    aceptados = {}
    for caso, token in _tokens_invalidos(config).items():
        cabeceras = {"Authorization": f"Bearer {token}"} if token else {}
        respuesta = cliente.request(metodo, _url(ruta), headers=cabeceras, json={})
        if respuesta.status_code != 401:
            aceptados[caso] = respuesta.status_code

    assert aceptados == {}, f"{servicio} {metodo} {ruta} no respondió 401 en: {aceptados}"


@pytest.mark.parametrize("servicio", sorted(SERVICIOS))
def test_el_401_del_microservicio_pide_bearer(
    clientes: dict[str, TestClient], servicio: str
) -> None:
    _, metodo, ruta = next(op for op in PROTEGIDAS if op[0] == servicio)

    respuesta = clientes[servicio].request(metodo, _url(ruta), json={})

    assert respuesta.status_code == 401
    assert respuesta.headers.get("www-authenticate", "").startswith("Bearer")


@pytest.mark.parametrize("servicio", sorted(SERVICIOS))
def test_token_valido_del_mismo_servicio_supera_la_autenticacion(
    clientes: dict[str, TestClient], servicio: str
) -> None:
    """Control: el 401 del barrido se debe al token, no a otra cosa de la ruta."""
    config = SERVICIOS[servicio][1]
    token = crear_token_acceso(
        1,
        [NombreRol.ADMINISTRADOR, NombreRol.CLIENTE, NombreRol.MECANICO],
        clave_secreta=_clave(config),
    )
    _, metodo, ruta = next(op for op in PROTEGIDAS if op[0] == servicio)

    respuesta = clientes[servicio].request(
        metodo, _url(ruta), headers={"Authorization": f"Bearer {token}"}, json={}
    )

    assert respuesta.status_code != 401


# ── 2. Rutas internas: credencial de servicio, nunca un JWT ─────────────────


def _jwt_administrador(config: object) -> dict[str, str]:
    token = crear_token_acceso(
        1, [NombreRol.ADMINISTRADOR], clave_secreta=_clave(config)
    )
    return {"Authorization": f"Bearer {token}"}


def test_evento_interno_de_ms1_no_se_abre_con_un_jwt_de_administrador(
    clientes: dict[str, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ms1_settings, "EVENT_SHARED_SECRET", SecretStr("secreto-de-servicio-pruebas-123456")
    )

    respuesta = clientes["ms1"].post(
        "/interno/eventos/ordenes/estado",
        json=_evento(),
        headers=_jwt_administrador(ms1_settings),
    )

    assert respuesta.status_code == 401


def test_destinatario_interno_de_ms2_no_se_abre_con_un_jwt_de_administrador(
    clientes: dict[str, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ms2_settings,
        "NOTIFICATION_LOOKUP_SECRET",
        SecretStr("secreto-de-consulta-pruebas-123456"),
    )

    respuesta = clientes["ms2"].get(
        "/interno/notificaciones/ordenes/1/destinatario",
        headers=_jwt_administrador(ms2_settings),
    )

    assert respuesta.status_code == 401


@pytest.mark.parametrize(
    "ruta",
    sorted({ruta for clave in INTERNAS for ruta in [clave.split(" ", 2)[2]]}),
)
def test_la_gateway_no_publica_rutas_internas(ruta: str) -> None:
    respuesta = TestClient(gateway_app).post(f"/api{_url(ruta)}", json={})

    assert respuesta.status_code == 404


# ── 3. La Gateway no valida ni altera el token ──────────────────────────────


@pytest.fixture(autouse=True)
def cliente_http_sin_estado() -> Iterator[None]:
    yield
    cliente_http.reset_cliente()


def test_la_gateway_no_tiene_secreto_jwt() -> None:
    campos = {nombre.upper() for nombre in GatewaySettings.model_fields}

    assert not {c for c in campos if "JWT" in c or "SECRET" in c}


@pytest.mark.parametrize(
    ("ruta_publica", "base", "ruta_interna"),
    [
        ("/api/auth/me", "MS1_URL", "/auth/me"),
        ("/api/ordenes", "MS2_URL", "/ordenes"),
        ("/api/presupuestos", "MS3_URL", "/presupuestos"),
        ("/api/evidencias", "MS4_URL", "/evidencias"),
    ],
)
def test_la_gateway_reenvia_el_token_intacto_y_devuelve_el_401_del_servicio(
    ruta_publica: str, base: str, ruta_interna: str
) -> None:
    forjado = "Bearer " + _b64({"alg": "none"}) + "." + _b64({"sub": "1"}) + "."
    rechazo = {"detail": "Token inválido o expirado"}

    with respx.mock(assert_all_mocked=True) as mock:
        destino = mock.get(f"{getattr(gateway_settings, base)}{ruta_interna}").mock(
            return_value=httpx.Response(
                401, json=rechazo, headers={"WWW-Authenticate": "Bearer"}
            )
        )
        respuesta = TestClient(gateway_app).get(
            ruta_publica, headers={"Authorization": forjado}
        )

    assert destino.called, "la Gateway decidió sin consultar al microservicio"
    assert destino.calls.last.request.headers["authorization"] == forjado
    assert respuesta.status_code == 401
    assert respuesta.json() == rechazo
