"""Revisión de casos de acceso indebido entre roles (matriz de autorización).

Contrasta dos zonas de `docs/matriz-autorizacion-roles.md` contra la
implementación real de los guards. La Gateway **no valida el JWT**, así que toda
decisión de autorización vive en el microservicio y se prueba aquí directamente.

El módulo tiene dos partes:

- **Límites que sí están implementados** (pruebas que PASAN): verifican que los
  guards `requerir_roles` rechazan al rol equivocado con `403` y que la falta de
  token responde `401`, **no** `403`. Protegen contra regresiones reales.

Los antiguos huecos §4.3 (`mecanico_id` sin validar contra MS1) y §4.4
(mecánico capaz de presupuestar órdenes ajenas) ya están corregidos; las
pruebas que los enunciaban nacieron como `xfail(strict=True)` y hoy se quedan
como regresión con aserciones de código exacto (404/409/503).

Los códigos de rechazo son ahora contrato y se verifican exactamente aquí.
MS4 queda fuera: sus filas 📐
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
from services.ms3_presupuestos.models import (  # noqa: E402
    Base as BaseMS3, Proveedor, Repuesto,
)
from shared.auth import NombreRol, crear_token_acceso  # noqa: E402


# Escenarios §4.3 y §4.4: huecos ya corregidos; las pruebas quedan como regresión
# de lo que antes se registraba con `xfail` en `matriz-autorizacion-roles.md`.

# Base del MS1 simulado: las respuestas de cada escenario salen bajo esta URL.
MOCK_MS1 = "http://ms1-acceso-indebido"

# Base del MS2 simulado para MS3: las llamadas se reencaminan al TestClient real
# de MS2, de modo que la visibilidad (mecánico = solo órdenes asignadas) sea la
# de verdad (§4.4).
MOCK_MS2 = "http://ms2-acceso-indebido"

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


def _simular_entorno_externo(
    monkeypatch: pytest.MonkeyPatch, ms1: dict, ms2: dict
) -> None:
    """Sustituye `httpx` por un dispatcher: MS1 y MS2 simulados, lo demás hostil.

    `GET {MOCK_MS1}/auth/usuarios/{id}` responde del catálogo
    `ms1["usuarios"]` (404 si el id no está) y con `ms1["caido"]` la conexión
    se corta (`httpx.ConnectError`), como si MS1 estuviera abajo.

    `GET {MOCK_MS2}/ordenes/...` se reencamina al TestClient REAL de MS2
    (`ms2["cliente"]`, montado al entrar al `with`), así MS3 comprueba la
    visibilidad con la lógica de autorización verdadera de MS2.

    Cualquier otra llamada externa rompe la prueba: nada más debiera salir
    de MS2/MS3.
    """

    def _get(url, **kwargs):
        if url.startswith(MOCK_MS1):
            if ms1["caido"]:
                raise httpx.ConnectError("MS1 no disponible")
            usuario_id = int(url.rsplit("/", 1)[-1])
            usuario = ms1["usuarios"].get(usuario_id)
            if usuario is None:
                return httpx.Response(404, request=httpx.Request("GET", url))
            return httpx.Response(
                200, json=usuario, request=httpx.Request("GET", url)
            )
        if url.startswith(MOCK_MS2):
            if ms2["caido"]:
                raise httpx.ConnectError("MS2 no disponible")
            cliente = ms2["cliente"]
            if cliente is None:
                raise AssertionError("El TestClient de MS2 aún no está montado")
            return cliente.get(url.removeprefix(MOCK_MS2), headers=kwargs.get("headers"))
        raise AssertionError(f"Llamada HTTP inesperada a {url}")

    def _rechazar(url, **_kwargs):
        raise AssertionError(f"Llamada HTTP inesperada a {url}")

    monkeypatch.setattr(httpx, "get", _get)
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

    with fabrica3() as db:
        # Un repuesto con stock para probar los movimientos de inventario.
        proveedor = Proveedor(nombre="Proveedor de refacción", contacto="Pruebas")
        repuesto = Repuesto(proveedor=proveedor, nombre="Filtro de aceite", stock=5)
        db.add_all([proveedor, repuesto])
        db.commit()
        repuesto_id = repuesto.repuesto_id

    # Mismo secreto en ambos servicios: los tokens se emiten con el de MS2.
    monkeypatch.setattr(settings_ms3, "JWT_SECRET_KEY", settings_ms2.JWT_SECRET_KEY)
    monkeypatch.setattr(settings_ms3, "MS2_URL", MOCK_MS2)
    monkeypatch.setattr(settings_ms2, "MS1_URL", MOCK_MS1)
    app_ms2.dependency_overrides[get_db_ms2] = _sesion_por_peticion(fabrica2)
    app_ms3.dependency_overrides[get_db_ms3] = _sesion_por_peticion(fabrica3)

    # Catálogo que servirá el MS1 simulado: la asignación de mecánico se
    # valida contra estos usuarios (§4.3).
    ms1 = {
        "usuarios": {
            42: {"id": 42, "email": "cliente@prueba.cl", "full_name": "Cliente 42",
                 "roles": ["cliente"], "is_active": True},
            77: {"id": 77, "email": "mecanico@prueba.cl", "full_name": "Mecánico 77",
                 "roles": ["mecanico"], "is_active": True},
            99: {"id": 99, "email": "admin@prueba.cl", "full_name": "Administrador 99",
                 "roles": ["administrador"], "is_active": True},
        },
        "caido": False,
    }
    # El dispatcher registra el TestClient real de MS2 apenas se monte.
    cliente_ms2 = {"cliente": None, "caido": False}
    _simular_entorno_externo(monkeypatch, ms1, cliente_ms2)

    with TestClient(app_ms2) as ms2, TestClient(app_ms3) as ms3:
        cliente_ms2["cliente"] = ms2
        yield SimpleNamespace(
            ms2=ms2, ms3=ms3, orden_id=orden_id, repuesto_id=repuesto_id,
            ms1=ms1, ms2_ext=cliente_ms2,
        )

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


def _registrar_movimiento(escenario: SimpleNamespace, tipo: str = "compromiso",
                          *, orden_id: int | None = None,
                          clave: str = "clv-prueba-0001",
                          **cabeceras_extra) -> httpx.Response:
    """`POST /inventario/movimientos` de MS3, operación del mecánico/administrador."""

    body: dict[str, object] = {
        "clave_operacion": clave,
        "repuesto_id": escenario.repuesto_id,
        "tipo": tipo,
        "cantidad": 1,
    }
    if tipo in ("compromiso", "consumo", "liberacion"):
        body["orden_id"] = orden_id if orden_id is not None else escenario.orden_id
    return escenario.ms3.post(
        "/inventario/movimientos", json=body, headers=_cabeceras(**cabeceras_extra)
    )


def _versiones(escenario: SimpleNamespace, presupuesto_id: int,
               **cabeceras_extra) -> httpx.Response:
    """`POST /presupuestos/{id}/versiones` de MS3 (nueva versión, sin body)."""

    return escenario.ms3.post(
        f"/presupuestos/{presupuesto_id}/versiones",
        headers=_cabeceras(**cabeceras_extra),
    )


def _reemplazar_items(escenario: SimpleNamespace, presupuesto_id: int, numero: int,
                      **cabeceras_extra) -> httpx.Response:
    """`PUT /presupuestos/{id}/versiones/{n}/items` de MS3 (borrador)."""

    return escenario.ms3.put(
        f"/presupuestos/{presupuesto_id}/versiones/{numero}/items",
        json={"items": [{
            "tipo": "mano_de_obra",
            "descripcion": "Diagnóstico ampliado",
            "cantidad": 2,
            "precio_unitario": 12000,
        }]},
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
# Huecos corregidos: quedan como regresión de lo antes marcado con xfail
# (§4.4 "mecánico limitado a órdenes asignadas", dato de MS2)
# ---------------------------------------------------------------------------


def test_mecanico_no_asignado_no_crea_presupuesto_de_orden_ajena(
    escenario: SimpleNamespace,
) -> None:
    """Un mecánico solo crea presupuesto de la orden que tiene asignada (§4.4).

    MS3 llama a `GET {MS2}/ordenes/{id}` reenviando el JWT del mecánico; MS2
    solo le tiene por visible su asignación, así que la orden ajena queda
    cubierta por el mismo 404 de los presupuestos ajenos al cliente.
    """

    respuesta = _crear_presupuesto(escenario, usuario_id=77, roles=NombreRol.MECANICO)

    assert respuesta.status_code == 404
    assert respuesta.json()["detail"] == f"Orden {escenario.orden_id} no existe"


def test_mecanico_no_crea_presupuesto_de_orden_inexistente(
    escenario: SimpleNamespace,
) -> None:
    """`orden_id` se valida al crear: no queda asociado a una referencia fantasma."""

    respuesta = _crear_presupuesto(
        escenario, orden_id=999999, usuario_id=77, roles=NombreRol.MECANICO
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["detail"] == "Orden 999999 no existe"


def test_mecanico_asignado_crea_presupuesto_de_su_orden(
    escenario: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La regla §4.4 no bloquea al mecánico legítimo.

    El mecánico 77 queda asignado a la orden por su administrador y, con esa
    asignación vigente, su JWT sí la vuelve visible en MS2.
    """

    admin = _cabeceras(99, NombreRol.ADMINISTRADOR)
    asignada = escenario.ms2.put(
        f"/ordenes/{escenario.orden_id}/mecanico",
        json={"mecanico_id": 77},
        headers=admin,
    )
    assert asignada.status_code == 200

    respuesta = _crear_presupuesto(escenario, usuario_id=77, roles=NombreRol.MECANICO)

    assert respuesta.status_code == 201
    assert respuesta.json()["orden_id"] == escenario.orden_id


