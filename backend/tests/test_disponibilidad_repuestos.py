"""Pruebas de stock libre y compromisos para continuar una orden."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import Base
from services.ms3_presupuestos.db import get_db
from services.ms3_presupuestos.integracion_ms2 import (
    obtener_coordinador_disponibilidad_repuestos,
    ReservaRepuestosNoAplicableError,
)
from services.ms3_presupuestos.main import app
from services.ms3_presupuestos.models import (
    DecisionPresupuesto,
    ItemPresupuesto,
    MovimientoInventario,
    Presupuesto,
    Proveedor,
    Repuesto,
    VersionPresupuesto,
)
from services.ms3_presupuestos.persistencia import UnidadDeTrabajo
from services.ms3_presupuestos.persistencia.errores import ReglaDeDatosViolada
from services.ms3_presupuestos.persistencia.errores import ConflictoDeDatos
from services.ms3_presupuestos.services.disponibilidad_repuestos import (
    RepuestosInsuficientesError,
    reservar_repuestos_aprobados,
    verificar_reserva_confirmada,
    revertir_reserva_rechazada,
)
from shared.auth import NombreRol, crear_token_acceso
from shared.contratos_decisiones import AplicacionDisponibilidadRepuestosRespuesta


@pytest.fixture
def db_disponibilidad():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def registrar_funciones_sqlite(conexion, _registro) -> None:
        conexion.create_function(
            "btrim", 1, lambda valor: valor.strip() if valor is not None else None
        )
        conexion.create_function(
            "char_length", 1, lambda valor: len(valor) if valor is not None else None
        )

    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def _presupuesto_aprobado(
    db: Session, *, orden_id: int, repuesto: Repuesto, cantidad: Decimal,
) -> Presupuesto:
    version = VersionPresupuesto(
        numero=1,
        creado_por_id=80,
        creado_en=datetime.now(timezone.utc),
        enviado_en=datetime.now(timezone.utc),
        bloqueada_en=datetime.now(timezone.utc),
    )
    version.items.append(ItemPresupuesto(
        tipo="repuesto",
        repuesto=repuesto,
        descripcion=repuesto.nombre,
        cantidad=cantidad,
        precio_unitario=Decimal("1000.00"),
    ))
    presupuesto = Presupuesto(orden_id=orden_id, versiones=[version])
    version.decision = DecisionPresupuesto(
        cliente_usuario_id=orden_id + 100,
        decision="aprobado",
        repuestos_disponibles=False,
    )
    db.add(presupuesto)
    db.commit()
    return presupuesto


def test_reserva_solo_stock_libre_y_reintento_idempotente(
    db_disponibilidad: Session,
) -> None:
    proveedor = Proveedor(nombre="Proveedor de prueba", contacto="contacto")
    repuesto = Repuesto(nombre="Pastilla", stock=5, proveedor=proveedor)
    db_disponibilidad.add(proveedor)
    db_disponibilidad.flush()
    _presupuesto_aprobado(
        db_disponibilidad, orden_id=9001, repuesto=repuesto, cantidad=Decimal("4.00")
    )
    db_disponibilidad.add(MovimientoInventario(
        clave_operacion="otra-orden-reserva",
        repuesto=repuesto,
        orden_id=9002,
        tipo="compromiso",
        cantidad=2,
        registrado_por_id=80,
    ))
    db_disponibilidad.commit()
    uow = UnidadDeTrabajo(db_disponibilidad)

    with pytest.raises(RepuestosInsuficientesError) as error:
        reservar_repuestos_aprobados(uow, orden_id=9001, actor_usuario_id=99)
    assert error.value.faltantes == [
        {"repuesto_id": repuesto.repuesto_id, "requerido": 4, "disponible": 3}
    ]
    assert db_disponibilidad.query(MovimientoInventario).filter_by(
        orden_id=9001, tipo="compromiso"
    ).count() == 0

    repuesto.stock = 6
    db_disponibilidad.commit()
    reserva = reservar_repuestos_aprobados(
        uow, orden_id=9001, actor_usuario_id=99
    )
    otra_vez = reservar_repuestos_aprobados(
        uow, orden_id=9001, actor_usuario_id=99
    )
    assert reserva == otra_vez
    assert reserva["clave_operacion"] == "disp:9001:1"
    assert verificar_reserva_confirmada(
        uow, orden_id=9001, clave_operacion="disp:9001:1"
    )["reserva_confirmada"] is True
    compromisos = db_disponibilidad.query(MovimientoInventario).filter_by(
        orden_id=9001, tipo="compromiso"
    ).all()
    assert len(compromisos) == 1
    assert compromisos[0].cantidad == 4


def test_reserva_rechaza_cantidad_fraccionaria_de_repuesto(
    db_disponibilidad: Session,
) -> None:
    proveedor = Proveedor(nombre="Proveedor fraccionario", contacto="contacto")
    repuesto = Repuesto(nombre="Aceite", stock=10, proveedor=proveedor)
    db_disponibilidad.add(proveedor)
    db_disponibilidad.flush()
    _presupuesto_aprobado(
        db_disponibilidad, orden_id=9010, repuesto=repuesto, cantidad=Decimal("1.50")
    )

    with pytest.raises(ReglaDeDatosViolada, match="unidades enteras"):
        reservar_repuestos_aprobados(
            UnidadDeTrabajo(db_disponibilidad), orden_id=9010, actor_usuario_id=99
        )


def test_reserva_rechazada_por_ms2_se_libera_con_movimiento_compensatorio(
    db_disponibilidad: Session,
) -> None:
    proveedor = Proveedor(nombre="Proveedor reversa", contacto="contacto")
    repuesto = Repuesto(nombre="Filtro", stock=5, proveedor=proveedor)
    db_disponibilidad.add(proveedor)
    db_disponibilidad.flush()
    _presupuesto_aprobado(
        db_disponibilidad, orden_id=9015, repuesto=repuesto, cantidad=Decimal("2.00")
    )
    uow = UnidadDeTrabajo(db_disponibilidad)
    reserva = reservar_repuestos_aprobados(
        uow, orden_id=9015, actor_usuario_id=99
    )
    revertir_reserva_rechazada(
        uow,
        orden_id=9015,
        clave_operacion=str(reserva["clave_operacion"]),
        actor_usuario_id=99,
    )

    movimientos = db_disponibilidad.query(MovimientoInventario).filter_by(
        orden_id=9015
    ).order_by(MovimientoInventario.movimiento_id).all()
    assert [(m.tipo, m.cantidad) for m in movimientos] == [
        ("compromiso", 2),
        ("liberacion", 2),
    ]
    with pytest.raises(ConflictoDeDatos, match="ya fue liberada"):
        verificar_reserva_confirmada(
            uow,
            orden_id=9015,
            clave_operacion=str(reserva["clave_operacion"]),
        )


def test_endpoint_admin_reserva_y_pide_transicion_a_ms2(
    db_disponibilidad: Session,
) -> None:
    proveedor = Proveedor(nombre="Proveedor API", contacto="contacto")
    repuesto = Repuesto(nombre="Bujía", stock=5, proveedor=proveedor)
    db_disponibilidad.add(proveedor)
    db_disponibilidad.flush()
    presupuesto = _presupuesto_aprobado(
        db_disponibilidad, orden_id=9020, repuesto=repuesto, cantidad=Decimal("2.00")
    )
    clave = f"disp:9020:{presupuesto.versiones[0].version_id}"
    llamadas: list[tuple[int, str, str]] = []

    class CoordinadorFalso:
        def aplicar(self, orden_id: int, clave_operacion: str, token: str):
            llamadas.append((orden_id, clave_operacion, token))
            return AplicacionDisponibilidadRepuestosRespuesta(
                clave_operacion=clave_operacion,
                orden_id=orden_id,
                estado_aplicado=5,
                historial_id=123,
            )

    def reemplazar_db():
        yield db_disponibilidad

    app.dependency_overrides[get_db] = reemplazar_db
    app.dependency_overrides[
        obtener_coordinador_disponibilidad_repuestos
    ] = lambda: CoordinadorFalso()
    token = crear_token_acceso(
        99,
        [NombreRol.ADMINISTRADOR],
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(),
        algoritmo=settings.JWT_ALGORITHM,
    )
    try:
        with TestClient(app) as client:
            respuesta = client.post(
                "/inventario/ordenes/9020/disponibilidad",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert respuesta.status_code == 200
    assert respuesta.json()["clave_operacion"] == clave
    assert respuesta.json()["repuestos"] == [
        {"repuesto_id": repuesto.repuesto_id, "cantidad": 2}
    ]
    assert llamadas == [(9020, clave, token)]


def test_endpoint_libera_compromiso_si_ms2_rechaza_definitivamente(
    db_disponibilidad: Session,
) -> None:
    proveedor = Proveedor(nombre="Proveedor rechazo", contacto="contacto")
    repuesto = Repuesto(nombre="Batería", stock=4, proveedor=proveedor)
    db_disponibilidad.add(proveedor)
    db_disponibilidad.flush()
    _presupuesto_aprobado(
        db_disponibilidad, orden_id=9030, repuesto=repuesto, cantidad=Decimal("1.00")
    )

    class CoordinadorFalso:
        def aplicar(self, _orden_id: int, _clave_operacion: str, _token: str):
            raise ReservaRepuestosNoAplicableError(409)

    def reemplazar_db():
        yield db_disponibilidad

    app.dependency_overrides[get_db] = reemplazar_db
    app.dependency_overrides[
        obtener_coordinador_disponibilidad_repuestos
    ] = lambda: CoordinadorFalso()
    token = crear_token_acceso(
        99,
        [NombreRol.ADMINISTRADOR],
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(),
        algoritmo=settings.JWT_ALGORITHM,
    )
    try:
        with TestClient(app) as client:
            respuesta = client.post(
                "/inventario/ordenes/9030/disponibilidad",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert respuesta.status_code == 409
    movimientos = db_disponibilidad.query(MovimientoInventario).filter_by(
        orden_id=9030
    ).order_by(MovimientoInventario.movimiento_id).all()
    assert [m.tipo for m in movimientos] == ["compromiso", "liberacion"]
