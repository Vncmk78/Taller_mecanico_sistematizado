# Estudio: PostgreSQL en Docker, variables de entorno y manejo de credenciales

Semana 10 · Base de datos para el ambiente de despliegue. Este estudio justifica
las decisiones de `despliegue/compose.bd.yml`, `despliegue/initdb/` y
`scripts/inicializar_bd.py`.

## 1. Cómo inicializa la imagen oficial `postgres`

| Variable | Qué hace | Uso en SGTM |
|---|---|---|
| `POSTGRES_PASSWORD` | Clave del superusuario. Obligatoria salvo `POSTGRES_HOST_AUTH_METHOD=trust`. | Clave aleatoria en `.env.despliegue`; solo para crear roles y bases. |
| `POSTGRES_USER` | Nombre del superusuario (por defecto `postgres`). | `sgtm_admin`: ningún microservicio lo usa. |
| `POSTGRES_DB` | Base creada al inicio (por defecto = `POSTGRES_USER`). | `postgres`; las bases de servicio las crea initdb. |
| `POSTGRES_INITDB_ARGS` | Argumentos extra de `initdb`. | `--auth-host=scram-sha-256 --data-checksums`. |
| `POSTGRES_HOST_AUTH_METHOD` | Método de autenticación para conexiones remotas. | No se define: **nunca** `trust`. |
| `PGDATA` | Carpeta de datos dentro del contenedor. | Por defecto, montada en el volumen `sgtm_despliegue_pg`. |
| `*_FILE` | Variantes que leen el valor desde un archivo (Docker secrets). | Ver §4: alternativa evaluada. |

Reglas que importan para no equivocarse:

1. **`/docker-entrypoint-initdb.d` solo se ejecuta con el volumen vacío.** Cambiar
   una clave en `.env` después no cambia la clave guardada en el volumen. Para
   aplicarla hay que hacer `ALTER ROLE ... PASSWORD` o reconstruir el volumen.
2. Los archivos se ejecutan en orden alfabético: `*.sql` con `psql`, `*.sh`
   ejecutables como proceso y `*.sh` no ejecutables con `source`. Si un script
   falla, el contenedor se detiene y la base queda a medio crear: hay que borrar
   el volumen y repetir.
3. Las variables de entorno quedan visibles con `docker inspect` para quien
   tenga acceso al demonio Docker. Son adecuadas para un equipo de desarrollo o
   un orquestador que las inyecta desde su almacén de secretos (Kubero/Kubernetes),
   no para dejarlas escritas en archivos versionados.
4. Archivos editados en Windows pueden quedar con fin de línea CRLF y romper los
   scripts de initdb. `despliegue/.gitattributes` fuerza `eol=lf`.

## 2. Una base y un rol por microservicio

La sistematización (§1.2 y §8) exige una base independiente por servicio. Con
un solo usuario para todo, cualquier servicio comprometido puede leer o borrar
las bases de los demás. Por eso `initdb/10-crear-bases-servicios.sql` crea:

- `sgtm_ms1..4`: roles `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
  NOBYPASSRLS`, con límite de 40 conexiones.
- Bases `sgtm_ms1..4`, **cuyo dueño es el rol del mismo servicio**. Ser dueño
  permite crear tablas en `public` (PostgreSQL 15+ ya no lo concede a PUBLIC) y
  crear las extensiones *trusted* `pg_trgm` y `unaccent` que usa MS3, sin
  superusuario.
- `REVOKE ALL ON DATABASE ... FROM PUBLIC`: un rol de servicio no puede ni
  conectarse a la base de otro (validado en `validacion-despliegue-limpio.md`).

Las claves se guardan como hash `SCRAM-SHA-256` (por defecto desde PostgreSQL
14). El script valida que tengan al menos 16 caracteres antes de crear nada.

## 3. Variables de entorno de la aplicación

Cada servicio lee solo `MSn_DATABASE_URL` (prefijo propio, `shared/config.py`).
Formato: `postgresql+psycopg://ROL:CLAVE@HOST:PUERTO/BASE[?sslmode=...]`.

