"""Logs de MS4 útiles para diagnosticar, sin contenido sensible (Semana 6).

Checklist 5.5: los logs nunca incluyen el contenido del archivo, el JWT, las
URLs prefirmadas ni la clave del objeto en el almacenamiento. Para que eso no
dependa de la memoria de quien escribe un log nuevo, todos los eventos pasan
por `registrar`, que:

- solo acepta campos de una **lista blanca** (`CAMPOS_PERMITIDOS`); cualquier
  otro campo se descarta y se anota en `campos_descartados` (solo el nombre,
  nunca el valor);
- limpia los valores: sin saltos de línea (evita *log injection*), sin
  espacios dentro del valor y con un máximo de 80 caracteres;
- agrega solo el `request_id` de la solicitud en curso (lo fija el middleware
  `MiddlewareRegistro`), para seguir una subida desde la Gateway hasta MS4.

Formato: una línea `clave=valor` por evento, fácil de filtrar con grep:

    evento=evidencia_subida request_id=abc123 evidencia_id=... orden_id=31 ...

El nombre original del archivo tampoco se registra: puede traer datos
personales (nombre del cliente, patente).
"""
from __future__ import annotations

import logging
import re
import time
from contextvars import ContextVar
from typing import Any

from services.ms4_evidencias.services.contexto import (
    CABECERA_REQUEST_ID,
    normalizar_request_id,
)

logger = logging.getLogger("ms4.evidencias")

CAMPOS_PERMITIDOS = frozenset(
    {
        "metodo",
        "ruta",
        "estado_http",
        "duracion_ms",
        "usuario_id",
        "evidencia_id",
        "orden_id",
        "presupuesto_id",
        "contexto",
        "tipo_archivo",
        "content_type",
        "tamano_bytes",
        "motivo",
        "servicio",
        "error",
        "pendiente_limpieza",
    }
)

_LARGO_MAXIMO = 80
_NO_SEGURO = re.compile(r"[\s\x00-\x1f\x7f]+")

_request_id_actual: ContextVar[str | None] = ContextVar("ms4_request_id", default=None)


def configurar_logs(nivel: str = "INFO") -> None:
    """Deja el logger de MS4 escribiendo a consola con fecha y nivel.

    Tiene su propio handler (no depende de la configuración de uvicorn) y no
    propaga a la raíz para no duplicar líneas. Llamarlo dos veces no agrega
    un segundo handler.
    """
    logger.setLevel(nivel)
    if not any(getattr(h, "_ms4", False) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        handler._ms4 = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    logger.propagate = False


def request_id_actual() -> str | None:
    """`request_id` de la solicitud en curso (None fuera de una solicitud)."""
    return _request_id_actual.get()


def _limpiar(valor: Any) -> str:
    texto = _NO_SEGURO.sub("_", str(valor))
    return texto[:_LARGO_MAXIMO]


def formatear(evento: str, campos: dict[str, Any]) -> str:
    """Arma la línea `evento=... clave=valor` aplicando la lista blanca."""
    partes = [f"evento={_limpiar(evento)}"]
    request_id = request_id_actual()
    if request_id:
        partes.append(f"request_id={request_id}")
    descartados = []
    for nombre, valor in campos.items():
        if nombre not in CAMPOS_PERMITIDOS:
            descartados.append(nombre)
            continue
        if valor is None:
            continue
        partes.append(f"{nombre}={_limpiar(valor)}")
    if descartados:
        partes.append(f"campos_descartados={_limpiar(','.join(sorted(descartados)))}")
    return " ".join(partes)


def registrar(evento: str, nivel: int = logging.INFO, **campos: Any) -> None:
    """Registra un evento de MS4 con campos de la lista blanca."""
    if logger.isEnabledFor(nivel):
        logger.log(nivel, formatear(evento, campos))


def nivel_para(estado_http: int) -> int:
    """INFO para éxitos, WARNING para rechazos del cliente, ERROR para 5xx."""
    if estado_http >= 500:
        return logging.ERROR
    if estado_http >= 400:
        return logging.WARNING
    return logging.INFO


class MiddlewareRegistro:
    """Middleware ASGI: fija el `request_id` y registra cada solicitud.

    Por cada solicitud HTTP escribe un evento `solicitud` con método, ruta (sin
    query string), estado, duración y el usuario si se autenticó
    (`request.state.usuario_id`, lo fija la dependencia de autenticación). Los
    healthchecks se registran en DEBUG para no llenar los logs.
    Nunca registra cabeceras (ahí viaja el JWT), el body ni la query string.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        cabeceras = {
            nombre.decode("latin-1").lower(): valor.decode("latin-1")
            for nombre, valor in scope.get("headers", [])
        }
        request_id = normalizar_request_id(cabeceras.get(CABECERA_REQUEST_ID.lower()))
        token = _request_id_actual.set(request_id)
        estado = {"http": 500}
        inicio = time.perf_counter()

        async def enviar(mensaje) -> None:
            if mensaje["type"] == "http.response.start":
                estado["http"] = mensaje["status"]
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        except Exception as exc:
            estado["http"] = 500
            # Solo el tipo: el mensaje puede traer bucket, claves o URLs internas.
            # El traceback completo queda en DEBUG, para depurar en local.
            registrar(
                "error_no_controlado",
                logging.ERROR,
                ruta=scope.get("path"),
                error=type(exc).__name__,
            )
            logger.debug("traceback del error no controlado", exc_info=True)
            raise
        finally:
            ruta = scope.get("path", "")
            usuario_id = scope.get("state", {}).get("usuario_id")
            nivel = logging.DEBUG if ruta.startswith("/health") else nivel_para(estado["http"])
            registrar(
                "solicitud",
                nivel,
                metodo=scope.get("method"),
                ruta=ruta,
                estado_http=estado["http"],
                duracion_ms=round((time.perf_counter() - inicio) * 1000),
                usuario_id=usuario_id,
            )
            _request_id_actual.reset(token)
