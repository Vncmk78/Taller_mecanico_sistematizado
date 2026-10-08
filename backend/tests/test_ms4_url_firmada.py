"""Pruebas de URLs firmadas de descarga de MS4 (controles 3.3 y 3.4).

La firma SigV4 se calcula localmente por boto3 **sin tocar la red**, así que
estos tests no necesitan MinIO. Se verifica: el endpoint público con el que se
firma, la vigencia (X-Amz-Expires), los parámetros de respuesta que viajan
dentro de la firma y el saneo del Content-Disposition.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import ValidationError

from services.ms4_evidencias.config import Settings
from services.ms4_evidencias.services.almacenamiento import (
    content_disposition_attachment,
    crear_cliente_s3_publico,
    generar_url_descarga,
)

BUCKET = "evidencias"
CLAVE = "ordenes/42/9f2c1d7a4b6e4a1c8f3d0b5e6a7c9d2e.jpg"


def _crear_settings(**campos) -> Settings:
    base = {
        "S3_ENDPOINT": "http://localhost:9000",
        "S3_ACCESS_KEY": "ms4-evidencias",
        "S3_SECRET_KEY": "clave-de-prueba",
        "S3_BUCKET": "evidencias",
        "S3_REGION": "us-east-1",
        "S3_SECURE": False,
    }
    base.update(campos)
    return Settings(_env_file=None, **base)


def _descargar(cfg: Settings, **params) -> str:
    params.setdefault("expira_en", cfg.URL_DESCARGA_TTL_SECONDS)
    return generar_url_descarga(
        crear_cliente_s3_publico(cfg),
        BUCKET,
        CLAVE,
        content_type="image/jpeg",
        nombre_descarga="foto.jpg",
        **params,
    )


def test_cliente_publico_sin_endpoint_definido_usa_el_interno() -> None:
    cfg = _crear_settings(S3_PUBLIC_ENDPOINT=None)
    url = _descargar(cfg)
    assert urlsplit(url).netloc == "localhost:9000"


def test_cliente_publico_con_endpoint_definido_lo_usa() -> None:
    cfg = _crear_settings(S3_PUBLIC_ENDPOINT="https://almacenamiento.ejemplo.cl")
    url = _descargar(cfg)
    assert urlsplit(url).scheme == "https"
    assert urlsplit(url).netloc == "almacenamiento.ejemplo.cl"


def test_cliente_publico_con_endpoint_vacio_cae_al_interno() -> None:
    cfg = _crear_settings(S3_PUBLIC_ENDPOINT="")
    url = _descargar(cfg)
    assert urlsplit(url).netloc == "localhost:9000"


def test_url_lleva_firma_sigv4_y_expira_en_300_segundos() -> None:
    cfg = _crear_settings(URL_DESCARGA_TTL_SECONDS=300)
    url = _descargar(cfg)
    parametros = parse_qs(urlsplit(url).query)
    assert parametros["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
    assert parametros["X-Amz-Expires"] == ["300"]
    assert parametros["X-Amz-Signature"][0]
    assert parametros["X-Amz-SignedHeaders"] == ["host"]
    assert "X-Amz-Credential" in parametros


def test_url_usa_el_ttl_indicado() -> None:
    cfg = _crear_settings(URL_DESCARGA_TTL_SECONDS=60)
    url = _descargar(cfg)
    parametros = parse_qs(urlsplit(url).query)
    assert parametros["X-Amz-Expires"] == ["60"]


def test_url_firma_content_type_y_disposicion_de_descarga() -> None:
    cfg = _crear_settings()
    url = generar_url_descarga(
        crear_cliente_s3_publico(cfg),
        BUCKET,
        CLAVE,
        content_type="image/webp",
        nombre_descarga="foto del taller.jpg",
        expira_en=300,
    )
    parametros = parse_qs(urlsplit(url).query)
    assert parametros["response-content-type"] == ["image/webp"]
    esperado = content_disposition_attachment("foto del taller.jpg")
    assert parametros["response-content-disposition"] == [esperado]


def test_disposition_archivo_plano() -> None:
    assert content_disposition_attachment("foto.jpg") == (
        'attachment; filename="foto.jpg"; ' "filename*=UTF-8''foto.jpg"
    )


def test_disposition_con_tildes_ascii_limpio_y_utf8_codificado() -> None:
    assert content_disposition_attachment("foto ñ.jpg") == (
        'attachment; filename="foto n.jpg"; '
        "filename*=UTF-8''foto%20%C3%B1.jpg"
    )


def test_disposition_normaliza_ticks_y_enies_con_nfkd() -> None:
    assert content_disposition_attachment("Fotografía_daño.jpg") == (
        'attachment; filename="Fotografia_dano.jpg"; '
        "filename*=UTF-8''Fotograf%C3%ADa_da%C3%B1o.jpg"
    )


def test_disposition_neutraliza_comillas_punto_y_coma_y_controles() -> None:
    assert content_disposition_attachment('a"b;c\r\nd.jpg') == (
        'attachment; filename="abcd.jpg"; ' "filename*=UTF-8''abcd.jpg"
    )


def test_disposition_quita_rutas() -> None:
    assert content_disposition_attachment("../../etc/passwd.jpg") == (
        'attachment; filename="passwd.jpg"; '
        "filename*=UTF-8''passwd.jpg"
    )


def test_disposition_solo_no_ascii_cae_a_archivo() -> None:
    assert content_disposition_attachment("ñandú.jpg") == (
        'attachment; filename="nandu.jpg"; '
        "filename*=UTF-8''%C3%B1and%C3%BA.jpg"
    )


def test_disposition_vacio_o_puntos_devuelve_archivo() -> None:
    assert 'filename="archivo"' in content_disposition_attachment("   ")
    assert 'filename="archivo"' in content_disposition_attachment("..")
    assert 'filename="archivo"' in content_disposition_attachment("")


def test_config_endpoint_publico_por_defecto_es_none() -> None:
    assert _crear_settings().S3_PUBLIC_ENDPOINT is None


def test_config_ttl_por_defecto_es_300() -> None:
    assert _crear_settings().URL_DESCARGA_TTL_SECONDS == 300


def test_config_ttl_extremos_validos() -> None:
    assert _crear_settings(URL_DESCARGA_TTL_SECONDS=30).URL_DESCARGA_TTL_SECONDS == 30
    assert (
        _crear_settings(URL_DESCARGA_TTL_SECONDS=3600).URL_DESCARGA_TTL_SECONDS
        == 3600
    )


def test_config_ttl_fuera_de_rango_falla() -> None:
    with pytest.raises(ValidationError):
        _crear_settings(URL_DESCARGA_TTL_SECONDS=10)
    with pytest.raises(ValidationError):
        _crear_settings(URL_DESCARGA_TTL_SECONDS=99999)