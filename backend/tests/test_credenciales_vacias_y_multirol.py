"""Pruebas de credenciales vacías o inválidas y de cuentas con roles múltiples.

Cubre dos ejes del login de MS1 (`POST /auth/login`) y del registro público:

- **Credenciales vacías o mal formadas**: deben rechazarse con `422` en la capa
  de schemas (Pydantic), sin llegar al caso de uso. Por eso no cuentan como
  intento fallido ni pueden bloquear una cuenta.
- **Cuentas con varios roles**: el token emitido lleva todos los roles sin
  duplicados, y las reglas de credenciales (mensaje genérico, bloqueo por
  intentos, cuenta inactiva) se aplican a la cuenta igual que a una de un rol.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.ms1_auth.config import settings
from services.ms1_auth.models.rol import Rol, UsuarioRol
from services.ms1_auth.models.usuario import Usuario
from shared.auth import NombreRol, validar_token_acceso


CONTRASENA = "ClaveSegura123!"
MENSAJE_CREDENCIALES = "Correo o contraseña incorrectos"


def _registrar(api: TestClient, email: str) -> int:
    """Registra una cuenta pública (nace con el rol cliente) y devuelve su id."""

    respuesta = api.post(
        "/auth/register",
        json={"email": email, "password": CONTRASENA, "full_name": "Usuario Prueba"},
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["id"]


def _asignar_roles_bd(db: Session, usuario_id: int, *roles: NombreRol) -> None:
    """Agrega roles directamente en la tabla puente para preparar el escenario."""

    for rol in roles:
        registro = db.scalar(select(Rol).where(Rol.nombre == rol.value))
        assert registro is not None
        db.add(UsuarioRol(usuario_id=usuario_id, rol=registro))
    db.commit()


def _usuario_bd(db: Session, usuario_id: int) -> Usuario:
    """Relee la cuenta desde la base para revisar contador y bloqueo."""

    usuario = db.get(Usuario, usuario_id)
    assert usuario is not None
    db.refresh(usuario)
    return usuario


def _login(api: TestClient, email: str, password: str = CONTRASENA):
    return api.post("/auth/login", json={"email": email, "password": password})


@pytest.fixture
def cuenta_multirol(api: TestClient, db: Session) -> tuple[int, str]:
    """Cuenta con los tres roles: cliente (registro) + mecánico + administrador."""

    email = "multirol@correo.cl"
    usuario_id = _registrar(api, email)
    _asignar_roles_bd(db, usuario_id, NombreRol.MECANICO, NombreRol.ADMINISTRADOR)
    return usuario_id, email


# --------------------------------------------------------------------------- #
# Login con credenciales vacías o mal formadas
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"email": "vacio@correo.cl", "password": ""},
        {"email": "vacio@correo.cl", "password": "   "},
        {"email": "", "password": CONTRASENA},
        {"email": "   ", "password": CONTRASENA},
        {"email": "", "password": ""},
        {"email": "no-es-un-correo", "password": CONTRASENA},
        {"email": None, "password": CONTRASENA},
        {"email": "vacio@correo.cl", "password": None},
        {"email": "vacio@correo.cl"},
        {"password": CONTRASENA},
        {},
    ],
    ids=[
        "password-vacia",
        "password-solo-espacios",
        "email-vacio",
        "email-solo-espacios",
        "ambos-vacios",
        "email-mal-formado",
        "email-null",
        "password-null",
        "falta-password",
        "falta-email",
        "cuerpo-vacio",
    ],
)
def test_login_con_credenciales_vacias_o_invalidas_devuelve_422(
    api: TestClient, cuerpo: dict
) -> None:
    respuesta = api.post("/auth/login", json=cuerpo)

    assert respuesta.status_code == 422
    assert "access_token" not in respuesta.text


def test_login_sin_cuerpo_devuelve_422(api: TestClient) -> None:
    respuesta = api.post("/auth/login")

    assert respuesta.status_code == 422


def test_password_vacia_no_cuenta_como_intento_fallido(
    api: TestClient, db: Session
) -> None:
    """Un `422` no llega al caso de uso: no suma intentos ni bloquea la cuenta."""

    usuario_id = _registrar(api, "nobloquea@correo.cl")

    for _ in range(settings.LOGIN_MAX_INTENTOS + 1):
        assert _login(api, "nobloquea@correo.cl", "").status_code == 422

    usuario = _usuario_bd(db, usuario_id)
    assert usuario.intentos_fallidos == 0
    assert usuario.bloqueado_hasta is None
    assert _login(api, "nobloquea@correo.cl").status_code == 200


def test_password_incorrecta_no_vacia_si_cuenta_como_intento(
    api: TestClient, db: Session
) -> None:
    """Contraste: una contraseña con formato válido pero errónea sí suma."""

    usuario_id = _registrar(api, "contraste@correo.cl")

    respuesta = _login(api, "contraste@correo.cl", "incorrecta")

    assert respuesta.status_code == 401
    assert respuesta.json() == {"detail": MENSAJE_CREDENCIALES}
    assert _usuario_bd(db, usuario_id).intentos_fallidos == 1


# --------------------------------------------------------------------------- #
# Registro con credenciales vacías o inválidas
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"email": "", "password": CONTRASENA, "full_name": "Nombre Valido"},
        {"email": "registro@correo.cl", "password": "", "full_name": "Nombre Valido"},
        {"email": "registro@correo.cl", "password": "        ", "full_name": "Nombre Valido"},
        {"email": "registro@correo.cl", "password": "corta", "full_name": "Nombre Valido"},
        {"email": "registro@correo.cl", "password": CONTRASENA, "full_name": ""},
        {"email": "registro@correo.cl", "password": CONTRASENA, "full_name": "  "},
        {"email": "no-es-un-correo", "password": CONTRASENA, "full_name": "Nombre Valido"},
        {},
    ],
    ids=[
        "email-vacio",
        "password-vacia",
        "password-solo-espacios",
        "password-menor-a-8",
        "nombre-vacio",
        "nombre-solo-espacios",
        "email-mal-formado",
        "cuerpo-vacio",
    ],
)
def test_registro_con_datos_vacios_o_invalidos_devuelve_422_y_no_crea_cuenta(
    api: TestClient, db: Session, cuerpo: dict
) -> None:
    respuesta = api.post("/auth/register", json=cuerpo)

    assert respuesta.status_code == 422
    assert db.scalar(select(Usuario.usuario_id)) is None


# --------------------------------------------------------------------------- #
# Cuentas con roles múltiples
# --------------------------------------------------------------------------- #


def test_token_de_cuenta_multirol_lleva_todos_los_roles_sin_duplicados(
    api: TestClient, cuenta_multirol: tuple[int, str]
) -> None:
    usuario_id, email = cuenta_multirol

    respuesta = _login(api, email)

    assert respuesta.status_code == 200
    token = respuesta.json()["access_token"]
    claims = jwt.get_unverified_claims(token)
    assert claims["sub"] == str(usuario_id)
    assert claims["roles"] == ["administrador", "cliente", "mecanico"]

    principal = validar_token_acceso(
        token,
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(),
        algoritmo=settings.JWT_ALGORITHM,
    )
    assert principal.usuario_id == usuario_id
    assert principal.roles == frozenset(NombreRol)


def test_cuenta_multirol_con_password_incorrecta_recibe_el_mismo_401(
    api: TestClient, cuenta_multirol: tuple[int, str]
) -> None:
    """Tener varios roles no cambia el mensaje genérico ni revela la cuenta."""

    _, email = cuenta_multirol

    multirol = _login(api, email, "incorrecta")
    inexistente = _login(api, "noexiste@correo.cl", "incorrecta")

    assert multirol.status_code == inexistente.status_code == 401
    assert multirol.json() == inexistente.json() == {"detail": MENSAJE_CREDENCIALES}
    assert multirol.headers["www-authenticate"] == "Bearer"


def test_cuenta_multirol_con_password_vacia_devuelve_422_sin_sumar_intentos(
    api: TestClient, db: Session, cuenta_multirol: tuple[int, str]
) -> None:
    usuario_id, email = cuenta_multirol

    assert _login(api, email, "").status_code == 422
    assert _usuario_bd(db, usuario_id).intentos_fallidos == 0


def test_cuenta_multirol_se_bloquea_igual_que_una_de_un_rol(
    api: TestClient, db: Session, cuenta_multirol: tuple[int, str]
) -> None:
    """El bloqueo es por cuenta: ni el rol administrador lo evita."""

    usuario_id, email = cuenta_multirol

    for _ in range(settings.LOGIN_MAX_INTENTOS):
        assert _login(api, email, "incorrecta").status_code == 401

    bloqueado = _login(api, email)  # contraseña correcta durante el bloqueo

    assert bloqueado.status_code == 429
    assert int(bloqueado.headers["retry-after"]) > 0
    assert _usuario_bd(db, usuario_id).bloqueado_hasta is not None


def test_cuenta_multirol_inactiva_recibe_401_generico(
    api: TestClient, db: Session, cuenta_multirol: tuple[int, str]
) -> None:
    usuario_id, email = cuenta_multirol
    usuario = _usuario_bd(db, usuario_id)
    usuario.activo = False
    db.commit()

    respuesta = _login(api, email)

    assert respuesta.status_code == 401
    assert respuesta.json() == {"detail": MENSAJE_CREDENCIALES}


def test_multirol_sin_administrador_no_accede_a_gestion_de_usuarios(
    api: TestClient, db: Session
) -> None:
    """Cliente + Mecánico es la unión de sus permisos, nunca Administrador."""

    usuario_id = _registrar(api, "cliente-mecanico@correo.cl")
    _asignar_roles_bd(db, usuario_id, NombreRol.MECANICO)
    token = _login(api, "cliente-mecanico@correo.cl").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert api.get("/auth/usuarios", headers=headers).status_code == 403
    assert api.get("/auth/me", headers=headers).json()["roles"] == ["cliente", "mecanico"]


def test_multirol_con_administrador_accede_con_token_de_login(
    api: TestClient, cuenta_multirol: tuple[int, str]
) -> None:
    _, email = cuenta_multirol
    token = _login(api, email).json()["access_token"]

    respuesta = api.get("/auth/usuarios", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 200
