#!/bin/sh
# Se ejecuta solo al crear el volumen (base vacía). Marca la base como parte del
# ambiente de pruebas separado: scripts/ambiente_pruebas.py exige esta marca
# antes de migrar, cargar datos o iniciar servicios, y así nunca opera sobre
# las bases del ambiente local existente (que no la tienen).
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "COMMENT ON DATABASE \"$POSTGRES_DB\" IS 'sgtm-ambiente-pruebas'"
