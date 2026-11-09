"""Regresión de roles, propiedad y asignaciones usando MS1, MS2 y MS3 reales.

Cada API usa su propia base SQLite; el transporte HTTP se dirige a TestClient.
Los cuatro defectos originalmente registrados como xfail ahora se exigen como
rechazos 422 (destino de asignación) y 404 (orden de presupuesto no autorizada).
También se comprueba 503 sin escrituras ante una caída del servicio consultado.
Locks, triggers y concurrencia PostgreSQL se verifican en sus suites específicas.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
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
from services.ms1_auth.config import settings as settings_ms1  # noqa: E402
from services.ms1_auth.db import get_db as get_db_ms1  # noqa: E402
from services.ms1_auth.main import app as app_ms1  # noqa: E402
from services.ms1_auth.models import Rol, Usuario, UsuarioRol  # noqa: E402
from services.ms2_taller.db import get_db as get_db_ms2  # noqa: E402
from services.ms2_taller.main import app as app_ms2  # noqa: E402
from services.ms2_taller.models import (  # noqa: E402
    Base as BaseMS2, Cliente, ConfiguracionCapacidadMecanico, EstadoOrden,
    IngresoVehiculo, OrdenTrabajo, Vehiculo,
)
from services.ms2_taller.models.estado_orden import ESTADOS_ORDEN, RECIBIDO  # noqa: E402
from services.ms3_presupuestos.config import settings as settings_ms3  # noqa: E402
from services.ms3_presupuestos.db import get_db as get_db_ms3  # noqa: E402
from services.ms3_presupuestos.main import app as app_ms3  # noqa: E402
from services.ms3_presupuestos.models import (  # noqa: E402
    Base as BaseMS3, Proveedor, Repuesto,
)
from shared.auth import NombreRol, crear_token_acceso  # noqa: E402


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


@pytest.fixture
def escenario(monkeypatch: pytest.MonkeyPatch, db: Session) -> SimpleNamespace:
    """Tres APIs reales con bases separadas; solo se reemplaza el transporte HTTP."""

    sesion_ms1 = db
    roles = {rol.nombre: rol for rol in db.scalars(select(Rol))}
    for usuario_id, rol, activo in [
        (42, NombreRol.CLIENTE, True), (77, NombreRol.MECANICO, True),
        (78, NombreRol.MECANICO, False), (99, NombreRol.ADMINISTRADOR, True),
    ]:
        usuario = Usuario(
            usuario_id=usuario_id, correo=f"cuenta{usuario_id}@example.test",
            nombre="Cuenta de prueba", contrasena_hash="hash-no-utilizado-en-esta-prueba",
            activo=activo,
        )
        usuario.roles = [UsuarioRol(rol=roles[rol.value])]
        db.add(usuario)
    db.commit()

    engine2, fabrica2 = _base_aislada(BaseMS2)
    engine3, fabrica3 = _base_aislada(BaseMS3)

    with fabrica2() as db:
        db.add_all(
            [EstadoOrden(estado_codigo=codigo, nombre=nombre)
             for codigo, nombre in ESTADOS_ORDEN.items()]
        )
        # La configuración evita que las pruebas de autorización pasen por el
        # error de capacidad no configurada, ajeno a los permisos evaluados.
        db.add(ConfiguracionCapacidadMecanico(
            configuracion_id=1, max_ordenes_activas=5, actualizado_por_id=99,
        ))
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
    monkeypatch.setattr(settings_ms1, "JWT_SECRET_KEY", settings_ms2.JWT_SECRET_KEY)
    monkeypatch.setattr(settings_ms2, "MS1_URL", "http://ms1-prueba")
    monkeypatch.setattr(settings_ms3, "MS2_URL", "http://ms2-prueba")
    app_ms1.dependency_overrides[get_db_ms1] = lambda: sesion_ms1
    app_ms2.dependency_overrides[get_db_ms2] = _sesion_por_peticion(fabrica2)
    app_ms3.dependency_overrides[get_db_ms3] = _sesion_por_peticion(fabrica3)
    fallos = {"ms1": False, "ms2": False}
    llamadas = []
    with TestClient(app_ms1) as ms1, TestClient(app_ms2) as ms2, TestClient(app_ms3) as ms3:
        def get(url, *, headers, timeout):
            llamadas.append((url, headers, timeout))
            for nombre, cliente in [("ms1", ms1), ("ms2", ms2)]:
                base = f"http://{nombre}-prueba"
                if url.startswith(base + "/"):
                    if fallos[nombre]:
                        raise httpx.ConnectError("Servicio simulado caído")
                    respuesta = cliente.get(url.removeprefix(base), headers=headers)
                    if nombre == "ms1":
                        assert respuesta.status_code in (200, 404), respuesta.json()
                    return respuesta
            raise AssertionError(f"Destino HTTP inesperado: {url}")

        monkeypatch.setattr(httpx, "get", get)
        yield SimpleNamespace(ms2=ms2, ms3=ms3, orden_id=orden_id,
                              repuesto_id=repuesto_id,
                              db2=fabrica2, db3=fabrica3, fallos=fallos, llamadas=llamadas)

    app_ms1.dependency_overrides.pop(get_db_ms1, None)
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
# Defectos corregidos: regresiones obligatorias
# ---------------------------------------------------------------------------


def test_mecanico_no_asignado_no_crea_presupuesto_de_orden_ajena(
    escenario: SimpleNamespace,
) -> None:
    """Un mecánico no debe crear presupuesto de una orden que no atiende.

    MS3 consulta la orden a MS2 con el JWT original antes de persistir.
    """

    respuesta = _crear_presupuesto(escenario, usuario_id=77, roles=NombreRol.MECANICO)

    assert respuesta.status_code == 404, (
        f"Un mecánico creó presupuesto de una orden que no atiende: {respuesta.status_code}"
    )


def test_mecanico_no_crea_presupuesto_de_orden_inexistente(
    escenario: SimpleNamespace,
) -> None:
    """MS3 guarda `orden_id` como referencia lógica sin comprobarla (§8).

    La validación por API evita guardar una referencia inexistente.
    """

    respuesta = _crear_presupuesto(
        escenario, orden_id=999999, usuario_id=77, roles=NombreRol.MECANICO
    )

    assert respuesta.status_code == 404, (
        f"Se creó presupuesto para la orden inexistente 999999: {respuesta.status_code}"
    )


def test_administrador_no_asigna_a_un_usuario_inexistente(
    escenario: SimpleNamespace,
) -> None:
    """MS1 responde 404 y MS2 rechaza el destino con 422."""

    respuesta = _asignar_mecanico(
        escenario, 12345, usuario_id=99, roles=NombreRol.ADMINISTRADOR
    )

    assert respuesta.status_code == 422, (
        f"Se asignó como mecánico al usuario inexistente 12345: {respuesta.status_code}"
    )


def test_administrador_no_asigna_a_un_usuario_sin_rol_mecanico(
    escenario: SimpleNamespace,
) -> None:
    """La cuenta 42 es propietaria del vehículo (rol cliente), no mecánica."""

    respuesta = _asignar_mecanico(
        escenario, 42, usuario_id=99, roles=NombreRol.ADMINISTRADOR
    )

    assert respuesta.status_code == 422, (
        f"Se asignó como mecánico a la cuenta 42 (rol cliente): {respuesta.status_code}"
    )


def _datos_guardados(escenario):
    """Incluye órdenes, historial, outbox, capacidad y las tres tablas de presupuesto."""
    datos = []
    for fabrica, base in [(escenario.db2, BaseMS2), (escenario.db3, BaseMS3)]:
        with fabrica() as db:
            for tabla in sorted(base.metadata.tables.values(), key=lambda t: t.name):
                filas = db.execute(select(tabla).order_by(*tabla.primary_key.columns)).all()
                datos.append((tabla.name, [tuple(fila) for fila in filas]))
    return datos


@pytest.mark.parametrize("mecanico_id", [12345, 42, 78])
def test_destino_invalido_no_deja_escrituras(escenario, mecanico_id):
    antes = _datos_guardados(escenario)
    r = _asignar_mecanico(escenario, mecanico_id, usuario_id=99, roles=NombreRol.ADMINISTRADOR)
    assert r.status_code == 422
    assert _datos_guardados(escenario) == antes
    assert escenario.llamadas[0][1] == _cabeceras(99, NombreRol.ADMINISTRADOR)


def test_ms1_caido_no_modifica_reasignacion_ni_historial(escenario):
    assert _asignar_mecanico(escenario, 77, usuario_id=99,
                            roles=NombreRol.ADMINISTRADOR).status_code == 200
    antes = _datos_guardados(escenario)
    escenario.fallos["ms1"] = True
    r = _asignar_mecanico(escenario, 78, usuario_id=99, roles=NombreRol.ADMINISTRADOR)
    assert r.status_code == 503
    assert _datos_guardados(escenario) == antes


@pytest.mark.parametrize("rol", [NombreRol.MECANICO, NombreRol.ADMINISTRADOR])
def test_ms2_caido_no_crea_presupuesto(escenario, rol):
    antes = _datos_guardados(escenario)
    escenario.fallos["ms2"] = True
    r = _crear_presupuesto(escenario, usuario_id=77, roles=rol)
    assert r.status_code == 503
    assert _datos_guardados(escenario) == antes


@pytest.mark.parametrize("roles", [NombreRol.MECANICO, NombreRol.ADMINISTRADOR,
                                   (NombreRol.CLIENTE, NombreRol.MECANICO)])
def test_orden_inexistente_no_deja_presupuesto(escenario, roles):
    antes = _datos_guardados(escenario)
    r = _crear_presupuesto(escenario, orden_id=999999, usuario_id=77, roles=roles)
    assert r.status_code == 404
    assert _datos_guardados(escenario) == antes


def test_cliente_mecanico_propietario_sin_asignacion_no_crea_presupuesto(escenario):
    antes = _datos_guardados(escenario)
    r = _crear_presupuesto(escenario, usuario_id=42,
                           roles=(NombreRol.CLIENTE, NombreRol.MECANICO))
    assert r.status_code == 404  # MS2 sí muestra su orden; MS3 exige además asignación.
    assert _datos_guardados(escenario) == antes


def test_mecanico_asignado_crea_presupuesto_con_su_identidad(escenario):
    assert _asignar_mecanico(escenario, 77, usuario_id=99,
                            roles=NombreRol.ADMINISTRADOR).status_code == 200
    r = _crear_presupuesto(escenario, usuario_id=77, roles=NombreRol.MECANICO)
    assert r.status_code == 201
    assert r.json()["versiones"][0]["creado_por_id"] == 77
    assert escenario.llamadas[-1][1] == _cabeceras(77, NombreRol.MECANICO)


@pytest.mark.parametrize("asignada", [False, True])
def test_administrador_crea_presupuesto_sin_exigir_asignacion_propia(escenario, asignada):
    if asignada:
        assert _asignar_mecanico(escenario, 77, usuario_id=99,
                                roles=NombreRol.ADMINISTRADOR).status_code == 200
    r = _crear_presupuesto(escenario, usuario_id=99,
                           roles=(NombreRol.ADMINISTRADOR, NombreRol.MECANICO))
    assert r.status_code == 201


def test_rol_insuficiente_no_consulta_servicios_externos(escenario):
    assert _crear_presupuesto(escenario, usuario_id=42, roles=NombreRol.CLIENTE).status_code == 403
    assert _asignar_mecanico(escenario, 77, usuario_id=77,
                            roles=NombreRol.MECANICO).status_code == 403
    assert escenario.llamadas == []


# ---------------------------------------------------------------------------
# Alcance de inventario y versiones (§4.4): mecánico = solo órdenes asignadas
# ---------------------------------------------------------------------------


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


def _presupuesto_admin(escenario: SimpleNamespace) -> dict:
    """Presupuesto versión 1 creado por el Administrador sobre la orden viva."""

    creada = _crear_presupuesto(escenario, usuario_id=99, roles=NombreRol.ADMINISTRADOR)
    assert creada.status_code == 201, creada.text
    return creada.json()


def test_mecanico_no_asignado_no_registra_compromiso_de_stock_ajeno(
    escenario: SimpleNamespace,
) -> None:
    """El stock se mueve solo desde órdenes que el mecánico tiene asignadas (§4.4)."""

    respuesta = _registrar_movimiento(escenario, usuario_id=77, roles=NombreRol.MECANICO)

    assert respuesta.status_code == 404
    assert respuesta.json()["detail"] == f"Orden {escenario.orden_id} no existe"


def test_mecanico_asignado_registra_compromiso_de_su_orden(
    escenario: SimpleNamespace,
) -> None:
    """La regla de §4.4 no bloquea al mecánico con la orden asignada."""

    assert _asignar_mecanico(escenario, 77, usuario_id=99,
                             roles=NombreRol.ADMINISTRADOR).status_code == 200

    respuesta = _registrar_movimiento(
        escenario, clave="clv-asignada-01", usuario_id=77, roles=NombreRol.MECANICO
    )

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["movimiento"]["orden_id"] == escenario.orden_id


def test_compromiso_sin_ms2_no_se_aplica_responde_503(
    escenario: SimpleNamespace,
) -> None:
    """Sin poder validar la orden en MS2, el stock no se toca (fail-closed)."""

    antes = _datos_guardados(escenario)
    escenario.fallos["ms2"] = True

    respuesta = _registrar_movimiento(escenario, usuario_id=77, roles=NombreRol.MECANICO)

    assert respuesta.status_code == 503
    assert _datos_guardados(escenario) == antes


def test_mecanico_no_asignado_no_versiona_ni_edita_presupuesto_ajeno(
    escenario: SimpleNamespace,
) -> None:
    """Crear versión y editar ítems exigen la orden asignada (§4.4)."""

    presupuesto_id = _presupuesto_admin(escenario)["presupuesto_id"]

    nueva = _versiones(escenario, presupuesto_id, usuario_id=77, roles=NombreRol.MECANICO)
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

    assert _asignar_mecanico(escenario, 77, usuario_id=99,
                             roles=NombreRol.ADMINISTRADOR).status_code == 200
    detalle = _presupuesto_admin(escenario)
    presupuesto_id = detalle["presupuesto_id"]

    # No puede haber un borrador abierto: el admin congela la versión 1
    # enviándola al cliente antes de que el mecánico proponga la 2. En un
    # despliegue completo MS3 confirma el efecto en MS2; aquí solo se simula
    # el transporte GET, así que esa confirmación puede responder 503, pero
    # la versión ya queda enviada (`envio_confirmado: true`).
    enviada = escenario.ms3.post(
        f"/presupuestos/{presupuesto_id}/versiones/1/envio",
        headers=_cabeceras(99, NombreRol.ADMINISTRADOR),
    )
    if enviada.status_code == 503:
        assert enviada.json()["envio_confirmado"] is True
    else:
        assert enviada.status_code == 200, enviada.text

    nueva = _versiones(escenario, presupuesto_id, usuario_id=77, roles=NombreRol.MECANICO)

    assert nueva.status_code == 201, nueva.text
    assert nueva.json()["orden_id"] == escenario.orden_id
    assert len(nueva.json()["versiones"]) == 2
