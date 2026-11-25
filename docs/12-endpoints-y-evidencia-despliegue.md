# 12 — Endpoints y evidencia básica del despliegue

Semana 11 · Registrar endpoints y evidencia básica del despliegue.

Versión desplegada: `sha-ee84ed4` (ver [07 §19](07-pruebas-realizadas.md)).
Registro: 24-11-2026, 21:13 (America/Santiago).

## Endpoints públicos

| Componente | URL | Uso |
| --- | --- | --- |
| Web | <https://tallerconnect.inf.uct.cl> | Clientes, mecánicos y administrador |
| Web → Gateway | `https://tallerconnect.inf.uct.cl/api/*` | Proxy de Nginx hacia `gateway-kuberoapp` |
| API Gateway | <https://api-tallerconnect.inf.uct.cl> | Entrada única de la API (web y app móvil) |
| Salud Gateway | `GET /api/health` | Proceso de la Gateway |
| Salud bases | `GET /api/health/servicios` | `/health/db` de MS1–MS4 en paralelo |
| Diagnóstico por servicio | `GET /api/health/servicios/{ms1_auth\|ms2_taller\|ms3_presupuestos\|ms4_evidencias}` | Proceso, base y (MS4) MinIO |
| Swagger UI | <https://api-tallerconnect.inf.uct.cl/docs> | Documentación interactiva |
| Contrato | <https://api-tallerconnect.inf.uct.cl/openapi.json> | OpenAPI 3.1, `info.version` 3.1.0, 75 rutas |
| Descargas firmadas | `https://ms4-tallerconnect.inf.uct.cl/...` | URLs prefirmadas que entrega MS4 (5 min) |
| Panel | <https://kubero.inf.uct.cl> | Solo responsable del despliegue |

### Prefijos de la Gateway (respuesta de `GET /`)

| Microservicio | Prefijos |
| --- | --- |
| MS1 `ms1_auth` | `/api/auth`, `/api/notificaciones` |
| MS2 `ms2_taller` | `/api/clientes`, `/api/mecanicos`, `/api/orden`, `/api/ordenes`, `/api/vehiculo`, `/api/vehiculos` |
| MS3 `ms3_presupuestos` | `/api/inventario`, `/api/presupuesto`, `/api/presupuestos`, `/api/proveedores`, `/api/repuestos` |
| MS4 `ms4_evidencias` | `/api/evidencia`, `/api/evidencias` |

El catálogo completo de las 75 rutas, con ejemplos, está en
[05 — API para la app móvil](05-api-app-movil.md) y en `/docs`.

## Evidencia

Archivo completo: [`evidencia/2026-11-24-despliegue/endpoints.json`](evidencia/2026-11-24-despliegue/endpoints.json)
(código, latencia, `X-Request-ID` y HSTS de cada llamada).

| Método | Ruta | Esperado | Obtenido | ms | Demuestra |
| --- | --- | --- | --- | --- | --- |
| GET | `/` | 200 | 200 | 39 | Gateway publica su mapa de prefijos |
| GET | `/api/health` | 200 | 200 | 29 | Proceso de la Gateway |
| GET | `/api/health/servicios` | 200 | 200 | 68 | Las 4 bases responden |
| GET | `/api/health/servicios/ms1_auth` | 200 | 200 | 77 | MS1: proceso y base |
| GET | `/api/health/servicios/ms2_taller` | 200 | 200 | 48 | MS2: proceso y base |
| GET | `/api/health/servicios/ms3_presupuestos` | 200 | 200 | 53 | MS3: proceso y base |
| GET | `/api/health/servicios/ms4_evidencias` | 200 | 200 | 1245 | MS4: proceso, base y MinIO |
| GET | `/docs` | 200 | 200 | 49 | Swagger UI |
| GET | `/openapi.json` | 200 | 200 | 210 | Contrato publicado |
| GET | `/api/auth/me` | 401 | 401 | 42 | MS1 exige JWT |
| GET | `/api/vehiculos` | 401 | 401 | 38 | MS2 exige JWT |
| GET | `/api/ordenes` | 401 | 401 | 46 | MS2 exige JWT |
| GET | `/api/presupuestos` | 401 | 401 | 52 | MS3 exige JWT |
| GET | `/api/repuestos` | 401 | 401 | 51 | MS3 exige JWT |
| GET | `/api/evidencias` | 401 | 401 | 48 | MS4 exige JWT |
| POST | `/api/auth/login` (cuerpo `{}`) | 422 | 422 | 42 | Validación del cuerpo |
| GET | `/api/no-existe` | 404 | 404 | 35 | Formato común de error con `request_id` |
| GET | web `/` | 200 | 200 | — | Web servida por Nginx |
| GET | web `/api/health` | 200 | 200 | — | Proxy `/api` de la web hacia la Gateway |

**19/19 como se esperaba.** Todas las respuestas de la Gateway traen
`X-Request-ID` y `Strict-Transport-Security`.

Los 401 son la evidencia de que la Gateway enruta al microservicio correcto y
que cada uno valida el JWT por su cuenta ([verificación JWT independiente](../backend/docs/verificacion-jwt-independiente.md)).
El flujo autenticado completo (login, orden, presupuesto, evidencia) ya está
registrado en [07 §20](07-pruebas-realizadas.md).

### Observaciones

- La latencia de MS4 (≈ 1,2 s) viene de la comprobación de MinIO; proceso y base
  responden en < 150 ms.
- Una subida de 13 MiB a `/api/evidencias` la corta el Nginx del ingress con
  413 antes de llegar a la Gateway (límite de 12 MiB de la Gateway, ver
  [08](08-pendientes-y-deuda.md)).
- `/api/health/servicios/ms4` responde 404 con la lista de nombres válidos: hay
  que usar el nombre completo (`ms4_evidencias`).

## Cómo repetir el registro

```bash
cd backend
python scripts/registrar_evidencia_despliegue.py \
  --json ../docs/evidencia/$(date +%F)-despliegue/endpoints.json
```

Usa solo la biblioteca estándar y no envía credenciales. Con `--api` y `--web`
se puede apuntar al smoke test local (`http://127.0.0.1:8080` y `:8081`, ver
[10](10-smoke-test-contenedores.md)). Sale con 1 si algún endpoint no responde
lo esperado.

> El registro del 24-11 se tomó con `fetch()` desde el navegador sobre el mismo
> origen, con los mismos campos que entrega el script.
