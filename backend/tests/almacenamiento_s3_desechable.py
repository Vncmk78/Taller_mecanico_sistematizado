"""Almacenamiento S3 exclusivo y desechable para las pruebas reales de MS4.

Las pruebas contra MinIO real nunca usan el bucket configurado de MS4
(`MS4_S3_BUCKET`: `evidencias` del ambiente existente o `evidencias-pruebas`
de la demostración). Cada prueba crea sus propios buckets
`sgtm-prueba-<ejecución>-<n>`, que no existían antes, y al terminar elimina solo
esos buckets y su contenido. Así una operación que recorre un bucket entero
—como la conciliación de huérfanos— no puede alcanzar archivos ajenos.

Configuración explícita (no se toma nada de `MS4_S3_*`):

    MS4_TEST_S3_ENDPOINT            endpoint del MinIO de pruebas
    MS4_TEST_S3_ADMIN_ACCESS_KEY    credencial que puede crear y borrar buckets
    MS4_TEST_S3_ADMIN_SECRET_KEY
    MS4_TEST_S3_REGION              opcional (us-east-1)
    MS4_TEST_S3_MS4_ACCESS_KEY      opcional: usuario de mínimo privilegio de
    MS4_TEST_S3_MS4_SECRET_KEY      MS4, para comprobar que no alcanza estos buckets

`python scripts/ambiente_pruebas.py pruebas-ms4` las define con el MinIO del
ambiente `sgtm_pruebas`. Sin `MS4_TEST_S3_ENDPOINT` las pruebas reales se omiten
con ese motivo; si está definida y el MinIO no responde, fallan.
"""
from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from services.ms4_evidencias.config import Settings

PREFIJO_BUCKET = "sgtm-prueba-"
_NOMBRE_VALIDO = re.compile(r"^sgtm-prueba-[0-9a-f]{12}-\d{1,3}$")
MOTIVO_SIN_CONFIGURAR = (
    "Pruebas reales de MS4 sin almacenamiento exclusivo configurado: definir "
    "MS4_TEST_S3_ENDPOINT y credenciales de administración, o ejecutar "
    "`python scripts/ambiente_pruebas.py pruebas-ms4`"
)


class ErrorAislamiento(AssertionError):
    """Se intentó usar o limpiar un bucket que no es exclusivo de la ejecución."""


@dataclass(frozen=True)
class ConfigS3Prueba:
    endpoint: str
    access_key: str
    secret_key: str
    region: str
    usuario_ms4: tuple[str, str] | None

    def cliente(self, access_key: str | None = None, secret_key: str | None = None):
        return boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=access_key or self.access_key,
            aws_secret_access_key=secret_key or self.secret_key,
            region_name=self.region,
            use_ssl=self.endpoint.startswith("https://"),
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=5,
                read_timeout=30,
                retries={"max_attempts": 1},
            ),
        )

    def settings(self, bucket: str) -> Settings:
        """Settings de MS4 apuntando al bucket exclusivo (sin leer .env)."""

        return Settings(
            _env_file=None,
            S3_ENDPOINT=self.endpoint,
            S3_PUBLIC_ENDPOINT=None,
            S3_ACCESS_KEY=self.access_key,
            S3_SECRET_KEY=self.secret_key,
            S3_BUCKET=bucket,
            S3_REGION=self.region,
            S3_SECURE=self.endpoint.startswith("https://"),
        )


def config_desde_entorno(entorno: dict[str, str] | None = None) -> ConfigS3Prueba | None:
    entorno = os.environ if entorno is None else entorno
    endpoint = entorno.get("MS4_TEST_S3_ENDPOINT", "").strip()
    if not endpoint:
        return None
    access = entorno.get("MS4_TEST_S3_ADMIN_ACCESS_KEY", "")
    secret = entorno.get("MS4_TEST_S3_ADMIN_SECRET_KEY", "")
    if not access or not secret:
        raise ErrorAislamiento(
            "MS4_TEST_S3_ENDPOINT está definido sin MS4_TEST_S3_ADMIN_ACCESS_KEY/SECRET_KEY"
        )
    ms4 = (entorno.get("MS4_TEST_S3_MS4_ACCESS_KEY", ""), entorno.get("MS4_TEST_S3_MS4_SECRET_KEY", ""))
    return ConfigS3Prueba(
        endpoint=endpoint,
        access_key=access,
        secret_key=secret,
        region=entorno.get("MS4_TEST_S3_REGION") or "us-east-1",
        usuario_ms4=ms4 if all(ms4) else None,
    )


class AlmacenamientoDesechable:
    """Buckets creados por una ejecución; solo esos se pueden vaciar y borrar."""

    def __init__(self, cliente, ejecucion: str | None = None) -> None:
        self.cliente = cliente
        self.ejecucion = ejecucion or uuid.uuid4().hex[:12]
        self._creados: list[str] = []

    @property
    def creados(self) -> tuple[str, ...]:
        return tuple(self._creados)

    def crear_bucket(self) -> str:
        nombre = f"{PREFIJO_BUCKET}{self.ejecucion}-{len(self._creados) + 1}"
        if not _NOMBRE_VALIDO.match(nombre):
            raise ErrorAislamiento(f"Nombre de bucket de prueba inválido: {nombre}")
        if self._existe(nombre):
            raise ErrorAislamiento(f"El bucket {nombre} ya existía: no es exclusivo de esta ejecución")
        try:
            self.cliente.create_bucket(Bucket=nombre)
        except ClientError as exc:
            codigo = exc.response.get("Error", {}).get("Code")
            if codigo in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
                raise ErrorAislamiento(f"El bucket {nombre} ya existía") from exc
            raise
        self._creados.append(nombre)
        return nombre

    def es_propio(self, bucket: str) -> bool:
        return bucket in self._creados

    def limpiar(self) -> None:
        """Vacía y borra solo los buckets que creó esta instancia."""

        pendientes = list(reversed(self._creados))
        errores: list[str] = []
        for bucket in pendientes:
            try:
                self.eliminar_bucket(bucket)
            except Exception as exc:  # se informa al final, sin ocultarlo
                errores.append(f"{bucket}: {type(exc).__name__}")
        if errores:
            raise ErrorAislamiento("No se pudieron eliminar: " + ", ".join(errores))

    def eliminar_bucket(self, bucket: str) -> None:
        if not self.es_propio(bucket):
            raise ErrorAislamiento(f"{bucket} no fue creado por esta ejecución: no se toca")
        # Subidas multipart incompletas (también ocupan espacio y bloquean el borrado).
        for subida in self.cliente.list_multipart_uploads(Bucket=bucket).get("Uploads", []):
            self.cliente.abort_multipart_upload(
                Bucket=bucket, Key=subida["Key"], UploadId=subida["UploadId"]
            )
        paginador = self.cliente.get_paginator("list_objects_v2")
        for pagina in paginador.paginate(Bucket=bucket):
            for objeto in pagina.get("Contents", []):
                self.cliente.delete_object(Bucket=bucket, Key=objeto["Key"])
        self.cliente.delete_bucket(Bucket=bucket)
        self._creados.remove(bucket)

    def _existe(self, bucket: str) -> bool:
        try:
            self.cliente.head_bucket(Bucket=bucket)
        except ClientError as exc:
            codigo = str(exc.response.get("Error", {}).get("Code"))
            if codigo in {"404", "NoSuchBucket", "NotFound"}:
                return False
            raise
        return True
