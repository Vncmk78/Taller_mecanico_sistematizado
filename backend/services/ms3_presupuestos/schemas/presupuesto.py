"""Contratos HTTP de presupuestos (MS3).

Entrada:  PresupuestoCrear (orden + ítems de la versión 1) e ItemsVersion
          (reemplaza los ítems de una versión en borrador).
Salida:   PresupuestoDetalle (con todas sus versiones), PresupuestoResumen
          (listados) y VersionDetalle.

Dinero y cantidades viajan como Decimal; en JSON se serializan como texto
("38990.00") para no perder precisión.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TipoItem = Literal["repuesto", "mano_de_obra"]
EstadoVersion = Literal["borrador", "enviada", "aprobada", "rechazada"]

MAX_ITEMS_POR_VERSION = 100


# ------------------------------------------------------------------ entrada --

class ItemEntrada(BaseModel):
    """Un trabajo (mano de obra) o un repuesto propuesto en la versión."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tipo: TipoItem
    descripcion: str = Field(min_length=1, max_length=200)
    cantidad: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    # El mecánico puede proponer el trabajo sin precio; el administrador
    # revisa y completa los importes antes de enviar (§4.3).
    precio_unitario: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=2
    )
    repuesto_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _repuesto_segun_tipo(self) -> "ItemEntrada":
        if self.tipo == "repuesto" and self.repuesto_id is None:
            raise ValueError("Un ítem de tipo repuesto requiere repuesto_id")
        if self.tipo == "mano_de_obra" and self.repuesto_id is not None:
            raise ValueError("Un ítem de mano de obra no lleva repuesto_id")
        return self


class ItemsVersion(BaseModel):
    """Lista completa de ítems de una versión en borrador (reemplaza la anterior)."""

    model_config = ConfigDict(extra="forbid")

    items: list[ItemEntrada] = Field(max_length=MAX_ITEMS_POR_VERSION)


class PresupuestoCrear(ItemsVersion):
    """Crea el presupuesto lógico de una orden con su versión 1 en borrador."""

    orden_id: int = Field(gt=0)
    items: list[ItemEntrada] = Field(default_factory=list, max_length=MAX_ITEMS_POR_VERSION)


class DecisionEntrada(BaseModel):
    """Decisión del cliente sobre la versión enviada (§4.3)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: Literal["aprobado", "rechazado"]
    motivo: str | None = Field(default=None, max_length=1000)
    # Antes de la primera aprobación, rechazar = rechazar el servicio y la
    # orden se cancela: el cliente debe confirmarlo explícitamente.
    confirmar_cancelacion: bool = False

    @model_validator(mode="after")
    def _rechazo_con_motivo(self) -> "DecisionEntrada":
        if self.decision == "rechazado" and not self.motivo:
            raise ValueError("Todo rechazo exige un motivo")
        return self


# ------------------------------------------------------------------- salida --

class ItemSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: int
    tipo: TipoItem
    descripcion: str
    cantidad: Decimal
    precio_unitario: Decimal
    subtotal: Decimal
    repuesto_id: int | None
    # Procedencia visible para el cliente (§4.3): repuesto y su proveedor.
    repuesto_nombre: str | None = None
    proveedor_nombre: str | None = None


class DecisionSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision: Literal["aprobado", "rechazado"]
    cliente_usuario_id: int
    fecha_hora: datetime
    motivo: str | None


class VersionDetalle(BaseModel):
    numero: int
    estado: EstadoVersion
    es_modificacion: bool
    creado_por_id: int
    creado_en: datetime
    enviado_en: datetime | None
    bloqueada_en: datetime | None
    total: Decimal
    items: list[ItemSalida]
    decision: DecisionSalida | None


class PresupuestoResumen(BaseModel):
    presupuesto_id: int
    orden_id: int
    creado_en: datetime
    cantidad_versiones: int
    ultima_version: int
    estado_ultima_version: EstadoVersion
    total_ultima_version: Decimal
    # Número de la última versión APROBADA (alcance autorizado), si existe.
    version_vigente: int | None


class PresupuestoDetalle(PresupuestoResumen):
    versiones: list[VersionDetalle]


class PaginaPresupuestos(BaseModel):
    total: int
    desde: int
    limite: int
    presupuestos: list[PresupuestoResumen]


EfectoOrden = Literal["esperando_aprobacion", "en_reparacion", "esperando_repuestos", "cancelado"]


class RepuestoFaltante(BaseModel):
    repuesto_id: int
    nombre: str
    requerido: Decimal
    disponible: int


class ResultadoOperacion(BaseModel):
    """Resultado de enviar o decidir: el presupuesto y lo que implica para la orden.

    MS3 no cambia el estado de la orden (vive en MS2, §8): informa el efecto
    que corresponde según §4.2 para que se aplique en MS2. `null` = la orden
    no cambia (p. ej. envío o rechazo de una modificación posterior).
    """

    presupuesto: PresupuestoDetalle
    efecto_en_orden: EfectoOrden | None
    repuestos_faltantes: list[RepuestoFaltante] = []
