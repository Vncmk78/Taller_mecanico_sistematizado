# Estudio: pruebas de contrato para los clientes web y móvil

**Ámbito:** backend (API Gateway y sus microservicios). Rama `DerisA`.
**Entregable:** estudio. **No se escriben ni modifican pruebas** en esta tarea.

---

## 1. Por qué este estudio

El frontend web (React) y la app móvil (Integración IV) no tocan los
microservicios directamente: consumen exclusivamente la API Gateway bajo
`/api/*`. Eso significa que **ambos clientes comparten un único contrato**, y
cualquier cambio en un microservicio les llega sin compilación intermedia ni
aviso: si un campo cambia de nombre o desaparece, el cliente se rompe en
tiempo de ejecución.

El proyecto ya tiene un cuerpo considerable de pruebas que tocan contratos.
Este estudio responde tres preguntas concretas:

1. ¿Qué contrato consumen hoy web y móvil?
2. ¿Qué pruebas de contrato existen y qué cubren de ese contrato?
3. ¿Qué huecos quedan y cómo se cerrarían?

---

## 2. Qué contrato consumen los clientes

### 2.1 Fuentes de verdad

| Fuente | Qué fija |
|---|---|
| `docs/contratos-api-gateway.md` | Contrato único escrito: rutas, cuerpos, errores, ejemplos y pendientes |
| `GET /openapi.json` y `/docs` | Fuente interactiva del contrato (la que leen ambos clientes) |
| `gateway/contratos/*.py` | Copias de los contratos HTTP de MS1, MS2 y MS4 (la Gateway no importa código de los microservicios) |
| `shared/auth.py` | Contrato único del token (claims `sub`, `roles`, `exp`) |
| `shared/contratos_decisiones.py` | Contrato de coordinación MS2 ↔ MS3 (decisiones de presupuesto) |

La regla que gobierna todo lo demás, tal como la fija el propio documento:

> El frontend web y la aplicación móvil deben consumir exclusivamente las
> rutas publicadas por la API Gateway con prefijo `/api`. La existencia de una
> llamada o una interfaz provisional en un cliente no convierte una ruta
> futura en contrato implementado.
> — `docs/contratos-api-gateway.md`, «Contratos todavía no publicados»

### 2.2 Extensión vigente del contrato

Medida sobre el OpenAPI que publica la Gateway (no supuesta):

| Prefijo | Operaciones | Microservicio |
|---|---:|---|
| `auth` | 3 | MS1 |
| `vehiculos` | 5 | MS2 |
| `ordenes` | 11 | MS2 |
| `evidencias` | 4 | MS4 |
| `presupuestos` (solo decisiones) | 2 | MS3 |
| `health` | 2 | Gateway |
| índice `GET /` | 1 | Gateway |
| **Total** | **28** | — |

De esos 28, **25 son operaciones de negocio** (las de `health` y el índice no
lo son; `test_gateway_openapi.py` compara contra `_ENDPOINTS_ESPERADOS`, que
tiene exactamente esas 25 entradas).

### 2.3 Enrutado pero no publicado

`gateway/rutas.py` define **14 prefijos**. Solo 5 de negocio están en el
contrato publicado; los otros **9 se reenvían igualmente** a su microservicio
pero **no aparecen en `/openapi.json`**:

```
vehiculo, orden, clientes, mecanicos,
presupuesto, repuestos, proveedores, inventario, evidencia
```

Lo mismo ocurre a nivel de capacidad: MS3 tiene endpoints de presupuestos,
repuestos, proveedores e inventario, pero el contrato publicado por la Gateway
solo incluye las **2 operaciones de decisiones**. El resto queda declarado
como «todavía no publicado».

Consecuencia práctica: esas rutas **funcionan a nivel de red** y un cliente
podría usarlas, pero al no estar publicadas **pueden cambiar sin aviso** y sin
que ninguna prueba lo señale.

### 2.4 En qué se diferencian los dos canales

| | Cliente web (navegador) | Aplicación móvil |
|---|---|---|
| Cabecera `Origin` | Siempre, en cada petición | Nunca |
| Preflight `OPTIONS` | Sí, antes de mutar | No aplica |
| `Authorization` | `Bearer` (también en fetch) | `Bearer` (nativo) |
| Cuerpo JSON y códigos | **Idénticos al móvil** | **Idénticos al web** |

