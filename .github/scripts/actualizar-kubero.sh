#!/usr/bin/env bash
set -euo pipefail

# Actualiza las 6 apps Docker de Kubero al tag publicado por el workflow.
# El token se recibe por variable de entorno (secreto de GitHub Actions).
# No modifica minio.

KUBERO_URL="${KUBERO_URL:-https://kubero.inf.uct.cl}"
PIPELINE="${KUBERO_PIPELINE:-tallerconnect}"
PHASE="${KUBERO_PHASE:-production}"
TOKEN="${KUBERO_TOKEN:-}"
REGISTRY="${REGISTRY:-ghcr.io}"
OWNER_LC="${GITHUB_REPOSITORY_OWNER,,}"
SHORT_SHA="${SHORT_SHA:-${GITHUB_SHA::7}}"
TAG="sha-${SHORT_SHA}"
SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/null}"

BACKEND_REPO="${REGISTRY}/${OWNER_LC}/tallerconnect-backend"
FRONTEND_REPO="${REGISTRY}/${OWNER_LC}/tallerconnect-frontend"
SALUD_URL="https://api-tallerconnect.inf.uct.cl/api/health/servicios"
WEB_URL="https://tallerconnect.inf.uct.cl/healthz"

log() { printf '%s\n' "$*"; }
summary() { printf '%s\n' "$*" >> "$SUMMARY"; }

api() {
  local method="$1" path="$2"
  shift 2
  curl --fail-with-body --silent --show-error \
    --connect-timeout 10 --max-time 30 \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Accept: application/json" \
    -X "$method" "$@" "${KUBERO_URL}${path}"
}

if [[ -z "${TOKEN}" ]]; then
  echo "::error::Falta el secreto KUBERO_TOKEN. Crea un token en Kubero > Perfil > API Tokens y guárdalo en GitHub > Settings > Secrets and variables > Actions."
  exit 1
fi

# Las migraciones no corren al arrancar los pods (runbook §5). Si el commit
# trae una migración nueva, publicamos la imagen pero no movemos producción.
MIGRACIONES=""
if git rev-parse --verify -q HEAD^ >/dev/null; then
  MIGRACIONES="$(git diff --name-only --diff-filter=AM HEAD^ HEAD -- \
    ':(glob)backend/services/*/alembic/versions/*.py' || true)"
fi

if [[ -n "${MIGRACIONES}" ]]; then
  summary "## Deploy automático omitido"
  summary "- El commit publicó \`${TAG}\`, pero incluye migraciones nuevas:"
  while IFS= read -r archivo; do
    [[ -n "${archivo}" ]] && summary "  - \`${archivo}\`"
  done <<< "${MIGRACIONES}"
  summary "- Kubero sigue en la versión anterior."
  summary "- Aplica las migraciones (runbook §5) y luego despliega de forma manual (runbook §4.2)."
  echo "::warning::Hay migraciones nuevas; no se actualizó Kubero automáticamente."
  exit 0
fi

# Preflight: Autentica y confirma el pipeline/fase antes de tocar nada.
if ! api GET "/api/apps/${PIPELINE}/${PHASE}/gateway" >/dev/null; then
  echo "::error::No se pudo leer ${PIPELINE}/${PHASE}/gateway en Kubero. Revisa KUBERO_TOKEN (permisos app:read y app:write) y el pipeline/fase configurados."
  exit 1
fi

actualizar_app() {
  local app="$1" repo="$2"
  local base="/api/apps/${PIPELINE}/${PHASE}/${app}"
  local actual rv payload verificacion tag_actual repo_actual

  actual="$(api GET "${base}")"
  rv="$(jq -r '.metadata.resourceVersion // empty' <<< "${actual}")"
  if [[ -z "${rv}" ]]; then
    echo "::error::Kubero no devolvió resourceVersion para ${app}."
    return 1
  fi

  # La API espera el spec de la app; resourceVersion va en la URL.
  payload="$(mktemp)"
  jq --arg repo "${repo}" --arg tag "${TAG}" \
    '.spec | .image.repository = $repo | .image.tag = $tag' <<< "${actual}" > "${payload}"

  if ! api PUT "${base}/${rv}" -H 'Content-Type: application/json' \
    --data-binary "@${payload}" >/dev/null; then
    rm -f "${payload}"
    echo "::error::No se pudo actualizar la imagen de ${app} en Kubero."
    return 1
  fi
  rm -f "${payload}"

  # updateApp() de Kubero silencia errores de Kubernetes: confirmar el cambio.
  verificacion="$(api GET "${base}")"
  tag_actual="$(jq -r '.spec.image.tag // empty' <<< "${verificacion}")"
  repo_actual="$(jq -r '.spec.image.repository // empty' <<< "${verificacion}")"
  if [[ "${tag_actual}" != "${TAG}" || "${repo_actual}" != "${repo}" ]]; then
    echo "::error::Kubero no confirmó ${app}: esperado ${repo}:${TAG}, obtenido ${repo_actual}:${tag_actual}."
    return 1
  fi

  if ! api GET "${base}/restart" >/dev/null; then
    echo "::error::No se pudo solicitar el redeploy de ${app}."
    return 1
  fi

  log "  - ${app} -> ${repo}:${TAG} (redeploy solicitado)"
}

verificar_salud() {
  local respuesta
  for _ in $(seq 1 12); do
    if curl -fsS --max-time 10 "${SALUD_URL}" \
      | jq -e '.status == "ok" and ((.servicios | length) == 4) and ([.servicios[].estado] | all(. == "ok"))' >/dev/null 2>&1; then
      respuesta="$(curl -fsS --max-time 10 "${WEB_URL}" || true)"
      if [[ "${respuesta}" == *ok* ]]; then
        return 0
      fi
    fi
    sleep 10
  done
  return 1
}

summary "## Deploy automático en Kubero"
summary "- Tag: \`${TAG}\`"
summary "- Apps actualizadas: \`gateway\`, \`ms1\`, \`ms2\`, \`ms3\`, \`ms4\`, \`web\`"
summary "- \`minio\` no se modifica."

for app in gateway ms1 ms2 ms3 ms4; do
  actualizar_app "${app}" "${BACKEND_REPO}"
done
actualizar_app web "${FRONTEND_REPO}"

if verificar_salud; then
  summary "- Salud: ✅ \`/api/health/servicios\` y \`/healthz\` en \`ok\`."
  log "Salud verificada en Kubero."
else
  summary "- Salud: ❌ no confirmó \`ok\` dentro del timeout; revisa los logs."
  echo "::error::La salud no confirmó ok tras el deploy; revisa los logs de Kubero."
  exit 1
fi
