"""Consulta a MS2 si una orden es visible para quien llama (§8: validación por API).

MS3 guarda `orden_id` como referencia lógica: no sabe quién es el dueño del
vehículo. Para que SOLO el cliente propietario vea y decida el presupuesto
(§4.3), MS3 llama a `GET {MS2_URL}/ordenes/{orden_id}` con el MISMO JWT del
usuario. MS2 aplica su propia visibilidad por rol:

    200 → la orden es visible para ese usuario (es suya)
    404 / 403 → no existe o no es suya  → OrdenNoVisible
    otro / sin conexión / timeout       → ServicioOrdenesNoDisponible (503)

`VerificadorOrdenes` es el puerto; los routers lo reciben por dependencia, así
las pruebas lo reemplazan sin levantar MS2.
"""
from __future__ import annotations

from typing import Protocol

import httpx

from services.ms3_presupuestos.config import settings
from shared.contratos_decisiones import AplicacionDecisionRespuesta


class OrdenNoVisible(Exception):
    """La orden no existe o no pertenece al usuario."""


class ServicioOrdenesNoDisponible(Exception):
    """MS2 no respondió de forma utilizable; no se puede validar la orden."""


class VerificadorOrdenes(Protocol):
    def verificar_acceso(self, orden_id: int, token: str) -> None:
        """Lanza OrdenNoVisible o ServicioOrdenesNoDisponible si no hay acceso."""

    def verificar_propiedad(self, orden_id: int, token: str) -> None:
        """Exige propietario; la visibilidad por otro rol no es suficiente."""


class VerificadorOrdenesHttp:
    def __init__(self, url_base: str, timeout: float) -> None:
        self.url_base = url_base.rstrip("/")
        self.timeout = timeout

    def verificar_acceso(self, orden_id: int, token: str) -> None:
        self._verificar(f"/ordenes/{orden_id}", orden_id, token)

    def verificar_propiedad(self, orden_id: int, token: str) -> None:
        respuesta = self._verificar(f"/ordenes/{orden_id}?solo_propietario=true", orden_id, token)
        if respuesta.headers.get("X-Orden-Propiedad-Verificada") != "true":
            # Un MS2 anterior puede ignorar la query y devolver visibilidad
            # administrativa. Sin confirmación explícita, no guardar la decisión.
            raise ServicioOrdenesNoDisponible("MS2 no confirmó la verificación de propiedad")

    def _verificar(self, ruta: str, orden_id: int, token: str) -> httpx.Response:
        try:
            respuesta = httpx.get(
                f"{self.url_base}{ruta}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise ServicioOrdenesNoDisponible(str(exc)) from exc
        if respuesta.status_code == 200:
            return respuesta
        if respuesta.status_code in (403, 404):
            raise OrdenNoVisible(orden_id)
        raise ServicioOrdenesNoDisponible(f"MS2 respondió {respuesta.status_code}")


def obtener_verificador_ordenes() -> VerificadorOrdenes:
    return VerificadorOrdenesHttp(settings.MS2_URL, settings.MS2_TIMEOUT_SEGUNDOS)


class DecisionAplicacionPendienteError(Exception):
    """MS3 guardó la decisión, pero el efecto en MS2 no está confirmado."""

    def __init__(self, orden_id: int, decision_id: int,
                 estado_ms2: int | None = None, detalle_ms2: str | None = None) -> None:
        super().__init__("La aplicación en MS2 no está confirmada")
        self.orden_id = orden_id
        self.decision_id = decision_id
        self.estado_ms2 = estado_ms2
        self.detalle_ms2 = detalle_ms2


class CoordinadorOrdenes(Protocol):
    def aplicar(self, orden_id: int, decision_id: int, token: str) -> AplicacionDecisionRespuesta: ...


class CoordinadorOrdenesHttp:
    def __init__(self, url_base: str, timeout: float) -> None:
        self.url_base = url_base.rstrip("/")
        self.timeout = timeout

    def aplicar(self, orden_id: int, decision_id: int, token: str) -> AplicacionDecisionRespuesta:
        try:
            respuesta = httpx.post(
                f"{self.url_base}/ordenes/{orden_id}/decisiones-presupuesto",
                json={"decision_id": decision_id},
                headers={"Authorization": f"Bearer {token}"}, timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise DecisionAplicacionPendienteError(orden_id, decision_id) from exc
        if respuesta.status_code != 200:
            try:
                body = respuesta.json()
                detalle = body.get("detail") if isinstance(body, dict) else None
            except ValueError:
                detalle = None
            raise DecisionAplicacionPendienteError(
                orden_id, decision_id, respuesta.status_code,
                detalle if isinstance(detalle, str) else None,
            )
        try:
            aplicada = AplicacionDecisionRespuesta.model_validate(respuesta.json())
        except ValueError as exc:
            raise DecisionAplicacionPendienteError(orden_id, decision_id) from exc
        if aplicada.decision_id != decision_id or aplicada.orden_id != orden_id:
            raise DecisionAplicacionPendienteError(orden_id, decision_id)
        return aplicada


def obtener_coordinador_ordenes() -> CoordinadorOrdenes:
    return CoordinadorOrdenesHttp(settings.MS2_URL, settings.MS2_TIMEOUT_SEGUNDOS)
