"""Pruebas del contrato HTTP, autenticación y reintento del outbox MS2."""
from __future__ import annotations

import asyncio
from uuid import uuid4

import httpx
from pydantic import SecretStr

from services.ms2_taller.config import settings
from services.ms2_taller.services import publicador_eventos as publicador


def _evento_reclamado() -> publicador.EventoReclamado:
    evento_id = str(uuid4())
    return publicador.EventoReclamado(
        outbox_id=1,
        evento_id=evento_id,
        intentos=1,
        payload={"evento_id": evento_id, "tipo": "orden.estado_cambiado"},
    )


def test_reintento_usa_espera_exponencial_acotada():
    assert [publicador.segundos_espera_reintento(n, 300) for n in range(1, 7)] == [
        1, 2, 4, 8, 16, 32,
    ]
    assert publicador.segundos_espera_reintento(20, 300) == 300


def test_publicador_autentica_y_confirma_el_mismo_evento(monkeypatch):
    evento = _evento_reclamado()
    publicado: list[int] = []
    monkeypatch.setattr(settings, "EVENT_SHARED_SECRET", SecretStr("s" * 40))
    monkeypatch.setattr(settings, "MS1_URL", "http://ms1.test/")
    monkeypatch.setattr(publicador, "_reclamar_evento", lambda: evento)
    monkeypatch.setattr(publicador, "_marcar_publicado", publicado.append)

    def responder(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://ms1.test/interno/eventos/ordenes/estado"
        assert request.headers["X-Service-Token"] == "s" * 40
        assert request.read()
        return httpx.Response(200, json={"evento_id": evento.evento_id})

    async def publicar() -> bool:
        async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as cliente:
            return await publicador.publicar_siguiente_evento(cliente)

    assert asyncio.run(publicar()) is True
    assert publicado == [evento.outbox_id]


def test_error_http_programa_reintento_sin_descartar_evento(monkeypatch):
    evento = _evento_reclamado()
    reintentos: list[tuple[publicador.EventoReclamado, str]] = []
    monkeypatch.setattr(settings, "EVENT_SHARED_SECRET", SecretStr("s" * 40))
    monkeypatch.setattr(publicador, "_reclamar_evento", lambda: evento)
    monkeypatch.setattr(
        publicador,
        "_programar_reintento",
        lambda fila, error: reintentos.append((fila, error)),
    )

    async def publicar() -> bool:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(503, text="temporal")
            )
        ) as cliente:
            return await publicador.publicar_siguiente_evento(cliente)

    assert asyncio.run(publicar()) is True
    assert len(reintentos) == 1
    assert reintentos[0][0] == evento
    assert "HTTPStatusError" in reintentos[0][1]
