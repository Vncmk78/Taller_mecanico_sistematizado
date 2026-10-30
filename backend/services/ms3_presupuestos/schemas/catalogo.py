"""Contratos HTTP de proveedores y repuestos (MS3, §4.6 y RF-13/14/15).

Entradas con `extra="forbid"`: el stock NO se edita por aquí (solo cambia con
movimientos de inventario auditables) y los ids los decide el servidor.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TipoDistribuidor = Literal["oficial", "generico"]

# ---------------------------------------------------------------- proveedores --


class ProveedorCrear(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=120)
    contacto: str = Field(min_length=1, max_length=200,
                          description="Teléfono, correo o persona de contacto")
    tipo_distribuidor: TipoDistribuidor = Field(
        default="generico", description="Distribuidor oficial de la marca o genérico")


class ProveedorActualizar(BaseModel):
    """Cambios parciales: solo se modifican los campos enviados."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    contacto: str | None = Field(default=None, min_length=1, max_length=200)
    tipo_distribuidor: TipoDistribuidor | None = None

    @model_validator(mode="after")
    def _algo_que_cambiar(self) -> "ProveedorActualizar":
        if self.nombre is None and self.contacto is None and self.tipo_distribuidor is None:
            raise ValueError("Indique nombre, contacto y/o tipo_distribuidor")
        return self


class ProveedorSalida(BaseModel):
    proveedor_id: int
    nombre: str
    contacto: str
    tipo_distribuidor: TipoDistribuidor
    cantidad_repuestos: int


class ProveedorDetalle(ProveedorSalida):
    repuestos: list["RepuestoSalida"]


class PaginaProveedores(BaseModel):
    total: int
    desde: int
    limite: int
    proveedores: list[ProveedorSalida]


# ------------------------------------------------------------------ repuestos --


class RepuestoCrear(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    proveedor_id: int = Field(gt=0)
    nombre: str = Field(min_length=1, max_length=120)
    # Stock con el que se da de alta; queda respaldado por un movimiento de
    # "ingreso" (no hay stock sin movimiento que lo explique).
    stock_inicial: int = Field(default=0, ge=0, le=1_000_000)
    # Vacío = usa el umbral general vigente.
    umbral_particular: int | None = Field(default=None, ge=0, le=1_000_000)


class RepuestoActualizar(BaseModel):
    """Cambios parciales. `umbral_particular: null` explícito = volver al general.

    El stock no se modifica aquí: se mueve con ingresos, ajustes y consumos.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    proveedor_id: int | None = Field(default=None, gt=0)
    umbral_particular: int | None = Field(default=None, ge=0, le=1_000_000)
    observacion: str | None = Field(default=None, min_length=1, max_length=500,
                                    description="Motivo del cambio de umbral o de proveedor "
                                                "(queda en el historial)")

    @model_validator(mode="after")
    def _algo_que_cambiar(self) -> "RepuestoActualizar":
        if not ({"nombre", "proveedor_id", "umbral_particular"} & self.model_fields_set):
            raise ValueError("Indique nombre, proveedor_id y/o umbral_particular")
        return self


class RepuestoSalida(BaseModel):
    repuesto_id: int
    nombre: str
    proveedor_id: int
    proveedor_nombre: str
    proveedor_tipo_distribuidor: TipoDistribuidor
    stock: int
    umbral_particular: int | None
    # El que se aplica: particular o, si no hay, el general vigente.
    umbral_efectivo: int | None
    bajo_umbral: bool


class PaginaRepuestos(BaseModel):
    total: int
    desde: int
    limite: int
    umbral_general: int | None
    repuestos: list[RepuestoSalida]


ProveedorDetalle.model_rebuild()


# --------------------------------------------------------------- trazabilidad --


class ProveedorBreve(BaseModel):
    proveedor_id: int
    nombre: str
    tipo_distribuidor: TipoDistribuidor


class CambioProveedor(BaseModel):
    # Vacío = alta del repuesto.
    proveedor_anterior: ProveedorBreve | None
    proveedor_nuevo: ProveedorBreve
    fecha_hora: datetime
    # Vacío solo en los registros creados al habilitar la trazabilidad.
    registrado_por_id: int | None
    observacion: str | None


class IngresosPorProveedor(BaseModel):
    proveedor: ProveedorBreve
    ingresos: int
    unidades: int
    primer_ingreso: datetime
    ultimo_ingreso: datetime


class UsoPorOrden(BaseModel):
    orden_id: int
    reservado: int
    consumido: int


class TrazabilidadRepuesto(BaseModel):
    repuesto: RepuestoSalida
    proveedor_actual: ProveedorBreve
    historial_proveedores: list[CambioProveedor]
    ingresos_por_proveedor: list[IngresosPorProveedor]
    uso_por_orden: list[UsoPorOrden]


class RepuestoAbastecido(BaseModel):
    repuesto_id: int
    nombre: str
    # true si el proveedor lo abastece hoy; false si lo abasteció antes.
    actual: bool
    unidades_ingresadas: int


class TrazabilidadProveedor(BaseModel):
    proveedor: ProveedorBreve
    unidades_ingresadas: int
    repuestos: list[RepuestoAbastecido]
