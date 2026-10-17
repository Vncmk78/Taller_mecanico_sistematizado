"""Pruebas del ciclo completo de archivos en MS4: subida → consulta → recuperación.

Cada prueba recorre la API HTTP real de MS4 (`main.app` con TestClient), no
las funciones internas, y comprueba que lo que se recupera es exactamente lo
que se subió:

- **Sin MinIO** (siempre corren): almacenamiento en memoria que guarda los
  bytes. Se sube por `POST /evidencias`, se consulta por listado y detalle, y
  se comprueba que la URL de `/descarga` apunta al objeto de ESA evidencia y
  que los bytes guardados tienen el SHA-256 registrado en la base.
- **Con MinIO real** (se omiten si MinIO no está levantado): la subida va al
  bucket privado con el usuario de mínimo privilegio de MS4 y la recuperación
  se hace siguiendo la URL prefirmada como lo haría el navegador. Se prueban
  integridad (SHA-256), cabeceras forzadas, metadatos del objeto, subida
  multipart (> 8 MiB), expiración y firma alterada (403), acceso anónimo
  (403) y que una falla de la base no deja archivos huérfanos en el bucket.

Las órdenes de las pruebas con MinIO usan un número aleatorio alto y al final
se borra su prefijo `ordenes/{orden_id}/`, así no se mezclan con datos reales.
"""
from __future__ import annotations

import hashlib
import io
import random
import time
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlsplit

