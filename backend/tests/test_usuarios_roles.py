"""Pruebas de gestión de usuarios: cuentas con uno y varios roles.

Cubre los endpoints administrativos de MS1 —listado, detalle, asignación y
retirada de roles— con el eje de la tarea: una cuenta con **un solo rol** y una
cuenta con **varios roles**. Incluye la autorización del guard (401 / 403) y la
persistencia real en la tabla puente `usuario_rol`.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.ms1_auth.config import settings
from services.ms1_auth.models.rol import Rol, UsuarioRol
from services.ms1_auth.models.usuario import Usuario
from shared.auth import NombreRol, crear_token_acceso


CONTRASENA = "ClaveSegura123!"


def _registrar(api: TestClient, email: str, nombre: str = "Usuario Prueba") -> int:
    """Registra una cuenta pública (nace con el rol cliente) y devuelve su id."""

    respuesta = api.post(
        "/auth/register",
        json={"email": email, "password": CONTRASENA, "full_name": nombre},
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["id"]


def _asignar_roles_bd(db: Session, usuario_id: int, *roles: NombreRol) -> None:
    """Asigna roles directamente en la tabla puente, para preparar escenarios."""

    for rol in roles:
        registro = db.scalar(select(Rol).where(Rol.nombre == rol.value))
        assert registro is not None
        db.add(UsuarioRol(usuario_id=usuario_id, rol=registro))
    db.commit()


def _headers_para(usuario_id: int, *roles: NombreRol) -> dict[str, str]:
    """Emite un Bearer JWT real con los roles indicados."""

    token = crear_token_acceso(
        usuario_id,
        roles,
        clave_secreta=settings.JWT_SECRET_KEY.get_secret_value(),
        algoritmo=settings.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


def _usuario_de(respuesta, usuario_id: int) -> dict:
    """Extrae una fila del listado por su id."""

    return next(fila for fila in respuesta.json() if fila["id"] == usuario_id)


def _roles_en_bd(db: Session, usuario_id: int) -> list[str]:
    """Lee los roles persistidos, ordenados, sin pasar por la API."""

    usuario = db.scalar(select(Usuario).where(Usuario.usuario_id == usuario_id))
    db.refresh(usuario)
    return sorted(asignacion.rol.nombre for asignacion in usuario.roles)


@pytest.fixture
def admin_id(api: TestClient, db: Session) -> int:
    """Id de una cuenta administradora real."""

    usuario_id = _registrar(api, "admin@taller.cl", "Admin Taller")
    _asignar_roles_bd(db, usuario_id, NombreRol.ADMINISTRADOR)
    return usuario_id


@pytest.fixture
def admin_headers(admin_id: int) -> dict[str, str]:
    """Cabecera Authorization de la cuenta administradora."""

    return _headers_para(admin_id, NombreRol.ADMINISTRADOR)


# --------------------------------------------------------------------------- #
# Listado: GET /auth/usuarios
# --------------------------------------------------------------------------- #


def test_listado_sin_token_devuelve_401(api: TestClient):
    respuesta = api.get("/auth/usuarios")

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_listado_con_token_invalido_devuelve_401(api: TestClient):
    respuesta = api.get(
        "/auth/usuarios",
        headers={"Authorization": "Bearer token-invalido"},
    )

    assert respuesta.status_code == 401


@pytest.mark.parametrize(
    "roles",
    [
        (NombreRol.CLIENTE,),
        (NombreRol.MECANICO,),
        (NombreRol.CLIENTE, NombreRol.MECANICO),
    ],
)
def test_listado_sin_rol_administrador_devuelve_403(
    api: TestClient,
    roles: tuple[NombreRol, ...],
):
    """Ni un solo rol ni varios alcanzan si ninguno es Administrador."""

    respuesta = api.get("/auth/usuarios", headers=_headers_para(99, *roles))

    assert respuesta.status_code == 403


def test_listado_administrador_multirol_es_permitido(
    api: TestClient,
    admin_id: int,
):
    """La unión de roles permite entrar: Administrador + Mecánico."""

    respuesta = api.get(
        "/auth/usuarios",
        headers=_headers_para(
            admin_id, NombreRol.ADMINISTRADOR, NombreRol.MECANICO
        ),
    )

    assert respuesta.status_code == 200


def test_listado_incluye_usuario_con_un_solo_rol(
    api: TestClient,
    admin_headers: dict[str, str],
):
    usuario_id = _registrar(api, "uno@correo.cl")

    respuesta = api.get("/auth/usuarios", headers=admin_headers)

    assert respuesta.status_code == 200
    assert _usuario_de(respuesta, usuario_id)["roles"] == ["cliente"]


def test_listado_incluye_usuario_con_varios_roles(
    api: TestClient,
    db: Session,
    admin_headers: dict[str, str],
):
    usuario_id = _registrar(api, "varios@correo.cl")
    _asignar_roles_bd(db, usuario_id, NombreRol.MECANICO, NombreRol.ADMINISTRADOR)

    respuesta = api.get("/auth/usuarios", headers=admin_headers)

    assert respuesta.status_code == 200
    assert _usuario_de(respuesta, usuario_id)["roles"] == [
        "administrador",
        "cliente",
        "mecanico",
    ]


def test_listado_ordena_por_identificador(
    api: TestClient,
    admin_headers: dict[str, str],
):
    primero = _registrar(api, "primero@correo.cl")
    segundo = _registrar(api, "segundo@correo.cl")

    respuesta = api.get("/auth/usuarios", headers=admin_headers)

    ids = [fila["id"] for fila in respuesta.json()]
    assert ids == sorted(ids)
    assert ids.index(primero) < ids.index(segundo)


def test_listado_incluye_cuenta_sin_roles_con_lista_vacia(
    api: TestClient,
    admin_headers: dict[str, str],
):
    usuario_id = _registrar(api, "sinroles@correo.cl")
    assert api.delete(
        f"/auth/usuarios/{usuario_id}/roles/cliente", headers=admin_headers
    ).status_code == 200

    respuesta = api.get("/auth/usuarios", headers=admin_headers)

    assert respuesta.status_code == 200
    fila = _usuario_de(respuesta, usuario_id)
    assert fila["roles"] == []
    assert fila["is_active"] is True


# --------------------------------------------------------------------------- #
# Detalle: GET /auth/usuarios/{usuario_id}
# --------------------------------------------------------------------------- #


def test_detalle_sin_token_devuelve_401(api: TestClient):
    respuesta = api.get("/auth/usuarios/1")

    assert respuesta.status_code == 401


@pytest.mark.parametrize(
    "roles",
    [
        (NombreRol.CLIENTE,),
        (NombreRol.MECANICO,),
        (NombreRol.CLIENTE, NombreRol.MECANICO),
    ],
)
def test_detalle_sin_rol_administrador_devuelve_403(
    api: TestClient,
    roles: tuple[NombreRol, ...],
):
    respuesta = api.get("/auth/usuarios/1", headers=_headers_para(99, *roles))

    assert respuesta.status_code == 403


def test_detalle_de_usuario_con_un_solo_rol(
    api: TestClient,
    admin_headers: dict[str, str],
):
    usuario_id = _registrar(api, "detalle-uno@correo.cl")

    respuesta = api.get(f"/auth/usuarios/{usuario_id}", headers=admin_headers)

    assert respuesta.status_code == 200
    assert respuesta.json()["roles"] == ["cliente"]
    assert respuesta.json()["id"] == usuario_id


def test_detalle_de_usuario_con_varios_roles(
    api: TestClient,
    db: Session,
    admin_headers: dict[str, str],
):
    usuario_id = _registrar(api, "detalle-varios@correo.cl")
    _asignar_roles_bd(db, usuario_id, NombreRol.MECANICO)

    respuesta = api.get(f"/auth/usuarios/{usuario_id}", headers=admin_headers)

    assert respuesta.status_code == 200
    assert respuesta.json()["roles"] == ["cliente", "mecanico"]


def test_detalle_de_cuenta_sin_roles_devuelve_lista_vacia(
    api: TestClient,
    admin_headers: dict[str, str],
):
    usuario_id = _registrar(api, "detalle-sinroles@correo.cl")
    api.delete(f"/auth/usuarios/{usuario_id}/roles/cliente", headers=admin_headers)

    respuesta = api.get(f"/auth/usuarios/{usuario_id}", headers=admin_headers)

    assert respuesta.status_code == 200
    assert respuesta.json()["roles"] == []


def test_detalle_de_usuario_inexistente_devuelve_404(
    api: TestClient,
    admin_headers: dict[str, str],
):
    respuesta = api.get("/auth/usuarios/999999", headers=admin_headers)

    assert respuesta.status_code == 404


def test_detalle_con_identificador_no_entero_devuelve_422(
    api: TestClient,
    admin_headers: dict[str, str],
):
    respuesta = api.get("/auth/usuarios/abc", headers=admin_headers)

    assert respuesta.status_code == 422


# --------------------------------------------------------------------------- #
# Asignación: POST /auth/usuarios/{usuario_id}/roles
# --------------------------------------------------------------------------- #


def test_asignar_sin_token_devuelve_401(api: TestClient):
    respuesta = api.post("/auth/usuarios/1/roles", json={"rol": "mecanico"})

    assert respuesta.status_code == 401


@pytest.mark.parametrize(
    "roles",
    [
        (NombreRol.CLIENTE,),
        (NombreRol.MECANICO,),
        (NombreRol.CLIENTE, NombreRol.MECANICO),
    ],
)
def test_asignar_sin_rol_administrador_devuelve_403(
    api: TestClient,
    roles: tuple[NombreRol, ...],
):
    respuesta = api.post(
        "/auth/usuarios/1/roles",
        json={"rol": "mecanico"},
        headers=_headers_para(99, *roles),
    )

    assert respuesta.status_code == 403


def test_asignar_a_usuario_de_un_rol_lo_convierte_en_multirol(
    api: TestClient,
    db: Session,
    admin_headers: dict[str, str],
):
    usuario_id = _registrar(api, "convierte@correo.cl")

    respuesta = api.post(
        f"/auth/usuarios/{usuario_id}/roles",
        json={"rol": "mecanico"},
        headers=admin_headers,
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["roles"] == ["cliente", "mecanico"]
    assert _roles_en_bd(db, usuario_id) == ["cliente", "mecanico"]


def test_asignar_acumula_los_tres_roles(
    api: TestClient,
    db: Session,
    admin_headers: dict[str, str],
):
    usuario_id = _registrar(api, "tresroles@correo.cl")

    for rol in ("mecanico", "administrador"):
        assert api.post(
            f"/auth/usuarios/{usuario_id}/roles",
            json={"rol": rol},
            headers=admin_headers,
        ).status_code == 200

    respuesta = api.get(f"/auth/usuarios/{usuario_id}", headers=admin_headers)
    assert respuesta.json()["roles"] == ["administrador", "cliente", "mecanico"]
    assert _roles_en_bd(db, usuario_id) == [
        "administrador",
        "cliente",
        "mecanico",
    ]


def test_asignar_el_mismo_rol_dos_veces_no_duplica(
    api: TestClient,
    db: Session,
    admin_headers: dict[str, str],
):
    usuario_id = _registrar(api, "idempotente@correo.cl")

    primera = api.post(
        f"/auth/usuarios/{usuario_id}/roles",
        json={"rol": "mecanico"},
        headers=admin_headers,
    )
    segunda = api.post(
        f"/auth/usuarios/{usuario_id}/roles",
        json={"rol": "mecanico"},
        headers=admin_headers,
    )

    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert primera.json() == segunda.json()
    assert _roles_en_bd(db, usuario_id) == ["cliente", "mecanico"]


def test_asignar_rol_desconocido_devuelve_422(
    api: TestClient,
    admin_headers: dict[str, str],
):
    respuesta = api.post(
        "/auth/usuarios/1/roles",
        json={"rol": "supervisor"},
        headers=admin_headers,
    )

    assert respuesta.status_code == 422


def test_asignar_a_usuario_inexistente_devuelve_404(
    api: TestClient,
    admin_headers: dict[str, str],
):
    respuesta = api.post(
        "/auth/usuarios/999999/roles",
        json={"rol": "mecanico"},
        headers=admin_headers,
    )

    assert respuesta.status_code == 404


# --------------------------------------------------------------------------- #
# Retirada: DELETE /auth/usuarios/{usuario_id}/roles/{rol}
# --------------------------------------------------------------------------- #


def test_retirar_sin_token_devuelve_401(api: TestClient):
    respuesta = api.delete("/auth/usuarios/1/roles/mecanico")

    assert respuesta.status_code == 401


@pytest.mark.parametrize(
    "roles",
    [
        (NombreRol.CLIENTE,),
        (NombreRol.MECANICO,),
        (NombreRol.CLIENTE, NombreRol.MECANICO),
    ],
)
def test_retirar_sin_rol_administrador_devuelve_403(
    api: TestClient,
    roles: tuple[NombreRol, ...],
):
    respuesta = api.delete(
        "/auth/usuarios/1/roles/mecanico", headers=_headers_para(99, *roles)
    )

    assert respuesta.status_code == 403


def test_retirar_un_rol_de_varios_conserva_los_demas(
    api: TestClient,
    db: Session,
    admin_headers: dict[str, str],
):
    usuario_id = _registrar(api, "conserva@correo.cl")
    _asignar_roles_bd(db, usuario_id, NombreRol.MECANICO)

    respuesta = api.delete(
        f"/auth/usuarios/{usuario_id}/roles/mecanico", headers=admin_headers
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["roles"] == ["cliente"]
    assert _roles_en_bd(db, usuario_id) == ["cliente"]


def test_retirar_el_ultimo_rol_deja_lista_vacia(
    api: TestClient,
    db: Session,
    admin_headers: dict[str, str],
):
    usuario_id = _registrar(api, "ultimo@correo.cl")

    respuesta = api.delete(
        f"/auth/usuarios/{usuario_id}/roles/cliente", headers=admin_headers
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["roles"] == []
    assert _roles_en_bd(db, usuario_id) == []


def test_retirar_es_idempotente(
    api: TestClient,
    db: Session,
    admin_headers: dict[str, str],
):
    usuario_id = _registrar(api, "retiro-idempotente@correo.cl")

    primera = api.delete(
        f"/auth/usuarios/{usuario_id}/roles/cliente", headers=admin_headers
    )
    segunda = api.delete(
        f"/auth/usuarios/{usuario_id}/roles/cliente", headers=admin_headers
    )

    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert primera.json() == segunda.json()
    assert _roles_en_bd(db, usuario_id) == []


def test_retirar_un_rol_no_asignado_responde_200(
    api: TestClient,
    db: Session,
    admin_headers: dict[str, str],
):
    usuario_id = _registrar(api, "no-asignado@correo.cl")

    respuesta = api.delete(
        f"/auth/usuarios/{usuario_id}/roles/mecanico", headers=admin_headers
    )

    assert respuesta.status_code == 200
    assert _roles_en_bd(db, usuario_id) == ["cliente"]


def test_retirar_a_usuario_inexistente_devuelve_404(
    api: TestClient,
    admin_headers: dict[str, str],
):
    respuesta = api.delete(
        "/auth/usuarios/999999/roles/mecanico", headers=admin_headers
    )

    assert respuesta.status_code == 404


def test_retirar_con_rol_desconocido_devuelve_422(
    api: TestClient,
    admin_headers: dict[str, str],
):
    respuesta = api.delete(
        "/auth/usuarios/1/roles/supervisor", headers=admin_headers
    )

    assert respuesta.status_code == 422


# --------------------------------------------------------------------------- #
# Consistencia: login, /auth/me y el token con uno y varios roles
# --------------------------------------------------------------------------- #


def test_login_emite_token_con_un_solo_rol(api: TestClient):
    _registrar(api, "login-uno@correo.cl")

    login = api.post(
        "/auth/login",
        json={"email": "login-uno@correo.cl", "password": CONTRASENA},
    )

    assert login.status_code == 200
    token = login.json()["access_token"]
    me = api.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["roles"] == ["cliente"]


def test_login_emite_token_con_varios_roles(
    api: TestClient,
    db: Session,
):
    usuario_id = _registrar(api, "login-varios@correo.cl")
    _asignar_roles_bd(db, usuario_id, NombreRol.MECANICO, NombreRol.ADMINISTRADOR)

    login = api.post(
        "/auth/login",
        json={"email": "login-varios@correo.cl", "password": CONTRASENA},
    )

    assert login.status_code == 200
    assert login.json()["user"]["roles"] == [
        "administrador",
        "cliente",
        "mecanico",
    ]
    token = login.json()["access_token"]
    me = api.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["roles"] == ["administrador", "cliente", "mecanico"]


def test_me_refleja_los_roles_actuales_tras_una_asignacion(
    api: TestClient,
    admin_headers: dict[str, str],
):
    """`/auth/me` consulta la base: ve el rol recién asignado con el token viejo."""

    usuario_id = _registrar(api, "me-actualiza@correo.cl")
    login = api.post(
        "/auth/login",
        json={"email": "me-actualiza@correo.cl", "password": CONTRASENA},
    )
    token = login.json()["access_token"]
    api.post(
        f"/auth/usuarios/{usuario_id}/roles",
        json={"rol": "mecanico"},
        headers=admin_headers,
    )

    me = api.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["roles"] == ["cliente", "mecanico"]
