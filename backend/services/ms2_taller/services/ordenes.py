"""Creación, consulta y asociación inicial de órdenes de trabajo.

INT-32 aporta el alta en estado ``Recibido`` y la visibilidad por recurso.
INT-33 agrega la asignación y reasignación auditada del mecánico. La primera
asignación de una orden recibida la deja esperando diagnóstico; las posteriores
no cambian automáticamente el estado. La validación remota del rol del destino
y la capacidad configurable siguen pendientes porque su infraestructura todavía
no está disponible.
"""

from __future__ import annotations

from sqlalchemy import false, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from services.ms2_taller.domain.transiciones_orden import (
    EstadoOrdenDesconocidoError,
    EventoOrden,
    TRANSICIONES_PERMITIDAS,
    TransicionOrdenNoPermitidaError,
    TransicionOrdenTerminalError,
    resolver_transicion,
    validar_estado_no_terminal,
    validar_transicion,
)
from services.ms2_taller.models.cliente import Cliente
from services.ms2_taller.integracion_ms3 import (
    DecisionNoAplicableError,
    DecisionNoVisibleError,
    ServicioPresupuestosNoDisponibleError,
    VerificadorDecisiones,
)
from services.ms2_taller.models.estado_orden import CANCELADO, RECIBIDO
from services.ms2_taller.models.historial_asignacion import HistorialAsignacion
from services.ms2_taller.models.historial_estado import HistorialEstado
from services.ms2_taller.models.ingreso_vehiculo import IngresoVehiculo
from services.ms2_taller.models.orden_trabajo import OrdenTrabajo
from services.ms2_taller.models.vehiculo import Vehiculo
from shared.auth import NombreRol, PrincipalAutenticado
from shared.contratos_decisiones import AplicacionDecisionRespuesta


# Solo eventos con una operación existente que verifica su hecho de negocio.
# Las demás brechas del PATCH se conservan pendientes de definición explícita.
_OPERACIONES_ESPECIFICAS_POR_EVENTO = {
    EventoOrden.PRIMERA_ASIGNACION: "PUT /ordenes/{orden_id}/mecanico",
    EventoOrden.PRIMERA_APROBACION_CON_REPUESTOS:
        "POST /ordenes/{orden_id}/decisiones-presupuesto",
    EventoOrden.PRIMERA_APROBACION_SIN_REPUESTOS:
        "POST /ordenes/{orden_id}/decisiones-presupuesto",
}


class VehiculoNoEncontradoError(Exception):
    """El vehículo indicado para la nueva orden no existe."""


class OrdenNoEncontradaError(Exception):
    """La orden no existe o no es visible para la identidad autenticada."""


class OrdenTerminalError(Exception):
    """Una orden entregada o cancelada ya no admite cambios de responsable."""


class PersistenciaOrdenError(Exception):
    """La operación sobre órdenes no pudo completarse de forma segura."""


class OrdenEstadoInvalidoError(Exception):
    """El estado de destino no pertenece al catálogo oficial de estados."""


class OrdenTransicionNoPermitidaError(Exception):
    """La transición solicitada no está permitida o la orden es terminal."""


class OrdenEstadoNoAutorizadoError(Exception):
    """La identidad autenticada no puede cambiar el estado de la orden."""


class OrdenObservacionInvalidaError(Exception):
    """La observación está vacía o falta el motivo de una cancelación."""


