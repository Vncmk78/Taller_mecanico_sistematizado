"""Pruebas del historial de cambios de roles (MS1).

Cada alta o baja de un rol debe dejar una fila en `historial_rol` con el rol, la
acción, el usuario responsable y la fecha/hora. Las operaciones idempotentes
(reasignar un rol ya presente, retirar uno ausente) no generan filas, y las
bajas conservan su registro aunque la fila de `usuario_rol` se borre.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.ms1_auth.config import settings
from services.ms1_auth.models.historial_rol import HistorialRol
from services.ms1_auth.models.rol import Rol, UsuarioRol
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


def _historial(db: Session, usuario_id: int) -> list[HistorialRol]:
    """Filas de historial de la cuenta, en orden cronológico."""

    return list(
        db.scalars(
            select(HistorialRol)
            .where(HistorialRol.usuario_id == usuario_id)
            .order_by(HistorialRol.historial_id)
        )
    )


def _nombre_rol(db: Session, rol_id: int) -> str:
    return db.scalar(select(Rol.nombre).where(Rol.rol_id == rol_id))


def _resumen(db: Session, filas: list[HistorialRol]) -> list[tuple[str, str]]:
    return [(fila.accion, _nombre_rol(db, fila.rol_id)) for fila in filas]


@pytest.fixture
def admin(api: TestClient, db: Session) -> tuple[int, dict[str, str]]:
    """Cuenta administradora real: id y cabecera Authorization."""

    usuario_id = _registrar(api, "admin-historial@correo.cl", "Admin Historial")
    _asignar_roles_bd(db, usuario_id, NombreRol.ADMINISTRADOR)
    return usuario_id, _headers_para(usuario_id, NombreRol.ADMINISTRADOR)


def test_registro_publico_registra_el_alta_inicial_sin_responsable(
    api: TestClient,
    db: Session,
):
    usuario_id = _registrar(api, "alta-inicial@correo.cl")

    filas = _historial(db, usuario_id)

    assert len(filas) == 1
    assert filas[0].accion == "asignado"
    assert filas[0].responsable_id is None
    assert filas[0].fecha_hora is not None
    assert _nombre_rol(db, filas[0].rol_id) == "cliente"


def test_asignar_rol_registra_el_cambio_con_responsable(
    api: TestClient,
    db: Session,
    admin: tuple[int, dict[str, str]],
):
    admin_id, admin_headers = admin
    usuario_id = _registrar(api, "asignar-historial@correo.cl")

    respuesta = api.post(
        f"/auth/usuarios/{usuario_id}/roles",
        json={"rol": "mecanico"},
        headers=admin_headers,
    )

    assert respuesta.status_code == 200
    filas = _historial(db, usuario_id)
    assert _resumen(db, filas) == [
        ("asignado", "cliente"),
        ("asignado", "mecanico"),
    ]
    assert filas[-1].responsable_id == admin_id
    assert filas[-1].fecha_hora is not None


def test_retirar_rol_registra_el_cambio_con_responsable(
    api: TestClient,
    db: Session,
    admin: tuple[int, dict[str, str]],
):
    admin_id, admin_headers = admin
    usuario_id = _registrar(api, "retirar-historial@correo.cl")

    respuesta = api.delete(
        f"/auth/usuarios/{usuario_id}/roles/cliente",
        headers=admin_headers,
    )

    assert respuesta.status_code == 200
    filas = _historial(db, usuario_id)
    assert _resumen(db, filas) == [
        ("asignado", "cliente"),
        ("retirado", "cliente"),
    ]
    assert filas[-1].responsable_id == admin_id
    assert filas[-1].fecha_hora is not None


def test_asignar_el_mismo_rol_dos_veces_no_duplica_historial(
    api: TestClient,
    db: Session,
    admin: tuple[int, dict[str, str]],
):
    _, admin_headers = admin
    usuario_id = _registrar(api, "idempotente-alta@correo.cl")

    for _ in range(2):
        respuesta = api.post(
            f"/auth/usuarios/{usuario_id}/roles",
            json={"rol": "mecanico"},
            headers=admin_headers,
        )
        assert respuesta.status_code == 200

    filas = _historial(db, usuario_id)
    assert _resumen(db, filas) == [
        ("asignado", "cliente"),
        ("asignado", "mecanico"),
    ]


def test_retirar_el_mismo_rol_dos_veces_no_duplica_historial(
    api: TestClient,
    db: Session,
    admin: tuple[int, dict[str, str]],
):
    _, admin_headers = admin
    usuario_id = _registrar(api, "idempotente-baja@correo.cl")

    for _ in range(2):
        respuesta = api.delete(
            f"/auth/usuarios/{usuario_id}/roles/cliente",
            headers=admin_headers,
        )
        assert respuesta.status_code == 200

    filas = _historial(db, usuario_id)
    assert _resumen(db, filas) == [
        ("asignado", "cliente"),
        ("retirado", "cliente"),
    ]


def test_historial_conserva_altas_y_bajas_del_mismo_rol(
    api: TestClient,
    db: Session,
    admin: tuple[int, dict[str, str]],
):
    admin_id, admin_headers = admin
    usuario_id = _registrar(api, "ciclo-historial@correo.cl")

    api.post(
        f"/auth/usuarios/{usuario_id}/roles",
        json={"rol": "mecanico"},
        headers=admin_headers,
    )
    api.delete(
        f"/auth/usuarios/{usuario_id}/roles/mecanico",
        headers=admin_headers,
    )

    filas = _historial(db, usuario_id)
    assert _resumen(db, filas) == [
        ("asignado", "cliente"),
        ("asignado", "mecanico"),
        ("retirado", "mecanico"),
    ]
    # El alta inicial la hizo el sistema; los otros dos, el administrador.
    assert filas[0].responsable_id is None
    assert all(fila.responsable_id == admin_id for fila in filas[1:])
