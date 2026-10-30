"""Lista blanca de formatos y tamaño máximo por tipo (MS4, Semana 6).

Controles del checklist de seguridad de evidencias:

- 1.1 Solo se aceptan `image/jpeg`, `image/png`, `image/webp`, `video/mp4` y
  `video/quicktime`; SVG, HTML, ejecutables, PDF, ZIP, GIF o HEIC → 415.
- 1.3 Fotos hasta `MS4_MAX_BYTES_FOTO` (10 MiB) y videos hasta
  `MS4_MAX_BYTES_VIDEO` (100 MiB); al superarlo la lectura se corta y se
  responde 413.

En todos los rechazos se comprueba que no queda ningún objeto en el
almacenamiento ni filas en la base (el archivo se valida ANTES de subirlo).
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from services.ms4_evidencias.config import MIB, Settings
from services.ms4_evidencias.main import app
from services.ms4_evidencias.models.evidencia import TipoArchivo
from services.ms4_evidencias.routers.evidencias import obtener_politica_archivos
from services.ms4_evidencias.services.almacenamiento import (
    TamanoMaximoExcedido,
    calcular_sha256_y_tamano,
)
from services.ms4_evidencias.services.validacion_archivos import (
    ArchivoDemasiadoGrandeError,
    EvidenciaInvalidaError,
    PoliticaArchivos,
    TipoArchivoNoPermitidoError,
)
from shared.auth import NombreRol

import archivos_muestra
from test_ms4_api_evidencias import (  # noqa: F401  (fixtures reutilizados)
    SECRETO,
    _contar_filas,
    _subir,
    _token,
    api,
    s3,
    s3_publico,
    sesion,
)
from test_ms4_recepcion import FakeS3

PERMITIDOS = sorted(archivos_muestra.POR_CONTENT_TYPE)


def _politica(**cambios) -> PoliticaArchivos:
    datos = {
        "tipos_permitidos": frozenset(PERMITIDOS),
        "max_bytes_foto": 10 * MIB,
        "max_bytes_video": 100 * MIB,
    }
    datos.update(cambios)
    return PoliticaArchivos(**datos)


def _usar_politica(politica: PoliticaArchivos) -> None:
    app.dependency_overrides[obtener_politica_archivos] = lambda: politica


def _mecanico() -> str:
    return _token(7, NombreRol.MECANICO)


# --------------------------------------------------------------------------- #
# 1) Configuración                                                            #
# --------------------------------------------------------------------------- #

def test_configuracion_por_defecto_cumple_el_checklist() -> None:
    config = Settings(_env_file=None, JWT_SECRET_KEY=SECRETO)

    assert sorted(config.TIPOS_PERMITIDOS) == PERMITIDOS
    assert config.MAX_BYTES_FOTO == 10 * MIB
    assert config.MAX_BYTES_VIDEO == 100 * MIB


def test_la_lista_blanca_se_puede_restringir_por_entorno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MS4_TIPOS_PERMITIDOS", '["image/jpeg", "IMAGE/PNG"]')
    monkeypatch.setenv("MS4_MAX_BYTES_FOTO", str(5 * MIB))

    config = Settings(_env_file=None, JWT_SECRET_KEY=SECRETO)

    assert config.TIPOS_PERMITIDOS == ["image/jpeg", "image/png"]
    assert config.MAX_BYTES_FOTO == 5 * MIB


@pytest.mark.parametrize("tipo", ["image/svg+xml", "text/html", "image/gif"])
def test_la_lista_blanca_no_admite_formatos_que_ms4_no_sabe_verificar(
    tipo: str,
) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, JWT_SECRET_KEY=SECRETO, TIPOS_PERMITIDOS=[tipo])


@pytest.mark.parametrize("campo", ["MAX_BYTES_FOTO", "MAX_BYTES_VIDEO"])
def test_los_limites_deben_ser_positivos(campo: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, JWT_SECRET_KEY=SECRETO, **{campo: 0})


# --------------------------------------------------------------------------- #
# 2) Política (unidad)                                                        #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("content_type", "tipo"),
    [
        ("image/jpeg", TipoArchivo.FOTO),
        ("image/png", TipoArchivo.FOTO),
        ("image/webp", TipoArchivo.FOTO),
        ("video/mp4", TipoArchivo.VIDEO),
        ("video/quicktime", TipoArchivo.VIDEO),
        ("IMAGE/JPEG; charset=binary", TipoArchivo.FOTO),
    ],
)
def test_formatos_de_la_lista_blanca_se_aceptan(
    content_type: str, tipo: TipoArchivo
) -> None:
    normalizado, clasificado = _politica().validar_tipo(content_type)

    assert normalizado == content_type.split(";")[0].strip().lower()
    assert clasificado is tipo


@pytest.mark.parametrize(
    "content_type",
    [
        "image/svg+xml",
        "text/html",
        "application/x-msdownload",
        "application/octet-stream",
        "application/pdf",
        "application/zip",
        "image/gif",
        "image/heic",
        "video/x-msvideo",
        "text/plain",
        "",
        "imagen",
    ],
)
def test_formatos_fuera_de_la_lista_blanca_se_rechazan(content_type: str) -> None:
    with pytest.raises(TipoArchivoNoPermitidoError):
        _politica().validar_tipo(content_type)


def test_un_tipo_no_permitido_sigue_siendo_una_evidencia_invalida() -> None:
    # Compatibilidad: quien capturaba EvidenciaInvalidaError lo sigue haciendo.
    assert issubclass(TipoArchivoNoPermitidoError, EvidenciaInvalidaError)
    assert issubclass(ArchivoDemasiadoGrandeError, EvidenciaInvalidaError)


def test_la_politica_restringida_rechaza_lo_que_no_esta_en_su_lista() -> None:
    politica = _politica(tipos_permitidos=frozenset({"image/jpeg"}))

    politica.validar_tipo("image/jpeg")
    with pytest.raises(TipoArchivoNoPermitidoError):
        politica.validar_tipo("image/png")


def test_cada_tipo_usa_su_propio_limite() -> None:
    politica = _politica(max_bytes_foto=10, max_bytes_video=20)

    assert politica.limite_para(TipoArchivo.FOTO) == 10
    assert politica.limite_para(TipoArchivo.VIDEO) == 20


def test_el_mensaje_413_indica_el_limite_del_tipo() -> None:
    error = _politica().error_tamano(TipoArchivo.FOTO)

    assert "10 MB" in str(error)
    assert error.limite_bytes == 10 * MIB
    assert "100 MB" in str(_politica().error_tamano(TipoArchivo.VIDEO))


# --------------------------------------------------------------------------- #
# 3) Lectura con tope (corta apenas se supera el límite)                      #
# --------------------------------------------------------------------------- #

class _ArchivoContado(io.BytesIO):
    def __init__(self, contenido: bytes) -> None:
        super().__init__(contenido)
        self.bytes_leidos = 0

    def read(self, n: int = -1) -> bytes:
        bloque = super().read(n)
        self.bytes_leidos += len(bloque)
        return bloque


def test_un_archivo_exacto_al_limite_se_acepta() -> None:
    archivo = io.BytesIO(b"x" * 100)

    _, tamano = calcular_sha256_y_tamano(archivo, maximo=100)

    assert tamano == 100
    assert archivo.tell() == 0


def test_la_lectura_se_corta_al_superar_el_limite_y_vuelve_al_inicio() -> None:
    archivo = _ArchivoContado(b"x" * (5 * MIB))

    with pytest.raises(TamanoMaximoExcedido):
        calcular_sha256_y_tamano(archivo, maximo=MIB)

    # Lee a lo sumo un bloque de 1 MiB más allá del límite, no los 5 MiB.
    assert archivo.bytes_leidos <= 2 * MIB
    assert archivo.tell() == 0


def test_sin_maximo_se_lee_el_archivo_completo() -> None:
    _, tamano = calcular_sha256_y_tamano(io.BytesIO(b"x" * (3 * MIB)))

    assert tamano == 3 * MIB


# --------------------------------------------------------------------------- #
# 4) API: 415 lista blanca                                                    #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("nombre", "contenido", "content_type"),
    [
        ("dibujo.svg", b"<svg onload='alert(1)'></svg>", "image/svg+xml"),
        ("pagina.html", b"<html><script>alert(1)</script></html>", "text/html"),
        ("programa.exe", b"MZ\x90\x00" + b"\x00" * 60, "application/x-msdownload"),
        ("documento.pdf", b"%PDF-1.7\n", "application/pdf"),
        ("comprimido.zip", b"PK\x03\x04", "application/zip"),
        ("animada.gif", b"GIF89a" + b"\x00" * 10, "image/gif"),
    ],
)
def test_formatos_no_permitidos_responden_415_sin_dejar_residuos(
    api: TestClient,
    s3: FakeS3,
    sesion: Session,
    nombre: str,
    contenido: bytes,
    content_type: str,
) -> None:
    respuesta = _subir(
        api, _mecanico(), archivo=contenido, nombre=nombre, content_type=content_type
    )

    assert respuesta.status_code == 415
    assert "no permitido" in respuesta.json()["detail"]
    assert not s3.objetos
    assert _contar_filas(sesion) == 0


@pytest.mark.parametrize("content_type", PERMITIDOS)
def test_cada_formato_de_la_lista_blanca_se_sube(
    api: TestClient, s3: FakeS3, content_type: str
) -> None:
    contenido = archivos_muestra.POR_CONTENT_TYPE[content_type]()

    respuesta = _subir(api, _mecanico(), archivo=contenido, content_type=content_type)

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["content_type"] == content_type
    assert len(s3.objetos) == 1


def test_la_lista_blanca_configurada_se_aplica_en_la_api(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    _usar_politica(_politica(tipos_permitidos=frozenset({"image/jpeg"})))

    respuesta = _subir(
        api, _mecanico(), archivo=archivos_muestra.png(), content_type="image/png"
    )

    assert respuesta.status_code == 415
    assert not s3.objetos
    assert _contar_filas(sesion) == 0


# --------------------------------------------------------------------------- #
# 5) API: 413 tamaño máximo                                                   #
# --------------------------------------------------------------------------- #

def test_foto_de_10_mib_mas_un_byte_responde_413(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    respuesta = _subir(
        api, _mecanico(), archivo=archivos_muestra.jpeg(10 * MIB + 1)
    )

    assert respuesta.status_code == 413
    assert "10 MB" in respuesta.json()["detail"]
    assert not s3.objetos
    assert _contar_filas(sesion) == 0


def test_foto_exacta_de_10_mib_se_acepta(api: TestClient, s3: FakeS3) -> None:
    respuesta = _subir(api, _mecanico(), archivo=archivos_muestra.jpeg(10 * MIB))

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["tamano_bytes"] == 10 * MIB


def test_video_que_supera_su_limite_responde_413(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    _usar_politica(_politica(max_bytes_foto=1024, max_bytes_video=8 * 1024))

    respuesta = _subir(
        api,
        _mecanico(),
        archivo=archivos_muestra.mp4(8 * 1024 + 1),
        nombre="video.mp4",
        content_type="video/mp4",
    )

    assert respuesta.status_code == 413
    assert respuesta.json()["detail"].startswith("El video")
    assert not s3.objetos
    assert _contar_filas(sesion) == 0


def test_el_limite_de_foto_no_aplica_a_los_videos(
    api: TestClient, s3: FakeS3
) -> None:
    _usar_politica(_politica(max_bytes_foto=1024, max_bytes_video=8 * 1024))

    respuesta = _subir(
        api,
        _mecanico(),
        archivo=archivos_muestra.mov(4 * 1024),
        nombre="video.mov",
        content_type="video/quicktime",
    )

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["tipo_archivo"] == TipoArchivo.VIDEO.value


def test_el_limite_de_foto_configurado_se_aplica_en_la_api(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    _usar_politica(_politica(max_bytes_foto=1024))

    respuesta = _subir(
        api, _mecanico(), archivo=archivos_muestra.png(2048), content_type="image/png"
    )

    assert respuesta.status_code == 413
    assert not s3.objetos
    assert _contar_filas(sesion) == 0
