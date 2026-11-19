# Pruebas: timeouts, respuestas 5xx y pérdida temporal de conectividad

**Tarea (Semana 10):** Probar timeouts, respuestas 5xx y pérdida temporal de conectividad
**Alcance:** Frontend Web (React) — capa de red real (Axios), clasificación de errores, reintentos de React Query y recuperación de los stores con caché.
**Base:** rama `Gustavo`, commit `a0b475f` (incluye el estudio previo `estudio-pruebas-integracion-fallos-red-servicios.md`).
**Entregable:** pruebas automatizadas nuevas y su evidencia de ejecución. No se modificó código de producción.

## 1. Qué se buscaba

El estudio previo dejó dos huecos concretos en la cobertura de fallos de red:

| Hueco del estudio | Estado antes | Qué se hizo |
|---|---|---|
| H1 — No había ninguna prueba de timeout | Sin cobertura | Pruebas con el adaptador real de Axios: `ECONNABORTED` en consultas y en subida de evidencias |
| H6 — `esResultadoIncierto` sin prueba unitaria | Solo cobertura indirecta | Tabla de casos en `errors.test.ts` |
| 5xx a nivel de transporte | Solo helpers con objetos imitando Axios | Respuestas `500`/`502`/`503`/`504` atravesando Axios de verdad |
| Pérdida temporal de conectividad | Casos aislados en páginas y stores | Ciclo caída → caché conservada → reintento exitoso, con Axios y React Query reales |

La diferencia con las pruebas que ya existían es el **nivel**: antes se mockeaba el
servicio (`vi.mock`) y se le entregaba un objeto con forma de `AxiosError`. Ahora se
reemplaza solo el adaptador de Axios (`apiClient.defaults.adapter`), de modo que la
petición pasa por:

```
apiClient → interceptores → adaptador simulado → clasificación de errores
          → React Query o fetchCollection → estado que consume la vista
```

No se añadieron dependencias (ni MSW ni Playwright): el patrón ya existía en
`AuthProvider.test.tsx` y se reutiliza.

## 2. Cómo se simula cada fallo

| Fallo | Cómo se construye | Qué representa |
|---|---|---|
| Timeout | `AxiosError` con código `ECONNABORTED` y **sin** `response` | Axios corta al vencer `config.timeout` |
| Red caída | `AxiosError` con código `ERR_NETWORK` y sin `response` | DNS, CORS, conexión cortada |
| `5xx` | `AxiosError` con `response.status` y el cuerpo real de la Gateway | El servidor respondió con error |
| Recuperación | El adaptador falla las primeras N llamadas y luego responde `200` | La conectividad vuelve y el usuario reintenta |

Los cuerpos `502/503/504/500` son los fixtures reales de
`src/infrastructure/mocks/payloads.reales.ts`, no textos inventados.

## 3. Matriz de escenarios probados

### 3.1 Timeouts

| # | Escenario | Resultado esperado | Prueba |
|---|---|---|---|
| 1 | Configuración del cliente | `apiClient` corta a los 30 s; la subida de evidencias usa 120 s | `el cliente general corta a los 30 s y la subida de evidencias a los 120 s` |
| 2 | Timeout en una consulta | `isOfflineError` true, mensaje de conexión, reintento automático y resultado incierto | `un timeout se presenta como caída de conexión y es reintentable` |
| 3 | Timeout subiendo evidencia | Se trata como fallo de conexión, no como rechazo del servidor | `un timeout durante la subida de evidencia no se confunde con un rechazo del servidor` |

### 3.2 Respuestas 5xx

| # | Respuesta | ¿Offline? | Mensaje | ¿Reintenta? | ¿Resultado incierto? |
|---|---|---|---|---|---|
| 4 | `500` con cuerpo de la Gateway | No | El `detail` real | Sí | Sí (trae código) |
| 5 | `502` | Sí | El `detail` real | Sí | Sí |
| 6 | `503` | Sí | El `detail` real | Sí | Sí |
| 7 | `504` | Sí | El `detail` real | Sí | Sí |
| 8 | `500` propio del microservicio (solo `detail`) | No | El `detail` real | Sí | **No** (rechazo definitivo) |

