"""Verificación de secretos y configuración por ambiente (Semana 11).

Las claves de estas pruebas son inventadas; ninguna es del despliegue real.
"""
from __future__ import annotations

import pytest

from scripts import verificar_config_ambiente as vca

JWT = "jwt-de-prueba-" + "a" * 40
EVENTOS = "eventos-ms1-ms2-" + "b" * 40
AVISOS = "avisos-ms1-ms3-" + "c" * 40
CONSULTA = "consulta-ms1-ms2-" + "d" * 40
CLAVE_BD = "ClaveLargaDeBase-123"


def _kubero(**cambios: str) -> dict[str, str]:
    """Variables equivalentes a las del panel de Kubero (docs/03)."""
    env = {
        **{f"MS{i}_JWT_SECRET_KEY": JWT for i in range(1, 5)},
        **{
            f"MS{i}_DATABASE_URL": f"postgresql+psycopg://postgres:{CLAVE_BD}@ms{i}-postgres:5432/taller_ms{i}"
            for i in range(1, 5)
        },
        "MS1_EVENT_SHARED_SECRET": EVENTOS,
        "MS2_EVENT_SHARED_SECRET": EVENTOS,
        "MS1_MS3_EVENT_SHARED_SECRET": AVISOS,
        "MS3_EVENT_SHARED_SECRET": AVISOS,
        "MS1_MS2_NOTIFICATION_SECRET": CONSULTA,
        "MS2_NOTIFICATION_LOOKUP_SECRET": CONSULTA,
        "MS2_EVENT_WORKER_ENABLED": "true",
        "MS3_EVENT_WORKER_ENABLED": "true",
        "MS2_MS1_URL": "http://ms1-kuberoapp",
        "MS4_MS2_URL": "http://ms2-kuberoapp",
        "MS4_S3_ENDPOINT": "http://minio-kuberoapp",
        "MS4_S3_PUBLIC_ENDPOINT": "https://ms4-tallerconnect.inf.uct.cl",
        "MS4_S3_SECRET_KEY": "s3-clave-larga-de-prueba-123",
        "GATEWAY_MS1_URL": "http://ms1-kuberoapp",
        "GATEWAY_CORS_ORIGINS": "https://tallerconnect.inf.uct.cl",
        "GATEWAY_CORS_ORIGIN_REGEX": "",
    }
    env.update(cambios)
    return env


def _fallas(reporte: vca.Reporte) -> list[str]:
    return [msg for nivel, msg in reporte.lineas if nivel == "FALLA"]


def test_configuracion_de_kubero_correcta_no_tiene_fallas():
    reporte = vca.verificar_ambiente(_kubero(), "kubero", env_gateway={"GATEWAY_MS1_URL": "x"})
    assert _fallas(reporte) == []


@pytest.mark.parametrize("cambio,esperado", [
    ({"MS3_JWT_SECRET_KEY": "otro-jwt-" + "z" * 40}, "mismo secreto"),
    ({"MS4_JWT_SECRET_KEY": "corto"}, "menos de 32"),
    ({"MS2_EVENT_SHARED_SECRET": "x" * 40}, "no coinciden"),
    ({"MS1_MS2_NOTIFICATION_SECRET": JWT, "MS2_NOTIFICATION_LOOKUP_SECRET": JWT}, "reutilizan el secreto JWT"),
    ({"MS3_EVENT_SHARED_SECRET": ""}, "solo uno"),
    ({"MS1_DATABASE_URL": "postgresql+psycopg://taller:taller@ms1-postgres:5432/taller_ms1"}, "débil"),
    ({"MS2_DATABASE_URL": f"postgresql+psycopg://postgres:{CLAVE_BD}@ms1-postgres:5432/taller_ms1"}, "misma base"),
    ({"MS4_MS2_URL": "http://localhost:8002"}, "localhost"),
    ({"GATEWAY_CORS_ORIGINS": "https://tallerconnect.inf.uct.cl,http://localhost:5173"}, "localhost"),
    ({"GATEWAY_CORS_ORIGIN_REGEX": r"https://.*\.vercel\.app"}, "previews"),
    ({"MS4_S3_SECRET_KEY": "cambia-esta-clave-ms4"}, "valor por defecto"),
    ({"MS4_S3_PUBLIC_ENDPOINT": "http://minio-kuberoapp"}, "HTTPS"),
    ({"MS1_JWT_SECRET_KEY": "reemplaza-por-una-clave-aleatoria-de-al-menos-32-caracteres"}, "plantilla"),
])
def test_errores_de_configuracion_en_kubero_se_detectan(cambio, esperado):
    fallas = _fallas(vca.verificar_ambiente(_kubero(**cambio), "kubero"))
    assert any(esperado in f for f in fallas), fallas


def test_gateway_con_secretos_es_falla():
    reporte = vca.verificar_ambiente(_kubero(), "kubero", env_gateway={"MS1_JWT_SECRET_KEY": JWT})
    assert any("gateway" in f for f in _fallas(reporte))


def test_valores_de_plantilla_en_local_son_solo_avisos():
    env = _kubero(
        MS4_S3_SECRET_KEY="cambia-esta-clave-ms4",
        GATEWAY_CORS_ORIGINS="http://localhost:5173",
        MS4_MS2_URL="http://localhost:8002",
        **{f"MS{i}_DATABASE_URL": f"postgresql+psycopg://taller:taller@localhost:543{i + 2}/taller_ms{i}" for i in range(1, 5)},
    )
    assert _fallas(vca.verificar_ambiente(env, "local")) == []


def test_el_reporte_nunca_incluye_valores_secretos():
    env = _kubero(MS3_JWT_SECRET_KEY="otro-jwt-" + "z" * 40, MS2_EVENT_SHARED_SECRET="x" * 40)
    texto = " ".join(msg for _, msg in vca.verificar_ambiente(env, "kubero").lineas)
    for secreto in (JWT, EVENTOS, AVISOS, CONSULTA, CLAVE_BD, "x" * 40):
        assert secreto not in texto


@pytest.mark.parametrize("texto,hallado", [
    ("token = ghp_" + "A" * 36, ["token de GitHub"]),
    ("url=postgresql+psycopg://sgtm:Real-Clave-99@host/db", ["DSN con clave"]),
    ("url=postgresql+psycopg://taller:taller@localhost:5433/taller_ms1", []),
    ("url=postgresql+psycopg://sgtm_ms1:${SGTM_MS1_BD_CLAVE}@postgres:5432/sgtm_ms1", []),
    ("url=postgresql+psycopg://postgres:<SECRETO>@ms1-postgres:5432/taller_ms1", []),
])
def test_busqueda_de_credenciales_en_el_repositorio(texto, hallado):
    assert vca.buscar_credenciales(texto) == hallado


def test_leer_env_quita_comillas_y_comentarios(tmp_path):
    archivo = tmp_path / ".env.ms4.kubero.local"
    archivo.write_text(
        "# comentario\nMS4_S3_BUCKET=evidencias\nMS4_TIPOS_PERMITIDOS='[\"image/png\"]'\nexport MS4_S3_SECURE=false\n",
        encoding="utf-8",
    )
    assert vca.leer_env(archivo) == {
        "MS4_S3_BUCKET": "evidencias",
        "MS4_TIPOS_PERMITIDOS": '["image/png"]',
        "MS4_S3_SECURE": "false",
    }
