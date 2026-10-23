"""Reserva de stock libre para continuar una orden que esperaba repuestos."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select

from services.ms3_presupuestos.models import (
    DecisionPresupuesto,
    ItemPresupuesto,
    MovimientoInventario,
    Repuesto,
    VersionPresupuesto,
)
from services.ms3_presupuestos.persistencia import (
    ConflictoDeDatos,
    ReglaDeDatosViolada,
    UnidadDeTrabajo,
)
from shared.auth import PrincipalAutenticado


class RepuestosInsuficientesError(ConflictoDeDatos):
    def __init__(self, faltantes: list[dict[str, int | str]]) -> None:
        super().__init__("El stock libre no cubre los repuestos aprobados")
        self.faltantes = faltantes


def clave_operacion_disponibilidad(orden_id: int, version_id: int) -> str:
    return f"disp:{orden_id}:{version_id}"


def reservar_repuestos_aprobados(
    uow: UnidadDeTrabajo, *, orden_id: int, actor_usuario_id: int,
) -> dict[str, object]:
    """Compromete el alcance aprobado usando stock físico menos otras reservas.

    Los bloqueos se toman en orden de ID para serializar dos reservas que
    compiten por cualquier repuesto común. La transacción registra las
    liberaciones de la versión anterior y los nuevos compromisos en conjunto.
    """
    with uow.transaccion():
        presupuesto = uow.presupuestos.obtener_de_orden_para_actualizar(orden_id)
        version = presupuesto.version_vigente
        if version is None or version.decision is None or version.decision.decision != "aprobado":
            raise ConflictoDeDatos("La orden no tiene una versión aprobada vigente")

        requeridos_decimal: dict[int, Decimal] = defaultdict(Decimal)
        for item in version.items:
            if item.tipo == "repuesto" and item.repuesto_id is not None:
                requeridos_decimal[item.repuesto_id] += item.cantidad
        if not requeridos_decimal:
            raise ConflictoDeDatos("La versión aprobada no contiene repuestos")
        if any(cantidad != cantidad.to_integral_value() for cantidad in requeridos_decimal.values()):
            raise ReglaDeDatosViolada(
                "Las cantidades de repuestos de inventario deben ser unidades enteras"
            )
        requeridos = {rid: int(cantidad) for rid, cantidad in requeridos_decimal.items()}
        clave = clave_operacion_disponibilidad(orden_id, version.version_id)
        prefijo = f"{clave}:reserva:"

        # El registro actual hace idempotentes las llamadas de MS3 incluso si
        # perdió la respuesta de MS2 después de que este confirmó la transición.
        movimientos_actuales = list(uow.movimientos.por_prefijo_clave_operacion(prefijo))
        if movimientos_actuales:
            reservas_por_repuesto = {
                m.repuesto_id: m.cantidad for m in movimientos_actuales if m.tipo == "compromiso"
            }
            if reservas_por_repuesto != requeridos:
                raise ConflictoDeDatos("La reserva registrada no coincide con la versión aprobada")
            if (
                list(uow.movimientos.por_prefijo_clave_operacion(f"{clave}:liberacion:"))
                or list(uow.movimientos.por_prefijo_clave_operacion(f"{clave}:reversa:"))
            ):
                raise ConflictoDeDatos("La reserva de esta versión ya fue liberada")
            return _respuesta_reserva(orden_id, version.numero, clave, requeridos)

        # Lock each stock row in stable order before reading any reservation
        # balances. Every operation that changes commitments must use the same
        # lock order to prevent overselling under concurrency.
        repuestos: dict[int, Repuesto] = {}
        for repuesto_id in sorted(set(requeridos) | {
            m.repuesto_id for m in uow.movimientos.de_orden(orden_id)
        }):
            repuestos[repuesto_id] = uow.repuestos.obtener_para_actualizar(repuesto_id)

        movimientos = uow.movimientos.de_repuestos(list(repuestos))
        saldos: dict[tuple[int, int], int] = defaultdict(int)
        for movimiento in movimientos:
            if movimiento.orden_id is None:
                continue
            if movimiento.tipo == "compromiso":
                saldos[(movimiento.repuesto_id, movimiento.orden_id)] += movimiento.cantidad
            elif movimiento.tipo in {"liberacion", "consumo"}:
                saldos[(movimiento.repuesto_id, movimiento.orden_id)] -= movimiento.cantidad

        comprometido_orden: dict[int, int] = defaultdict(int)
        comprometido_total: dict[int, int] = defaultdict(int)
        for (repuesto_id, reserva_orden_id), cantidad in saldos.items():
            if cantidad < 0:
                raise ReglaDeDatosViolada("El historial de compromisos de inventario es inconsistente")
            comprometido_total[repuesto_id] += cantidad
            if reserva_orden_id == orden_id:
                comprometido_orden[repuesto_id] += cantidad

        faltantes = []
        for repuesto_id, requerido in sorted(requeridos.items()):
            disponible = repuestos[repuesto_id].stock - (
                comprometido_total[repuesto_id] - comprometido_orden[repuesto_id]
            )
            if disponible < requerido:
                faltantes.append({
                    "repuesto_id": repuesto_id,
                    "requerido": requerido,
                    "disponible": max(0, disponible),
                })
        if faltantes:
            raise RepuestosInsuficientesError(faltantes)

        # Release this order's older reservation, if an approved version changed,
        # then reserve the current approved quantities without erasing history.
        for repuesto_id, cantidad in sorted(comprometido_orden.items()):
            if cantidad:
                uow.movimientos.agregar(MovimientoInventario(
                    clave_operacion=f"{clave}:liberacion:{repuesto_id}",
                    repuesto_id=repuesto_id,
                    orden_id=orden_id,
                    tipo="liberacion",
                    cantidad=cantidad,
                    registrado_por_id=actor_usuario_id,
                ))
        for repuesto_id, cantidad in sorted(requeridos.items()):
            uow.movimientos.agregar(MovimientoInventario(
                clave_operacion=f"{clave}:reserva:{repuesto_id}",
                repuesto_id=repuesto_id,
                orden_id=orden_id,
                tipo="compromiso",
                cantidad=cantidad,
                registrado_por_id=actor_usuario_id,
            ))
        return _respuesta_reserva(orden_id, version.numero, clave, requeridos)


def verificar_reserva_confirmada(
    uow: UnidadDeTrabajo, *, orden_id: int, clave_operacion: str,
) -> dict[str, object]:
    partes = clave_operacion.split(":")
    if len(partes) != 3 or partes[0] != "disp" or partes[1] != str(orden_id):
        raise ConflictoDeDatos("La clave de reserva no corresponde a la orden")
    try:
        version_id = int(partes[2])
    except ValueError as exc:
        raise ConflictoDeDatos("La clave de reserva no es válida") from exc
    version = uow.sesion.scalar(
        select(VersionPresupuesto).where(VersionPresupuesto.version_id == version_id)
    )
    if (
        version is None
        or version.presupuesto.orden_id != orden_id
        or not version.bloqueada
        or version.decision is None
        or version.decision.decision != "aprobado"
        or version.presupuesto.version_vigente is None
        or version.presupuesto.version_vigente.version_id != version_id
    ):
        raise ConflictoDeDatos("La versión aprobada no corresponde a la reserva")
    requeridos: dict[int, Decimal] = defaultdict(Decimal)
    for item in version.items:
        if item.tipo == "repuesto" and item.repuesto_id is not None:
            requeridos[item.repuesto_id] += item.cantidad
    if any(cantidad != cantidad.to_integral_value() for cantidad in requeridos.values()):
        raise ConflictoDeDatos("La versión aprobada contiene cantidades fraccionarias")
    esperado = {rid: int(cantidad) for rid, cantidad in requeridos.items()}
    prefijo = f"{clave_operacion}:reserva:"
    reservas = list(uow.movimientos.por_prefijo_clave_operacion(prefijo))
    comprometido = {
        m.repuesto_id: m.cantidad for m in reservas if m.tipo == "compromiso"
    }
    if (
        not reservas
        or any(m.orden_id != orden_id or m.tipo != "compromiso" for m in reservas)
        or comprometido != esperado
    ):
        raise ConflictoDeDatos("La reserva no está confirmada para esta orden")
    if (
        list(uow.movimientos.por_prefijo_clave_operacion(f"{clave_operacion}:liberacion:"))
        or list(uow.movimientos.por_prefijo_clave_operacion(f"{clave_operacion}:reversa:"))
    ):
        raise ConflictoDeDatos("La reserva ya fue liberada")
    return {
        "clave_operacion": clave_operacion,
        "orden_id": orden_id,
        "reserva_confirmada": True,
    }


def revertir_reserva_rechazada(
    uow: UnidadDeTrabajo, *, orden_id: int, clave_operacion: str, actor_usuario_id: int,
) -> None:
    """Libera una reserva cuando MS2 respondió un rechazo definitivo pre-commit."""
    prefijo = f"{clave_operacion}:reserva:"
    with uow.transaccion():
        reservas = list(uow.movimientos.por_prefijo_clave_operacion(prefijo))
        if not reservas:
            return
        if any(m.orden_id != orden_id or m.tipo != "compromiso" for m in reservas):
            raise ConflictoDeDatos("No se puede compensar una reserva inconsistente")
        if list(uow.movimientos.por_prefijo_clave_operacion(f"{clave_operacion}:reversa:")):
            return
        for repuesto_id in sorted({m.repuesto_id for m in reservas}):
            uow.repuestos.obtener_para_actualizar(repuesto_id)
        saldos: dict[int, int] = defaultdict(int)
        for movimiento in uow.movimientos.de_repuestos(
            sorted({m.repuesto_id for m in reservas})
        ):
            if movimiento.orden_id == orden_id:
                if movimiento.tipo == "compromiso":
                    saldos[movimiento.repuesto_id] += movimiento.cantidad
                elif movimiento.tipo in {"liberacion", "consumo"}:
                    saldos[movimiento.repuesto_id] -= movimiento.cantidad
        for repuesto_id, cantidad in sorted(saldos.items()):
            if cantidad < 0:
                raise ConflictoDeDatos("El saldo comprometido quedó inconsistente")
            if cantidad:
                uow.movimientos.agregar(MovimientoInventario(
                    clave_operacion=f"{clave_operacion}:reversa:{repuesto_id}",
                    repuesto_id=repuesto_id,
                    orden_id=orden_id,
                    tipo="liberacion",
                    cantidad=cantidad,
                    registrado_por_id=actor_usuario_id,
                ))


def _respuesta_reserva(
    orden_id: int, version_numero: int, clave: str, requeridos: dict[int, int],
) -> dict[str, object]:
    return {
        "clave_operacion": clave,
        "orden_id": orden_id,
        "version_presupuesto": version_numero,
        "repuestos": [
            {"repuesto_id": repuesto_id, "cantidad": cantidad}
            for repuesto_id, cantidad in sorted(requeridos.items())
        ],
        "aplicacion_confirmada": True,
    }
