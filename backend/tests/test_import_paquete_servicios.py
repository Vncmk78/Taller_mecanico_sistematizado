"""El paquete `services` debe ser inerte al importarse.

Kubero arranca MS1–MS4 con `services.msN_...:app`. Python ejecuta primero
`services/__init__.py`; si ahí se instancia `Settings` de MS4, cualquier
microservicio que importe un submódulo exige `MS4_JWT_SECRET_KEY` y entra en
CrashLoopBackOff cuando esa variable no está definida (despliegue `sha-181e65d`).

Las pruebas aíslan los imports en subprocesses sin variables `MS4_` y sin
archivo `.env`, para reproducir el entorno de los pods de MS1/MS2/MS3.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
MODULOS = (
    "services.ms1_auth.main",
    "services.ms2_taller.main",
    "services.ms3_presupuestos.main",
)


def _entorno_sin_ms4() -> dict[str, str]:
    entorno = {
        clave: valor
        for clave, valor in os.environ.items()
        if not clave.startswith("MS4_") and clave != "JWT_SECRET_KEY"
    }
    # pydantic-settings leería el .env local (con secretos de MS4) si no se
    # apunta a un archivo inexistente: el pod de producción no tiene ese .env.
    entorno["SGTM_ENV_FILE"] = ".env.inexistente-para-esta-prueba"
    entorno["PYTHONIOENCODING"] = "utf-8"
    # Valores ficticios suficientes para construir los motores y los settings;
    # no se abre ninguna conexión durante el import.
    entorno.update(
        {
            "MS1_JWT_SECRET_KEY": "clave-de-prueba-import-ms1-1234567890",
            "MS2_JWT_SECRET_KEY": "clave-de-prueba-import-ms2-1234567890",
            "MS3_JWT_SECRET_KEY": "clave-de-prueba-import-ms3-1234567890",
            "MS1_DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/ms1",
            "MS2_DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/ms2",
            "MS3_DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/ms3",
            "MS2_EVENT_WORKER_ENABLED": "false",
        }
    )
    return entorno


def _importar_en_subprocess(modulo: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", f"import {modulo}"],
        cwd=RAIZ_BACKEND,
        env=_entorno_sin_ms4(),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def test_importar_paquete_servicios_no_exige_secretos_de_ms4() -> None:
    resultado = _importar_en_subprocess("services")
    assert resultado.returncode == 0, resultado.stderr


@pytest.mark.parametrize("modulo", MODULOS)
def test_arrancar_ms1_ms2_ms3_sin_secretos_de_ms4(modulo: str) -> None:
    resultado = _importar_en_subprocess(modulo)
    assert resultado.returncode == 0, resultado.stderr
