# Revisión de adaptación a tamaños de pantalla (Frontend Web)

Revisión de la responsividad de las vistas de los portales **Cliente**,
**Mecánico** y **Administrador**, en anchos representativos de móvil (360 px),
tablet (768 px) y escritorio (1024–1440 px). No se alteró la paleta ni el
lenguaje visual; solo se ajustaron contenedores y puntos de quiebre.

## Método

- Inspección de las clases Tailwind de layouts, listados, formularios, tablas y
  diálogos.
- Revisión de anchos fijos (`w-[…px]`), grillas sin breakpoints y contenedores
  flexibles sin `min-w-0`.
- Verificación con `npm run build`, `npm run lint` y `npx vitest run`.

## Cambios aplicados

### Navegación y layout

- `SidebarNav` ahora funciona como panel fuera de pantalla en móvil
  (`fixed` + `-translate-x-full`) y como barra lateral fija desde `lg`.
- `TopBar` incorpora un botón de menú visible solo en móvil, con
  `aria-expanded` y `aria-controls`.
- El panel lateral se cierra al elegir un enlace o tocar el fondo oscurecido.
- La navegación superior del portal Cliente pasa a una segunda fila con scroll
  horizontal en pantallas pequeñas.
- `main` usa `min-w-0` para que las tablas puedan desplazarse en horizontal sin
  desbordar el layout.

### Páginas y contenedores

- Padding de páginas ajustado de `p-10` / `px-10` a
  `p-4 sm:p-6 lg:p-10` (y equivalentes en `px` / `mx`).
- Encabezados con `flex-wrap` y separación para evitar solapamientos.
- Búsqueda global del administrador oculta en móvil y con ancho progresivo en
  tablet/escritorio.
- Buscadores de vehículos y listados pasan a `w-full sm:w-[320px]`.
- `HomePage`: grillas de características y pasos pasan de 4 columnas fijas a
  `1 / 2 / 4` columnas; navegación y footer se reorganizan en móvil.
- `ClientDashboardPage`: tarjetas de acceso se apilan en móvil.
- `AdminDashboardPage`: indicadores en una columna en móvil y panel principal en
  una sola columna hasta `lg`.
- Formularios y diálogos mantienen `w-full max-w-[…]` y padding reducido en
  pantallas pequeñas.

### Tablas

- El componente `Table` ya envuelve la tabla en `overflow-x-auto`; se verificó
  que todos los listados (inventario, movimientos, alertas, umbral, clientes,
  distribuidores y compromisos) lo usan.

## Verificación

| Comando | Resultado |
| --- | --- |
| `npm run build` | Correcto |
| `npm run lint` | Sin observaciones |
| `npm test` | 102 archivos / 787 pruebas correctas |

Las pruebas de `RoleLayout` cubren la apertura/cierre del menú móvil y el cierre
automático al navegar.
