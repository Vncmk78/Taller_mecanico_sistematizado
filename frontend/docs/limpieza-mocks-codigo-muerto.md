# Limpieza de mocks, componentes muertos y código temporal

**Tarea (Semana 11):** Eliminar mocks componentes muertos y código temporal
**Alcance:** Frontend Web (React). Sin backend, sin móvil, sin cambios de diseño.
**Entregable:** código + ajustes de pruebas + este documento. Commit `477305f` en
`Gustavo`, promovido por `Develop` → `main` → `kubero-deploy`.
**Base:** rama `Gustavo`, commit `5a5dd64`, sincronizada con `origin/Gustavo` antes de empezar.

## 1. Metodología

Se inventariaron los 354 archivos `.ts/.tsx` de `frontend/src` y se resolvieron
2029 sentencias de import/export (alias `@/` incluido) hacia 216 destinos únicos.
Además se hicieron búsquedas por nombre base y por símbolo exportado en **los 354
archivos, incluidos los tests**, y un recorrido de alcanzabilidad desde `main.tsx`.
También se revisaron `index.html`, `vite.config.ts` y `package.json`.

Regla aplicada: **si un archivo o símbolo lo usa un test, no es muerto** y no se elimina.

## 2. Eliminado

### 2.1 Componente muerto y su constants huérfana (no eliminados en el resultado final)

En el análisis sobre `Gustavo` (`5a5dd64`), `src/presentation/components/ui/Pagination.tsx`
y `src/presentation/constants/pagination.ts` no tenían imports entrantes y parecían
duplicados de `components/orders/OrderPagination.tsx`, por lo que el commit de limpieza
los eliminó.

Al promover a `main`, ese branch ya incluía el trabajo de otro integrante
(`0ffdae1 feat(paginacion): unificar los listados operativos de MS1, MS2 y MS4`), que
adopta `ui/Pagination` en 12 pantallas y `constants/pagination.ts` desde
`hooks/useClientPagination.ts`. En la resolución del conflicto se conservó **su versión
de ambos archivos**: eliminarlos habría borrado una feature ajena recién integrada.
El efecto neto en `main`/`kubero-deploy` es que estos dos archivos **siguen presentes**;
la limpieza efectiva se limita a §2.2 y §2.3.

### 2.2 Exportaciones sin uso

| Archivo | Símbolo | Motivo |
|---|---|---|
| `src/presentation/components/ui/Table.tsx` | `TableEmptyState` | Una sola coincidencia en todo `src`: su propia declaración. El resto de exportaciones de `Table` sí se usan |
| `src/domain/entities/Evidencia.ts` | `TAMANO_MAXIMO_EVIDENCIA_BYTES` | Una sola coincidencia: su declaración. El límite de 12 MiB se aplica con literal en `utils/evidenceValidation.ts:25` |

### 2.3 Campo demo residual del historial

`OrderHistoryEntry.usuarioNombre` estaba marcado como *«Solo presentación/demo: no
viene en el contrato del historial»*. Confirmado: `OrderService.mapHistorialApi()`
no lo puebla, por lo que en producción la línea de tiempo ya mostraba
`Usuario <id>`; el nombre solo existía en los fixtures de test.

Se eliminó el campo de la entidad y de todos sus consumidores:

- `domain/entities/OrderHistory.ts`: se quita el campo y su comentario.
- `presentation/components/orders/OrderHistoryTimeline.tsx`: la rama `origen ===
  'usuario'` muestra directamente `Usuario ${actorUsuarioId ?? '?'}`.
- `infrastructure/mocks/orders.history.mock.ts`: se quitan 10 asignaciones del
  campo (el mock sigue vivo y lo usan 2 pruebas).
- Pruebas ajustadas: `OrderHistoryTimeline.test.tsx`,
  `OrderStatusAndHistory.test.tsx`, `OrderStatusAndHistory.reuse.test.tsx`,
  `ClientServiceTracking.test.tsx`, `useOrderHistory.test.ts` y
  `useOrderHistoryStore.test.ts`. Las aserciones que esperaban nombres ahora
  esperan `Usuario 1`, que es lo que realmente renderiza la API.
- `infrastructure/stores/useOrderHistoryStore.ts`: se actualizó un comentario que
  aún hablaba de «demos de la misma orden».

## 3. Revisado y conservado (con evidencia)

| Elemento | Resultado |
|---|---|
| 5 archivos de `infrastructure/mocks/` | **Todos usados por tests**. `budgets.mock` (3 tests), `evidence.mock` (5), `orders.history.mock` (2), `payloads.reales` (10), `vehicles.mock` (2). No se elimina ninguno |
| `mockEvidenciaFiltro`, `mockEvidenciaVideo`, `repuestoBitacoraReal` | No se importan directamente, pero se consumen dentro de su propio archivo para componer fixtures que sí se usan. No son código muerto |
| 50 exportaciones «solo internas» | Se usan dentro de su propio archivo; quitar `export` no aporta y eliminar el símbolo rompería el archivo. Sin cambios |
| Dependencias de `package.json` | Las 24 tienen uso real |
| Código comentado | Sin bloques de JSX/TS inactivos; las rachas largas son JSDoc |
| `TODO` / `FIXME` / `debugger` | Ninguno. Los 2 `console.error` existentes son manejores de error legítimos |
| URLs hardcodeadas | Ninguna fuera de fixtures de test |

## 4. Verificación

| Comando | Resultado |
|---|---|
| `npm run lint` | Sin errores; las 2 advertencias preexistentes de notificaciones siguen igual |
| `npm test` | 135 archivos, 1181 pruebas: **1179 pasan y 2 fallan**, los ya conocidos de `src/infrastructure/api/contratosOpenApi.test.ts` (archivo no versionado, ajeno) |
| `npm run build` | Correcto (`tsc -b && vite build`), 2159 módulos |
| Pruebas focalizadas de historial/tablas/evidencias | 8 archivos, 55 pruebas, todas pasan |
| Búsqueda final | 0 coincidencias de `usuarioNombre`, `TAMANO_MAXIMO_EVIDENCIA_BYTES` ni `TableEmptyState`. Los archivos de paginación se conservan según §2.1 |

## 5. Archivos modificados

En el resultado final de `main`: 12 archivos editados (entidad, mock, store,
componente de timeline, tabla y 7 pruebas), más este documento. Los 2 archivos de
paginación se restauraron desde `main` durante la resolución del conflicto (§2.1).
No se tocaron los archivos no versionados ajenos
`contratosOpenApi.test.ts` ni `diseno-responsive-accesibilidad-admin.md`, ni el
documento de estudio anterior `estudio-herramientas-navegador-diagnostico.md`.
