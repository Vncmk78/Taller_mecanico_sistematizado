# Revisión básica de accesibilidad (Frontend Web)

Revisión de accesibilidad de las vistas y componentes del **portal Cliente**
(`/client/*`) y de la infraestructura de UI reutilizable de las que dependen,
todos de autoría de Gustavo Rosa. No se auditaron ni modificaron componentes de
otros integrantes (`ClientLayout`, `Toast`, `OrderStatusAndHistory`,
`OfflineBanner`, `VehicleCard`, `ClientOrderDetailPage`).

- Alcance: navegación, formularios, diálogos modales, estados de carga/vacío/error
  y listados del portal Cliente.
- Método: inspección de código contra las pautas **WCAG 2.1 nivel A/AA**
  (criterios relevantes enumerados abajo) y verificación con la suite existente
  (`npm run lint`, `npx vitest run`, `npm run build`). No se incorporó un
  analizador automático (axe) para no añadir dependencias fuera del alcance.
- Referencia de contraste: tokens de diseño definidos para el *glassmorphism*
  del demo; no se alteró la paleta.

## Criterios WCAG revisados

| Criterio | Descripción | Estado |
| --- | --- | --- |
| 1.1.1 | Contenido no textual (iconos, imágenes) | Corregido |
| 1.3.1 | Información y relaciones (encabezados, etiquetas) | Corregido |
| 2.1.1 / 2.1.2 | Accesible por teclado / sin trampa de teclado | Corregido |
| 2.4.3 | Orden del foco | Corregido |
| 2.4.4 | Propósito del enlace (en contexto) | Corregido |
| 2.4.7 | Foco visible | Ya presente |
| 3.3.1 / 3.3.2 | Identificación de errores / etiquetas e instrucciones | Ya presente |
| 4.1.2 | Nombre, función, valor | Corregido |
| 4.1.3 | Mensajes de estado | Corregido |

## Hallazgos y resoluciones

### H1 — Iconos decorativos sin `aria-hidden` (severidad: baja)

Los iconos de `lucide-react` dentro de encabezados, botones y enlaces con texto
visible se exponían al árbol de accesibilidad sin aportar información.
**Corregido** añadiendo `aria-hidden` en:

- `layout/AppNavLink.tsx` (el icono se envuelve en un `span` con `aria-hidden`).
- `layout/UserMenu.tsx`, `layout/AppBrand.tsx`.
- `ui/Input.tsx` (el `span` del icono).
- `orders/OrderCard.tsx`.
- `vehicles/VehicleInfoPanel.tsx`.
- Páginas cliente: `ClientDashboardPage`, `ClientVehiclesPage`,
  `ClientVehicleDetailPage`, `ClientVehicleFormPage`,
  `ClientBudgetDetailPage`, `ClientOrderEvidencePage`.
- Diálogos: `ConfirmDialog`, `ApproveBudgetDialog`, `RejectBudgetDialog`,
  `EvidencePreviewDialog`.

`Alert`, `EmptyState`, `ErrorState`, `ServiceCard`, `BudgetCard`,
`BudgetItemRow`, `EvidenceCard` y `Spinner` **ya** marcaban sus iconos como
decorativos.

### H2 — Diálogos sin gestión de foco (severidad: media)

`ConfirmDialog`, `ApproveBudgetDialog`, `RejectBudgetDialog` y
`EvidencePreviewDialog` no movían el foco al abrirse, no lo encerraban dentro
del modal (Tab/Shift+Tab) y no lo devolvían al elemento de origen al cerrar.

**Corregido** con un hook reutilizable
`presentation/hooks/useDialogFocus.ts` que:

1. al abrir, enfoca el contenedor del diálogo (`tabIndex={-1}`, así el lector de
   pantalla anuncia la etiqueta `aria-label`);
2. mantiene el foco dentro del diálogo al recorrer con Tab/Shift+Tab;
3. al cerrar/desmontar, devuelve el foco al elemento que abrió el diálogo.

Los cuatro diálogos ya cerraban con `Escape` y con clic en el fondo; se conserva.

### H3 — Enlaces que quedan solo-icono en móvil (severidad: media)

En `orders/ServiceCard.tsx` los enlaces "Vehículo" y "Evidencia" ocultan su
etiqueta en pantallas pequeñas (`hidden sm:inline`), por lo que en móvil
quedaban sin nombre accesible real (solo un `title` poco fiable).
**Corregido** añadiendo `aria-label` explícito a ambos enlaces.

