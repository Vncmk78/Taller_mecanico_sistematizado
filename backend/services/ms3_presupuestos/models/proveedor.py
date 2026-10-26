"""Modelos Proveedor y Repuesto (MS3: Presupuestos, repuestos y proveedores).

MER (recuadro "BD MS3"):
  PROVEEDOR(proveedor_id PK, nombre, contacto, tipo_distribuidor)
  REPUESTO(repuesto_id PK, proveedor_id FK, nombre, stock, umbral_particular?)
  HISTORIAL_PROVEEDOR_REPUESTO(historial_id PK, repuesto_id FK,
      proveedor_anterior_id? FK, proveedor_nuevo_id FK, registrado_por_id?,
      observacion?, fecha_hora)

Trazabilidad Repuesto–Proveedor/Distribuidor (migración 0007_ms3):
- `tipo_distribuidor`: "oficial" (distribuidor de la marca) o "generico".
- Cada cambio de proveedor de un repuesto (y su alta) queda en
  HISTORIAL_PROVEEDOR_REPUESTO: siempre se sabe quién lo abastecía y desde cuándo.
- Cada ingreso de stock guarda el proveedor que entregó esas unidades
  (movimiento_inventario.proveedor_id), aunque después el repuesto cambie de
  proveedor.
- Por eso un proveedor con historial no se borra (FK RESTRICT): es auditoría.

Relación 1:N FÍSICA (misma base MS3): un proveedor abastece varios repuestos y
cada repuesto tiene un proveedor.

Índices de búsqueda (migración 0006_ms3):
- ix_proveedor_nombre_trgm, ix_proveedor_contacto_trgm, ix_repuesto_nombre_trgm:
  GIN de trigramas sobre ms3_normalizar(col) para "contiene el texto" sin
  mayúsculas ni tildes. Solo existen en PostgreSQL (no se declaran aquí porque
  dependen de pg_trgm y de la función ms3_normalizar de la migración).
- ix_*_nombre_orden: listar ordenado por nombre y paginar.
- uq_proveedor_nombre_ci: proveedor único sin distinguir mayúsculas.

`stock` es la cantidad física disponible. Se actualiza junto con cada
MovimientoInventario (ver inventario.py), que es el registro auditable de por qué
cambió. `umbral_particular` vacío significa "usar el umbral general" (§4.6).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    event,
    func,
    inspect,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.ms3_presupuestos.db import Base

if TYPE_CHECKING:
    from services.ms3_presupuestos.models.inventario import MovimientoInventario

TIPOS_DISTRIBUIDOR = ("oficial", "generico")


class Proveedor(Base):
    __tablename__ = "proveedor"

    __table_args__ = (
        Index("uq_proveedor_nombre_ci", text("lower(nombre)"), unique=True),
        Index("ix_proveedor_nombre_orden", text("lower(nombre)"), "proveedor_id"),
        CheckConstraint("tipo_distribuidor in ('oficial', 'generico')",
                        name="tipo_distribuidor_valido"),
    )

    proveedor_id: Mapped[int] = mapped_column(primary_key=True)
    # Único: evita registrar dos veces el mismo proveedor.
    nombre: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    # Teléfono, correo o persona de contacto (texto libre).
    contacto: Mapped[str] = mapped_column(String(200), nullable=False)
    # Distribuidor oficial de la marca o genérico.
    tipo_distribuidor: Mapped[str] = mapped_column(
        String(10), nullable=False, default="generico", server_default="generico"
    )

    repuestos: Mapped[list["Repuesto"]] = relationship(
        back_populates="proveedor",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Proveedor proveedor_id={self.proveedor_id} nombre={self.nombre!r}>"


class Repuesto(Base):
    __tablename__ = "repuesto"

    __table_args__ = (
        # Umbrales no negativos (§4.6). El stock nunca queda bajo cero: un consumo
        # que lo dejaría negativo debe rechazarse.
        CheckConstraint("stock >= 0", name="stock_no_negativo"),
        CheckConstraint(
            "umbral_particular is null or umbral_particular >= 0",
            name="umbral_no_negativo",
        ),
        # Un proveedor no tiene dos repuestos con el mismo nombre (sin
        # distinguir mayúsculas): "Filtro de aceite" = "filtro de aceite".
        # Proveedores distintos sí pueden vender un repuesto homónimo.
        Index(
            "uq_repuesto_proveedor_nombre",
            "proveedor_id",
            text("lower(nombre)"),
            unique=True,
        ),
        Index("ix_repuesto_nombre_orden", text("lower(nombre)"), "repuesto_id"),
    )

    repuesto_id: Mapped[int] = mapped_column(primary_key=True)
    # RESTRICT: no se borra un proveedor que todavía tiene repuestos.
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedor.proveedor_id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    stock: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    umbral_particular: Mapped[int | None] = mapped_column(Integer, nullable=True)

    proveedor: Mapped["Proveedor"] = relationship(back_populates="repuestos")
    # Movimientos del repuesto. Sin cascada de borrado: son auditoría.
    movimientos: Mapped[list["MovimientoInventario"]] = relationship(
        back_populates="repuesto",
        cascade="save-update, merge",
        passive_deletes="all",
        lazy="select",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Repuesto repuesto_id={self.repuesto_id} stock={self.stock}>"


class HistorialProveedorRepuesto(Base):
    """Quién abastecía cada repuesto y desde cuándo (alta y cada cambio)."""

    __tablename__ = "historial_proveedor_repuesto"

    __table_args__ = (
        CheckConstraint(
            "proveedor_anterior_id is null or proveedor_anterior_id <> proveedor_nuevo_id",
            name="cambio_real",
        ),
        CheckConstraint("registrado_por_id is null or registrado_por_id > 0",
                        name="registrado_por_positivo"),
        Index("ix_historial_proveedor_repuesto_repuesto", "repuesto_id", "fecha_hora"),
    )

    historial_id: Mapped[int] = mapped_column(primary_key=True)
    # CASCADE: un repuesto solo se borra si nunca se usó; su historial se va con él.
    repuesto_id: Mapped[int] = mapped_column(
        ForeignKey("repuesto.repuesto_id", ondelete="CASCADE"), nullable=False)
    # Vacío = alta del repuesto (no tenía proveedor antes).
    proveedor_anterior_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedor.proveedor_id", ondelete="RESTRICT"), nullable=True, index=True)
    proveedor_nuevo_id: Mapped[int] = mapped_column(
        ForeignKey("proveedor.proveedor_id", ondelete="RESTRICT"), nullable=False, index=True)
    # REF lógica a MS1. Vacío solo en las filas creadas por la migración.
    registrado_por_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observacion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())

    proveedor_anterior: Mapped["Proveedor | None"] = relationship(
        foreign_keys=[proveedor_anterior_id], lazy="joined")
    proveedor_nuevo: Mapped["Proveedor"] = relationship(
        foreign_keys=[proveedor_nuevo_id], lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return (f"<HistorialProveedorRepuesto repuesto_id={self.repuesto_id} "
                f"{self.proveedor_anterior_id}->{self.proveedor_nuevo_id}>")


# ---------------------------------------------------------- trazabilidad --
# Los registros de trazabilidad se escriben con eventos del ORM para que NINGUNA
# forma de crear o mover un repuesto (API, semilla, pruebas) se los salte.
# Quién lo hizo y por qué se pasan en atributos transitorios del repuesto:
#   repuesto.registrado_por_id_traza = <usuario MS1>
#   repuesto.observacion_traza = "motivo"


def _insertar_historial(connection, repuesto: Repuesto, anterior: int | None) -> None:
    connection.execute(
        HistorialProveedorRepuesto.__table__.insert().values(
            repuesto_id=repuesto.repuesto_id,
            proveedor_anterior_id=anterior,
            proveedor_nuevo_id=repuesto.proveedor_id,
            registrado_por_id=getattr(repuesto, "registrado_por_id_traza", None),
            observacion=getattr(repuesto, "observacion_traza", None),
        )
    )


@event.listens_for(Repuesto, "after_insert")
def _historial_alta(_mapper, connection, repuesto: Repuesto) -> None:
    _insertar_historial(connection, repuesto, None)


@event.listens_for(Repuesto, "after_update")
def _historial_cambio_proveedor(_mapper, connection, repuesto: Repuesto) -> None:
    cambio = inspect(repuesto).attrs.proveedor_id.history
    if not cambio.has_changes() or not cambio.deleted:
        return
    anterior = cambio.deleted[0]
    if anterior is not None and anterior != repuesto.proveedor_id:
        _insertar_historial(connection, repuesto, anterior)
