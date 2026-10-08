"""Flujo HTTP MS3–MS2 real con bases separadas, sin servidores externos.

SQLite comprueba contratos, autorización y commits/rollbacks; los triggers y
locks PostgreSQL se verifican en las pruebas ORM de MS3, no se simulan aquí.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.ms2_taller.config import settings as settings_ms2
from services.ms2_taller.db import get_db as get_db_ms2
from services.ms2_taller.main import app as app_ms2
from services.ms2_taller.models import (
    Base as BaseMS2, Cliente, EstadoOrden, HistorialEstado, IngresoVehiculo, OrdenTrabajo, Vehiculo,
)
from services.ms2_taller.models.estado_orden import (
    CANCELADO, EN_REPARACION, ESPERANDO_APROBACION_PRESUPUESTO, ESPERANDO_REPUESTOS,
    ESTADOS_ORDEN, LISTO, RECIBIDO,
)
from services.ms2_taller.services import ordenes as servicio_ordenes
from services.ms3_presupuestos.config import settings as settings_ms3
from services.ms3_presupuestos.db import get_db as get_db_ms3
from services.ms3_presupuestos.main import app as app_ms3
from services.ms3_presupuestos.models import (
    Base as BaseMS3, DecisionPresupuesto, ItemPresupuesto, Presupuesto, Proveedor,
    Repuesto, VersionPresupuesto,
)
from shared.auth import NombreRol, crear_token_acceso


def _base_aislada(base):
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def funciones(conexion, _registro):
        conexion.create_function("btrim", 1, lambda x: x.strip() if x is not None else None)
        conexion.create_function("char_length", 1, lambda x: len(x) if x is not None else None)
        conexion.execute("PRAGMA foreign_keys=ON")

    base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)


def _sesion_por_peticion(fabrica):
    def dependencia():
        with fabrica() as db:
            yield db
    return dependencia


@pytest.fixture
def flujo(monkeypatch):
    yield from preparar_flujo(
        monkeypatch, _base_aislada(BaseMS2), _base_aislada(BaseMS3),
    )


def preparar_flujo(monkeypatch, base2, base3):
    """Comparte el transporte HTTP y los datos entre SQLite y PostgreSQL."""
    engine2, fabrica2 = base2
    engine3, fabrica3 = base3
    with fabrica2() as db:
        if not db.scalar(select(func.count()).select_from(EstadoOrden)):
            db.add_all([EstadoOrden(estado_codigo=c, nombre=n) for c, n in ESTADOS_ORDEN.items()])
        cliente = Cliente(usuario_id=42)
        vehiculo = Vehiculo(cliente=cliente, patente="TEST438", marca="Marca", modelo="Modelo")
        db.add(vehiculo)
        db.flush()
        ingreso = IngresoVehiculo(vehiculo_id=vehiculo.vehiculo_id, registrado_por_id=99)
        db.add(ingreso)
        db.flush()
        orden = OrdenTrabajo(vehiculo_id=vehiculo.vehiculo_id, ingreso_id=ingreso.ingreso_id,
                             estado_codigo=ESPERANDO_APROBACION_PRESUPUESTO, creado_por_id=99)
        db.add(orden)
        db.commit()
        orden_id = orden.orden_id
    with fabrica3() as db:
        proveedor = Proveedor(nombre="Proveedor", contacto="Pruebas")
        repuesto = Repuesto(proveedor=proveedor, nombre="Repuesto", stock=10)
        presupuesto = Presupuesto(orden_id=orden_id)
        version = VersionPresupuesto(presupuesto=presupuesto, numero=1, creado_por_id=50)
        version.items = [ItemPresupuesto(tipo="repuesto", descripcion="Repuesto",
                                         cantidad=Decimal("2"), precio_unitario=Decimal("10"),
                                         repuesto=repuesto)]
        db.add_all([proveedor, presupuesto])
        db.flush()  # Primero los ítems en borrador; después se congela el envío.
        version.enviado_en = func.now()
        db.commit()
        presupuesto_id, repuesto_id = presupuesto.presupuesto_id, repuesto.repuesto_id

    monkeypatch.setattr(settings_ms3, "JWT_SECRET_KEY", settings_ms2.JWT_SECRET_KEY)
    monkeypatch.setattr(settings_ms2, "MS3_URL", "http://ms3-prueba")
    monkeypatch.setattr(settings_ms3, "MS2_URL", "http://ms2-prueba")
    app_ms2.dependency_overrides[get_db_ms2] = _sesion_por_peticion(fabrica2)
    app_ms3.dependency_overrides[get_db_ms3] = _sesion_por_peticion(fabrica3)
    fallo = {"modo": None}
    llamadas = []
    with TestClient(app_ms2) as ms2, TestClient(app_ms3) as ms3:
        def get(url, *, headers, timeout):
            llamadas.append(("GET", url, headers))
            if url.startswith("http://ms3-prueba"):
                if fallo["modo"] == "verificacion":
                    raise httpx.ConnectError("MS3 no disponible")
                return ms3.get(url.removeprefix("http://ms3-prueba"), headers=headers)
            return ms2.get(url.removeprefix("http://ms2-prueba"), headers=headers)

        def post(url, *, json, headers, timeout):
            llamadas.append(("POST", url, headers))
            if fallo["modo"] == "antes":
                return httpx.Response(503, request=httpx.Request("POST", url))
            respuesta = ms2.post(url.removeprefix("http://ms2-prueba"), json=json, headers=headers)
            if fallo["modo"] == "despues" and respuesta.status_code == 200:
                raise httpx.ReadTimeout("Se perdió la respuesta después del commit")
            return respuesta

        monkeypatch.setattr(httpx, "get", get)
        monkeypatch.setattr(httpx, "post", post)
        yield SimpleNamespace(ms2=ms2, ms3=ms3, db2=fabrica2, db3=fabrica3,
                              orden_id=orden_id, presupuesto_id=presupuesto_id,
                              repuesto_id=repuesto_id, fallo=fallo, llamadas=llamadas)
    app_ms2.dependency_overrides.pop(get_db_ms2, None)
    app_ms3.dependency_overrides.pop(get_db_ms3, None)
    engine2.dispose()
    engine3.dispose()


def _headers(usuario=42, rol=NombreRol.CLIENTE):
    token = crear_token_acceso(usuario, [rol], clave_secreta=settings_ms2.JWT_SECRET_KEY.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


def _decidir(flujo, decision="aprobado", stock=10):
    with flujo.db3() as db:
        db.get(Repuesto, flujo.repuesto_id).stock = stock
        db.commit()
    body = {"decision": decision}
    if decision == "rechazado":
        body.update(motivo="  No autorizo el servicio  ", confirmar_cancelacion=True)
    return flujo.ms3.post(f"/presupuestos/{flujo.presupuesto_id}/versiones/1/decision",
                          json=body, headers=_headers())


def _aplicar(flujo, decision_id, *, orden_id=None, headers=None, **extras):
    return flujo.ms2.post(f"/ordenes/{orden_id or flujo.orden_id}/decisiones-presupuesto",
                          json={"decision_id": decision_id, **extras},
                          headers=_headers() if headers is None else headers)


def _estado_y_historial(flujo):
    with flujo.db2() as db:
        return db.get(OrdenTrabajo, flujo.orden_id).estado_codigo, list(db.scalars(select(HistorialEstado)))


@pytest.mark.parametrize("decision,stock,esperado,motivo", [
    ("rechazado", 10, CANCELADO, "No autorizo el servicio"),
    ("aprobado", 10, EN_REPARACION, None),
    ("aprobado", 1, ESPERANDO_REPUESTOS, None),
])
def test_decision_coordina_estado_historial_actor_y_motivo(flujo, decision, stock, esperado, motivo):
    respuesta = _decidir(flujo, decision, stock)
    assert respuesta.status_code == 201, respuesta.text
    decision_id = respuesta.json()["decision_id"]
    estado, historial = _estado_y_historial(flujo)
    assert estado == esperado and len(historial) == 1
    assert historial[0].estado_anterior == ESPERANDO_APROBACION_PRESUPUESTO
    assert historial[0].estado_nuevo == esperado
    assert historial[0].decision_presupuesto_id == decision_id
    assert historial[0].actor_usuario_id == 42 and historial[0].origen == "usuario"
    assert historial[0].observacion == motivo
    with flujo.db3() as db:
        registro = db.get(DecisionPresupuesto, decision_id)
        assert registro.motivo == motivo
        assert registro.repuestos_disponibles == (None if decision == "rechazado" else stock >= 2)
    assert all(headers == flujo.llamadas[0][2] for _, _, headers in flujo.llamadas)
    hecho = flujo.ms3.get(f"/presupuestos/decisiones/{decision_id}", headers=_headers())
    assert set(hecho.json()) == {"decision_id", "orden_id", "cliente_usuario_id", "decision",
                                "primera_decision", "repuestos_disponibles", "motivo"}


def test_repetir_decision_aplicacion_y_retry_no_duplica_historial(flujo):
    primera = _decidir(flujo)
    decision_id = primera.json()["decision_id"]
    aplicada = primera.json()["aplicacion_en_orden"]
    assert _aplicar(flujo, decision_id).json() == aplicada
    reintento = flujo.ms3.post(f"/presupuestos/decisiones/{decision_id}/aplicacion", headers=_headers())
    assert reintento.status_code == 200 and reintento.json() == aplicada
    assert _decidir(flujo).status_code == 409
    assert len(_estado_y_historial(flujo)[1]) == 1
    with flujo.db3() as db:
        assert db.scalar(select(func.count()).select_from(DecisionPresupuesto)) == 1


@pytest.mark.parametrize("fallo,historias_antes", [("antes", 0), ("verificacion", 0), ("despues", 1)])
def test_fallo_ms2_conserva_decision_y_retry_aplica_una_sola_vez(flujo, fallo, historias_antes):
    flujo.fallo["modo"] = fallo
    respuesta = _decidir(flujo, "rechazado")
    assert respuesta.status_code == 503, respuesta.text
    body = respuesta.json()
    assert body["decision_registrada"] is True and body["aplicacion_confirmada"] is False
    decision_id = body["decision_id"]
    assert body["reintento"] == f"/api/presupuestos/decisiones/{decision_id}/aplicacion"
    with flujo.db3() as db:
        assert db.get(DecisionPresupuesto, decision_id).motivo == "No autorizo el servicio"
    assert len(_estado_y_historial(flujo)[1]) == historias_antes
    flujo.fallo["modo"] = None
    reintento = flujo.ms3.post(f"/presupuestos/decisiones/{decision_id}/aplicacion", headers=_headers())
    assert reintento.status_code == 200, reintento.text
    estado, historial = _estado_y_historial(flujo)
    assert estado == CANCELADO and len(historial) == 1
    assert _aplicar(flujo, decision_id).json() == reintento.json()
    with flujo.db3() as db:
        assert db.scalar(select(func.count()).select_from(DecisionPresupuesto)) == 1


def test_fallo_de_persistencia_ms2_hace_rollback_y_se_reintenta(flujo, monkeypatch):
    registrar = servicio_ordenes.registrar_historial_estado
    def fallo(*args, **kwargs):
        raise SQLAlchemyError("Fallo simulado de persistencia")
    monkeypatch.setattr(servicio_ordenes, "registrar_historial_estado", fallo)
    respuesta = _decidir(flujo)
    assert respuesta.status_code == 503
    assert _estado_y_historial(flujo) == (ESPERANDO_APROBACION_PRESUPUESTO, [])
    decision_id = respuesta.json()["decision_id"]
    monkeypatch.setattr(servicio_ordenes, "registrar_historial_estado", registrar)
    assert _aplicar(flujo, decision_id).status_code == 200
    assert len(_estado_y_historial(flujo)[1]) == 1


def test_fallo_despues_del_flush_revierte_estado_e_historial_juntos(flujo):
    def fallar_despues_de_escribir(db, _contexto):
        if any(isinstance(objeto, HistorialEstado) for objeto in db.new):
            raise SQLAlchemyError("Fallo después de escribir el historial")

    event.listen(flujo.db2, "after_flush", fallar_despues_de_escribir)
    try:
        respuesta = _decidir(flujo)
    finally:
        event.remove(flujo.db2, "after_flush", fallar_despues_de_escribir)
    assert respuesta.status_code == 503
    assert respuesta.json()["estado_ms2"] == 500
    assert _estado_y_historial(flujo) == (ESPERANDO_APROBACION_PRESUPUESTO, [])
    assert _aplicar(flujo, respuesta.json()["decision_id"]).status_code == 200
    assert len(_estado_y_historial(flujo)[1]) == 1


@pytest.mark.parametrize("decision", ["aprobado", "rechazado"])
def test_modificacion_conserva_comportamiento_y_no_reaplica_transicion_inicial(flujo, decision):
    assert _decidir(flujo).status_code == 201
    with flujo.db3() as db:
        # Fixture de una aprobación previa: SQLite no ejecuta el trigger de MS3.
        db.scalar(select(VersionPresupuesto)).bloqueada_en = datetime.now(timezone.utc)
        version = VersionPresupuesto(
            presupuesto_id=flujo.presupuesto_id, numero=2, creado_por_id=50,
            es_modificacion=True,
        )
        db.add(version)
        db.flush()
        version.enviado_en = func.now()
        db.commit()
    llamadas_antes = len([llamada for llamada in flujo.llamadas if llamada[0] == "POST"])
    body = {"decision": decision, "motivo": "Rechazo el trabajo adicional"}
    respuesta = flujo.ms3.post(
        f"/presupuestos/{flujo.presupuesto_id}/versiones/2/decision",
        json=body, headers=_headers(),
    )
    assert respuesta.status_code == 201, respuesta.text
    resultado = respuesta.json()
    assert resultado["aplicacion_en_orden"] is None
    assert resultado["efecto_en_orden"] == ("en_reparacion" if decision == "aprobado" else None)
    assert len([llamada for llamada in flujo.llamadas if llamada[0] == "POST"]) == llamadas_antes
    decision_id = resultado["decision_id"]
    assert _aplicar(flujo, decision_id).status_code == 409
    assert flujo.ms3.post(f"/presupuestos/decisiones/{decision_id}/aplicacion",
                         headers=_headers()).status_code == 409
    assert _estado_y_historial(flujo)[0] == EN_REPARACION
    assert len(_estado_y_historial(flujo)[1]) == 1


def test_stock_del_reintento_no_cambia_la_rama_persistida(flujo):
    flujo.fallo["modo"] = "antes"
    respuesta = _decidir(flujo, stock=10)
    decision_id = respuesta.json()["decision_id"]
    with flujo.db3() as db:
        db.get(Repuesto, flujo.repuesto_id).stock = 0
        db.commit()
    flujo.fallo["modo"] = None
    assert _aplicar(flujo, decision_id).status_code == 200
    assert _estado_y_historial(flujo)[0] == EN_REPARACION


def test_retry_despues_de_otro_estado_devuelve_aplicacion_original(flujo):
    resultado = _decidir(flujo).json()
    assert flujo.ms2.patch(f"/ordenes/{flujo.orden_id}/estado", json={"estado_destino": LISTO},
                           headers=_headers(99, NombreRol.ADMINISTRADOR)).status_code == 200
    flujo.fallo["modo"] = "verificacion"  # Un efecto ya guardado no necesita verificar MS3 otra vez.
    repetida = _aplicar(flujo, resultado["decision_id"])
    assert repetida.status_code == 200 and repetida.json() == resultado["aplicacion_en_orden"]
    estado, historial = _estado_y_historial(flujo)
    assert estado == LISTO and len(historial) == 2


@pytest.mark.parametrize("extra", [{"estado_destino": 8}, {"actor_usuario_id": 99},
                                     {"repuestos_disponibles": True}, {"evento": "rechazo_primer_presupuesto"}])
def test_no_acepta_hechos_actor_ni_destino_del_body(flujo, extra):
    assert _aplicar(flujo, 1, **extra).status_code == 422
    assert _estado_y_historial(flujo)[1] == []


@pytest.mark.parametrize("headers,esperado", [({}, 401), ({"Authorization": "Bearer invalido"}, 401),
                                             (None, 403)])
def test_aplicacion_protegida_por_jwt_y_rol(flujo, headers, esperado):
    if headers is None:
        headers = _headers(99, NombreRol.ADMINISTRADOR)
    assert _aplicar(flujo, 1, headers=headers).status_code == esperado


def test_decision_ajena_o_de_otra_orden_no_se_aplica(flujo):
    flujo.fallo["modo"] = "antes"
    decision_id = _decidir(flujo).json()["decision_id"]
    flujo.fallo["modo"] = None
    with flujo.db3() as db:
        # Hecho remoto de otra orden: MS2 debe comprobarlo, aunque el actor coincida.
        db.get(Presupuesto, flujo.presupuesto_id).orden_id = 999
        db.commit()
    assert _aplicar(flujo, decision_id).status_code == 404
    assert flujo.ms3.get(f"/presupuestos/decisiones/{decision_id}", headers=_headers(88)).status_code == 404
    assert _aplicar(flujo, decision_id, headers=_headers(88)).status_code == 404
    assert _estado_y_historial(flujo)[1] == []


def test_decision_de_otro_usuario_no_pasa_la_verificacion(flujo):
    with flujo.db3() as db:
        version = db.scalar(select(VersionPresupuesto))
        registro = DecisionPresupuesto(version=version, cliente_usuario_id=88,
                                       decision="aprobado", repuestos_disponibles=True)
        db.add(registro)
        db.commit()
        decision_id = registro.decision_id
    assert _aplicar(flujo, decision_id).status_code == 404
    assert _estado_y_historial(flujo)[1] == []


@pytest.mark.parametrize("usuario,esperado", [(42, 201), (88, 404)])
def test_cliente_multirol_solo_decide_presupuesto_de_su_orden(flujo, usuario, esperado):
    token = crear_token_acceso(
        usuario, [NombreRol.CLIENTE, NombreRol.ADMINISTRADOR],
        clave_secreta=settings_ms2.JWT_SECRET_KEY.get_secret_value(),
    )
    respuesta = flujo.ms3.post(
        f"/presupuestos/{flujo.presupuesto_id}/versiones/1/decision",
        json={"decision": "aprobado"},
        headers={"Authorization": f"Bearer {token}", "X-Orden-Propiedad-Verificada": "true"},
    )
    assert respuesta.status_code == esperado, respuesta.text
    with flujo.db3() as db:
        assert db.scalar(select(func.count()).select_from(DecisionPresupuesto)) == (usuario == 42)
    assert len(_estado_y_historial(flujo)[1]) == (usuario == 42)


def test_ms2_sin_confirmacion_de_propiedad_no_deja_decision_guardada(flujo, monkeypatch):
    get_original = httpx.get

    def ms2_anterior(url, **kwargs):
        respuesta = get_original(url, **kwargs)
        if "solo_propietario=true" in url:
            del respuesta.headers["X-Orden-Propiedad-Verificada"]
        return respuesta

    monkeypatch.setattr(httpx, "get", ms2_anterior)
    # La señal enviada por el cliente no sustituye la respuesta interna de MS2.
    respuesta = flujo.ms3.post(
        f"/presupuestos/{flujo.presupuesto_id}/versiones/1/decision",
        json={"decision": "aprobado"},
        headers={**_headers(), "X-Orden-Propiedad-Verificada": "true"},
    )
    assert respuesta.status_code == 503
    assert "decision_id" not in respuesta.json()  # Falló antes del commit en MS3.
    with flujo.db3() as db:
        assert db.scalar(select(func.count()).select_from(DecisionPresupuesto)) == 0
    assert _estado_y_historial(flujo) == (ESPERANDO_APROBACION_PRESUPUESTO, [])


def test_estado_incompatible_deja_decision_persistida_y_no_escribe_historial(flujo):
    with flujo.db2() as db:
        db.get(OrdenTrabajo, flujo.orden_id).estado_codigo = RECIBIDO
        db.commit()
    respuesta = _decidir(flujo)
    assert respuesta.status_code == 503
    assert respuesta.json()["estado_ms2"] == 409
    assert "no permitido" in respuesta.json()["detalle_ms2"]
    assert _aplicar(flujo, respuesta.json()["decision_id"]).status_code == 409
    assert _estado_y_historial(flujo) == (RECIBIDO, [])


def test_referencia_de_decision_es_unica_en_la_base(flujo):
    decision_id = _decidir(flujo).json()["decision_id"]
    with flujo.db2() as db:
        db.add(HistorialEstado(orden_id=flujo.orden_id, estado_anterior=3, estado_nuevo=5,
                               actor_usuario_id=42, origen="usuario", decision_presupuesto_id=decision_id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    assert len(_estado_y_historial(flujo)[1]) == 1


def test_aprobacion_historica_sin_snapshot_no_inventa_stock(flujo):
    with flujo.db3() as db:
        registro = DecisionPresupuesto(version=db.scalar(select(VersionPresupuesto)),
                                       cliente_usuario_id=42, decision="aprobado")
        db.add(registro)
        db.commit()
        decision_id = registro.decision_id
    consulta = flujo.ms3.get(f"/presupuestos/decisiones/{decision_id}", headers=_headers())
    assert consulta.status_code == 409
    assert _aplicar(flujo, decision_id).status_code == 409
    assert _estado_y_historial(flujo)[1] == []
