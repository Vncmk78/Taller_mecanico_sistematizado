"""Seed de usuarios de prueba para el despliegue (SGTM).

Crea en MS1 una cuenta controlada por cada rol y por cada combinación de roles:
las tres de un solo rol, las tres de dos roles y la que reúne a los tres (siete
en total), y en MS2 un perfil de Cliente por cada cuenta que incluya el rol
Cliente (MS1 y MS2 no comparten base: la relación Usuario↔Cliente es lógica,
§8). El script es idempotente: si una cuenta ya existe, la actualiza sin
duplicarla.

Credenciales (para documentar en CONEXIONES.md):
    cliente@pruebas.cl                        / ClientePrueba123!
    mecanico@pruebas.cl                       / MecanicoPrueba123!
    administrador@pruebas.cl                  / AdminPrueba123!
    cliente-mecanico@pruebas.cl               / ClienteMecanicoPrueba123!
    cliente-administrador@pruebas.cl          / ClienteAdministradorPrueba123!
    mecanico-administrador@pruebas.cl         / MecanicoAdministradorPrueba123!
    cliente-mecanico-administrador@pruebas.cl / ClienteMecanicoAdministradorPrueba123!

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
    # Combinaciones de dos roles.
    {
        "nombre": "Cliente y Mecánico de Prueba",
        "correo": "cliente-mecanico@pruebas.cl",
        "contrasena": "ClienteMecanicoPrueba123!",
        "roles": [NombreRol.CLIENTE, NombreRol.MECANICO],
        "telefono": "+56911111112",
    },
    {
        "nombre": "Cliente y Administrador de Prueba",
        "correo": "cliente-administrador@pruebas.cl",
        "contrasena": "ClienteAdministradorPrueba123!",
        "roles": [NombreRol.CLIENTE, NombreRol.ADMINISTRADOR],
        "telefono": "+56911111113",
    },
    {
        "nombre": "Mecánico y Administrador de Prueba",
        "correo": "mecanico-administrador@pruebas.cl",
        "contrasena": "MecanicoAdministradorPrueba123!",
        "roles": [NombreRol.MECANICO, NombreRol.ADMINISTRADOR],
    },
    # Los tres roles en la misma cuenta.
    {
        "nombre": "Cliente, Mecánico y Administrador de Prueba",
        "correo": "cliente-mecanico-administrador@pruebas.cl",
        "contrasena": "ClienteMecanicoAdministradorPrueba123!",
        "roles": [NombreRol.CLIENTE, NombreRol.MECANICO, NombreRol.ADMINISTRADOR],
        "telefono": "+56911111114",
    },
]


def _ocultar_correo(correo: str) -> str:
    """Enmascara el correo para poder identificar la cuenta sin imprimirlo.

    La salida de este script termina en los logs del despliegue, así que no debe
    contener datos de usuario en claro. Conserva el dominio y las iniciales, que
    es lo necesario para saber qué cuenta se sembró.
    """
    local, _, dominio = correo.partition("@")
    visible = local[:1]
    return f"{visible}***@{dominio}" if dominio else f"{visible}***"


def _sembrar_ms1() -> list[tuple[int, str]]:
    """Crea o actualiza las cuentas y sus roles en la base de MS1.

    Devuelve `(usuario_id, teléfono)` de cada cuenta con rol Cliente, que es lo
    necesario para su perfil en MS2.
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

        cuentas_cliente: list[tuple[int, str]] = []
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
                print(f"  + Usuario creado: {_ocultar_correo(correo)}")
            else:
                usuario.nombre = datos["nombre"]
                usuario.contrasena_hash = hash_contrasena(datos["contrasena"])
                usuario.activo = True
                print(f"  ~ Usuario actualizado: {_ocultar_correo(correo)}")

            roles_actuales = {a.rol.nombre for a in usuario.roles}
            for rol in datos["roles"]:
                if rol.value not in roles_actuales:
                    db.add(UsuarioRol(usuario=usuario, rol=roles_existentes[rol.value]))
                    print(f"    + Rol asignado: {rol.value}")
            db.flush()

            if NombreRol.CLIENTE in datos["roles"]:
                cuentas_cliente.append((usuario.usuario_id, datos["telefono"]))

        db.commit()
        if not cuentas_cliente:
            raise SystemExit("No se encontro ninguna cuenta con rol Cliente")
        return cuentas_cliente


def _sembrar_ms2(cuentas_cliente: list[tuple[int, str]]) -> None:
    """Crea en MS2 un perfil de Cliente por cada cuenta con rol Cliente."""
    with SessionLocalMS2() as db:
        for usuario_id, telefono in cuentas_cliente:
            perfil = db.scalar(
                select(Cliente).where(Cliente.usuario_id == usuario_id)
            )
            if perfil is not None:
                print(
                    f"  ~ Perfil Cliente ya existia (cliente_id={perfil.cliente_id})"
                )
                continue

            db.add(Cliente(usuario_id=usuario_id, telefono=telefono))
            print(f"  + Perfil Cliente creado en MS2 para usuario_id={usuario_id}")
        db.commit()


def main() -> None:
    print("Sembrando usuarios de prueba en MS1 (auth)...")
    cuentas_cliente = _sembrar_ms1()
    print("Sembrando perfiles Cliente en MS2 (taller)...")
    _sembrar_ms2(cuentas_cliente)
    print("Seed completado.")


if __name__ == "__main__":
    main()