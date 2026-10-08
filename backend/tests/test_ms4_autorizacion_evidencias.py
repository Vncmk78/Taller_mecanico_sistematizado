"""Autorización y visibilidad de evidencias por rol (MS4) contra MS2.

Tarea *Validar autorización y visibilidad* (Semana 5): MS4 consulta MS2 con el
MISMO JWT para saber si la orden existe y es visible para el solicitante
(`integracion_ms2.py`, mismo contrato que MS3). Un `FakeVerificador` sustituye a
MS2 vía `app.dependency_overrides[obtener_verificador_ordenes]`:

- cliente dueño lista solo lo visible; cliente ajeno → 404 "Orden no encontrada";
- cliente/mecánico ajeno en detalle/descarga → 404 con el MISMO body que una
  evidencia inexistente (no enumeración);
- mecánico asignado sube (201); no asignado → 404 sin filas ni objetos;
- cliente no sube (403) y el verificador no se llama;
- administrador: el listado incluye las eliminadas y no consulta MS2 en
  detalle/descarga (auditoría);
- multirol cliente+mecánico se comporta por unión (alcance del mecánico);
- MS2 caído → 503 en subir/listar/detalle/descarga, sin filas ni objetos en subir;
- `VerificadorOrdenesHttp`: reenvía el JWT a `{MS2_URL}/ordenes/{id}`, 403/404 →
  `OrdenNoVisible`, resto de errores/timeouts → `ServicioOrdenesNoDisponible`.
"""
from __future__ import annotations

import uuid
from collections.abc import Generator
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from services.ms4_evidencias import integracion_ms2
from services.ms4_evidencias.db import get_db
from services.ms4_evidencias.dependencies import obtener_s3, obtener_s3_publico
from services.ms4_evidencias.integracion_ms2 import (
    OrdenNoVisible,
    ServicioOrdenesNoDisponible,
    VerificadorOrdenesHttp,
    obtener_verificador_ordenes,
)
from services.ms4_evidencias.main import app
from services.ms4_evidencias.models import Base
from services.ms4_evidencias.models.evidencia import EstadoEvidencia
from services.ms4_evidencias.services.almacenamiento import crear_cliente_s3_publico
from shared.auth import NombreRol

from test_ms4_api_evidencias import (
    ORDEN,
    _contar_filas,
    _crear_settings_publico,
    _escenario_visibilidad,
    _sembrar,
    _subir,
    _token,
)
from test_ms4_recepcion import FakeS3

_MSG_ORDENES = "El servicio de órdenes no está disponible"


class FakeVerificador:
    """Falso MS2: en `visibles` van las órdenes visibles para este usuario."""

    def __init__(self, visibles: set[int] | None = None) -> None:
        self.visibles = None if visibles is None else set(visibles)
        self.caido = False
        self.llamadas: list[tuple[int, str]] = []

    def verificar_acceso(self, orden_id: int, token: str) -> None:
        self.llamadas.append((orden_id, token))
        if self.caido:
            raise ServicioOrdenesNoDisponible("MS2 caído")
        if self.visibles is not None and orden_id not in self.visibles:
            raise OrdenNoVisible(orden_id)


@pytest.fixture
def sesion() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)
    sesion = fabrica()
    try:
        yield sesion
    finally:
        sesion.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def s3() -> FakeS3:
    return FakeS3()


@pytest.fixture
def s3_publico():
    return crear_cliente_s3_publico(_crear_settings_publico())


@contextmanager
def api_con(sesion: Session, s3: FakeS3, s3_publico, verificador: FakeVerificador):
    """TestClient con db/S3/verificador falsos, limpia los overrides al salir."""

    def reemplazar_db():
        yield sesion

    app.dependency_overrides[get_db] = reemplazar_db
    app.dependency_overrides[obtener_s3] = lambda: s3
    app.dependency_overrides[obtener_s3_publico] = lambda: s3_publico
    app.dependency_overrides[obtener_verificador_ordenes] = lambda: verificador
    try:
        with TestClient(app) as cliente:
            yield cliente
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Cliente: dueño vs ajeno (la propiedad la decide MS2)                        #
# --------------------------------------------------------------------------- #

