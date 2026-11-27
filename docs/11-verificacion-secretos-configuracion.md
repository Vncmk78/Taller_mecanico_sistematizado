# 11 — Verificación de secretos y configuración por ambiente

Semana 11 · Verificar secretos y configuración por ambiente.

El estudio previo está en
[`backend/docs/estudio-secretos-cors-configuracion-por-ambiente.md`](../backend/docs/estudio-secretos-cors-configuracion-por-ambiente.md)
y la lista de variables por app en [03 — Variables de entorno](03-variables-entorno.md).
Este documento deja **cómo se verifica** que eso se cumpla y el resultado del
24-11-2026.

## Ambientes

| Ambiente | De dónde salen las variables | Qué se acepta |
| --- | --- | --- |
| Local | `backend/.env` (copia de `.env.example`) | Valores de plantilla, `localhost`, MinIO con clave por defecto |
| Pruebas | `backend/.env.pruebas` (`scripts/ambiente_pruebas.py`) | Igual que local, con bases propias |
| Smoke de contenedores | `backend/despliegue/.env.despliegue` (claves aleatorias de `inicializar_bd.py`) | Claves reales pero desechables |
| Kubero (público) | Variables de cada app en el panel | Nada de plantilla, nada de `localhost`, CORS solo HTTPS |

Ningún archivo de entorno real se versiona; `.gitignore` cubre `.env`,
`.env.pruebas`, `.env.despliegue` y `.env.*.local`.

## Script

`backend/scripts/verificar_config_ambiente.py` (solo biblioteca estándar).
Nunca imprime un valor: solo dice si está, si coincide y si cumple el largo.

```bash
cd backend
# 1. Repositorio público: .env versionados, credenciales reales, .gitignore
python scripts/verificar_config_ambiente.py --repo

# 2. Ambiente local
python scripts/verificar_config_ambiente.py --ambiente local --archivo .env

# 3. Kubero: copiar las variables de cada app del panel a .env.<app>.kubero.local
python scripts/verificar_config_ambiente.py --ambiente kubero \
  --archivo gateway=.env.gateway.kubero.local \
  --archivo .env.ms1.kubero.local --archivo .env.ms2.kubero.local \
  --archivo .env.ms3.kubero.local --archivo .env.ms4.kubero.local
# borrar los .env.*.kubero.local al terminar
```

Sale con 1 si hay alguna FALLA, así sirve como paso previo a un push a `main`.

### Qué revisa

| Regla | Local | Kubero |
| --- | --- | --- |
| `MSn_JWT_SECRET_KEY` presente en MS1–MS4, ≥ 32 caracteres e idéntico (HS256) | Falla | Falla |
| Algoritmo JWT = `HS256` | Falla | Falla |
| Pares MS1↔MS2, MS1↔MS3 y consulta de destinatario: ambos lados definidos, iguales, ≥ 32 y distintos al JWT | Falla (plantilla = aviso) | Falla |
| Worker de eventos activo sin su secreto (MS2, MS3) | Falla | Falla |
| Valores de plantilla (`reemplaza…`, `cambia-esta…`, `<SECRETO>`) | Aviso | Falla |
| Cuatro `DATABASE_URL` distintas, esquema `postgresql+psycopg` | Falla | Falla |
| Clave de base débil (`taller`, `postgres`, < 12 caracteres) o host `localhost` | — | Falla |
| URLs entre servicios (`*_URL`, `*_ENDPOINT`, `GATEWAY_UPSTREAM`) con `localhost` | — | Falla |
| CORS: sin `*`; en Kubero solo `https://`, sin `localhost` y `GATEWAY_CORS_ORIGIN_REGEX` vacío | Falla si `*` | Falla |
| `MS4_S3_SECRET_KEY` distinta al valor por defecto del código (`config.py`) | Aviso | Falla |
| `MS4_S3_PUBLIC_ENDPOINT` con HTTPS y distinto al endpoint interno | — | Falla / aviso |
| La app `gateway` no recibe JWT, DSN ni secretos de servicio | — | Falla |
| Repo: sin `.env` versionado, sin tokens de GitHub, llaves AWS, llaves privadas, JWT emitidos, claves Neon ni DSN con clave real | Falla (código legado = aviso) | — |

Pruebas: `backend/tests/test_verificar_config_ambiente.py` (23 casos, uno por
regla, más uno que confirma que el reporte nunca contiene los secretos).

```bash
python -m pytest tests/test_verificar_config_ambiente.py -q
```

## Resultado 24-11-2026

### Repositorio

```text
==> Repositorio
  [ OK  ] Ningún .env versionado (solo plantillas .example)
  [AVISO] Clave de desarrollo en código legado sin desplegar: presupuestos-service/.env.example (DSN con clave)
  [AVISO] Clave de desarrollo en código legado sin desplegar: presupuestos-service/docker-compose.yml (DSN con clave)
  [ OK  ] .gitignore cubre .env, .env.pruebas, .env.despliegue y .env.*.local

Resultado: 0 falla(s), 2 aviso(s).
```

Además se revisó el historial de **todas las ramas** (`git log --all -p`) buscando
tokens de GitHub, llaves AWS, llaves privadas y claves de Neon: sin resultados.
Los únicos `.env` que alguna vez se agregaron son plantillas `.example`.

Los dos avisos son de `presupuestos-service/`, que no se despliega
([08](08-pendientes-y-deuda.md)); la clave es de un PostgreSQL de desarrollo en
`localhost` / compose y no existe en Kubero.

### Plantilla `backend/.env.example`

0 fallas, 7 avisos (los esperados: valores de plantilla, correo apagado y clave
por defecto de MinIO). Confirma que la plantilla no trae nada que sirva en
producción.

### Ambiente público (lado del cliente)

Revisado desde el navegador contra los dominios públicos
(detalle en [12](12-endpoints-y-evidencia-despliegue.md)):

- Todo el tráfico va por HTTPS y la Gateway responde con
  `Strict-Transport-Security: max-age=31536000; includeSubDomains`.
- El bundle de la web (`/assets/index-*.js`) no contiene `SECRET`, `PASSWORD`,
  `ghp_` ni `AKIA` y usa `VITE_API_URL=/api` relativo: el frontend no recibe
  credenciales.
- `https://tallerconnect.inf.uct.cl/.env` responde el `index.html` de la SPA, no
  un archivo de entorno.
- `/openapi.json` no expone variables ni valores de configuración.

### Variables del panel de Kubero

Las variables reales no salen del panel (el repo es público), así que esta
parte la corre el responsable del panel con el comando 3. La configuración
documentada en [03](03-variables-entorno.md) pasa todas las reglas (es el caso
`test_configuracion_de_kubero_correcta_no_tiene_fallas`).

## Hallazgos

| # | Hallazgo | Severidad | Acción |
| --- | --- | --- | --- |
| S1 | `MS4_S3_ACCESS_KEY` / `MS4_S3_SECRET_KEY` tienen valor por defecto en `ms4_evidencias/config.py`; si en Kubero faltara la variable, MS4 arrancaría con `cambia-esta-clave-ms4` sin avisar | Media | El script lo marca como FALLA en Kubero. Pendiente S12: quitar el default o exigirlo fuera de local |
| S2 | Nginx muestra su versión en las páginas de error (`nginx/1.30.8`) | Baja | `server_tokens off;` en la config de la web |
| S3 | Clave de PostgreSQL de desarrollo versionada en `presupuestos-service/` | Baja | Código legado; se resuelve al decidir qué hacer con esa carpeta |
