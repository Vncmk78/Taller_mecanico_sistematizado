"""Unidad de trabajo (Unit of Work) de MS3: límites de transacción.

Un caso de uso completo (p. ej. "aprobar presupuesto y comprometer stock")
debe guardarse entero o no guardarse. La unidad de trabajo agrupa los
repositorios sobre UNA misma sesión y controla commit/rollback:

    def aprobar(uow: UnidadDeTrabajo, ...):
        with uow.transaccion():               # BEGIN
            version = ...
            uow.repuestos.obtener_para_actualizar(...)   # FOR UPDATE
            uow.movimientos.agregar(...)
            ...                                # si algo falla → ROLLBACK
                                               # si todo sale bien → COMMIT

- Si dentro del bloque se lanza cualquier excepción, se hace rollback y la
  excepción sigue su curso; un IntegrityError de la base se traduce a
  ConflictoDeDatos / ReglaDeDatosViolada (ver errores.py).
- Las transacciones anidadas usan SAVEPOINT: un error interno revierte solo
  lo del bloque anidado y la transacción externa puede continuar.
- Los repositorios nunca hacen commit: solo la unidad de trabajo.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.ms3_presupuestos.persistencia.errores import traducir_error_de_integridad
from services.ms3_presupuestos.persistencia.repositorios import (
    RepositorioMovimientos,
    RepositorioParametros,
    RepositorioPresupuestos,
    RepositorioProveedores,
    RepositorioRepuestos,
)


class UnidadDeTrabajo:
    """Repositorios de MS3 sobre una sesión compartida + control transaccional."""

    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion
        self.proveedores = RepositorioProveedores(sesion)
        self.repuestos = RepositorioRepuestos(sesion)
        self.movimientos = RepositorioMovimientos(sesion)
        self.parametros = RepositorioParametros(sesion)
        self.presupuestos = RepositorioPresupuestos(sesion)

    @contextmanager
    def transaccion(self) -> Iterator[UnidadDeTrabajo]:
        """Ejecuta el bloque como una transacción: commit al final o rollback.

        Si ya hay una transacción de esta unidad en curso, abre un SAVEPOINT
        (transacción anidada) para que un fallo interno no arrastre todo.
        """
        if self.sesion.in_transaction() and getattr(self, "_activa", False):
            with self._manejar_errores(), self.sesion.begin_nested():
                yield self
            return

        self._activa = True
        try:
            with self._manejar_errores():
                try:
                    yield self
                    self.sesion.commit()
                except BaseException:
                    self.sesion.rollback()
                    raise
        finally:
            self._activa = False

    @staticmethod
    @contextmanager
    def _manejar_errores() -> Iterator[None]:
        try:
            yield
        except IntegrityError as exc:
            raise traducir_error_de_integridad(exc) from exc

    def liberar_conexion(self) -> None:
        """Cierra la transacción de LECTURA abierta antes de llamar a otro servicio.

        SQLAlchemy abre una transacción con la primera consulta (autobegin). Si
        después el router llama por HTTP a MS2, la conexión queda "idle in
        transaction" todo lo que tarde MS2 (hasta MS2_TIMEOUT_SEGUNDOS) y, si MS2
        consulta de vuelta a MS3 (verificación de una decisión o un envío), esa
        consulta necesita OTRA conexión del pool. Con varias peticiones a la vez
        el pool se agota esperando. Cerrarla aquí no pierde nada: la sesión no
        expira objetos al confirmar (expire_on_commit=False).

        Solo para lecturas: si hay cambios sin confirmar o se llama dentro de
        `transaccion()`, es un error de programación.
        """
        if getattr(self, "_activa", False):
            raise RuntimeError("liberar_conexion() no se usa dentro de transaccion()")
        if self.sesion.new or self.sesion.dirty or self.sesion.deleted:
            raise RuntimeError("Hay cambios sin confirmar; use transaccion()")
        if self.sesion.in_transaction():
            self.sesion.commit()

    # Atajos para casos simples fuera de `transaccion()` (p. ej. un script).
    def commit(self) -> None:
        with self._manejar_errores():
            try:
                self.sesion.commit()
            except BaseException:
                self.sesion.rollback()
                raise

    def rollback(self) -> None:
        self.sesion.rollback()
