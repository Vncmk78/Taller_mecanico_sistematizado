"""Cliente S3 y operaciones de almacenamiento para MS4.

El archivo de la evidencia vive en MinIO/S3; este módulo construye el cliente
con la configuración MS4_S3_* (settings) y provee las operaciones de subida,
cálculo de integridad y borrado. La firma es s3v4 y el direccionamiento es por
path (misma configuración que ya probó scripts/prueba_minio.py contra MinIO).
"""
from __future__ import annotations

import hashlib
import unicodedata
from urllib.parse import quote

import boto3
from botocore.config import Config
from boto3.s3.transfer import TransferConfig

from services.ms4_evidencias.config import Settings

# Lectura del archivo en bloques de 1 MiB para no cargarlo entero en memoria.
TAMANO_BLOQUE = 1024 * 1024

# Multipart desde 8 MiB (decisión 3 del estudio de almacenamiento).
UPLOAD_TRANSFER = TransferConfig(multipart_threshold=8 * 1024 * 1024)


def _config_boto() -> Config:
    """Configuración boto3 compartida (firma v4, path-style, timeouts cortos)."""
    return Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        connect_timeout=5,
        read_timeout=15,
        retries={"max_attempts": 1},
    )


def crear_cliente_s3(settings: Settings) -> object:
    """Cliente boto3 de S3 con el endpoint interno de MS4 (firma v4, path-style).

    Se usa para subir, borrar y verificar el bucket dentro de la red del
    servicio. Para firmar URLs de descarga, usar `crear_cliente_s3_publico`.
    """
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        use_ssl=settings.S3_SECURE,
        config=_config_boto(),
    )


def crear_cliente_s3_publico(settings: Settings) -> object:
    """Cliente boto3 que firma URLs con el endpoint que ve el cliente.

    La firma SigV4 incluye el Host (X-Amz-SignedHeaders): una URL generada con
    el endpoint interno (por ejemplo http://minio:9000) no sirve fuera de esa
    red. Si `S3_PUBLIC_ENDPOINT` está definido se usa ese; si no, se cae en
    `S3_ENDPOINT` (válido en desarrollo local, donde ambos hosts coinciden).
    """
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_PUBLIC_ENDPOINT or settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        use_ssl=settings.S3_SECURE,
        config=_config_boto(),
    )


def verificar_bucket(cliente: object, bucket: str) -> bool:
    """Devuelve True si el bucket existe y responde al usuario de MS4.

    Nunca expone detalles del error ni del bucket: el healthcheck responde 503
    con un mensaje genérico cuando esto devuelve False.
    """
    try:
        cliente.head_bucket(Bucket=bucket)
    except Exception:  # noqa: BLE001  (cualquier fallo = almacenamiento caído)
        return False
    return True


def calcular_sha256_y_tamano(archivo) -> tuple[str, int]:
    """SHA-256 y tamaño del archivo leyéndolo en bloques de 1 MiB.

    Al terminar deja el archivo al inicio (`seek(0)`) para que la subida
    posterior lea el contenido completo.
    """
    digest = hashlib.sha256()
    tamano = 0
    while True:
        bloque = archivo.read(TAMANO_BLOQUE)
        if not bloque:
            break
        digest.update(bloque)
        tamano += len(bloque)
    archivo.seek(0)
    return digest.hexdigest(), tamano


def subir_objeto(cliente: object, bucket: str, clave: str, archivo, content_type: str) -> None:
    """Sube el archivo a MinIO/S3 con multipart desde 8 MiB (decisión 3)."""
    cliente.upload_fileobj(
        archivo,
        bucket,
        clave,
        ExtraArgs={"ContentType": content_type},
        Config=UPLOAD_TRANSFER,
    )


def eliminar_objeto(cliente: object, bucket: str, clave: str) -> None:
    """Borra el objeto; se usa para deshacer la subida si la base falla."""
    cliente.delete_object(Bucket=bucket, Key=clave)


def content_disposition_attachment(nombre: str) -> str:
    """Valor seguro de ``Content-Disposition`` para forzar la descarga.

    Devuelve las dos formas del RFC 6266/5987: ``filename=`` solo con ASCII
    (compatibilidad) y ``filename*=UTF-8''...`` percent-encoded (conserva
    tildes y ñ). Se neutralizan comillas, punto y coma y saltos de línea para
    no romper la cabecera, y solo se deja el nombre de archivo (sin rutas).
    Antes de quedarse solo con ASCII, se aplica ``NFKD`` para que tildes y
    eñes pasen a su forma descompuesta y la forma ``filename=`` quede como
    ``Fotografia_dano.jpg``; el ``filename*`` usa el nombre original.
    """
    base = (nombre or "").replace("\\", "/").split("/")[-1]
    base = "".join(caracter for caracter in base if caracter not in '\r\n";').strip()
    if base in ("", ".", ".."):
        base = "archivo"

    ascii_nombre = (
        unicodedata.normalize("NFKD", base)
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip(" .")
    )
    if not ascii_nombre:
        ascii_nombre = "archivo"
    nombre_codificado = quote(base, safe="")
    return (
        f'attachment; filename="{ascii_nombre}"; '
        f"filename*=UTF-8''{nombre_codificado}"
    )


def generar_url_descarga(
    cliente: object,
    bucket: str,
    clave: str,
    *,
    content_type: str,
    nombre_descarga: str,
    expira_en: int,
) -> str:
    """URL GET prefirmada que fuerza el tipo validado y la descarga (3.3 y 3.4).

    ``ResponseContentType`` y ``ResponseContentDisposition`` viajan dentro de la
    firma: MinIO/S3 los aplica al servir el objeto, así el navegador no adivina
    el tipo ni renderiza el archivo. ``expira_en`` son segundos.
    """
    return cliente.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": clave,
            "ResponseContentType": content_type,
            "ResponseContentDisposition": content_disposition_attachment(nombre_descarga),
        },
        ExpiresIn=expira_en,
    )
