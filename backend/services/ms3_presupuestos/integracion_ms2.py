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


class OrdenNoVisible(Exception):
    """La orden no existe o no pertenece al usuario."""


class ServicioOrdenesNoDisponible(Exception):
    """MS2 no respondió de forma utilizable; no se puede validar la orden."""


class VerificadorOrdenes(Protocol):
    def verificar_acceso(self, orden_id: int, token: str) -> None:
        """Lanza OrdenNoVisible o ServicioOrdenesNoDisponible si no hay acceso."""


class VerificadorOrdenesHttp:
    def __init__(self, url_base: str, timeout: float) -> None:
        self.url_base = url_base.rstrip("/")
        self.timeout = timeout

    def verificar_acceso(self, orden_id: int, token: str) -> None:
        try:
            respuesta = httpx.get(
                f"{self.url_base}/ordenes/{orden_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise ServicioOrdenesNoDisponible(str(exc)) from exc
        if respuesta.status_code == 200:
            return
        if respuesta.status_code in (403, 404):
            raise OrdenNoVisible(orden_id)
        raise ServicioOrdenesNoDisponible(f"MS2 respondió {respuesta.status_code}")


def obtener_verificador_ordenes() -> VerificadorOrdenes:
    return VerificadorOrdenesHttp(settings.MS2_URL, settings.MS2_TIMEOUT_SEGUNDOS)