def registrar_historial_estado(
    db: Session,
    *,
    orden_id: int,
    estado_anterior: int | None,
    estado_nuevo: int,
    actor_usuario_id: int | None,
    origen: str,
    observacion: str | None = None,
    decision_presupuesto_id: int | None = None,
) -> HistorialEstado:
    """Agrega el cambio de estado a la sesión sin confirmar la transacción.

    La base genera la fecha/hora y aplica las restricciones del modelo. La
    operación que invoca esta función controla flush, commit y rollback para
    persistir el historial junto con el resto de sus cambios de forma atómica.
    """

    # Regla de negocio compartida por los cambios de estado, incluidos los
    # iniciados por el sistema. El campo sigue admitiendo None en otros destinos.
    if observacion is not None:
        observacion = observacion.strip()
        if not observacion:
            raise OrdenObservacionInvalidaError(
                "La observación no puede estar vacía ni contener solo espacios"
            )
    if estado_nuevo == CANCELADO and observacion is None:
        raise OrdenObservacionInvalidaError(
            "Toda transición a Cancelado requiere una observación o motivo no vacío"
        )

    historial = HistorialEstado(
        orden_id=orden_id,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        actor_usuario_id=actor_usuario_id,
        origen=origen,
        observacion=observacion,
        decision_presupuesto_id=decision_presupuesto_id,
    )
    db.add(historial)
    return historial


def _consulta_orden_para_actualizacion(
    orden_id: int,
) -> Select[tuple[OrdenTrabajo]]:
    """Selecciona y bloquea la orden cuyo responsable se modificará."""

    return (
        select(OrdenTrabajo)
        .where(OrdenTrabajo.orden_id == orden_id)
        # OrdenTrabajo carga EstadoOrden con un LEFT JOIN. Limitar el lock a la
        # tabla de órdenes evita que PostgreSQL intente bloquear el lado nullable
        # del join y expresa exactamente la fila que protege esta operación.
        .with_for_update(of=OrdenTrabajo)
    )


def _consulta_vehiculo_para_actualizacion(
    vehiculo_id: int,
) -> Select[tuple[Vehiculo]]:
    """Selecciona y bloquea solo el vehículo cuya estancia se decidirá."""

    return (
        select(Vehiculo)
        .where(Vehiculo.vehiculo_id == vehiculo_id)
        .with_for_update()
    )


def crear_orden(
    db: Session,
    vehiculo_id: int,
    administrador_id: int,
) -> OrdenTrabajo:
    """Crea ingreso, orden e historial inicial dentro de una transacción.

    Si ya existe una estancia abierta para el vehículo, se reutiliza. La
    comprobación del cupo diario configurable queda deliberadamente pendiente.
    """

    try:
        # PostgreSQL conserva este bloqueo de fila hasta el commit/rollback. Así
        # dos altas del mismo vehículo no pueden decidir en paralelo que falta
        # un ingreso abierto; vehículos distintos usan filas y locks distintos.
        vehiculo = db.scalar(_consulta_vehiculo_para_actualizacion(vehiculo_id))
        if vehiculo is None:
            raise VehiculoNoEncontradoError("Vehículo no encontrado")

        ingreso = db.scalar(
            select(IngresoVehiculo)
            .where(
                IngresoVehiculo.vehiculo_id == vehiculo_id,
                IngresoVehiculo.salida_en.is_(None),
            )
            .order_by(
                IngresoVehiculo.fecha_hora.desc(),
                IngresoVehiculo.ingreso_id.desc(),
            )
            .limit(1)
        )
        if ingreso is None:
            ingreso = IngresoVehiculo(
                vehiculo_id=vehiculo_id,
                registrado_por_id=administrador_id,
            )
            db.add(ingreso)
            db.flush()

        estado_inicial = resolver_transicion(None, EventoOrden.CREACION)
        orden = OrdenTrabajo(
            vehiculo_id=vehiculo_id,
            ingreso_id=ingreso.ingreso_id,
            estado_codigo=estado_inicial,
            mecanico_actual_id=None,
            creado_por_id=administrador_id,
        )
        db.add(orden)
        db.flush()

        registrar_historial_estado(
            db,
            orden_id=orden.orden_id,
            estado_anterior=None,
            estado_nuevo=estado_inicial,
            actor_usuario_id=administrador_id,
            origen="usuario",
        )
        db.flush()
        db.refresh(orden)
        db.commit()
        return orden
    except VehiculoNoEncontradoError:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaOrdenError("No fue posible crear la orden") from exc


