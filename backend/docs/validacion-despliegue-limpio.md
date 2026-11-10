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

## Contenedor de migraciones: validación completada en macOS

El pendiente de construir y ejecutar la imagen real quedó cerrado el
**9 de noviembre de 2026**, sobre `MartinH` (base `83b75de`), con Docker Desktop
y arquitectura **ARM64**. La validación inicial descrita arriba usó el script
desde el equipo; esta comprobación adicional ejecutó el `CMD` del Dockerfile:
`scripts/iniciar_servicio.py` → `SGTM_SERVICIO=migraciones` → `inicializar_bd.py`.

Se usó el Compose existente con una sobreescritura local que asigna nombres
únicos a contenedores, volumen, red e imagen, y un puerto libre en `127.0.0.1`.
**Cambiar solo `-p` no basta para aislar este Compose:** sus nombres de
contenedores, volumen y red están fijados explícitamente. Se comprobó que los
recursos nuevos no existieran antes y se generaron credenciales privadas nuevas.
Las bases de desarrollo, pruebas, demostración y despliegue existentes no se usaron.

| Comprobación adicional | Resultado |
|---|---|
| `docker compose ... build migraciones` | Código 0, 27,9 s; dependencias descargadas dentro de `docker build` |
| Ejecución de la imagen sin red para inspección | UID 10001; sin `.env`, `.git`, `.pruebas`, `.demo-final` ni el archivo privado del correo |
| PostgreSQL nuevo | Sano en 6,1 s; cuatro bases sin tablas antes de migrar y cuatro roles propios sin superusuario, createdb, createrole ni bypassrls |
| Matriz de conexiones | 4 conexiones propias aceptadas y las 12 conexiones cruzadas rechazadas |
| `docker compose ... run --rm --no-deps migraciones` | Código 0, 2,1 s; aplica las 38 revisiones desde cero en orden MS1 → MS4 |
| Segunda ejecución del mismo contenedor | Código 0, 1,7 s; 0 revisiones nuevas; columnas, índices, cantidades de filas y revisiones idénticos |
| `docker compose ... run --rm --no-deps migraciones python scripts/inicializar_bd.py verificar` | Código 0, 1,6 s; cuatro heads correctos y tablas de los modelos presentes |
| Limpieza del proyecto propio | Contenedores, volumen y red descartables eliminados; etiqueta de imagen propia retirada; todos los contenedores anteriores conservados |

Las ejecuciones terminaron con:

```text
MS1: OK | BD: 0008_contexto_avisos_ms1
MS2: OK | BD: 0014_nueva_atencion_ms2
MS3: OK | BD: 0011_avisos_ms3
MS4: OK | BD: 0001_ms4
Base de datos lista: las cuatro bases coinciden con el código.
```

También pasaron **42 pruebas** de `tests/test_inicializar_bd.py` y
`tests/test_scripts_despliegue.py` (2 avisos de deprecación de dependencias).
Se agregó `.pruebas` y `.demo-final` a `.dockerignore` para excluir las carpetas
privadas del contexto de construcción, además de las copias explícitas del
Dockerfile. No se modificaron migraciones ni lógica de negocio. Esta ejecución
no repite la carga de escenarios ni acredita un despliegue público o en AMD64.

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