Solo cambia la capa CORS (`Access-Control-*`). El contrato de negocio —
métodos, cuerpos, `status`, formato de `{"detail": ...}`, catálogo de códigos
`error`, `X-Request-ID` y límites de body — es **el mismo para los dos**.

---

## 3. Qué pruebas de contrato existen hoy

Se ordenan por el tipo de garantía que ofrecen.

### 3.1 Documento contra documento

Comparan el contrato publicado con otros documentos (esquemas de los
microservicios, copias de `gateway/contratos`, ejemplo contra esquema).

| Archivo | Pruebas | Qué comprueba |
|---|---:|---|
| `tests/test_gateway_openapi.py` | 42 | El Swagger publica exactamente `_ENDPOINTS_ESPERADOS`, seguridad `bearer` en los protegidos, ausencia del proxy genérico, y que **cada copia de `gateway/contratos` coincida campo a campo y en obligatoriedad** con el esquema real de MS1, MS2 y MS4 |
| `tests/test_gateway_openapi_ejemplos.py` | 20 | El esquema cumple el especificador OpenAPI (`openapi-spec-validator`), **todos los ejemplos cumplen su esquema** (`jsonschema.Draft202012Validator`), el catálogo de errores, `X-Request-ID` declarado en toda respuesta y que no se filtren URLs internas ni tokens reales |
| `tests/test_gateway_openapi_evidencias.py` | 4 | Los ejemplos publicados de `/api/evidencias*` **son respuestas reales de MS4** (errores) o cumplen sus esquemas (éxitos) |
| `tests/test_ms3_presupuestos_contratos.py` | 15 | El OpenAPI de MS3 publica sus endpoints y sus validaciones de body (versión con `items` o copia, motivo en rechazo, orden positiva) |
| `tests/test_gateway_openapi.py::test_coordinacion_publica_contrato_minimo_y_error_reintentable` | — | El contrato MS3 ↔ MS2 publicado coincide con los modelos de `shared/contratos_decisiones.py` |

### 3.2 Documento contra respuestas reales (parcial)

Comprueban que lo publicado coincide con lo que la aplicación responde de
verdad, pero **solo en casos puntuales**:

- `test_ejemplos_errores_coinciden_con_respuestas_reales_ms2` — dispara **6
  errores reales** de MS2 (`401` sin token, `401` token inválido, `403` rol,
  `422` ×3) y exige `respuesta.json() == ejemplo` contra el OpenAPI de la
  Gateway **y** el de MS2.
- `test_gateway_openapi_evidencias.py` — los ejemplos de error de
  `/api/evidencias*` se comparan con respuestas reales de MS4 (base SQLite,
  almacenamiento y MS2 falsos) y el `413` con la respuesta real de la Gateway.

### 3.3 Comportamiento en runtime (formato y transporte)

No comparan contra el OpenAPI, pero fijan partes del contrato que los clientes
leen directamente:

| Archivo | Pruebas | Qué comprueba |
|---|---:|---|
| `tests/test_gateway_formato.py` | 15 | Formato común de errores (`404`, `405`, `502`, `500`, `ERROR_HTTP`), `detail` siempre string, generación/propagación/validación de `X-Request-ID`, error del microservicio reenviado tal cual |
| `tests/test_gateway_errores_proxy.py` | 28 | Mapeo de fallos de red a `502`/`504`/`503`, cabeceras que llegan al cliente y las que se descartan, `204` sin cuerpo, traducción de `Location` |
| `tests/test_gateway_rutas.py` | 43 | Enrutamiento con microservicios simulados (`respx`): body, query string y `Authorization` conservados |
| `tests/test_gateway_evidencias.py` | 14 | Límites de body (`413`/`400`) antes de llamar al microservicio y flujo real de subida/listado/descarga contra MS4 |
| `tests/test_gateway_estructura.py` | 6 | CORS: preflight permitido para el origen del frontend y rechazo de origen no permitido |

### 3.4 Integración completa (in-process)

