"""Tratamiento de errores durante la carga de evidencias (MS4, Semana 6).

Toda falla en `POST /evidencias` termina en una respuesta controlada, sin
filtrar datos internos y sin dejar archivos ni filas a medias:

- La base falla al guardar después de subir → rollback, se borra el objeto
  (compensación) y se responde 503 "No se pudo guardar la evidencia, intenta
  nuevamente". Si el borrado también falla, `GuardadoEvidenciaError` trae la
  clave del objeto huérfano para registrarlo.
- El archivo recibido no se puede leer → 400 "No se pudo leer el archivo
  enviado", sin subir nada.
- Cualquier excepción no prevista → 500 con un mensaje genérico (manejador de
  main.py), sin el mensaje de la excepción ni el traceback.
- Las HTTPException y los 422 de validación de FastAPI no cambian.
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from services.ms4_evidencias.main import MENSAJE_ERROR_INTERNO, app
from services.ms4_evidencias.models.evidencia import ContextoEvidencia
from services.ms4_evidencias.routers import evidencias as router_evidencias
from services.ms4_evidencias.schemas.evidencia import DatosRecepcion
from services.ms4_evidencias.services.evidencias import (
    ArchivoIlegibleError,
    GuardadoEvidenciaError,
    recibir_evidencia,
)
from shared.auth import NombreRol

from archivos_muestra import JPEG_VALIDO
from test_ms4_api_evidencias import (  # noqa: F401  (fixtures reutilizados)
    BUCKET,
    _contar_filas,
    _subir,
    _token,
    api,
    s3,
    s3_publico,
    sesion,
)
from test_ms4_recepcion import FakeS3

MSG_GUARDADO = "No se pudo guardar la evidencia, intenta nuevamente"
MSG_ILEGIBLE = "No se pudo leer el archivo enviado"


class FakeS3SinBorrado(FakeS3):
    """FakeS3 cuyo borrado falla: la compensación no puede limpiar."""

    def delete_object(self, Bucket, Key):
        raise RuntimeError("MinIO no responde al borrar")


class ArchivoQueFalla(io.BytesIO):
    """Archivo temporal ilegible: read() lanza OSError."""

    def read(self, n: int = -1) -> bytes:
        raise OSError("disco ilegible")


def _mecanico() -> str:
    return _token(7, NombreRol.MECANICO)


def _sin_residuos(s3: FakeS3, sesion: Session) -> None:
    assert not s3.objetos
    assert _contar_filas(sesion) == 0


def _fallar_commit(sesion: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    def commit_que_falla(*args, **kwargs) -> None:
        raise RuntimeError("base caída: tabla evidencia bloqueada")

    monkeypatch.setattr(sesion, "commit", commit_que_falla)


def _recibir(sesion: Session, s3: FakeS3, archivo=None):
    return recibir_evidencia(
        sesion,
        s3,
        BUCKET,
        DatosRecepcion(orden_id=1, contexto=ContextoEvidencia.DIAGNOSTICO),
        archivo if archivo is not None else io.BytesIO(JPEG_VALIDO),
        "foto.jpg",
        "image/jpeg",
        7,
        "req-1",
    )


def _sin_datos_internos(cuerpo: str) -> None:
    # (El nombre del bucket se prueba con BUCKET_OCULTO en test_ms4_api_evidencias.)
    for prohibido in ("ordenes/", "http://", "Traceback", "base caída", "bucket="):
        assert prohibido not in cuerpo, prohibido


# --------------------------------------------------------------------------- #
# 1) Falla de la base al guardar                                              #
# --------------------------------------------------------------------------- #

def test_falla_de_la_base_responde_503_y_compensa(
    api: TestClient, s3: FakeS3, sesion: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fallar_commit(sesion, monkeypatch)

    respuesta = _subir(api, _mecanico())

    assert respuesta.status_code == 503
    assert respuesta.json() == {"detail": MSG_GUARDADO}
    _sin_datos_internos(respuesta.text)
    _sin_residuos(s3, sesion)


def test_con_compensacion_exitosa_no_hay_clave_huerfana(
    sesion: Session, s3: FakeS3, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fallar_commit(sesion, monkeypatch)

    with pytest.raises(GuardadoEvidenciaError) as error:
        _recibir(sesion, s3)

    assert error.value.clave_huerfana is None
    assert isinstance(error.value.__cause__, RuntimeError)
    _sin_residuos(s3, sesion)


def test_si_el_borrado_tambien_falla_se_informa_la_clave_huerfana(
    sesion: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    s3 = FakeS3SinBorrado()
    _fallar_commit(sesion, monkeypatch)

    with pytest.raises(GuardadoEvidenciaError) as error:
        _recibir(sesion, s3)

    [clave] = s3.objetos
    assert error.value.clave_huerfana == clave
    assert _contar_filas(sesion) == 0


def test_si_el_borrado_falla_la_api_responde_el_mismo_503(
    api: TestClient, sesion: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from services.ms4_evidencias.dependencies import obtener_s3

    app.dependency_overrides[obtener_s3] = lambda: FakeS3SinBorrado()
    _fallar_commit(sesion, monkeypatch)

    respuesta = _subir(api, _mecanico())

    assert respuesta.status_code == 503
    assert respuesta.json() == {"detail": MSG_GUARDADO}
    _sin_datos_internos(respuesta.text)


# --------------------------------------------------------------------------- #
# 2) Archivo ilegible                                                         #
# --------------------------------------------------------------------------- #

def test_archivo_ilegible_lanza_error_de_dominio_sin_subir(
    sesion: Session, s3: FakeS3
) -> None:
    with pytest.raises(ArchivoIlegibleError) as error:
        _recibir(sesion, s3, archivo=ArchivoQueFalla())

    assert str(error.value) == MSG_ILEGIBLE
    assert isinstance(error.value.__cause__, OSError)
    _sin_residuos(s3, sesion)


def test_archivo_cerrado_lanza_error_de_dominio_sin_subir(
    sesion: Session, s3: FakeS3
) -> None:
    archivo = io.BytesIO(JPEG_VALIDO)
    archivo.close()  # read() sobre un archivo cerrado lanza ValueError

    with pytest.raises(ArchivoIlegibleError):
        _recibir(sesion, s3, archivo=archivo)
    _sin_residuos(s3, sesion)


def test_archivo_ilegible_responde_400_por_la_api(
    api: TestClient, s3: FakeS3, sesion: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def calcular_que_falla(archivo, maximo=None):
        raise OSError("temporal ilegible")

    monkeypatch.setattr(
        "services.ms4_evidencias.services.evidencias.calcular_sha256_y_tamano",
        calcular_que_falla,
    )

    respuesta = _subir(api, _mecanico())

    assert respuesta.status_code == 400
    assert respuesta.json() == {"detail": MSG_ILEGIBLE}
    _sin_residuos(s3, sesion)


# --------------------------------------------------------------------------- #
# 3) Error no previsto → 500 genérico                                         #
# --------------------------------------------------------------------------- #

@pytest.fixture
def api_sin_excepciones(api: TestClient) -> TestClient:
    """Mismo cliente, pero devolviendo el 500 en vez de relanzar la excepción."""
    return TestClient(app, raise_server_exceptions=False)


def test_excepcion_inesperada_responde_500_generico(
    api_sin_excepciones: TestClient, s3: FakeS3, monkeypatch: pytest.MonkeyPatch
) -> None:
    def recibir_que_explota(*args, **kwargs):
        raise RuntimeError(f"detalle-secreto bucket={BUCKET} clave=ordenes/1/x.jpg")

    monkeypatch.setattr(router_evidencias, "recibir_evidencia", recibir_que_explota)

    respuesta = _subir(api_sin_excepciones, _mecanico())

    assert respuesta.status_code == 500
    assert respuesta.json() == {"detail": MENSAJE_ERROR_INTERNO}
    assert "detalle-secreto" not in respuesta.text
    _sin_datos_internos(respuesta.text)


def test_excepcion_inesperada_en_la_consulta_tambien_es_generica(
    api_sin_excepciones: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def listar_que_explota(*args, **kwargs):
        raise KeyError("columna-interna")

    monkeypatch.setattr(router_evidencias, "listar_por_orden", listar_que_explota)

    respuesta = api_sin_excepciones.get(
        "/evidencias",
        params={"orden_id": 1},
        headers={"Authorization": f"Bearer {_mecanico()}"},
    )

    assert respuesta.status_code == 500
    assert respuesta.json() == {"detail": MENSAJE_ERROR_INTERNO}
    assert "columna-interna" not in respuesta.text


# --------------------------------------------------------------------------- #
# 4) Lo que ya existía no cambia                                              #
# --------------------------------------------------------------------------- #

def test_las_http_exception_mantienen_su_respuesta(api: TestClient) -> None:
    respuesta = _subir(api, _token(9, NombreRol.CLIENTE))

    assert respuesta.status_code == 403
    assert respuesta.json() == {"detail": "No tienes permiso para realizar esta operación"}


def test_sin_la_parte_archivo_sigue_siendo_422_de_fastapi(api: TestClient) -> None:
    respuesta = api.post(
        "/evidencias",
        headers={"Authorization": f"Bearer {_mecanico()}"},
        data={"orden_id": "1", "contexto": "diagnostico"},
    )

    assert respuesta.status_code == 422
    assert isinstance(respuesta.json()["detail"], list)  # formato de FastAPI


def test_falla_del_almacenamiento_sigue_siendo_503_generico(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    from test_ms4_api_evidencias import FakeS3ConError
    from services.ms4_evidencias.dependencies import obtener_s3

    roto = FakeS3ConError()
    roto.fallar_subida = True
    app.dependency_overrides[obtener_s3] = lambda: roto

    respuesta = _subir(api, _mecanico())

    assert respuesta.status_code == 503
    assert respuesta.json() == {
        "detail": "El almacenamiento de evidencias no está disponible"
    }
    _sin_datos_internos(respuesta.text)
    assert _contar_filas(sesion) == 0
