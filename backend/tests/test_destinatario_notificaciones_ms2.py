"""Consulta interna de propietario sin compartir bases ni abrir acceso público."""

from pydantic import SecretStr
from services.ms2_taller.config import settings
from test_ordenes_api import api_ordenes, db_ordenes, _crear_orden, _headers_para  # noqa: F401
from shared.auth import NombreRol


def test_requiere_secreto_dedicado_y_devuelve_solo_ids(api_ordenes, db_ordenes, monkeypatch):
    o = _crear_orden(db_ordenes, 10)
    ruta = f"/interno/notificaciones/ordenes/{o.orden_id}/destinatario"
    monkeypatch.setattr(settings, "NOTIFICATION_LOOKUP_SECRET", None)
    assert api_ordenes.get(ruta).status_code == 503
    secreto = "consulta-exclusiva-destinatario-ms2-123456"
    monkeypatch.setattr(settings, "NOTIFICATION_LOOKUP_SECRET", SecretStr(secreto))
    assert (
        api_ordenes.get(ruta, headers=_headers_para(99, NombreRol.ADMINISTRADOR)).status_code == 401
    )
    assert api_ordenes.get(ruta, headers={"X-Service-Token": "otra"}).status_code == 401
    h = {"X-Service-Token": secreto}
    r = api_ordenes.get(ruta, headers=h)
    assert r.status_code == 200
    assert r.json() == {
        "orden_id": o.orden_id,
        "vehiculo_id": o.vehiculo_id,
        "cliente_usuario_id": 10,
    }
    assert (
        api_ordenes.get(
            "/interno/notificaciones/ordenes/999999/destinatario", headers=h
        ).status_code
        == 404
    )
    assert (
        api_ordenes.get("/interno/notificaciones/ordenes/0/destinatario", headers=h).status_code
        == 422
    )
