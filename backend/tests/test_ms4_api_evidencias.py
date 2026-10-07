"""Pruebas HTTP de subida y consulta de evidencias (MS4) — controles 3.1, 3.3 y 3.4.

Usan el TestClient de FastAPI contra `main.app` con SQLite en memoria
(StaticPool) y `dependency_overrides` para `get_db`, `obtener_s3` (FakeS3) y
`obtener_s3_publico` (cliente boto3 real que firma offline contra un endpoint
público de prueba, sin tocar la red). Verifican los contratos:

- subida: 201 mecánico/admin, 403 cliente, 401 sin token, 422 archivo vacío /
  tipo de archivo / contexto / reglas de presupuesto, 503 si el almacenamiento
  falla (sin filas ni objetos sueltos);
- consulta: filtros de visibilidad por rol en el listado, 422 sin `orden_id`,
  404 por no enumeración en detalle y descarga, cabeceras seguras en la
  descarga, y que `clave_objeto`, `sha256` y el autor nunca viajan en JSON.
"""
from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from services.ms4_evidencias.config import Settings, settings
from services.ms4_evidencias.db import get_db
from services.ms4_evidencias.dependencies import obtener_s3, obtener_s3_publico
from services.ms4_evidencias.integracion_ms2 import obtener_verificador_ordenes
from services.ms4_evidencias.main import app
from services.ms4_evidencias.models import Base
from services.ms4_evidencias.models.evidencia import (
    ContextoEvidencia,
    EstadoEvidencia,
    Evidencia,
    TipoArchivo,
)
from services.ms4_evidencias.services.almacenamiento import crear_cliente_s3_publico
from shared.auth import NombreRol, crear_token_acceso

from test_ms4_recepcion import FakeS3

SECRETO = "clave-secreta-exclusiva-para-pruebas-de-ms4-123456"
BUCKET = "evidencias"
# Distinto de la palabra "evidencias" del mensaje genérico, para poder
# comprobar que el body no filtra el bucket en que ocurrió el error.
BUCKET_OCULTO = "evidencias-s3-prueba-oculta"
ORDEN = 10


class FakeS3ConError(FakeS3):
    """FakeS3 cuyo fallo de subida es un error real de botocore (→ 503)."""

    def upload_fileobj(self, fileobj, bucket, clave, ExtraArgs=None, Config=None):
        if self.fallar_subida:
            raise ClientError(
                {"Error": {"Code": "NoSuchBucket", "Message": "bucket no existe"}},
                "HeadBucket",
            )
        return super().upload_fileobj(
            fileobj, bucket, clave, ExtraArgs=ExtraArgs, Config=Config
        )


class FakeS3SubidaFallida(FakeS3):
    """FakeS3 cuyo fallo de subida es un S3UploadFailedError de boto3 (→ 503)."""

    def upload_fileobj(self, fileobj, bucket, clave, ExtraArgs=None, Config=None):
        if self.fallar_subida:
            raise S3UploadFailedError(
                f"Failed to upload {clave} to {bucket}: An error occurred "
                "(AccessDenied) when calling the PutObject operation: Access Denied"
            )
        return super().upload_fileobj(
            fileobj, bucket, clave, ExtraArgs=ExtraArgs, Config=Config
        )


class VerificadorPermiteTodo:
    """Falso MS2 que acepta cualquier orden: los tests de aquí no prueban la
    verificación (esa es tarea de test_ms4_autorizacion_evidencias.py)."""

    def verificar_acceso(self, orden_id: int, token: str) -> None:
        return None


def _crear_settings_publico() -> Settings:
    return Settings(
        _env_file=None,
        S3_ENDPOINT="http://minio:9000",
        S3_PUBLIC_ENDPOINT="http://minio.publico.test:9000",
        S3_ACCESS_KEY="ms4-evidencias",
        S3_SECRET_KEY="clave-de-prueba",
        S3_BUCKET=BUCKET,
        S3_REGION="us-east-1",
        S3_SECURE=False,
    )


