"""Casos de uso para configurar y validar el cupo diario de ingresos físicos."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from services.ms2_taller.config import settings
from services.ms2_taller.models.configuracion_cupo_ingresos import (
    ConfiguracionCupoIngresos,
    HistorialConfiguracionCupoIngresos,
    HistorialValidacionCupoIngreso,
)
from services.ms2_taller.models.ingreso_vehiculo import IngresoVehiculo


@dataclass(frozen=True)
class RechazoCupoIngreso:
    """Datos de una validación rechazada, tomados en el momento de validar.

    La validación ya no confirma nada por sí misma: quien la llama deshace su
    transacción y después guarda esta auditoría con `registrar_rechazo_cupo`.
    """

    vehiculo_id: int
    jornada_local: date
    ingresos_registrados: int
    max_ingresos_diarios: int | None
    administrador_id: int
    resultado: str


class _RechazoCupoError(Exception):
    def __init__(self, mensaje: str, rechazo: RechazoCupoIngreso | None = None) -> None:
        super().__init__(mensaje)
        self.rechazo = rechazo


class CupoDiarioNoConfiguradoError(_RechazoCupoError):
    """El Administrador debe configurar el máximo diario antes de recibir."""


class CupoDiarioExcedidoError(_RechazoCupoError):
    """El taller ya alcanzó el máximo diario de ingresos físicos."""


class PersistenciaCupoIngresosError(Exception):
    """No fue posible consultar o guardar el cupo diario de ingresos."""


@dataclass(frozen=True)
class ValidacionCupoIngreso:
    jornada_local: date
    ingresos_registrados: int
    max_ingresos_diarios: int
    administrador_id: int
    vehiculo_id: int


def _consulta_configuracion_para_actualizacion():
    """Bloquea el singleton para serializar configuración y altas concurrentes."""

    return (
        select(ConfiguracionCupoIngresos)
        .where(ConfiguracionCupoIngresos.configuracion_id == 1)
        .with_for_update()
    )


def _zona_taller() -> ZoneInfo:
    return ZoneInfo(settings.TIMEZONE)


def _jornada_actual(ahora: datetime | None = None) -> date:
    instante = ahora or datetime.now(timezone.utc)
    return instante.astimezone(_zona_taller()).date()


def _rango_jornada_utc(jornada_local: date) -> tuple[datetime, datetime]:
    zona = _zona_taller()
    inicio = datetime.combine(jornada_local, time.min, tzinfo=zona)
    siguiente = datetime.combine(jornada_local + timedelta(days=1), time.min, tzinfo=zona)
    return inicio.astimezone(timezone.utc), siguiente.astimezone(timezone.utc)


def _contar_ingresos_jornada(db: Session, jornada_local: date) -> int:
    inicio_utc, fin_utc = _rango_jornada_utc(jornada_local)
    consulta = (
        select(func.count())
        .select_from(IngresoVehiculo)
        .where(
            IngresoVehiculo.fecha_hora >= inicio_utc,
            IngresoVehiculo.fecha_hora < fin_utc,
        )
    )
    return int(db.scalar(consulta) or 0)


def obtener_cupo_diario_ingresos(
    db: Session,
) -> tuple[ConfiguracionCupoIngresos, date, int, bool]:
    """Devuelve el límite, la jornada local, el uso de hoy y si está excedido."""

    try:
        configuracion = db.get(ConfiguracionCupoIngresos, 1)
        if configuracion is None:
            configuracion = ConfiguracionCupoIngresos(configuracion_id=1)
            db.add(configuracion)
            db.flush()
            db.commit()
        jornada = _jornada_actual()
        cantidad = _contar_ingresos_jornada(db, jornada)
        excedido = (
            configuracion.max_ingresos_diarios is not None
            and cantidad > configuracion.max_ingresos_diarios
        )
        return configuracion, jornada, cantidad, excedido
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaCupoIngresosError(
            "No fue posible consultar el cupo diario de ingresos"
        ) from exc


def configurar_cupo_diario_ingresos(
    db: Session,
    *,
    max_ingresos_diarios: int,
    administrador_id: int,
) -> tuple[ConfiguracionCupoIngresos, date, int, bool]:
    """Guarda el límite y su auditoría; informa si la jornada ya lo supera."""

    try:
        configuracion = db.scalar(
            _consulta_configuracion_para_actualizacion()
        )
        if configuracion is None:
            configuracion = ConfiguracionCupoIngresos(configuracion_id=1)
            db.add(configuracion)
            db.flush()

        anterior = configuracion.max_ingresos_diarios
        if anterior != max_ingresos_diarios:
            db.add(
                HistorialConfiguracionCupoIngresos(
                    valor_anterior=anterior,
                    valor_nuevo=max_ingresos_diarios,
                    administrador_id=administrador_id,
                )
            )
            configuracion.max_ingresos_diarios = max_ingresos_diarios
            configuracion.actualizado_por_id = administrador_id

        jornada = _jornada_actual()
        db.flush()
        db.refresh(configuracion)
        cantidad = _contar_ingresos_jornada(db, jornada)
        excedido = cantidad > max_ingresos_diarios
        db.commit()
        return configuracion, jornada, cantidad, excedido
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaCupoIngresosError(
            "No fue posible guardar el cupo diario de ingresos"
        ) from exc


def validar_cupo_para_nuevo_ingreso(
    db: Session,
    *,
    vehiculo_id: int,
    administrador_id: int,
) -> ValidacionCupoIngreso:
    """Bloquea la fila singleton y valida el cupo antes de crear un ingreso.

    No confirma la transacción. Si rechaza, la excepción lleva en `rechazo` los
    datos de esta validación (jornada, uso y máximo leídos con el bloqueo):
    quien llama deshace todo y los guarda con `registrar_rechazo_cupo`. Las
    aceptadas se insertan junto con el ingreso y la orden para conservar su
    atomicidad.
    """

    try:
        configuracion = db.scalar(
            _consulta_configuracion_para_actualizacion()
        )
        jornada = _jornada_actual()
        cantidad = _contar_ingresos_jornada(db, jornada)
        maximo = configuracion.max_ingresos_diarios if configuracion else None

        if maximo is None:
            raise CupoDiarioNoConfiguradoError(
                "Configura el máximo diario de ingresos físicos antes de recibir vehículos",
                RechazoCupoIngreso(
                    vehiculo_id=vehiculo_id,
                    jornada_local=jornada,
                    ingresos_registrados=cantidad,
                    max_ingresos_diarios=None,
                    administrador_id=administrador_id,
                    resultado="cupo_no_configurado",
                ),
            )
        if cantidad >= maximo:
            raise CupoDiarioExcedidoError(
                "El taller ya alcanzó el máximo diario de ingresos físicos",
                RechazoCupoIngreso(
                    vehiculo_id=vehiculo_id,
                    jornada_local=jornada,
                    ingresos_registrados=cantidad,
                    max_ingresos_diarios=maximo,
                    administrador_id=administrador_id,
                    resultado="cupo_excedido",
                ),
            )
        return ValidacionCupoIngreso(
            jornada_local=jornada,
            ingresos_registrados=cantidad,
            max_ingresos_diarios=maximo,
            administrador_id=administrador_id,
            vehiculo_id=vehiculo_id,
        )
    except (CupoDiarioNoConfiguradoError, CupoDiarioExcedidoError):
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaCupoIngresosError(
            "No fue posible validar el cupo diario de ingresos"
        ) from exc


def registrar_rechazo_cupo(db: Session, rechazo: RechazoCupoIngreso) -> None:
    """Guarda, en su propia transacción, la auditoría de un rechazo de cupo.

    Se llama después de deshacer la operación rechazada, de modo que no se
    confirma ningún ingreso, orden ni dato parcial junto con la auditoría.
    """

    try:
        db.add(
            HistorialValidacionCupoIngreso(
                vehiculo_id=rechazo.vehiculo_id,
                jornada_local=rechazo.jornada_local,
                ingresos_registrados=rechazo.ingresos_registrados,
                max_ingresos_diarios=rechazo.max_ingresos_diarios,
                administrador_id=rechazo.administrador_id,
                aceptada=False,
                resultado=rechazo.resultado,
            )
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenciaCupoIngresosError(
            "No fue posible registrar la auditoría del cupo diario"
        ) from exc


def registrar_validacion_cupo_aceptada(
    db: Session,
    *,
    validacion: ValidacionCupoIngreso,
    ingreso_id: int,
) -> None:
    """Agrega al commit local la validación aceptada y su ingreso físico."""

    db.add(
        HistorialValidacionCupoIngreso(
            vehiculo_id=validacion.vehiculo_id,
            ingreso_id=ingreso_id,
            jornada_local=validacion.jornada_local,
            ingresos_registrados=validacion.ingresos_registrados,
            max_ingresos_diarios=validacion.max_ingresos_diarios,
            administrador_id=validacion.administrador_id,
            aceptada=True,
            resultado="cupo_disponible",
        )
    )
