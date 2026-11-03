# Revisión básica de accesibilidad (Frontend Web)

Revisión de accesibilidad de las vistas y componentes del **portal Cliente**
(`/client/*`) y de la infraestructura de UI reutilizable de las que dependen
(Tarea 15). La **Tarea 16** amplía la revisión a los formularios, diálogos,
validaciones y mensajes de **todos los portales** (Cliente, Mecánico y
Administrador) y a los componentes compartidos. En ambas pasadas se mantuvo el
criterio de no rediseñar la interfaz ni alterar la paleta.

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

## Tarea 16 — Inputs, validaciones y mensajes (todos los portales)

Segunda pasada de accesibilidad sobre los formularios, diálogos, validaciones y
mensajes de estado de **todos los portales** (Cliente, Mecánico y
Administrador), incluidos los componentes compartidos. Se mantuvo el criterio de
la revisión anterior: sin dependencias nuevas, sin rediseño visual y sin alterar
la paleta.

### Alcance

- Campos de texto, selectores, casillas y campos de archivo.
- Mensajes de validación local, errores del servidor y avisos de estado.
- Diálogos modales de confirmación, aprobación y rechazo.
- Barras de búsqueda de los listados y del layout de administración.

### Criterios WCAG trabajados

| Criterio | Descripción | Estado |
| --- | --- | --- |
| 1.3.1 | Información y relaciones (etiquetas, ayudas y errores asociados) | Corregido |
| 2.4.6 | Encabezados y etiquetas descriptivas | Corregido |
| 3.3.1 | Identificación de errores | Corregido |
| 3.3.2 | Etiquetas o instrucciones | Corregido |
| 3.3.3 | Sugerencia de corrección | Corregido |
| 4.1.2 | Nombre, función, valor | Corregido |
| 4.1.3 | Mensajes de estado | Corregido |

### Hallazgos y resoluciones

#### H1 — `Input` no admitía ayuda y pisaba descripciones externas

El componente compartido `ui/Input.tsx` solo asociaba el error y no permitía
mostrar una ayuda bajo el campo. Además, si un consumidor pasaba
`aria-describedby`, el valor se sobrescribía.
**Corregido**: nueva prop `hint`; `aria-describedby` combina la descripción
externa, la ayuda y el error sin perder ninguna; `required` se refleja en el
atributo nativo y en `aria-required`; `aria-invalid` se mantiene.

#### H2 — Mensajes sin `id` ni anuncio completo

`ui/Alert.tsx` no permitía referenciar el aviso desde el campo que lo originaba
y no fijaba `aria-atomic`.
**Corregido**: nueva prop `id` y `aria-atomic="true"` en todos los tonos. Los
diálogos `ui/ConfirmDialog.tsx`, `budgets/ApproveBudgetDialog.tsx` y
`budgets/RejectBudgetDialog.tsx` pasan de `aria-label` a
`aria-labelledby`/`aria-describedby` con `useId`, de modo que el lector anuncia
título y contexto.

#### H3 — Errores de archivo mezclados con errores generales

En `evidence/EvidenceUploadForm.tsx` todos los fallos usaban el mismo estado y
el campo de archivo solo se marcaba inválido con una condición indirecta.
**Corregido**:

- `errorArchivo` separado de `errorLocal`: los errores de archivo (sin archivo,
  tipo no permitido, tamaño excedido) se muestran junto al campo y se asocian
  con `aria-describedby`/`aria-invalid`.
- El error general (presupuesto ausente o en carga, error del servidor, sin
  conexión) sigue en el `Alert` general y **no** marca el archivo como inválido.
- El campo de archivo describe los formatos permitidos y el tamaño máximo
  (12 MiB), y el campo de contexto describe la asociación automática cuando es
  presupuesto.
- La etiqueta del archivo se separó del texto de ayuda para que la ayuda no se
  sume al nombre accesible del control.

#### H4 — Validaciones sin vínculo campo-error

- `orders/BitacoraForm.tsx`: descripción y repuestos (nombre y cantidad) ahora
  tienen `id`, `aria-required`, `aria-invalid` y `aria-describedby` hacia el
  párrafo de error correspondiente.
- `orders/OrderActionsPanel.tsx`: el motivo obligatorio de cancelación ya no usa
  el `Alert` general; tiene error de campo con `aria-invalid`/`aria-describedby`
  y se limpia al escribir. Destino, mecánico, motivo y observación tienen
  `id`, `name` y semántica de obligatorio.
- `budgets/RejectBudgetDialog.tsx`: el motivo es obligatorio, está descrito por
  la ayuda, el contador y su error; la casilla de confirmación de cancelación
  tiene `id`, `name` y su propio error asociado. El `Alert` de error usa un `id`
  distinto según el control que lo origine, para no marcar como inválido un
  campo que no corresponde.
