"""Correlación de solicitudes entre la Gateway y los microservicios (Semana 10).

SCRUM-582. La Gateway ya asigna un `X-Request-ID` a cada petición y lo reenvía
al microservicio destino (gateway/middleware.py y gateway/routers/proxy.py).
Este módulo hace que **cada microservicio** lo aproveche de la misma forma:

1. `MiddlewareCorrelacion` lee `X-Request-ID` de la petición entrante; si no
   viene o no cumple el formato de la Gateway (`^[A-Za-z0-9-]{1,128}$`),
   genera un UUID. Lo guarda en un `ContextVar` mientras dura la petición y lo
   devuelve en la cabecera `X-Request-ID` de **toda** respuesta, incluidos los
   errores 4xx/5xx.
2. Al terminar escribe una línea de log por petición, en formato `clave=valor`
   fácil de filtrar con grep:

       evento=solicitud servicio=ms2_taller request_id=abc-123 metodo=GET
       ruta=/ordenes/7 estado_http=503 duracion_ms=3012

   Nunca registra cabeceras (ahí viaja el JWT), body ni query string. Los
   health checks van en DEBUG para no llenar los logs.
3. `cabeceras_correlacion()` devuelve `{"X-Request-ID": <id recibido>}` para
   agregarlo a las llamadas HTTP salientes entre microservicios (MS3 -> MS2,
   MS2 -> MS1/MS3). Así una petición que encadena varios servicios deja el
   **mismo** identificador en todos sus logs.

   Solo se propaga un ID **recibido** (el que puso la Gateway o el servicio que
   llamó). Un ID generado localmente —petición directa al microservicio, sin
   pasar por la Gateway— identifica solo esa línea de log y no se reenvía: la
   Gateway es el único origen de la correlación. Fuera de una petición (workers
   en segundo plano, pruebas unitarias) también devuelve `{}`.

MS4 conserva su propio middleware (services/ms4_evidencias/services/registro.py,
Semana 6), que ya cumplía 1 y 2 con su lista blanca de campos; desde la Semana
10 también propaga el identificador en sus llamadas salientes.
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CABECERA_REQUEST_ID = "X-Request-ID"
_CABECERA_MIN = CABECERA_REQUEST_ID.lower().encode("latin-1")

# Mismo formato que acepta la Gateway (gateway/middleware.py): letras, números
# y guiones, hasta 128 caracteres. Cualquier otro valor se reemplaza: evita
# inyectar saltos de línea o texto arbitrario en los logs.
_ID_VALIDO = re.compile(r"^[A-Za-z0-9-]{1,128}$")

_request_id_actual: ContextVar[str | None] = ContextVar(
    "sgtm_request_id", default=None
)
# ID recibido en la cabecera (None si se generó localmente): es el único que
# se propaga a otros servicios.
_request_id_recibido: ContextVar[str | None] = ContextVar(
    "sgtm_request_id_recibido", default=None
)

logger = logging.getLogger("sgtm.correlacion")


def normalizar_request_id(valor: str | None) -> str | None:
    """Devuelve `valor` si tiene el formato válido; si no, `None`."""
    if valor and _ID_VALIDO.fullmatch(valor):
        return valor
    return None


def request_id_actual() -> str | None:
    """Identificador de la petición en curso, o `None` fuera de una petición."""
    return _request_id_actual.get()


def cabeceras_correlacion() -> dict[str, str]:
    """Cabecera para propagar el identificador a otro microservicio.

    Uso: `headers={"Authorization": ..., **cabeceras_correlacion()}`. Fuera de
    una petición devuelve `{}`, así las llamadas de los workers y las pruebas
    unitarias no cambian.
    """
    recibido = _request_id_recibido.get()
    return {CABECERA_REQUEST_ID: recibido} if recibido else {}


def configurar_logs(nivel: str | int = logging.INFO) -> None:
    """Deja `sgtm.correlacion` escribiendo a consola con fecha y nivel.

    Tiene su propio handler porque uvicorn no configura el logger raíz; llamar
    a la función varias veces no agrega handlers duplicados. Sigue propagando
    a la raíz para que `caplog` lo capture en las pruebas.
    """
    logger.setLevel(nivel)
    if not any(getattr(h, "_sgtm_correlacion", False) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        handler._sgtm_correlacion = True  # type: ignore[attr-defined]
        logger.addHandler(handler)


def _nivel_para(estado_http: int, ruta: str) -> int:
    if ruta.startswith("/health"):
        return logging.DEBUG
    if estado_http >= 500:
        return logging.ERROR
    if estado_http >= 400:
        return logging.WARNING
    return logging.INFO


def _limpiar(valor: object) -> str:
    """Sin espacios ni caracteres de control (evita *log injection*), máx. 200."""
    return re.sub(r"[\s\x00-\x1f\x7f]+", "_", str(valor))[:200]


class MiddlewareCorrelacion:
    """Middleware ASGI: fija el `request_id`, lo devuelve y registra la petición."""

    def __init__(self, app: ASGIApp, servicio: str) -> None:
        self.app = app
        self.servicio = servicio

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        recibido = self._extraer(scope)
        request_id = recibido or str(uuid.uuid4())
        token = _request_id_actual.set(request_id)
        token_recibido = _request_id_recibido.set(recibido)
        estado = {"http": 500}
        inicio = time.perf_counter()

        async def enviar(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                estado["http"] = mensaje["status"]
                cabeceras = list(mensaje.get("headers", []))
                if not any(clave.lower() == _CABECERA_MIN for clave, _ in cabeceras):
                    cabeceras.append((_CABECERA_MIN, request_id.encode("latin-1")))
                    mensaje["headers"] = cabeceras
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        except Exception as exc:
            estado["http"] = 500
            # Solo el tipo: el mensaje puede traer SQL, URLs o datos internos.
            logger.error(
                "evento=error_no_controlado servicio=%s request_id=%s ruta=%s error=%s",
                self.servicio,
                request_id,
                _limpiar(scope.get("path", "")),
                type(exc).__name__,
            )
            raise
        finally:
            ruta = scope.get("path", "")
            logger.log(
                _nivel_para(estado["http"], ruta),
                "evento=solicitud servicio=%s request_id=%s metodo=%s ruta=%s "
                "estado_http=%s duracion_ms=%s",
                self.servicio,
                request_id,
                scope.get("method", "-"),
                _limpiar(ruta),
                estado["http"],
                round((time.perf_counter() - inicio) * 1000),
            )
            _request_id_actual.reset(token)
            _request_id_recibido.reset(token_recibido)

    @staticmethod
    def _extraer(scope: Scope) -> str | None:
        for nombre, valor in scope.get("headers", []):
            if nombre.lower() == _CABECERA_MIN:
                return normalizar_request_id(valor.decode("latin-1"))
        return None
