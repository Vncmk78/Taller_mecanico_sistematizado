"""Consulta a MS3 a qué orden pertenece un presupuesto (asociación, Semana 6).

Una evidencia de contexto `presupuesto` guarda `presupuesto_id` como
referencia lógica a MS3. Para no asociar una foto al presupuesto de OTRA
orden, MS4 llama a `GET {MS3_URL}/presupuestos/{presupuesto_id}` con el MISMO
JWT del usuario (solo suben Mecánico y Administrador, que MS3 trata como
personal) y compara el `orden_id` de la respuesta:

    200 → devuelve el `orden_id` del presupuesto
    404 / 403 → el presupuesto no existe o no es visible → PresupuestoNoEncontrado
    otro / sin conexión / timeout / body inválido → ServicioPresupuestosNoDisponible

`VerificadorPresupuestos` es el puerto; el router lo recibe por dependencia,
así las pruebas lo reemplazan sin levantar MS3. El JWT reenviado nunca se
loguea.
"""
from __future__ import annotations

from typing import Protocol

import httpx

from services.ms4_evidencias.config import settings


class PresupuestoNoEncontrado(Exception):
    """El presupuesto no existe o no es visible para el usuario."""


class ServicioPresupuestosNoDisponible(Exception):
    """MS3 no respondió de forma utilizable; no se puede validar el presupuesto."""


class VerificadorPresupuestos(Protocol):
    def orden_del_presupuesto(self, presupuesto_id: int, token: str) -> int:
        """`orden_id` al que pertenece el presupuesto.

        Lanza PresupuestoNoEncontrado o ServicioPresupuestosNoDisponible.
        """


class VerificadorPresupuestosHttp:
    def __init__(self, url_base: str, timeout: float) -> None:
        self.url_base = url_base.rstrip("/")
        self.timeout = timeout

    def orden_del_presupuesto(self, presupuesto_id: int, token: str) -> int:
        try:
            respuesta = httpx.get(
                f"{self.url_base}/presupuestos/{presupuesto_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise ServicioPresupuestosNoDisponible(str(exc)) from exc
        if respuesta.status_code in (403, 404):
            raise PresupuestoNoEncontrado(presupuesto_id)
        if respuesta.status_code != 200:
            raise ServicioPresupuestosNoDisponible(
                f"MS3 respondió {respuesta.status_code}"
            )
        try:
            orden_id = respuesta.json().get("orden_id")
        except (ValueError, AttributeError) as exc:
            raise ServicioPresupuestosNoDisponible("MS3 respondió un body inválido") from exc
        if not isinstance(orden_id, int) or isinstance(orden_id, bool):
            raise ServicioPresupuestosNoDisponible("MS3 no informó la orden del presupuesto")
        return orden_id


def obtener_verificador_presupuestos() -> VerificadorPresupuestos:
    return VerificadorPresupuestosHttp(settings.MS3_URL, settings.MS3_TIMEOUT_SEGUNDOS)
