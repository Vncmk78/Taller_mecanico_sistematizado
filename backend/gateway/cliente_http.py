"""Cliente HTTPX compartido de la API Gateway.

La Gateway reutiliza un único `AsyncClient` (pool de conexiones) en lugar de
crear uno por petición. Se crea de forma **perezosa** (`obtener_cliente`) para
que funcione igual en local, en tests y en funciones serverless; el lifespan
de la app solo lo cierra al apagar (`cerrar_cliente`, ver `gateway/main.py`).

Los timeouts se configuran por fase (decisión 1 de `estudio-httpx-proxy.md`) y
el prefijo `evidencias` usa read/write más largos porque sube archivos.
"""
from __future__ import annotations

import asyncio

import httpx

from gateway.config import settings

# Referencias del cliente compartido y del event loop en que se creó.
_cliente: httpx.AsyncClient | None = None
_loop: asyncio.AbstractEventLoop | None = None

_LIMITES = httpx.Limits(max_connections=100, max_keepalive_connections=20)


def timeout_para(prefijo: str) -> httpx.Timeout:
    """Timeout por fase para un prefijo; `evidencias` usa un plazo mayor.

    read y write se amplían para el prefijo de archivos; connect y pool se
    mantienen en los valores generales. No se define `total`: cada fase tiene
    su propio techo.
    """
    archivos = prefijo == "evidencias"
    return httpx.Timeout(
        connect=settings.TIMEOUT_CONNECT_SECONDS,
        read=(
            settings.TIMEOUT_ARCHIVOS_SECONDS
            if archivos
            else settings.TIMEOUT_READ_SECONDS
        ),
        write=(
            settings.TIMEOUT_ARCHIVOS_SECONDS
            if archivos
            else settings.TIMEOUT_WRITE_SECONDS
        ),
        pool=settings.TIMEOUT_POOL_SECONDS,
    )


def obtener_cliente() -> httpx.AsyncClient:
    """Devuelve el cliente compartido, creándolo la primera vez que se pide.

    Guarda el event loop en que se creó: si la llamada llega desde otro loop
    (un `TestClient` sin `with`, o una función serverless), crea uno nuevo. El
    cliente del loop anterior no se cierra (ese loop ya no existe); solo se
    reemplaza.
    """
    global _cliente, _loop
    loop = asyncio.get_running_loop()
    if _cliente is None or _loop is not loop:
        _cliente = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=settings.TIMEOUT_CONNECT_SECONDS,
                read=settings.TIMEOUT_READ_SECONDS,
                write=settings.TIMEOUT_WRITE_SECONDS,
                pool=settings.TIMEOUT_POOL_SECONDS,
            ),
            # Un solo reintento, solo al conectar (decisión 5): nunca reintenta
            # una petición ya enviada. OJO: con un `transport` propio, HTTPX
            # ignora el `limits=` del cliente; los límites van en el transporte.
            transport=httpx.AsyncHTTPTransport(limits=_LIMITES, retries=1),
            follow_redirects=False,
        )
        _loop = loop
    return _cliente


async def cerrar_cliente() -> None:
    """Cierra el cliente compartido si existe y lo deja en `None`."""
    global _cliente, _loop
    if _cliente is not None:
        await _cliente.aclose()
        _cliente = None
        _loop = None


def reset_cliente() -> None:
    """Descarta la referencia al cliente compartido sin cerrarlo.

    Lo usan los tests para que cada caso parta sin estado: el cliente puede
    pertenecer al event loop de un `TestClient` anterior que ya no existe, y
    cerrarlo desde otro loop no es posible.
    """
    global _cliente, _loop
    _cliente = None
    _loop = None