- `budgets/ApproveBudgetDialog.tsx`: la casilla de revisión expone
  `aria-required`, `aria-describedby` y una ayuda visible que explica que
  habilita la confirmación.
- `pages/mechanic/MechanicStatusPage.tsx`: destino y observación tienen `id`,
  `name` y `aria-required` en el selector de avance.

#### H5 — Formularios públicos y de cliente

- `pages/auth/LoginPage.tsx`: el formulario usa `noValidate` (la validación la
  hace Zod y sus errores ya se asocian al campo), el título de la tarjeta pasa a
  `h2` para no saltar niveles y los logos decorativos quedan `aria-hidden`.
- `pages/client/ClientVehicleFormPage.tsx`: patente, marca y modelo se marcan
  como obligatorios (`required` + `aria-required`); año y kilometraje declaran
  `inputMode="numeric"`.

#### H6 — Búsquedas sin semántica de búsqueda

Las barras de búsqueda usaban `type="text"` y no se agrupaban como región de
búsqueda.
**Corregido** en `orders/OrderListToolbar.tsx`,
`pages/client/ClientVehiclesPage.tsx`, `pages/mechanic/MechanicVehiclesPage.tsx`,
`pages/admin/AdminVehiclesPage.tsx` y `components/layout/AdminLayout.tsx`:
`role="search"`, un `aria-label` para la región, `type="search"`, `name` y
`autoComplete="off"`. Las pruebas que consultaban `textbox` se actualizaron a
`searchbox`.

### Decisiones de implementación

- `aria-invalid` se aplica cuando el campo ya tiene un error visible; en los
  controles que solo habilitan un botón (destino, mecánico, casilla de revisión)
  se usa `aria-required` y una ayuda visible en lugar de marcar el campo como
  inválido antes de interactuar.
- Los mensajes de error conservan el texto existente para no romper la promesa
  al usuario ni las pruebas de flujo; solo cambió dónde y cómo se asocian.
- No se añadieron dependencias ni se modificó la presentación visual.

### Verificación

- `npm test` → **619/619** pruebas en 85 archivos.
- `npm run lint` → 0 advertencias, 0 errores.
- `npx tsc -b` → sin errores.
- Pruebas focalizadas de los componentes tocados: **260/260** en 36 archivos.

### Archivos modificados

Nuevos:

- `src/presentation/components/budgets/RejectBudgetDialog.test.tsx`
- `src/presentation/components/orders/OrderListToolbar.test.tsx`

Editados (código):

- `src/presentation/components/ui/Input.tsx`
- `src/presentation/components/ui/Alert.tsx`
- `src/presentation/components/ui/ConfirmDialog.tsx`
- `src/presentation/components/orders/OrderListToolbar.tsx`
- `src/presentation/components/orders/BitacoraForm.tsx`
- `src/presentation/components/orders/OrderActionsPanel.tsx`
- `src/presentation/components/evidence/EvidenceUploadForm.tsx`
- `src/presentation/components/budgets/ApproveBudgetDialog.tsx`
- `src/presentation/components/budgets/RejectBudgetDialog.tsx`
- `src/presentation/pages/auth/LoginPage.tsx`
- `src/presentation/pages/client/ClientVehicleFormPage.tsx`
- `src/presentation/pages/client/ClientVehiclesPage.tsx`
- `src/presentation/pages/mechanic/MechanicVehiclesPage.tsx`
- `src/presentation/pages/mechanic/MechanicStatusPage.tsx`
- `src/presentation/pages/admin/AdminVehiclesPage.tsx`
- `src/presentation/components/layout/AdminLayout.tsx`

Editados (pruebas):

- `src/presentation/components/ui/Input.test.tsx`
- `src/presentation/components/ui/Alert.test.tsx`
- `src/presentation/components/ui/ConfirmDialog.test.tsx`
- `src/presentation/components/orders/BitacoraForm.test.tsx`
- `src/presentation/components/orders/OrderActionsPanel.test.tsx`
- `src/presentation/components/evidence/EvidenceUploadForm.validacion.test.tsx`
- `src/presentation/components/budgets/ApproveBudgetDialog.test.tsx`
- `src/presentation/pages/auth/LoginPage.test.tsx`
- `src/presentation/pages/client/ClientVehicleFormPage.test.tsx`
- `src/presentation/pages/client/ClientVehiclesPage.test.tsx`
- `src/presentation/pages/mechanic/MechanicVehiclesPage.test.tsx`
- `src/presentation/pages/mechanic/MechanicStatusPage.test.tsx`
- `src/presentation/pages/admin/AdminVehiclesPage.test.tsx`
