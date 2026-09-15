"""Registro de modelos ORM.

Importar Base y todos los modelos aquí garantiza que Alembic y
Base.metadata "vean" todas las tablas al generar/ejecutar migraciones.
"""
from app.models.base import Base
from app.models.cliente import Cliente
from app.models.enums import RolUsuario
from app.models.usuario import Usuario
from app.models.vehiculo import Vehiculo

__all__ = ["Base", "RolUsuario", "Usuario", "Cliente", "Vehiculo"]
