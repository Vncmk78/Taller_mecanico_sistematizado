# Evidencia de integración con el equipo móvil (Integra IV)

**Semana 9 — Registrar evidencia de integración con el equipo móvil.**

Registro de cada sesión de prueba entre la app de Integra IV y la Gateway. Sirve
de evidencia para el curso y como fuente de las correcciones del backend: toda
incompatibilidad que aparezca aquí se registra con un ID nuevo en
[`diferencias-contrato-consumo-real.md`](diferencias-contrato-consumo-real.md)
(D-04, …) o en [`contratos-integracion-iv.md`](contratos-integracion-iv.md)
(B-05, …), con su prueba de regresión.

- Operaciones que usa la app: [`contratos-integracion-iv.md`](contratos-integracion-iv.md) §2
- Configuración y reglas para la app: [`estudio-consumo-api-movil-redes-externas.md`](estudio-consumo-api-movil-redes-externas.md) §4

---

## 1. Estado

| | |
|---|---|
| Stack de la app | Sin confirmar (Flutter o React Native) |
| Build de la app disponible | No |
| Entorno acordado para las pruebas | Propuesto: `https://tallerconect.vercel.app` |
| Cuentas de prueba entregadas al equipo móvil | Pendiente |
| Sesiones de prueba realizadas | 2 (S-00 preparación y S-01 checklist de contratos; ambas sin la app) |

## 2. Sesiones

### S-00 — Preparación del backend (2026-11-03)

| | |
|---|---|
| Participantes | Bastián Liempi (backend) |
| Entorno | Gateway local (`0.0.0.0:8000`) y producción en Vercel |
| Cliente | `curl` y pruebas automáticas; simulan un cliente nativo (sin `Origin`) y un build web (con `Origin`) |
| Objetivo | Dejar la Gateway lista para que la app la consuma desde fuera de la red del backend |

Resultado:

| Verificación | Resultado | Evidencia |
|---|---|---|
| Contratos de las 25 operaciones móviles | 179 comprobaciones ok | `pytest tests/test_contratos_integracion_iv.py` |
| Respuestas reales contra el contrato | 29 de 29 ok | `pytest tests/test_contrato_consumo_real.py` |
| Cabeceras para clientes móviles y externos | 4 de 4 ok (2 fallaban antes de corregir H-01) | `pytest tests/test_cabeceras_cliente_movil.py` |
| Regresión de incompatibilidades corregidas (B-01 a B-04, D-01, D-02, O-01) | 18 de 18 ok | `pytest tests/test_regresion_incompatibilidades.py` |
| Producción accesible desde red externa | `200` en `/api/health`; los 4 servicios `ok` tras el arranque en frío | Estudio §2.2 |
| Incompatibilidades corregidas | H-01 (`Retry-After` no expuesto por CORS) y O-01 (matriz de roles desactualizada) | Estudio §3 |
| Pendientes para el equipo móvil | Confirmar stack y si habrá build web (H-02); recibir cuentas de prueba | — |

### S-01 — Ejecución del checklist de contratos de la app móvil (2026-11-12)

**SCRUM-541.** Se ejecutó el checklist de las 38 operaciones que usa la app
(`gateway/contratos/integracion_iv.py`) en dos niveles: el código de la rama y
la Gateway desplegada. Todavía no hay build de la app: esta sesión acredita el
lado del backend, no el consumo desde un teléfono (eso queda para S-02,
SCRUM-538).

| | |
|---|---|
| Participantes | Bastián Liempi (backend) |
| Entorno | Rama `Bastian` (con Semana 10) y producción `https://tallerconect.vercel.app` |
| Cliente | Pruebas automáticas y `httpx` desde fuera de la red del backend, sin `Origin` (cliente nativo) y con `Origin` (build web) |
| Contrato | `info.version` = 3.0.1 en producción |

Resultado en el código (rama `Bastian`):

| Verificación | Resultado | Evidencia |
|---|---|---|
| Contratos de las 38 operaciones móviles | ok | `pytest tests/test_contratos_integracion_iv.py` |
| Respuestas reales contra el contrato | ok | `pytest tests/test_contrato_consumo_real.py` |
| Cabeceras para clientes móviles y externos | ok | `pytest tests/test_cabeceras_cliente_movil.py` |
| Regresión de incompatibilidades corregidas | ok | `pytest tests/test_regresion_incompatibilidades.py` |
| Total de los cuatro archivos | 338 de 338 ok | — |

