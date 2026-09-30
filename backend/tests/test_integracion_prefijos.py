"""Pruebas de integración Gateway ↔ 4 microservicios reales (in-process).

"Integración" aquí significa: la Gateway REAL (`gateway.main:app`) conectada a
los CUATRO apps REALES de los microservicios mediante `httpx.AsyncClient` con
transportes `ASGITransport` por URL base (sin red, sin Docker y sin respx);
cada microservicio usa su propia base SQLite en memoria con `StaticPool`. El
token lo EMITE MS1 y lo VALIDAN MS2 (y MS4) porque en el fixture las tres
claves `JWT_SECRET_KEY` quedan igualadas.

Qué NO cubre: PostgreSQL real, red entre procesos ni MinIO/S3; eso es la prueba
real con servicios levantados (`scripts/prueba_comunicacion.py`). Complementa a
`tests/test_gateway_rutas.py` (respx, microservicios simulados).

Para correrlo solo:
    python -m pytest tests/test_integracion_prefijos.py -v
"""
from __future__ import annotations

from urllib.parse import urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import gateway.routers.health as routers_health
import gateway.routers.proxy as routers_proxy
import services.ms1_auth.models  # noqa: F401  (registra las tablas en BaseMS1)
import services.ms2_taller.models  # noqa: F401  (registra las tablas en BaseMS2)
import services.ms3_presupuestos.models  # noqa: F401  (registra las tablas en BaseMS3)
import services.ms4_evidencias.models  # noqa: F401  (registra las tablas en BaseMS4)
from gateway.config import settings as gateway_settings
from gateway.main import app as gateway_app
from services.ms1_auth.config import settings as ms1_settings
from services.ms1_auth.db import Base as BaseMS1
from services.ms1_auth.db import get_db as get_db_ms1
from services.ms1_auth.main import app as app_ms1
from services.ms1_auth.models import Rol
from services.ms1_auth.models.rol import UsuarioRol
from services.ms1_auth.models.usuario import Usuario
from services.ms1_auth.security.passwords import hash_contrasena
from services.ms2_taller.config import settings as ms2_settings
from services.ms2_taller.db import Base as BaseMS2
from services.ms2_taller.db import get_db as get_db_ms2
from services.ms2_taller.main import app as app_ms2
from services.ms2_taller.models import Cliente
from services.ms2_taller.models.estado_orden import ESTADOS_ORDEN, EstadoOrden
from services.ms3_presupuestos.db import Base as BaseMS3
from services.ms3_presupuestos.db import get_db as get_db_ms3
from services.ms3_presupuestos.main import app as app_ms3
from services.ms4_evidencias.config import settings as ms4_settings
from services.ms4_evidencias.db import Base as BaseMS4
from services.ms4_evidencias.db import get_db as get_db_ms4
from services.ms4_evidencias.main import app as app_ms4
from shared.auth import NombreRol

# Funciones nativas de PostgreSQL que SQLite no tiene y que aparecen en CHECKs
# de varios modelos (MS2 y MS3); se registran en cada engine SQLite de prueba.
_FUNCIONES_SQLITE: list[tuple[str, int, object]] = [
    ("btrim", 1, lambda valor: valor.strip() if valor is not None else None),
    ("char_length", 1, lambda valor: len(valor) if valor is not None else None),
]

DATOS_VEHICULO = {
    "patente": "ABCD12",
    "marca": "Toyota",
    "modelo": "Yaris",
    "anio": 2021,
    "kilometraje": 45000,
}

CLIENTE = ("cliente@integracion.cl", "ClaveIntegracion123!", "Cliente Integración")
SEGUNDO_CLIENTE = ("otro@integracion.cl", "ClaveIntegracion123!", "Otro Cliente")
ADMINISTRADOR = ("admin@integracion.cl", "AdminIntegracion123!", "Admin Integración")


def _crear_sqlite(
    base: type,
    funciones_sqlite: list[tuple[str, int, object]] | None = None,
) -> tuple[Engine, Session]:
    """Engine SQLite en memoria + una sesión; devuelve ambos para el teardown."""
    motor = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    if funciones_sqlite:

        @event.listens_for(motor, "connect")
        def _registrar_funciones(conexion, _registro) -> None:
            for nombre, aridad, funcion in funciones_sqlite:
                conexion.create_function(nombre, aridad, funcion)

    base.metadata.create_all(motor)
    fabrica = sessionmaker(bind=motor, expire_on_commit=False)
    return motor, fabrica()