def asignar_mecanico(
    db: Session,
    *,
    orden_id: int,
    mecanico_id: int,
    administrador_id: int,
    observacion: str | None = None,
) -> OrdenTrabajo:
    """Asigna o reasigna el mecánico y conserva el cambio en una transacción.

    El bloqueo de la orden se mantiene hasta el commit o rollback. De este modo,
    una operación concurrente sobre la misma orden observa el responsable que
    haya confirmado la operación anterior. En la primera asignación, una orden
    ``Recibida`` pasa a ``Esperando diagnóstico`` y se auditan ambos cambios.
    La comprobación remota del rol del destino y la capacidad configurable quedan
    deliberadamente fuera de INT-33.
    """

    try:
        orden = db.scalar(_consulta_orden_para_actualizacion(orden_id))
        if orden is None:
            raise OrdenNoEncontradaError("Orden no encontrada")
        try:
            validar_estado_no_terminal(orden.estado_codigo)
        except TransicionOrdenTerminalError as exc:
            raise OrdenTerminalError(
                "No se puede cambiar el mecánico de una orden terminal"
            ) from exc

        mecanico_anterior_id = orden.mecanico_actual_id
        if mecanico_anterior_id == mecanico_id:
            # No hay cambio que auditar. El commit libera explícitamente el lock
            # sin emitir UPDATE ni insertar una fila de historial.
            db.commit()
            return orden

        orden.mecanico_actual_id = mecanico_id
        db.add(
            HistorialAsignacion(
                orden_id=orden.orden_id,
                mecanico_anterior_id=mecanico_anterior_id,
                mecanico_nuevo_id=mecanico_id,
                administrador_id=administrador_id,
                observacion=observacion,
            )
        )

        if mecanico_anterior_id is None and orden.estado_codigo == RECIBIDO:
            estado_nuevo = resolver_transicion(
                orden.estado_codigo,
                EventoOrden.PRIMERA_ASIGNACION,
            )
            orden.estado_codigo = estado_nuevo
            registrar_historial_estado(
                db,
                orden_id=orden.orden_id,
                estado_anterior=RECIBIDO,
                estado_nuevo=estado_nuevo,
                actor_usuario_id=administrador_id,
                origen="usuario",
            )

        db.flush()
        db.refresh(orden)
        db.commit()
        return orden
    except OrdenNoEncontradaError:
        db.rollback()
        raise
    except OrdenTerminalError:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaOrdenError(
            "No fue posible asignar el mecánico"
        ) from exc


def listar_ordenes(
    db: Session,
    principal: PrincipalAutenticado,
) -> list[OrdenTrabajo]:
    """Lista la unión de órdenes visibles para todos los roles del principal."""

    try:
        consulta = select(OrdenTrabajo).order_by(OrdenTrabajo.orden_id)
        filtro = _filtro_visibilidad(principal)
        if filtro is not None:
            consulta = consulta.where(filtro)
        return list(db.scalars(consulta).unique().all())
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaOrdenError("No fue posible consultar las órdenes") from exc


def obtener_orden_visible(
    db: Session,
    principal: PrincipalAutenticado,
    orden_id: int,
) -> OrdenTrabajo:
    """Obtiene una orden sin revelar si una orden no visible realmente existe."""

    try:
        consulta = select(OrdenTrabajo).where(OrdenTrabajo.orden_id == orden_id)
        filtro = _filtro_visibilidad(principal)
        if filtro is not None:
            consulta = consulta.where(filtro)
        orden = db.scalar(consulta)
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaOrdenError("No fue posible consultar la orden") from exc

    if orden is None:
        raise OrdenNoEncontradaError("Orden no encontrada")
    return orden


