"""Reglas de reserva, descuento y rechazo por stock insuficiente (§4.6).

RESERVA (compromiso)
    Al aprobar un presupuesto, si TODO lo que falta usar está disponible, se
    reservan esas unidades para la orden en la misma transacción de la
    decisión: desde ese momento otra orden no puede tomarlas. Si algo no
    alcanza, no se reserva nada (todo o nada) y la orden queda esperando
    repuestos; `reservar_presupuesto_aprobado` reintenta cuando llegue stock.
    La reserva se AJUSTA a lo pendiente: si una modificación aprobada pide
    menos, se libera el sobrante; si pide más, se reserva la diferencia.

DESCUENTO (consumo)
    Usar repuestos en la orden descuenta el stock físico. Primero se toma lo
    reservado por la orden y el resto debe estar libre; nunca se toman unidades
    reservadas por otra orden. Varios repuestos se descuentan juntos: si uno
    no alcanza, no se descuenta ninguno.

RECHAZO
    Si no alcanza, la operación se rechaza con 409 y el detalle por repuesto
    (`faltantes`: solicitado, disponible y cuánto falta). No queda nada a medias.

LIBERACIÓN
    Si la orden se cancela, se libera todo lo que tenía reservado.

Concurrencia: los repuestos se bloquean con SELECT ... FOR UPDATE siempre en
orden de id (sin interbloqueos), y cada operación tiene una `clave_operacion`
para que un reintento no se aplique dos veces.
"""
from __future__ import annotations

import uuid
from collections.abc import Mapping

from services.ms3_presupuestos.models import MovimientoInventario, Repuesto
from services.ms3_presupuestos.persistencia import (
    ConflictoDeDatos,
    RecursoNoEncontrado,
    UnidadDeTrabajo,
)
from services.ms3_presupuestos.schemas.inventario import (
    FaltanteStock,
    MovimientoSalida,
    ResultadoOperacionOrden,
    ResultadoReserva,
)
from services.ms3_presupuestos.services import disponibilidad
from services.ms3_presupuestos.services.inventario import StockInsuficiente


def _mover(uow: UnidadDeTrabajo, repuesto: Repuesto, tipo: str, cantidad: int, orden_id: int,
           usuario_id: int, clave: str) -> MovimientoInventario:
    if tipo == "consumo":
        repuesto.stock -= cantidad
    movimiento = uow.movimientos.agregar(MovimientoInventario(
        clave_operacion=clave, repuesto=repuesto, tipo=tipo, cantidad=cantidad,
        orden_id=orden_id, registrado_por_id=usuario_id))
    uow.sesion.refresh(movimiento, ["fecha_hora"])
    return movimiento


def _salida(movimientos: list[MovimientoInventario]) -> list[MovimientoSalida]:
    return [MovimientoSalida.model_validate(m) for m in movimientos]


# ------------------------------------------------------------------ reserva --

def ajustar_reserva(
    uow: UnidadDeTrabajo, orden_id: int, objetivo: Mapping[int, int], *, usuario_id: int,
) -> tuple[list[FaltanteStock], list[MovimientoInventario]]:
    """Deja reservado para la orden exactamente `objetivo` (por repuesto). Todo o nada.

    Debe llamarse dentro de una transacción. Devuelve (faltantes, movimientos):
    con faltantes no se escribe nada.
    """
    repuestos = uow.repuestos.bloquear_varios(objetivo)
    todos = uow.movimientos.comprometido_por_ordenes(objetivo)
    cambios: list[tuple[Repuesto, int]] = []
    faltantes: list[FaltanteStock] = []
    for rid, quiero in sorted(objetivo.items()):
        repuesto = repuestos[rid]
        compromisos = todos.get(rid, {})
        tengo = compromisos.get(orden_id, 0)
        libre = repuesto.stock - sum(compromisos.values())
        diferencia = quiero - tengo
        if diferencia > libre:
            faltantes.append(FaltanteStock(
                repuesto_id=rid, nombre=repuesto.nombre, solicitado=quiero,
                disponible=tengo + max(0, libre), faltan=diferencia - max(0, libre)))
        elif diferencia:
            cambios.append((repuesto, diferencia))
    if faltantes:
        return faltantes, []

    lote = uuid.uuid4().hex[:12]
    movimientos = [
        _mover(uow, repuesto, "compromiso" if dif > 0 else "liberacion", abs(dif), orden_id,
               usuario_id, f"reserva:{orden_id}:{repuesto.repuesto_id}:{lote}")
        for repuesto, dif in cambios
    ]
    return [], movimientos


