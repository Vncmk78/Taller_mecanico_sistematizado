"""Aislamiento del almacenamiento S3 de las pruebas reales de MS4.

- Sin MinIO (siempre corren): la configuración de las pruebas nunca sale de
  `MS4_S3_*`; un bucket que ya existía se rechaza; la limpieza solo vacía y
  borra buckets creados por la misma ejecución.
- Con MinIO real (requiere `MS4_TEST_S3_*`): la limpieza de una ejecución deja
  intactos el bucket y los objetos de otra, y el servidor queda con los mismos
  buckets que antes.
"""
from __future__ import annotations

import uuid

import pytest
from botocore.exceptions import ClientError

from almacenamiento_s3_desechable import (
    PREFIJO_BUCKET,
    AlmacenamientoDesechable,
    ErrorAislamiento,
    config_desde_entorno,
)
from archivos_muestra import JPEG_VALIDO


class S3Falso:
    """S3 mínimo en memoria con las operaciones que usa la limpieza."""

    def __init__(self, buckets: dict[str, dict[str, bytes]] | None = None) -> None:
        self.buckets = buckets or {}
        self.multipart: dict[str, list[dict]] = {}
        self.llamadas: list[tuple[str, str]] = []

    def head_bucket(self, Bucket):
        if Bucket not in self.buckets:
            raise ClientError({"Error": {"Code": "404"}}, "HeadBucket")

    def create_bucket(self, Bucket):
        self.llamadas.append(("create_bucket", Bucket))
        if Bucket in self.buckets:
            raise ClientError({"Error": {"Code": "BucketAlreadyOwnedByYou"}}, "CreateBucket")
        self.buckets[Bucket] = {}

    def list_multipart_uploads(self, Bucket):
        return {"Uploads": self.multipart.get(Bucket, [])}

    def abort_multipart_upload(self, Bucket, Key, UploadId):
        self.llamadas.append(("abort_multipart_upload", Bucket))
        self.multipart[Bucket] = [u for u in self.multipart[Bucket] if u["UploadId"] != UploadId]

    def get_paginator(self, _nombre):
        falso = self

        class Paginador:
            def paginate(self, Bucket):
                yield {"Contents": [{"Key": k} for k in sorted(falso.buckets[Bucket])]}

        return Paginador()

    def delete_object(self, Bucket, Key):
        self.llamadas.append(("delete_object", Bucket))
        del self.buckets[Bucket][Key]

    def delete_bucket(self, Bucket):
        self.llamadas.append(("delete_bucket", Bucket))
        assert not self.buckets[Bucket]
        del self.buckets[Bucket]


# ── sin MinIO ──────────────────────────────────────────────────────────────


def test_la_configuracion_de_prueba_nunca_usa_la_de_ms4():
    entorno_de_ms4 = {
        "MS4_S3_ENDPOINT": "http://localhost:9000",
        "MS4_S3_ACCESS_KEY": "ms4-evidencias",
        "MS4_S3_SECRET_KEY": "x",
        "MS4_S3_BUCKET": "evidencias",
    }
    assert config_desde_entorno(entorno_de_ms4) is None


def test_endpoint_de_prueba_sin_credenciales_de_administracion_se_rechaza():
    with pytest.raises(ErrorAislamiento, match="ADMIN"):
        config_desde_entorno({"MS4_TEST_S3_ENDPOINT": "http://127.0.0.1:9010"})


def test_crea_buckets_nuevos_con_nombre_de_prueba():
    s3 = S3Falso({"evidencias": {"ordenes/1/a.jpg": b"real"}})
    propio = AlmacenamientoDesechable(s3)

    primero, segundo = propio.crear_bucket(), propio.crear_bucket()

    assert primero != segundo
    assert all(b.startswith(PREFIJO_BUCKET + propio.ejecucion) for b in (primero, segundo))
    assert "evidencias" not in propio.creados


