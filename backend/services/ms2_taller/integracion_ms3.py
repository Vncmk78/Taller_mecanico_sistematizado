"""Consulta hechos de MS3 con el JWT original; no acepta hechos del body."""
from __future__ import annotations

from typing import Protocol

import httpx

from services.ms2_taller.config import settings
from shared.contratos_decisiones import (
    DisponibilidadRepuestosSolicitud,
    DisponibilidadRepuestosVerificada,
    DecisionPresupuestoVerificada,
    EnvioPresupuestoVerificado,
)


class DecisionNoVisibleError(Exception):
    """La decisión no existe o no corresponde al usuario autenticado."""


class DecisionNoAplicableError(Exception):
    """La decisión carece de los hechos necesarios para aplicar el efecto."""


class ServicioPresupuestosNoDisponibleError(Exception):
    """No se pudo obtener una decisión verificable desde MS3."""


class DisponibilidadRepuestosNoVisibleError(Exception):
    """La reserva de repuestos no existe o no corresponde a la orden."""


class DisponibilidadRepuestosNoAplicableError(Exception):
    """MS3 no confirmó la reserva para esa orden."""


class VerificadorDisponibilidadRepuestos(Protocol):
    def consultar(
        self, orden_id: int, clave_operacion: str, token: str,
    ) -> DisponibilidadRepuestosVerificada: ...


class VerificadorDecisiones(Protocol):
    def consultar(self, decision_id: int, token: str) -> DecisionPresupuestoVerificada: ...


class EnvioPresupuestoNoVisibleError(Exception):
    """El presupuesto no existe o no tiene un envío inicial verificable."""


class EnvioPresupuestoNoAplicableError(Exception):
    """La versión inicial de ese presupuesto todavía no fue enviada."""


class VerificadorEnviosPresupuesto(Protocol):
    def consultar(self, presupuesto_id: int, token: str) -> EnvioPresupuestoVerificado: ...


class VerificadorEnviosPresupuestoHttp:
    def __init__(self, url_base: str, timeout: float) -> None:
        self.url_base = url_base.rstrip("/")
        self.timeout = timeout

    def consultar(self, presupuesto_id: int, token: str) -> EnvioPresupuestoVerificado:
        try:
            respuesta = httpx.get(
                f"{self.url_base}/presupuestos/{presupuesto_id}/envio-inicial",
                headers={"Authorization": f"Bearer {token}"}, timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise ServicioPresupuestosNoDisponibleError("No fue posible consultar MS3") from exc
        if respuesta.status_code in (403, 404):
            raise EnvioPresupuestoNoVisibleError("Envío inicial no encontrado")
        if respuesta.status_code == 409:
            raise EnvioPresupuestoNoAplicableError("La primera versión aún no fue enviada")
        if respuesta.status_code != 200:
            raise ServicioPresupuestosNoDisponibleError(
                "MS3 no devolvió un envío inicial verificable"
            )
        try:
            envio = EnvioPresupuestoVerificado.model_validate(respuesta.json())
        except ValueError as exc:
            raise ServicioPresupuestosNoDisponibleError("Respuesta inválida de MS3") from exc
        if envio.presupuesto_id != presupuesto_id:
            raise ServicioPresupuestosNoDisponibleError(
                "La referencia devuelta por MS3 no coincide"
            )
        return envio


class VerificadorDecisionesHttp:
    def __init__(self, url_base: str, timeout: float) -> None:
        self.url_base = url_base.rstrip("/")
        self.timeout = timeout

    def consultar(self, decision_id: int, token: str) -> DecisionPresupuestoVerificada:
        try:
            respuesta = httpx.get(
                f"{self.url_base}/presupuestos/decisiones/{decision_id}",
                headers={"Authorization": f"Bearer {token}"}, timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise ServicioPresupuestosNoDisponibleError("No fue posible consultar MS3") from exc
        if respuesta.status_code in (403, 404):
            raise DecisionNoVisibleError("Decisión no encontrada")
        if respuesta.status_code == 409:
            raise DecisionNoAplicableError("La decisión no puede aplicarse automáticamente")
        if respuesta.status_code != 200:
            raise ServicioPresupuestosNoDisponibleError("MS3 no devolvió una decisión verificable")
        try:
            decision = DecisionPresupuestoVerificada.model_validate(respuesta.json())
        except ValueError as exc:
            raise ServicioPresupuestosNoDisponibleError("Respuesta inválida de MS3") from exc
        if decision.decision_id != decision_id:
            raise ServicioPresupuestosNoDisponibleError("La referencia devuelta por MS3 no coincide")
        return decision


def obtener_verificador_decisiones() -> VerificadorDecisiones:
    return VerificadorDecisionesHttp(settings.MS3_URL, settings.MS3_TIMEOUT_SEGUNDOS)


def obtener_verificador_envios_presupuesto() -> VerificadorEnviosPresupuesto:
    return VerificadorEnviosPresupuestoHttp(settings.MS3_URL, settings.MS3_TIMEOUT_SEGUNDOS)


class VerificadorDisponibilidadRepuestosHttp:
    def __init__(self, url_base: str, timeout: float) -> None:
        self.url_base = url_base.rstrip("/")
        self.timeout = timeout

    def consultar(
        self, orden_id: int, clave_operacion: str, token: str,
    ) -> DisponibilidadRepuestosVerificada:
        try:
            respuesta = httpx.get(
                f"{self.url_base}/inventario/ordenes/{orden_id}/disponibilidad/{clave_operacion}",
                headers={"Authorization": f"Bearer {token}"}, timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise ServicioPresupuestosNoDisponibleError(
                "No fue posible verificar la reserva en MS3"
            ) from exc
        if respuesta.status_code in (403, 404):
            raise DisponibilidadRepuestosNoVisibleError(
                "Reserva de repuestos no encontrada"
            )
        if respuesta.status_code == 409:
            raise DisponibilidadRepuestosNoAplicableError(
                "MS3 no confirmó la reserva de repuestos"
            )
        if respuesta.status_code != 200:
            raise ServicioPresupuestosNoDisponibleError(
                "MS3 no devolvió una reserva verificable"
            )
        try:
            hecho = DisponibilidadRepuestosVerificada.model_validate(respuesta.json())
        except ValueError as exc:
            raise ServicioPresupuestosNoDisponibleError(
                "Respuesta inválida de MS3"
            ) from exc
        if hecho.orden_id != orden_id or hecho.clave_operacion != clave_operacion:
            raise ServicioPresupuestosNoDisponibleError(
                "La reserva devuelta por MS3 no coincide"
            )
        return hecho


def obtener_verificador_disponibilidad_repuestos() -> VerificadorDisponibilidadRepuestos:
    return VerificadorDisponibilidadRepuestosHttp(
        settings.MS3_URL, settings.MS3_TIMEOUT_SEGUNDOS
    )
