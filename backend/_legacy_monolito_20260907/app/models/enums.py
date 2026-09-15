"""Enumeraciones del dominio.

El MER define el rol del usuario como 'cliente | mecanico | admin'. Se modela
como Enum para mantener el esquema idéntico al diagrama acordado por el equipo
y, a la vez, cubrir el "modelo Rol" pedido en el ticket de Semana 1.
"""
from __future__ import annotations

import enum


class RolUsuario(str, enum.Enum):
    cliente = "cliente"
    mecanico = "mecanico"
    admin = "admin"
