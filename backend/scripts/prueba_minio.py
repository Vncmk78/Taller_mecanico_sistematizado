"""Prueba mínima de conexión de MS4 con MinIO (S3-compatible).

Ejecuta el flujo completo de guardado, consulta y recuperación de un archivo
usando el usuario de mínimo privilegio de MS4 (MS4_S3_ACCESS_KEY), sin crear
endpoints ni modelos. Marca cada paso con ✔/✘ y termina con exit 0 o 1.

Uso:
    python scripts/prueba_minio.py
    python scripts/prueba_minio.py --conservar   (no borra el objeto)
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import boto3
from botocore.config import Config

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.ms4_evidencias.config import Settings  # noqa: E402

TAMANO_PRUEBA = 256 * 1024


def crear_cliente(cfg: Settings):
    return boto3.client(
        "s3",
        endpoint_url=cfg.S3_ENDPOINT,
        aws_access_key_id=cfg.S3_ACCESS_KEY,
        aws_secret_access_key=cfg.S3_SECRET_KEY,
        region_name=cfg.S3_REGION,
        use_ssl=cfg.S3_SECURE,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=15,
            retries={"max_attempts": 1},
        ),
    )


def marcar_ok(texto: str) -> None:
    print(f"✔ {texto}")


def marcar_error(texto: str, exc: BaseException) -> None:
    print(f"✘ {texto}: {exc}")


def bytes_de_prueba() -> tuple[bytes, str]:
    datos = (bytes(range(256)) * (TAMANO_PRUEBA // 256))[:TAMANO_PRUEBA]
    return datos, hashlib.sha256(datos).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba mínima de MS4 con MinIO")
    parser.add_argument(
        "--conservar",
        action="store_true",
        help="no borra el objeto de prueba (para verlo en la consola)",
    )
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    cfg = Settings()
    cliente = crear_cliente(cfg)

    # Paso 1: las credenciales de MS4 funcionan (listar su propio bucket).
    try:
        cliente.list_objects_v2(Bucket=cfg.S3_BUCKET, MaxKeys=1)
    except Exception as exc:  # noqa: BLE001
        marcar_error(f"Conexión con usuario {cfg.S3_ACCESS_KEY}", exc)
        return 1
    marcar_ok(f"Conexión con usuario {cfg.S3_ACCESS_KEY}")

    # Paso 2: archivo de prueba (256 KB) y su SHA-256 como referencia.
    datos, checksum = bytes_de_prueba()

    # Paso 3: subida con clave de UUID (checklist 1.4 y 2.5).
    clave = f"pruebas/{uuid.uuid4().hex}.bin"
    try:
        cliente.put_object(
            Bucket=cfg.S3_BUCKET, Key=clave, Body=datos, ContentType="application/octet-stream"
        )
    except Exception as exc:  # noqa: BLE001
        marcar_error(f"Subida: {clave}", exc)
        return 1
    marcar_ok(f"Subida: {clave} ({len(datos)} bytes)")

    # Paso 4: metadatos del objeto guardado.
    try:
        meta = cliente.head_object(Bucket=cfg.S3_BUCKET, Key=clave)
    except Exception as exc:  # noqa: BLE001
        marcar_error("Metadatos", exc)
        return 1
    marcar_ok(
        f"Metadatos: {meta['ContentLength']} bytes, "
        f"{meta.get('ContentType', 'application/octet-stream')}"
    )

    # Paso 5: descarga con el usuario de MS4 y comparación SHA-256 (2.4).
    try:
        cuerpo = cliente.get_object(Bucket=cfg.S3_BUCKET, Key=clave)["Body"].read()
        coincide = hashlib.sha256(cuerpo).hexdigest() == checksum
    except Exception as exc:  # noqa: BLE001
        marcar_error("Descarga", exc)
        return 1
    if not coincide:
        marcar_error("Descarga", RuntimeError("el SHA-256 NO coincide"))
        return 1
    marcar_ok("Descarga: SHA-256 coincide")

    # Paso 6: URL prefirmada de 5 minutos y descarga con ella (3.3).
    try:
        url_firmada = cliente.generate_presigned_url(
            "get_object",
            Params={"Bucket": cfg.S3_BUCKET, "Key": clave},
            ExpiresIn=5 * 60,
        )
        with urllib.request.urlopen(url_firmada, timeout=30) as respuesta:
            cuerpo_firmado = respuesta.read()
        if hashlib.sha256(cuerpo_firmado).hexdigest() != checksum:
            raise RuntimeError("el SHA-256 vía URL prefirmada NO coincide")
    except Exception as exc:  # noqa: BLE001
        marcar_error("URL prefirmada (5 min)", exc)
        return 1
    marcar_ok("URL prefirmada (5 min): descarga OK")

    # Paso 7: GET anónimo al objeto debe responder 403, bucket privado (2.1).
    url_objeto = f"{cfg.S3_ENDPOINT.rstrip('/')}/{cfg.S3_BUCKET}/{clave}"
    try:
        urllib.request.urlopen(url_objeto, timeout=10)
        marcar_error("Acceso anónimo bloqueado", RuntimeError("respondió OK (bucket público?)"))
        return 1
    except urllib.error.HTTPError as exc:
        if exc.code != 403:
            marcar_error("Acceso anónimo bloqueado", RuntimeError(f"código {exc.code}"))
            return 1
    marcar_ok("Acceso anónimo bloqueado (403)")

    # Paso 8: limpieza (salvo con --conservar).
    if args.conservar:
        marcar_ok(f"Objeto conservado: {clave} (--conservar)")
    else:
        try:
            cliente.delete_object(Bucket=cfg.S3_BUCKET, Key=clave)
        except Exception as exc:  # noqa: BLE001
            marcar_error("Limpieza", exc)
            return 1
        marcar_ok("Limpieza: objeto eliminado")

    print("Prueba mínima OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())