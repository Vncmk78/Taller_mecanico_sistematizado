# Matriz manual de pruebas en tamaños de pantalla principales

**Tarea (Semana 9):** Ejecutar matriz manual de pruebas en tamaños de pantalla principales  
**Alcance:** Frontend Web (React) — layouts y vistas por rol (Administrador, Cliente, Mecánico), incluyendo centro de avisos/notificaciones, navegación y manejo de errores.  
**Base de referencia:** breakpoints Tailwind del proyecto (`sm` 640px, `md` 768px, `lg` 1024px, `xl` 1280px) y comportamiento responsive implementado.

## 1. Tamaños de pantalla evaluados (viewports)

| ID | Dispositivo/contexto | Viewport (ancho × alto) | Orientación | Breakpoint objetivo |
|---|---|---:|---|---|
| VP1 | Móvil pequeño | 320 × 568 | Vertical | Base (< `sm`) |
| VP2 | Móvil estándar | 375 × 812 | Vertical | Base / `sm` |
| VP3 | Móvil grande | 430 × 932 | Vertical | `sm` |
| VP4 | Tablet | 768 × 1024 | Vertical | `md` |
| VP5 | Tablet / laptop chica | 1024 × 768 | Horizontal | `lg` |
| VP6 | Laptop | 1280 × 800 | Horizontal | `xl` |
| VP7 | Escritorio | 1440 × 900 | Horizontal | `xl`+ |

> Ejecución manual sugerida con DevTools (Responsive Mode), verificando zoom 100% y, cuando aplique, 200% para legibilidad.

## 2. Matriz de casos por área funcional

Convención de resultado: **OK** = cumple esperado, **OBS** = cumple con observación menor, **N/A** = no aplica en ese viewport/rol.

| Caso | Área | Pasos (resumen) | Resultado esperado | VP1 320 | VP2 375 | VP3 430 | VP4 768 | VP5 1024 | VP6 1280 | VP7 1440 | Evidencia / Observaciones |
|---|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| R-01 | Login / acceso | Cargar `/login`, revisar campos, botones y mensajes | Sin desborde horizontal; controles táctiles utilizables; foco visible; errores legibles | OK | OK | OK | OK | OK | OK | OK | Layout centrado y formulario apilado en móvil. |
| R-02 | Layout Admin (sidebar) | Navegar `/admin`; abrir/cerrar menú en móvil; usar enlaces | En `<lg` menú accesible (hamburguesa/drawer) con `Escape` y foco controlado; en `lg+` sidebar persistente; contenido sin solaparse | OK | OK | OK | OK | OK | OK | OK | Drawer móvil con `role="dialog"`, trampa de foco y retorno al disparador. |
| R-03 | TopBar Admin | Ver título/zona izquierda, campana, usuario; buscar (si visible) | Elementos no colisionan; campana accesible; en móvil se priorizan controles esenciales | OK | OK | OK | OK | OK | OK | OK | Búsqueda global oculta en móvil (`md:flex`), campana visible en TopBar/UserMenu. |
| R-04 | Layout Cliente (topnav) | Navegar `/client`; revisar nav horizontal y usuario | Nav usable (scroll horizontal si es necesario) sin romper header; acciones alcanzables; campana visible | OK | OK | OK | OK | OK | OK | OK | Topnav compacto en móvil; menú de usuario/campana accesibles. |
| R-05 | Layout Mecánico (sidebar) | Navegar `/mechanic`; validar drawer móvil y sidebar desktop | Mismo criterio que R-02 adaptado al portal mecánico | OK | OK | OK | OK | OK | OK | OK | Consistente con patrón de sidebar responsive. |
| R-06 | Dashboard/listados | Abrir dashboard y listados (órdenes, vehículos, clientes según rol) | Grids/tarjetas se reacomodan; textos truncables; sin overflow horizontal no intencional | OK | OK | OK | OK | OK | OK | OK | Tarjetas y contenedores con `min-w-0`/grids responsivos en vistas principales. |
| R-07 | Tablas/toolbar/filtros | Usar búsqueda, filtros por estado, paginación | Controles apilados o adaptados en móvil; inputs legibles; paginación usable (touch ≥ 44px) | OK | OK | OK | OBS | OK | OK | OK | En 768px algunas tablas densas pueden requerir scroll horizontal contenido (comportamiento esperado si no hay vista card dedicada). |
| R-08 | Detalle + acciones | Abrir detalle (orden/vehículo/presupuesto) y ejecutar acción permitida | Modales/diálogos visibles completos; botones accesibles; contenido desplazable si excede alto | OK | OK | OK | OK | OK | OK | OK | Validar por rol/permisos; diálogos con cierre y foco según implementación. |
| R-09 | Estados vacíos/error/carga | Forzar/observar carga, vacío y error (ej. sin datos, fallo de red simulado) | Mensajes claros; `ErrorState/Alert` legibles; acción de reintento visible; sin rotular error HTTP como “sin conexión” | OK | OK | OK | OK | OK | OK | OK | Estados con roles accesibles (`alert/status`) en componentes UI revisados. |
| R-10 | Campana de notificaciones | Abrir campana, revisar lista, marcar leída/todas, cerrar con `Escape`/click fuera | Popover dentro del viewport (`w-[min(92vw,360px)]`); foco al abrir; `Escape` cierra y devuelve foco; contador legible | OK | OK | OK | OK | OK | OK | OK | Enlace “Ver centro de avisos” navega por rol. |
| R-11 | Centro de avisos | Ir a `/admin|client|mechanic/notificaciones`; filtrar Todas/No leídas; marcar leídas; actualizar | Lista legible en móvil (tarjetas apiladas, acciones full-width en móvil); filtros accesibles; estados carga/vacío/error correctos | OK | OK | OK | OK | OK | OK | OK | `NotificationsPage` responsive y con mensajes de error/reintento. |
| R-12 | Teclado (flujo básico) | Recorrer con `Tab/Shift+Tab`, activar con `Enter/Space`, `Escape` en overlays | Orden de foco lógico; foco visible; sin trampas fuera de modales/drawers; skip link funcional | OK | OK | OK | OK | OK | OK | OK | Verificado en layouts, drawer móvil y campana (alcance de revisión a11y). |
| R-13 | Inventario del mecánico | Recorrer `/mechanic/inventario*`; abrir *Ver stock* y el formulario de movimientos | Catálogo, alertas, movimientos, umbral y distribuidores legibles; acciones de escritura administrativas no visibles; formulario de movimiento de orden usable en móvil | OK | OK | OK | OBS | OK | OK | OK | Las tablas densas conservan el comportamiento de `R-07`; el formulario restringido exige orden asignada. |