`tests/test_integracion_prefijos.py` conecta la **Gateway real** con los
**cuatro microservicios reales** por `httpx.ASGITransport` (sin red, sin
Docker, sin `respx`), cada uno con SQLite en memoria. Recorre el flujo que
usarán los clientes: registro, login, `me`, vehículos con token emitido por
MS1, `422` con `detail` en lista, `404` de vehículo ajeno, y `404` de MS3/MS4
**sin** la clave `error` de la Gateway (así se distingue un 404 del
microservicio de uno de la Gateway).

### 3.5 Los dos canales

`tests/test_autenticacion_canales.py` (**10 pruebas**) es la única que
ejercita explícitamente los dos clientes:

- **Web:** preflight de login respondido por la Gateway sin llegar a MS1,
  `Authorization` autorizado en preflight, `Access-Control-Allow-Origin` en la
  respuesta, origen no permitido rechazado y sin `Allow-Origin`.
- **Móvil:** login sin `Origin` y sin preflight, reenvío del `Bearer` a MS1,
  y que **el error sea idéntico en los dos canales** (`401` con el mismo
  cuerpo; `ACAO` presente solo en el canal web).

### 3.6 Verificación manual con servicios levantados

| Script | Qué verifica | ¿Automática? |
|---|---|---|
| `scripts/prueba_comunicacion.py` | 13 pasos con red real, PostgreSQL y MinIO: health, logins, token cruzado MS1→MS2, `401`, `404` del microservicio, `X-Request-ID` de ida y vuelta | No |
| `scripts/revisar_openapi.py` | Para **cada operación** que la Gateway documenta, descarga el `/openapi.json` del microservicio dueño del prefijo y comprueba ruta, método, campos de body y de respuesta. Cualquier diferencia es una **discrepancias que el frontend heredaría** | No |

Ambos están descritos en `docs/pruebas-comunicacion-gateway.md` y se ejecutan
a mano; **no forman parte de `pytest`**.

---

## 4. Hallazgos (huecos)

### 4.1 Ninguna prueba valida una respuesta viva contra el esquema publicado

`jsonschema` se usa **solo sobre ejemplos** (`test_gateway_openapi_ejemplos.py`).
Las comparaciones contra respuestas reales existen, pero son puntuales: 6
errores de MS2 y los ejemplos de evidencias. **No hay ninguna prueba que
tome una respuesta real** (`200` de `GET /api/vehiculos`, `201` de creación,
etc.) **y la valide contra el `schema` publicado en `/openapi.json`**
(campos obligatorios, tipos, `additionalProperties`).

Efecto: si un microservicio deja de devolver un campo que la Gateway documenta,
ninguna prueba se entera salvo que ese campo esté hardcodeado en algún otro
test. El cliente descubre el cambio cuando se rompe en producción.

### 4.2 Solo `auth` se ejercita en los dos canales

Las 10 pruebas de canales cubren `POST /api/auth/login` y `GET /api/auth/me`
(+ un `401` y un `401` de login). Las **otras 24 operaciones de negocio nunca
se prueban simultáneamente con `Origin` y sin `Origin`**.

El preflight está cubierto en `/api/auth/login` (2 pruebas) y en
`/api/health` (`test_gateway_estructura.py`), y un error con `Origin` en
`/api/vehiculos` (`test_gateway_formato.py`). La semántica JSON en los dos
canales, en cambio, solo se verifica en `auth`.

### 4.3 Nada fija qué prefijos están publicados y cuáles no

Solo `test_proxy_generico_no_aparece` evita que aparezca el proxy genérico
`{ruta}` en el Swagger. **No hay ninguna prueba que impida**:

- que uno de los 9 prefijos enrutados sin publicar (`clientes`, `mecanicos`,
  `repuestos`, …) se publique sin querer, o
- que un cliente empiece a depender de una de esas rutas porque «funciona».

El contrato lo prohíbe por escrito; ninguna prueba lo hace cumplir.

### 4.4 MS3 queda fuera del contrato publicado, salvo decisiones

Los clientes pueden llamar a `/api/presupuestos/*` y obtener respuestas, pero
esas rutas no son contrato. Si 4° año consume alguna (listado o creación de
presupuestos desde la web o la app), **no está cubierto por ninguna prueba de
contrato** y puede cambiar sin aviso. Esto ya está declarado en el documento
de contratos, pero es el punto donde el riesgo de los dos clientes es mayor.