def _fabrica_override(sesion: Session) -> object:
    """Devuelve un override de `get_db` SIN parámetros.

    FastAPI inspecciona la firma de la función que reemplaza la dependencia:
    un parámetro `_sesion=...` se convertiría en un query param y pydantic
    intentaría `deepcopy` de la Session (no pickeable). La sesión se captura por
    closure, no como argumento.
    """

    def reemplazar_db() -> Generator[Session, None, None]:
        yield sesion

    return reemplazar_db


def _clave_montaje(url: str) -> str:
    """Clave de mount de HTTPX: `scheme://netloc` exacta para la URL dada."""
    partes = urlsplit(url)
    return f"{partes.scheme}://{partes.netloc}"


# Registro de qué microservicio recibió cada petición: (servicio, método, ruta).
# MS3 y MS4 responden el mismo 404 de FastAPI, así que el body no alcanza para
# saber a cuál llegó la Gateway; este espía lo deja explícito.
LLAMADAS: list[tuple[str, str, str]] = []


def _espiar(nombre: str, app):
    """Envuelve la app ASGI de un microservicio y anota cada petición HTTP."""

    async def envoltura(scope, receive, send):
        if scope["type"] == "http":
            LLAMADAS.append((nombre, scope["method"], scope["path"]))
        await app(scope, receive, send)

    return envoltura


def ultima_llamada() -> tuple[str, str, str]:
    assert LLAMADAS, "la Gateway no llamó a ningún microservicio"
    return LLAMADAS[-1]


@pytest.fixture
def ecosistema(monkeypatch: pytest.MonkeyPatch):
    """Gateway real + 4 microservicios reales sobre SQLite en memoria.

    Arma las cuatro bases, iguala las claves JWT (MS2/MS4 copian la de MS1:
    la leen en tiempo de llamada desde `dependencies.py`) y le da a la Gateway
    un cliente HTTPX con `ASGITransport` por URL base, para que el enrutamiento
    (`gateway.rutas`) lleve cada prefijo a la app real que corresponde.
    """
    LLAMADAS.clear()
    motor_ms1, sesion_ms1 = _crear_sqlite(BaseMS1)
    sesion_ms1.add_all([Rol(nombre=rol.value) for rol in NombreRol])
    sesion_ms1.commit()

    # MS2: mismo patrón que test_vehiculos_api.py y test_ordenes_api.py:
    # funciones que PostgreSQL tiene y SQLite no, y el catálogo de estados.
    motor_ms2, sesion_ms2 = _crear_sqlite(BaseMS2, funciones_sqlite=_FUNCIONES_SQLITE)
    sesion_ms2.add_all(
        [
            EstadoOrden(estado_codigo=codigo, nombre=nombre)
            for codigo, nombre in ESTADOS_ORDEN.items()
        ]
    )
    sesion_ms2.commit()

    # MS3 y MS4 también usan btrim/char_length en CHECKs de sus modelos.
    motor_ms3, sesion_ms3 = _crear_sqlite(BaseMS3, funciones_sqlite=_FUNCIONES_SQLITE)
    motor_ms4, sesion_ms4 = _crear_sqlite(BaseMS4, funciones_sqlite=_FUNCIONES_SQLITE)

    motores = [motor_ms1, motor_ms2, motor_ms3, motor_ms4]
    bases = [BaseMS1, BaseMS2, BaseMS3, BaseMS4]
    apps = [app_ms1, app_ms2, app_ms3, app_ms4]
    get_dbs = [get_db_ms1, get_db_ms2, get_db_ms3, get_db_ms4]
    sesiones = [sesion_ms1, sesion_ms2, sesion_ms3, sesion_ms4]

    for app, get_db, sesion in zip(apps, get_dbs, sesiones):
        app.dependency_overrides[get_db] = _fabrica_override(sesion)

    # Clave JWT compartida: MS2 y MS4 validan el token que emite MS1.
    clave_ms1 = ms1_settings.JWT_SECRET_KEY
    monkeypatch.setattr(ms2_settings, "JWT_SECRET_KEY", clave_ms1)
    monkeypatch.setattr(ms4_settings, "JWT_SECRET_KEY", clave_ms1)

    # Cliente HTTPX de la Gateway: cada URL base de gateway.config monta el
    # ASGITransport de su microservicio. Se crea perezosamente (lo llama el
    # código async de la Gateway dentro del event loop del TestClient) y uno
    # por test.
    cliente = None

    def _obtener_cliente() -> httpx.AsyncClient:
        nonlocal cliente
        if cliente is None:
            cliente = httpx.AsyncClient(
                mounts={
                    _clave_montaje(gateway_settings.MS1_URL): httpx.ASGITransport(
                        app=_espiar("ms1_auth", app_ms1)
                    ),
                    _clave_montaje(gateway_settings.MS2_URL): httpx.ASGITransport(
                        app=_espiar("ms2_taller", app_ms2)
                    ),
                    _clave_montaje(gateway_settings.MS3_URL): httpx.ASGITransport(
                        app=_espiar("ms3_presupuestos", app_ms3)
                    ),
                    _clave_montaje(gateway_settings.MS4_URL): httpx.ASGITransport(
                        app=_espiar("ms4_evidencias", app_ms4)
                    ),
                }
            )
        return cliente

    # Están importados por nombre en los routers; parchear solo
    # gateway.cliente_http no tendría efecto.
    monkeypatch.setattr(routers_proxy, "obtener_cliente", _obtener_cliente)
    monkeypatch.setattr(routers_health, "obtener_cliente", _obtener_cliente)

    try:
        with TestClient(gateway_app) as gw:
            yield gw, sesion_ms1, sesion_ms2
    finally:
        for app in apps:
            app.dependency_overrides.clear()
        for sesion in sesiones:
            sesion.close()
        for motor, base in zip(motores, bases):
            base.metadata.drop_all(motor)
            motor.dispose()


