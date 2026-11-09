# Base de datos del ambiente de despliegue: configuración y migraciones

Cómo dejar las cuatro bases de SGTM listas para un despliegue, desde cero, y
cómo aplicar migraciones nuevas después. Fundamentos en
`estudio-postgresql-docker-credenciales.md`; evidencia en
`validacion-despliegue-limpio.md`.

## Piezas

| Archivo | Para qué |
|---|---|
| `despliegue/compose.bd.yml` | PostgreSQL 16 con 4 bases y 4 roles + contenedor `migraciones`. Proyecto `sgtm_despliegue`, puerto `127.0.0.1:5460`. |
| `despliegue/initdb/10-crear-bases-servicios.sql` | Primera ejecución: roles `sgtm_ms1..4`, bases propias, sin acceso cruzado, marca del ambiente. |
| `despliegue/env.despliegue.example` | Plantilla. El archivo real (`.env.despliegue`) se genera y no se versiona. |
| `scripts/inicializar_bd.py` | Valida, espera, revisa permisos, migra MS1 → MS4 con candado y verifica. |
| `scripts/iniciar_servicio.py` | `SGTM_SERVICIO=migraciones` ejecuta lo anterior dentro de la imagen del backend. |
| `scripts/datos_demo.py` | Datos de demostración: ver `datos-demostracion.md`. |

No reemplaza a `docker-compose.yml` (desarrollo) ni a `docker-compose.pruebas.yml`
(pruebas): usa otro proyecto, otro puerto y otro volumen.

## A. Despliegue local completo desde cero (Docker)

Desde `backend/`, con el entorno virtual activo y Docker Desktop abierto:

```bash
python scripts/inicializar_bd.py configurar
docker compose -f despliegue/compose.bd.yml --env-file despliegue/.env.despliegue up -d --wait postgres
docker compose -f despliegue/compose.bd.yml --env-file despliegue/.env.despliegue run --rm --build migraciones
```

Sin construir la imagen, el mismo paso desde el equipo:

```bash
# PowerShell:  $env:SGTM_ENV_FILE = "despliegue/.env.despliegue"
export SGTM_ENV_FILE=despliegue/.env.despliegue
python scripts/inicializar_bd.py
```

Salida esperada (resumida):

```
[1/6] Configuración (perfil despliegue)
[2/6] Conexión (hasta 60 s)
[3/6] Permisos y extensiones
[4/6] Estado previo de las migraciones      MS1..MS4: ATRASADA | BD: sin versión
[5/6] Migraciones en orden MS1 → MS2 → MS3 → MS4
[6/6] Verificación final                    MS1..MS4: OK
Base de datos lista: las cuatro bases coinciden con el código.
```

Para levantar los servicios contra estas bases, usar las cuatro
`MSn_DATABASE_URL` y `MSn_JWT_SECRET_KEY` de `.env.despliegue` (o
`SGTM_ENV_FILE=despliegue/.env.despliegue`).

## B. Despliegue real (Kubero, Neon u otro PostgreSQL administrado)

1. **Crear bases y roles una sola vez** con un usuario administrador del
   proveedor: ejecutar `despliegue/initdb/10-crear-bases-servicios.sql` con
   `psql`, definiendo antes `SGTM_MS1..4_BD_CLAVE` y
   `SGTM_BD_MARCA=sgtm-despliegue` (producción) o `sgtm-despliegue-demo`
   (ambiente de demostración). En Neon, si no se permite crear roles por SQL,
   crear en el panel una base por servicio y un rol dueño de cada una.
2. **Configurar** en cada instancia del orquestador su propia
   `MSn_DATABASE_URL` (`postgresql+psycopg://`, con `?sslmode=require`) y
   `MSn_JWT_SECRET_KEY`.
3. **Migrar antes de publicar la nueva versión**, con una tarea de una sola
   ejecución de la misma imagen:
   `SGTM_SERVICIO=migraciones` + las cuatro `MSn_DATABASE_URL` + las cuatro
   `MSn_JWT_SECRET_KEY` + `SGTM_EXIGIR_TLS=true`. Termina con código 0 si todo
   quedó al día. Desde un equipo: `python scripts/inicializar_bd.py --exigir-tls`.
4. **Recién con código 0**, publicar los servicios.

## Migraciones nuevas (uso diario)

- Cada servicio sigue teniendo su propio `alembic/` (`alembic -c
  services/msN_.../alembic.ini revision ...`).
- Antes de integrar en `Develop`: `python scripts/inicializar_bd.py` contra una
  base nueva (ver A) para comprobar que el historial completo aplica desde cero.
- En el despliegue se ejecuta el paso 3: solo aplica lo que falta.
- `inicializar_bd.py verificar` informa sin escribir (útil antes de una demo).

## Qué revisa y qué responde

| Paso | Falla si… | Código |
|---|---|---|
| 1. Configuración | falta una URL, no es `postgresql+psycopg`, dos servicios comparten base; en perfil `despliegue`: clave de ejemplo/corta o rol `postgres`/`taller`; con `--exigir-tls`: sin `sslmode` seguro | 1 |
| 2. Conexión | alguna base no responde en `--espera` segundos (reintentos con espera creciente) | 1 |
| 3. Permisos | PostgreSQL < 13, el rol no puede crear en `public`, faltan `pg_trgm`/`unaccent` (MS3). Avisa si el rol es superusuario o no es dueño | 1 |
| 4. Estado previo | una base tiene una revisión que no existe en el código (otra rama) | 2 |
| 5. Migración | falla un `upgrade`; los servicios anteriores quedan migrados y se puede reintentar | 2 |
| 6. Verificación | una base no quedó en heads o falta una tabla de los modelos | 2 |

Los pasos 1 a 4 no modifican nada. El orden MS1 → MS4 es fijo y la ejecución es
idempotente: repetirla no cambia una base ya al día. Dos ejecuciones a la vez
no chocan: la segunda espera el candado y encuentra todo aplicado.

Opciones: `--perfil local` (acepta `taller/taller` del compose de desarrollo,
solo avisa), `--exigir-tls`, `--espera N`. También por entorno:
`SGTM_PERFIL_BD`, `SGTM_EXIGIR_TLS=true`, `SGTM_ESPERA_BD_SEGUNDOS`.

## Reconstruir el ambiente local de despliegue

Borra **solo** el proyecto `sgtm_despliegue` (no toca desarrollo ni pruebas):

```bash
docker compose -f despliegue/compose.bd.yml --env-file despliegue/.env.despliegue down --volumes
```

`.env.despliegue` se conserva y sus claves se reutilizan al recrear el volumen.
Si se borra o se cambian claves, hacerlo **después** de `down --volumes`.

## Problemas frecuentes

- **`password authentication failed`** tras cambiar `.env.despliegue`: initdb
  solo corre con el volumen vacío. Reconstruir (arriba) o `ALTER ROLE`.
- **El contenedor nunca queda sano**: `docker logs sgtm_despliegue_postgres`.
  Una clave de menos de 16 caracteres detiene initdb con un mensaje claro.
- **`INCOMPATIBLE`** en el paso 4: la base fue migrada desde otra rama. Cambiar
  a la rama correcta; no se hace `stamp` ni `downgrade` automático.
- **Puerto 5460 ocupado**: cambiar `DESPLIEGUE_PG_PUERTO` y el puerto de las
  cuatro URL en `.env.despliegue`.
