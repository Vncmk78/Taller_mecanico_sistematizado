"""Capa de persistencia de MS3: repositorios, unidad de trabajo y errores.

    router (HTTP)
      └─ services (reglas de negocio)
           └─ UnidadDeTrabajo  ← una transacción por caso de uso
                ├─ repositorios (consultas y altas, SIN commit)
                └─ Session de SQLAlchemy (get_db)

- Los REPOSITORIOS encapsulan el acceso a datos de un agregado: buscar,
  listar, agregar. Nunca hacen commit ni rollback.
- La UNIDAD DE TRABAJO decide los límites de la transacción: todo lo que se
  hace dentro de `with uow.transaccion():` se confirma junto o se revierte
  junto.
- Los ERRORES de la base (UNIQUE, CHECK, FK, triggers) se traducen a errores
  propios del servicio, que main.py convierte en 404 / 409 / 422.
"""
from __future__ import annotations

from services.ms3_presupuestos.persistencia.errores import (
    ConflictoDeDatos,
    ErrorDePersistencia,
    RecursoNoEncontrado,
    ReglaDeDatosViolada,
    traducir_error_de_integridad,
)
from services.ms3_presupuestos.persistencia.repositorios import (
    RepositorioBase,
    RepositorioMovimientos,
    RepositorioParametros,
    RepositorioPresupuestos,
    RepositorioProveedores,
    RepositorioRepuestos,
)
from services.ms3_presupuestos.persistencia.unidad_de_trabajo import UnidadDeTrabajo

__all__ = [
    "ConflictoDeDatos",
    "ErrorDePersistencia",
    "RecursoNoEncontrado",
    "ReglaDeDatosViolada",
    "RepositorioBase",
    "RepositorioMovimientos",
    "RepositorioParametros",
    "RepositorioPresupuestos",
    "RepositorioProveedores",
    "RepositorioRepuestos",
    "UnidadDeTrabajo",
    "traducir_error_de_integridad",
]
