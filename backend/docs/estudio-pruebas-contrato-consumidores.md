# Estudio: pruebas de contrato orientadas a consumidores (CDC)

**Semana 8 — Estudiar pruebas de contrato orientadas a consumidores.**
**Entregable:** estudio. No se agregan dependencias ni pruebas en esta tarea.

Complementa [`estudio-pruebas-contrato-clientes-web-movil.md`](estudio-pruebas-contrato-clientes-web-movil.md).
Ese estudio hace el inventario de las pruebas de contrato que **ya existen**,
todas escritas desde el lado del proveedor (la Gateway y los microservicios).
Este estudio mira el otro lado: **qué cambia cuando el contrato lo escribe el
consumidor** (frontend web y app móvil de Integración IV), qué herramientas
hay para cada stack y cómo encajaría en el SGTM.

---

## 1. La idea en una frase

En una prueba de contrato orientada a consumidores (*Consumer-Driven Contract*,
CDC), **cada cliente declara en una prueba propia exactamente qué pide y qué
usa de la respuesta**, y el proveedor **reproduce esas expectativas contra su
código real** antes de publicar un cambio. El contrato deja de ser «todo lo que
el proveedor ofrece» y pasa a ser «lo que los consumidores realmente usan».

## 2. Conceptos

| Concepto | Qué es | En el SGTM sería… |
|---|---|---|
| Consumidor | Quien llama a la API | Frontend web (React), app móvil (Integra IV) |
| Proveedor | Quien responde | La Gateway (`/api/*`) con MS1–MS4 detrás |
| Interacción | Un par petición → respuesta esperada | `GET /api/ordenes/31` con token de cliente → `200` con `orden_id`, `estado`, `patente` |
| Pacto (*pact*) | Archivo JSON con todas las interacciones de un consumidor contra un proveedor | `sgtm-web-sgtm-gateway.json`, `sgtm-movil-sgtm-gateway.json` |
| *Matchers* | Reglas «por tipo» en vez de valores exactos | «`orden_id` es un entero», no «`orden_id` vale 31» |
| Estado del proveedor (*provider state*) | Precondición que el proveedor prepara antes de reproducir una interacción | «existe la orden 31 del cliente 42 en `esperando_aprobacion`» |
| Verificación del proveedor | El proveedor levanta su app real, prepara cada estado, reproduce cada petición del pacto y compara | Una prueba de `pytest` contra la Gateway in-process |
| Broker | Servidor que guarda pactos y resultados por versión | Pact Broker (libre) o PactFlow (SaaS). Opcional con un solo repositorio |
| `can-i-deploy` | Consulta al broker: «¿esta versión es compatible con lo que está desplegado?» | Solo con broker |

### Flujo

```
Consumidor (web/móvil)                       Proveedor (Gateway + MS)
───────────────────────                      ────────────────────────
1. Prueba unitaria del cliente HTTP
   contra un mock server de Pact
2. Si pasa, se genera el pacto  ───────────► 3. Verificación: por cada interacción
   (JSON)                                       a) preparar el provider state
                                                b) llamar a la app real
                                                c) comparar con los matchers
                                             4. Si falla: el cambio del proveedor
                                                rompe a un consumidor concreto
```

Lo importante: **el consumidor no prueba contra el proveedor real**. Prueba
contra un mock que Pact arma con sus propias expectativas, y esas mismas
expectativas viajan al proveedor. Ningún lado necesita al otro levantado.

## 3. Tres formas de hacer pruebas de contrato

| | Guiadas por el proveedor (lo que hay hoy) | CDC clásico (Pact) | Bidireccional (BDCT) |
|---|---|---|---|
| Quién escribe el contrato | El proveedor (OpenAPI) | Cada consumidor (pacto) | Ambos: el proveedor su OpenAPI, el consumidor su pacto |
| Qué se verifica | El proveedor cumple su OpenAPI | El proveedor real responde lo que cada consumidor espera | Comparación **estática**: el pacto es un subconjunto válido del OpenAPI |
| Detecta un campo que nadie usa | Lo protege igual (rigidez innecesaria) | No: se puede quitar sin romper a nadie | No |
| Detecta que un consumidor usa algo no publicado | No | Sí | Sí |
| Necesita *provider states* | No | **Sí** (el costo principal) | No |
| Necesita levantar el proveedor | No | Sí (puede ser in-process) | No |
| Herramienta | `jsonschema`, `openapi-spec-validator` (ya en uso) | Pact (libre) | Función de PactFlow (comercial) |

La documentación de PactFlow describe el bidireccional como una comparación
estática entre un contrato del consumidor y otro que representa la capacidad
del proveedor (normalmente un OpenAPI), y advierte que confía en el OpenAPI que
recibe: si el proveedor no lo verificó contra su API, la garantía es débil
(«garbage in, garbage out»). En el SGTM esa verificación ya existe
(`test_gateway_openapi*.py`, `test_contratos_integracion_iv.py`), y la versión
1.0.0 está congelada en `docs/openapi/sgtm-gateway-1.0.0.json`.

