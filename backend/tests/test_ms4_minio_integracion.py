"""Integración mínima MS4 ↔ MinIO (S3) como test de pytest.

Mismo flujo que ``scripts/prueba_minio.py``, pero sobre un bucket exclusivo y
desechable de cada prueba (``tests/almacenamiento_s3_desechable.py``), nunca el
bucket configurado de MS4: sube un archivo de 256 KB, consulta metadatos, lo
descarga (por S3 y por URL prefirmada) y compara el SHA-256, y verifica que el
acceso anónimo responde 403. Con el usuario de mínimo privilegio de MS4
configurado, comprueba además que ese usuario no alcanza los buckets de prueba.

Sin ``MS4_TEST_S3_ENDPOINT`` se omite indicando cómo configurarlo; si está
definido y MinIO no responde, falla.
"""
from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
import uuid

import pytest
from botocore.exceptions import ClientError

from services.ms4_evidencias.services.almacenamiento import generar_url_descarga

from archivos_muestra import jpeg_con

TAMANO_PRUEBA = 256 * 1024


@pytest.fixture
def cliente_minio(s3_prueba, almacenamiento):
    """(settings, cliente) sobre un bucket exclusivo; se elimina al terminar."""

    bucket = almacenamiento.crear_bucket()
    return s3_prueba.settings(bucket), s3_prueba.cliente()


def test_guardado_y_recuperacion_en_bucket_exclusivo(cliente_minio):
    cfg, cliente = cliente_minio
    datos = (bytes(range(256)) * (TAMANO_PRUEBA // 256))[:TAMANO_PRUEBA]
    checksum = hashlib.sha256(datos).hexdigest()
    clave = f"pruebas/{uuid.uuid4().hex}.bin"

    # 3. Subida con clave UUID (checklist 1.4 y 2.5).
    cliente.put_object(
        Bucket=cfg.S3_BUCKET, Key=clave, Body=datos, ContentType="application/octet-stream"
    )

    # 4. Metadatos: tamaño y tipo del objeto guardado.
    meta = cliente.head_object(Bucket=cfg.S3_BUCKET, Key=clave)
    assert meta["ContentLength"] == len(datos)
    assert meta.get("ContentType", "application/octet-stream") == "application/octet-stream"

    # 5. Descarga e integridad SHA-256 (2.4).
    cuerpo = cliente.get_object(Bucket=cfg.S3_BUCKET, Key=clave)["Body"].read()
    assert hashlib.sha256(cuerpo).hexdigest() == checksum, "El archivo descargado no es idéntico"

    # 6. URL prefirmada de 5 minutos descarga el mismo contenido (3.3).
    url_firmada = cliente.generate_presigned_url(
        "get_object",
        Params={"Bucket": cfg.S3_BUCKET, "Key": clave},
        ExpiresIn=5 * 60,
    )
    with urllib.request.urlopen(url_firmada, timeout=30) as respuesta:
        cuerpo_firmado = respuesta.read()
    assert hashlib.sha256(cuerpo_firmado).hexdigest() == checksum

    # 7. GET anónimo al objeto responde 403: bucket privado (2.1).
    url_objeto = f"{cfg.S3_ENDPOINT.rstrip('/')}/{cfg.S3_BUCKET}/{clave}"
    with pytest.raises(urllib.error.HTTPError) as capturado:
        urllib.request.urlopen(url_objeto, timeout=10)
    assert capturado.value.code == 403


def test_descarga_prefirmada_fuerza_tipo_y_disposicion(cliente_minio):
    cfg, cliente = cliente_minio
    datos = jpeg_con(b"evidencia-de-prueba-jpeg")
    clave = f"pruebas/{uuid.uuid4().hex}.jpg"
    checksum = hashlib.sha256(datos).hexdigest()

    cliente.put_object(
        Bucket=cfg.S3_BUCKET, Key=clave, Body=datos, ContentType="image/jpeg"
    )

    # 3.4: ResponseContentType y ResponseContentDisposition firmados (3.3).
    url = generar_url_descarga(
        cliente,
        cfg.S3_BUCKET,
        clave,
        content_type="image/jpeg",
        nombre_descarga="foto del taller.jpg",
        expira_en=300,
    )
    with urllib.request.urlopen(url, timeout=30) as respuesta:
        assert respuesta.headers.get("Content-Type") == "image/jpeg"
        disposicion = respuesta.headers.get("Content-Disposition") or ""
        assert "attachment" in disposicion
        assert "foto del taller.jpg" in disposicion
        assert hashlib.sha256(respuesta.read()).hexdigest() == checksum


def test_el_usuario_de_ms4_no_alcanza_los_buckets_de_prueba(s3_prueba, almacenamiento):
    """El usuario de mínimo privilegio de MS4 no puede leer ni escribir fuera de su bucket."""

    if s3_prueba.usuario_ms4 is None:
        pytest.skip("Definir MS4_TEST_S3_MS4_ACCESS_KEY/SECRET_KEY para comprobar el mínimo privilegio")
    bucket = almacenamiento.crear_bucket()
    usuario = s3_prueba.cliente(*s3_prueba.usuario_ms4)
    with pytest.raises(ClientError) as listado:
        usuario.list_objects_v2(Bucket=bucket, MaxKeys=1)
    assert listado.value.response["Error"]["Code"] == "AccessDenied"
    with pytest.raises(ClientError) as escritura:
        usuario.put_object(Bucket=bucket, Key="ordenes/1/intento.jpg", Body=b"x")
    assert escritura.value.response["Error"]["Code"] == "AccessDenied"
