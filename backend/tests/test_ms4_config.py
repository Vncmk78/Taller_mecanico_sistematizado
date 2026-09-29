"""Pruebas de configuración S3 del microservicio MS4 (MinIO local).

Verifican que las variables MS4_S3_* se leen del entorno y que los valores
por defecto coinciden con el desarrollo local (controls 2.1 y 2.2 del
checklist de seguridad de evidencias).
"""
from __future__ import annotations

import pytest

from services.ms4_evidencias.config import Settings


def test_settings_s3_sin_entorno_usa_defaults_locales(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for var in (
        "MS4_S3_ENDPOINT",
        "MS4_S3_ACCESS_KEY",
        "MS4_S3_SECRET_KEY",
        "MS4_S3_BUCKET",
        "MS4_S3_REGION",
        "MS4_S3_SECURE",
    ):
        monkeypatch.delenv(var, raising=False)

    settings = Settings(_env_file=None)

    assert settings.S3_ENDPOINT == "http://localhost:9000"
    assert settings.S3_ACCESS_KEY == "ms4-evidencias"
    assert settings.S3_BUCKET == "evidencias"
    assert settings.S3_REGION == "us-east-1"
    assert settings.S3_SECURE is False


def test_settings_s3_lee_las_variables_del_entorno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MS4_S3_ENDPOINT", "http://localhost:19000")
    monkeypatch.setenv("MS4_S3_ACCESS_KEY", "otro-usuario")
    monkeypatch.setenv("MS4_S3_SECRET_KEY", "clave-del-otro-usuario")
    monkeypatch.setenv("MS4_S3_BUCKET", "otro-bucket")
    monkeypatch.setenv("MS4_S3_REGION", "sa-east-1")
    monkeypatch.setenv("MS4_S3_SECURE", "true")

    settings = Settings()

    assert settings.S3_ENDPOINT == "http://localhost:19000"
    assert settings.S3_ACCESS_KEY == "otro-usuario"
    assert settings.S3_SECRET_KEY == "clave-del-otro-usuario"
    assert settings.S3_BUCKET == "otro-bucket"
    assert settings.S3_REGION == "sa-east-1"
    assert settings.S3_SECURE is True