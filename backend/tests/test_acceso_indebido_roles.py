"""Revisión de casos de acceso indebido entre roles (matriz de autorización).

Contrasta dos zonas de `docs/matriz-autorizacion-roles.md` contra la
implementación real de los guards. La Gateway **no valida el JWT**, así que toda
decisión de autorización vive en el microservicio y se prueba aquí directamente.

El módulo tiene dos partes:

- **Límites que sí están implementados** (pruebas que PASAN): verifican que los
  guards `requerir_roles` rechazan al rol equivocado con `403` y que la falta de
  token responde `401`, **no** `403`. Protegen contra regresiones reales.

- **Huecos declarados en la matriz** (pruebas `xfail(strict=True)`): la matriz
  ya los lista como pendientes (§4.4 "limitar al mecánico a las órdenes que
  tiene asignadas"; §4.3 `mecanico_id` "no se valida en el servidor que exista,
  esté activo ni tenga el rol mecanico"). La aserción enuncia el comportamiento
  **correcto**, y el marcador documenta que hoy no se cumple.

  Por qué `xfail(strict=True)` y no un `assert` simple: si la aserción fallara
  rojo, la suite entera quedaría roja por un defecto que no introduce este
  cambio; y si se caracterizara el comportamiento actual (201/200), el código
  quedaría "bendecido" como correcto en un tema de seguridad. Con `strict=True`,
  en cuanto alguien implemente la corrección la prueba pasa y **strict** la
  convierte en fallo, obligando a retirar el marcador. Es un registro honesto
  del pendiente, no una afirmación de que esté resuelto.

Los códigos exactos de rechazo de esos huecos todavía no son contrato (la
matriz no los fija), así que las aserciones piden solo la esencia de seguridad:
**que la operación sea rechazada**. MS4 queda fuera: sus filas 📐
(`visible_cliente`, `Eliminar`) son endpoints que aún no existen —el router solo
expone `POST` y `GET`— y un endpoint inexistente no es un acceso explotable.

SQLite comprueba contratos y autorización; los triggers y locks de PostgreSQL se
verifican en las pruebas ORM de cada servicio, no aquí.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# El conftest de tests/ ya inyecta las claves JWT; aquí se repiten para que el
# módulo se pueda leer (y ejecutar) de forma independiente.
for _servicio in ("MS1", "MS2", "MS3", "MS4"):
    os.environ.setdefault(
        f"{_servicio}_JWT_SECRET_KEY", f"clave-acceso-indebido-{_servicio}-123456"
    )
    os.environ.setdefault(
        f"{_servicio}_DATABASE_URL",
        f"sqlite+pysqlite:////tmp/sgtm_acceso_{_servicio.lower()}.db",
    )

from services.ms2_taller.config import settings as settings_ms2  # noqa: E402
from services.ms2_taller.db import get_db as get_db_ms2  # noqa: E402
from services.ms2_taller.main import app as app_ms2  # noqa: E402
from services.ms2_taller.models import (  # noqa: E402
    Base as BaseMS2, Cliente, EstadoOrden, IngresoVehiculo, OrdenTrabajo, Vehiculo,
)
from services.ms2_taller.models.estado_orden import ESTADOS_ORDEN, RECIBIDO  # noqa: E402
from services.ms3_presupuestos.config import settings as settings_ms3  # noqa: E402
from services.ms3_presupuestos.db import get_db as get_db_ms3  # noqa: E402
from services.ms3_presupuestos.main import app as app_ms3  # noqa: E402
from services.ms3_presupuestos.models import Base as BaseMS3  # noqa: E402
from shared.auth import NombreRol, crear_token_acceso  # noqa: E402


# Los dos huecos revisados, con la referencia exacta en la matriz.
HUECO_MS3_SIN_ASIGNAR = (
    "matriz-autorizacion-roles.md §4.4: pendiente limitar al mecánico a las "
    "órdenes que tiene asignadas (dato de MS2)"
)
HUECO_MS2_MECANICO_ID = (
    "matriz-autorizacion-roles.md §4.3: mecanico_id no se valida en el servidor "
    "que exista, esté activo ni tenga el rol mecanico"
)

# Una orden en estado no terminal, requisito de la asignación de mecánico.
ORDEN_VIVA = RECIBIDO


def _base_aislada(base) -> tuple:
    """Motor SQLite en memoria con las funciones que los modelos necesitan."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _funciones_sqlite(conexion, _registro):
        conexion.create_function(
            "btrim", 1, lambda x: x.strip() if x is not None else None
        )
        conexion.create_function(
            "char_length", 1, lambda x: len(x) if x is not None else None
        )
        conexion.execute("PRAGMA foreign_keys=ON")

    base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)


def _sesion_por_peticion(fabrica):
    def dependencia() -> Generator[Session, None, None]:
        with fabrica() as db:
            yield db

    return dependencia


