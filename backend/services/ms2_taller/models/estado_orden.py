"""Catálogo EstadoOrden (MS2: Vehículos, órdenes y capacidad).

MER (recuadro "BD MS2"): ESTADO_ORDEN(estado_codigo PK, nombre UK).

Los ocho estados de la orden de trabajo (Sistematización §4.2) se guardan como
una tabla catálogo y no como texto libre en cada orden: así la orden y su
historial apuntan con una FK a un código válido y la base rechaza cualquier
estado inventado. Los valores se cargan en la propia migración (0003_ms2), no
desde la aplicación, para que toda base recién migrada tenga el catálogo completo.

Entregado (7) y Cancelado (8) son estados terminales (§4.8).
"""
from __future__ import annotations

from sqlalchemy import CheckConstraint, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from services.ms2_taller.db import Base

# Códigos fijos del catálogo. Se usan desde el código en vez de "números mágicos".
RECIBIDO = 1
ESPERANDO_DIAGNOSTICO = 2
ESPERANDO_APROBACION_PRESUPUESTO = 3
ESPERANDO_REPUESTOS = 4
EN_REPARACION = 5
LISTO = 6
ENTREGADO = 7
CANCELADO = 8

ESTADOS_ORDEN: dict[int, str] = {
    RECIBIDO: "Recibido",
    ESPERANDO_DIAGNOSTICO: "Esperando diagnóstico",
    ESPERANDO_APROBACION_PRESUPUESTO: "Esperando aprobación de presupuesto",
    ESPERANDO_REPUESTOS: "Esperando repuestos",
    EN_REPARACION: "En reparación",
    LISTO: "Listo",
    ENTREGADO: "Entregado",
    CANCELADO: "Cancelado",
}

ESTADOS_TERMINALES: frozenset[int] = frozenset({ENTREGADO, CANCELADO})


class EstadoOrden(Base):
    __tablename__ = "estado_orden"

    __table_args__ = (
        CheckConstraint("estado_codigo between 1 and 8", name="codigo_valido"),
    )

    # PK natural (código fijo del catálogo): sin autoincremento.
    estado_codigo: Mapped[int] = mapped_column(
        SmallInteger, primary_key=True, autoincrement=False
    )
    nombre: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EstadoOrden {self.estado_codigo} {self.nombre!r}>"
