"""Pruebas unitarias del patrón de persistencia de MS3 (sin base de datos).

- La unidad de trabajo hace commit si el bloque termina bien y rollback si
  falla; traduce IntegrityError a errores propios.
- La traducción de SQLSTATE → error propio → código HTTP.
- main.py convierte los errores de persistencia en respuestas 404/409/422
  sin exponer SQL.

Las pruebas contra PostgreSQL real están en services/ms3_presupuestos/tests.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.ms3_presupuestos.main import app
from services.ms3_presupuestos.persistencia import (
    ConflictoDeDatos,
    ErrorDePersistencia,
    RecursoNoEncontrado,
    ReglaDeDatosViolada,
    UnidadDeTrabajo,
    traducir_error_de_integridad,
)


def _integrity(sqlstate: str, mensaje: str = "fallo", restriccion: str | None = None) -> IntegrityError:
    """IntegrityError con un `orig` que imita a psycopg (sqlstate + diag)."""
    orig = SimpleNamespace(
        sqlstate=sqlstate,
        diag=SimpleNamespace(constraint_name=restriccion, message_primary=mensaje),
    )
    return IntegrityError("INSERT ...", {}, orig)


# --------------------------------------------------------- traducción de errores --

@pytest.mark.parametrize(
    ("sqlstate", "tipo", "http"),
    [
        ("23505", ConflictoDeDatos, 409),
        ("23503", ReglaDeDatosViolada, 422),
        ("23514", ReglaDeDatosViolada, 422),
        ("23502", ReglaDeDatosViolada, 422),
        ("99999", ErrorDePersistencia, 500),
    ],
)
def test_sqlstate_se_traduce_al_error_y_codigo_correctos(sqlstate, tipo, http) -> None:
    error = traducir_error_de_integridad(_integrity(sqlstate, restriccion="uq_x"))
    assert type(error) is tipo
    assert error.codigo_http == http
    assert error.restriccion == "uq_x"


def test_violacion_de_trigger_conserva_el_mensaje_de_negocio() -> None:
    mensaje = "La versión 4 ya fue enviada; sus ítems no se pueden modificar"
    error = traducir_error_de_integridad(_integrity("23514", mensaje))
    assert error.mensaje == mensaje


# ------------------------------------------------------------ unidad de trabajo --

def _uow() -> tuple[UnidadDeTrabajo, MagicMock]:
    sesion = MagicMock(spec=Session)
    return UnidadDeTrabajo(sesion), sesion


def test_bloque_exitoso_hace_commit_y_no_rollback() -> None:
    uow, sesion = _uow()
    with uow.transaccion():
        uow.proveedores.agregar(object())
    sesion.commit.assert_called_once()
    sesion.rollback.assert_not_called()


def test_excepcion_en_el_bloque_hace_rollback_y_se_propaga() -> None:
    uow, sesion = _uow()
    with pytest.raises(ValueError):
        with uow.transaccion():
            raise ValueError("regla de negocio")
    sesion.rollback.assert_called_once()
    sesion.commit.assert_not_called()


def test_integrity_error_se_traduce_y_hace_rollback() -> None:
    uow, sesion = _uow()
    sesion.flush.side_effect = _integrity("23505")
    with pytest.raises(ConflictoDeDatos):
        with uow.transaccion():
            uow.proveedores.agregar(object())
    sesion.rollback.assert_called_once()
    sesion.commit.assert_not_called()


def test_error_en_commit_tambien_se_traduce() -> None:
    uow, sesion = _uow()
    sesion.commit.side_effect = _integrity("23514", "stock negativo")
    with pytest.raises(ReglaDeDatosViolada, match="stock negativo"):
        with uow.transaccion():
            pass
    sesion.rollback.assert_called_once()


def test_repositorios_comparten_la_misma_sesion() -> None:
    uow, sesion = _uow()
    repos = [uow.proveedores, uow.repuestos, uow.movimientos, uow.parametros, uow.presupuestos]
    assert all(r.sesion is sesion for r in repos)


def test_obtener_o_error_lanza_no_encontrado() -> None:
    uow, sesion = _uow()
    sesion.get.return_value = None
    with pytest.raises(RecursoNoEncontrado, match="Repuesto 99 no existe"):
        uow.repuestos.obtener_o_error(99)


# --------------------------------------------------------- respuesta HTTP --------

@pytest.mark.parametrize(
    ("error", "http"),
    [
        (RecursoNoEncontrado("Presupuesto 5 no existe"), 404),
        (ConflictoDeDatos("Ya existe un registro con esos datos"), 409),
        (ReglaDeDatosViolada("La versión 1 ya fue enviada"), 422),
    ],
)
def test_main_convierte_errores_de_persistencia_en_http(error, http) -> None:
    ruta = f"/_prueba_error_{http}"

    @app.get(ruta, include_in_schema=False)
    def _lanza() -> None:
        raise error

    try:
        respuesta = TestClient(app).get(ruta)
    finally:
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", "") != ruta]
    assert respuesta.status_code == http
    assert respuesta.json() == {"detail": error.mensaje}
