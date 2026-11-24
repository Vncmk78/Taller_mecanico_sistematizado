#!/usr/bin/env bash
# Smoke test de contenedores previo al despliegue (SGTM).
#
# Construye las imágenes del backend y de la web desde el código actual (los
# mismos Dockerfile que publica el workflow), levanta en Docker local la
# topología de Kubero (PostgreSQL + migraciones + MinIO + MS1-MS4 + Gateway +
# web) y la verifica de punta a punta. Detalle: docs/10-smoke-test-contenedores.md
#
# Uso (desde backend/, en Git Bash o Linux/macOS, con Docker Desktop abierto):
#   bash scripts/smoke_contenedores.sh            # construye, levanta y verifica
#   bash scripts/smoke_contenedores.sh --bajar    # igual y al final apaga los contenedores
#
# Sale con 0 si todo pasa y con 1 si algo falla. No imprime claves.
set -uo pipefail

cd "$(dirname "$0")/.."
BAJAR=0
[[ "${1:-}" == "--bajar" ]] && BAJAR=1

ENV_FILE="despliegue/.env.despliegue"
GATEWAY="http://127.0.0.1:${SMOKE_GATEWAY_PUERTO:-8080}"
WEB="http://127.0.0.1:${SMOKE_WEB_PUERTO:-8081}"
PY="${PYTHON:-python}"
compose() {
  docker compose -f despliegue/compose.bd.yml -f despliegue/compose.smoke.yml \
    --env-file "$ENV_FILE" "$@"
}

FALLOS=0
paso() { printf '\n==> %s\n' "$*"; }
ok() { printf '  [ OK ] %s\n' "$*"; }
falla() { printf '  [FALLA] %s\n' "$*"; FALLOS=$((FALLOS + 1)); }
codigo() { curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$1"; }

paso "0. Requisitos"
docker info >/dev/null 2>&1 && ok "Docker responde" || { falla "Docker no responde: abre Docker Desktop"; exit 1; }
if [[ ! -f "$ENV_FILE" ]]; then
  "$PY" scripts/inicializar_bd.py configurar || { falla "No se pudo crear $ENV_FILE"; exit 1; }
fi
ok "Configuración en $ENV_FILE (claves aleatorias, fuera de Git)"

paso "1. Construir imágenes (backend y web)"
INICIO=$(date +%s)
if compose build migraciones web; then
  ok "Imágenes construidas en $(( $(date +%s) - INICIO )) s: sgtm-backend:despliegue, sgtm-web:despliegue"
else
  falla "Falló la construcción de imágenes"; exit 1
fi

paso "2. Levantar la topología"
compose up -d || { falla "docker compose up falló"; compose ps -a; exit 1; }

paso "3. Esperar healthchecks (máx. 180 s)"
for i in $(seq 1 36); do
  ESTADOS=$(docker inspect -f '{{.Name}} {{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
    sgtm_smoke_ms1 sgtm_smoke_ms2 sgtm_smoke_ms3 sgtm_smoke_ms4 sgtm_smoke_gateway sgtm_smoke_web 2>/dev/null)
  if [[ $(grep -c ' healthy$' <<<"$ESTADOS") -eq 6 ]]; then break; fi
  if grep -q -E ' (unhealthy|exited)$' <<<"$ESTADOS"; then break; fi
  sleep 5
done
while read -r nombre estado; do
  [[ -z "$nombre" ]] && continue
  [[ "$estado" == "healthy" ]] && ok "${nombre#/}: healthy" || falla "${nombre#/}: ${estado:-no creado}"
done <<<"$ESTADOS"
MIG=$(docker inspect -f '{{.State.ExitCode}}' sgtm_despliegue_migraciones 2>/dev/null || echo "?")
[[ "$MIG" == "0" ]] && ok "migraciones: terminó con 0 (MS1 -> MS4)" || falla "migraciones: código $MIG"

paso "4. Salud de punta a punta (verificar_salud.py)"
"$PY" scripts/verificar_salud.py --base "$GATEWAY" --json salidas-integracion/smoke-contenedores.json \
  && ok "Gateway + 4 bases + MinIO: 6/6" || falla "verificar_salud.py reportó fallas"

paso "5. Web (Nginx) y proxy /api"
[[ $(codigo "$WEB/") == "200" ]] && ok "GET / de la web: 200" || falla "GET / de la web"
[[ $(codigo "$WEB/healthz") == "200" ]] && ok "GET /healthz: 200" || falla "GET /healthz"
[[ $(codigo "$WEB/api/health/servicios") == "200" ]] && ok "GET /api/health/servicios vía Nginx: 200" || falla "proxy /api de la web"

paso "6. Enrutamiento por prefijos (smoke_prefijos_gateway.py)"
"$PY" scripts/smoke_prefijos_gateway.py --gateway "$GATEWAY" --json salidas-integracion/smoke-prefijos.json >/dev/null \
  && ok "Todos los prefijos /api/* llegan a su microservicio" || falla "smoke_prefijos_gateway.py reportó fallas (ver salidas-integracion/smoke-prefijos.json)"

paso "Estado de los contenedores"
compose ps --format 'table {{.Name}}\t{{.Status}}'

if [[ $BAJAR -eq 1 ]]; then
  paso "Apagando contenedores (la base se conserva)"
  compose down
fi

echo
if [[ $FALLOS -eq 0 ]]; then
  echo "SMOKE TEST OK: listo para hacer push a main."
  exit 0
fi
echo "SMOKE TEST CON $FALLOS FALLA(S): no desplegar. Logs: docker compose -f despliegue/compose.bd.yml -f despliegue/compose.smoke.yml --env-file $ENV_FILE logs <servicio>"
exit 1
