# Estudio: pruebas de integración del frontend ante fallos de red y servicios

**Tarea (Semana 10):** Estudiar pruebas de integración frontend ante fallos de red y servicios
**Alcance:** Frontend Web (React) — qué cubre hoy la suite de Vitest cuando la API Gateway no responde, responde con error o el servicio de un microservicio está caído.
**Entregable:** estudio. **No se escriben ni modifican pruebas ni código** en esta tarea; las propuestas del final quedan como trabajo futuro.
**Base:** rama `Gustavo`, commit `844fe3c` (incluye la tarea previa "Mejorar manejo global de errores y estados de carga").

---

## 1. Por qué este estudio

El frontend web consume exclusivamente la API Gateway bajo `/api/*`. En producción
pueden fallar cuatro cosas distintas, y la UI debe reaccionar distinto en cada caso:

1. **No hay red o la Gateway no responde** (DNS, CORS, conexión cortada, timeout):
   el usuario debe conservar lo que ya vio y saber que está sin conexión.
2. **La Gateway está viva pero un microservicio no responde** (`502`/`503`/`504`):
   no es culpa del usuario, se puede reintentar.
3. **El servidor responde con un error propio** (`500`) o de negocio
   (`401`/`403`/`404`/`409`/`422`): no es "sin conexión" y no siempre se reintenta.
4. **Una escritura pudo aplicarse aunque no llegó la respuesta** (timeout, `502`-`504`,
   `500` de la Gateway): hay que comprobar el estado antes de repetir.

La pregunta de esta tarea no es "¿hay pruebas?" — hay 1117 — sino **qué nivel de
fallo cubren realmente**. La suite mockea servicios con `vi.mock`, así que una parte
importante de lo que se verifica es el comportamiento observable de stores y
páginas, no la cadena HTTP completa. Este documento separa ambas cosas.

---

## 2. Taxonomía de fallos que el frontend ya distingue

Fuente: `src/infrastructure/api/errors.ts`.

| Fallo | Helper que lo clasifica | Resultado | Tratamiento en UI |
|---|---|---|---|
| Axios sin `response` (red, DNS, timeout) | `isOfflineError` | `true` | `OfflineBanner` + caché local |
| `502` / `503` / `504` | `isOfflineError` | `true` | Igual que sin conexión, pero con el `detail` real |
| `500` de la Gateway | `isOfflineError` | `false` | `ErrorState` reintentable |
| `401` | interceptor de `apiClient` → `AuthProvider` | sesión expirada | Limpia sesión y va a `/login` |
| `403` | interceptor de `apiClient` → `AuthProvider` | acceso denegado | Va a `/acceso-denegado` |
| `404` / `409` / `422` | `isNotFoundError` / `isConflictError` | negocio | Mensaje del backend, sin reintento automático |
| Escritura sin respuesta, `502`-`504`, `500` con código de Gateway | `esResultadoIncierto` | `true` | Ofrece "comprobar" antes de repetir |

Además, `getApiErrorMessage` normaliza el `detail` (string o lista de validación de
FastAPI), `getApiErrorRequestId` lee `error.request_id` o la cabecera `X-Request-ID`,
y `getApiErrorCode` expone el código del catálogo de la Gateway
(`MICROSERVICIO_INALCANZABLE`, `GATEWAY_SATURADA`, `TIEMPO_AGOTADO`, etc.).

Esa clasificación es la pieza que hace que "fallo de red" signifique algo concreto en
las pruebas; por eso el estudio parte de ella.

---

## 3. Inventario medido

Ejecución con reporter JSON de Vitest sobre el commit `844fe3c`:

```
Test Files  129 passed (129)
Tests       1117 passed (1117)
```

Distribución por capa:

| Capa | Archivos | Pruebas |
|---|---:|---:|
| `domain/` (entidades y reglas) | 5 | 57 |
| `infrastructure/api/` (servicios, errores, React Query) | 14 | 136 |
| `infrastructure/stores/` (Zustand + caché/offline) | 6 | 54 |
| `presentation/` (componentes, hooks, páginas, rutas) | 104 | 870 |
| **Total** | **129** | **1117** |