def test_administrador_no_asigna_a_un_usuario_inexistente(
    escenario: SimpleNamespace,
) -> None:
    """`mecanico_id` se valida contra MS1 (§4.3): inexistente → 404."""

    respuesta = _asignar_mecanico(
        escenario, 12345, usuario_id=99, roles=NombreRol.ADMINISTRADOR
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["detail"] == "El mecánico indicado no existe"


def test_administrador_no_asigna_a_un_usuario_sin_rol_mecanico(
    escenario: SimpleNamespace,
) -> None:
    """La cuenta 42 existe pero es cliente, no mecánica (§4.3) → 409."""

    respuesta = _asignar_mecanico(
        escenario, 42, usuario_id=99, roles=NombreRol.ADMINISTRADOR
    )

    assert respuesta.status_code == 409
    assert (
        respuesta.json()["detail"] == "El usuario indicado no es un mecánico disponible"
    )


def test_asignacion_a_un_mecanico_inactivo_responde_409(
    escenario: SimpleNamespace,
) -> None:
    """El destino debe estar activo, además de tener el rol `mecanico` (§4.3).

    El catálogo del escenario ya cubre el caso 42 (cliente activo); esta
    prueba ejercita la rama `is_active: false` con el mecánico 77 inhabilitado.
    """

    escenario.ms1["usuarios"][77] = {
        "id": 77, "email": "mecanico@prueba.cl", "full_name": "Mecánico 77",
        "roles": ["mecanico"], "is_active": False,
    }
    respuesta = _asignar_mecanico(
        escenario, 77, usuario_id=99, roles=NombreRol.ADMINISTRADOR
    )

    assert respuesta.status_code == 409


def test_asignacion_sin_ms1_responde_503_y_deja_la_orden_intacta(
    escenario: SimpleNamespace,
) -> None:
    """Si no se puede validar el destino, la asignación no ocurre (fail-closed)."""

    escenario.ms1["caido"] = True

    respuesta = _asignar_mecanico(
        escenario, 77, usuario_id=99, roles=NombreRol.ADMINISTRADOR
    )

    assert respuesta.status_code == 503
    orden = escenario.ms2.get(
        f"/ordenes/{escenario.orden_id}",
        headers=_cabeceras(99, NombreRol.ADMINISTRADOR),
    )
    assert orden.status_code == 200
    assert orden.json()["mecanico_actual_id"] is None


# ---------------------------------------------------------------------------
# Alcance de inventario y versiones (§4.4): mecánico = solo órdenes asignadas
# ---------------------------------------------------------------------------


def _presupuesto_admin(escenario: SimpleNamespace) -> dict[str, int]:
    """Presupuesto versión 1 creado por el Administrador sobre la orden viva."""

    creada = _crear_presupuesto(escenario, usuario_id=99, roles=NombreRol.ADMINISTRADOR)
    assert creada.status_code == 201, creada.text
    detalle = creada.json()
    assert detalle["presupuesto_id"] > 0
    return detalle


def test_mecanico_no_asignado_no_registra_compromiso_de_stock_ajeno(
    escenario: SimpleNamespace,
) -> None:
    """El stock se mueve solo desde órdenes que el mecánico tiene asignadas (§4.4)."""

    respuesta = _registrar_movimiento(
        escenario, usuario_id=77, roles=NombreRol.MECANICO
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["detail"] == f"Orden {escenario.orden_id} no existe"


def test_mecanico_asignado_registra_compromiso_de_su_orden(
    escenario: SimpleNamespace,
) -> None:
    """La regla de §4.4 no bloquea al mecánico con la orden asignada."""

    assert _asignar_mecanico(
        escenario, 77, usuario_id=99, roles=NombreRol.ADMINISTRADOR
    ).status_code == 200

    respuesta = _registrar_movimiento(
        escenario, clave="clv-asignada-01", usuario_id=77, roles=NombreRol.MECANICO
    )

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["movimiento"]["orden_id"] == escenario.orden_id


def test_compromiso_sin_ms2_no_se_aplica_responde_503(
    escenario: SimpleNamespace,
) -> None:
    """Sin poder validar la orden en MS2, el stock no se toca (fail-closed)."""

    escenario.ms2_ext["caido"] = True

    respuesta = _registrar_movimiento(
        escenario, usuario_id=77, roles=NombreRol.MECANICO
    )

    assert respuesta.status_code == 503


def test_mecanico_no_asignado_no_versiona_ni_edita_presupuesto_ajeno(
    escenario: SimpleNamespace,
) -> None:
    """Crear versión y editar ítems exigen la orden asignada (§4.4)."""

    detalle = _presupuesto_admin(escenario)
    presupuesto_id = detalle["presupuesto_id"]

    nueva = _versiones(
        escenario, presupuesto_id, usuario_id=77, roles=NombreRol.MECANICO
    )
    assert nueva.status_code == 404
    # No revela la orden ni su existencia: solo que el presupuesto no está
    # disponible para el mecánico (misma respuesta que para el cliente ajeno).
    assert nueva.json()["detail"] == f"Presupuesto {presupuesto_id} no existe"

    items = _reemplazar_items(
        escenario, presupuesto_id, 1, usuario_id=77, roles=NombreRol.MECANICO
    )
    assert items.status_code == 404
    assert items.json()["detail"] == f"Presupuesto {presupuesto_id} no existe"


def test_mecanico_asignado_versiona_presupuesto_de_su_orden(
    escenario: SimpleNamespace,
) -> None:
    """Con la asignación vigente, el mecánico crea la versión siguiente (§4.4)."""

    assert _asignar_mecanico(
        escenario, 77, usuario_id=99, roles=NombreRol.ADMINISTRADOR
    ).status_code == 200
    detalle = _presupuesto_admin(escenario)
    presupuesto_id = detalle["presupuesto_id"]

    # No puede haber un borrador abierto: el admin congela la versión 1
    # enviándola al cliente antes de que el mecánico proponga la 2.
    enviada = escenario.ms3.post(
        f"/presupuestos/{presupuesto_id}/versiones/1/envio",
        headers=_cabeceras(99, NombreRol.ADMINISTRADOR),
    )
    assert enviada.status_code == 200, enviada.text

    nueva = _versiones(
        escenario, presupuesto_id, usuario_id=77, roles=NombreRol.MECANICO
    )

    assert nueva.status_code == 201, nueva.text
    assert nueva.json()["orden_id"] == escenario.orden_id
    assert len(nueva.json()["versiones"]) == 2
