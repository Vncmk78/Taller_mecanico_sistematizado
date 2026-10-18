"""Pruebas para el bloqueo de cuenta tras intentos fallidos repetidos de login."""

from __future__ import annotations

from fastapi.testclient import TestClient


DATOS_REGISTRO = {
    "email": "lock@correo.cl",
    "password": "ClaveSegura123!",
    "full_name": "Cuenta Bloqueada",
}


def test_bloqueo_tras_max_intentos_devuelve_429(api: TestClient) -> None:
    """Tras alcanzar el umbral, el siguiente intento devuelve 429 con Retry-After."""
    assert api.post("/auth/register", json=DATOS_REGISTRO).status_code == 201

    # Alcanzar el máximo de intentos (por defecto 5)
    for _ in range(5):
        respuesta = api.post(
            "/auth/login",
            json={"email": DATOS_REGISTRO["email"], "password": "incorrecta"},
        )
        assert respuesta.status_code == 401
        assert "www-authenticate" in respuesta.headers

    bloqueado = api.post(
        "/auth/login",
        json={"email": DATOS_REGISTRO["email"], "password": "incorrecta"},
    )
    assert bloqueado.status_code == 429
    assert bloqueado.json()["detail"] == (
        "Demasiados intentos fallidos. Inténtalo de nuevo más tarde"
    )
    assert "retry-after" in bloqueado.headers
    assert int(bloqueado.headers["retry-after"]) > 0


def test_login_correcto_reinicia_contador(api: TestClient) -> None:
    datos = {
        "email": "reinicia2@correo.cl",
        "password": "ClaveSegura123!",
        "full_name": "Cuenta",
    }
    assert api.post("/auth/register", json=datos).status_code == 201
    for _ in range(4):
        assert api.post("/auth/login", json={"email": datos["email"], "password": "mal"}).status_code == 401
    assert api.post("/auth/login", json={"email": datos["email"], "password": datos["password"]}).status_code == 200
    for _ in range(4):
        assert api.post("/auth/login", json={"email": datos["email"], "password": "mal"}).status_code == 401