### 4.5 La comparación Gateway ↔ microservicio con servicios reales es manual

`scripts/revisar_openapi.py` hace exactamente el chequeo que faltaría (cada
operación publicada contra el OpenAPI real del microservicio dueño), pero
requiere los servicios levantados y **no corre en `pytest` ni en CI**. Lo que
sí corre en `pytest` (la comparación de `gateway/contratos` con los esquemas
reales) se hace importando los esquemas de MS1, MS2 y MS4; para las 2
operaciones de decisiones de MS3 la comparación es contra
`shared/contratos_decisiones.py`, no contra el OpenAPI de MS3.

### 4.6 Observación menor: un docstring desactualizado

El docstring de `tests/test_gateway_openapi.py` dice que el Swagger publica
«los **22** endpoints reales de Auth, Vehículos, Órdenes y Evidencias». Hoy
esos cuatro grupos suman **23**: después se agregó
`POST /api/ordenes/{orden_id}/decisiones-presupuesto`. **La prueba no falla**
porque compara contra `_ENDPOINTS_ESPERADOS` y no contra el número 22; solo
desorienta al lector. *No se corrigió por estar fuera del alcance de esta
tarea.*

---

## 5. Propuestas para cerrar los huecos

**No implementadas.** Las anoto para una tarea futura; varias requieren decidir
el contrato antes (sobre todo el alcance de MS3).

1. **Respuesta real ↔ esquema publicado.** Parametrizar por operación: hacer
   la llamada a través de la Gateway, tomar el `schema` de la respuesta en
   `/openapi.json` y validarla con `jsonschema.Draft202012Validator`
   (dependencia ya presente). Cierra el hueco 4.1.
2. **Canales parametrizados.** Reutilizar el patrón de
   `test_autenticacion_canales.py` (fixture con/sin `Origin`) sobre
   representativos de cada grupo (vehículos, órdenes, evidencias) en vez de
   solo `auth`. Cierra el 4.2.
3. **Fijar el conjunto publicado.** Un test que compare
   `set(gateway.rutas.RUTAS)` con los prefijos publicados y exija que la
   diferencia sea exactamente la lista de pendientes documentados. Cierra el 4.3.
4. **Automatizar `revisar_openapi.py`.** Ya existe el patrón in-process de
   `test_integracion_prefijos.py`; llevar ese chequeo a `pytest` eliminaría la
   verificación manual. Cierra el 4.5.
5. **Actualizar el docstring** de `test_gateway_openapi.py`. Cierra el 4.6.

---

## 6. Qué no cubre este estudio

- **No escribe ni modifica pruebas** ni código: alcance acordado para esta
  tarea (documento únicamente).
- **No analiza `frontend/` ni la app móvil**: ambos pertenecen al otro equipo;
  aquí los clientes se describen solo por cómo llegan a la Gateway.
- **No evalúa autorización por recurso**: eso lo gobierna
  `matriz-autorizacion-roles.md`.
- **No cubre** evolución/versionado del contrato, compatibilidad hacia atrás,
  rendimiento ni UX.
- Las cifras (28 operaciones, 14 prefijos, conteos de pruebas) se midieron
  sobre el árbol de la rama `DerisA`; si el OpenAPI o los tests cambian, deben
  volverse a medir.

---

## 7. Referencias

- `docs/contratos-api-gateway.md` — contrato único que consumen ambos clientes.
- `docs/pruebas-comunicacion-gateway.md` — verificación manual con servicios levantados.
- `docs/matriz-autorizacion-roles.md` — qué rol puede hacer qué.
- `gateway/openapi.py` — construcción del OpenAPI publicado.
- `gateway/rutas.py` — tabla de enrutamiento por prefijo.
- `gateway/contratos/` — copias de los contratos de MS1, MS2 y MS4.
- `tests/test_gateway_openapi.py`, `tests/test_gateway_openapi_ejemplos.py`,
  `tests/test_gateway_openapi_evidencias.py` — contrato publicado.
- `tests/test_autenticacion_canales.py` — canales web y móvil.
- `tests/test_integracion_prefijos.py` — Gateway + 4 microservicios reales.
- `scripts/prueba_comunicacion.py`, `scripts/revisar_openapi.py` — verificación manual.
