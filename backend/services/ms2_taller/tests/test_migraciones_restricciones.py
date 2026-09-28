"""Pruebas rápidas de migración — MS2 (Semana 2).

Verifican que el esquema producido por las migraciones hasta `0005_ms2`
realmente hace cumplir en la base:

- las claves e índices esperados (PK, unicidad e índice de FK),
- las restricciones documentadas de vehículo y cliente,
- la unicidad de la referencia lógica `cliente.usuario_id`,
- el borrado en cascada de la FK `vehiculo.cliente_id`.

No prueban el ORM: van directo al SQL para comprobar lo que garantiza la BD.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def _nuevo_cliente(conn, usuario_id: int) -> int:
    """Inserta un cliente válido y devuelve su cliente_id."""
    return conn.execute(
        text("INSERT INTO cliente (usuario_id) VALUES (:u) RETURNING cliente_id"),
        {"u": usuario_id},
    ).scalar_one()


# --------------------------------------------------------------------------- #
# 1) Existencia de claves, índices y restricciones                            #
# --------------------------------------------------------------------------- #

def test_indices_esperados_existen(conn):
    filas = conn.execute(
        text(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename = 'vehiculo'"
        )
    ).all()
    indices = {nombre: definicion for nombre, definicion in filas}

    # Índice de la FK (búsquedas 'vehículos del cliente X').
    assert "ix_vehiculo_cliente_id" in indices
    # La restricción UNIQUE simple crea el índice físico de patente.
    assert "uq_vehiculo_patente" in indices
    definicion = indices["uq_vehiculo_patente"].lower()
    assert "unique" in definicion
    assert "upper" not in definicion


@pytest.mark.parametrize(
    "constraint",
    [
        "ck_vehiculo_patente_no_vacia",
        "ck_cliente_usuario_id_positivo",
    ],
)
def test_checks_esperados_existen(conn, constraint):
    existe = conn.execute(
        text(
            "SELECT 1 FROM pg_constraint WHERE conname = :n AND contype = 'c'"
        ),
        {"n": constraint},
    ).scalar_one_or_none()
    assert existe == 1, f"falta el CHECK {constraint}"


@pytest.mark.parametrize(
    "constraint",
    [
        "ck_vehiculo_patente_formato",
        "ck_vehiculo_anio_valido",
        "ck_vehiculo_km_no_negativo",
    ],
)
def test_checks_sin_respaldo_funcional_fueron_retirados(conn, constraint):
    existe = conn.execute(
        text("SELECT 1 FROM pg_constraint WHERE conname = :n AND contype = 'c'"),
        {"n": constraint},
    ).scalar_one_or_none()
    assert existe is None


# --------------------------------------------------------------------------- #
# 2) Unicidad (claves únicas)                                                 #
# --------------------------------------------------------------------------- #

def test_patente_duplicada_es_rechazada(conn):
    cid = _nuevo_cliente(conn, 1001)
    conn.execute(
        text(
            "INSERT INTO vehiculo (cliente_id, patente, marca, modelo) "
            "VALUES (:c, 'ABCD12', 'Toyota', 'Yaris')"
        ),
        {"c": cid},
    )
    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO vehiculo (cliente_id, patente, marca, modelo) "
                "VALUES (:c, 'ABCD12', 'Nissan', 'V16')"
            ),
            {"c": cid},
        )


def test_usuario_id_de_cliente_es_unico(conn):
    _nuevo_cliente(conn, 1002)
    with pytest.raises(IntegrityError):
        _nuevo_cliente(conn, 1002)


# --------------------------------------------------------------------------- #
# 3) Restricciones de dominio (CHECK)                                         #
# --------------------------------------------------------------------------- #

def test_patente_no_vacia_es_requerida(conn):
    cid = _nuevo_cliente(conn, 1003)
    with pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO vehiculo (cliente_id, patente, marca, modelo) "
                "VALUES (:c, '   ', 'Kia', 'Rio')"
            ),
            {"c": cid},
        )


def test_patente_no_impone_formato_o_largo_no_documentado(conn):
    cid = _nuevo_cliente(conn, 1004)
    conn.execute(
        text(
            "INSERT INTO vehiculo (cliente_id, patente, marca, modelo) "
            "VALUES (:c, 'a', 'Kia', 'Rio')"
        ),
        {"c": cid},
    )


def test_anio_y_kilometraje_no_tienen_rangos_no_documentados(conn):
    cid = _nuevo_cliente(conn, 1005)
    conn.execute(
        text(
            "INSERT INTO vehiculo "
            "(cliente_id, patente, marca, modelo, anio, kilometraje) "
            "VALUES (:c, 'sin-formato-prescrito', 'Kia', 'Rio', 1200, -5)"
        ),
        {"c": cid},
    )


def test_usuario_id_no_positivo_es_rechazado(conn):
    with pytest.raises(IntegrityError):
        conn.execute(text("INSERT INTO cliente (usuario_id) VALUES (0)"))


# --------------------------------------------------------------------------- #
# 4) Integridad referencial (FK con ON DELETE CASCADE)                        #
# --------------------------------------------------------------------------- #

def test_borrar_cliente_borra_sus_vehiculos_en_cascada(conn):
    cid = _nuevo_cliente(conn, 1006)
    conn.execute(
        text(
            "INSERT INTO vehiculo (cliente_id, patente, marca, modelo) "
            "VALUES (:c, 'CASC01', 'Ford', 'Focus')"
        ),
        {"c": cid},
    )
    conn.execute(text("DELETE FROM cliente WHERE cliente_id = :c"), {"c": cid})
    restantes = conn.execute(
        text("SELECT count(*) FROM vehiculo WHERE cliente_id = :c"), {"c": cid}
    ).scalar_one()
    assert restantes == 0