def reservar_presupuesto_aprobado(
    uow: UnidadDeTrabajo, orden_id: int, *, usuario_id: int,
) -> ResultadoReserva:
    """Reserva lo que falta usar del presupuesto aprobado de la orden (todo o nada).

    Sirve para la aprobación y para reintentar una orden que quedó esperando
    repuestos. Si no alcanza devuelve `reservado: false` con los faltantes.
    """
    with uow.transaccion():
        _, pendientes = disponibilidad.pendientes_de_orden(uow, orden_id)
        faltantes, movimientos = ajustar_reserva(uow, orden_id, pendientes, usuario_id=usuario_id)
        resultado = ResultadoReserva(orden_id=orden_id, reservado=not faltantes,
                                     faltantes=faltantes, movimientos=_salida(movimientos))
    return resultado


# ---------------------------------------------------------------- descuento --

def consumir_para_orden(
    uow: UnidadDeTrabajo, orden_id: int, requeridos: Mapping[int, int], *,
    usuario_id: int, clave_operacion: str,
) -> ResultadoOperacionOrden:
    """Descuenta varios repuestos de una orden: todos o ninguno (409 con faltantes).

    Cada repuesto queda como un consumo con clave `<clave_operacion>:<repuesto_id>`.
    Reenviar la misma clave con los mismos datos devuelve lo ya aplicado.
    """
    with uow.transaccion():
        repuestos = uow.repuestos.bloquear_varios(requeridos)
        inexistentes = sorted(set(requeridos) - set(repuestos))
        if inexistentes:
            raise RecursoNoEncontrado(
                "No existen los repuestos: " + ", ".join(str(i) for i in inexistentes))

        claves = {rid: f"{clave_operacion}:{rid}" for rid in requeridos}
        previos = {rid: uow.movimientos.por_clave_operacion(c) for rid, c in claves.items()}
        if any(previos.values()):
            iguales = all(
                p is not None and (p.tipo, p.orden_id, p.cantidad) == ("consumo", orden_id, requeridos[rid])
                for rid, p in previos.items())
            if not iguales:
                raise ConflictoDeDatos(
                    f"La clave_operacion {clave_operacion!r} ya se usó para otro descuento")
            return ResultadoOperacionOrden(
                orden_id=orden_id, movimientos=_salida(list(previos.values())), repetido=True)

        faltantes = []
        compromisos = uow.movimientos.comprometido_por_ordenes(requeridos)
        for rid, cantidad in sorted(requeridos.items()):
            d = disponibilidad.evaluar_repuesto(uow, repuestos[rid], cantidad, orden_id,
                                                compromisos.get(rid, {}))
            if not d.alcanza:
                faltantes.append(FaltanteStock(repuesto_id=rid, nombre=d.nombre, solicitado=cantidad,
                                               disponible=max(0, d.disponible), faltan=d.faltan))
        if faltantes:
            raise StockInsuficiente(
                "Stock insuficiente para descontar los repuestos de la orden "
                f"{orden_id}; no se descontó ninguno", faltantes)

        movimientos = [_mover(uow, repuestos[rid], "consumo", cantidad, orden_id, usuario_id,
                              claves[rid]) for rid, cantidad in sorted(requeridos.items())]
        resultado = ResultadoOperacionOrden(orden_id=orden_id, movimientos=_salida(movimientos))
    return resultado


# --------------------------------------------------------------- liberación --

def liberar_orden(
    uow: UnidadDeTrabajo, orden_id: int, *, usuario_id: int, clave_operacion: str,
) -> ResultadoOperacionOrden:
    """Libera todo lo reservado por la orden (p. ej. al cancelarla). Idempotente."""
    with uow.transaccion():
        repetidos = [m for m in uow.movimientos.de_orden(orden_id)
                     if m.clave_operacion.startswith(f"{clave_operacion}:")]
        if repetidos:
            return ResultadoOperacionOrden(orden_id=orden_id, movimientos=_salida(repetidos),
                                           repetido=True)
        reservados = {m.repuesto_id for m in uow.movimientos.de_orden(orden_id)
                      if m.tipo == "compromiso"}
        repuestos = uow.repuestos.bloquear_varios(reservados)
        compromisos = uow.movimientos.comprometido_por_ordenes(repuestos)
        movimientos = []
        for rid, repuesto in sorted(repuestos.items()):
            tengo = compromisos.get(rid, {}).get(orden_id, 0)
            if tengo:
                movimientos.append(_mover(uow, repuesto, "liberacion", tengo, orden_id, usuario_id,
                                          f"{clave_operacion}:{rid}"))
        resultado = ResultadoOperacionOrden(orden_id=orden_id, movimientos=_salida(movimientos))
    return resultado