El peso está en `presentation/`: la suite es, sobre todo, de **integración de UI con
stores y dominio**. No es una suite de integración HTTP.

---

## 4. Cómo se simulan hoy los fallos

| Mecanismo | Archivos que lo usan | Qué prueba y qué no |
|---|---:|---|
| `vi.mock('@/infrastructure/api/<Servicio>')` | 58 | Prueba la página/store contra un servicio falso: estados, mensajes, caché. **No** prueba el mapeo del contrato ni Axios. |
| `vi.mock('@/infrastructure/config/apiClient')` | 12 | Prueba URL, verbo y payload que arma cada servicio. **No** ejecuta interceptores ni timeout. |
| `apiClient.defaults.adapter` (Axios real) | 1 (`AuthProvider.test.tsx`) | Única prueba que atraviesa interceptores reales (`401`/`403`). No cubre timeout ni `Authorization`. |
| Fixtures `src/infrastructure/mocks/payloads.reales.ts` | Servicios, `errors.test.ts`, páginas | Cuerpos literales de la Gateway y de los microservicios; los 7 códigos del catálogo de errores. |
| MSW / nock / `axios-mock-adapter` | 0 | No instalados como dependencia directa. |
| Playwright / Cypress | 0 | No hay E2E ni pruebas en navegador real. |

Consecuencia: cuando una prueba dice "sin conexión", normalmente significa que el
**servicio mockeado rechazó** con un objeto con forma de `AxiosError`. Es una prueba
válida del comportamiento de la vista, pero no demuestra que Axios, el interceptor y
el store se comporten así sobre un transporte real.

---

## 5. Matriz de cobertura

| # | Escenario | Dónde está probado | Nivel | Cubierto |
|---|---|---|---|---|
| 1 | Lectura sin respuesta → offline + caché | `asyncCollection.test.ts`, `useOrderStore.test.ts`, `ClientVehiclesPage`, `AdminOrdersPage`, `MechanicVehiclesPage` | Store + página | Sí |
| 2 | Lectura `503` → offline con mensaje real | `errors.test.ts`, `asyncCollection.test.ts`, `ClientVehiclesPage`, `NotificationService.test.ts` | Clasificación + store + página | Sí |
| 3 | `500` no se disfraza de "sin conexión" | `errors.test.ts`, `AdminOrdersPage`, `ClientVehiclesPage`, `OrderStatusAndHistory` | Clasificación + página | Sí |
| 4 | Caché se conserva tras fallo | `asyncCollection.test.ts`, `useOrderHistoryStore`, `useOrderBitacoraStore`, páginas de cliente/admin | Store + página | Sí |
| 5 | Reintento manual desde `ErrorState` | `ErrorState.test.tsx`, `AdminVehiclesPage`, `ClientVehiclesPage`, `AdminDashboardPage` | Componente + página | Sí |
| 6 | Reintento automático solo de red/`5xx`, tope 2 | `queryClient.test.tsx` (7 pruebas) | Función pura + default de React Query | Sí |
| 7 | `4xx` deterministas no se reintentan | `queryClient.test.tsx` | Función pura | Sí |
| 8 | `X-Request-ID` visible y propagado | `OfflineBanner.test.tsx`, `asyncCollection.test.ts`, `errors.test.ts` | Componente + store + helper | Sí |
| 9 | `401` sesión expirada / `403` acceso denegado | `AuthProvider.test.tsx` con adaptador Axios real | Integración HTTP parcial | Sí |
| 10 | Escritura con resultado incierto | `AdminOrderDetailPage`, `AdminNuevaAtencionDetailPage`, `ClientBudgetDetailPage`, `MechanicBudgetPage`, `PresupuestoAplicacionPanel`, `RegistrarIngresoPanel` | Página + componente | Sí |
| 11 | Timeout de `apiClient` (30 s) y de evidencias (120 s) | — | — | **No** |
| 12 | Interceptor de request agrega `Authorization: Bearer` | — | — | **No** (solo indirecto) |
| 13 | Cadena completa servicio → Axios → store → UI sobre red real | — | — | **No** |
| 14 | Eventos `online`/`offline` del navegador (`navigator.onLine`) | — | — | **No** (no existe la funcionalidad) |
| 15 | `NotificationsPage` ante `503` y sin conexión | `NotificationService.test.ts` cubre el servicio; la página no tiene prueba | Servicio solamente | Parcial |
| 16 | Offline en `AdminInventoryAlertsPage`, `AdminInventoryMovementsPage`, `AdminStockDetailPage`, `AdminThresholdPage` | Tienen prueba de página, pero sin caso offline | Página | **No** |
| 17 | Offline en `OrderEvidencePage` / `OrderEvidenceSection` | `OrderEvidencePage.test.tsx` no prueba offline | Página/componente | **No** |
| 18 | `esResultadoIncierto` con tabla de casos | Solo cobertura indirecta vía componentes | — | Parcial |

