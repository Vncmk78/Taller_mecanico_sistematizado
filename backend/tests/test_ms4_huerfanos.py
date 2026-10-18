"""Detección y limpieza de archivos huérfanos (MS4, Semana 6).

`conciliar` compara el bucket con la tabla de evidencias. Se verifica que:

- detecta objetos sin fila (por ejemplo, cuando la base y el borrado de
  compensación fallaron juntos: `GuardadoEvidenciaError.clave_huerfana`);
- por defecto solo informa; borra únicamente con `eliminar=True`;
- nunca toca objetos recientes (subidas en curso), claves fuera de la
  convención ni archivos de evidencias eliminadas lógicamente (tienen fila);
- un fallo al borrar no detiene la pasada y queda para reintentar;
- sigue la paginación de S3 y reporta filas cuyo archivo ya no existe.

Al final hay una prueba contra MinIO real que se omite si no está levantado.
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from services.ms4_evidencias.models.evidencia import (
    ContextoEvidencia,
    EstadoEvidencia,
    Evidencia,
    TipoArchivo,
)
from services.ms4_evidencias.schemas.evidencia import DatosRecepcion
from services.ms4_evidencias.services.evidencias import (
    GuardadoEvidenciaError,
    recibir_evidencia,
)
from services.ms4_evidencias.services.huerfanos import (
    ANTIGUEDAD_MINIMA_POR_DEFECTO,
    conciliar,
)

from archivos_muestra import JPEG_VALIDO
from test_ms4_recepcion import BUCKET, sesion  # noqa: F401  (fixture)
from test_ms4_recepcion_minio import cliente_minio  # noqa: F401  (fixture)

AHORA = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
VIEJO = AHORA - timedelta(hours=3)
RECIENTE = AHORA - timedelta(minutes=5)


class S3Listable:
    """S3 en memoria con listado paginado y fecha de modificación por objeto."""

    def __init__(self, tamano_pagina: int = 1000) -> None:
        self.objetos: dict[str, dict] = {}
        self.tamano_pagina = tamano_pagina
        self.no_borrables: set[str] = set()
        self.paginas_pedidas = 0

    def poner(self, clave: str, modificado: datetime = VIEJO) -> str:
        self.objetos[clave] = {"data": b"x", "modificado": modificado}
        return clave

    def upload_fileobj(self, fileobj, bucket, clave, ExtraArgs=None, Config=None):
        self.objetos[clave] = {"data": fileobj.read(), "modificado": VIEJO}

    def delete_object(self, Bucket, Key):
        if Key in self.no_borrables:
            raise RuntimeError("MinIO no responde")
        self.objetos.pop(Key, None)

    def list_objects_v2(self, Bucket, Prefix="", ContinuationToken=None, MaxKeys=None):
        self.paginas_pedidas += 1
        claves = sorted(c for c in self.objetos if c.startswith(Prefix))
        inicio = int(ContinuationToken or 0)
        pagina = claves[inicio : inicio + self.tamano_pagina]
        respuesta = {
            "Contents": [
                {"Key": c, "LastModified": self.objetos[c]["modificado"]} for c in pagina
            ],
            "IsTruncated": inicio + self.tamano_pagina < len(claves),
        }
        if respuesta["IsTruncated"]:
            respuesta["NextContinuationToken"] = str(inicio + self.tamano_pagina)
        return respuesta


def _clave(orden: int = 1) -> str:
    return f"ordenes/{orden}/{uuid.uuid4().hex}.jpg"


def _fila(sesion: Session, clave: str, **cambios) -> Evidencia:
    datos = {
        "orden_id": int(clave.split("/")[1]),
        "autor_usuario_id": 7,
        "contexto": ContextoEvidencia.DIAGNOSTICO,
        "tipo_archivo": TipoArchivo.FOTO,
        "estado": EstadoEvidencia.CONFIRMADA,
        "confirmada_en": VIEJO,
        "sha256": "a" * 64,
        "clave_objeto": clave,
        "nombre_original": "foto.jpg",
        "content_type": "image/jpeg",
        "tamano_bytes": 10,
        "creada_en": VIEJO,
    }
    datos.update(cambios)
    evidencia = Evidencia(**datos)
    sesion.add(evidencia)
    sesion.commit()
    return evidencia


def _conciliar(sesion: Session, s3: S3Listable, **kwargs):
    return conciliar(sesion, s3, BUCKET, ahora=AHORA, **kwargs)


# --------------------------------------------------------------------------- #
# 1) Detección                                                                #
# --------------------------------------------------------------------------- #

def test_la_antiguedad_minima_por_defecto_es_una_hora() -> None:
    assert ANTIGUEDAD_MINIMA_POR_DEFECTO == timedelta(minutes=60)


def test_detecta_el_objeto_sin_fila_y_por_defecto_no_lo_borra(sesion: Session) -> None:
    s3 = S3Listable()
    con_fila = s3.poner(_clave())
    _fila(sesion, con_fila)
    huerfano = s3.poner(_clave())

    resultado = _conciliar(sesion, s3)

    assert resultado.revisados == 2
    assert resultado.huerfanos == [huerfano]
    assert resultado.eliminar is False
    assert resultado.eliminados == []
    assert set(s3.objetos) == {con_fila, huerfano}  # simulación: nada se borra


def test_con_eliminar_borra_solo_los_huerfanos(sesion: Session) -> None:
    s3 = S3Listable()
    con_fila = s3.poner(_clave())
    _fila(sesion, con_fila)
    huerfanos = sorted([s3.poner(_clave(1)), s3.poner(_clave(2))])

    resultado = _conciliar(sesion, s3, eliminar=True)

    assert resultado.eliminados == huerfanos
    assert resultado.no_eliminados == []
    assert set(s3.objetos) == {con_fila}


def test_no_toca_objetos_recientes(sesion: Session) -> None:
    s3 = S3Listable()
    en_curso = s3.poner(_clave(), modificado=RECIENTE)

    resultado = _conciliar(sesion, s3, eliminar=True)

    assert resultado.recientes == 1
    assert resultado.huerfanos == []
    assert en_curso in s3.objetos


def test_la_antiguedad_minima_es_configurable(sesion: Session) -> None:
    s3 = S3Listable()
    clave = s3.poner(_clave(), modificado=RECIENTE)

    resultado = _conciliar(sesion, s3, antiguedad_minima=timedelta(minutes=1))

    assert resultado.huerfanos == [clave]


@pytest.mark.parametrize(
    "clave",
    [
        "ordenes/1/no-es-uuid.jpg",
        "ordenes/01/" + "a" * 32 + ".jpg",
        "ordenes/1/" + "a" * 32 + ".exe-largo",
        "ordenes/1/../../otra/" + "a" * 32 + ".jpg",
    ],
)
def test_nunca_borra_claves_fuera_de_la_convencion(sesion: Session, clave: str) -> None:
    s3 = S3Listable()
    s3.poner(clave)

    resultado = _conciliar(sesion, s3, eliminar=True)

    assert resultado.claves_ajenas == [clave]
    assert resultado.huerfanos == []
    assert clave in s3.objetos


def test_solo_revisa_el_prefijo_de_evidencias(sesion: Session) -> None:
    s3 = S3Listable()
    s3.poner("otro-sistema/archivo.jpg")

    resultado = _conciliar(sesion, s3, eliminar=True)

    assert resultado.revisados == 0
    assert "otro-sistema/archivo.jpg" in s3.objetos


def test_el_archivo_de_una_evidencia_eliminada_no_es_huerfano(sesion: Session) -> None:
    s3 = S3Listable()
    clave = s3.poner(_clave())
    _fila(sesion, clave, eliminada_en=VIEJO, eliminada_por_usuario_id=2)

    resultado = _conciliar(sesion, s3, eliminar=True)

    assert resultado.huerfanos == []
    assert clave in s3.objetos


def test_compara_por_clave_objeto_y_respeta_claves_antiguas(sesion: Session) -> None:
    # Antes de la convención, el UUID de la clave no era el evidencia_id.
    s3 = S3Listable()
    clave_antigua = s3.poner(_clave())
    _fila(sesion, clave_antigua, evidencia_id=uuid.uuid4())

    resultado = _conciliar(sesion, s3, eliminar=True)

    assert resultado.huerfanos == []


def test_un_borrado_fallido_no_detiene_la_pasada(sesion: Session) -> None:
    s3 = S3Listable()
    primero, segundo = sorted([s3.poner(_clave()), s3.poner(_clave())])
    s3.no_borrables.add(primero)

    resultado = _conciliar(sesion, s3, eliminar=True)

    assert resultado.no_eliminados == [primero]
    assert resultado.eliminados == [segundo]
    assert primero in s3.objetos


def test_sigue_la_paginacion_del_bucket(sesion: Session) -> None:
    s3 = S3Listable(tamano_pagina=2)
    claves = [s3.poner(_clave(orden)) for orden in range(1, 6)]

    resultado = _conciliar(sesion, s3)

    assert resultado.revisados == 5
    assert resultado.huerfanos == sorted(claves)
    assert s3.paginas_pedidas == 3


def test_consulta_la_base_por_lotes(sesion: Session) -> None:
    s3 = S3Listable()
    claves = [s3.poner(_clave()) for _ in range(1200)]
    for clave in claves[:600]:
        _fila(sesion, clave)

    resultado = _conciliar(sesion, s3)

    assert len(resultado.huerfanos) == 600
    assert set(resultado.huerfanos) == set(claves[600:])


# --------------------------------------------------------------------------- #
# 2) Filas sin archivo (solo se reportan)                                     #
# --------------------------------------------------------------------------- #

def test_reporta_filas_vigentes_sin_archivo_sin_tocarlas(sesion: Session) -> None:
    s3 = S3Listable()
    sin_archivo = _fila(sesion, _clave())
    _fila(sesion, _clave(), eliminada_en=VIEJO, eliminada_por_usuario_id=2)
    _fila(sesion, _clave(), creada_en=RECIENTE, confirmada_en=RECIENTE)
    con_archivo = s3.poner(_clave())
    _fila(sesion, con_archivo)

    resultado = _conciliar(sesion, s3, eliminar=True)

    assert resultado.filas_sin_objeto == [sin_archivo.evidencia_id]
    assert sesion.get(Evidencia, sin_archivo.evidencia_id) is not None


# --------------------------------------------------------------------------- #
# 3) Integración con la compensación de recibir_evidencia                     #
# --------------------------------------------------------------------------- #

class S3SinBorrado(S3Listable):
    def delete_object(self, Bucket, Key):
        raise RuntimeError("MinIO no responde al borrar")


def test_la_clave_huerfana_de_la_compensacion_se_limpia_despues(
    sesion: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    s3 = S3SinBorrado()

    def commit_que_falla(*args, **kwargs) -> None:
        raise RuntimeError("base caída")

    monkeypatch.setattr(sesion, "commit", commit_que_falla)
    with pytest.raises(GuardadoEvidenciaError) as error:
        recibir_evidencia(
            sesion,
            s3,
            BUCKET,
            DatosRecepcion(orden_id=1, contexto=ContextoEvidencia.DIAGNOSTICO),
            io.BytesIO(JPEG_VALIDO),
            "foto.jpg",
            "image/jpeg",
            7,
            None,
        )
    monkeypatch.undo()
    clave = error.value.clave_huerfana
    assert clave in s3.objetos

    # Más tarde, con MinIO de vuelta, la conciliación encuentra y borra el huérfano.
    s3.__class__ = S3Listable
    resultado = _conciliar(sesion, s3, eliminar=True)

    assert resultado.eliminados == [clave]
    assert clave not in s3.objetos


# --------------------------------------------------------------------------- #
# 4) MinIO real (se omite si no está levantado)                               #
# --------------------------------------------------------------------------- #

def test_conciliacion_contra_minio_real(cliente_minio, sesion: Session) -> None:  # noqa: F811
    cfg, cliente = cliente_minio
    orden = 900_000_000 + uuid.uuid4().int % 99_999_999
    huerfano = f"ordenes/{orden}/{uuid.uuid4().hex}.jpg"
    con_fila = f"ordenes/{orden}/{uuid.uuid4().hex}.jpg"
    for clave in (huerfano, con_fila):
        cliente.put_object(Bucket=cfg.S3_BUCKET, Key=clave, Body=JPEG_VALIDO)
    _fila(sesion, con_fila)

    try:
        resultado = conciliar(
            sesion,
            cliente,
            cfg.S3_BUCKET,
            antiguedad_minima=timedelta(0),
            eliminar=True,
            ahora=datetime.now(timezone.utc) + timedelta(seconds=5),
        )
        assert huerfano in resultado.eliminados
        assert con_fila not in resultado.huerfanos
        restantes = cliente.list_objects_v2(Bucket=cfg.S3_BUCKET, Prefix=f"ordenes/{orden}/")
        assert [o["Key"] for o in restantes.get("Contents", [])] == [con_fila]
    finally:
        for clave in (huerfano, con_fila):
            cliente.delete_object(Bucket=cfg.S3_BUCKET, Key=clave)


# --------------------------------------------------------------------------- #
# 5) Script de línea de comandos                                              #
# --------------------------------------------------------------------------- #

def _cargar_script():
    import importlib.util
    from pathlib import Path

    ruta = Path(__file__).resolve().parents[1] / "scripts" / "limpiar_huerfanos_ms4.py"
    spec = importlib.util.spec_from_file_location("limpiar_huerfanos_ms4", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize(
    ("argumentos", "huerfanos", "no_eliminados", "codigo", "texto"),
    [
        ([], ["ordenes/1/x.jpg"], [], 1, "SIMULACIÓN"),
        ([], [], [], 0, "SIMULACIÓN"),
        (["--eliminar"], ["ordenes/1/x.jpg"], [], 0, "ELIMINACIÓN"),
        (["--eliminar"], ["ordenes/1/x.jpg"], ["ordenes/1/x.jpg"], 1, "ELIMINACIÓN"),
    ],
)
def test_script_informa_y_devuelve_el_codigo_de_salida(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argumentos: list[str],
    huerfanos: list[str],
    no_eliminados: list[str],
    codigo: int,
    texto: str,
) -> None:
    from services.ms4_evidencias.services.huerfanos import ResultadoConciliacion

    script = _cargar_script()
    llamadas: list[dict] = []

    def conciliar_falso(db, s3, bucket, **kwargs):
        llamadas.append(kwargs)
        return ResultadoConciliacion(
            revisados=3,
            huerfanos=huerfanos,
            eliminados=[c for c in huerfanos if c not in no_eliminados]
            if kwargs["eliminar"]
            else [],
            no_eliminados=no_eliminados,
            eliminar=kwargs["eliminar"],
        )

    monkeypatch.setattr(script, "conciliar", conciliar_falso)
    monkeypatch.setattr(script, "crear_cliente_s3", lambda cfg: object())
    monkeypatch.setattr(script, "SessionLocal", lambda: _SesionNula())
    monkeypatch.setattr("sys.argv", ["limpiar_huerfanos_ms4.py", *argumentos])

    assert script.main() == codigo
    assert texto in capsys.readouterr().out
    assert llamadas[0]["eliminar"] is ("--eliminar" in argumentos)
    assert llamadas[0]["antiguedad_minima"] == timedelta(minutes=60)


def test_script_sin_conexion_sale_con_2_sin_detalles(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = _cargar_script()

    def cliente_que_falla(cfg):
        raise RuntimeError("clave-secreta http://minio:9000")

    monkeypatch.setattr(script, "crear_cliente_s3", cliente_que_falla)
    monkeypatch.setattr("sys.argv", ["limpiar_huerfanos_ms4.py"])

    assert script.main() == 2
    salida = capsys.readouterr()
    assert "clave-secreta" not in salida.err + salida.out
    assert "RuntimeError" in salida.err


class _SesionNula:
    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None
