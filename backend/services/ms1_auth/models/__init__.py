"""Modelos ORM del microservicio MS1: Autenticación y Usuarios.

Se importan aquí TODOS los modelos del servicio para que `Base.metadata` (y por
lo tanto Alembic) los vea al generar y ejecutar las migraciones. Si un modelo no
aparece en este archivo, su tabla no entra en las migraciones.

Modelos iniciales (INT-13, Semana 1): Usuario, Rol, UsuarioRol.
Referencia: lámina 04-mer-erd, recuadro "BD MS1 | Identidad, acceso y notificaciones".
"""
from __future__ import annotations

from services.ms1_auth.db import Base
from services.ms1_auth.models.rol import Rol, UsuarioRol
from services.ms1_auth.models.usuario import Usuario

__all__ = ["Base", "Usuario", "Rol", "UsuarioRol"]
