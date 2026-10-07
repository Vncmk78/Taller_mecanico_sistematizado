"""Pruebas HTTP de creación y visibilidad inicial de órdenes de trabajo."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from services.ms2_taller.config import settings
from services.ms2_taller.db import get_db
from services.ms2_taller.main import app
from services.ms2_taller.models import (
    Base,
    Cliente,
    EstadoOrden,
    HistorialEstado,
    IngresoVehiculo,
    OrdenTrabajo,
    Vehiculo,
)
from services.ms2_taller.models.estado_orden import ESTADOS_ORDEN, RECIBIDO
from services.ms2_taller.services.ordenes import (
    _consulta_vehiculo_para_actualizacion,
)
from shared.auth import NombreRol, crear_token_acceso


@pytest.fixture
def db_ordenes() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def registrar_funciones_sqlite(conexion, _registro) -> None:
        conexion.create_function(
            "btrim",
            1,
            lambda valor: valor.strip() if valor is not None else None,
        )
        conexion.create_function(
            "char_length",
            1,
            lambda valor: len(valor) if valor is not None else None,
        )

    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)
    sesion = fabrica()
    sesion.add_all(
        [
            EstadoOrden(estado_codigo=codigo, nombre=nombre)
            for codigo, nombre in ESTADOS_ORDEN.items()
        ]
    )
    sesion.commit()
    try:
        yield sesion
    finally:
        sesion.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def api_ordenes(db_ordenes: Session) -> Generator[TestClient, None, None]:
    def reemplazar_db():
        yield db_ordenes

    app.dependency_overrides[get_db] = reemplazar_db
    with TestClient(app) as cliente_http:
        yield cliente_http
    app.dependency_overrides.clear()


def test_post_administrador_crea_orden_inicial_completa(
    api_ordenes: TestClient,
    db_ordenes: Session,
):
    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)

    respuesta = api_ordenes.post(
        "/ordenes",
        json={"vehiculo_id": vehiculo.vehiculo_id},
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["vehiculo_id"] == vehiculo.vehiculo_id
    assert datos["estado_codigo"] == RECIBIDO
    assert datos["mecanico_actual_id"] is None
    assert datos["creado_por_id"] == 99

    orden = db_ordenes.scalar(select(OrdenTrabajo))
    ingreso = db_ordenes.scalar(select(IngresoVehiculo))
    historial = db_ordenes.scalar(select(HistorialEstado))
    assert orden is not None
    assert ingreso is not None
    assert historial is not None
    assert orden.ingreso_id == ingreso.ingreso_id
    assert ingreso.vehiculo_id == vehiculo.vehiculo_id
    assert ingreso.registrado_por_id == 99
    assert ingreso.fecha_hora is not None
    assert historial.orden_id == orden.orden_id
    assert historial.estado_anterior is None
    assert historial.estado_nuevo == RECIBIDO
    assert historial.actor_usuario_id == 99
    assert historial.origen == "usuario"


def test_post_reutiliza_ingreso_abierto(
    api_ordenes: TestClient,
    db_ordenes: Session,
):
    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)
    ingreso = IngresoVehiculo(
        vehiculo_id=vehiculo.vehiculo_id,
        registrado_por_id=80,
    )
    db_ordenes.add(ingreso)
    db_ordenes.commit()

    respuesta = api_ordenes.post(
        "/ordenes",
        json={"vehiculo_id": vehiculo.vehiculo_id},
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["ingreso_id"] == ingreso.ingreso_id
    assert db_ordenes.scalar(select(func.count()).select_from(IngresoVehiculo)) == 1


def test_post_no_reutiliza_ingreso_cerrado(
    api_ordenes: TestClient,
    db_ordenes: Session,
):
    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)
    ahora = datetime.now(timezone.utc)
    ingreso_cerrado = IngresoVehiculo(
        vehiculo_id=vehiculo.vehiculo_id,
        fecha_hora=ahora - timedelta(hours=1),
        salida_en=ahora,
        registrado_por_id=80,
    )
    db_ordenes.add(ingreso_cerrado)
    db_ordenes.commit()

    respuesta = api_ordenes.post(
        "/ordenes",
        json={"vehiculo_id": vehiculo.vehiculo_id},
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["ingreso_id"] != ingreso_cerrado.ingreso_id
    assert db_ordenes.scalar(select(func.count()).select_from(IngresoVehiculo)) == 2
    ingreso_abierto = db_ordenes.scalar(
        select(IngresoVehiculo).where(IngresoVehiculo.salida_en.is_(None))
    )
    assert ingreso_abierto is not None
    assert respuesta.json()["ingreso_id"] == ingreso_abierto.ingreso_id


def test_post_multirol_con_administrador_puede_crear(
    api_ordenes: TestClient,
    db_ordenes: Session,
):
    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)

    respuesta = api_ordenes.post(
        "/ordenes",
        json={"vehiculo_id": vehiculo.vehiculo_id},
        headers=_headers_para(
            99,
            NombreRol.CLIENTE,
            NombreRol.ADMINISTRADOR,
        ),
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["creado_por_id"] == 99


@pytest.mark.parametrize("rol", [NombreRol.CLIENTE, NombreRol.MECANICO])
def test_post_usuario_no_administrador_recibe_403(
    api_ordenes: TestClient,
    db_ordenes: Session,
    rol: NombreRol,
):
    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)

    respuesta = api_ordenes.post(
        "/ordenes",
        json={"vehiculo_id": vehiculo.vehiculo_id},
        headers=_headers_para(10, rol),
    )

    assert respuesta.status_code == 403
    assert db_ordenes.scalar(select(func.count()).select_from(OrdenTrabajo)) == 0


def test_post_sin_token_devuelve_401(api_ordenes: TestClient):
    respuesta = api_ordenes.post("/ordenes", json={"vehiculo_id": 1})

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("vehiculo_id", [0, -1])
def test_post_vehiculo_id_invalido_devuelve_422_sin_escrituras(
    api_ordenes: TestClient,
    db_ordenes: Session,
    vehiculo_id: int,
):
    respuesta = api_ordenes.post(
        "/ordenes",
        json={"vehiculo_id": vehiculo_id},
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 422
    assert db_ordenes.scalar(select(func.count()).select_from(IngresoVehiculo)) == 0
    assert db_ordenes.scalar(select(func.count()).select_from(OrdenTrabajo)) == 0
    assert (
        db_ordenes.scalar(select(func.count()).select_from(HistorialEstado))
        == 0
    )


def test_post_vehiculo_inexistente_devuelve_404(
    api_ordenes: TestClient,
    db_ordenes: Session,
):
    respuesta = api_ordenes.post(
        "/ordenes",
        json={"vehiculo_id": 999},
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Vehículo no encontrado"}
    assert db_ordenes.scalar(select(func.count()).select_from(IngresoVehiculo)) == 0


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("estado_codigo", 2),
        ("creado_por_id", 7),
        ("mecanico_actual_id", 8),
        ("historial", []),
        ("ingreso_id", 123),
    ],
)
def test_post_rechaza_campos_controlados_por_el_servidor(
    api_ordenes: TestClient,
    db_ordenes: Session,
    campo: str,
    valor: object,
):
    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)

    respuesta = api_ordenes.post(
        "/ordenes",
        json={"vehiculo_id": vehiculo.vehiculo_id, campo: valor},
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 422
    assert db_ordenes.scalar(select(func.count()).select_from(OrdenTrabajo)) == 0


def test_post_fallo_en_historial_hace_rollback_completo(
    api_ordenes: TestClient,
    db_ordenes: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)
    flush_real = db_ordenes.flush
    llamadas = 0

    def fallar_tercer_flush(*args, **kwargs) -> None:
        nonlocal llamadas
        llamadas += 1
        if llamadas == 3:
            raise SQLAlchemyError("fallo simulado al crear historial")
        flush_real(*args, **kwargs)

    monkeypatch.setattr(db_ordenes, "flush", fallar_tercer_flush)

    respuesta = api_ordenes.post(
        "/ordenes",
        json={"vehiculo_id": vehiculo.vehiculo_id},
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 500
    monkeypatch.setattr(db_ordenes, "flush", flush_real)
    assert db_ordenes.scalar(select(func.count()).select_from(IngresoVehiculo)) == 0
    assert db_ordenes.scalar(select(func.count()).select_from(OrdenTrabajo)) == 0
    assert db_ordenes.scalar(select(func.count()).select_from(HistorialEstado)) == 0


def test_consulta_de_vehiculo_usa_for_update_en_postgresql():
    consulta = _consulta_vehiculo_para_actualizacion(123)

    sql = " ".join(
        str(
            consulta.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).split()
    )

    assert "WHERE vehiculo.vehiculo_id = 123" in sql
    assert sql.endswith("FOR UPDATE")


def test_get_administrador_ve_todas_las_ordenes(
    api_ordenes: TestClient,
    db_ordenes: Session,
):
    orden_a = _crear_orden(db_ordenes, usuario_cliente=10)
    orden_b = _crear_orden(db_ordenes, usuario_cliente=20)

    respuesta = api_ordenes.get(
        "/ordenes",
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 200
    assert _ids(respuesta.json()) == [orden_a.orden_id, orden_b.orden_id]


def test_get_cliente_ve_solo_ordenes_de_sus_vehiculos(
    api_ordenes: TestClient,
    db_ordenes: Session,
):
    propia = _crear_orden(db_ordenes, usuario_cliente=10)
    _crear_orden(db_ordenes, usuario_cliente=20)

    respuesta = api_ordenes.get(
        "/ordenes",
        headers=_headers_para(10, NombreRol.CLIENTE),
    )

    assert respuesta.status_code == 200
    assert _ids(respuesta.json()) == [propia.orden_id]


def test_get_mecanico_ve_solo_ordenes_asignadas(
    api_ordenes: TestClient,
    db_ordenes: Session,
):
    asignada = _crear_orden(db_ordenes, usuario_cliente=10, mecanico_id=50)
    _crear_orden(db_ordenes, usuario_cliente=20, mecanico_id=60)
    _crear_orden(db_ordenes, usuario_cliente=30)

    respuesta = api_ordenes.get(
        "/ordenes",
        headers=_headers_para(50, NombreRol.MECANICO),
    )

    assert respuesta.status_code == 200
    assert _ids(respuesta.json()) == [asignada.orden_id]


def test_get_multirol_une_alcances_sin_duplicados(
    api_ordenes: TestClient,
    db_ordenes: Session,
):
    propia = _crear_orden(db_ordenes, usuario_cliente=10)
    asignada = _crear_orden(db_ordenes, usuario_cliente=20, mecanico_id=10)
    ambos = _crear_orden(db_ordenes, usuario_cliente=10, mecanico_id=10)
    _crear_orden(db_ordenes, usuario_cliente=30, mecanico_id=30)

    respuesta = api_ordenes.get(
        "/ordenes",
        headers=_headers_para(10, NombreRol.CLIENTE, NombreRol.MECANICO),
    )

    assert respuesta.status_code == 200
    ids = _ids(respuesta.json())
    assert ids == [propia.orden_id, asignada.orden_id, ambos.orden_id]
    assert len(ids) == len(set(ids))


def test_get_administrador_multirol_mantiene_acceso_global(
    api_ordenes: TestClient,
    db_ordenes: Session,
):
    ordenes = [
        _crear_orden(db_ordenes, usuario_cliente=10),
        _crear_orden(db_ordenes, usuario_cliente=20),
        _crear_orden(db_ordenes, usuario_cliente=30),
    ]

    respuesta = api_ordenes.get(
        "/ordenes",
        headers=_headers_para(
            10,
            NombreRol.CLIENTE,
            NombreRol.MECANICO,
            NombreRol.ADMINISTRADOR,
        ),
    )

    assert respuesta.status_code == 200
    assert _ids(respuesta.json()) == [orden.orden_id for orden in ordenes]


def test_get_detalle_administrador_accede(
    api_ordenes: TestClient,
    db_ordenes: Session,
):
    orden = _crear_orden(db_ordenes, usuario_cliente=10)

    respuesta = api_ordenes.get(
        f"/ordenes/{orden.orden_id}",
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["orden_id"] == orden.orden_id


def test_get_detalle_cliente_propietario_accede(
    api_ordenes: TestClient,
    db_ordenes: Session,
):
    orden = _crear_orden(db_ordenes, usuario_cliente=10)

    respuesta = api_ordenes.get(
        f"/ordenes/{orden.orden_id}",
        headers=_headers_para(10, NombreRol.CLIENTE),
    )

    assert respuesta.status_code == 200


def test_get_detalle_cliente_ajeno_recibe_404(
    api_ordenes: TestClient,
    db_ordenes: Session,
):
    orden = _crear_orden(db_ordenes, usuario_cliente=20)

    respuesta = api_ordenes.get(
        f"/ordenes/{orden.orden_id}",
        headers=_headers_para(10, NombreRol.CLIENTE),
    )

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Orden no encontrada"}


def test_get_detalle_mecanico_asignado_accede(
    api_ordenes: TestClient,
    db_ordenes: Session,
):
    orden = _crear_orden(db_ordenes, usuario_cliente=10, mecanico_id=50)

    respuesta = api_ordenes.get(
        f"/ordenes/{orden.orden_id}",
        headers=_headers_para(50, NombreRol.MECANICO),
    )

    assert respuesta.status_code == 200


def test_get_detalle_mecanico_no_asignado_recibe_404(
    api_ordenes: TestClient,
    db_ordenes: Session,
):
    orden = _crear_orden(db_ordenes, usuario_cliente=10, mecanico_id=60)

    respuesta = api_ordenes.get(
        f"/ordenes/{orden.orden_id}",
        headers=_headers_para(50, NombreRol.MECANICO),
    )

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Orden no encontrada"}


def test_get_detalle_inexistente_devuelve_el_mismo_404(
    api_ordenes: TestClient,
):
    respuesta = api_ordenes.get(
        "/ordenes/999",
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Orden no encontrada"}



def test_historial_completo_campos_cronologia_y_aislamiento(
    api_ordenes: TestClient, db_ordenes: Session, monkeypatch: pytest.MonkeyPatch,
):
    orden = _crear_orden(db_ordenes, usuario_cliente=10)
    otra = _crear_orden(db_ordenes, usuario_cliente=20)
    fecha = datetime(2030, 1, 1, tzinfo=timezone.utc)
    db_ordenes.add_all([
        HistorialEstado(
            historial_id=5, orden_id=orden.orden_id,
            estado_anterior=2, estado_nuevo=3, actor_usuario_id=99,
            origen="usuario", fecha_hora=fecha + timedelta(hours=1),
            observacion="Presupuesto enviado",
        ),
        HistorialEstado(
            historial_id=20, orden_id=orden.orden_id,
            estado_anterior=1, estado_nuevo=2, actor_usuario_id=None,
            origen="sistema", fecha_hora=fecha, observacion=None,
        ),
        HistorialEstado(
            historial_id=10, orden_id=orden.orden_id,
            estado_anterior=None, estado_nuevo=RECIBIDO, actor_usuario_id=99,
            origen="usuario", fecha_hora=fecha, observacion=None,
        ),
        HistorialEstado(
            historial_id=40, orden_id=otra.orden_id,
            estado_anterior=None, estado_nuevo=RECIBIDO, actor_usuario_id=99,
            origen="usuario", fecha_hora=fecha, observacion=None,
        ),
    ])
    db_ordenes.commit()

    def impedir_commit():
        pytest.fail("La consulta no debe hacer commit")

    monkeypatch.setattr(db_ordenes, "commit", impedir_commit)
    respuesta = api_ordenes.get(
        f"/ordenes/{orden.orden_id}/historial",
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )
    assert respuesta.status_code == 200
    registros = respuesta.json()
    assert [r["historial_id"] for r in registros] == [10, 20, 5]
    campos = {
        "historial_id", "orden_id", "estado_anterior", "estado_nuevo",
        "actor_usuario_id", "fecha_hora", "origen", "observacion",
    }
    for registro in registros:
        assert set(registro) == campos
        assert registro["orden_id"] == orden.orden_id
        datetime.fromisoformat(registro["fecha_hora"])
    assert registros[0]["estado_anterior"] is None
    assert registros[0]["estado_nuevo"] == RECIBIDO
    assert registros[0]["actor_usuario_id"] == 99
    assert registros[0]["origen"] == "usuario"
    assert registros[0]["observacion"] is None
    assert registros[1]["actor_usuario_id"] is None
    assert registros[1]["origen"] == "sistema"
    assert registros[1]["observacion"] is None
    assert registros[2]["estado_anterior"] == 2
    assert registros[2]["estado_nuevo"] == 3
    assert registros[2]["observacion"] == "Presupuesto enviado"
    assert db_ordenes.scalar(select(func.count()).select_from(HistorialEstado)) == 4
    assert not db_ordenes.new and not db_ordenes.dirty and not db_ordenes.deleted


def test_historial_incluye_creacion_y_primera_asignacion(
    api_ordenes: TestClient, db_ordenes: Session,
):
    vehiculo = _crear_vehiculo(db_ordenes, usuario_cliente=10)
    headers = _headers_para(99, NombreRol.ADMINISTRADOR)
    creada = api_ordenes.post(
        "/ordenes", json={"vehiculo_id": vehiculo.vehiculo_id}, headers=headers,
    )
    assert creada.status_code == 201
    orden_id = creada.json()["orden_id"]
    asignada = api_ordenes.put(
        f"/ordenes/{orden_id}/mecanico", json={"mecanico_id": 50}, headers=headers,
    )
    assert asignada.status_code == 200
    respuesta = api_ordenes.get(f"/ordenes/{orden_id}/historial", headers=headers)
    assert respuesta.status_code == 200
    assert [(r["estado_anterior"], r["estado_nuevo"]) for r in respuesta.json()] == [
        (None, 1), (1, 2),
    ]
    assert all(r["actor_usuario_id"] == 99 for r in respuesta.json())


@pytest.mark.parametrize(
    "usuario_id,roles",
    [
        (99, (NombreRol.ADMINISTRADOR,)),
        (10, (NombreRol.CLIENTE,)),
        (50, (NombreRol.MECANICO,)),
        (10, (NombreRol.CLIENTE, NombreRol.MECANICO)),
        (50, (NombreRol.CLIENTE, NombreRol.MECANICO)),
        (99, (NombreRol.ADMINISTRADOR, NombreRol.MECANICO)),
    ],
)
def test_historial_visible_por_rol_y_multirol(
    api_ordenes: TestClient, db_ordenes: Session,
    usuario_id: int, roles: tuple[NombreRol, ...],
):
    orden = _crear_orden(db_ordenes, usuario_cliente=10, mecanico_id=50)
    db_ordenes.add(HistorialEstado(
        orden_id=orden.orden_id, estado_anterior=None, estado_nuevo=RECIBIDO,
        actor_usuario_id=99, origen="usuario",
    ))
    db_ordenes.commit()
    respuesta = api_ordenes.get(
        f"/ordenes/{orden.orden_id}/historial",
        headers=_headers_para(usuario_id, *roles),
    )
    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 1
    assert respuesta.json()[0]["orden_id"] == orden.orden_id


@pytest.mark.parametrize("rol", [NombreRol.CLIENTE, NombreRol.MECANICO])
def test_historial_ajeno_e_inexistente_devuelven_mismo_404(
    api_ordenes: TestClient, db_ordenes: Session, rol: NombreRol,
):
    orden = _crear_orden(db_ordenes, usuario_cliente=10, mecanico_id=50)
    headers = _headers_para(20, rol)
    ajena = api_ordenes.get(f"/ordenes/{orden.orden_id}/historial", headers=headers)
    inexistente = api_ordenes.get("/ordenes/99999/historial", headers=headers)
    assert ajena.status_code == inexistente.status_code == 404
    assert ajena.json() == inexistente.json() == {"detail": "Orden no encontrada"}


def test_historial_inexistente_para_administrador_devuelve_404(api_ordenes: TestClient):
    respuesta = api_ordenes.get(
        "/ordenes/99999/historial", headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )
    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Orden no encontrada"}


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer token-invalido"}])
def test_historial_requiere_jwt(api_ordenes: TestClient, headers: dict[str, str]):
    respuesta = api_ordenes.get("/ordenes/1/historial", headers=headers)
    assert respuesta.status_code == 401


def test_historial_orden_visible_sin_registros_devuelve_lista_vacia(
    api_ordenes: TestClient, db_ordenes: Session,
):
    orden = _crear_orden(db_ordenes, usuario_cliente=10)
    respuesta = api_ordenes.get(
        f"/ordenes/{orden.orden_id}/historial",
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )
    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_historial_identificador_invalido_devuelve_422(api_ordenes: TestClient):
    respuesta = api_ordenes.get(
        "/ordenes/no-es-entero/historial",
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )
    assert respuesta.status_code == 422


@pytest.mark.parametrize("fallar_visibilidad", [False, True])
def test_historial_error_consulta_devuelve_500_y_rollback(
    api_ordenes: TestClient, db_ordenes: Session,
    monkeypatch: pytest.MonkeyPatch, fallar_visibilidad: bool,
):
    orden = _crear_orden(db_ordenes, usuario_cliente=10)
    rollbacks = []
    rollback_real = db_ordenes.rollback

    def registrar_rollback():
        rollbacks.append(True)
        rollback_real()

    def fallar_consulta(*args, **kwargs):
        raise SQLAlchemyError("fallo simulado de consulta")

    monkeypatch.setattr(db_ordenes, "rollback", registrar_rollback)
    monkeypatch.setattr(
        db_ordenes, "scalar" if fallar_visibilidad else "scalars", fallar_consulta,
    )
    respuesta = api_ordenes.get(
        f"/ordenes/{orden.orden_id}/historial",
        headers=_headers_para(99, NombreRol.ADMINISTRADOR),
    )
    assert respuesta.status_code == 500
    assert respuesta.json() == {
        "detail": "No fue posible consultar el historial de la orden",
    }
    assert len(rollbacks) == 1


def _crear_vehiculo(db: Session, usuario_cliente: int) -> Vehiculo:
    cliente = db.scalar(select(Cliente).where(Cliente.usuario_id == usuario_cliente))
    if cliente is None:
        cliente = Cliente(usuario_id=usuario_cliente)
        db.add(cliente)
        db.flush()

    siguiente = db.scalar(select(func.count()).select_from(Vehiculo)) + 1
    vehiculo = Vehiculo(
        cliente_id=cliente.cliente_id,
        patente=f"AA{int(siguiente):04d}",
        marca="Toyota",
        modelo="Yaris",
    )
    db.add(vehiculo)
    db.commit()
    db.refresh(vehiculo)
    return vehiculo


def _crear_orden(
    db: Session,
    usuario_cliente: int,
    mecanico_id: int | None = None,
) -> OrdenTrabajo:
    vehiculo = _crear_vehiculo(db, usuario_cliente)
    ingreso = IngresoVehiculo(
        vehiculo_id=vehiculo.vehiculo_id,
        registrado_por_id=99,
    )
    db.add(ingreso)
    db.flush()
    orden = OrdenTrabajo(
        vehiculo_id=vehiculo.vehiculo_id,
        ingreso_id=ingreso.ingreso_id,
        estado_codigo=RECIBIDO,
        mecanico_actual_id=mecanico_id,
        creado_por_id=99,
    )
    db.add(orden)
    db.commit()
    db.refresh(orden)
    return orden


def _headers_para(usuario_id: int, *roles: NombreRol) -> dict[str, str]:
    token = crear_token_acceso(
        usuario_id,
        roles,
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(),
        algoritmo=settings.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


def _ids(ordenes: list[dict]) -> list[int]:
    return [orden["orden_id"] for orden in ordenes]
