# Manejo global de errores y estados de carga

**Tarea (Semana 10):** Mejorar manejo global de errores y estados de carga
**Alcance:** Frontend Web (React) — capas transversales de captura de errores, reintentos de consultas, sesión expirada, timeouts, estados de carga y registro seguro de fallos.
**Base:** rama `Gustavo` sincronizada con `Develop` (commit base `b12f0ae`).

## 1. Problema detectado

Antes de esta tarea, los errores y las cargas se resolvían pantalla por pantalla, con
comportamientos distintos según la vista. Los puntos concretos:

| # | Síntoma | Causa |
|---|---|---|
| 1 | Un error de render dejaba la app en blanco o en la pantalla de error hasta recargar manualmente | `ErrorBoundary` capturaba el error, pero no ofrecía recuperación al navegar |
| 2 | Consultas que fallaban con 400/401/404 se reintentaban igual que un 5xx | React Query configurado con `retry: 1` global |
| 3 | Fallo de consulta sin rastro útil en consola | No había logging centralizado con `X-Request-ID` |
| 4 | Token vencido devolvía al login sin explicar por qué | El handler de 401 limpiaba la sesión y navegaba en silencio |
| 5 | Destello del estado vacío (o de un error previo) antes de los datos | Las vistas solo miraban `status === 'loading'`, pero los stores parten en `idle` |
| 6 | Petición colgada = spinner para siempre | `apiClient` no tenía timeout |
| 7 | Riesgo de filtrar el token de acceso en consola | Volcar un `AxiosError` completo imprime `config.headers.Authorization` |
| 8 | Centro de avisos mostraba un texto plano como carga | No reutilizaba el componente `LoadingState` del design system |

## 2. ErrorBoundary con recuperación y dos capas

### 2.1 `ErrorBoundary` (`src/presentation/components/ui/ErrorBoundary.tsx`)

- Nueva prop opcional `resetKey`: al cambiar su valor se descarta el error capturado y
  se vuelve a intentar el render.
- El reinicio se implementa con `getDerivedStateFromProps` (no con `setState` dentro de
  `componentDidUpdate`), para no encadenar un segundo render tras cada actualización ni
  disparar la regla `react/no-did-update-set-state`.
- No remonta a los hijos sanos ni a los providers: solo se limpia `hasError`.
- `componentDidCatch` registra **nombre + mensaje + `componentStack`**, nunca el objeto
  `error` completo.

### 2.2 `RouteErrorBoundary` (`src/presentation/components/ui/RouteErrorBoundary.tsx`)

- Envuelve a `AppRoutes` y usa `location.pathname` como `resetKey`.
- Consecuencia: si una página falla al renderizar, el usuario puede navegar a otra y la
  app se recupera sin recargar; la sesión, los toasts y la campana siguen vivos.

### 2.3 Montaje en `App.tsx`

```
QueryClientProvider
└─ BrowserRouter
   └─ ErrorBoundary                ← errores de providers (fallback con recarga)
      └─ AuthProvider
         └─ ToastProvider
            ├─ RouteChangeFocus
            └─ RouteErrorBoundary  ← errores de página (se recuperan al navegar)
               └─ AppRoutes
```

La capa externa cubre fallos de `AuthProvider`/`ToastProvider`; la interna cubre las
páginas y es la que se reinicia con la navegación.

## 3. Reintentos inteligentes y logging de React Query

`src/infrastructure/api/queryClient.ts` centraliza la instancia que antes se creaba suelta
en `App.tsx`:

- **`shouldRetryQuery(failureCount, error)`**:
  - Reintenta solo fallos potencialmente transitorios: sin respuesta (red caída o
    timeout) o respuesta `5xx`.
  - Un `4xx` (400/401/403/404/409/422) es determinista: falla de inmediato y la vista
    muestra su `ErrorState` con reintento manual.
  - Tope de **2 reintentos** (`MAX_REINTENTOS_QUERY`), no infinitos.
- **`QueryCache.onError`** registra una sola línea con:
  - `queryKey` serializada,
  - mensaje normalizado (`getApiErrorMessage`),
  - `request-id` de la Gateway (`X-Request-ID`) cuando existe.
- Nunca se pasa el objeto `error` a `console`: un `AxiosError` incluye
  `config.headers.Authorization`, es decir, el token en claro.

## 4. Sesión expirada informada (401)

- `AuthProvider` guarda si la sesión estaba activa al recibir el 401 antes de limpiarla
  (`isAuthenticated`). Solo en ese caso navega a `/login` con
  `state.sesionExpirada = true`.
- Abrir la app con un token ya vencido durante la restauración **no** se anuncia como
  “sesión expirada”: nunca hubo sesión que expirar.
- `LoginPage` muestra un `Alert` warning: “Tu sesión ha expirado. Inicia sesión
  nuevamente para continuar.” No se muestra si hay error de credenciales o si se está en
  modo registro.

## 5. Estados de carga sin destellos

`src/infrastructure/stores/asyncCollection.ts` añade el helper:

```ts
isInitialLoad(status, hasData):
  status === 'loading' || (status === 'idle' && !hasData)
```

- `loading` mantiene el skeleton también durante un refetch (los datos no “parpadean”).
- `idle` sin datos cubre el primer render, antes de que el `useEffect` dispare el fetch
  (los stores parten en `idle`).
- `idle` con datos en caché no bloquea la vista.

### Vistas actualizadas (9)

