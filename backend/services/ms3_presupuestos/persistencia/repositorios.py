"""Repositorios de MS3: acceso a datos por agregado, sin manejo de transacciones.

Reglas del patrón en este servicio:

1. Un repositorio recibe la `Session` y NUNCA hace commit ni rollback: eso lo
   decide la UnidadDeTrabajo (un caso de uso = una transacción).
2. `agregar()` hace `flush()` para que la base valide ya (UNIQUE, CHECK,
   triggers) y el objeto tenga su id; el error se traduce al salir de la
   transacción de la unidad de trabajo.
3. Solo consultas del propio servicio (§8): nada de joins con tablas de otras
   bases; `orden_id` y los *_id de usuarios son referencias lógicas.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.ms3_presupuestos.db import Base
from services.ms3_presupuestos.models import (
    MovimientoInventario,
    ParametroInventario,
    Presupuesto,
    Proveedor,
    Repuesto,
    VersionPresupuesto,
)
from services.ms3_presupuestos.persistencia.errores import RecursoNoEncontrado

ModeloT = TypeVar("ModeloT", bound=Base)

LIMITE_MAXIMO = 200


class RepositorioBase(Generic[ModeloT]):
    """Operaciones comunes a todos los repositorios del servicio."""

    modelo: type[ModeloT]
    nombre_recurso: str = "Registro"

    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion

    # -------- lectura --------
    def obtener(self, id_: int) -> ModeloT | None:
        """Busca por clave primaria (usa el mapa de identidad de la sesión)."""
        return self.sesion.get(self.modelo, id_)

    def obtener_o_error(self, id_: int) -> ModeloT:
        """Como obtener(), pero lanza RecursoNoEncontrado (→ 404) si no existe."""
        encontrado = self.obtener(id_)
        if encontrado is None:
            raise RecursoNoEncontrado(f"{self.nombre_recurso} {id_} no existe")
        return encontrado

    def listar(self, *, desde: int = 0, limite: int = 50) -> Sequence[ModeloT]:
        """Lista paginada y en orden estable (por clave primaria)."""
        limite = max(1, min(limite, LIMITE_MAXIMO))
        pk = self.modelo.__mapper__.primary_key[0]
        consulta = select(self.modelo).order_by(pk).offset(max(desde, 0)).limit(limite)
        return self.sesion.scalars(consulta).all()

    def contar(self) -> int:
        return self.sesion.scalar(select(func.count()).select_from(self.modelo)) or 0

    # -------- escritura (sin commit) --------
    def agregar(self, entidad: ModeloT) -> ModeloT:
        """Agrega y hace flush: la base valida ahora y la entidad recibe su id."""
        self.sesion.add(entidad)
        self.sesion.flush()
        return entidad


class RepositorioProveedores(RepositorioBase[Proveedor]):
    modelo = Proveedor
    nombre_recurso = "Proveedor"

    def buscar_por_nombre(self, nombre: str) -> Proveedor | None:
        return self.sesion.scalar(select(Proveedor).where(Proveedor.nombre == nombre))


class RepositorioRepuestos(RepositorioBase[Repuesto]):
    modelo = Repuesto
    nombre_recurso = "Repuesto"

    def de_proveedor(self, proveedor_id: int) -> Sequence[Repuesto]:
        consulta = (
            select(Repuesto)
            .where(Repuesto.proveedor_id == proveedor_id)
            .order_by(Repuesto.nombre)
        )
        return self.sesion.scalars(consulta).all()

    def obtener_para_actualizar(self, repuesto_id: int) -> Repuesto:
        """Lee el repuesto con SELECT ... FOR UPDATE (bloqueo de fila).

        Se usa antes de mover stock: si dos órdenes consumen el mismo repuesto
        a la vez, la segunda espera a que la primera termine su transacción y
        ve el stock ya actualizado (evita vender lo que no hay).
        """
        consulta = select(Repuesto).where(Repuesto.repuesto_id == repuesto_id).with_for_update()
        repuesto = self.sesion.scalar(consulta)
        if repuesto is None:
            raise RecursoNoEncontrado(f"Repuesto {repuesto_id} no existe")
        return repuesto

    def bajo_umbral(self, umbral_general: int) -> Sequence[Repuesto]:
        """Repuestos con stock < umbral efectivo (particular o, si falta, general)."""
        umbral_efectivo = func.coalesce(Repuesto.umbral_particular, umbral_general)
        consulta = select(Repuesto).where(Repuesto.stock < umbral_efectivo).order_by(Repuesto.nombre)
        return self.sesion.scalars(consulta).all()


class RepositorioMovimientos(RepositorioBase[MovimientoInventario]):
    modelo = MovimientoInventario
    nombre_recurso = "Movimiento"

    def por_clave_operacion(self, clave: str) -> MovimientoInventario | None:
        """Para operaciones idempotentes: si la clave ya existe, no repetir."""
        return self.sesion.scalar(
            select(MovimientoInventario).where(MovimientoInventario.clave_operacion == clave)
        )

    def de_orden(self, orden_id: int) -> Sequence[MovimientoInventario]:
        consulta = (
            select(MovimientoInventario)
            .where(MovimientoInventario.orden_id == orden_id)
            .order_by(MovimientoInventario.fecha_hora, MovimientoInventario.movimiento_id)
        )
        return self.sesion.scalars(consulta).all()


class RepositorioParametros(RepositorioBase[ParametroInventario]):
    modelo = ParametroInventario
    nombre_recurso = "Parámetro de inventario"

    def vigente(self) -> ParametroInventario | None:
        return self.sesion.scalar(
            select(ParametroInventario).where(ParametroInventario.vigente_hasta.is_(None))
        )


class RepositorioPresupuestos(RepositorioBase[Presupuesto]):
    modelo = Presupuesto
    nombre_recurso = "Presupuesto"

    def de_orden(self, orden_id: int) -> Presupuesto | None:
        """Presupuesto de una orden (MS2) con sus versiones (selectin)."""
        return self.sesion.scalar(select(Presupuesto).where(Presupuesto.orden_id == orden_id))

    def buscar(
        self, *, orden_id: int | None = None, desde: int = 0, limite: int = 50
    ) -> Sequence[Presupuesto]:
        """Lista paginada (más recientes primero), opcionalmente de una orden."""
        limite = max(1, min(limite, LIMITE_MAXIMO))
        consulta = select(Presupuesto)
        if orden_id is not None:
            consulta = consulta.where(Presupuesto.orden_id == orden_id)
        consulta = (
            consulta.order_by(Presupuesto.presupuesto_id.desc())
            .offset(max(desde, 0))
            .limit(limite)
        )
        return self.sesion.scalars(consulta).all()

    def contar_busqueda(self, *, orden_id: int | None = None) -> int:
        consulta = select(func.count()).select_from(Presupuesto)
        if orden_id is not None:
            consulta = consulta.where(Presupuesto.orden_id == orden_id)
        return self.sesion.scalar(consulta) or 0

    def version(self, presupuesto_id: int, numero: int) -> VersionPresupuesto:
        """Versión `numero` de un presupuesto; RecursoNoEncontrado (404) si no existe."""
        encontrada = self.sesion.scalar(
            select(VersionPresupuesto).where(
                VersionPresupuesto.presupuesto_id == presupuesto_id,
                VersionPresupuesto.numero == numero,
            )
        )
        if encontrada is None:
            raise RecursoNoEncontrado(
                f"El presupuesto {presupuesto_id} no tiene versión {numero}"
            )
        return encontrada
