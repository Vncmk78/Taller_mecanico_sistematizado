"""Consulta hechos de MS3 con el JWT original; no acepta hechos del body."""
from __future__ import annotations

from typing import Protocol

import httpx

from services.ms2_taller.config import settings
from shared.contratos_decisiones import DecisionPresupuestoVerificada


class DecisionNoVisibleError(Exception):
    """La decisión no existe o no corresponde al usuario autenticado."""


class DecisionNoAplicableError(Exception):
    """La decisión carece de los hechos necesarios para aplicar el efecto."""


class ServicioPresupuestosNoDisponibleError(Exception):
    """No se pudo obtener una decisión verificable desde MS3."""


class VerificadorDecisiones(Protocol):
    def consultar(self, decision_id: int, token: str) -> DecisionPresupuestoVerificada: ...


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