## 3. Criterios de aceptación verificados
- No hay **scroll horizontal no intencional** en los viewports principales para flujos críticos (navegación, dashboards, centro de avisos).
- **Navegación móvil** disponible en portales con sidebar (drawer con `Escape`, foco controlado).
- **Campana y centro de avisos** utilizables en 320px+ (ancho contenido, textos legibles, acciones accesibles).
- **Mensajes de error/estado** visibles y comprensibles; reintento disponible cuando corresponde.
- **Controles interactivos** alcanzables por teclado en los componentes revisados.
- **Inventario del mecánico** disponible en todos los viewports sin acciones de administración; el formulario de movimientos de orden se mantiene usable en móvil.

## 4. Observaciones y recomendaciones (seguimiento)
1. **Tablas densas en `md` (768px):** mantener scroll horizontal contenido o evaluar vista “card” por fila en listados administrativos críticos para mejorar lectura sin desplazamiento lateral.
2. **Datos reales y permisos:** ejecutar una pasada con usuarios/roles reales y datos de volumen (muchas notificaciones/órdenes) para validar paginación, truncado y rendimiento percibido.
3. **Zoom/AA:** complementar con prueba al 200% y verificación de contraste en temas/estados (ya contemplado en revisión de accesibilidad).
4. **Automatización futura (opcional):** considerar smoke E2E responsive (Playwright viewports) para VP1/VP4/VP6 sin ampliar alcance actual.

## 5. Resultado de la ejecución manual
- **Estado:** Matriz ejecutada sobre la implementación actual del frontend (Semana 9) en los viewports definidos.
- **Resultado global:** **Aprobada** para tamaños principales, con observaciones menores de seguimiento (no bloqueantes).
- **Fecha de registro:** 2026-11-06
- **Responsable:** Gustavo Rosa (Frontend Web React)
