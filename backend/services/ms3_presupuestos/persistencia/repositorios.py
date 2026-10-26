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

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

from sqlalchemy import case, exists, func, select
from sqlalchemy.sql import Select
from sqlalchemy.orm import Session

from services.ms3_presupuestos.db import Base
from services.ms3_presupuestos.models import (
    HistorialUmbral,
    ItemPresupuesto,
    MovimientoInventario,
    ParametroInventario,
    Presupuesto,
    Proveedor,
    Repuesto,
    VersionPresupuesto,
)
from services.ms3_presupuestos.persistencia.errores import RecursoNoEncontrado

ModeloT = TypeVar("ModeloT", bound=Base)

OrdenRepuestos = Literal["nombre", "stock_asc", "stock_desc"]


def contiene_texto(columna, texto: str):
    """`columna` contiene `texto` sin distinguir mayúsculas ni tildes.

    Usa ms3_normalizar() (lower + unaccent, migración 0006_ms3) en ambos lados,
    que es la misma expresión de los índices GIN de trigramas: así PostgreSQL
    puede usar el índice para '%texto%'. Los comodines del usuario (% y _) se
    escapan: buscar "10%" busca literalmente "10%".
    """
    escapado = texto.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    patron = func.concat("%", func.ms3_normalizar(escapado), "%")
    return func.ms3_normalizar(columna).like(patron, escape="\\")