- La clave va dentro de una URL: si tiene `@ : / ? #` hay que codificarla.
  `inicializar_bd.py configurar` genera claves con `secrets.token_urlsafe`
  (solo `A-Z a-z 0-9 - _`), que no requieren codificación.
- Dentro de la red Compose el host es `postgres`; desde el equipo es
  `127.0.0.1:5460`. Nunca `localhost` dentro de un pod.
- Fuera de la red local, exigir TLS: `?sslmode=require` (o `verify-full` si el
  proveedor entrega la CA). `inicializar_bd.py --exigir-tls` lo valida.
- `SGTM_ENV_FILE` elige el archivo (`.env`, `.env.pruebas`,
  `despliegue/.env.despliegue`); las variables del proceso siempre tienen
  prioridad, que es como Kubero las inyecta.

## 4. Dónde viven las credenciales

| Opción | Ventaja | Riesgo | Decisión |
|---|---|---|---|
| Escritas en `docker-compose.yml` (`taller/taller`) | Cero configuración | Quedan en Git; todos los equipos comparten la clave | Solo el compose local histórico de desarrollo. |
| Archivo `.env` ignorado por Git | Simple; Compose lo interpola | Puede copiarse por error; visible en `docker inspect` | **Elegido** para el ambiente de despliegue local (`.env.despliegue`, permisos 600, generado). |
| Docker secrets (`POSTGRES_PASSWORD_FILE`) | No aparece en `docker inspect` | La app necesitaría leer `*_FILE` para armar su URL | Evaluado; no aporta en Kubero, que ya monta secretos como variables. |
| Variables/secretos del orquestador (Kubero, Neon) | Fuera del código, con control de acceso | Requiere acceso al panel | **Elegido** para el despliegue real. |

Reglas acordadas:

1. Ninguna clave en Git, ni siquiera de ejemplo con valor real. Las plantillas
   usan `__GENERAR__`.
2. Los scripts nunca imprimen DSN ni claves: ante un error muestran solo el tipo
   de excepción y `host:puerto/base`.
3. El superusuario no se entrega a los servicios. `inicializar_bd.py` rechaza en
   el perfil `despliegue` los roles `postgres`/`taller` y claves de ejemplo.
4. Rotación: `ALTER ROLE sgtm_msN PASSWORD '...'` con el superusuario,
   actualizar `MSn_DATABASE_URL` en el orquestador y reiniciar solo ese servicio.
5. El puerto se publica en `127.0.0.1`, no en `0.0.0.0`.

## 5. Otras decisiones

- **Imagen:** `postgres:16`, la misma mayor que usan los otros ambientes y
  GitHub Actions. Para un despliegue estable conviene fijar el digest
  (`postgres:16@sha256:...`), como ya se hace con MinIO.
- **Salud:** el healthcheck consulta `sgtm_ms4` (la última base creada), no solo
  el servidor: así `depends_on: service_healthy` no deja migrar con initdb a medias.
- **Migraciones concurrentes:** si dos réplicas o dos personas migran a la vez,
  Alembic puede chocar. `inicializar_bd.py` toma un candado consultivo
  (`pg_try_advisory_lock`) por base antes de migrar.
- **Arranque de la app:** las imágenes no migran al iniciar (ya documentado en
  el README). La migración es un paso explícito: `SGTM_SERVICIO=migraciones`.

## Fuentes

- [Imagen oficial postgres en Docker Hub (variables, initdb, `*_FILE`)](https://hub.docker.com/_/postgres)
- [PostgreSQL 16: CREATE ROLE](https://www.postgresql.org/docs/16/sql-createrole.html)
- [PostgreSQL 16: autenticación SCRAM](https://www.postgresql.org/docs/16/auth-password.html)
- [PostgreSQL 15: cambio de permisos sobre el esquema public](https://www.postgresql.org/docs/release/15.0/)
- [PostgreSQL 16: funciones de candados consultivos](https://www.postgresql.org/docs/16/functions-admin.html#FUNCTIONS-ADVISORY-LOCKS)
