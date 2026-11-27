# Evidencia de validación del despliegue — rama `DerisA`

Fecha: 2026-11-25 · Rama `DerisA`, commit base `b74030a` · Windows ·
Python 3.13.3 del entorno `backend/.venv`.

Estado Git al iniciar: `DerisA...origin/DerisA`, sin cambios locales.

Objetivo: registrar las validaciones **ejecutadas localmente** sobre el código de
despliegue de `DerisA`. Este documento no reemplaza
`validacion-despliegue-limpio.md` (evidencia histórica de las ramas `MartinL` y
`MartinH`) y no acredita un despliegue público. El procedimiento de referencia
sigue siendo `despliegue-base-datos.md`.

## Comprobaciones ejecutadas

Todas se ejecutaron desde `backend/`, con `PYTHONPATH` apuntando a ese directorio.

### 1. Scripts de aprovisionamiento y migración (registro histórico)

> El comando original incluía `tests/test_despliegue_vercel.py`, retirado junto
> con la plataforma anterior. Las pruebas vigentes equivalentes son
> `tests/test_direccion_ms3.py` y `tests/test_direccion_notificaciones.py`.

```powershell
$env:PYTHONPATH=(Get-Location).Path; .\.venv\Scripts\python.exe -m pytest tests/test_inicializar_bd.py tests/test_scripts_despliegue.py tests/test_despliegue_vercel.py -q
```

Resultado real: `1 failed, 66 passed, 1 warning in 3.94s`.

Cubre las pruebas unitarias de `inicializar_bd.py`, `migrar.py`, el contrato de
Vercel y el resto de scripts de despliegue. El único fallo se detalla más abajo.

### 2. Aislamiento, rotación JWT, CORS y exposición de secretos

```powershell
$env:PYTHONPATH=(Get-Location).Path; .\.venv\Scripts\python.exe -m pytest tests/test_ambiente_pruebas.py tests/test_gateway_estructura.py tests/test_exposicion_indebida_datos.py -q
```

Resultado real: `38 passed, 1 warning in 38.14s`.

Cubre el ambiente aislado de pruebas, la rotación de la clave JWT, la
configuración de CORS de la Gateway y el enmascaramiento de secretos en
respuestas y mensajes.

### 3. Sintaxis de scripts

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts/inicializar_bd.py scripts/ambiente_pruebas.py scripts/verificar_backend.py
```

Resultado real: sin salida y código de salida 0.

El aviso de las dos ejecuciones de `pytest` es el mismo:
`StarletteDeprecationWarning` de `fastapi/testclient.py` sobre el uso de `httpx`
con `starlette.testclient`. No afecta al resultado de las pruebas.

## Fallo conocido reproducido

Prueba: `tests/test_scripts_despliegue.py::test_migrador_incluye_ms4_y_verificacion_final`.

Repetición aislada:

```powershell
$env:PYTHONPATH=(Get-Location).Path; .\.venv\Scripts\python.exe -m pytest tests/test_scripts_despliegue.py::test_migrador_incluye_ms4_y_verificacion_final -q
```

Resultado real: `1 failed, 1 warning in 1.29s`.

Aserción que falla:

```text
assert migradas[-1][0].endswith("ms4_evidencias/alembic.ini")
AssertionError: assert False
```

La ruta real termina en `services\ms4_evidencias\alembic.ini`; la prueba espera
el separador `/`. Es un problema de separador de rutas en Windows, ajeno a este
registro de evidencia. No se modificó la prueba ni el código del migrador.

## Alcance no validado

Con estas ejecuciones **no** se acredita:

- despliegue real en Vercel, Kubero o Neon;
- bases de datos, TLS, roles ni migraciones aplicadas en infraestructura en vivo;
- secretos configurados en los paneles de las plataformas;
- dominio real de CORS en producción;
- rotación de JWT fuera del ambiente aislado de pruebas;
- carga de datos de demostración ni matriz de conexiones de la evidencia
  histórica;
- suite completa del backend (solo se ejecutaron los conjuntos listados).

## Conclusión

Queda registrada una validación local sobre `DerisA`: 104 pruebas aprobadas en
los conjuntos ejecutados y 1 fallo conocido por el separador de rutas en
Windows, reproducido de forma aislada, además de la comprobación de sintaxis de
tres scripts. No constituye evidencia de despliegue en producción.