def autorizacion(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def registrar_y_login(gw: TestClient, email: str, password: str, nombre: str) -> str:
    """Registra un cliente por la Gateway y devuelve su token (rollo real MS1)."""
    registro = gw.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": nombre},
    )
    assert registro.status_code == 201, registro.text
    login = gw.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def usuario_id_por_token(gw: TestClient, token: str) -> int:
    me = gw.get("/api/auth/me", headers=autorizacion(token))
    assert me.status_code == 200, me.text
    return me.json()["id"]


def crear_perfil_cliente(sesion_ms2: Session, usuario_id: int) -> Cliente:
    """Perfil Cliente en MS2 para un usuario de MS1 (relación lógica, §8)."""
    cliente = Cliente(usuario_id=usuario_id)
    sesion_ms2.add(cliente)
    sesion_ms2.commit()
    sesion_ms2.refresh(cliente)
    return cliente


def crear_administrador(
    sesion_ms1: Session, gw: TestClient, email: str, password: str, nombre: str
) -> str:
    """Crea un administrador directo en MS1 (no hay endpoint público) y loguea."""
    rol_admin = sesion_ms1.scalar(
        select(Rol).where(Rol.nombre == NombreRol.ADMINISTRADOR.value)
    )
    assert rol_admin is not None
    usuario = Usuario(
        correo=email,
        nombre=nombre,
        contrasena_hash=hash_contrasena(password),
        activo=True,
    )
    sesion_ms1.add(usuario)
    sesion_ms1.flush()
    sesion_ms1.add(UsuarioRol(usuario=usuario, rol=rol_admin))
    sesion_ms1.commit()

    login = gw.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


# ---------------------------------------------------------------------------
# MS1 — /api/auth
# ---------------------------------------------------------------------------


def test_registro_login_y_me_devuelven_usuario_cliente(ecosistema):
    gw, _, _ = ecosistema
    correo, clave, nombre = CLIENTE

    token = registrar_y_login(gw, correo, clave, nombre)
    me = gw.get("/api/auth/me", headers=autorizacion(token))

    assert me.status_code == 200
    cuerpo = me.json()
    assert cuerpo["id"] == usuario_id_por_token(gw, token)
    assert cuerpo["email"] == correo
    assert cuerpo["roles"] == ["cliente"]


def test_login_con_contrasena_incorrecta_devuelve_401(ecosistema):
    gw, _, _ = ecosistema
    correo, clave, nombre = CLIENTE
    registrar_y_login(gw, correo, clave, nombre)

    respuesta = gw.post(
        "/api/auth/login",
        json={"email": correo, "password": "ClaveIncorrecta123!"},
    )

    # El 401 viene de MS1 y el body pasa tal cual, con "detail".
    assert respuesta.status_code == 401
    assert "detail" in respuesta.json()


def test_me_sin_token_devuelve_401(ecosistema):
    gw, _, _ = ecosistema

    respuesta = gw.get("/api/auth/me")

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


# ---------------------------------------------------------------------------
# MS2 — /api/vehiculos y /api/ordenes
# ---------------------------------------------------------------------------