def _token(usuario_id: int, *roles: NombreRol) -> str:
    return crear_token_acceso(usuario_id, frozenset(roles), clave_secreta=SECRETO)


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


@pytest.fixture
def api(
    sesion: Session, s3: FakeS3, s3_publico
) -> Generator[TestClient, None, None]:
    def reemplazar_db():
        yield sesion

    app.dependency_overrides[get_db] = reemplazar_db
    app.dependency_overrides[obtener_s3] = lambda: s3
    app.dependency_overrides[obtener_s3_publico] = lambda: s3_publico
    app.dependency_overrides[obtener_verificador_ordenes] = lambda: VerificadorPermiteTodo()
    with TestClient(app) as cliente:
        yield cliente
    app.dependency_overrides.clear()


def _contar_filas(sesion: Session) -> int:
    return sesion.scalar(select(func.count()).select_from(Evidencia)) or 0


def _subir(
    cliente: TestClient,
    token: str,
    *,
    archivo: bytes = b"datos-de-foto",
    nombre: str = "foto.jpg",
    content_type: str = "image/jpeg",
    orden_id: int = 1,
    contexto: str = "diagnostico",
    presupuesto_id: int | None = None,
    visible_cliente: str | None = None,
):
    datos = {"orden_id": str(orden_id), "contexto": contexto}
    if presupuesto_id is not None:
        datos["presupuesto_id"] = str(presupuesto_id)
    if visible_cliente is not None:
        datos["visible_cliente"] = visible_cliente
    return cliente.post(
        "/evidencias",
        headers={"Authorization": f"Bearer {token}"},
        data=datos,
        files={"archivo": (nombre, archivo, content_type)},
    )


def _nueva(**cambios) -> Evidencia:
    """Evidencia mínima válida para armar escenarios sin pasar por la API."""
    datos = {
        "orden_id": ORDEN,
        "autor_usuario_id": 7,
        "contexto": ContextoEvidencia.DIAGNOSTICO,
        "tipo_archivo": TipoArchivo.FOTO,
        "clave_objeto": f"ordenes/{ORDEN}/{uuid.uuid4().hex}.bin",
        "nombre_original": "foto.jpg",
        "content_type": "image/jpeg",
        "tamano_bytes": 2048,
    }
    datos.update(cambios)
    return Evidencia(**datos)


def _sembrar(sesion: Session, *evidencias: Evidencia) -> None:
    sesion.add_all(evidencias)
    sesion.commit()


def _escenario_visibilidad() -> list[Evidencia]:
    t1 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 1, 10, 1, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 1, 10, 2, tzinfo=timezone.utc)
    t4 = datetime(2026, 9, 1, 10, 3, tzinfo=timezone.utc)
    t5 = datetime(2026, 9, 1, 10, 4, tzinfo=timezone.utc)
    return [
        _nueva(estado=EstadoEvidencia.PENDIENTE, creada_en=t1),
        _nueva(
            estado=EstadoEvidencia.CONFIRMADA,
            confirmada_en=t2,
            sha256="a" * 64,
            visible_cliente=False,
            creada_en=t2,
        ),
        _nueva(
            contexto=ContextoEvidencia.RESULTADO_FINAL,
            estado=EstadoEvidencia.CONFIRMADA,
            confirmada_en=t3,
            sha256="b" * 64,
            visible_cliente=True,
            creada_en=t3,
        ),
        _nueva(
            contexto=ContextoEvidencia.REPARACION,
            estado=EstadoEvidencia.CONFIRMADA,
            confirmada_en=t4,
            sha256="c" * 64,
            visible_cliente=True,
            eliminada_en=t4,
            eliminada_por_usuario_id=2,
            creada_en=t4,
        ),
        _nueva(
            contexto=ContextoEvidencia.REPARACION,
            estado=EstadoEvidencia.ANULADA,
            visible_cliente=True,
            creada_en=t5,
        ),
    ]


