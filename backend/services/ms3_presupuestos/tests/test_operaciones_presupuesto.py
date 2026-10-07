"""Operaciones transaccionales de presupuesto: envío y decisión (PostgreSQL).

Cada petición corre sobre la sesión de prueba (transacción revertida al final).
MS2 se reemplaza por un verificador falso: se controla qué órdenes son del
cliente y si MS2 está caído.
"""
from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.ms3_presupuestos import datos_prueba as datos
from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.db import get_db
from services.ms3_presupuestos.integracion_ms2 import (
    OrdenNoVisible,
    ServicioOrdenesNoDisponible,
    obtener_verificador_ordenes,
)
from services.ms3_presupuestos.main import app
from services.ms3_presupuestos.models import (
    DecisionPresupuesto,
    ItemPresupuesto,
    Presupuesto,
    Repuesto,
)
from services.ms3_presupuestos.services import presupuestos as casos
from services.ms3_presupuestos.tests import fabricas
from shared.auth import NombreRol, crear_token_acceso


def _cabecera(rol: NombreRol, usuario_id: int) -> dict[str, str]:
    token = crear_token_acceso(
        usuario_id=usuario_id, roles=[rol],
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(), algoritmo="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


ADMIN = _cabecera(NombreRol.ADMINISTRADOR, datos.ADMIN_ID)
MECANICO = _cabecera(NombreRol.MECANICO, datos.MECANICO_ID)
CLIENTE = _cabecera(NombreRol.CLIENTE, datos.CLIENTE_ID)


class VerificadorFalso:
    """Hace de MS2: `propias` son las órdenes visibles para el cliente."""

    def __init__(self) -> None:
        self.propias: set[int] = set()
        self.caido = False
        self.consultas: list[tuple[int, str]] = []

    def verificar_acceso(self, orden_id: int, token: str) -> None:
        self.consultas.append((orden_id, token))
        if self.caido:
            raise ServicioOrdenesNoDisponible("MS2 caído")
        if orden_id not in self.propias:
            raise OrdenNoVisible(orden_id)


@pytest.fixture
def ms2() -> VerificadorFalso:
    return VerificadorFalso()


@pytest.fixture
def api(db: Session, ms2: VerificadorFalso) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[obtener_verificador_ordenes] = lambda: ms2
    try:
        with TestClient(app) as cliente:
            yield cliente
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(obtener_verificador_ordenes, None)


def _ruta(presupuesto: Presupuesto, numero: int = 1, accion: str = "") -> str:
    base = f"/presupuestos/{presupuesto.presupuesto_id}/versiones/{numero}"
    return f"{base}/{accion}" if accion else base


def _del_cliente(ms2: VerificadorFalso, presupuesto: Presupuesto) -> Presupuesto:
    ms2.propias.add(presupuesto.orden_id)
    return presupuesto


def _decisiones(db: Session, presupuesto: Presupuesto) -> int:
    ids = [v.version_id for v in presupuesto.versiones]
    return db.scalar(
        select(func.count()).select_from(DecisionPresupuesto)
        .where(DecisionPresupuesto.version_id.in_(ids))
    )


# ===================================================================== ENVÍO ==

def test_enviar_congela_la_version_y_pide_aprobacion(
    api: TestClient, db: Session, presupuesto_borrador: Presupuesto
) -> None:
    r = api.post(_ruta(presupuesto_borrador, accion="envio"), headers=ADMIN)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["efecto_en_orden"] == "esperando_aprobacion"
    v1 = cuerpo["presupuesto"]["versiones"][0]
    assert v1["estado"] == "enviada" and v1["enviado_en"] is not None

    db.expire_all()
    version = db.get(Presupuesto, presupuesto_borrador.presupuesto_id).versiones[0]
    assert version.enviado_en is not None and not version.editable
    # Ya no se edita: ni por la API ni directo en la base (trigger).
    assert api.put(_ruta(presupuesto_borrador, accion="items"), json={"items": []},
                   headers=ADMIN).status_code == 409


def test_enviar_dos_veces_es_409(api: TestClient, presupuesto_enviado: Presupuesto) -> None:
    r = api.post(_ruta(presupuesto_enviado, accion="envio"), headers=ADMIN)
    assert r.status_code == 409 and "ya fue enviada" in r.json()["detail"]


def test_no_se_envia_sin_items(api: TestClient, db: Session) -> None:
    presupuesto = fabricas.nueva_version(db, items=[]).presupuesto
    r = api.post(_ruta(presupuesto, accion="envio"), headers=ADMIN)
    assert r.status_code == 422 and "no tiene ítems" in r.json()["detail"]


def test_no_se_envia_con_items_sin_precio(api: TestClient, db: Session) -> None:
    presupuesto = fabricas.nueva_version(db, items=[
        ItemPresupuesto(tipo="mano_de_obra", descripcion="Diagnóstico",
                        cantidad=Decimal("1"), precio_unitario=Decimal("0")),
    ]).presupuesto
    db.commit()
    r = api.post(_ruta(presupuesto, accion="envio"), headers=ADMIN)
    assert r.status_code == 422 and "Diagnóstico" in r.json()["detail"]
    db.expire_all()
    assert db.get(Presupuesto, presupuesto.presupuesto_id).versiones[0].enviado_en is None


def test_enviar_modificacion_no_cambia_la_orden(
    api: TestClient, db: Session, presupuesto_aprobado: Presupuesto
) -> None:
    v2 = fabricas.nueva_version_siguiente(db, presupuesto_aprobado)
    assert v2.es_modificacion
    r = api.post(_ruta(presupuesto_aprobado, 2, "envio"), headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["efecto_en_orden"] is None
    assert r.json()["presupuesto"]["version_vigente"] == 1


def test_no_se_envia_una_version_que_no_es_la_ultima(
    api: TestClient, db: Session, presupuesto_borrador: Presupuesto
) -> None:
    # v1 borrador + v2 borrador (caso forzado): solo la última puede enviarse.
    fabricas.nueva_version_siguiente(db, presupuesto_borrador)
    r = api.post(_ruta(presupuesto_borrador, 1, "envio"), headers=ADMIN)
    assert r.status_code == 409 and "reemplazada" in r.json()["detail"]


def test_solo_el_administrador_envia(api: TestClient, presupuesto_borrador: Presupuesto) -> None:
    assert api.post(_ruta(presupuesto_borrador, accion="envio"), headers=MECANICO).status_code == 403
    assert api.post(_ruta(presupuesto_borrador, accion="envio"), headers=CLIENTE).status_code == 403


def test_enviar_version_inexistente_es_404(api: TestClient, presupuesto_borrador: Presupuesto) -> None:
    assert api.post(_ruta(presupuesto_borrador, 7, "envio"), headers=ADMIN).status_code == 404


# ================================================================== DECISIÓN ==

def test_aprobar_bloquea_y_pasa_a_reparacion_si_hay_stock(
    api: TestClient, db: Session, ms2: VerificadorFalso, presupuesto_ejemplo: Presupuesto
) -> None:
    _del_cliente(ms2, presupuesto_ejemplo)
    r = api.post(_ruta(presupuesto_ejemplo, accion="decision"), headers=CLIENTE,
                 json={"decision": "aprobado"})
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["efecto_en_orden"] == "en_reparacion" and cuerpo["repuestos_faltantes"] == []
    assert cuerpo["presupuesto"]["version_vigente"] == 1
    v1 = cuerpo["presupuesto"]["versiones"][0]
    assert v1["estado"] == "aprobada" and v1["bloqueada_en"] is not None
    assert v1["decision"]["cliente_usuario_id"] == datos.CLIENTE_ID
    # MS2 recibió el mismo token del cliente.
    assert ms2.consultas[0] == (presupuesto_ejemplo.orden_id,
                                CLIENTE["Authorization"].removeprefix("Bearer "))


def test_aprobar_sin_stock_suficiente_espera_repuestos(
    api: TestClient, db: Session, ms2: VerificadorFalso, repuesto_bajo_umbral: Repuesto
) -> None:
    version = fabricas.nueva_version(db, items=[ItemPresupuesto(
        tipo="repuesto", repuesto=repuesto_bajo_umbral, descripcion="Discos",
        cantidad=Decimal("3"), precio_unitario=Decimal("45000"))])
    fabricas.enviar(db, version)
    presupuesto = _del_cliente(ms2, version.presupuesto)
    r = api.post(_ruta(presupuesto, accion="decision"), headers=CLIENTE,
                 json={"decision": "aprobado"})
    assert r.status_code == 201, r.text
    assert r.json()["efecto_en_orden"] == "esperando_repuestos"
    assert r.json()["repuestos_faltantes"] == [{
        "repuesto_id": repuesto_bajo_umbral.repuesto_id, "nombre": repuesto_bajo_umbral.nombre,
        "requerido": "3.00", "disponible": 2,
    }]


def test_primer_rechazo_sin_confirmar_no_registra_nada(
    api: TestClient, db: Session, ms2: VerificadorFalso, presupuesto_enviado: Presupuesto
) -> None:
    _del_cliente(ms2, presupuesto_enviado)
    db.commit()
    r = api.post(_ruta(presupuesto_enviado, accion="decision"), headers=CLIENTE,
                 json={"decision": "rechazado", "motivo": "Muy caro"})
    assert r.status_code == 422 and "cancela el servicio" in r.json()["detail"]
    assert _decisiones(db, presupuesto_enviado) == 0


def test_primer_rechazo_confirmado_cancela_la_orden(
    api: TestClient, ms2: VerificadorFalso, presupuesto_enviado: Presupuesto
) -> None:
    _del_cliente(ms2, presupuesto_enviado)
    r = api.post(_ruta(presupuesto_enviado, accion="decision"), headers=CLIENTE,
                 json={"decision": "rechazado", "motivo": "Muy caro",
                       "confirmar_cancelacion": True})
    assert r.status_code == 201, r.text
    assert r.json()["efecto_en_orden"] == "cancelado"
    v1 = r.json()["presupuesto"]["versiones"][0]
    assert v1["estado"] == "rechazada" and v1["decision"]["motivo"] == "Muy caro"
    assert r.json()["presupuesto"]["version_vigente"] is None


def test_rechazo_sin_motivo_es_422(
    api: TestClient, ms2: VerificadorFalso, presupuesto_enviado: Presupuesto
) -> None:
    _del_cliente(ms2, presupuesto_enviado)
    r = api.post(_ruta(presupuesto_enviado, accion="decision"), headers=CLIENTE,
                 json={"decision": "rechazado", "confirmar_cancelacion": True})
    assert r.status_code == 422


def test_rechazar_modificacion_conserva_la_aprobacion_vigente(
    api: TestClient, db: Session, ms2: VerificadorFalso, presupuesto_aprobado: Presupuesto
) -> None:
    v2 = fabricas.nueva_version_siguiente(db, presupuesto_aprobado)
    fabricas.enviar(db, v2)
    _del_cliente(ms2, presupuesto_aprobado)
    r = api.post(_ruta(presupuesto_aprobado, 2, "decision"), headers=CLIENTE,
                 json={"decision": "rechazado", "motivo": "No quiero el trabajo extra"})
    assert r.status_code == 201, r.text
    assert r.json()["efecto_en_orden"] is None
    assert r.json()["presupuesto"]["version_vigente"] == 1
    estados = [v["estado"] for v in r.json()["presupuesto"]["versiones"]]
    assert estados == ["aprobada", "rechazada"]


def test_aprobar_modificacion_la_vuelve_vigente(
    api: TestClient, db: Session, ms2: VerificadorFalso, presupuesto_aprobado: Presupuesto
) -> None:
    v2 = fabricas.nueva_version_siguiente(db, presupuesto_aprobado)
    fabricas.enviar(db, v2)
    _del_cliente(ms2, presupuesto_aprobado)
    r = api.post(_ruta(presupuesto_aprobado, 2, "decision"), headers=CLIENTE,
                 json={"decision": "aprobado"})
    assert r.status_code == 201
    assert r.json()["presupuesto"]["version_vigente"] == 2


def test_decidir_dos_veces_es_409(
    api: TestClient, ms2: VerificadorFalso, presupuesto_aprobado: Presupuesto
) -> None:
    _del_cliente(ms2, presupuesto_aprobado)
    r = api.post(_ruta(presupuesto_aprobado, accion="decision"), headers=CLIENTE,
                 json={"decision": "rechazado", "motivo": "cambié de opinión"})
    assert r.status_code == 409 and "ya tiene una decisión" in r.json()["detail"]


def test_no_se_decide_sobre_una_version_reemplazada(
    api: TestClient, db: Session, ms2: VerificadorFalso, presupuesto_enviado: Presupuesto
) -> None:
    v2 = fabricas.nueva_version_siguiente(db, presupuesto_enviado)
    fabricas.enviar(db, v2)
    _del_cliente(ms2, presupuesto_enviado)
    r = api.post(_ruta(presupuesto_enviado, 1, "decision"), headers=CLIENTE,
                 json={"decision": "aprobado"})
    assert r.status_code == 409 and "reemplazada por la versión 2" in r.json()["detail"]


def test_borrador_no_existe_para_el_cliente(
    api: TestClient, ms2: VerificadorFalso, presupuesto_borrador: Presupuesto
) -> None:
    _del_cliente(ms2, presupuesto_borrador)
    r = api.post(_ruta(presupuesto_borrador, accion="decision"), headers=CLIENTE,
                 json={"decision": "aprobado"})
    assert r.status_code == 404


def test_presupuesto_de_otra_persona_es_404(
    api: TestClient, db: Session, presupuesto_enviado: Presupuesto
) -> None:
    r = api.post(_ruta(presupuesto_enviado, accion="decision"), headers=CLIENTE,
                 json={"decision": "aprobado"})
    assert r.status_code == 404
    assert r.json()["detail"] == f"Presupuesto {presupuesto_enviado.presupuesto_id} no existe"
    assert _decisiones(db, presupuesto_enviado) == 0


def test_ms2_caido_responde_503_sin_decidir(
    api: TestClient, db: Session, ms2: VerificadorFalso, presupuesto_enviado: Presupuesto
) -> None:
    ms2.caido = True
    r = api.post(_ruta(presupuesto_enviado, accion="decision"), headers=CLIENTE,
                 json={"decision": "aprobado"})
    assert r.status_code == 503
    assert _decisiones(db, presupuesto_enviado) == 0


def test_personal_del_taller_no_decide(api: TestClient, presupuesto_enviado: Presupuesto) -> None:
    for cabecera in (ADMIN, MECANICO):
        r = api.post(_ruta(presupuesto_enviado, accion="decision"), headers=cabecera,
                     json={"decision": "aprobado"})
        assert r.status_code == 403


# ============================================================== ATOMICIDAD ==

def test_si_falla_despues_de_registrar_la_decision_no_queda_nada(
    api: TestClient, db: Session, ms2: VerificadorFalso,
    presupuesto_enviado: Presupuesto, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La decisión, el bloqueo (trigger) y el cálculo del efecto son UNA transacción."""
    _del_cliente(ms2, presupuesto_enviado)
    db.commit()

    def falla(_version):
        raise RuntimeError("falla simulada después del INSERT de la decisión")

    monkeypatch.setattr(casos, "_repuestos_faltantes", falla)
    with TestClient(app, raise_server_exceptions=False) as cliente:
        r = cliente.post(_ruta(presupuesto_enviado, accion="decision"), headers=CLIENTE,
                         json={"decision": "aprobado"})
    assert r.status_code == 500
    db.expire_all()
    assert _decisiones(db, presupuesto_enviado) == 0
    version = db.get(Presupuesto, presupuesto_enviado.presupuesto_id).versiones[0]
    assert version.bloqueada_en is None


# ========================================================= CLIENTE CONSULTA ==

def test_cliente_ve_su_presupuesto_sin_borradores(
    api: TestClient, db: Session, ms2: VerificadorFalso, presupuesto_enviado: Presupuesto
) -> None:
    fabricas.nueva_version_siguiente(db, presupuesto_enviado)  # v2 en borrador
    _del_cliente(ms2, presupuesto_enviado)
    r = api.get(f"/presupuestos/{presupuesto_enviado.presupuesto_id}", headers=CLIENTE)
    assert r.status_code == 200
    assert [v["numero"] for v in r.json()["versiones"]] == [1]
    assert r.json()["ultima_version"] == 1
    assert api.get(_ruta(presupuesto_enviado, 2), headers=CLIENTE).status_code == 404
    assert api.get(_ruta(presupuesto_enviado, 1), headers=CLIENTE).status_code == 200
    # El personal sí ve el borrador.
    assert len(api.get(f"/presupuestos/{presupuesto_enviado.presupuesto_id}",
                       headers=ADMIN).json()["versiones"]) == 2


def test_cliente_no_ve_presupuesto_que_solo_tiene_borrador(
    api: TestClient, ms2: VerificadorFalso, presupuesto_borrador: Presupuesto
) -> None:
    _del_cliente(ms2, presupuesto_borrador)
    assert api.get(f"/presupuestos/{presupuesto_borrador.presupuesto_id}",
                   headers=CLIENTE).status_code == 404
    pagina = api.get(f"/presupuestos?orden_id={presupuesto_borrador.orden_id}",
                     headers=CLIENTE).json()
    assert pagina["total"] == 0 and pagina["presupuestos"] == []


def test_cliente_busca_por_su_orden(
    api: TestClient, ms2: VerificadorFalso, presupuesto_enviado: Presupuesto
) -> None:
    _del_cliente(ms2, presupuesto_enviado)
    r = api.get(f"/presupuestos?orden_id={presupuesto_enviado.orden_id}", headers=CLIENTE)
    assert r.status_code == 200 and r.json()["total"] == 1
    assert api.get("/presupuestos", headers=CLIENTE).status_code == 422


def test_cliente_no_ve_ordenes_ajenas(api: TestClient, presupuesto_enviado: Presupuesto) -> None:
    assert api.get(f"/presupuestos/{presupuesto_enviado.presupuesto_id}",
                   headers=CLIENTE).status_code == 404
    assert api.get(f"/presupuestos?orden_id={presupuesto_enviado.orden_id}",
                   headers=CLIENTE).status_code == 404
