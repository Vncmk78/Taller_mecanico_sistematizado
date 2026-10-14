"""Inventario y stock de MS3 (§4.6).

    stock        físico (repuesto.stock). Solo lo cambian ingreso, ajuste y consumo.
    comprometido reservado para órdenes: Σ compromiso − liberación − consumo (por orden).
    disponible   stock − comprometido.

Reglas de cada movimiento (todas en UNA transacción, con el repuesto
bloqueado con SELECT ... FOR UPDATE para que dos órdenes no tomen las mismas
unidades ni el stock quede negativo):

    ingreso     stock += n                                  (Administrador)
    ajuste      stock += n (n puede ser negativo); stock ≥ 0  (Administrador)
    compromiso  reserva n para la orden; exige n ≤ disponible
    consumo     stock −= n; usa primero lo reservado por la orden y el resto
                debe estar disponible (no toma lo reservado por otras órdenes)
    liberacion  devuelve n reservadas; exige n ≤ comprometido de la orden

`clave_operacion` es única: si la misma operación llega dos veces se devuelve
el movimiento original sin aplicarlo otra vez; si la clave se reutiliza con
otros datos → 409.

Alerta: stock < umbral efectivo (particular o, si no hay, el general vigente).
El resultado indica si el movimiento la ACTIVÓ (pasó de no-alerta a alerta),
para avisar una sola vez mientras persista (el envío lo hará MS1).
"""
from __future__ import annotations

from sqlalchemy import func, select

from services.ms3_presupuestos.models import (
    HistorialUmbral,
    MovimientoInventario,
    ParametroInventario,
    Repuesto,
)
from services.ms3_presupuestos.persistencia import (
    ConflictoDeDatos,
    RecursoNoEncontrado,
    UnidadDeTrabajo,
)
from services.ms3_presupuestos.schemas.inventario import (
    AlertaRepuesto,
    AlertaStock,
    CambioUmbral,
    CompromisoOrden,
    MovimientoCrear,
    MovimientoSalida,
    ResultadoMovimiento,
    StockSalida,
    UmbralGeneralSalida,
)

TIPOS_ADMINISTRADOR = frozenset({"ingreso", "ajuste"})


class StockInsuficiente(ConflictoDeDatos):
    """La operación pide más unidades de las que hay disponibles (409)."""


# ------------------------------------------------------------------ consultas --


def umbral_general(uow: UnidadDeTrabajo) -> int | None:
    vigente = uow.parametros.vigente()
    return vigente.umbral_general if vigente else None


def umbral_efectivo(repuesto: Repuesto, general: int | None) -> int | None:
    return repuesto.umbral_particular if repuesto.umbral_particular is not None else general


def esta_bajo_umbral(stock: int, efectivo: int | None) -> bool:
    """§4.6: alerta si stock < umbral (igual NO es alerta)."""
    return efectivo is not None and stock < efectivo


def estado_stock(uow: UnidadDeTrabajo, repuesto: Repuesto, general: int | None = None) -> StockSalida:
    if general is None:
        general = umbral_general(uow)
    compromisos = uow.movimientos.comprometido_por_orden(repuesto.repuesto_id)
    comprometido = sum(compromisos.values())
    efectivo = umbral_efectivo(repuesto, general)
    return StockSalida(
        repuesto_id=repuesto.repuesto_id, nombre=repuesto.nombre,
        proveedor_nombre=repuesto.proveedor.nombre, stock=repuesto.stock,
        comprometido=comprometido, disponible=repuesto.stock - comprometido,
        umbral_efectivo=efectivo, bajo_umbral=esta_bajo_umbral(repuesto.stock, efectivo),
        compromisos=[CompromisoOrden(orden_id=o, comprometido=c) for o, c in sorted(compromisos.items())],
    )


def disponible_para_orden(uow: UnidadDeTrabajo, repuesto: Repuesto, orden_id: int | None) -> int:
    """Stock que puede usar una orden: lo libre + lo que ella misma tiene reservado."""
    compromisos = uow.movimientos.comprometido_por_orden(repuesto.repuesto_id)
    de_otras = sum(c for o, c in compromisos.items() if o != orden_id)
    return repuesto.stock - de_otras