# --------------------------------------------------------------------------- #
# 1) Subida (control 3.1): rol, autenticación y rechazos                      #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("rol", [NombreRol.MECANICO, NombreRol.ADMINISTRADOR])
def test_mecanico_y_administrador_suben_una_foto(
    api: TestClient, s3: FakeS3, sesion: Session, rol: NombreRol
) -> None:
    respuesta = _subir(api, _token(7, rol))

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert "evidencia_id" in cuerpo
    assert cuerpo["orden_id"] == 1
    assert cuerpo["estado"] == EstadoEvidencia.CONFIRMADA.value
    # Los campos internos jamás salen en el JSON.
    assert "clave_objeto" not in cuerpo
    assert "sha256" not in cuerpo
    assert "autor" not in cuerpo
    assert "ordenes/" not in str(cuerpo)
    # El objeto quedó en el almacenamiento y la fila en la base.
    assert len(s3.objetos) == 1
    assert _contar_filas(sesion) == 1


def test_cliente_no_puede_subir_y_no_deja_residuos(api: TestClient, s3: FakeS3, sesion: Session) -> None:
    respuesta = _subir(api, _token(9, NombreRol.CLIENTE))

    assert respuesta.status_code == 403
    assert not s3.objetos
    assert _contar_filas(sesion) == 0


def test_sin_token_responde_401_con_www_authenticate(api: TestClient) -> None:
    respuesta = api.post("/evidencias")

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_token_invalido_responde_401(api: TestClient) -> None:
    respuesta = api.post(
        "/evidencias", headers={"Authorization": "Bearer token-invalido"}
    )

    assert respuesta.status_code == 401


