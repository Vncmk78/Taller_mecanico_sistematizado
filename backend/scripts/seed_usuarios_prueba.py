"""Seed de usuarios de prueba para el despliegue (SGTM).

Crea en MS1 tres cuentas funcionales —Cliente, Mecánico y Administrador— con sus
roles, y en MS2 el perfil de Cliente correspondiente al usuario cliente (MS1 y
MS2 no comparten base: la relación Usuario↔Cliente es lógica, §8). El script es
idempotente: si una cuenta ya existe, la actualiza sin duplicarla.

Credenciales (para documentar en CONEXIONES.md):
    cliente@pruebas.cl      / ClientePrueba123!
    mecanico@pruebas.cl     / MecanicoPrueba123!
    administrador@pruebas.cl/ AdminPrueba123!

Uso (desde backend/ con las dependencias instaladas y .env con los DSN de Neon):
    python scripts/seed_usuarios_prueba.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.ms1_auth.db import SessionLocal as SessionLocalMS1
from services.ms1_auth.models.rol import Rol, UsuarioRol
from services.ms1_auth.models.usuario import Usuario
from services.ms1_auth.security.passwords import hash_contrasena
from services.ms2_taller.db import SessionLocal as SessionLocalMS2
from services.ms2_taller.models.cliente import Cliente
from shared.auth import NombreRol

# nombre_usuario, correo, contrasena, roles (en el orden en que aparecen)
USUARIOS = [
    {
        "nombre": "Cliente de Prueba",
        "correo": "cliente@pruebas.cl",
        "contrasena": "ClientePrueba123!",
        "roles": [NombreRol.CLIENTE],
        "telefono": "+56911111111",
    },
    {
        "nombre": "Mecánico de Prueba",
        "correo": "mecanico@pruebas.cl",
        "contrasena": "MecanicoPrueba123!",
        "roles": [NombreRol.MECANICO],
    },
    {
        "nombre": "Administrador de Prueba",
        "correo": "administrador@pruebas.cl",
        "contrasena": "AdminPrueba123!",
        "roles": [NombreRol.ADMINISTRADOR],
    },
]


def _sembrar_ms1() -> int:
    """Crea o actualiza las cuentas y sus roles en la base de MS1.

    Devuelve el usuario_id del cliente (necesario para su perfil en MS2).
    """
    with SessionLocalMS1() as db:
        roles_existentes = {
            rol.nombre: rol for rol in db.scalars(select(Rol)).all()
        }
        faltantes = [
            rol.value for rol in NombreRol if rol.value not in roles_existentes
        ]
        if faltantes:
            raise SystemExit(
                "Faltan roles en MS1 (corre primero las migraciones): "
                + ", ".join(faltantes)
            )

        usuario_id_cliente: int | None = None
        for datos in USUARIOS:
            correo = datos["correo"].strip().lower()
            usuario = db.scalar(select(Usuario).where(Usuario.correo == correo))

            if usuario is None:
                usuario = Usuario(
                    correo=correo,
                    nombre=datos["nombre"],
                    contrasena_hash=hash_contrasena(datos["contrasena"]),
                    activo=True,
                )
                db.add(usuario)
                db.flush()
                print(f"  + Usuario creado: {correo}")
            else:
                usuario.nombre = datos["nombre"]
                usuario.contrasena_hash = hash_contrasena(datos["contrasena"])
                usuario.activo = True
                print(f"  ~ Usuario actualizado: {correo}")

            roles_actuales = {a.rol.nombre for a in usuario.roles}
            for rol in datos["roles"]:
                if rol.value not in roles_actuales:
                    db.add(UsuarioRol(usuario=usuario, rol=roles_existentes[rol.value]))
                    print(f"    + Rol asignado: {rol.value}")
            db.flush()

            if NombreRol.CLIENTE in datos["roles"]:
                usuario_id_cliente = usuario.usuario_id

        db.commit()
        if usuario_id_cliente is None:
            raise SystemExit("No se encontro un usuario con rol Cliente")
        return usuario_id_cliente


def _sembrar_ms2(usuario_id: int) -> None:
    """Crea el perfil de Cliente en MS2 para el usuario cliente de MS1."""
    with SessionLocalMS2() as db:
        perfil = db.scalar(
            select(Cliente).where(Cliente.usuario_id == usuario_id)
        )
        if perfil is not None:
            print(f"  ~ Perfil Cliente ya existia (cliente_id={perfil.cliente_id})")
            return

        db.add(Cliente(usuario_id=usuario_id, telefono="+56911111111"))
        db.commit()
        print(f"  + Perfil Cliente creado en MS2 para usuario_id={usuario_id}")


def main() -> None:
    print("Sembrando usuarios de prueba en MS1 (auth)...")
    usuario_id_cliente = _sembrar_ms1()
    print("Sembrando perfil Cliente en MS2 (taller)...")
    _sembrar_ms2(usuario_id_cliente)
    print("Seed completado.")


if __name__ == "__main__":
    main()