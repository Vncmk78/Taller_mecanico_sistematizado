"""Errores de persistencia de MS3 y su traducción desde la base de datos.

PostgreSQL informa por qué rechazó una operación con un código SQLSTATE:

    23505  unique_violation       → ConflictoDeDatos     (409): ya existe
    23503  foreign_key_violation  → ReglaDeDatosViolada  (422): referencia inválida
                                                                o registro en uso
    23514  check_violation        → ReglaDeDatosViolada  (422): regla del dominio
    23502  not_null_violation     → ReglaDeDatosViolada  (422): falta un dato

Los triggers de versionado (migración 0003_ms3) lanzan sus errores con
ERRCODE 'check_violation', así que caen en ReglaDeDatosViolada con su mensaje
en español ("La versión 1 ya fue enviada...").

Así los routers no dependen de SQLAlchemy ni de psycopg: capturan estas
excepciones (o dejan que main.py las convierta en respuestas HTTP).
"""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError

UNIQUE_VIOLATION = "23505"
FOREIGN_KEY_VIOLATION = "23503"
CHECK_VIOLATION = "23514"
NOT_NULL_VIOLATION = "23502"


class ErrorDePersistencia(Exception):
    """Base de los errores de la capa de datos de MS3."""

    codigo_http: int = 500

    def __init__(self, mensaje: str, *, restriccion: str | None = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        # Nombre de la restricción violada (p. ej. uq_proveedor_nombre); útil
        # para que un service dé un mensaje más específico.
        self.restriccion = restriccion


class RecursoNoEncontrado(ErrorDePersistencia):
    codigo_http = 404


class ConflictoDeDatos(ErrorDePersistencia):
    """El dato ya existe (clave única repetida)."""

    codigo_http = 409


class ReglaDeDatosViolada(ErrorDePersistencia):
    """La base rechazó el dato por una regla (CHECK, FK, NOT NULL o trigger)."""

    codigo_http = 422


def _sqlstate(exc: IntegrityError) -> str | None:
    return getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)


def _restriccion(exc: IntegrityError) -> str | None:
    diag = getattr(exc.orig, "diag", None)
    return getattr(diag, "constraint_name", None)


def _mensaje_base(exc: IntegrityError) -> str:
    """Primera línea del mensaje de PostgreSQL (sin SQL ni parámetros)."""
    diag = getattr(exc.orig, "diag", None)
    principal = getattr(diag, "message_primary", None)
    if principal:
        return principal
    return str(exc.orig).splitlines()[0] if exc.orig is not None else str(exc)


def traducir_error_de_integridad(exc: IntegrityError) -> ErrorDePersistencia:
    """Convierte un IntegrityError de SQLAlchemy en un error propio de MS3."""
    estado = _sqlstate(exc)
    restriccion = _restriccion(exc)
    if estado == UNIQUE_VIOLATION:
        return ConflictoDeDatos(
            "Ya existe un registro con esos datos", restriccion=restriccion
        )
    if estado == FOREIGN_KEY_VIOLATION:
        return ReglaDeDatosViolada(
            "El registro referenciado no existe o está en uso", restriccion=restriccion
        )
    if estado == CHECK_VIOLATION:
        # Los triggers traen un mensaje de negocio claro; los CHECK traen el
        # nombre de la restricción. En ambos casos se conserva el texto de la base.
        return ReglaDeDatosViolada(_mensaje_base(exc), restriccion=restriccion)
    if estado == NOT_NULL_VIOLATION:
        return ReglaDeDatosViolada("Falta un dato obligatorio", restriccion=restriccion)
    return ErrorDePersistencia("No fue posible guardar los datos", restriccion=restriccion)
