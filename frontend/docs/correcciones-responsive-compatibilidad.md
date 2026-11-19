# Correcciones de problemas responsive y de compatibilidad detectados

**Tarea (Semana 11):** Corregir problemas responsive y de compatibilidad detectados
**Alcance:** Frontend Web (React). Sin backend, sin móvil, sin cambios de paleta ni rediseño.
**Entregable:** código + pruebas + este documento. **No se crea commit.**
**Base:** rama `Gustavo`, commit `a42c370` (sincronizada con `origin/Gustavo`; `origin/main` y
`origin/Develop` tenían avances de otros integrantes, ninguno del frontend web).

## 1. Origen de los hallazgos

1. **Lighthouse sobre `/login`** en el estudio previo de herramientas del navegador:
   `target-size` (botón «Mostrar contraseña» de 20×20 px), accesibilidad 0.95.
2. **Revisión de patrones** de `frontend/src` (áreas táctiles, viewport, anchos fijos,
   APIs de navegador y configuración de build), siguiendo los lineamientos de
   `diseno-responsive-accesibilidad-admin.md` y `revision-responsividad.md`.

Se corrigieron los defectos con impacto claro y solución acotada. Los de menor severidad
o que requieren una decisión de soporte de navegadores quedan registrados en §5.

---

## 2. Correcciones aplicadas

### 2.1 Áreas táctiles (objetivo ≥ 44×44 px)

| Componente | Antes | Después |
|---|---|---|
| `ui/Input.tsx` | sin soporte para controles finales | nueva prop `trailingControl`: reserva `pr-14` y centra el control con `absolute inset-y-0 right-2` |
| `auth/LoginPage.tsx`, `auth/RegisterPage.tsx` | botón de visibilidad de 20×20 posicionado a `top-[42px]` | mismo botón de 44×44 vía `trailingControl`, centrado sobre el input y sin solapar el texto |
| `layout/UserMenu.tsx` | logout sin padding (~20 px), presente en los 3 portales | `inline-flex h-11 w-11` + hover de fondo |
| `layout/TopBar.tsx` | botón de menú móvil `p-2` (~36 px) | `h-11 w-11` |
| `layout/SidebarNav.tsx` | cierre del drawer `p-1.5` (~32 px) | `h-11 w-11` |
| `ui/ConfirmDialog.tsx`, `evidence/EvidencePreviewDialog.tsx` | cierre ~20 px en `right-4 top-4` | `h-11 w-11` en `right-2 top-2` |
| `ui/Toast.tsx` | cierre de 16 px (`w-4 h-4`) | `h-11 w-11` con icono `w-5 h-5` |
| `notifications/NotificationBell.tsx` | campana 40×40, «Leer todas» ~28 px, cierre ~28 px | campana 44×44, «Leer todas» `min-h-11` con `aria-label`, cierre 44×44 |

### 2.2 Viewport dinámico (barras de navegador en móvil)

`100vh` usa el viewport máximo, por lo que el contenido inferior queda tapado por las
barras del navegador. Se agregó en `src/index.css`:

```css
:root { --viewport-height: 100vh; }
@supports (height: 100dvh) {
  :root { --viewport-height: 100dvh; }
}
```

Todas las alturas de viewport (`min-h-screen`, `lg:h-screen`, `max-h-[65vh]`,
`max-h-[70vh]`, `min-h-[60vh]`) pasaron a `min-h-[var(--viewport-height)]`,
`lg:h-[var(--viewport-height)]` o `max-h-[calc(var(--viewport-height)*0.65)]`
según el caso. Afecta a `RoleLayout`, `SidebarNav`, `EvidencePreviewDialog`,
`NotificationBell`, `LoginPage`, `RegisterPage`, `HomePage`, `AccessDeniedPage`,
`ClientProfileGate`, `ErrorBoundary`, `FullScreenLoader` y `ClientDashboardPage`.

> Nota técnica: no basta con poner `h-screen h-dvh` juntas. Tailwind emite la regla
> `dvh` **antes** que la `vh`, así que la última gana y se pierde el soporte dinámico.
> La variable CSS con `@supports` sí degrades correctamente. Verificado en el CSS
> compilado y en el navegador (`--viewport-height` resuelve a `100dvh`).

### 2.3 Diálogo de formularios

`ui/FormModal.tsx` era el único diálogo `aria-modal="true"` sin `useDialogFocus`: no
movía el foco al abrir, no lo atrapaba y no respondía a `Escape`. Se alineó con
`ConfirmDialog`: `ref`, `tabIndex={-1}`, `onKeyDown` del hook y listener de `Escape`.
El botón de cierre también pasó a 44×44.

### 2.4 Preferencia de movimiento reducido

`src/index.css` no tenía ninguna regla `prefers-reduced-motion` y `scroll-behavior: smooth`
era global. Se agregó el bloque `@media (prefers-reduced-motion: reduce)` que anula
animaciones, transiciones y scroll suave, y se acotó `.card` de `transition: all` a
`box-shadow`, `border-color` y `transform`.