def alertas(uow: UnidadDeTrabajo) -> tuple[int | None, list[AlertaRepuesto]]:
    general = umbral_general(uow)
    bajo = uow.repuestos.buscar(solo_bajo_umbral=True, umbral_general=general, limite=200)
    lista = []
    for r in bajo:
        efectivo = umbral_efectivo(r, general)
        lista.append(AlertaRepuesto(repuesto_id=r.repuesto_id, nombre=r.nombre,
                                    proveedor_nombre=r.proveedor.nombre, stock=r.stock,
                                    umbral_efectivo=efectivo, faltan=efectivo - r.stock))
    lista.sort(key=lambda a: (-a.faltan, a.nombre.lower()))
    return general, lista


# -------------------------------------------------------------- movimientos --


def registrar_movimiento(
    uow: UnidadDeTrabajo, datos: MovimientoCrear, *, usuario_id: int
) -> ResultadoMovimiento:
    with uow.transaccion():
        # 1) Bloquear el repuesto: todas las operaciones de stock de ESTE
        #    repuesto quedan en fila (incluida la consulta de la clave).
        repuesto = uow.repuestos.obtener_para_actualizar(datos.repuesto_id)

        # 2) Idempotencia: la misma operación no se aplica dos veces.
        previo = uow.movimientos.por_clave_operacion(datos.clave_operacion)
        if previo is not None:
            iguales = (previo.repuesto_id, previo.tipo, previo.cantidad, previo.orden_id) == \
                      (datos.repuesto_id, datos.tipo, datos.cantidad, datos.orden_id)
            if not iguales:
                raise ConflictoDeDatos(
                    f"La clave_operacion {datos.clave_operacion!r} ya se usó para otro movimiento")
            general = umbral_general(uow)
            return ResultadoMovimiento(
                movimiento=MovimientoSalida.model_validate(previo),
                stock=estado_stock(uow, repuesto, general),
                alerta=AlertaStock(activa=esta_bajo_umbral(
                    repuesto.stock, umbral_efectivo(repuesto, general)), nueva=False),
                repetido=True,
            )

        general = umbral_general(uow)
        efectivo = umbral_efectivo(repuesto, general)
        estaba_bajo = esta_bajo_umbral(repuesto.stock, efectivo)

        # 3) Reglas de disponibilidad y nuevo stock.
        repuesto.stock = _nuevo_stock(uow, repuesto, datos)

        movimiento = uow.movimientos.agregar(MovimientoInventario(
            clave_operacion=datos.clave_operacion, repuesto=repuesto, tipo=datos.tipo,
            cantidad=datos.cantidad, orden_id=datos.orden_id, registrado_por_id=usuario_id,
        ))
        uow.sesion.refresh(movimiento)
        queda_bajo = esta_bajo_umbral(repuesto.stock, efectivo)
        resultado = ResultadoMovimiento(
            movimiento=MovimientoSalida.model_validate(movimiento),
            stock=estado_stock(uow, repuesto, general),
            alerta=AlertaStock(activa=queda_bajo, nueva=queda_bajo and not estaba_bajo),
        )
    return resultado