def test_vehiculos_flujo_completo_con_token_de_ms1(ecosistema):
    gw, _, sesion_ms2 = ecosistema
    correo, clave, nombre = CLIENTE
    token = registrar_y_login(gw, correo, clave, nombre)
    crear_perfil_cliente(sesion_ms2, usuario_id_por_token(gw, token))
    cabeceras = autorizacion(token)

    # El caso clave: el token emitido por MS1 lo acepta MS2.
    alta = gw.post("/api/vehiculos", json=DATOS_VEHICULO, headers=cabeceras)
    assert alta.status_code == 201, alta.text
    id_vehiculo = alta.json()["vehiculo_id"]

    lista = gw.get("/api/vehiculos", headers=cabeceras)
    assert lista.status_code == 200
    assert [v["vehiculo_id"] for v in lista.json()] == [id_vehiculo]

    detalle = gw.get(f"/api/vehiculos/{id_vehiculo}", headers=cabeceras)
    assert detalle.status_code == 200
    assert detalle.json()["patente"] == DATOS_VEHICULO["patente"]


def test_vehiculos_sin_token_devuelve_401_con_www_authenticate(ecosistema):
    gw, _, _ = ecosistema

    respuesta = gw.get("/api/vehiculos")

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_vehiculos_con_body_invalido_devuelve_422_con_detalle_lista(ecosistema):
    gw, _, sesion_ms2 = ecosistema
    correo, clave, nombre = CLIENTE
    token = registrar_y_login(gw, correo, clave, nombre)
    crear_perfil_cliente(sesion_ms2, usuario_id_por_token(gw, token))

    respuesta = gw.post(
        "/api/vehiculos", json={"patente": "ABCD12"}, headers=autorizacion(token)
    )

    # El 422 lo genera MS2 (falta marca/modelo) y pasa tal cual, con detalle lista.
    assert respuesta.status_code == 422
    assert isinstance(respuesta.json()["detail"], list)


def test_otro_cliente_no_ve_vehiculo_del_primero(ecosistema):
    gw, _, sesion_ms2 = ecosistema
    correo_a, clave, nombre_a = CLIENTE
    correo_b, _, nombre_b = SEGUNDO_CLIENTE

    token_a = registrar_y_login(gw, correo_a, clave, nombre_a)
    token_b = registrar_y_login(gw, correo_b, clave, nombre_b)
    crear_perfil_cliente(sesion_ms2, usuario_id_por_token(gw, token_a))
    crear_perfil_cliente(sesion_ms2, usuario_id_por_token(gw, token_b))

    alta = gw.post("/api/vehiculos", json=DATOS_VEHICULO, headers=autorizacion(token_a))
    id_vehiculo = alta.json()["vehiculo_id"]

    # Comportamiento real de MS2 (test_vehiculos_api.py): 404 idéntico al inexistente.
    detalle = gw.get(
        f"/api/vehiculos/{id_vehiculo}", headers=autorizacion(token_b)
    )

    assert detalle.status_code == 404
    assert detalle.json() == {"detail": "Vehículo no encontrado"}


def test_ordenes_administrador_devuelve_200_y_lista(ecosistema):
    gw, sesion_ms1, _ = ecosistema
    correo, clave, nombre = ADMINISTRADOR
    token = crear_administrador(sesion_ms1, gw, correo, clave, nombre)

    respuesta = gw.get("/api/ordenes", headers=autorizacion(token))

    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_token_alterado_devuelve_401(ecosistema):
    gw, _, _ = ecosistema
    correo, clave, nombre = CLIENTE
    token = registrar_y_login(gw, correo, clave, nombre)

    alterado = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    respuesta = gw.get("/api/vehiculos", headers=autorizacion(alterado))

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


# ---------------------------------------------------------------------------
# MS3 / MS4 — prefijos sin endpoints de negocio aún (Semana 5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefijo", ["presupuestos", "repuestos"])
def test_ms3_responde_404_propio_por_cada_prefijo(ecosistema, prefijo):
    gw, _, _ = ecosistema

    respuesta = gw.get(f"/api/{prefijo}")

    # 404 que viene DE la app real de MS3 (FastAPI), no de la Gateway.
    assert respuesta.status_code == 404
    cuerpo = respuesta.json()
    assert cuerpo == {"detail": "Not Found"}
    assert "error" not in cuerpo
    assert ultima_llamada() == ("ms3_presupuestos", "GET", f"/{prefijo}")


