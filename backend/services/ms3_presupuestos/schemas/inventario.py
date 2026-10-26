"""Contratos HTTP de inventario y stock (MS3, §4.6).

Conceptos:
- stock        unidades físicas en bodega (columna repuesto.stock).
- comprometido unidades reservadas para órdenes y aún no consumidas ni
               liberadas (Σ compromisos − liberaciones − consumos, por orden).
- disponible   stock − comprometido: lo que se puede ofrecer a otra orden.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TipoMovimiento = Literal["ingreso", "ajuste", "compromiso", "consumo", "liberacion"]
TIPOS_CON_ORDEN = ("compromiso", "consumo", "liberacion")


class MovimientoCrear(BaseModel):
    """Un movimiento de stock. `clave_operacion` hace la operación idempotente:
    reenviar la misma petición (reintento, doble clic) no descuenta dos veces."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    clave_operacion: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9._:-]+$",
                                 description="Identificador único generado por el cliente (p. ej. un UUID)")
    repuesto_id: int = Field(gt=0)
    tipo: TipoMovimiento
    # Ajuste: positivo suma, negativo resta. El resto: siempre positivo.
    cantidad: int = Field(ge=-1_000_000, le=1_000_000)
    orden_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _reglas_por_tipo(self) -> "MovimientoCrear":
        if self.tipo == "ajuste":
            if self.cantidad == 0:
                raise ValueError("Un ajuste no puede ser 0")
        elif self.cantidad <= 0:
            raise ValueError(f"La cantidad de un {self.tipo} debe ser positiva")
        if self.tipo in TIPOS_CON_ORDEN and self.orden_id is None:
            raise ValueError(f"Un {self.tipo} debe indicar orden_id")
        if self.tipo not in TIPOS_CON_ORDEN and self.orden_id is not None:
            raise ValueError(f"Un {self.tipo} no se asocia a una orden")
        return self


class MovimientoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    movimiento_id: int
    clave_operacion: str
    repuesto_id: int
    tipo: TipoMovimiento
    cantidad: int
    orden_id: int | None
    fecha_hora: datetime
    registrado_por_id: int


class CompromisoOrden(BaseModel):
    orden_id: int
    comprometido: int


class StockSalida(BaseModel):
    repuesto_id: int
    nombre: str
    proveedor_nombre: str
    stock: int
    comprometido: int
    disponible: int
    umbral_efectivo: int | None
    bajo_umbral: bool
    compromisos: list[CompromisoOrden]


class AlertaStock(BaseModel):
    """Resultado de evaluar la alerta tras el movimiento (§4.6).

    `nueva` = este movimiento hizo pasar el repuesto a estar bajo su umbral:
    es el momento de avisar (una sola vez mientras siga la misma situación).
    """

    activa: bool
    nueva: bool


class ResultadoMovimiento(BaseModel):
    movimiento: MovimientoSalida
    stock: StockSalida
    alerta: AlertaStock
    # true si la clave ya existía y se devolvió el movimiento original.
    repetido: bool = False


class PaginaMovimientos(BaseModel):
    total: int
    desde: int
    limite: int
    movimientos: list[MovimientoSalida]


class UmbralGeneralEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    umbral_general: int = Field(ge=0, le=1_000_000)
    observacion: str | None = Field(default=None, min_length=1, max_length=500)


class UmbralGeneralSalida(BaseModel):
    umbral_general: int | None
    vigente_desde: datetime | None
    actualizado_por_id: int | None


class CambioUmbral(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    historial_id: int
    repuesto_id: int | None
    valor_anterior: int | None
    valor_nuevo: int | None
    administrador_id: int
    fecha_hora: datetime
    observacion: str | None


class AlertaRepuesto(BaseModel):
    repuesto_id: int
    nombre: str
    proveedor_nombre: str
    stock: int
    umbral_efectivo: int
    faltan: int


class PaginaAlertas(BaseModel):
    umbral_general: int | None
    total: int
    alertas: list[AlertaRepuesto]


# ------------------------------------------------- disponibilidad (validación) --


class ItemRequerido(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repuesto_id: int = Field(gt=0)
    cantidad: int = Field(ge=1, le=1_000_000, description="Unidades que se quieren usar")


class ConsultaDisponibilidad(BaseModel):
    """Repuestos que se quieren usar, opcionalmente para una orden.

    Con `orden_id` cuenta como disponible lo que esa orden ya tiene reservado;
    sin orden, solo lo libre. Un repuesto repetido en la lista se suma.
    """

    model_config = ConfigDict(extra="forbid")

    orden_id: int | None = Field(default=None, gt=0)
    items: list[ItemRequerido] = Field(min_length=1, max_length=100)


class DisponibilidadRepuesto(BaseModel):
    repuesto_id: int
    nombre: str
    proveedor_nombre: str
    requerido: int
    stock: int
    # Reservado por la orden consultada (0 si no se indicó orden).
    reservado_para_orden: int
    comprometido_otras_ordenes: int
    # Lo que esa orden puede usar: stock − lo comprometido por OTRAS órdenes.
    disponible: int
    alcanza: bool
    faltan: int


class ResultadoDisponibilidad(BaseModel):
    orden_id: int | None
    # true si TODOS los repuestos alcanzan.
    disponible: bool
    repuestos: list[DisponibilidadRepuesto]
    # Solo en la consulta por orden: presupuesto aprobado del que salen los requeridos.
    presupuesto_id: int | None = None
    version: int | None = None