---

## 6. Qué está bien cubierto

### 6.1 Clasificación de errores (26 pruebas)

`errors.test.ts` es la prueba más densa del área y usa los cuerpos reales de la
Gateway y de los microservicios. Cubre:

- offline para error no-Axios, Axios sin respuesta y `502`/`503`/`504`;
- que `500` y los errores de negocio **no** se marquen offline;
- prioridad del `detail` string, del primer `msg` de FastAPI y del fallback;
- mensajes propios de cada código del catálogo;
- `request_id` desde el cuerpo y desde la cabecera, incluido el caso "no inventar
  referencia";
- `getApiErrorCode` para clasificar sin parsear el mensaje.

Es la base que hace confiables las pruebas de páginas: si la clasificación cambia,
estas 26 pruebas fallan primero.

### 6.2 Stores con caché y offline centralizados (54 pruebas)

`asyncCollection.ts` concentra `fetchCollection` y `fetchItemById`; los stores
(`useOrderStore`, `useOrderHistoryStore`, `useOrderBitacoraStore`,
`useEvidenceStore`, `useAuthStore`) no repiten la lógica. `asyncCollection.test.ts`
(21 pruebas) verifica el contrato del helper:

- error de red → `isOffline` + caché conservada;
- `503` → offline, `500` → no offline;
- `404` confirmado no toca la caché;
- fallo sin copia local → `failed`, para que la vista muestre error y no un falso
  "no encontrado";
- `request_id` guardado y limpiado al reintentar con éxito;
- `isInitialLoad` evita el destello de estado vacío.

Este es el mejor nivel de integración que tiene hoy la suite: store real, helpers
reales, servicio mockeado en el borde.

### 6.3 Reintentos de React Query (7 pruebas)

`queryClient.test.tsx` prueba `shouldRetryQuery` como función pura: red sí, `5xx`
sí, `4xx` no, no-Axios no, tope de 2, y que sea el default de las consultas. También
verifica que el logging no vuelque el objeto de error (riesgo de filtrar el token).

### 6.4 Páginas con caché, banner y error reintentable (870 pruebas de presentación)

Casi todas las páginas que muestran `OfflineBanner` tienen al menos una prueba
explícita de offline o de error de servidor: cliente (`ClientOrdersPage`,
`ClientVehiclesPage`, `ClientServicesPage`, `ClientBudgetsPage`,
`ClientBudgetDetailPage`, `ClientServiceTracking`, `ClientOrderEvidencePage`),
mecánico (`MechanicVehiclesPage`, `MechanicStatusPage`, `MechanicOrdersPage`,
`MechanicOrderDetailPage`) y administración (`AdminOrdersPage`, `AdminVehiclesPage`,
`AdminOrderDetailPage`, `AdminClientsPage`, `AdminDistributorsPage`,
`AdminInventoryPage`, `AdminVehicleDetailPage`).