def test_un_bucket_que_ya_existia_no_se_adopta():
    propio = AlmacenamientoDesechable(S3Falso(), ejecucion="0123456789ab")
    s3 = propio.cliente
    s3.buckets[f"{PREFIJO_BUCKET}0123456789ab-1"] = {"dato": b"previo"}

    with pytest.raises(ErrorAislamiento, match="ya existía"):
        propio.crear_bucket()

    assert propio.creados == ()
    assert s3.buckets[f"{PREFIJO_BUCKET}0123456789ab-1"] == {"dato": b"previo"}


@pytest.mark.parametrize("ajeno", ["evidencias", "evidencias-pruebas", f"{PREFIJO_BUCKET}ffffffffffff-1"])
def test_no_vacia_ni_borra_buckets_que_no_creo(ajeno: str):
    s3 = S3Falso({ajeno: {"ordenes/1/a.jpg": b"real"}})
    propio = AlmacenamientoDesechable(s3)

    with pytest.raises(ErrorAislamiento, match="no fue creado por esta ejecución"):
        propio.eliminar_bucket(ajeno)

    assert s3.buckets[ajeno] == {"ordenes/1/a.jpg": b"real"}
    assert s3.llamadas == []


def test_la_limpieza_borra_solo_lo_creado_incluidas_subidas_incompletas():
    s3 = S3Falso({"evidencias": {"ordenes/1/a.jpg": b"real"}})
    otra = AlmacenamientoDesechable(s3)
    ajeno = otra.crear_bucket()
    s3.buckets[ajeno]["ordenes/2/b.jpg"] = b"de otra ejecucion"
    propio = AlmacenamientoDesechable(s3)
    bucket = propio.crear_bucket()
    s3.buckets[bucket].update({"ordenes/9/c.jpg": b"1", "otra/d.bin": b"2"})
    s3.multipart[bucket] = [{"Key": "ordenes/9/grande.jpg", "UploadId": "u1"}]

    propio.limpiar()

    assert bucket not in s3.buckets
    assert s3.multipart[bucket] == []
    assert s3.buckets == {"evidencias": {"ordenes/1/a.jpg": b"real"},
                          ajeno: {"ordenes/2/b.jpg": b"de otra ejecucion"}}
    assert {b for _, b in s3.llamadas if _ != "create_bucket"} == {bucket}
    otra.limpiar()
    assert s3.buckets == {"evidencias": {"ordenes/1/a.jpg": b"real"}}


# ── con MinIO real ─────────────────────────────────────────────────────────


def test_minio_la_limpieza_de_una_ejecucion_no_toca_lo_ajeno(s3_prueba):
    administrador = s3_prueba.cliente()
    buckets_antes = {b["Name"] for b in administrador.list_buckets()["Buckets"]}

    otra = AlmacenamientoDesechable(s3_prueba.cliente())
    propio = AlmacenamientoDesechable(s3_prueba.cliente())
    try:
        ajeno = otra.crear_bucket()
        clave_ajena = f"ordenes/1/{uuid.uuid4().hex}.jpg"
        administrador.put_object(Bucket=ajeno, Key=clave_ajena, Body=JPEG_VALIDO)
        etag_ajeno = administrador.head_object(Bucket=ajeno, Key=clave_ajena)["ETag"]

        bucket = propio.crear_bucket()
        for n in range(3):
            administrador.put_object(Bucket=bucket, Key=f"ordenes/9/{n}.jpg", Body=JPEG_VALIDO)
        incompleta = administrador.create_multipart_upload(Bucket=bucket, Key="ordenes/9/grande.jpg")

        # Un bucket existente no puede vaciarse a través de esta ejecución.
        with pytest.raises(ErrorAislamiento):
            propio.eliminar_bucket(ajeno)

        propio.limpiar()

        actuales = {b["Name"] for b in administrador.list_buckets()["Buckets"]}
        assert bucket not in actuales
        assert actuales == buckets_antes | {ajeno}
        assert administrador.head_object(Bucket=ajeno, Key=clave_ajena)["ETag"] == etag_ajeno
        assert incompleta["UploadId"]
    finally:
        propio.limpiar()
        otra.limpiar()

    assert {b["Name"] for b in administrador.list_buckets()["Buckets"]} == buckets_antes