def test_archivo_vacio_se_rechaza_con_422(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    respuesta = _subir(api, _token(7, NombreRol.MECANICO), archivo=b"")

    assert respuesta.status_code == 422
    assert not s3.objetos
    assert _contar_filas(sesion) == 0


def test_tipo_de_archivo_no_permitido_se_rechaza_con_422(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    respuesta = _subir(
        api, _token(7, NombreRol.MECANICO), content_type="text/plain"
    )

    assert respuesta.status_code == 422
    assert not s3.objetos
    assert _contar_filas(sesion) == 0


def test_contexto_invalido_se_rechaza_con_422(api: TestClient) -> None:
    respuesta = _subir(api, _token(7, NombreRol.MECANICO), contexto="otro")

    assert respuesta.status_code == 422


def test_presupuesto_sin_presupuesto_id_se_rechaza_con_422(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    respuesta = _subir(
        api, _token(7, NombreRol.MECANICO), contexto="presupuesto"
    )

    assert respuesta.status_code == 422
    assert not s3.objetos
    assert _contar_filas(sesion) == 0


def test_presupuesto_con_presupuesto_id_queda_visible_para_el_cliente(
    api: TestClient, s3: FakeS3, sesion: Session
) -> None:
    respuesta = _subir(
        api,
        _token(7, NombreRol.MECANICO),
        contexto="presupuesto",
        presupuesto_id=42,
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["visible_cliente"] is True
    assert _contar_filas(sesion) == 1


def test_si_el_almacenamiento_falla_responde_503_sin_filas(
    sesion: Session, s3_publico
) -> None:
    s3 = FakeS3ConError()
    s3.fallar_subida = True

    def reemplazar_db():
        yield sesion

    def reemplazar_s3():
        return s3

    app.dependency_overrides[get_db] = reemplazar_db
    app.dependency_overrides[obtener_s3] = reemplazar_s3
    app.dependency_overrides[obtener_s3_publico] = lambda: s3_publico
    app.dependency_overrides[obtener_verificador_ordenes] = lambda: VerificadorPermiteTodo()
    try:
        with TestClient(app) as cliente:
            respuesta = _subir(cliente, _token(7, NombreRol.MECANICO))
    finally:
        app.dependency_overrides.clear()

    assert respuesta.status_code == 503
    assert not s3.objetos
    assert _contar_filas(sesion) == 0


def test_s3_upload_failed_error_responde_503_sin_filas_ni_detalles(
    sesion: Session, s3_publico, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "S3_BUCKET", BUCKET_OCULTO)
    s3 = FakeS3SubidaFallida()
    s3.fallar_subida = True

    def reemplazar_db():
        yield sesion

    def reemplazar_s3():
        return s3

    app.dependency_overrides[get_db] = reemplazar_db
    app.dependency_overrides[obtener_s3] = reemplazar_s3
    app.dependency_overrides[obtener_s3_publico] = lambda: s3_publico
    app.dependency_overrides[obtener_verificador_ordenes] = lambda: VerificadorPermiteTodo()
    try:
        with TestClient(app) as cliente:
            respuesta = _subir(cliente, _token(7, NombreRol.MECANICO))
    finally:
        app.dependency_overrides.clear()

    assert respuesta.status_code == 503
    assert not s3.objetos
    assert _contar_filas(sesion) == 0
    # El 503 es genérico: no filtra el AccessDenied ni el bucket de S3.
    cuerpo = respuesta.json()
    assert "AccessDenied" not in str(cuerpo)
    assert BUCKET_OCULTO not in str(cuerpo)


# --------------------------------------------------------------------------- #
# 2) Listado por orden: visibilidad por rol                                   #
# --------------------------------------------------------------------------- #

def test_listado_aplica_los_filtros_de_visibilidad_por_rol(
    api: TestClient, sesion: Session
) -> None:
    escenario = _escenario_visibilidad()
    _sembrar(sesion, *escenario)

    cliente = api.get(
        "/evidencias",
        params={"orden_id": ORDEN},
        headers={"Authorization": f"Bearer {_token(9, NombreRol.CLIENTE)}"},
    )
    assert cliente.status_code == 200
    ids_cliente = [e["evidencia_id"] for e in cliente.json()]
    esperado_cliente = [
        str(e.evidencia_id)
        for e in escenario
        if e.visible_cliente
        and e.estado == EstadoEvidencia.CONFIRMADA
        and e.eliminada_en is None
    ]
    assert sorted(ids_cliente) == sorted(esperado_cliente)

    mecanico = api.get(
        "/evidencias",
        params={"orden_id": ORDEN},
        headers={"Authorization": f"Bearer {_token(7, NombreRol.MECANICO)}"},
    )
    assert mecanico.status_code == 200
    # Todas las no eliminadas (incluye pendiente, no-visible y anulada).
    assert len(mecanico.json()) == sum(
        1 for e in escenario if e.eliminada_en is None
    )

    admin = api.get(
        "/evidencias",
        params={"orden_id": ORDEN},
        headers={"Authorization": f"Bearer {_token(1, NombreRol.ADMINISTRADOR)}"},
    )
    assert admin.status_code == 200
    # El administrador ve todas, incluidas las eliminadas (auditoría, §4.5).
    assert len(admin.json()) == len(escenario)


def test_listado_sin_orden_id_responde_422(api: TestClient) -> None:
    respuesta = api.get(
        "/evidencias",
        headers={"Authorization": f"Bearer {_token(7, NombreRol.MECANICO)}"},
    )

    assert respuesta.status_code == 422


def test_listado_sin_token_responde_401(api: TestClient) -> None:
    respuesta = api.get("/evidencias", params={"orden_id": ORDEN})

    assert respuesta.status_code == 401


# --------------------------------------------------------------------------- #
# 3) Detalle y descarga: 404 por no enumeración                               #
# --------------------------------------------------------------------------- #

def test_cliente_ve_la_visible_y_no_existe_la_oculta(
    api: TestClient, sesion: Session
) -> None:
    pendiente, no_visible, visible, *_ = _escenario_visibilidad()
    _sembrar(sesion, pendiente, no_visible, visible)

    cabeceras = {
        "Authorization": f"Bearer {_token(9, NombreRol.CLIENTE)}"
    }
    oculta = api.get(f"/evidencias/{no_visible.evidencia_id}", headers=cabeceras)
    assert oculta.status_code == 404
    assert "clave_objeto" not in str(oculta.json())

    publica = api.get(f"/evidencias/{visible.evidencia_id}", headers=cabeceras)
    assert publica.status_code == 200
    cuerpo = publica.json()
    assert cuerpo["evidencia_id"] == str(visible.evidencia_id)
    assert "clave_objeto" not in cuerpo
    assert "sha256" not in cuerpo
    # Ningún campo interno replica la convención de claves ("ordenes/...").
    assert "ordenes/" not in str(cuerpo)


def test_mecanico_ve_evidencias_no_visibles_y_administrador_ve_eliminadas(
    api: TestClient, sesion: Session
) -> None:
    pendiente, no_visible, visible, eliminada, anulada = _escenario_visibilidad()
    _sembrar(sesion, pendiente, no_visible, visible, eliminada, anulada)

    mecanico = api.get(
        f"/evidencias/{no_visible.evidencia_id}",
        headers={"Authorization": f"Bearer {_token(7, NombreRol.MECANICO)}"},
    )
    assert mecanico.status_code == 200

    # La eliminada solo la ve el administrador: el mecánico recibe 404 (no enumera).
    mecanico_oculta = api.get(
        f"/evidencias/{eliminada.evidencia_id}",
        headers={"Authorization": f"Bearer {_token(7, NombreRol.MECANICO)}"},
    )
    assert mecanico_oculta.status_code == 404

    admin = api.get(
        f"/evidencias/{eliminada.evidencia_id}",
        headers={"Authorization": f"Bearer {_token(1, NombreRol.ADMINISTRADOR)}"},
    )
    assert admin.status_code == 200


def test_detalle_de_uuid_inexistente_responde_404(api: TestClient) -> None:
    respuesta = api.get(
        f"/evidencias/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {_token(9, NombreRol.CLIENTE)}"},
    )

    assert respuesta.status_code == 404


def test_descarga_devuelve_url_firmada_y_cabeceras_seguras(
    api: TestClient, sesion: Session
) -> None:
    visible = _nueva(
        contexto=ContextoEvidencia.RESULTADO_FINAL,
        estado=EstadoEvidencia.CONFIRMADA,
        confirmada_en=datetime.now(timezone.utc),
        sha256="d" * 64,
        visible_cliente=True,
        nombre_original="foto del taller.jpg",
        content_type="image/jpeg",
    )
    _sembrar(sesion, visible)

    respuesta = api.get(
        f"/evidencias/{visible.evidencia_id}/descarga",
        headers={"Authorization": f"Bearer {_token(9, NombreRol.CLIENTE)}"},
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["cache-control"] == "no-store"
    assert respuesta.headers["x-content-type-options"] == "nosniff"

    cuerpo = respuesta.json()
    url = cuerpo["url"]
    assert cuerpo["expira_en"] == 300
    assert urlsplit(url).netloc == "minio.publico.test:9000"
    parametros = parse_qs(urlsplit(url).query)
    assert parametros["X-Amz-Expires"] == ["300"]
    assert parametros["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
    assert parametros["response-content-type"] == ["image/jpeg"]
    assert "response-content-disposition" in parametros
    # Schema mínimo (url + expira_en): la clave del objeto solo puede aparecer
    # dentro de la URL firmada (es el key de S3), nunca como campo del JSON.
    assert set(cuerpo) == {"url", "expira_en"}
    assert "clave_objeto" not in str(cuerpo)


def test_descarga_de_evidencia_fuera_del_alcance_responde_404(
    api: TestClient, sesion: Session
) -> None:
    no_visible = _nueva(
        estado=EstadoEvidencia.CONFIRMADA,
        confirmada_en=datetime.now(timezone.utc),
        sha256="e" * 64,
        visible_cliente=False,
    )
    _sembrar(sesion, no_visible)

    respuesta = api.get(
        f"/evidencias/{no_visible.evidencia_id}/descarga",
        headers={"Authorization": f"Bearer {_token(9, NombreRol.CLIENTE)}"},
    )

    assert respuesta.status_code == 404