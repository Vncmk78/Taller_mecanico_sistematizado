"""Modelos de inventario/stock (MS3: Presupuestos, repuestos y proveedores).

MER (recuadro "BD MS3"):
  MOVIMIENTO_INVENTARIO(movimiento_id PK, clave_operacion UK, repuesto_id FK,
                        proveedor_id? FK (solo ingresos),
                        orden_id? REF → MS2, tipo, cantidad, fecha_hora,
                        registrado_por_id REF → MS1)
  PARAMETRO_INVENTARIO(parametro_id PK, umbral_general,
                       actualizado_por_id REF → MS1, vigente_desde, vigente_hasta?)

MovimientoInventario (§4.6):
- Cada cambio de stock queda registrado como un movimiento. Tipos:
  compromiso (se reserva para una orden), consumo (se usa en la orden),
  liberacion (se suelta un compromiso), ajuste (corrección manual) e ingreso
  (entra mercadería del proveedor).
- `clave_operacion` es ÚNICA: si la misma operación llega dos veces (reintento,
  doble clic), la base rechaza el duplicado. Así un consumo no se descuenta dos
  veces ("los consumos controlan duplicados").
- Compromiso, consumo y liberación siempre se vinculan a una orden (REF lógica
  a MS2, sin FK, §8).

ParametroInventario: el umbral GENERAL de alerta de stock, con vigencia. Solo
puede haber un parámetro vigente a la vez (vigente_hasta vacío).
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    event,
    func,
    select,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.ms3_presupuestos.db import Base

if TYPE_CHECKING:
    from services.ms3_presupuestos.models.proveedor import Repuesto

TIPOS_MOVIMIENTO = ("compromiso", "consumo", "liberacion", "ajuste", "ingreso")
# Tipos que siempre pertenecen a una orden de trabajo.
TIPOS_CON_ORDEN = ("compromiso", "consumo", "liberacion")


class MovimientoInventario(Base):
    __tablename__ = "movimiento_inventario"

    __table_args__ = (
        CheckConstraint(
            "tipo in ('compromiso', 'consumo', 'liberacion', 'ajuste', 'ingreso')",
            name="tipo_valido",
        ),
        # Los ajustes pueden sumar o restar (distinto de cero); el resto siempre
        # es una cantidad positiva y el tipo indica el sentido.
        CheckConstraint(
            "(tipo = 'ajuste' and cantidad <> 0) or (tipo <> 'ajuste' and cantidad > 0)",
            name="cantidad_valida",
        ),
        CheckConstraint(
            "tipo not in ('compromiso', 'consumo', 'liberacion') or orden_id is not null",
            name="orden_obligatoria",
        ),
        CheckConstraint("orden_id is null or orden_id > 0", name="orden_positiva"),
        CheckConstraint("registrado_por_id > 0", name="registrado_por_positivo"),
        # Trazabilidad: todo ingreso dice qué proveedor entregó las unidades;
        # los demás movimientos no llevan proveedor.
        CheckConstraint(
            "(tipo = 'ingreso' and proveedor_id is not null) or "
            "(tipo <> 'ingreso' and proveedor_id is null)",
            name="proveedor_solo_en_ingreso",
        ),
        # Índices de consulta: ver al final del archivo (0008_ms3).
    )

    movimiento_id: Mapped[int] = mapped_column(primary_key=True)
    clave_operacion: Mapped[str] = mapped_column(
        String(80), unique=True, nullable=False
    )
    repuesto_id: Mapped[int] = mapped_column(
        ForeignKey("repuesto.repuesto_id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Proveedor que entregó las unidades (solo en ingresos).
    proveedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedor.proveedor_id", ondelete="RESTRICT"), nullable=True)
    # REF lógica a OrdenTrabajo (MS2). Sin ForeignKey a propósito (§8).
    orden_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tipo: Mapped[str] = mapped_column(String(12), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    # REF lógica a Usuario (MS1).
    registrado_por_id: Mapped[int] = mapped_column(Integer, nullable=False)

    repuesto: Mapped["Repuesto"] = relationship(back_populates="movimientos")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<MovimientoInventario {self.tipo} repuesto_id={self.repuesto_id} "
            f"cantidad={self.cantidad}>"
        )


class ParametroInventario(Base):
    __tablename__ = "parametro_inventario"

    __table_args__ = (
        CheckConstraint("umbral_general >= 0", name="umbral_no_negativo"),
        CheckConstraint("actualizado_por_id > 0", name="actualizado_por_positivo"),
        CheckConstraint(
            "vigente_hasta is null or vigente_hasta > vigente_desde",
            name="vigencia_valida",
        ),
        # Índice único PARCIAL: a lo más una fila con vigente_hasta vacío, es
        # decir, un único umbral general vigente.
        Index(
            "uq_parametro_inventario_vigente",
            text("(vigente_hasta is null)"),
            unique=True,
            postgresql_where=text("vigente_hasta is null"),
        ),
    )

    parametro_id: Mapped[int] = mapped_column(primary_key=True)
    umbral_general: Mapped[int] = mapped_column(Integer, nullable=False)
    # REF lógica a Usuario (MS1): administrador que lo configuró.
    actualizado_por_id: Mapped[int] = mapped_column(Integer, nullable=False)
    vigente_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    vigente_hasta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ParametroInventario umbral_general={self.umbral_general}>"


# --------------------------------------------------------------------------- #
# Índices de las consultas de inventario y trazabilidad (revisión 0008_ms3).   #
# Cada uno corresponde a una consulta del repositorio; las pruebas de          #
# test_indices_inventario.py verifican con EXPLAIN que se usan.               #
# --------------------------------------------------------------------------- #
_M = MovimientoInventario
# Saldo reservado por orden (comprometido_por_orden): historial del repuesto en
# orden de movimiento, solo con orden. INCLUDE → lectura solo del índice.
Index("ix_movimiento_inventario_saldo", _M.repuesto_id, _M.movimiento_id,
      postgresql_include=["orden_id", "tipo", "cantidad"],
      postgresql_where=text("orden_id is not null"))
# Movimientos de un repuesto, más recientes primero (listado paginado). Su
# primera columna también sirve a la FK repuesto_id.
Index("ix_movimiento_inventario_repuesto_fecha",
      _M.repuesto_id, _M.fecha_hora.desc(), _M.movimiento_id.desc())
# Movimientos de una orden (listado, consumido por orden, liberación).
Index("ix_movimiento_inventario_orden_fecha",
      _M.orden_id, _M.fecha_hora.desc(), _M.movimiento_id.desc(),
      postgresql_where=text("orden_id is not null"))
# Ingresos de un proveedor (trazabilidad del proveedor y filtro proveedor_id).
Index("ix_movimiento_inventario_proveedor_fecha",
      _M.proveedor_id, _M.fecha_hora.desc(), _M.movimiento_id.desc(),
      postgresql_include=["repuesto_id", "cantidad"],
      postgresql_where=text("proveedor_id is not null"))
# Ingresos de un repuesto agrupados por proveedor (trazabilidad del repuesto).
Index("ix_movimiento_inventario_ingresos", _M.repuesto_id, _M.proveedor_id,
      postgresql_include=["cantidad", "fecha_hora"],
      postgresql_where=text("tipo = 'ingreso'"))

@event.listens_for(MovimientoInventario, "before_insert")
def _proveedor_del_ingreso(_mapper, connection, movimiento: MovimientoInventario) -> None:
    """Un ingreso sin proveedor explícito lo recibe del proveedor actual del repuesto."""
    if movimiento.tipo != "ingreso" or movimiento.proveedor_id is not None:
        return
    from services.ms3_presupuestos.models.proveedor import Repuesto

    repuesto_id = movimiento.repuesto_id or (movimiento.repuesto and movimiento.repuesto.repuesto_id)
    movimiento.proveedor_id = connection.scalar(
        select(Repuesto.proveedor_id).where(Repuesto.repuesto_id == repuesto_id))
