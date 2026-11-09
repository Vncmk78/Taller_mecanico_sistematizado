# Validación: despliegue limpio de la base de datos desde cero

Fecha: 2026-11-09 · Rama `MartinL` (con `Develop` integrado, base `112e54a`) ·
PostgreSQL 16.15 (imagen `postgres:16`) · Docker Engine 29 · Python 3.13.

Objetivo: comprobar que, partiendo de **nada** (sin contenedor ni volumen), el
procedimiento de `despliegue-base-datos.md` deja las cuatro bases creadas,
aisladas, migradas, con datos controlados y lista para los servicios, y que se
puede limpiar y repetir con el mismo resultado.

## Resultado

| # | Paso | Resultado |
|---|---|---|
| 0 | `down --volumes` del proyecto `sgtm_despliegue` | Volumen eliminado (0 restantes) |
| 1 | `up -d --wait postgres` (initdb) | Sano en 5,8 s. 4 roles, 4 bases, 4 `REVOKE`, 4 marcas |
| 2 | Dos `inicializar_bd.py` **a la vez** sobre bases vacías | Ambos con código 0 en 2,2 s. Uno aplicó las 38 revisiones; el otro esperó el candado y no aplicó ninguna |
| 3 | `inicializar_bd.py verificar` | MS1 `0008_contexto_avisos_ms1`, MS2 `0014_nueva_atencion_ms2`, MS3 `0011_avisos_ms3`, MS4 `0001_ms4`: OK y todas las tablas de los modelos presentes |
| 4 | Conexión de cada rol a cada base (16 combinaciones) | Solo `sgtm_msN → sgtm_msN`; las 12 cruzadas rechazadas (`no CONNECT privilege`). Roles sin superusuario/createdb/createrole; claves en SCRAM-SHA-256 |
| 5 | MS1–MS4 + Gateway sobre las bases nuevas | `/api/health/servicios`: los cuatro `ok` |
| 6 | `datos_demo.py cargar --gateway` | Código 0 en 8,4 s: 7/7 cuentas, 4 perfiles Cliente, 2/2 proveedores, 4/4 repuestos, 9/9 escenarios DEMO (70 llamadas validadas contra el contrato 3.0.0) |
| 7 | `POST /api/auth/login` con `administrador@pruebas.cl` | HTTP 200 |
| 8 | `datos_demo.py reiniciar` y comparación | Código 0. Órdenes antes y después **idénticas**: `DEMO01:1:1 DEMO02:2:2 DEMO03:3:3 DEMO04:4:5 DEMO05:5:6 DEMO06:6:7 DEMO07:7:8 DEMO08:8:8` (patente:orden:estado) |
| 9 | Protecciones | Base sin marca de demo → `limpiar` rechazado sin escribir; `reiniciar` sin `--confirmar` rechazado; DSN `taller:taller` rechazado en el paso 1 |
| 10 | initdb con una clave de 5 caracteres | Detenido: `Clave de sgtm_ms2 ausente o con menos de 16 caracteres`; nunca queda sano |

Comprobaciones adicionales:

- Re-ejecutar `inicializar_bd.py` sobre bases al día: código 0, sin cambios.
- Base caída (puerto sin servidor) con `--espera 3`: código 1, mensaje
  `sin respuesta después de 3 s: MS4 (127.0.0.1:5999/sgtm_ms4: OperationalError)`,
  sin mostrar la clave.
- Dos servicios con la misma base, `--exigir-tls` sin `sslmode`: rechazados en el paso 1.
- Después de `limpiar`: tablas vacías, pero se conservan los datos de referencia
  de las migraciones (`rol`: cliente, mecanico, administrador; 8 estados de
  orden) y las extensiones `pg_trgm` y `unaccent`.
- Suite completa del backend: **2186 pruebas aprobadas, 600 omitidas** (las que
  requieren infraestructura externa), incluidas las 10 nuevas de
  `tests/test_inicializar_bd.py`.

## Pendiente de ejecutar en un equipo del grupo

El contenedor `migraciones` (`docker compose ... run --rm --build migraciones`)
no se pudo construir en el entorno de validación porque ese entorno no permite
que `pip` descargue paquetes dentro de `docker build`. El contenedor ejecuta
exactamente el mismo `scripts/inicializar_bd.py` (vía
`SGTM_SERVICIO=migraciones`), que sí se validó desde el equipo con las mismas
bases. Para cerrarlo, en Docker Desktop:

```bash
docker compose -f despliegue/compose.bd.yml --env-file despliegue/.env.despliegue down --volumes
docker compose -f despliegue/compose.bd.yml --env-file despliegue/.env.despliegue up -d --wait postgres
docker compose -f despliegue/compose.bd.yml --env-file despliegue/.env.despliegue run --rm --build migraciones
```

Resultado esperado: la última línea es
`Base de datos lista: las cuatro bases coinciden con el código.` y código 0.

## Cómo repetir esta validación

```bash
cd backend
python scripts/inicializar_bd.py configurar
docker compose -f despliegue/compose.bd.yml --env-file despliegue/.env.despliegue down --volumes
docker compose -f despliegue/compose.bd.yml --env-file despliegue/.env.despliegue up -d --wait postgres
export SGTM_ENV_FILE=despliegue/.env.despliegue
python scripts/inicializar_bd.py
python scripts/inicializar_bd.py verificar
# levantar MS1–MS4 y la Gateway con SGTM_ENV_FILE=despliegue/.env.despliegue
python scripts/datos_demo.py cargar --gateway http://127.0.0.1:8000
python scripts/datos_demo.py reiniciar --confirmar LIMPIAR-DEMO --gateway http://127.0.0.1:8000
python scripts/datos_demo.py verificar --escenarios
```