import httpx
import pytest
from botocore.exceptions import (
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from services.ms4_evidencias.config import Settings
from services.ms4_evidencias.db import get_db
from services.ms4_evidencias.dependencies import obtener_s3, obtener_s3_publico
from services.ms4_evidencias.integracion_ms2 import obtener_verificador_ordenes
from services.ms4_evidencias.main import app
from services.ms4_evidencias.models import Base
from services.ms4_evidencias.models.evidencia import Evidencia
from services.ms4_evidencias.services.almacenamiento import (
    crear_cliente_s3,
    crear_cliente_s3_publico,
    generar_url_descarga,
)
from services.ms4_evidencias.services.evidencias import es_clave_valida
from shared.auth import NombreRol, crear_token_acceso

SECRETO = "clave-secreta-exclusiva-para-pruebas-de-ms4-123456"
MECANICO = 21
ADMIN = 1
CLIENTE = 40

_ERRORES_MINIO_APAGADO = (
    EndpointConnectionError,
    ConnectTimeoutError,
    ReadTimeoutError,
    ConnectionClosedError,
    ConnectionRefusedError,
    TimeoutError,
)


# ---------------------------------------------------------------------------
# Utilidades comunes
# ---------------------------------------------------------------------------


class AlmacenamientoEnMemoria:
    """Cliente S3 mínimo que guarda los bytes para poder recuperarlos."""

    def __init__(self) -> None:
        self.objetos: dict[str, dict] = {}

    def upload_fileobj(self, fileobj, bucket, clave, ExtraArgs=None, Config=None):
        self.objetos[clave] = {
            "bucket": bucket,
            "data": fileobj.read(),
            "content_type": (ExtraArgs or {}).get("ContentType"),
            "metadata": (ExtraArgs or {}).get("Metadata") or {},
        }

    def delete_object(self, Bucket, Key):
        self.objetos.pop(Key, None)


class PermiteTodo:
    """MS2 falso que acepta cualquier orden (la autorización se prueba aparte)."""

    def verificar_acceso(self, orden_id: int, token: str) -> None:
        return None


def _token(usuario_id: int, *roles: NombreRol) -> str:
    return crear_token_acceso(usuario_id, frozenset(roles), clave_secreta=SECRETO)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _subir(
    cliente: TestClient,
    token: str,
    orden_id: int,
    datos: bytes,
    *,
    nombre: str = "foto.jpg",
    content_type: str = "image/jpeg",
    contexto: str = "resultado_final",
    request_id: str | None = None,
):
    cabeceras = _auth(token)
    if request_id:
        cabeceras["X-Request-ID"] = request_id
    return cliente.post(
        "/evidencias",
        headers=cabeceras,
        data={"orden_id": str(orden_id), "contexto": contexto},
        files={"archivo": (nombre, datos, content_type)},
    )


def _clave_desde_url(url: str, bucket: str) -> str:
    """`ordenes/...` a partir de una URL prefirmada path-style."""
    camino = unquote(urlsplit(url).path)
    prefijo = f"/{bucket}/"
    assert camino.startswith(prefijo), camino
    return camino[len(prefijo):]


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


def _montar_api(sesion: Session, s3, s3_publico) -> TestClient:
    def reemplazar_db():
        yield sesion

    app.dependency_overrides[get_db] = reemplazar_db
    app.dependency_overrides[obtener_s3] = lambda: s3
    app.dependency_overrides[obtener_s3_publico] = lambda: s3_publico
    app.dependency_overrides[obtener_verificador_ordenes] = lambda: PermiteTodo()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Ciclo sin MinIO (almacenamiento en memoria)
# ---------------------------------------------------------------------------

BUCKET_MEMORIA = "evidencias"


@pytest.fixture
def memoria() -> AlmacenamientoEnMemoria:
    return AlmacenamientoEnMemoria()


@pytest.fixture
def api_memoria(
    sesion: Session, memoria: AlmacenamientoEnMemoria
) -> Generator[TestClient, None, None]:
    # Cliente S3 real que solo FIRMA (offline): la URL queda con el host público.
    firmante = crear_cliente_s3_publico(
        Settings(
            _env_file=None,
            S3_ENDPOINT="http://minio:9000",
            S3_PUBLIC_ENDPOINT="http://archivos.taller.test",
            S3_BUCKET=BUCKET_MEMORIA,
        )
    )
    with _montar_api(sesion, memoria, firmante) as cliente:
        yield cliente
    app.dependency_overrides.clear()


def test_ciclo_subir_listar_detallar_y_recuperar_el_mismo_archivo(
    api_memoria: TestClient, memoria: AlmacenamientoEnMemoria, sesion: Session
) -> None:
    datos = b"\xff\xd8\xff\xe0" + bytes(range(256)) * 40
    token = _token(MECANICO, NombreRol.MECANICO)

    subida = _subir(api_memoria, token, 7, datos, nombre="frontal.jpg")
    assert subida.status_code == 201, subida.text
    creada = subida.json()

    listado = api_memoria.get("/evidencias", params={"orden_id": 7}, headers=_auth(token))
    assert listado.status_code == 200
    assert [e["evidencia_id"] for e in listado.json()] == [creada["evidencia_id"]]

    detalle = api_memoria.get(f"/evidencias/{creada['evidencia_id']}", headers=_auth(token))
    assert detalle.status_code == 200
    assert detalle.json() == creada

    descarga = api_memoria.get(
        f"/evidencias/{creada['evidencia_id']}/descarga", headers=_auth(token)
    )
    assert descarga.status_code == 200
    url = descarga.json()["url"]
    assert urlsplit(url).netloc == "archivos.taller.test"

    # La URL apunta al objeto de ESTA evidencia y ese objeto tiene los bytes subidos.
    clave = _clave_desde_url(url, BUCKET_MEMORIA)
    assert es_clave_valida(clave)
    assert clave.endswith(f"{uuid.UUID(creada['evidencia_id']).hex}.jpg")
    recuperado = memoria.objetos[clave]["data"]
    assert recuperado == datos

    fila = sesion.scalar(select(Evidencia))
    assert fila.sha256 == _sha256(recuperado)
    assert fila.tamano_bytes == len(datos) == creada["tamano_bytes"]


def test_varias_evidencias_de_una_orden_se_recuperan_sin_cruzarse(
    api_memoria: TestClient, memoria: AlmacenamientoEnMemoria
) -> None:
    token = _token(MECANICO, NombreRol.MECANICO)
    archivos = {
        "antes.jpg": (b"foto-antes" * 50, "image/jpeg"),
        "despues.png": (b"\x89PNG-despues" * 50, "image/png"),
        "prueba.mp4": (b"\x00\x00\x00\x18ftypmp4" * 50, "video/mp4"),
    }
    ids: dict[str, str] = {}
    for nombre, (datos, tipo) in archivos.items():
        respuesta = _subir(api_memoria, token, 8, datos, nombre=nombre, content_type=tipo)
        assert respuesta.status_code == 201, respuesta.text
        ids[nombre] = respuesta.json()["evidencia_id"]

    listado = api_memoria.get("/evidencias", params={"orden_id": 8}, headers=_auth(token))
    # Orden de creación (creada_en ascendente).
    assert [e["nombre_original"] for e in listado.json()] == list(archivos)
    tipos = {e["nombre_original"]: e["tipo_archivo"] for e in listado.json()}
    assert tipos == {"antes.jpg": "foto", "despues.png": "foto", "prueba.mp4": "video"}

    for nombre, (datos, tipo) in archivos.items():
        url = api_memoria.get(
            f"/evidencias/{ids[nombre]}/descarga", headers=_auth(token)
        ).json()["url"]
        clave = _clave_desde_url(url, BUCKET_MEMORIA)
        assert memoria.objetos[clave]["data"] == datos
        assert memoria.objetos[clave]["content_type"] == tipo
        query = parse_qs(urlsplit(url).query)
        assert query["response-content-type"] == [tipo]
        assert nombre in query["response-content-disposition"][0]


def test_nombre_con_tildes_se_conserva_en_consulta_y_descarga(
    api_memoria: TestClient,
) -> None:
    token = _token(MECANICO, NombreRol.MECANICO)
    subida = _subir(api_memoria, token, 9, b"datos" * 20, nombre="daño frontal.jpg")
    assert subida.status_code == 201
    assert subida.json()["nombre_original"] == "daño frontal.jpg"

    url = api_memoria.get(
        f"/evidencias/{subida.json()['evidencia_id']}/descarga", headers=_auth(token)
    ).json()["url"]
    disposicion = parse_qs(urlsplit(url).query)["response-content-disposition"][0]
    assert 'filename="dano frontal.jpg"' in disposicion
    assert "filename*=UTF-8''da%C3%B1o%20frontal.jpg" in disposicion


def test_request_id_de_la_subida_queda_trazable_en_la_base(
    api_memoria: TestClient, sesion: Session
) -> None:
    token = _token(MECANICO, NombreRol.MECANICO)
    subida = _subir(api_memoria, token, 11, b"x" * 64, request_id="req-ciclo-0001")
    assert subida.status_code == 201
    fila = sesion.get(Evidencia, uuid.UUID(subida.json()["evidencia_id"]))
    assert fila.request_id == "req-ciclo-0001"
    assert fila.autor_usuario_id == MECANICO


def test_evidencia_eliminada_no_se_recupera_salvo_administrador(
    api_memoria: TestClient, sesion: Session
) -> None:
    token_mecanico = _token(MECANICO, NombreRol.MECANICO)
    subida = _subir(api_memoria, token_mecanico, 12, b"borrable" * 10)
    evidencia_id = subida.json()["evidencia_id"]

    fila = sesion.get(Evidencia, uuid.UUID(evidencia_id))
    fila.eliminada_en = datetime.now(timezone.utc)
    fila.eliminada_por_usuario_id = ADMIN
    sesion.commit()

    ruta = f"/evidencias/{evidencia_id}/descarga"
    assert api_memoria.get(ruta, headers=_auth(token_mecanico)).status_code == 404
    admin = api_memoria.get(ruta, headers=_auth(_token(ADMIN, NombreRol.ADMINISTRADOR)))
    assert admin.status_code == 200
    assert admin.json()["url"]


def test_cliente_recupera_solo_lo_visible_para_el(
    api_memoria: TestClient, memoria: AlmacenamientoEnMemoria
) -> None:
    token_mecanico = _token(MECANICO, NombreRol.MECANICO)
    visible = _subir(api_memoria, token_mecanico, 13, b"entrega" * 10, contexto="resultado_final")
    interna = _subir(api_memoria, token_mecanico, 13, b"interno" * 10, contexto="diagnostico")
    assert visible.status_code == interna.status_code == 201

    token_cliente = _token(CLIENTE, NombreRol.CLIENTE)
    listado = api_memoria.get("/evidencias", params={"orden_id": 13}, headers=_auth(token_cliente))
    assert [e["evidencia_id"] for e in listado.json()] == [visible.json()["evidencia_id"]]

    ok = api_memoria.get(
        f"/evidencias/{visible.json()['evidencia_id']}/descarga", headers=_auth(token_cliente)
    )
    assert ok.status_code == 200
    assert memoria.objetos[_clave_desde_url(ok.json()["url"], BUCKET_MEMORIA)]["data"] == b"entrega" * 10

    oculta = api_memoria.get(
        f"/evidencias/{interna.json()['evidencia_id']}/descarga", headers=_auth(token_cliente)
    )
    assert oculta.status_code == 404


# ---------------------------------------------------------------------------
# Ciclo con MinIO real (skip si no está levantado)
# ---------------------------------------------------------------------------


@pytest.fixture
def minio() -> Generator[tuple[Settings, object, int], None, None]:
    cfg = Settings()
    cliente = crear_cliente_s3(cfg)
    try:
        cliente.list_objects_v2(Bucket=cfg.S3_BUCKET, MaxKeys=1)
    except _ERRORES_MINIO_APAGADO:
        pytest.skip("MinIO no está disponible (docker compose up -d minio minio_init)")

    orden_id = random.randint(900_000_000, 999_999_999)
    yield cfg, cliente, orden_id

    # Limpieza del prefijo de la orden de prueba.
    respuesta = cliente.list_objects_v2(Bucket=cfg.S3_BUCKET, Prefix=f"ordenes/{orden_id}/")
    for objeto in respuesta.get("Contents", []):
        cliente.delete_object(Bucket=cfg.S3_BUCKET, Key=objeto["Key"])


@pytest.fixture
def api_minio(sesion: Session, minio) -> Generator[TestClient, None, None]:
    cfg, cliente, _ = minio
    with _montar_api(sesion, cliente, crear_cliente_s3_publico(cfg)) as api:
        yield api
    app.dependency_overrides.clear()


def _objetos_de_orden(cfg: Settings, cliente, orden_id: int) -> list[str]:
    respuesta = cliente.list_objects_v2(Bucket=cfg.S3_BUCKET, Prefix=f"ordenes/{orden_id}/")
    return [objeto["Key"] for objeto in respuesta.get("Contents", [])]


def _descargar(url: str) -> httpx.Response:
    # trust_env=False: la URL es del MinIO local, no debe pasar por un proxy.
    return httpx.get(url, timeout=30, trust_env=False)


def test_minio_ciclo_completo_recupera_bytes_identicos(
    api_minio: TestClient, minio, sesion: Session
) -> None:
    cfg, cliente, orden_id = minio
    datos = bytes(random.getrandbits(8) for _ in range(300 * 1024))
    token = _token(MECANICO, NombreRol.MECANICO)

    subida = _subir(api_minio, token, orden_id, datos, nombre="motor daño.jpg")
    assert subida.status_code == 201, subida.text
    evidencia_id = subida.json()["evidencia_id"]

    listado = api_minio.get("/evidencias", params={"orden_id": orden_id}, headers=_auth(token))
    assert [e["evidencia_id"] for e in listado.json()] == [evidencia_id]

    descarga = api_minio.get(f"/evidencias/{evidencia_id}/descarga", headers=_auth(token))
    assert descarga.status_code == 200
    assert descarga.json()["expira_en"] == cfg.URL_DESCARGA_TTL_SECONDS

    archivo = _descargar(descarga.json()["url"])
    assert archivo.status_code == 200
    assert archivo.content == datos
    fila = sesion.get(Evidencia, uuid.UUID(evidencia_id))
    assert _sha256(archivo.content) == fila.sha256

    # Cabeceras forzadas por la firma (checklist 3.4).
    assert archivo.headers["content-type"] == "image/jpeg"
    disposicion = archivo.headers["content-disposition"]
    assert disposicion.startswith("attachment;")
    assert 'filename="motor dano.jpg"' in disposicion


def test_minio_objeto_guarda_metadatos_sin_datos_personales(
    api_minio: TestClient, minio
) -> None:
    cfg, cliente, orden_id = minio
    datos = b"metadatos" * 100
    subida = _subir(
        api_minio, _token(MECANICO, NombreRol.MECANICO), orden_id, datos, nombre="cliente juan.jpg"
    )
    assert subida.status_code == 201
    evidencia_id = uuid.UUID(subida.json()["evidencia_id"])

    [clave] = _objetos_de_orden(cfg, cliente, orden_id)
    assert clave == f"ordenes/{orden_id}/{evidencia_id.hex}.jpg"
    cabecera = cliente.head_object(Bucket=cfg.S3_BUCKET, Key=clave)
    assert cabecera["ContentType"] == "image/jpeg"
    assert cabecera["ContentLength"] == len(datos)
    assert cabecera["Metadata"] == {
        "evidencia-id": evidencia_id.hex,
        "orden-id": str(orden_id),
        "sha256": _sha256(datos),
        "autor-id": str(MECANICO),
    }
    assert "juan" not in str(cabecera["Metadata"])


def test_minio_archivo_sobre_8_mib_usa_multipart_y_se_recupera_integro(
    api_minio: TestClient, minio, sesion: Session
) -> None:
    _, _, orden_id = minio
    # 9 MiB > umbral multipart de 8 MiB (decisión 3 del estudio de almacenamiento).
    bloque = bytes(random.getrandbits(8) for _ in range(64 * 1024))
    datos = bloque * (9 * 16)
    token = _token(MECANICO, NombreRol.MECANICO)

    subida = _subir(api_minio, token, orden_id, datos, nombre="grande.jpg")
    assert subida.status_code == 201, subida.text
    evidencia_id = subida.json()["evidencia_id"]

    url = api_minio.get(f"/evidencias/{evidencia_id}/descarga", headers=_auth(token)).json()["url"]
    archivo = _descargar(url)
    assert archivo.status_code == 200
    assert len(archivo.content) == len(datos)
    assert _sha256(archivo.content) == sesion.get(Evidencia, uuid.UUID(evidencia_id)).sha256


def test_minio_url_vencida_o_alterada_no_permite_recuperar(minio) -> None:
    cfg, cliente, orden_id = minio
    clave = f"ordenes/{orden_id}/{uuid.uuid4().hex}.jpg"
    cliente.upload_fileobj(io.BytesIO(b"secreto" * 10), cfg.S3_BUCKET, clave)

    vigente = generar_url_descarga(
        cliente, cfg.S3_BUCKET, clave,
        content_type="image/jpeg", nombre_descarga="x.jpg", expira_en=300,
    )
    assert _descargar(vigente).status_code == 200

    # Firma alterada → 403.
    partes = urlsplit(vigente)
    query = parse_qs(partes.query)
    firma = query["X-Amz-Signature"][0]
    alterada = vigente.replace(firma, ("0" if firma[0] != "0" else "1") + firma[1:])
    assert _descargar(alterada).status_code == 403

    # Cambiar el nombre forzado invalida la firma → 403 (no se puede manipular 3.4).
    manipulada = vigente.replace("x.jpg", "x.html")
    assert _descargar(manipulada).status_code == 403

    # Vencida → 403.
    corta = generar_url_descarga(
        cliente, cfg.S3_BUCKET, clave,
        content_type="image/jpeg", nombre_descarga="x.jpg", expira_en=1,
    )
    time.sleep(2.5)
    assert _descargar(corta).status_code == 403


def test_minio_acceso_anonimo_al_objeto_es_rechazado(api_minio: TestClient, minio) -> None:
    cfg, cliente, orden_id = minio
    subida = _subir(api_minio, _token(MECANICO, NombreRol.MECANICO), orden_id, b"privado" * 10)
    assert subida.status_code == 201
    [clave] = _objetos_de_orden(cfg, cliente, orden_id)

    anonimo = _descargar(f"{cfg.S3_ENDPOINT.rstrip('/')}/{cfg.S3_BUCKET}/{clave}")
    assert anonimo.status_code == 403
    # Tampoco se puede listar el bucket sin firma.
    assert _descargar(f"{cfg.S3_ENDPOINT.rstrip('/')}/{cfg.S3_BUCKET}").status_code == 403


def test_minio_falla_de_base_no_deja_archivo_huerfano(
    api_minio: TestClient, minio, sesion: Session, monkeypatch
) -> None:
    cfg, cliente, orden_id = minio

    def commit_que_falla() -> None:
        raise RuntimeError("base caída durante el commit")

    monkeypatch.setattr(sesion, "commit", commit_que_falla)
    respuesta = _subir(api_minio, _token(MECANICO, NombreRol.MECANICO), orden_id, b"huerfano" * 50)

    assert respuesta.status_code == 500
    assert _objetos_de_orden(cfg, cliente, orden_id) == []
