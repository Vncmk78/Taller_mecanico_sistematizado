"""El secreto de protección de Vercel no sale al host o prefijo equivocado."""

import pytest
from shared.direccion_notificaciones import url_notificaciones_por_defecto, cabeceras_notificaciones


@pytest.mark.parametrize("ms", [1, 2])
def test_mismo_despliegue_y_bypass_acotado(monkeypatch, ms):
    monkeypatch.delenv("VERCEL", raising=False)
    assert url_notificaciones_por_defecto(ms) == f"http://localhost:800{ms}"
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_URL", "preview-seguro.vercel.app")
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "produccion.vercel.app")
    monkeypatch.setenv("VERCEL_AUTOMATION_BYPASS_SECRET", "secreto-plataforma-prueba")
    destino = f"https://preview-seguro.vercel.app/ms{ms}"
    assert url_notificaciones_por_defecto(ms) == destino
    assert cabeceras_notificaciones(destino, ms, "servicio") == {
        "X-Service-Token": "servicio",
        "x-vercel-protection-bypass": "secreto-plataforma-prueba",
    }
    for url in [
        f"https://produccion.vercel.app/ms{ms}",
        destino + ".evil",
        destino + "/extra",
        f"https://preview-seguro.vercel.app/ms{3-ms}",
        f"http://preview-seguro.vercel.app/ms{ms}",
    ]:
        assert cabeceras_notificaciones(url, ms, "servicio") == {"X-Service-Token": "servicio"}


@pytest.mark.parametrize(
    "host",
    [
        "",
        "https://otro.vercel.app",
        "usuario@otro.vercel.app",
        "otro.vercel.app/ruta",
        "otro.vercel.app?x=y",
        "otro.vercel.app:443",
        "otro..vercel.app",
    ],
)
def test_url_invalida_no_cae_a_localhost_ni_transmite_bypass(monkeypatch, host):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_URL", host)
    monkeypatch.setenv("VERCEL_AUTOMATION_BYPASS_SECRET", "secreto-plataforma-prueba")
    with pytest.raises(ValueError):
        url_notificaciones_por_defecto(1)
    assert cabeceras_notificaciones("https://otro.vercel.app/ms1", 1, "servicio") == {
        "X-Service-Token": "servicio"
    }