Además, `errors.test.ts` incorpora la tabla unitaria de `esResultadoIncierto`:
sin respuesta, error no-Axios, `502`-`504`, `500` con código de Gateway, `500` sin
código, `400/401/403/404/409/422`. Es la decisión que habilita el botón
"comprobar" antes de repetir una escritura.

### 3.3 Pérdida temporal de conectividad

| # | Escenario | Resultado esperado | Prueba |
|---|---|---|---|
| 9 | Colección con caché: primer intento sin red | `status: error`, `isOffline: true`, mensaje de conexión y **items de caché intactos** | `la caché se conserva durante la caída y el reintento la actualiza al volver la red` |
| 10 | Reintento con la red de vuelta | `status: success`, `isOffline: false`, `error: null`, datos actualizados | Misma prueba |
| 11 | Detalle con copia local: primer intento con timeout | Devuelve el item cacheado, `failed: false`, `isOffline: true` | `el detalle conserva la copia local cuando la red cae y se actualiza al reintentar` |
| 12 | Detalle al reintentar | Item actualizado del servidor, `isOffline: false` | Misma prueba |
| 13 | React Query con `503` transitorio | Reintenta y termina en `success` tras 3 intentos (inicial + 2) | `React Query reintenta un 503 transitorio y termina mostrando los datos` |
| 14 | React Query con `503` persistente | Se detiene tras 2 reintentos, queda en `error` y registra el fallo con mensaje y `request-id` | `si el 503 persiste, React Query se detiene tras dos reintentos y deja el error` |

## 4. Resultado de la ejecución

```
Test Files  133 passed (133)
Tests       1166 passed (1166)
```

- Antes de la tarea: 132 archivos / 1148 pruebas.
- Nuevas: **1 archivo / 18 pruebas** (12 de red + 6 de `esResultadoIncierto`).
- `npm run build`: `tsc -b && vite build` correcto.
- `npm run lint`: sin errores nuevos (se mantienen dos advertencias previas en
  `NotificationsPage` y `NotificationBell`).

Comandos usados:

```powershell
cd frontend
npx vitest run src/infrastructure/api/resilienciaRed.test.tsx src/infrastructure/api/errors.test.ts
npm run test
npm run build
npm run lint
```

## 5. Decisiones y limitaciones

1. **El timeout se simula rechazando el adaptador**, no esperando 30 segundos reales.
   Así la prueba verifica la clasificación y el reintento sin volver lenta la suite.
   Que Axios respete `config.timeout` es comportamiento del propio Axios; la prueba
   fija el valor configurado por la app (30 s / 120 s) y el tratamiento del rechazo.
2. **No se prueban los eventos `online`/`offline` del navegador** porque la app no
   los escucha: el estado offline se deriva de la respuesta de la API. La
   "conectividad temporal" se prueba como caída y recuperación de la petición.
3. **No hay E2E ni MSW.** Cubrir el ciclo en un navegador real requeriría Playwright
   con `context.setOffline(true)` y backend levantado en CI; queda fuera del alcance
   de esta tarea.
4. **El reintento de escrituras sigue siendo manual y consciente.** Las pruebas
   confirman que un timeout o un `502`-`504` marcan la escritura como incierta; no se
   añadió reintento automático de escrituras para no duplicar operaciones.
5. **Los 5xx se siguen reintentando en consultas** (decisión previa de
   `shouldRetryQuery`), con tope de 2. Las pruebas confirman que un `503` persistente
   termina en error en lugar de reintentar indefinidamente.

## 6. Archivos

| Archivo | Cambio |
|---|---|
| `src/infrastructure/api/resilienciaRed.test.tsx` | Nuevo: 12 pruebas sobre el adaptador real de Axios |
| `src/infrastructure/api/errors.test.ts` | 6 pruebas nuevas de `esResultadoIncierto` |

- **Fecha de registro:** 2026-11-12
- **Responsable:** Gustavo Rosa (Frontend Web React)