## 4. Situación actual del SGTM

### 4.1 Lado proveedor: sólido

- OpenAPI 1.0.0 estable y congelado; cualquier cambio sin subir versión rompe
  `test_gateway_openapi_version_estable.py`.
- Las copias de contratos en `gateway/contratos/` se comparan campo a campo con
  los esquemas reales de los microservicios.
- La app móvil tiene su catálogo cerrado de 25 operaciones
  (`gateway/contratos/integracion_iv.py`) validado en 7 dimensiones.

### 4.2 Lado consumidor: las expectativas existen, pero nadie las verifica

El frontend web ya tiene, sin llamarlo así, **la mitad de un contrato de
consumidor**:

- `frontend/src/infrastructure/mocks/payloads.reales.ts`: 37 cuerpos copiados a
  mano de los ejemplos del backend, con un comentario que cita su origen.
- Los tests de `src/infrastructure/api/*Service.test.ts` hacen `vi.mock` del
  cliente axios y prueban el mapeo contra esos cuerpos.
- `frontend/docs/contratos-openapi.md` es una auditoría manual de cada llamada.

El problema: **ese conocimiento no vuelve al backend**. Si MS2 cambia un campo
y actualiza su OpenAPI (subiendo versión como corresponde), los tests del
frontend siguen pasando contra la copia vieja de `payloads.reales.ts`. El fallo
aparece recién en ejecución. Es el hueco que CDC cierra: las expectativas que
hoy están en `payloads.reales.ts` serían el pacto, y el backend las reproduciría.

La app móvil todavía no tiene código en este repositorio, así que es el momento
más barato para elegir cómo declarará sus expectativas.

### 4.3 Qué CDC **no** resuelve

- **Errores que el consumidor ignora.** El OpenAPI 1.0.0 publica el `429` de
  login (bloqueo por intentos fallidos), pero el interceptor de
  `apiClient.ts` solo trata `401` y `403`. CDC no lo detecta: un pacto solo
  contiene lo que el consumidor declaró. Eso se revisa leyendo el contrato
  publicado, no con Pact.
- **Autorización por recurso** (quién ve qué orden): sigue siendo de
  `matriz-autorizacion-roles.md` y de las pruebas de acceso cruzado.
- **Comportamiento entre servicios** (MS3 ↔ MS2): es contrato interno; podría
  modelarse con Pact (MS3 como consumidor de MS2), pero está fuera de este estudio.

## 5. Herramientas por stack

| Stack | Biblioteca | Estado | Notas para el SGTM |
|---|---|---|---|
| Web (TypeScript, Vitest, axios) | `@pact-foundation/pact` (Pact JS) | Madura, mantenida por Pact Foundation | El mock server reemplaza el `vi.mock` de axios: el `*Service` real hace la llamada HTTP |
| Móvil React Native | `@pact-foundation/pact` | Igual que web | Mismo flujo que el frontend |
| Móvil Flutter | `pact_dart` | Implementa Pact v3 vía la librería FFI de Pact, pero sin publicar al broker ni verificar varios *provider states*; el repositorio no muestra actividad reciente | Viable para **generar** el pacto; el resto se haría desde el backend. Alternativa: el enfoque bidireccional |
| Proveedor Python (FastAPI) | `pact-python` v3 | v3 estable desde 2025; trae un ejemplo con FastAPI | Verificaría la Gateway; requiere Python ≥ 3.9 (el proyecto usa 3.12+) |

Integra IV todavía no define si la app será Flutter o React Native
(`Grupo10_TallerMecanico_v2.tex`). **Esa decisión cambia la recomendación**:
con React Native, CDC clásico es directo; con Flutter, conviene el formato
bidireccional o un contrato de consumidor propio (Fase 0 de §7).

## 6. Cómo se vería la verificación en el backend

El costo real de CDC son los *provider states*. En el SGTM se podrían montar
sobre lo que ya existe en `tests/test_integracion_prefijos.py` (fixture
`ecosistema`): la Gateway real conectada a los cuatro microservicios reales
in-process, cada uno con SQLite en memoria, sin red ni Docker.

Estados mínimos para cubrir los flujos móviles del catálogo:

| Provider state | Qué prepara | Interacciones que lo usan |
|---|---|---|
| `existe un cliente con un vehículo` | Usuario Cliente en MS1, perfil y vehículo en MS2 | login, `me`, vehículos |
| `el cliente tiene una orden en esperando_aprobacion` | Orden + historial en MS2 | órdenes, historial, cancelación |
| `existe un presupuesto enviado para esa orden` | Presupuesto y versión enviada en MS3 | presupuestos, decisión |
| `existe un mecánico con una orden asignada` | Usuario Mecánico + asignación en MS2 | vehículos asignados, estado, bitácora |
| `la orden tiene una evidencia` | Fila en MS4 con almacenamiento falso | evidencias |
| `la cuenta está bloqueada` | Superar `LOGIN_MAX_INTENTOS` | `429` de login |