Resultado en producción:

| # | Verificación | Esperado | Obtenido | `X-Request-ID` | ¿OK? |
|---|---|---|---|---|---|
| 1 | `GET /api/health/servicios` | 4 servicios `ok` | 4 `ok` (tras arranque en frío; el primer intento dio `tiempo_agotado`) | — | ✅ |
| 2 | `/openapi.json` publica las 38 operaciones con sus estados requeridos | 38 de 38 | 38 de 38, versión 3.0.1 | — | ✅ |
| 3 | `GET /api/auth/me` sin token | `401` + `WWW-Authenticate: Bearer` | `401`, `Bearer` | `checklist-541-a` (eco) | ✅ |
| 4 | `GET /api/vehiculos` sin token | `401` `{"detail": ...}` | `401` | `checklist-541-b` (eco) | ✅ |
| 5 | `POST /api/auth/login` con credenciales inválidas | `401` | `401` | `checklist-541-c` (eco) | ✅ |
| 6 | Ruta inexistente | `404 RUTA_NO_ENCONTRADA` | igual | `checklist-541-d` | ✅ |
| 7 | Preflight CORS desde un build web (`*.vercel.app`) | `200` + `Access-Control-Allow-Origin` | igual | — | ✅ |
| 8 | Cabeceras expuestas por CORS | `X-Request-ID`, `Retry-After`, `X-Notificaciones-*` | **falta `Retry-After`** | — | ⚠️ H-03 |

Incompatibilidades encontradas:

- **H-03 — Producción no expone `Retry-After` por CORS.** La corrección H-01
  (Semana 9) está en la rama `Bastian` (`gateway/main.py`, `expose_headers`)
  pero todavía no llega a `Develop` ni a `main`, que es lo desplegado. Solo
  afecta a un build web de la app (un cliente nativo lee la cabecera igual).
  Se resuelve al integrar `Bastian` en `Develop` y `main`; la regresión ya la
  cubre `tests/test_cabeceras_cliente_movil.py`.

Pendiente para S-02 (SCRUM-538, con el equipo de Integra IV): repetir la tabla
de la plantilla desde la app real, por flujo y rol, y marcar la sección 4.

### Plantilla para las próximas sesiones

Copiar este bloque por sesión (S-01, S-02, …):

```markdown
### S-0N — <tema> (<AAAA-MM-DD>)

| | |
|---|---|
| Participantes | <backend> / <equipo móvil> |
| Entorno | <Vercel / local + IP> |
| App | <Flutter / React Native>, build <versión o commit>, <emulador / teléfono, Android/iOS + versión> |
| Red | <Wi-Fi del campus / datos móviles / misma LAN> |
| Cuentas usadas | <cliente de prueba, mecánico de prueba> (nunca anotar contraseñas) |

| # | Flujo | Operación | Rol | Esperado | Obtenido | `X-Request-ID` | ¿OK? |
|---|---|---|---|---|---|---|---|
| 1 | Acceso | `POST /api/auth/login` | Cliente | `200` + token | | | |

Incompatibilidades encontradas: <ID nuevo (D-0N / B-0N) o «ninguna»>
Capturas: `docs/evidencias-movil/S-0N/` (pantalla de la app + respuesta)
Acuerdos y próximos pasos: <…>
```

## 3. Qué evidencia guardar en cada sesión

1. La tabla de operaciones con el estado HTTP y el `X-Request-ID` de cada
   llamada. Con el id se busca la petición en los logs de la Gateway y del
   microservicio.
2. Una captura de la app por flujo (pantalla del resultado o del error que ve el
   usuario).
3. Para cada fallo: método, ruta, body enviado (sin contraseñas ni tokens) y
   body recibido.
4. Versión del contrato contra la que se probó (`info.version` de
   `/openapi.json`).

## 4. Cobertura de flujos

Se marca al terminar cada sesión.

| Flujo | Operaciones | Cliente | Mecánico | Sesión |
|---|---:|:-:|:-:|---|
| Acceso | 3 | ☐ | ☐ | |
| Vehículos | 5 | ☐ | ☐ | |
| Órdenes | 4 | ☐ | ☐ | |
| Trabajo del mecánico | 3 | — | ☐ | |
| Evidencias | 4 | ☐ | ☐ | |
| Presupuestos | 6 | ☐ | — | |