def obtener_historial_orden(
    db: Session,
    principal: PrincipalAutenticado,
    orden_id: int,
) -> list[HistorialEstado]:
    """Devuelve el historial cronológico de una orden visible al principal.

    Aplica la misma autorización por recurso del detalle: una orden inexistente
    o ajena responde el mismo error de recurso ausente.
    """

    obtener_orden_visible(db, principal, orden_id)
    try:
        consulta = (
            select(HistorialEstado)
            .where(HistorialEstado.orden_id == orden_id)
            # El orden por id desempata filas con la misma fecha_hora.
            .order_by(HistorialEstado.fecha_hora, HistorialEstado.historial_id)
        )
        return list(db.scalars(consulta).all())
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaOrdenError(
            "No fue posible consultar el historial de la orden"
        ) from exc


def cambiar_estado_orden(
    db: Session,
    *,
    orden_id: int,
    estado_destino: int,
    principal: PrincipalAutenticado,
    observacion: str | None = None,
) -> OrdenTrabajo:
    """Valida rol, estructura y operaciones específicas antes del cambio directo.

    El lock de la orden se conserva hasta el commit o rollback, de modo que una
    operación concurrente observa el estado confirmado por la anterior. Dentro
    de la misma transacción se actualiza ``estado_codigo`` y se registra el
    historial con el actor autenticado y ``origen="usuario"``.
    """

    try:
        orden = db.scalar(_consulta_orden_para_actualizacion(orden_id))
        if orden is None:
            raise OrdenNoEncontradaError("Orden no encontrada")
        if not _puede_cambiar_estado(orden, principal):
            raise OrdenEstadoNoAutorizadoError(
                "No tienes permiso para cambiar el estado de esta orden"
            )

        try:
            validar_transicion(orden.estado_codigo, estado_destino)
        except EstadoOrdenDesconocidoError as exc:
            raise OrdenEstadoInvalidoError(str(exc)) from exc
        except TransicionOrdenNoPermitidaError as exc:
            raise OrdenTransicionNoPermitidaError(str(exc)) from exc

        for (origen, evento), destino in TRANSICIONES_PERMITIDAS.items():
            if origen == orden.estado_codigo and destino == estado_destino:
                operacion = _OPERACIONES_ESPECIFICAS_POR_EVENTO.get(evento)
                if operacion is not None:
                    raise OrdenTransicionNoPermitidaError(
                        f"Esta transición requiere la operación específica {operacion}"
                    )

        estado_anterior = orden.estado_codigo
        orden.estado_codigo = estado_destino
        registrar_historial_estado(
            db,
            orden_id=orden.orden_id,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_destino,
            actor_usuario_id=principal.usuario_id,
            origen="usuario",
            observacion=observacion,
        )
        db.flush()
        db.refresh(orden)
        db.commit()
        return orden
    except (
        OrdenNoEncontradaError,
        OrdenEstadoNoAutorizadoError,
        OrdenEstadoInvalidoError,
        OrdenTransicionNoPermitidaError,
        OrdenObservacionInvalidaError,
    ):
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaOrdenError(
            "No fue posible cambiar el estado de la orden"
        ) from exc