def _sin_token_externo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falla rápido y con mensaje claro si algo intenta consultar MS2 o MS3.

    Ninguna de las operaciones revisadas debiera salirse de su servicio: la
    creación de presupuesto (MS3) no valida la orden contra MS2 y la asignación
    (MS2) no consulta MS1. Si algún día eso cambia, mejor enterarse aquí.
    """

    def _rechazar(url, **_kwargs):
        raise AssertionError(f"Llamada HTTP inesperada a {url}")

    monkeypatch.setattr(httpx, "get", _rechazar)
    monkeypatch.setattr(httpx, "post", _rechazar)


@pytest.fixture
def escenario(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """MS2 y MS3 con bases propias en memoria y una orden viva sembrada."""

    engine2, fabrica2 = _base_aislada(BaseMS2)
    engine3, fabrica3 = _base_aislada(BaseMS3)

    with fabrica2() as db:
        db.add_all(
            [EstadoOrden(estado_codigo=codigo, nombre=nombre)
             for codigo, nombre in ESTADOS_ORDEN.items()]
        )
        # El dueño del vehículo es la cuenta 42 (rol cliente); la orden es
        # ajena a todo mecánico, que es el punto de la revisión.
        vehiculo = Vehiculo(
            cliente=Cliente(usuario_id=42),
            patente="ACC001", marca="Marca", modelo="Modelo",
        )
        db.add(vehiculo)
        db.flush()
        ingreso = IngresoVehiculo(vehiculo_id=vehiculo.vehiculo_id, registrado_por_id=99)
        db.add(ingreso)
        db.flush()
        orden = OrdenTrabajo(
            vehiculo_id=vehiculo.vehiculo_id,
            ingreso_id=ingreso.ingreso_id,
            estado_codigo=ORDEN_VIVA,
            creado_por_id=99,
        )
        db.add(orden)
        db.commit()
        orden_id = orden.orden_id

    # Mismo secreto en ambos servicios: los tokens se emiten con el de MS2.
    monkeypatch.setattr(settings_ms3, "JWT_SECRET_KEY", settings_ms2.JWT_SECRET_KEY)
    monkeypatch.setattr(settings_ms3, "MS2_URL", "http://ms2-no-debe-usarse")
    app_ms2.dependency_overrides[get_db_ms2] = _sesion_por_peticion(fabrica2)
    app_ms3.dependency_overrides[get_db_ms3] = _sesion_por_peticion(fabrica3)
    _sin_token_externo(monkeypatch)

    with TestClient(app_ms2) as ms2, TestClient(app_ms3) as ms3:
        yield SimpleNamespace(ms2=ms2, ms3=ms3, orden_id=orden_id)

    app_ms2.dependency_overrides.pop(get_db_ms2, None)
    app_ms3.dependency_overrides.pop(get_db_ms3, None)
    engine2.dispose()
    engine3.dispose()


def _cabeceras(usuario_id: int | None, roles=()) -> dict[str, str]:
    """`Authorization` con un JWT real, o vacío si `usuario_id` es `None`.

    `roles` acepta un `NombreRol` suelto o una colección: `crear_token_acceso`
    exige una colección no vacía.
    """

    if usuario_id is None:
        return {}
    if isinstance(roles, NombreRol):
        roles = (roles,)
    token = crear_token_acceso(
        usuario_id,
        roles,
        clave_secreta=settings_ms2.JWT_SECRET_KEY.get_secret_value(),
        algoritmo=settings_ms2.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


def _crear_presupuesto(escenario: SimpleNamespace, orden_id: int | None = None,
                       **cabeceras_extra) -> httpx.Response:
    """`POST /presupuestos` de MS3, la operación reservada al personal."""

    body = {
        "orden_id": orden_id if orden_id is not None else escenario.orden_id,
        "items": [{
            "tipo": "mano_de_obra",
            "descripcion": "Diagnóstico general",
            "cantidad": 1,
            "precio_unitario": 15000,
        }],
    }
    return escenario.ms3.post(
        "/presupuestos", json=body, headers=_cabeceras(**cabeceras_extra)
    )


def _asignar_mecanico(escenario: SimpleNamespace, mecanico_id: int,
                      **cabeceras_extra) -> httpx.Response:
    """`PUT /ordenes/{id}/mecanico` de MS2, operación reservada al administrador."""

    return escenario.ms2.put(
        f"/ordenes/{escenario.orden_id}/mecanico",
        json={"mecanico_id": mecanico_id},
        headers=_cabeceras(**cabeceras_extra),
    )


# ---------------------------------------------------------------------------
# Límites implementados: protegen contra regresiones
# ---------------------------------------------------------------------------


def test_cliente_no_crea_presupuesto(escenario: SimpleNamespace) -> None:
    """Crear presupuesto exige Mecánico o Administrador (§4.4)."""

    respuesta = _crear_presupuesto(escenario, usuario_id=42, roles=NombreRol.CLIENTE)

    assert respuesta.status_code == 403
    assert respuesta.json()["detail"] == "No tienes permiso para realizar esta operación"


def test_sin_token_responde_401_y_no_403_en_presupuestos(
    escenario: SimpleNamespace,
) -> None:
    """La falta de credenciales es `401`; el `403` es solo para rol insuficiente."""

    respuesta = _crear_presupuesto(escenario, usuario_id=None)

    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == "No autenticado"


def test_cliente_no_asigna_mecanico(escenario: SimpleNamespace) -> None:
    """Asignar mecánico es exclusivo del Administrador (§4.3)."""

    respuesta = _asignar_mecanico(escenario, 77, usuario_id=42, roles=NombreRol.CLIENTE)

    assert respuesta.status_code == 403
    assert respuesta.json()["detail"] == "No tienes permiso para realizar esta operación"


def test_mecanico_no_asigna_mecanico(escenario: SimpleNamespace) -> None:
    """El rol Mecánico por sí solo no autoriza a asignar (§4.3)."""

    respuesta = _asignar_mecanico(escenario, 77, usuario_id=77, roles=NombreRol.MECANICO)

    assert respuesta.status_code == 403


def test_multirol_no_hereda_permisos_de_administrador(
    escenario: SimpleNamespace,
) -> None:
    """Los roles se acumulan, pero Mecánico+Cliente no es Administrador (§3.1).

    Un usuario con dos roles debe ver la **unión** de sus alcances, nunca
    ganar un permiso que ninguno de sus roles otorga.
    """

    respuesta = _asignar_mecanico(
        escenario, 77, usuario_id=77, roles=(NombreRol.MECANICO, NombreRol.CLIENTE)
    )

    assert respuesta.status_code == 403


def test_asignacion_solo_administrador_en_rol_multiple(
    escenario: SimpleNamespace,
) -> None:
    """Caso simétrico: Administrador+Mecánico sí puede asignar, salvo a sí mismo."""

    respuesta = _asignar_mecanico(
        escenario, 77, usuario_id=99, roles=(NombreRol.ADMINISTRADOR, NombreRol.MECANICO)
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["mecanico_actual_id"] == 77


# ---------------------------------------------------------------------------
# Huecos declarados en la matriz: registrados como xfail estricto
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason=HUECO_MS3_SIN_ASIGNAR)
def test_mecanico_no_asignado_no_crea_presupuesto_de_orden_ajena(
    escenario: SimpleNamespace,
) -> None:
    """Un mecánico no debe crear presupuesto de una orden que no atiende.

    `crear` (MS3) solo aplica `requerir_roles(MECANICO, ADMINISTRADOR)` y nunca
    recibe el `VerificadorOrdenes` que sí usan los caminos del cliente, de modo
    que cualquier mecánico del taller puede presupuestar órdenes ajenas.
    """

    respuesta = _crear_presupuesto(escenario, usuario_id=77, roles=NombreRol.MECANICO)

    # Debe rechazarse: el código exacto (403) aún no es contrato.
    assert respuesta.status_code >= 400, (
        f"Un mecánico creó presupuesto de una orden que no atiende: {respuesta.status_code}"
    )


@pytest.mark.xfail(strict=True, reason=HUECO_MS3_SIN_ASIGNAR)
def test_mecanico_no_crea_presupuesto_de_orden_inexistente(
    escenario: SimpleNamespace,
) -> None:
    """MS3 guarda `orden_id` como referencia lógica sin comprobarla (§8).

    Ni la existencia de la orden ni su pertenencia se verifican al crear: el
    presupuesto queda asociado a un `orden_id` que puede no existir.
    """

    respuesta = _crear_presupuesto(
        escenario, orden_id=999999, usuario_id=77, roles=NombreRol.MECANICO
    )

    assert respuesta.status_code >= 400, (
        f"Se creó presupuesto para la orden inexistente 999999: {respuesta.status_code}"
    )


@pytest.mark.xfail(strict=True, reason=HUECO_MS2_MECANICO_ID)
def test_administrador_no_asigna_a_un_usuario_inexistente(
    escenario: SimpleNamespace,
) -> None:
    """`mecanico_id` no se valida contra MS1: se guarda tal cual."""

    respuesta = _asignar_mecanico(
        escenario, 12345, usuario_id=99, roles=NombreRol.ADMINISTRADOR
    )

    assert respuesta.status_code >= 400, (
        f"Se asignó como mecánico al usuario inexistente 12345: {respuesta.status_code}"
    )


@pytest.mark.xfail(strict=True, reason=HUECO_MS2_MECANICO_ID)
def test_administrador_no_asigna_a_un_usuario_sin_rol_mecanico(
    escenario: SimpleNamespace,
) -> None:
    """La cuenta 42 es propietaria del vehículo (rol cliente), no mecánica."""

    respuesta = _asignar_mecanico(
        escenario, 42, usuario_id=99, roles=NombreRol.ADMINISTRADOR
    )

    assert respuesta.status_code >= 400, (
        f"Se asignó como mecánico a la cuenta 42 (rol cliente): {respuesta.status_code}"
    )