También hay pruebas específicas de **resultado incierto** en escrituras, que es el
caso más difícil: `ClientBudgetDetailPage` ("un 503 con decisión guardada ofrece
aplicar su ID sin volver a decidir"), `MechanicBudgetPage`, `PresupuestoAplicacionPanel`
("se recupera de otro 503", "no confirma éxito si el reintento falla") y
`AdminNuevaAtencionDetailPage` / `NuevaAtencionSection` ("Resultado incierto…
comprobar de nuevo").

### 6.5 La única prueba con Axios real

`AuthProvider.test.tsx` reemplaza `apiClient.defaults.adapter` y dispara `401`/`403`
de verdad, comprobando que el interceptor de respuesta llama al handler, que se
conserva la ruta pedida y que `StrictMode` no duplica la restauración. Es el patrón
que falta replicar para timeout y `Authorization`.

---

## 7. Huecos detectados

Ordenados por riesgo real, no por cantidad de pruebas.

### H1. No hay ninguna prueba de timeout

`apiClient` define `timeout: 30000` y `EvidenciaService` usa `120000` para subidas.
No hay prueba que rechace con `AxiosError` de timeout (`ECONNABORTED`) y verifique que
la UI lo presenta como fallo de conexión con reintento. Es el fallo de red más común
en producción y el único que no puede reproducirse con el mockeo actual de servicios.

### H2. El interceptor de `Authorization` no se prueba

Ninguna prueba verifica que, con token en almacenamiento, la petición salga con
`Authorization: Bearer <token>`, y que sin token no se agregue la cabecera. Un cambio
en `tokenStorage` o en el orden de los interceptores rompería toda la autenticación
sin que la suite lo note; las páginas seguirían verdes porque los servicios están
mockeados.

### H3. `NotificationsPage` no tiene prueba propia

Es la única página de datos sin archivo de prueba (junto con `HomePage`, que es
estática). Maneja carga, error, refresco, cambio de filtro, marcado de leídas y
respuesta obsoleta con `requestSeqRef`. Además, su `catch` colapsa **cualquier**
fallo en `'No se pudieron cargar las notificaciones.'`: no distingue red de servidor
ni usa `OfflineBanner`. El servicio sí está probado (`NotificationService.test.ts`,
incluido `503`), pero la página no.

### H4. Cuatro páginas admin con `OfflineBanner` no prueban el offline

`AdminInventoryAlertsPage`, `AdminInventoryMovementsPage`, `AdminStockDetailPage` y
`AdminThresholdPage` renderizan el banner y distinguen `isOffline`, pero sus pruebas
solo cubren datos, validación y errores de formulario. El patrón a copiar ya existe
en `AdminOrdersPage` ("queda offline con banner y conserva la caché").

### H5. `OrderEvidenceSection` se cubre solo de forma indirecta

`OrderEvidencePage.test.tsx` prueba contenido y `404`, pero no el fallo de red.
`OrderEvidenceSection` tiene `OfflineBanner`, `isOffline` y `refetch`, y no tiene caso
offline ni archivo propio.

### H6. `esResultadoIncierto` no tiene prueba unitaria

Es la función que decide si se ofrece "comprobar" en una escritura. Su condición
(`sin response` → incierto; `502`-`504` → incierto; `500` **solo** si hay código de
Gateway; resto definitivo) se ejercita a través de componentes, pero no hay una tabla
de casos en `errors.test.ts`. Un cambio sutil —por ejemplo, tratar todo `500` como
incierto— degradaría varios flujos sin una prueba focalizada que lo explique.

### H7. `isOfflineError` rotula como "sin conexión" cualquier error no-Axios

Está probado y es intencional (un fallo de transporte inesperado se presenta como
offline), pero implica que un `TypeError` de programación dentro de un `catch`
también se muestra como problema de red. Es una decisión de producto que conviene
dejar documentada y probada explícitamente si se mantiene.

### H8. No hay pruebas de integración HTTP ni E2E

No hay MSW, `axios-mock-adapter` ni Playwright/Cypress. Por lo tanto:

- no se prueba el mapeo servicio → Axios → store en una sola prueba;
- no se prueba el comportamiento real de `navigator.onLine` (que, por cierto, la app
  hoy no escucha: el estado offline se deriva de la respuesta, no del evento);
- no se prueba el flujo "Gateway caída → banner → Gateway vuelve → reintento" en un
  navegador.

---

## 8. Propuestas (no implementadas)

| # | Propuesta | Cubre | Esfuerzo | Prioridad |
|---|---|---|---|---|
| P1 | Añadir a `errors.test.ts` una tabla de casos de `esResultadoIncierto` (sin respuesta, `502`, `503`, `504`, `500` con y sin código, `409`, `404`, `422`) | H6 | Bajo | Alta |
| P2 | Copiar el caso offline de `AdminOrdersPage` a las 4 páginas admin y a `OrderEvidencePage` | H4, H5 | Bajo | Alta |
| P3 | Crear `NotificationsPage.test.tsx`: carga, error con reintento, `503`/sin conexión, refresco, filtro, marcar leída/todas, respuesta obsoleta | H3 | Medio | Alta |
| P4 | Probar timeout con `apiClient.defaults.adapter` que rechace con `AxiosError` `ECONNABORTED`; verificar mensaje offline y reintento. Igual para el timeout de 120 s de evidencias | H1 | Medio | Media |
| P5 | Probar el interceptor de request con adaptador real: con token envía `Bearer`, sin token no agrega cabecera | H2 | Bajo | Media |
| P6 | Introducir MSW como capa de red en pruebas de servicios (handlers por endpoint, `onUnhandledRequest: 'error'`), sin reemplazar los unit tests actuales | H8, H2, H1 | Medio | Media |
| P7 | E2E con Playwright y `context.setOffline(true)` para el ciclo offline → banner → reconexión → reintento | H8 | Alto | Baja |
| P8 | Si se decide reaccionar a `navigator.onLine`, probar los eventos `online`/`offline`; hoy no existe la funcionalidad y no corresponde probarla | H8 | Bajo | Baja |
| P9 | Documentar y probar la decisión de `isOfflineError` ante errores no-Axios | H7 | Bajo | Baja |

### Orden sugerido

1. **P1 + P2 + P3** cierran los huecos de mayor valor con bajo costo y sin nuevas
   dependencias: son pruebas que faltan, no infraestructura nueva.
2. **P4 + P5** cubren la capa Axios real con el patrón que ya existe en
   `AuthProvider.test.tsx`.
3. **P6** solo si se quiere subir el nivel de integración de forma sistemática;
   exige instalar y configurar MSW y decidir dónde vive el `setup` de handlers.
4. **P7/P8** quedan fuera del alcance de una tarea de estudio y dependen de tener el
   backend levantado en CI.

---

## 9. Cómo se reproduce este inventario

```powershell
cd frontend
npm run test                     # 129 archivos / 1117 pruebas
npx vitest run --reporter=json --outputFile="$env:TEMP\vitest-frontend.json"
npm run build
```

Comandos usados para medir:

- archivos y pruebas: reporter JSON de Vitest (`numTotalTestSuites`,
  `numTotalTests`, `assertionResults`);
- mockeo de servicios: búsqueda de `vi.mock('@/infrastructure/api/…')` en `src/`;
- mockeo de `apiClient`: búsqueda de `vi.mock('@/infrastructure/config/apiClient')`;
- adaptador real: búsqueda de `defaults.adapter`;
- páginas con `OfflineBanner`: búsqueda del componente en `src/presentation/` y
  comprobación de la existencia de `<archivo>.test.tsx`.

---

## 10. Conclusión

La suite actual **sí prueba fallos de red y de servicios**, y lo hace bien en el
nivel que eligió: clasificación de errores, stores con caché, reintentos
inteligentes, estados de carga y páginas con banner/error reintentable. Las 26
pruebas de `errors.test.ts`, las 21 de `asyncCollection.test.ts` y las 7 de
`queryClient.test.tsx` forman un núcleo sólido, y las pruebas de "resultado incierto"
cubren el caso más delicado de las escrituras.

El hueco no es de cantidad sino de **nivel de integración**. Todo fallo de red se
simula con objetos que imitan a Axios o con servicios mockeados; solo una prueba
(`AuthProvider.test.tsx`) atraviesa Axios de verdad, y ninguna cubre timeout,
`Authorization` ni la cadena completa servicio → store → UI sobre un transporte. A
eso se suman huecos concretos y acotados: `NotificationsPage`, cuatro páginas admin
con banner sin caso offline, `OrderEvidencePage` y la falta de prueba unitaria de
`esResultadoIncierto`.

Cerrar P1-P3 es barato y de alto valor; P4-P5 completan la capa Axios con el patrón
ya existente; MSW y E2E solo se justifican si se quiere subir el nivel de forma
permanente. Este estudio deja el mapa y las prioridades; no modifica la suite.
