# Ambiente de pruebas separado (`sgtm_pruebas`)

Ambiente local nuevo para validar los recorridos con datos sintéticos
reproducibles. Corre **al lado** del ambiente local existente
(`docker-compose.yml` + `.env`), que no se lee, no se modifica y no se borra.

## Qué tiene propio

| Recurso | Ambiente existente | Ambiente de pruebas |
|---|---|---|
| Proyecto Compose | `backend` (por carpeta) | `sgtm_pruebas` (`name:` fijo) |
| Archivo Compose | `docker-compose.yml` | `docker-compose.pruebas.yml` |
| Configuración | `.env` | `.env.pruebas` (generado, ignorado por Git) |
| Contenedores | `sgtm_db_ms1..4`, `sgtm_minio` | `sgtm_pruebas_db_ms1..4`, `sgtm_pruebas_minio` |
| PostgreSQL | 5433–5436, `taller_ms1..4` | 127.0.0.1:5443–5446, `taller_ms1..4_pruebas` |
| Volúmenes | `pg_ms1..4`, `minio_data` | `sgtm_pruebas_pg_ms1..4`, `sgtm_pruebas_minio` |
| Red | por defecto del proyecto | `sgtm_pruebas_red` |
| MinIO | 9000/9001, bucket `evidencias` | 127.0.0.1:9010/9011, bucket `evidencias-pruebas` |
| Gateway / MS1–MS4 | 8000 / 8001–8004 | 127.0.0.1:8100 / 8101–8104 |
| Frontend | 5173 | 127.0.0.1:5183 (Vite con `SGTM_GATEWAY_URL`) |
| Secretos JWT y de eventos | los de `.env` | propios: los tokens de un ambiente no sirven en el otro |

## Cómo se garantiza el aislamiento

- **Configuración efectiva.** Los servicios y scripts leen el archivo indicado en
  `SGTM_ENV_FILE` (por defecto `.env`, sin cambios para el ambiente existente).
  `scripts/ambiente_pruebas.py` lanza cada proceso con `SGTM_ENV_FILE` apuntando
  a `.env.pruebas`, exporta todas sus variables (tienen prioridad sobre cualquier
  archivo) y descarta las variables de servicio heredadas de la terminal.
- **Verificación de la configuración** (antes de cualquier acción): bases en
  5443–5446 con sufijo `_pruebas`, URLs de servicio en 8101–8104, MinIO en 9010
  con bucket `evidencias-pruebas`, CORS solo para 5183, secretos distintos de los
  de `.env`. Además carga la configuración real de los cinco servicios en un
  proceso aparte y rechaza cualquier valor —incluidos los valores por defecto del
  código, como `localhost:8002`— que apunte a un puerto del ambiente existente.
- **Verificación del destino** (antes de migrar, cargar datos o iniciar): se
  conecta a cada base y exige la marca `sgtm-ambiente-pruebas`, que pone
  `pruebas/initdb/01-marcar-ambiente.sh` solo al crear los volúmenes nuevos; y
  exige la etiqueta `ambiente=sgtm-pruebas` en el bucket. Las bases y el bucket
  del ambiente existente no tienen esas marcas, así que nunca pasan.
- **Compose** se invoca siempre con
  `-p sgtm_pruebas -f docker-compose.pruebas.yml --env-file .env.pruebas`; las
  credenciales no tienen valores por defecto (si falta una, Compose se detiene).
- No se muestran credenciales: los mensajes indican solo host, puerto y base.

## Primera vez

Desde `backend/`, con el entorno virtual del backend y Docker Desktop abiertos
(en macOS: `.venv/bin/python`):

```bash
python scripts/ambiente_pruebas.py configurar          # crea .env.pruebas con secretos propios
python scripts/ambiente_pruebas.py verificar           # revisa la configuración (sin conectar)
python scripts/ambiente_pruebas.py infra               # PostgreSQL x4 + MinIO + bucket del ambiente
python scripts/ambiente_pruebas.py verificar --destino # marcas de las 4 bases y del bucket
python scripts/ambiente_pruebas.py migrar              # alembic desde cero en las 4 bases
python scripts/ambiente_pruebas.py iniciar             # MS1–MS4, Gateway y frontend
python scripts/ambiente_pruebas.py sembrar             # usuarios, catálogo y escenarios DEMO
```

Abrir <http://127.0.0.1:5183>. Cuentas: las de `scripts/seed_usuarios_prueba.py`
(por ejemplo `administrador@pruebas.cl` / `AdminPrueba123!`).

## Datos de prueba (reproducibles)

`sembrar` ejecuta, en orden:

1. `seed_usuarios_prueba.py`: 7 cuentas (cada rol y cada combinación) y sus
   perfiles de Cliente en MS2. Idempotente.
2. `seed_datos_ms3.py` (catálogo base: 2 proveedores, 4 repuestos con stock,
   umbral general) con los ids reales del Administrador y Mecánico. **No** usa
   `--integracion`, porque esa carga escribe en MS3 consumos y reservas para
   órdenes que MS2 no tiene.
3. `sembrar_demo_pruebas.py`: solo por la Gateway, con los tokens de las cuentas
   de prueba. Configura cupo diario (60) y capacidad por mecánico (20) si faltan
   y deja estos escenarios del Cliente de prueba:

| Patente | Orden | Cómo se llega |
|---|---|---|
| DEMO01 | Recibido | ingreso y orden sin mecánico |
| DEMO02 | Asignado | + asignación |
| DEMO03 | Esperando aprobación | + presupuesto enviado |
| DEMO04 | En reparación | + aprobación del Cliente |
| DEMO05 | Listo | + Mecánico marca lista |
| DEMO06 | Entregado | + entrega del Administrador |
| DEMO07 | Cancelado | solicitud del Cliente confirmada por el Administrador |
| DEMO08 | Cancelado | rechazo del primer presupuesto |
| DEMO09 | sin orden | para registrar un ingreso en la demostración |

Sobre un ambiente recién construido produce siempre las mismas órdenes (1–8),
con los mismos estados. Si los escenarios ya existen no hace nada; si existen
solo algunos, se detiene y pide reconstruir.

## Validar los recorridos

```bash
python scripts/ambiente_pruebas.py recorridos --salida recorridos.md
```

Informa por separado:

1. **Recorridos implementados**: `flujos_e2e_gateway.py` (registro y acceso,
   configuración, orden completa hasta la entrega, rechazo, cancelación,
   seguridad), validados contra el contrato congelado.
2. **Problemas conocidos reproducidos** por la API con vehículos nuevos: varias
   órdenes activas por vehículo; la entrega no registra la salida y la orden
   siguiente reutiliza ese ingreso. No cuentan como recorridos funcionales.
3. **Pendientes**: devolución, solicitud de nueva atención, regla de una orden
   activa y registro de salida. Solo se comprueba que no existen; no se simulan.

`recorridos` crea datos nuevos (vehículos `E2E*`, `PVA*`, `PSE*`). Para una
demostración limpia, reconstruir y ejecutar solo `sembrar`.

## Uso diario

```bash
python scripts/ambiente_pruebas.py estado    # procesos y contenedores de sgtm_pruebas
python scripts/ambiente_pruebas.py detener   # detiene procesos y contenedores (conserva datos)
python scripts/ambiente_pruebas.py infra && python scripts/ambiente_pruebas.py iniciar
python scripts/ambiente_pruebas.py ejecutar -- python scripts/flujos_e2e_gateway.py --gateway http://127.0.0.1:8100
```

`ejecutar` corre cualquier comando con la configuración de pruebas, después de
verificar el destino. Los logs quedan en `backend/.pruebas/logs/`.

## Reconstruir desde cero

Elimina **solo** los contenedores y volúmenes del proyecto `sgtm_pruebas`:

```bash
python scripts/ambiente_pruebas.py eliminar --confirmar sgtm_pruebas
python scripts/ambiente_pruebas.py infra
python scripts/ambiente_pruebas.py migrar
python scripts/ambiente_pruebas.py iniciar
python scripts/ambiente_pruebas.py sembrar
```

`eliminar` sin `--confirmar sgtm_pruebas` no hace nada. Internamente ejecuta
`docker compose -p sgtm_pruebas -f docker-compose.pruebas.yml --env-file .env.pruebas down --volumes --remove-orphans`.
Nunca usar `docker compose down -v` sin `-p sgtm_pruebas -f docker-compose.pruebas.yml`:
en `backend/` eso apunta al ambiente existente.

`.env.pruebas` se conserva al reconstruir (sus credenciales son las de los
volúmenes). Si se borra, crear uno nuevo con `configurar` solo después de
`eliminar`.

## Advertencia: pruebas automatizadas y MinIO

`tests/test_ms4_huerfanos.py::test_conciliacion_contra_minio_real` se ejecuta
cuando el MinIO configurado está disponible y llama a la conciliación de
huérfanos con `eliminar=True` sobre **todo el bucket**, comparándolo con una base
de pruebas vacía: borra cualquier objeto que no haya creado la propia prueba.
Mientras no se corrija, no ejecutar `pytest` con el MinIO del ambiente existente
(`docker compose up` de `docker-compose.yml`) encendido, ni con
`SGTM_ENV_FILE=.env.pruebas`.