def aplicar_decision_presupuesto(
    db: Session, *, orden_id: int, decision_id: int,
    principal: PrincipalAutenticado, token: str, verificador: VerificadorDecisiones,
) -> AplicacionDecisionRespuesta:
    """Verifica el hecho en MS3 y aplica una sola transición local auditada.

    El bloqueo serializa decisiones sobre la misma orden. La referencia única
    del historial hace durable el reintento incluso tras avanzar a otro estado.
    MS3 ya confirmó su decisión antes de llamar a esta operación.
    """
    try:
        if NombreRol.CLIENTE not in principal.roles:
            raise OrdenEstadoNoAutorizadoError("Se requiere rol Cliente")
        orden = db.scalar(_consulta_orden_para_actualizacion(orden_id))
        if orden is None:
            raise OrdenNoEncontradaError("Orden no encontrada")
        propietario = db.scalar(
            select(Cliente.usuario_id).join(Vehiculo, Vehiculo.cliente_id == Cliente.cliente_id)
            .where(Vehiculo.vehiculo_id == orden.vehiculo_id)
        )
        if propietario != principal.usuario_id:
            raise OrdenNoEncontradaError("Orden no encontrada")

        historial = db.scalar(select(HistorialEstado).where(
            HistorialEstado.decision_presupuesto_id == decision_id,
        ))
        if historial is not None:
            if historial.orden_id != orden_id or historial.actor_usuario_id != principal.usuario_id:
                raise DecisionNoVisibleError("Decisión no encontrada")
            respuesta = _aplicacion_de_historial(historial)
            db.commit()  # Libera el lock sin modificar estado ni historial.
            return respuesta

        decision = verificador.consultar(decision_id, token)
        if (decision.decision_id != decision_id or decision.orden_id != orden_id
                or decision.cliente_usuario_id != principal.usuario_id):
            raise DecisionNoVisibleError("Decisión no encontrada")
        if not decision.primera_decision:
            raise DecisionNoAplicableError("Una modificación no produce esta transición inicial")

        if decision.decision == "rechazado":
            evento = EventoOrden.RECHAZO_PRIMER_PRESUPUESTO
        elif decision.repuestos_disponibles is True:
            evento = EventoOrden.PRIMERA_APROBACION_CON_REPUESTOS
        elif decision.repuestos_disponibles is False:
            evento = EventoOrden.PRIMERA_APROBACION_SIN_REPUESTOS
        else:
            raise DecisionNoAplicableError("La aprobación no conserva una evaluación de stock")
        try:
            destino = resolver_transicion(orden.estado_codigo, evento)
        except (EstadoOrdenDesconocidoError, TransicionOrdenNoPermitidaError) as exc:
            raise OrdenTransicionNoPermitidaError(str(exc)) from exc

        historial = registrar_historial_estado(
            db, orden_id=orden_id, estado_anterior=orden.estado_codigo, estado_nuevo=destino,
            actor_usuario_id=principal.usuario_id, origen="usuario",
            observacion=decision.motivo if decision.decision == "rechazado" else None,
            decision_presupuesto_id=decision_id,
        )
        orden.estado_codigo = destino
        db.flush()
        respuesta = _aplicacion_de_historial(historial)
        db.commit()
        return respuesta
    except (OrdenEstadoNoAutorizadoError, OrdenNoEncontradaError,
            OrdenTransicionNoPermitidaError, OrdenObservacionInvalidaError,
            DecisionNoVisibleError, DecisionNoAplicableError,
            ServicioPresupuestosNoDisponibleError):
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaOrdenError("No fue posible aplicar la decisión") from exc


def _aplicacion_de_historial(historial: HistorialEstado) -> AplicacionDecisionRespuesta:
    return AplicacionDecisionRespuesta(
        decision_id=historial.decision_presupuesto_id, orden_id=historial.orden_id,
        estado_aplicado=historial.estado_nuevo, historial_id=historial.historial_id,
    )


def _puede_cambiar_estado(
    orden: OrdenTrabajo,
    principal: PrincipalAutenticado,
) -> bool:
    """El Administrador o el Mecánico asignado pueden mover el estado."""

    if NombreRol.ADMINISTRADOR in principal.roles:
        return True
    return (
        NombreRol.MECANICO in principal.roles
        and orden.mecanico_actual_id == principal.usuario_id
    )


def _filtro_visibilidad(
    principal: PrincipalAutenticado,
) -> ColumnElement[bool] | None:
    """Construye la autorización por recurso específica del dominio órdenes."""

    if NombreRol.ADMINISTRADOR in principal.roles:
        return None

    alcances = []
    if NombreRol.CLIENTE in principal.roles:
        alcances.append(
            OrdenTrabajo.vehiculo.has(
                Vehiculo.cliente.has(Cliente.usuario_id == principal.usuario_id)
            )
        )
    if NombreRol.MECANICO in principal.roles:
        alcances.append(OrdenTrabajo.mecanico_actual_id == principal.usuario_id)

    return or_(*alcances) if alcances else false()