def test_ms4_responde_404_propio(ecosistema):
    gw, _, _ = ecosistema

    respuesta = gw.get("/api/evidencias")

    assert respuesta.status_code == 404
    cuerpo = respuesta.json()
    assert cuerpo == {"detail": "Not Found"}
    assert "error" not in cuerpo
    assert ultima_llamada() == ("ms4_evidencias", "GET", "/evidencias")


# ---------------------------------------------------------------------------
# Transversales
# ---------------------------------------------------------------------------


def test_health_servicios_devuelve_200_con_cuatro_ok(ecosistema):
    gw, _, _ = ecosistema

    respuesta = gw.get("/api/health/servicios")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "ok"
    assert set(cuerpo["servicios"]) == {
        "ms1_auth",
        "ms2_taller",
        "ms3_presupuestos",
        "ms4_evidencias",
    }
    for estado in cuerpo["servicios"].values():
        assert estado["estado"] == "ok"


def test_x_request_id_enviado_vuelve_igual_en_peticion_proxied(ecosistema):
    gw, _, _ = ecosistema
    correo, clave, nombre = CLIENTE
    token = registrar_y_login(gw, correo, clave, nombre)

    respuesta = gw.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "integracion-abc-123",
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["x-request-id"] == "integracion-abc-123"


def test_prefijo_desconocido_devuelve_404_ruta_no_encontrada(ecosistema):
    gw, _, _ = ecosistema

    respuesta = gw.get("/api/noexiste")

    # Es la Gateway quien responde: ningún microservicio la acepta.
    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["codigo"] == "RUTA_NO_ENCONTRADA"
    assert LLAMADAS == []  # no llegó a ningún microservicio


def _verificar_ms1(gw: TestClient, sesion_ms1: Session, sesion_ms2: Session) -> None:
    """MS1: solo él conoce el perfil del usuario registrado (email y roles)."""
    correo, clave, nombre = CLIENTE
    token = registrar_y_login(gw, correo, clave, nombre)
    me = gw.get("/api/auth/me", headers=autorizacion(token))
    assert me.status_code == 200
    assert me.json()["email"] == correo
    assert me.json()["roles"] == ["cliente"]
    assert ultima_llamada() == ("ms1_auth", "GET", "/auth/me")


def _verificar_ms2(gw: TestClient, sesion_ms1: Session, sesion_ms2: Session) -> None:
    """MS2: solo él registra vehículos y responde su patente con 201."""
    correo, clave, nombre = CLIENTE
    token = registrar_y_login(gw, correo, clave, nombre)
    crear_perfil_cliente(sesion_ms2, usuario_id_por_token(gw, token))
    alta = gw.post("/api/vehiculos", json=DATOS_VEHICULO, headers=autorizacion(token))
    assert alta.status_code == 201
    assert alta.json()["patente"] == DATOS_VEHICULO["patente"]
    assert ultima_llamada() == ("ms2_taller", "POST", "/vehiculos")


def _verificar_ms3(gw: TestClient, sesion_ms1: Session, sesion_ms2: Session) -> None:
    """MS3: solo él responde el 404 FastAPI propio (sin clave "error")."""
    respuesta = gw.get("/api/presupuestos")
    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Not Found"}
    assert "error" not in respuesta.json()
    assert ultima_llamada() == ("ms3_presupuestos", "GET", "/presupuestos")


def _verificar_ms4(gw: TestClient, sesion_ms1: Session, sesion_ms2: Session) -> None:
    """MS4: solo él responde el 404 FastAPI propio (sin clave "error")."""
    respuesta = gw.get("/api/evidencias")
    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Not Found"}
    assert "error" not in respuesta.json()
    assert ultima_llamada() == ("ms4_evidencias", "GET", "/evidencias")


@pytest.mark.parametrize(
    "nombre_servicio,verificador",
    [
        ("ms1_auth", _verificar_ms1),
        ("ms2_taller", _verificar_ms2),
        ("ms3_presupuestos", _verificar_ms3),
        ("ms4_evidencias", _verificar_ms4),
    ],
)
def test_cada_servicio_produce_algo_que_solo_el_genera(
    ecosistema, nombre_servicio, verificador
):
    """Una petición proxied responde algo que SOLO ese microservicio produce.

    MS1 → el perfil del usuario autenticado; MS2 → el vehículo recién creado
    (201 + patente); MS3 y MS4 → su 404 FastAPI propio, sin la clave "error"
    de la Gateway.
    """
    gw, sesion_ms1, sesion_ms2 = ecosistema
    verificador(gw, sesion_ms1, sesion_ms2)