@dataclass(frozen=True)
class FiltroRepuestos:
    """Filtros combinables de la búsqueda de repuestos (todos opcionales)."""

    proveedor_id: int | None = None
    texto: str | None = None
    solo_bajo_umbral: bool = False
    umbral_general: int | None = None
    con_stock: bool | None = None          # True: stock > 0 · False: stock = 0
    orden: OrdenRepuestos = "nombre"

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

    def con_nombre_similar(self, nombre: str, *, excepto: int | None = None) -> Proveedor | None:
        """Mismo nombre sin distinguir mayúsculas ni espacios extremos."""
        consulta = select(Proveedor).where(func.lower(Proveedor.nombre) == nombre.strip().lower())
        if excepto is not None:
            consulta = consulta.where(Proveedor.proveedor_id != excepto)
        return self.sesion.scalar(consulta)

    def _filtro(self, texto: str | None, con_repuestos: bool | None,
                tipo_distribuidor: str | None = None) -> Select:
        consulta = select(Proveedor)
        if tipo_distribuidor is not None:
            consulta = consulta.where(Proveedor.tipo_distribuidor == tipo_distribuidor)
        if texto and texto.strip():
            # Índices ix_proveedor_nombre_trgm / ix_proveedor_contacto_trgm.
            consulta = consulta.where(contiene_texto(Proveedor.nombre, texto)
                                      | contiene_texto(Proveedor.contacto, texto))
        if con_repuestos is not None:
            tiene = exists().where(Repuesto.proveedor_id == Proveedor.proveedor_id)
            consulta = consulta.where(tiene if con_repuestos else ~tiene)
        return consulta

    def buscar(self, *, texto: str | None = None, con_repuestos: bool | None = None,
               tipo_distribuidor: str | None = None,
               desde: int = 0, limite: int = 50) -> Sequence[Proveedor]:
        limite = max(1, min(limite, LIMITE_MAXIMO))
        # Orden = índice ix_proveedor_nombre_orden (lower(nombre), proveedor_id).
        consulta = (self._filtro(texto, con_repuestos, tipo_distribuidor)
                    .order_by(func.lower(Proveedor.nombre), Proveedor.proveedor_id)
                    .offset(max(desde, 0)).limit(limite))
        return self.sesion.scalars(consulta).all()

    def contar_busqueda(self, *, texto: str | None = None, con_repuestos: bool | None = None,
                        tipo_distribuidor: str | None = None) -> int:
        filtro = self._filtro(texto, con_repuestos, tipo_distribuidor)
        return self.sesion.scalar(select(func.count()).select_from(filtro.subquery())) or 0


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

    def bloquear_varios(self, repuesto_ids: Iterable[int]) -> dict[int, Repuesto]:
        """Bloquea (FOR UPDATE) varios repuestos SIEMPRE en orden de id.

        Si dos transacciones bloquean los mismos repuestos, ambas lo hacen en el
        mismo orden: la segunda espera a la primera en vez de quedar en un
        interbloqueo (deadlock) con ella. Los inexistentes no aparecen.
        """
        ids = sorted(set(repuesto_ids))
        if not ids:
            return {}
        consulta = (
            select(Repuesto).where(Repuesto.repuesto_id.in_(ids))
            .order_by(Repuesto.repuesto_id).with_for_update()
            .execution_options(populate_existing=True)
        )
        return {r.repuesto_id: r for r in self.sesion.scalars(consulta)}

    def con_nombre_similar(
        self, proveedor_id: int, nombre: str, *, excepto: int | None = None
    ) -> Repuesto | None:
        """Repuesto del MISMO proveedor con el mismo nombre (sin distinguir mayúsculas)."""
        consulta = select(Repuesto).where(
            Repuesto.proveedor_id == proveedor_id,
            func.lower(Repuesto.nombre) == nombre.strip().lower(),
        )
        if excepto is not None:
            consulta = consulta.where(Repuesto.repuesto_id != excepto)
        return self.sesion.scalar(consulta)

    @staticmethod
    def _filtro(f: FiltroRepuestos) -> Select:
        consulta = select(Repuesto)
        if f.proveedor_id is not None:
            # Índice ix_repuesto_proveedor_id (y uq_repuesto_proveedor_nombre).
            consulta = consulta.where(Repuesto.proveedor_id == f.proveedor_id)
        if f.texto and f.texto.strip():
            # Índice ix_repuesto_nombre_trgm.
            consulta = consulta.where(contiene_texto(Repuesto.nombre, f.texto))
        if f.con_stock is not None:
            consulta = consulta.where(Repuesto.stock > 0 if f.con_stock else Repuesto.stock == 0)
        if f.solo_bajo_umbral:
            # Sin umbral general vigente, solo cuentan los umbrales particulares.
            efectivo = func.coalesce(Repuesto.umbral_particular, f.umbral_general)
            consulta = consulta.where(efectivo.is_not(None), Repuesto.stock < efectivo)
        return consulta

    def buscar(self, filtro: FiltroRepuestos = FiltroRepuestos(), *,
               desde: int = 0, limite: int = 50) -> Sequence[Repuesto]:
        limite = max(1, min(limite, LIMITE_MAXIMO))
        orden = {
            # Índice ix_repuesto_nombre_orden (lower(nombre), repuesto_id).
            "nombre": (func.lower(Repuesto.nombre), Repuesto.repuesto_id),
            "stock_asc": (Repuesto.stock, func.lower(Repuesto.nombre), Repuesto.repuesto_id),
            "stock_desc": (Repuesto.stock.desc(), func.lower(Repuesto.nombre), Repuesto.repuesto_id),
        }[filtro.orden]
        consulta = self._filtro(filtro).order_by(*orden).offset(max(desde, 0)).limit(limite)
        return self.sesion.scalars(consulta).all()

    def contar_busqueda(self, filtro: FiltroRepuestos = FiltroRepuestos()) -> int:
        return self.sesion.scalar(
            select(func.count()).select_from(self._filtro(filtro).subquery())
        ) or 0

    def tiene_historial(self, repuesto_id: int) -> bool:
        """¿Aparece en movimientos, presupuestos o cambios de umbral? Entonces no se borra."""
        return bool(self.sesion.scalar(select(
            exists().where(MovimientoInventario.repuesto_id == repuesto_id)
            | exists().where(ItemPresupuesto.repuesto_id == repuesto_id)
            | exists().where(HistorialUmbral.repuesto_id == repuesto_id)
        )))

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

    def comprometido_por_orden(self, repuesto_id: int) -> dict[int, int]:
        """Unidades reservadas y aún no usadas, por orden.

        Por orden: compromisos − liberaciones − consumos (nunca menos de 0:
        un consumo mayor que lo reservado toma el resto del stock libre).
        """
        saldo = func.sum(case(
            (MovimientoInventario.tipo == "compromiso", MovimientoInventario.cantidad),
            (MovimientoInventario.tipo.in_(("liberacion", "consumo")), -MovimientoInventario.cantidad),
            else_=0,
        ))
        filas = self.sesion.execute(
            select(MovimientoInventario.orden_id, saldo)
            .where(MovimientoInventario.repuesto_id == repuesto_id,
                   MovimientoInventario.orden_id.is_not(None))
            .group_by(MovimientoInventario.orden_id)
        ).all()
        return {orden: int(valor) for orden, valor in filas if valor and valor > 0}

    def _filtro(self, *, repuesto_id: int | None, orden_id: int | None, tipo: str | None,
                proveedor_id: int | None = None) -> Select:
        consulta = select(MovimientoInventario)
        if proveedor_id is not None:
            consulta = consulta.where(MovimientoInventario.proveedor_id == proveedor_id)
        if repuesto_id is not None:
            consulta = consulta.where(MovimientoInventario.repuesto_id == repuesto_id)
        if orden_id is not None:
            consulta = consulta.where(MovimientoInventario.orden_id == orden_id)
        if tipo is not None:
            consulta = consulta.where(MovimientoInventario.tipo == tipo)
        return consulta

    def buscar(
        self, *, repuesto_id: int | None = None, orden_id: int | None = None,
        tipo: str | None = None, proveedor_id: int | None = None, desde: int = 0, limite: int = 50,
    ) -> Sequence[MovimientoInventario]:
        """Más recientes primero."""
        limite = max(1, min(limite, LIMITE_MAXIMO))
        consulta = (self._filtro(repuesto_id=repuesto_id, orden_id=orden_id, tipo=tipo,
                                 proveedor_id=proveedor_id)
                    .order_by(MovimientoInventario.fecha_hora.desc(),
                              MovimientoInventario.movimiento_id.desc())
                    .offset(max(desde, 0)).limit(limite))
        return self.sesion.scalars(consulta).all()

    def contar_busqueda(
        self, *, repuesto_id: int | None = None, orden_id: int | None = None, tipo: str | None = None,
        proveedor_id: int | None = None,
    ) -> int:
        consulta = self._filtro(repuesto_id=repuesto_id, orden_id=orden_id, tipo=tipo,
                                proveedor_id=proveedor_id)
        return self.sesion.scalar(select(func.count()).select_from(consulta.subquery())) or 0

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

    def vigente_para_actualizar(self) -> ParametroInventario | None:
        """El vigente con FOR UPDATE: dos cambios simultáneos no abren dos vigentes."""
        return self.sesion.scalar(
            select(ParametroInventario).where(ParametroInventario.vigente_hasta.is_(None))
            .with_for_update().execution_options(populate_existing=True)
        )


class RepositorioPresupuestos(RepositorioBase[Presupuesto]):
    modelo = Presupuesto
    nombre_recurso = "Presupuesto"

    def de_orden(self, orden_id: int) -> Presupuesto | None:
        """Presupuesto de una orden (MS2) con sus versiones (selectin)."""
        return self.sesion.scalar(select(Presupuesto).where(Presupuesto.orden_id == orden_id))

    def obtener_para_actualizar(self, presupuesto_id: int) -> Presupuesto:
        """Lee el presupuesto con SELECT ... FOR UPDATE.

        Serializa las operaciones que cambian su estado (enviar, decidir): si dos
        peticiones llegan a la vez, la segunda espera a que la primera confirme
        y ve el resultado (no se registran dos decisiones ni dos envíos).
        """
        consulta = (
            select(Presupuesto)
            .where(Presupuesto.presupuesto_id == presupuesto_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        presupuesto = self.sesion.scalar(consulta)
        if presupuesto is None:
            raise RecursoNoEncontrado(f"Presupuesto {presupuesto_id} no existe")
        return presupuesto

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