### 2.5 Compatibilidad de `crypto.randomUUID()`

Tres páginas lo usaban como clave de idempotencia al liberar/reservar stock. La API
requiere contexto seguro y navegador moderno; en HTTP plano (desarrollo por IP) puede
no existir y lanzar `TypeError`. Se creó `infrastructure/utils/idOperacion.ts` con
`generarIdOperacion()`: usa `randomUUID` si existe, si no construye un UUID v4 con
`getRandomValues`, y como último recurso un UUID no criptográfico. Se adoptó en
`MechanicOrderDetailPage`, `AdminOrderDetailPage` y `AdminInventoryMovementsPage`.

### 2.6 Desbordes y textos largos

- `AppNavLink` (variante sidebar): `min-w-0` en el enlace y `truncate` en la etiqueta;
  antes `whitespace-nowrap shrink-0` recortaba títulos de sección sin ellipsis.
- `AdminLayout`: el buscador global pasó de `w-[220px] lg:w-[350px]` a
  `w-full min-w-0 max-w-[220px] lg:max-w-[350px]` para no forzar ancho en tablet.

---

## 3. Pruebas agregadas

| Archivo | Caso |
|---|---|
| `ui/Input.test.tsx` | reserva `pr-14` y renderiza el control final; mantiene `pr-4` sin él |
| `pages/auth/LoginPage.test.tsx` | botón de contraseña con `h-11 w-11` |
| `ui/FormModal.test.tsx` | foco en el diálogo al abrir y cierre con `Escape` |
| `infrastructure/utils/idOperacion.test.ts` | usa `randomUUID`, fallback con `getRandomValues`, sin `crypto`, unicidad |

---

## 4. Verificación

| Comando / comprobación | Resultado |
|---|---|
| `npm run lint` | Sin errores; las 2 advertencias preexistentes de notificaciones siguen igual |
| `npm run build` | Correcto (`tsc -b && vite build`) |
| `npm test` | 135 archivos, 1181 pruebas: **Solo los 2 fallos preexistentes** de `src/infrastructure/api/contratosOpenApi.test.ts` (archivo no versionado, ajeno a esta tarea) |
| Navegador local (`/login`, build de producción) | Botón «Mostrar contraseña» **44×44**; `--viewport-height` = `100dvh`; `scrollWidth === clientWidth` (sin desborde horizontal) |
| Lighthouse antes | Accessibilidad **0.95** (`target-size`), Best Practices 1.00, SEO 0.60 |
| Lighthouse después | Accesibilidad **1.00**, Best Practices 1.00, SEO 0.60 (quedan `meta-description` y `robots.txt`, fuera de este alcance) |

La medición se repitió sobre `http://127.0.0.1:4173/login` servido desde `dist/`, no
sobre la web de producción, para no exponer credenciales ni afectar el despliegue.

---

## 5. No abordado (registro para seguimiento)

| Hallazgo | Motivo |
|---|---|
| Botones de paginación (~28-30 px), chips de `EvidenceContextFilter`, enlaces «Reintentar» | Baja severidad; ajustarlos de forma masiva puede alterar densidad de listados ya validada |
| `whitespace-nowrap` en badges e importes aislados | Riesgo bajo y ya mitigado por `overflow-x-auto` del componente `Table` y `truncate` en entidades |
| Grids fijos de 2 columnas en 3 vistas puntuales | Baja severidad; requiere revisión visual de cada pantalla |
| Diálogo de notificaciones sin `Escape`/foco | Requiere decidir si se usa `useDialogFocus` en un popover no modal (`aria-modal="false"`) |
| `color-mix()` de Tailwind 4 y ausencia de `build.target` | Define la política de navegadores soportados; es una decisión del equipo, no un defecto local. No se cambió la configuración de build |
| `localStorage` sin `try/catch` en modo privado estricto | Fuera del alcance responsive/compatibilidad visual; merece tarea propia |

---

## 6. Archivos modificados

`src/index.css`, `Input.tsx`, `LoginPage.tsx`, `RegisterPage.tsx`, `UserMenu.tsx`,
`TopBar.tsx`, `SidebarNav.tsx`, `RoleLayout.tsx`, `AppNavLink.tsx`, `AdminLayout.tsx`,
`ConfirmDialog.tsx`, `EvidencePreviewDialog.tsx`, `Toast.tsx`, `FormModal.tsx`,
`NotificationBell.tsx`, tres páginas de detalle/movimientos de inventario, nueve
pantallas con altura de viewport y sus pruebas asociadas, más
`src/infrastructure/utils/idOperacion.ts` y su prueba.

No se modificaron los archivos no versionados ajenos
`frontend/src/infrastructure/api/contratosOpenApi.test.ts` ni
`frontend/docs/diseno-responsive-accesibilidad-admin.md`.