def _nuevo_stock(uow: UnidadDeTrabajo, repuesto: Repuesto, datos: MovimientoCrear) -> int:
    n = datos.cantidad
    compromisos = uow.movimientos.comprometido_por_orden(repuesto.repuesto_id)
    comprometido = sum(compromisos.values())
    propio = compromisos.get(datos.orden_id, 0) if datos.orden_id else 0

    if datos.tipo == "ingreso":
        return repuesto.stock + n
    if datos.tipo == "ajuste":
        if repuesto.stock + n < 0:
            raise StockInsuficiente(
                f"El ajuste dejaría el stock de {repuesto.nombre!r} en {repuesto.stock + n}")
        return repuesto.stock + n
    if datos.tipo == "compromiso":
        disponible = repuesto.stock - comprometido
        if n > disponible:
            raise StockInsuficiente(
                f"Stock insuficiente de {repuesto.nombre!r}: se piden {n}, disponibles {disponible} "
                f"(stock {repuesto.stock}, comprometidas {comprometido})")
        return repuesto.stock
    if datos.tipo == "consumo":
        utilizable = repuesto.stock - (comprometido - propio)
        if n > utilizable:
            raise StockInsuficiente(
                f"Stock insuficiente de {repuesto.nombre!r}: se consumen {n}, la orden puede usar "
                f"{utilizable} (reservadas por ella {propio}, libres {repuesto.stock - comprometido})")
        return repuesto.stock - n
    # liberacion
    if n > propio:
        raise ConflictoDeDatos(
            f"La orden {datos.orden_id} tiene {propio} unidad(es) de {repuesto.nombre!r} "
            f"comprometidas; no se pueden liberar {n}")
    return repuesto.stock


def listar_movimientos(uow: UnidadDeTrabajo, *, repuesto_id: int | None, orden_id: int | None,
                       tipo: str | None, desde: int, limite: int):
    filtros = dict(repuesto_id=repuesto_id, orden_id=orden_id, tipo=tipo)
    return (uow.movimientos.contar_busqueda(**filtros),
            uow.movimientos.buscar(**filtros, desde=desde, limite=limite))


# ------------------------------------------------------------ umbral general --


def obtener_umbral_general(uow: UnidadDeTrabajo) -> UmbralGeneralSalida:
    vigente = uow.parametros.vigente()
    if vigente is None:
        return UmbralGeneralSalida(umbral_general=None, vigente_desde=None, actualizado_por_id=None)
    return UmbralGeneralSalida(umbral_general=vigente.umbral_general,
                               vigente_desde=vigente.vigente_desde,
                               actualizado_por_id=vigente.actualizado_por_id)


def cambiar_umbral_general(
    uow: UnidadDeTrabajo, *, valor: int, administrador_id: int, observacion: str | None
) -> UmbralGeneralSalida:
    """Cierra el umbral vigente y abre uno nuevo; deja el cambio en el historial.

    El mismo instante (clock_timestamp) cierra el anterior y abre el nuevo: no
    hay huecos ni solapes. Si el valor no cambia, no se escribe nada.
    """
    with uow.transaccion():
        vigente = uow.parametros.vigente_para_actualizar()
        anterior = vigente.umbral_general if vigente else None
        if anterior != valor:
            instante = uow.sesion.scalar(select(func.clock_timestamp()))
            if vigente is not None:
                vigente.vigente_hasta = instante
                uow.sesion.flush()
            uow.parametros.agregar(ParametroInventario(
                umbral_general=valor, actualizado_por_id=administrador_id, vigente_desde=instante))
            uow.sesion.add(HistorialUmbral(
                repuesto_id=None, valor_anterior=anterior, valor_nuevo=valor,
                administrador_id=administrador_id, observacion=observacion))
            uow.sesion.flush()
    return obtener_umbral_general(uow)


def historial_umbral(uow: UnidadDeTrabajo, *, repuesto_id: int | None, solo_general: bool,
                     limite: int) -> list[CambioUmbral]:
    consulta = select(HistorialUmbral)
    if repuesto_id is not None:
        if uow.repuestos.obtener(repuesto_id) is None:
            raise RecursoNoEncontrado(f"Repuesto {repuesto_id} no existe")
        consulta = consulta.where(HistorialUmbral.repuesto_id == repuesto_id)
    elif solo_general:
        consulta = consulta.where(HistorialUmbral.repuesto_id.is_(None))
    consulta = consulta.order_by(HistorialUmbral.fecha_hora.desc(),
                                 HistorialUmbral.historial_id.desc()).limit(limite)
    return [CambioUmbral.model_validate(h) for h in uow.sesion.scalars(consulta)]