Dos detalles propios del proyecto:

1. **JWT.** El pacto no puede llevar un token real (expira y depende de la
   clave). Se declara con un *matcher* de formato (`Bearer .+`) y el verificador
   reemplaza la cabecera por un token emitido por MS1 para el estado preparado.
2. **Identificadores.** Los IDs dependen del orden de inserción en SQLite: el
   pacto debe usar *matchers* por tipo y, cuando el ID va en la ruta, inyectarlo
   desde el estado del proveedor.

## 7. Propuesta por fases

### Fase 0 — Contrato de consumidor propio, sin herramientas nuevas

Cada consumidor declara en un JSON versionado **qué operaciones y qué campos
usa** de cada respuesta (por ejemplo `frontend/contratos/consumo-web.json`). Una
prueba del backend comprueba que todo lo declarado existe en
`docs/openapi/sgtm-gateway-<versión>.json` con el mismo tipo. Es la idea del
enfoque bidireccional sin depender de PactFlow, y extiende lo que ya hace
`gateway/contratos/integracion_iv.py` (que hoy llega a nivel de operación, no de
campo).

- Costo: bajo. Sin *provider states* ni dependencias.
- Detecta: quitar o renombrar un campo que un consumidor usa.
- No detecta: que la app real responda distinto de su OpenAPI (eso ya lo
  cubren las pruebas del proveedor).

### Fase 1 — Pact en el frontend web

- Reemplazar el `vi.mock` de axios en los `*Service.test.ts` por el mock server
  de Pact JS en tres flujos: login, órdenes y decisión de presupuesto.
- Guardar los pactos generados en el repositorio (con un solo repo no hace
  falta broker).
- En el backend, `pact-python` v3 verifica esos pactos contra la Gateway
  in-process con los estados de §6.

### Fase 2 — App móvil

- React Native: igual que la Fase 1.
- Flutter: generar el pacto con `pact_dart` y verificarlo desde el backend, o
  quedarse en la Fase 0 si la herramienta no alcanza.

### Fase 3 (opcional) — Broker

Solo si web, móvil y backend pasan a desplegarse por separado y con versiones
independientes. Pact Broker es libre y se levanta con Docker; `can-i-deploy`
bloquearía un despliegue incompatible.

## 8. Costos y riesgos

| Riesgo | Mitigación |
|---|---|
| Mantener *provider states* cuesta más que escribir la prueba | Empezar por la Fase 0; en la Fase 1, pocos estados reutilizables (§6) |
| Pactos sobreespecificados (valores exactos) que fallan por cualquier cambio | Usar *matchers* por tipo; valores exactos solo en enums y códigos de error |
| Dos equipos de cursos distintos (Integra II e Integra IV) | El pacto móvil se guarda en este repo; el backend lo verifica en su suite |
| Herramienta Flutter con soporte parcial | Fase 0 como camino alternativo |
| Duplicar lo que ya cubre el OpenAPI | CDC no reemplaza las pruebas del proveedor: se suma solo donde hay consumidores reales |

## 9. Recomendación

1. **Ahora:** Fase 0. Es barata, no depende del stack móvil y aprovecha el
   OpenAPI 1.0.0 congelado. Conviene que la diseñe el backend y que la llenen
   web e Integra IV.
2. **Cuando el frontend estabilice sus servicios:** Fase 1 en los tres flujos
   críticos, para validar el costo real de los *provider states* antes de
   extenderlo.
3. **Pedir a Integra IV** que confirme Flutter o React Native: define si la
   Fase 2 es CDC clásico o se queda en la Fase 0.

## 10. Qué no cubre este estudio

- No agrega dependencias (`pact-python`, `@pact-foundation/pact`) ni pruebas.
- No evalúa contratos asíncronos o de mensajería: el SGTM no usa colas.
- No compara herramientas fuera del ecosistema Pact (por ejemplo Spring Cloud
  Contract), porque ninguna aplica a Python + TypeScript + Dart a la vez.

## 11. Referencias

- Pact Python — anuncio de v3: <https://pact-foundation.github.io/pact-python/blog/2025/12/04/announcing-pact-python-v3>
- Pact Python en PyPI: <https://pypi.org/project/pact-python>
- PactFlow — guía de Bi-Directional Contract Testing: <https://docs.pactflow.io/docs/bi-directional-contract-testing>
- PactFlow — guía del proveedor en BDCT: <https://docs.pactflow.io/docs/bi-directional-contract-testing/provider>
- `pact_dart` (Flutter/Dart): <https://pub.dev/documentation/pact_dart/latest/>
- Documentación general de Pact: <https://docs.pact.io/>
- Internas: `estudio-pruebas-contrato-clientes-web-movil.md`,
  `contratos-integracion-iv.md`, `versionado-contrato-openapi.md`,
  `frontend/docs/contratos-openapi.md`,
  `frontend/src/infrastructure/mocks/payloads.reales.ts`.