| Portal | Página |
|---|---|
| Cliente | `ClientOrdersPage`, `ClientServicesPage`, `ClientVehiclesPage` |
| Mecánico | `MechanicDashboardPage`, `MechanicOrdersPage`, `MechanicStatusPage`, `MechanicVehiclesPage` |
| Administrador | `AdminOrdersPage`, `AdminVehiclesPage` |

El cambio es mecánico (`status === 'loading'` → `isInitialLoad(status, <datos>.length > 0)`),
preservando filtros, estados de error y lógica existente.

> Las páginas de administración que manejan su carga con `useState('loading')` local no
> presentan este destello y **no se modificaron**. `useClientBudgets` ya arranca en
> `loading` y también queda fuera.

`NotificationsPage` pasa a usar el `LoadingState` compartido (spinner + mensaje dentro de
`role="status"`), en lugar de un texto plano.

## 6. Timeouts de red

| Petición | Timeout | Razón |
|---|---:|---|
| `apiClient` general (`src/infrastructure/config/apiClient.ts`) | 30 s | Evita spinners eternos si la Gateway no responde; al vencer se trata como fallo de conexión con reintento |
| Subida de evidencias (`EvidenciaService`) | 120 s | Archivos de hasta 12 MB en redes lentas; no debe cortarse con el tope general |

Las descargas usan la URL prefirmada directamente en el navegador, por lo que no pasan
por `apiClient`.

## 7. Comportamiento resultante por escenario

| Escenario | Comportamiento |
|---|---|
| Red caída o timeout | Reintento automático (hasta 2), luego `ErrorState` con reintento manual y mensaje de conexión |
| `5xx` | Igual que red caída: reintento acotado y estado de error reintentable |
| `4xx` | Sin reintentos; la vista muestra el mensaje específico del backend |
| `401` con sesión activa | Limpieza de sesión, redirección a `/login` con aviso de sesión expirada |
| `401` durante restauración | Limpieza silenciosa; no se anuncia expiración |
| Error de render en una página | Pantalla de error del boundary; al navegar se reintenta sin recargar |
| Error de render en un provider | Pantalla de error global con botón “Recargar página” |
| Consulta fallida | Log centralizado con `queryKey`, mensaje y `request-id`, sin token |
| Primer render de una colección | Skeleton (no estado vacío fugaz) |

## 8. Pruebas

Se agregaron **20 pruebas** (2 archivos nuevos):

| Archivo | Cobertura |
|---|---|
| `ui/ErrorBoundary.test.tsx` | Captura de error + reinicio por `resetKey` sin remontar hijos |
| `ui/RouteErrorBoundary.test.tsx` (nuevo) | Reset al cambiar de ruta y conservación del fallback |
| `api/queryClient.test.tsx` (nuevo) | `shouldRetryQuery` (red, 5xx, 4xx, tope) y logging sin token |
| `stores/asyncCollection.test.ts` | `isInitialLoad` en `idle`/`loading`/`success`/`error` con y sin datos |
| `auth/AuthProvider.test.tsx` | 401 con sesión activa marca `sesionExpirada`; 401 en restauración no |
| `auth/LoginPage.test.tsx` | Aviso visible con `sesionExpirada`; ausente sin él |

Resultado: **129 archivos / 1117 pruebas aprobadas** (base anterior: 127 / 1097).
`tsc -b` y `vite build` sin errores. Lint sin errores; quedan solo dos warnings
preexistentes de `react(set-state-in-effect)` en `NotificationBell` y `NotificationsPage`.

## 9. Decisiones y límites

1. **No se cambió `initialAsyncStatus` a `loading`**: eso rompería la semántica de “aún no
   se ha pedido nada” que usan los stores y las pruebas de restauración. El destello se
   corrige en la vista con `isInitialLoad`.
2. **Solo se tocaron 9 páginas con store zustand** (las que parten en `idle`). Las de
   administración con `useState('loading')` local no tenían el problema.
3. **No se remontan providers**: el reinicio del boundary es de estado, no de árbol, para
   no perder sesión, toasts ni caché.
4. **El logging es deliberadamente conservador**: solo cadenas armadas con helpers
   seguros; jamás el objeto `error`.
5. **No hay verificación manual en navegador** en esta ejecución: la validación se hizo
   con la suite Vitest/RTL, `tsc -b` y build de producción.

## 10. Archivos principales

| Archivo | Cambio |
|---|---|
| `src/presentation/components/ui/ErrorBoundary.tsx` | `resetKey` + logging seguro |
| `src/presentation/components/ui/RouteErrorBoundary.tsx` | Nuevo wrapper con `useLocation` |
| `src/App.tsx` | Doble capa de boundaries + `createQueryClient` |
| `src/infrastructure/api/queryClient.ts` | Reintentos selectivos + `QueryCache.onError` |
| `src/infrastructure/stores/asyncCollection.ts` | Helper `isInitialLoad` |
| `src/presentation/components/auth/AuthProvider.tsx` | `sesionExpirada` en 401 |
| `src/presentation/pages/auth/LoginPage.tsx` | `Alert` de sesión expirada |
| `src/infrastructure/config/apiClient.ts` | Timeout global de 30 s |
| `src/infrastructure/api/EvidenciaService.ts` | Timeout de 120 s en subida |
| `src/presentation/pages/shared/NotificationsPage.tsx` | `LoadingState` compartido |
| 9 páginas de cliente/mecánico/admin | `isInitialLoad` en el skeleton |

- **Fecha de registro:** 2026-11-12
- **Responsable:** Gustavo Rosa (Frontend Web React)