### H4 — Estados de carga sin anuncio (severidad: baja)

`OrderListSkeleton` y `VehicleListSkeleton` mostraban solo cajas animadas sin
`role="status"` ni texto alternativo.
**Corregido**: el contenedor pasa a `role="status"`, `aria-busy="true"` y
`aria-live="polite"`, con un texto `sr-only` ("Cargando órdenes...",
"Cargando vehículos...") y la representación visual marcada `aria-hidden`.

### H5 — Falta de encabezado `h1` por página (severidad: media)

Las páginas del portal usaban `h2` como título principal, de modo que el
documento no tenía `h1` (las páginas públicas sí lo tenían).
**Corregido** promoviendo el título de cada página a `h1` (conservando estilos)
y ajustando los encabezados de subsección a `h2` cuando correspondía:

- `ClientDashboardPage`, `ClientVehiclesPage`, `ClientOrdersPage`,
  `ClientServicesPage`, `ClientBudgetsPage`, `ClientBudgetDetailPage`,
  `ClientOrderEvidencePage`, `ClientVehicleFormPage`.
- `ClientVehicleDetailPage`: se añadió un `h1` oculto
  ("Ficha del vehículo …") y el historial pasa a `h2`.
- Secciones internas de `ClientServicesPage` (grupos) y
  `ClientBudgetDetailPage` ("Detalle del presupuesto", "Su decisión") pasan a
  `h2`.

## Puntos menores documentados (sin cambio)

| Punto | Motivo | Severidad |
| --- | --- | --- |
| `VehicleInfoPanel` mantiene su `h3` | Es un componente compartido con los portales de mecánico y administrador; cambiar su nivel alteraría la jerarquía de páginas ajenas. | Muy baja (salto `h1 → h3` en la ficha del vehículo). |
| Tarjetas (`OrderCard`, `BudgetCard`, `ServiceCard`) usan `h3` bajo el `h1` de la página | Componentes reutilizados entre portales; el salto de nivel es válido y no rompe la lectura. | Muy baja. |
| `LoadingState` anuncia el mensaje por el `Spinner` (`role="status"`) y además muestra el texto visible | Duplicación leve del anuncio; el patrón ya superaba la verificación de accesibilidad y cuenta con prueba propia. | Muy baja. |
| Paleta / contraste | Se respetan los tokens del demo; no se rediseñaron colores. | Informativo. |

## Verificación

- `npm run lint` → 0 advertencias, 0 errores.
- `npx vitest run` → **478/478** pruebas en 70 archivos.
- `npm run build` → correcto (`tsc -b` + `vite build`; se mantiene el aviso
  preexistente de *chunk* > 500 kB).

## Archivos modificados

Nuevo:

- `src/presentation/hooks/useDialogFocus.ts`

Editados:

- `src/presentation/components/layout/AppNavLink.tsx`
- `src/presentation/components/layout/UserMenu.tsx`
- `src/presentation/components/layout/AppBrand.tsx`
- `src/presentation/components/ui/Input.tsx`
- `src/presentation/components/ui/ConfirmDialog.tsx`
- `src/presentation/components/orders/OrderCard.tsx`
- `src/presentation/components/orders/OrderListSkeleton.tsx`
- `src/presentation/components/orders/ServiceCard.tsx`
- `src/presentation/components/vehicles/VehicleListSkeleton.tsx`
- `src/presentation/components/vehicles/VehicleInfoPanel.tsx`
- `src/presentation/components/budgets/ApproveBudgetDialog.tsx`
- `src/presentation/components/budgets/RejectBudgetDialog.tsx`
- `src/presentation/components/evidence/EvidencePreviewDialog.tsx`
- `src/presentation/pages/client/ClientDashboardPage.tsx`
- `src/presentation/pages/client/ClientVehiclesPage.tsx`
- `src/presentation/pages/client/ClientVehicleDetailPage.tsx`
- `src/presentation/pages/client/ClientVehicleFormPage.tsx`
- `src/presentation/pages/client/ClientOrdersPage.tsx`
- `src/presentation/pages/client/ClientServicesPage.tsx`
- `src/presentation/pages/client/ClientBudgetsPage.tsx`
- `src/presentation/pages/client/ClientBudgetDetailPage.tsx`
- `src/presentation/pages/client/ClientOrderEvidencePage.tsx`
