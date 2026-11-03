# Versionado del contrato OpenAPI de la Gateway

**Semana 8 — Publicar una versión estable del contrato OpenAPI para integración.**

El contrato que publica la Gateway en `/openapi.json` es el que consumen el
frontend web y la app móvil de Integración IV. Desde **1.0.0** se considera
**estable**: un cliente que se integró contra 1.0.0 no se rompe hasta 2.0.0.

| | |
|---|---|
| Versión vigente | **1.1.0** |
| Copia congelada | [`docs/openapi/sgtm-gateway-1.1.0.json`](openapi/sgtm-gateway-1.1.0.json) |
| Interactivo | `http://localhost:8000/docs` (Swagger) y `/openapi.json` |
| Dónde se define | `gateway/openapi.py` (`_VERSION`), `gateway/openapi_ms3.py`, `gateway/openapi_ejemplos.py`, `shared/openapi_ordenes.py` |

---

## 1. Cómo lo consumen los otros equipos

- **Sin levantar la Gateway:** usen el archivo congelado. Sirve para generar
  tipos o clientes (`openapi-typescript`, `openapi-generator`, Flutter/Dart,
  etc.) y mocks a partir de los ejemplos.
- **Fijen la versión:** referencien `sgtm-gateway-1.0.0.json`, no «el último».
  Una versión nueva llega como un archivo nuevo; el anterior no se borra.
- **Solo lo publicado es contrato.** Una ruta que la Gateway reenvía pero no
  aparece en el archivo puede cambiar sin aviso.

## 2. Reglas de versionado (semver)

| Cambio | Versión | Ejemplos |
|---|---|---|
| No cambia el comportamiento | **PATCH** `1.0.x` | Descripciones, ejemplos, documentar un estado de error que el servicio **ya** respondía |
| Agrega sin romper | **MINOR** `1.x.0` | Operación nueva, campo nuevo **opcional** en el body, campo nuevo en una respuesta, valor nuevo de un enum de respuesta |
| Rompe a algún cliente | **MAJOR** `2.0.0` | Quitar o renombrar una ruta o campo, volver obligatorio un campo, cambiar un tipo o formato, cambiar el significado de un estado, exigir autenticación o un rol donde antes no |

Ante la duda entre MINOR y MAJOR, es MAJOR. Un MAJOR se coordina antes con
los equipos web e Integración IV.

## 3. Cómo publicar una versión nueva

Desde `backend/`:

1. Cambia el contrato (`gateway/openapi*.py`, `gateway/contratos/*`).
2. Sube `_VERSION` en `gateway/openapi.py` y `version=` en `gateway/main.py`
   según la tabla anterior.
3. Exporta: `python scripts/exportar_openapi.py` (crea
   `docs/openapi/sgtm-gateway-<version>.json`; el anterior queda como historial).
4. Agrega la entrada en el historial de este documento.
5. Corre `python -m pytest tests/test_gateway_openapi_version_estable.py tests/test_contratos_integracion_iv.py`.

Si cambias el contrato y olvidas los pasos 2 y 3,
`test_archivo_congelado_coincide_con_el_publicado` falla. Para comprobarlo a
mano: `python scripts/exportar_openapi.py --verificar`.

## 4. Historial

### 1.1.0 — Integración de historial, avisos y disponibilidad

Se conserva la copia 1.0.0. Este incremento agrega operaciones sin retirar las
existentes: bandeja personal de notificaciones, historial paginado por vehículo,
reserva verificada de repuestos y su aplicación en MS2. La respuesta de entrega
incorpora datos de auditoría. Se conservan los métodos GET y POST cuando ambos
comparten la ruta de disponibilidad de inventario. Los eventos `/interno/*`
siguen fuera de la Gateway.

Los ejemplos para móvil incluyen listado, detalle y finalización de órdenes por
el Mecánico asignado. La validación del contrato y la copia congelada no prueban
que la base del despliegue público esté migrada ni sustituyen una prueba desde
la aplicación de Integración IV.

### 1.0.0 — Semana 8 (primera versión estable)

Base: 59 rutas publicadas (MS1, MS2, MS3, MS4, health e índice). Respecto de
0.1.0 no se quitó ni se renombró nada; solo se completó la documentación de
comportamiento que ya existía (brechas de `contratos-integracion-iv.md` §4):

| ID | Operación | Cambio |
|---|---|---|
| B-01 | `POST /api/auth/login` | Se publican `403` (cuenta sin roles), `422` (body inválido) y `429` (cuenta bloqueada, con cabecera `Retry-After`), con ejemplos tomados de respuestas reales de MS1 |
| B-02 | `GET /api/vehiculos/{vehiculo_id}` | Se publica `422` (identificador no numérico) con su ejemplo real. Se retira un ejemplo de `403` que no correspondía: el endpoint no rechaza por rol, el Mecánico ve los vehículos de sus órdenes asignadas y los demás reciben `404` |
| B-03 | `GET` y `POST /api/ordenes/{orden_id}/bitacora` | Ejemplos de éxito (lista con observación y acción, lista vacía, y body/respuesta del registro) |
| B-04 | `POST /api/ordenes/{orden_id}/cancelacion` | Ejemplos de body, `201` (solicitud creada) y `200` (solicitud repetida) |
| — | `info` | `version` pasa de `0.1.0` a `1.0.0` y la descripción incluye la política de versionado |

### 0.1.0 — Semanas 1 a 7

Contrato en construcción, sin garantía de compatibilidad.
