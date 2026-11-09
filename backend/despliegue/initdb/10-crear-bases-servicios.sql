-- Se ejecuta UNA vez, cuando el volumen de PostgreSQL está vacío
-- (docker-entrypoint-initdb.d). Crea, por microservicio:
--   * un rol de aplicación sin privilegios de administración (sgtm_msN);
--   * una base propia (sgtm_msN) de la que ese rol es DUEÑO;
--   * sin acceso para PUBLIC: ningún rol de servicio entra a la base de otro.
-- Las claves NO están en este archivo: se leen del entorno del contenedor con
-- \getenv y se escapan con format(%L). La marca SGTM_BD_MARCA queda como
-- comentario de cada base; datos_demo.py solo escribe en bases marcadas
-- "sgtm-despliegue-demo".
\set ON_ERROR_STOP on

\getenv clave_ms1 SGTM_MS1_BD_CLAVE
\getenv clave_ms2 SGTM_MS2_BD_CLAVE
\getenv clave_ms3 SGTM_MS3_BD_CLAVE
\getenv clave_ms4 SGTM_MS4_BD_CLAVE
\getenv marca SGTM_BD_MARCA

CREATE TEMP TABLE sgtm_servicios(rol text, clave text) ON COMMIT PRESERVE ROWS;
INSERT INTO sgtm_servicios VALUES
  ('sgtm_ms1', :'clave_ms1'),
  ('sgtm_ms2', :'clave_ms2'),
  ('sgtm_ms3', :'clave_ms3'),
  ('sgtm_ms4', :'clave_ms4');

-- Rechaza claves cortas antes de crear nada.
SELECT format(
  'DO $v$ BEGIN RAISE EXCEPTION %L; END $v$',
  'Clave de ' || rol || ' ausente o con menos de 16 caracteres')
FROM sgtm_servicios WHERE length(coalesce(clave, '')) < 16
\gexec

SELECT format(
  'CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION '
  'NOBYPASSRLS CONNECTION LIMIT 40 PASSWORD %L', rol, clave)
FROM sgtm_servicios ORDER BY rol
\gexec

SELECT format(
  'CREATE DATABASE %I OWNER %I ENCODING %L TEMPLATE template0', rol, rol, 'UTF8')
FROM sgtm_servicios ORDER BY rol
\gexec

SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', rol)
FROM sgtm_servicios ORDER BY rol
\gexec

SELECT format('COMMENT ON DATABASE %I IS %L', rol, coalesce(:'marca', 'sgtm-despliegue'))
FROM sgtm_servicios ORDER BY rol
\gexec

DROP TABLE sgtm_servicios;
