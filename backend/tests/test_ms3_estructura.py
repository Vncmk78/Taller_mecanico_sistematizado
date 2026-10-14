"""Pruebas de estructura del microservicio MS3 (Presupuestos, Repuestos y Proveedores).

Verifican que el esqueleto del servicio quedó coherente, sin requerir PostgreSQL:

- `/health` responde 200 y `/health/db` usa la sesión inyectada por `get_db`.
- La documentación OpenAPI declara las secciones del servicio.
- Alembic tiene UNA sola cadena lineal 0001_ms3 → 0002_ms3 → 0003_ms3 → 0004_ms3.
- Todos los modelos del MER quedan registrados en `Base.metadata`.
- El guard `requerir_roles` responde 401 sin token / token inválido,
  403 con un rol no permitido y 200 con el rol correcto.

La ejecución real de las migraciones (triggers de PostgreSQL) se prueba contra
PostgreSQL en services/ms2_taller/tests y en la validación desde base vacía.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from services.ms3_presupuestos import models  # noqa: F401  (registra modelos)
from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import Base, get_db
from services.ms3_presupuestos.dependencies import requerir_roles
from services.ms3_presupuestos.main import app
from shared.auth import NombreRol, PrincipalAutenticado, crear_token_acceso

RUTA_ALEMBIC = "services/ms3_presupuestos/alembic.ini"
CLAVE = settings.JWT_SECRET_KEY.get_secret_value()


def _token(*roles: NombreRol, usuario_id: int = 7) -> str:
    return crear_token_acceso(
        usuario_id=usuario_id, roles=roles, clave_secreta=CLAVE, algoritmo="HS256"
    )


# --------------------------------------------------------------------------- #
# 1) Healthchecks y OpenAPI                                                   #
# --------------------------------------------------------------------------- #

def test_health_responde_200() -> None:
    with TestClient(app) as cliente:
        respuesta = cliente.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json()["servicio"].startswith("MS3")


def test_health_db_usa_la_sesion_de_get_db() -> None:
    class SesionFalsa:
        def __init__(self) -> None:
            self.consultas: list[str] = []

        def execute(self, sentencia):  # noqa: ANN001
            self.consultas.append(str(sentencia))

    sesion = SesionFalsa()
    app.dependency_overrides[get_db] = lambda: sesion
    try:
        with TestClient(app) as cliente:
            respuesta = cliente.get("/health/db")
    finally:
        app.dependency_overrides.clear()
    assert respuesta.status_code == 200
    assert respuesta.json()["database"] == "ok"
    assert sesion.consultas == ["SELECT 1"]


def test_openapi_declara_las_secciones_del_servicio() -> None:
    etiquetas = {t["name"] for t in app.openapi()["tags"]}
    assert {"health", "presupuestos", "repuestos", "proveedores", "inventario"} <= etiquetas


# --------------------------------------------------------------------------- #
# 2) Modelos y migraciones                                                    #
# --------------------------------------------------------------------------- #

def test_modelos_del_mer_registrados_en_la_metadata() -> None:
    esperadas = {
        "proveedor", "repuesto", "movimiento_inventario", "parametro_inventario",
        "historial_umbral", "presupuesto", "version_presupuesto",
        "item_presupuesto", "decision_presupuesto",
    }
    assert esperadas <= set(Base.metadata.tables)


def test_alembic_tiene_una_sola_cadena_lineal() -> None:
    script = ScriptDirectory.from_config(Config(RUTA_ALEMBIC))
    assert script.get_heads() == ["0004_ms3"]
    cadena = [rev.revision for rev in script.walk_revisions("base", "heads")]
    assert list(reversed(cadena)) == ["0001_ms3", "0002_ms3", "0003_ms3", "0004_ms3"]


# --------------------------------------------------------------------------- #
# 3) Autenticación y roles                                                    #
# --------------------------------------------------------------------------- #

def _app_con_guard() -> FastAPI:
    """App mínima que solo usa el guard: prueba la dependencia aislada."""
    prueba = FastAPI()

    @prueba.get("/solo-admin")
    def solo_admin(
        principal: PrincipalAutenticado = Depends(requerir_roles(NombreRol.ADMINISTRADOR)),
    ) -> dict[str, int]:
        return {"usuario_id": principal.usuario_id}

    return prueba


def test_guard_sin_token_responde_401() -> None:
    respuesta = TestClient(_app_con_guard()).get("/solo-admin")
    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_guard_token_invalido_responde_401() -> None:
    respuesta = TestClient(_app_con_guard()).get(
        "/solo-admin", headers={"Authorization": "Bearer no-es-un-jwt"}
    )
    assert respuesta.status_code == 401


def test_guard_token_expirado_responde_401() -> None:
    vencido = jwt.encode(
        {
            "sub": "7",
            "roles": ["administrador"],
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        CLAVE,
        algorithm="HS256",
    )
    respuesta = TestClient(_app_con_guard()).get(
        "/solo-admin", headers={"Authorization": f"Bearer {vencido}"}
    )
    assert respuesta.status_code == 401


def test_guard_rol_no_permitido_responde_403() -> None:
    respuesta = TestClient(_app_con_guard()).get(
        "/solo-admin", headers={"Authorization": f"Bearer {_token(NombreRol.CLIENTE)}"}
    )
    assert respuesta.status_code == 403


def test_guard_rol_permitido_responde_200_con_la_identidad() -> None:
    token = _token(NombreRol.MECANICO, NombreRol.ADMINISTRADOR, usuario_id=42)
    respuesta = TestClient(_app_con_guard()).get(
        "/solo-admin", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 200
    assert respuesta.json() == {"usuario_id": 42}