def test_cliente_dueño_lista_solo_evidencias_visibles(
    sesion: Session, s3: FakeS3, s3_publico
) -> None:
    escenario = _escenario_visibilidad()
    _sembrar(sesion, *escenario)
    verificador = FakeVerificador(visibles={ORDEN})
    token = _token(9, NombreRol.CLIENTE)

    with api_con(sesion, s3, s3_publico, verificador) as cliente:
        respuesta = cliente.get(
            "/evidencias",
            params={"orden_id": ORDEN},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert respuesta.status_code == 200
    ids = [e["evidencia_id"] for e in respuesta.json()]
    esperado = [
        e.evidencia_id
        for e in escenario
        if e.visible_cliente
        and e.estado == EstadoEvidencia.CONFIRMADA
        and e.eliminada_en is None
    ]
    assert sorted(ids) == sorted(str(e) for e in esperado)
    assert verificador.llamadas == [(ORDEN, token)]


def test_cliente_ajeno_no_puede_listar_responde_404(
    sesion: Session, s3: FakeS3, s3_publico
) -> None:
    _sembrar(sesion, *(_escenario_visibilidad()))
    verificador = FakeVerificador(visibles={999})
    token = _token(9, NombreRol.CLIENTE)

    with api_con(sesion, s3, s3_publico, verificador) as cliente:
        respuesta = cliente.get(
            "/evidencias",
            params={"orden_id": ORDEN},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Orden no encontrada"}
    assert verificador.llamadas == [(ORDEN, token)]


def test_cliente_ajeno_detalle_y_descarga_responde_404_igual_a_inexistente(
    sesion: Session, s3: FakeS3, s3_publico
) -> None:
    _, no_visible, visible, _, _ = _escenario_visibilidad()
    _sembrar(sesion, no_visible, visible)
    verificador = FakeVerificador(visibles={999})
    token = _token(9, NombreRol.CLIENTE)

    with api_con(sesion, s3, s3_publico, verificador) as cliente:
        cabeceras = {"Authorization": f"Bearer {token}"}
        ajeno = cliente.get(f"/evidencias/{visible.evidencia_id}", headers=cabeceras)
        descarga = cliente.get(
            f"/evidencias/{visible.evidencia_id}/descarga", headers=cabeceras
        )
        inexistente = cliente.get(
            f"/evidencias/{uuid.uuid4()}", headers=cabeceras
        )

    # La evidencia ajena "no existe": mismo 404 que un UUID inexistente (no enumera).
    assert ajeno.status_code == 404
    assert descarga.status_code == 404
    assert inexistente.status_code == 404
    assert ajeno.json() == inexistente.json() == {"detail": "Evidencia no encontrada"}
    # MS4 pidió la orden al falso MS2 con el token del cliente, en ambos casos.
    assert [orden for orden, _ in verificador.llamadas] == [ORDEN, ORDEN]


def test_multirol_cliente_mecanico_ve_como_mecanico(
    sesion: Session, s3: FakeS3, s3_publico
) -> None:
    pendiente, no_visible, visible, eliminada, anulada = _escenario_visibilidad()
    _sembrar(sesion, pendiente, no_visible, visible, eliminada, anulada)
    verificador = FakeVerificador(visibles={ORDEN})
    token = _token(15, NombreRol.CLIENTE, NombreRol.MECANICO)
    cabeceras = {"Authorization": f"Bearer {token}"}

    with api_con(sesion, s3, s3_publico, verificador) as cliente:
        lista = cliente.get("/evidencias", params={"orden_id": ORDEN}, headers=cabeceras)
        detalle_no_visible = cliente.get(f"/evidencias/{no_visible.evidencia_id}", headers=cabeceras)
        detalle_eliminada = cliente.get(f"/evidencias/{eliminada.evidencia_id}", headers=cabeceras)

    # Unión de roles (matriz §3.1): el alcance de mecánico manda sobre el filtro
    # estricto del cliente → ve la no-visible pero no las eliminadas.
    assert lista.status_code == 200
    assert len(lista.json()) == 4  # pendiente, no_visible, visible, anulada
    assert detalle_no_visible.status_code == 200
    assert detalle_eliminada.status_code == 404


# --------------------------------------------------------------------------- #
# Mecánico: solo órdenes que atiende                                          #
# --------------------------------------------------------------------------- #

def test_mecanico_asignado_puede_subir(
    sesion: Session, s3: FakeS3, s3_publico
) -> None:
    verificador = FakeVerificador(visibles={1})
    token = _token(7, NombreRol.MECANICO)

    with api_con(sesion, s3, s3_publico, verificador) as cliente:
        respuesta = _subir(cliente, token)

    assert respuesta.status_code == 201
    assert len(s3.objetos) == 1
    assert _contar_filas(sesion) == 1
    assert verificador.llamadas == [(1, token)]


def test_mecanico_no_asignado_no_puede_subir_y_no_deja_residuos(
    sesion: Session, s3: FakeS3, s3_publico
) -> None:
    verificador = FakeVerificador(visibles={999})
    token = _token(7, NombreRol.MECANICO)

    with api_con(sesion, s3, s3_publico, verificador) as cliente:
        respuesta = _subir(cliente, token)

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Orden no encontrada"}
    assert not s3.objetos
    assert _contar_filas(sesion) == 0
    assert verificador.llamadas == [(1, token)]


def test_cliente_no_puede_subir_y_el_verificador_no_se_llama(
    sesion: Session, s3: FakeS3, s3_publico
) -> None:
    verificador = FakeVerificador(visibles={1})

    with api_con(sesion, s3, s3_publico, verificador) as cliente:
        respuesta = _subir(cliente, _token(9, NombreRol.CLIENTE))

    assert respuesta.status_code == 403
    assert not s3.objetos
    assert _contar_filas(sesion) == 0
    assert verificador.llamadas == []


def test_mecanico_no_asignado_no_puede_listar(
    sesion: Session, s3: FakeS3, s3_publico
) -> None:
    _sembrar(sesion, *(_escenario_visibilidad()))
    verificador = FakeVerificador(visibles={999})

    with api_con(sesion, s3, s3_publico, verificador) as cliente:
        respuesta = cliente.get(
            "/evidencias",
            params={"orden_id": ORDEN},
            headers={"Authorization": f"Bearer {_token(7, NombreRol.MECANICO)}"},
        )

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Orden no encontrada"}


# --------------------------------------------------------------------------- #
# Administrador: ve todo y no consulta MS2 en detalle/descarga                #
# --------------------------------------------------------------------------- #

def test_administrador_lista_e_incluye_las_eliminadas(
    sesion: Session, s3: FakeS3, s3_publico
) -> None:
    escenario = _escenario_visibilidad()
    _sembrar(sesion, *escenario)
    verificador = FakeVerificador(visibles={ORDEN})
    token = _token(1, NombreRol.ADMINISTRADOR)

    with api_con(sesion, s3, s3_publico, verificador) as cliente:
        respuesta = cliente.get(
            "/evidencias",
            params={"orden_id": ORDEN},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert respuesta.status_code == 200
    assert len(respuesta.json()) == len(escenario)
    assert verificador.llamadas == [(ORDEN, token)]


def test_administrador_ve_eliminadas_en_detalle_y_descarga_sin_consultar_ms2(
    sesion: Session, s3: FakeS3, s3_publico
) -> None:
    eliminada = _escenario_visibilidad()[3]
    _sembrar(sesion, eliminada)
    # MS2 "caído" y sin órdenes visibles: si se consultase, no habría admin que vea.
    verificador = FakeVerificador(visibles=set())
    verificador.caido = True
    cabeceras = {
        "Authorization": f"Bearer {_token(1, NombreRol.ADMINISTRADOR)}"
    }

    with api_con(sesion, s3, s3_publico, verificador) as cliente:
        detalle = cliente.get(f"/evidencias/{eliminada.evidencia_id}", headers=cabeceras)
        descarga = cliente.get(
            f"/evidencias/{eliminada.evidencia_id}/descarga", headers=cabeceras
        )

    assert detalle.status_code == 200
    assert descarga.status_code == 200
    assert verificador.llamadas == []


def test_mecanico_que_atiende_la_orden_no_ve_la_eliminada(
    sesion: Session, s3: FakeS3, s3_publico
) -> None:
    eliminada = _escenario_visibilidad()[3]
    _sembrar(sesion, eliminada)
    verificador = FakeVerificador(visibles={ORDEN})

    with api_con(sesion, s3, s3_publico, verificador) as cliente:
        respuesta = cliente.get(
            f"/evidencias/{eliminada.evidencia_id}",
            headers={"Authorization": f"Bearer {_token(7, NombreRol.MECANICO)}"},
        )

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Evidencia no encontrada"}
    assert [orden for orden, _ in verificador.llamadas] == [ORDEN]


# --------------------------------------------------------------------------- #
# MS2 caído → 503 en los cuatro endpoints                                     #
# --------------------------------------------------------------------------- #

def test_ms2_caido_en_subida_responde_503_sin_filas_ni_objetos(
    sesion: Session, s3: FakeS3, s3_publico
) -> None:
    verificador = FakeVerificador(visibles={1})
    verificador.caido = True

    with api_con(sesion, s3, s3_publico, verificador) as cliente:
        respuesta = _subir(cliente, _token(7, NombreRol.MECANICO))

    assert respuesta.status_code == 503
    assert respuesta.json() == {"detail": _MSG_ORDENES}
    assert not s3.objetos
    assert _contar_filas(sesion) == 0


def test_ms2_caido_en_listado_responde_503(
    sesion: Session, s3: FakeS3, s3_publico
) -> None:
    verificador = FakeVerificador(visibles={ORDEN})
    verificador.caido = True

    with api_con(sesion, s3, s3_publico, verificador) as cliente:
        respuesta = cliente.get(
            "/evidencias",
            params={"orden_id": ORDEN},
            headers={"Authorization": f"Bearer {_token(9, NombreRol.CLIENTE)}"},
        )

    assert respuesta.status_code == 503
    assert respuesta.json() == {"detail": _MSG_ORDENES}


@pytest.mark.parametrize("ruta", ["detalle", "descarga"])
def test_ms2_caido_en_detalle_y_descarga_responde_503(
    sesion: Session, s3: FakeS3, s3_publico, ruta: str
) -> None:
    visible = _escenario_visibilidad()[2]
    _sembrar(sesion, visible)
    verificador = FakeVerificador(visibles={ORDEN})
    verificador.caido = True

    url = f"/evidencias/{visible.evidencia_id}"
    if ruta == "descarga":
        url += "/descarga"

    with api_con(sesion, s3, s3_publico, verificador) as cliente:
        respuesta = cliente.get(
            url,
            headers={"Authorization": f"Bearer {_token(9, NombreRol.CLIENTE)}"},
        )

    assert respuesta.status_code == 503
    assert respuesta.json() == {"detail": _MSG_ORDENES}


# --------------------------------------------------------------------------- #
# VerificadorOrdenesHttp: unidad (httpx simulado, no se levanta MS2)          #
# --------------------------------------------------------------------------- #

def _simular(monkeypatch: pytest.MonkeyPatch, respuesta) -> list[dict]:
    llamadas: list[dict] = []

    def falso_get(url: str, *, headers: dict, timeout: float):
        llamadas.append({"url": url, "headers": headers, "timeout": timeout})
        if isinstance(respuesta, Exception):
            raise respuesta
        return httpx.Response(respuesta, request=httpx.Request("GET", url))

    monkeypatch.setattr(integracion_ms2.httpx, "get", falso_get)
    return llamadas


def test_verificador_reenvia_el_mismo_jwt_a_ms2(monkeypatch: pytest.MonkeyPatch) -> None:
    llamadas = _simular(monkeypatch, 200)
    VerificadorOrdenesHttp("http://ms2:8002/", 2.5).verificar_acceso(31, "token-del-cliente")
    assert llamadas == [{"url": "http://ms2:8002/ordenes/31",
                         "headers": {"Authorization": "Bearer token-del-cliente"},
                         "timeout": 2.5}]


@pytest.mark.parametrize("codigo", [403, 404])
def test_verificador_orden_ajena_o_inexistente(
    monkeypatch: pytest.MonkeyPatch, codigo: int
) -> None:
    _simular(monkeypatch, codigo)
    with pytest.raises(OrdenNoVisible):
        VerificadorOrdenesHttp("http://ms2", 1).verificar_acceso(31, "t")


@pytest.mark.parametrize(
    "respuesta",
    [500, 401, httpx.ConnectError("caído"),
     httpx.ConnectTimeout("lento"), httpx.ReadTimeout("lento")],
)
def test_verificador_ms2_no_disponible(
    monkeypatch: pytest.MonkeyPatch, respuesta
) -> None:
    _simular(monkeypatch, respuesta)
    with pytest.raises(ServicioOrdenesNoDisponible):
        VerificadorOrdenesHttp("http://ms2", 1).verificar_acceso(31, "t")


def test_verificador_dependencia_usa_la_configuracion() -> None:
    verificador = integracion_ms2.obtener_verificador_ordenes()
    assert verificador.url_base == integracion_ms2.settings.MS2_URL.rstrip("/")
    assert verificador.timeout == integracion_ms2.settings.MS2_TIMEOUT_SEGUNDOS