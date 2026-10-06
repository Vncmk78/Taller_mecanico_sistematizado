"""Contratos de los endpoints iniciales de presupuestos de MS3 (sin base de datos).

La persistencia real se prueba en services/ms3_presupuestos/tests/
test_api_presupuestos.py (PostgreSQL).
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from services.ms3_presupuestos.config import settings
from services.ms3_presupuestos.main import app
from services.ms3_presupuestos.schemas.presupuesto import (
    DecisionEntrada,
    ItemEntrada,
    PresupuestoCrear,
)
from shared.auth import NombreRol, crear_token_acceso

RUTAS = {
    ("post", "/presupuestos"),
    ("get", "/presupuestos"),
    ("get", "/presupuestos/{presupuesto_id}"),
    ("get", "/presupuestos/{presupuesto_id}/versiones/{numero}"),
    ("put", "/presupuestos/{presupuesto_id}/versiones/{numero}/items"),
    ("post", "/presupuestos/{presupuesto_id}/versiones/{numero}/envio"),
    ("post", "/presupuestos/{presupuesto_id}/versiones/{numero}/decision"),
}


def test_openapi_publica_los_endpoints_de_presupuestos() -> None:
    rutas = app.openapi()["paths"]
    publicadas = {(m, r) for r, ops in rutas.items() for m in ops if r.startswith("/presupuestos")}
    assert publicadas == RUTAS
    for metodo, ruta in RUTAS:
        assert rutas[ruta][metodo]["tags"] == ["presupuestos"]


def _token(*roles: NombreRol) -> dict[str, str]:
    token = crear_token_acceso(
        usuario_id=1, roles=roles,
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(), algoritmo="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(("roles", "ruta", "cuerpo"), [
    ((NombreRol.CLIENTE,), "/presupuestos", {"orden_id": 1}),
    ((NombreRol.CLIENTE,), "/presupuestos/1/versiones/1/envio", None),
    ((NombreRol.MECANICO,), "/presupuestos/1/versiones/1/envio", None),
    ((NombreRol.ADMINISTRADOR,), "/presupuestos/1/versiones/1/decision", {"decision": "aprobado"}),
    ((NombreRol.MECANICO,), "/presupuestos/1/versiones/1/decision", {"decision": "aprobado"}),
])
def test_rol_no_permitido_recibe_403_antes_de_tocar_la_base(roles, ruta, cuerpo) -> None:
    with TestClient(app) as cliente:
        assert cliente.post(ruta, json=cuerpo, headers=_token(*roles)).status_code == 403


def test_decision_de_rechazo_exige_motivo() -> None:
    with pytest.raises(ValidationError):
        DecisionEntrada(decision="rechazado", motivo="   ")
    assert DecisionEntrada(decision="aprobado").confirmar_cancelacion is False


def test_item_de_mano_de_obra_valido_y_precio_por_defecto() -> None:
    item = ItemEntrada(tipo="mano_de_obra", descripcion="  Revisión  ", cantidad="1.5")
    assert item.descripcion == "Revisión"
    assert item.cantidad == Decimal("1.5") and item.precio_unitario == 0


@pytest.mark.parametrize("datos", [
    {"tipo": "repuesto", "descripcion": "x", "cantidad": 1},
    {"tipo": "mano_de_obra", "descripcion": "x", "cantidad": 1, "repuesto_id": 3},
    {"tipo": "mano_de_obra", "descripcion": "x", "cantidad": "1.555"},
    {"tipo": "mano_de_obra", "descripcion": "x", "cantidad": 1, "extra": True},
])
def test_items_invalidos(datos: dict) -> None:
    with pytest.raises(ValidationError):
        ItemEntrada(**datos)


def test_presupuesto_crear_exige_orden_positiva() -> None:
    with pytest.raises(ValidationError):
        PresupuestoCrear(orden_id=0)
    assert PresupuestoCrear(orden_id=5).items == []
