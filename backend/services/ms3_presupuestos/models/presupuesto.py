"""Modelos de presupuesto (MS3: Presupuestos, repuestos y proveedores).

MER (recuadro "BD MS3"):
  PRESUPUESTO(presupuesto_id PK, orden_id UK/REF → MS2, creado_en)
  VERSION_PRESUPUESTO(version_id PK, presupuesto_id FK,
                      UK (presupuesto_id, numero), creado_en, enviado_en?,
                      creado_por_id REF → MS1)
  ITEM_PRESUPUESTO(item_id PK, version_id FK, tipo: repuesto / mano_de_obra,
                   repuesto_id? FK, descripcion, cantidad, precio_unitario)

Idea central (§4.3): el presupuesto es UNO por orden y lo que cambia son sus
VERSIONES. Una corrección no edita la versión enviada: crea otra versión con el
número siguiente. Los ítems cuelgan de la versión, no del presupuesto.

Versionado y bloqueo (Semana 3):

  borrador ──enviar──▶ enviada ──cliente aprueba──▶ aprobada (BLOQUEADA)
                           └────cliente rechaza───▶ rechazada (con motivo)

- Una versión se edita libremente mientras es BORRADOR (enviado_en vacío).
- Al ENVIARSE queda congelada: no cambian sus datos ni sus ítems. Corregirla
  significa crear la versión siguiente (numero + 1).
- La DecisionPresupuesto es única por versión y no se modifica ni se borra.
- Aprobar BLOQUEA la versión (bloqueada_en = fecha de la decisión). Una versión
  bloqueada no se vuelve a tocar nunca.
- es_modificacion = true marca una versión creada DESPUÉS de una aprobación
  (trabajo adicional). Si el cliente la rechaza, sigue vigente la última
  aprobación (§4.3).

Estas reglas las hace cumplir la BASE con triggers (migración 0003_ms3), así
que valen aunque alguien escriba SQL directo o un servicio se equivoque.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Boolean,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.ms3_presupuestos.db import Base

if TYPE_CHECKING:
    from services.ms3_presupuestos.models.proveedor import Repuesto


class Presupuesto(Base):
    __tablename__ = "presupuesto"

    __table_args__ = (
        CheckConstraint("orden_id > 0", name="orden_positiva"),
    )

    presupuesto_id: Mapped[int] = mapped_column(primary_key=True)
    # REF lógica a OrdenTrabajo (MS2). Única: un presupuesto por orden.
    # Sin ForeignKey a propósito (§8): la orden vive en otra base.
    orden_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Versiones en orden (1, 2, 3...). Sin borrado en cascada: las versiones
    # enviadas se conservan (§4.3).
    versiones: Mapped[list["VersionPresupuesto"]] = relationship(
        back_populates="presupuesto",
        cascade="save-update, merge",
        passive_deletes="all",
        order_by="VersionPresupuesto.numero",
        lazy="selectin",
    )

    @property
    def version_vigente(self) -> "VersionPresupuesto | None":
        """Última versión APROBADA: la que manda aunque existan otras después."""
        aprobadas = [v for v in self.versiones if v.bloqueada]
        return aprobadas[-1] if aprobadas else None

    @property
    def siguiente_numero(self) -> int:
        return (self.versiones[-1].numero + 1) if self.versiones else 1

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Presupuesto presupuesto_id={self.presupuesto_id} orden_id={self.orden_id}>"


class VersionPresupuesto(Base):
    __tablename__ = "version_presupuesto"

    __table_args__ = (
        # No puede haber dos "versión 2" del mismo presupuesto.
        UniqueConstraint("presupuesto_id", "numero"),
        CheckConstraint("numero >= 1", name="numero_positivo"),
        CheckConstraint("creado_por_id > 0", name="creado_por_positivo"),
        CheckConstraint(
            "enviado_en is null or enviado_en >= creado_en",
            name="envio_posterior",
        ),
        # Solo se bloquea una versión que ya fue enviada al cliente.
        CheckConstraint(
            "bloqueada_en is null or (enviado_en is not null and bloqueada_en >= enviado_en)",
            name="bloqueo_requiere_envio",
        ),
        # La primera versión nunca es modificación de una aprobación previa.
        CheckConstraint(
            "numero > 1 or not es_modificacion",
            name="primera_no_es_modificacion",
        ),
    )

    version_id: Mapped[int] = mapped_column(primary_key=True)
    # El índice lo cubre la UK (presupuesto_id, numero): empieza por presupuesto_id.
    presupuesto_id: Mapped[int] = mapped_column(
        ForeignKey("presupuesto.presupuesto_id", ondelete="RESTRICT"),
        nullable=False,
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    # REF lógica a Usuario (MS1).
    creado_por_id: Mapped[int] = mapped_column(Integer, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    enviado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # true = versión creada después de una aprobación (trabajo adicional).
    es_modificacion: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Lo completa el trigger al registrarse una aprobación. No se escribe a mano.
    bloqueada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    presupuesto: Mapped["Presupuesto"] = relationship(back_populates="versiones")
    decision: Mapped["DecisionPresupuesto | None"] = relationship(
        back_populates="version",
        uselist=False,
        lazy="selectin",
    )

    # --- Estado derivado (no se guarda: sale de las fechas y la decisión) ---
    @property
    def enviada(self) -> bool:
        return self.enviado_en is not None

    @property
    def bloqueada(self) -> bool:
        return self.bloqueada_en is not None

    @property
    def editable(self) -> bool:
        """Solo un borrador (no enviado) admite cambios en datos e ítems."""
        return not self.enviada
    # Los ítems SÍ se manejan junto con su versión (se crean con ella).
    items: Mapped[list["ItemPresupuesto"]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<VersionPresupuesto presupuesto_id={self.presupuesto_id} numero={self.numero}>"


class ItemPresupuesto(Base):
    __tablename__ = "item_presupuesto"

    __table_args__ = (
        CheckConstraint(
            "tipo in ('repuesto', 'mano_de_obra')", name="tipo_valido"
        ),
        # repuesto_id obligatorio para repuestos y vacío en mano de obra (MER).
        CheckConstraint(
            "(tipo = 'repuesto') = (repuesto_id is not null)",
            name="repuesto_segun_tipo",
        ),
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        CheckConstraint("precio_unitario >= 0", name="precio_no_negativo"),
    )

    item_id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("version_presupuesto.version_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(String(12), nullable=False)
    repuesto_id: Mapped[int | None] = mapped_column(
        ForeignKey("repuesto.repuesto_id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    descripcion: Mapped[str] = mapped_column(String(200), nullable=False)
    # Numeric: la mano de obra puede cobrarse en fracciones de hora (1.5 h) y el
    # dinero nunca se guarda en float (errores de redondeo).
    cantidad: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    version: Mapped["VersionPresupuesto"] = relationship(back_populates="items")
    repuesto: Mapped["Repuesto | None"] = relationship()

    @property
    def subtotal(self) -> Decimal:
        """cantidad × precio_unitario (calculado, no se guarda)."""
        return self.cantidad * self.precio_unitario

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ItemPresupuesto {self.tipo} {self.descripcion!r}>"


class DecisionPresupuesto(Base):
    """Decisión del cliente sobre una versión enviada (MER: DECISION_PRESUPUESTO).

    DECISION_PRESUPUESTO(decision_id PK, version_id UK/FK,
                         cliente_usuario_id REF → MS1, decision, fecha_hora,
                         motivo?)

    - Una sola decisión por versión (UK version_id).
    - Todo rechazo exige motivo (§4.3).
    - Al insertar una aprobación, el trigger bloquea la versión.
    - Es un registro histórico: no admite UPDATE ni DELETE.
    """

    __tablename__ = "decision_presupuesto"

    __table_args__ = (
        CheckConstraint(
            "decision in ('aprobado', 'rechazado')", name="decision_valida"
        ),
        CheckConstraint(
            "decision <> 'rechazado' or (motivo is not null and btrim(motivo) <> '')",
            name="rechazo_con_motivo",
        ),
        CheckConstraint("cliente_usuario_id > 0", name="cliente_positivo"),
    )

    decision_id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("version_presupuesto.version_id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    # REF lógica al usuario cliente (MS1). Sin ForeignKey a propósito (§8).
    cliente_usuario_id: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)

    version: Mapped["VersionPresupuesto"] = relationship(back_populates="decision")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DecisionPresupuesto version_id={self.version_id} {self.decision}>"
