# Flujo completo web para cliente, mecánico y administrador

**Tarea (Semana 10):** Ejecutar flujo completo web para cliente mecánico y administrador
**Alcance:** Frontend Web (React) — recorrido end-to-end por rol (Cliente, Mecánico, Administrador) contra backend real: login, portal, vistas principales, campana y centro de avisos, cierre de sesión y protección de rutas por rol.
**Base de ejecución:** `main` sincronizado en `Gustavo` (commit base `6ebcabf`), usuarios de prueba sembrados en Neon y backend levantado en local.

## 1. Ambiente de ejecución

| Componente | Detalle |
|---|---|
| Frontend | Vite dev server en `http://localhost:5173` con `VITE_API_URL=http://localhost:8000/api` |
| Gateway | `gateway.main:app` en `http://localhost:8000` (puerto 8000) |
| MS1 Auth | `services.ms1_auth.main:app` en 8001 → Neon `taller_ms1` |
| MS2 Taller | `services.ms2_taller.main:app` en 8002 → Neon `taller_ms2` |
| MS3 Presupuestos | `services.ms3_presupuestos.main:app` en 8003 → Neon `taller_ms3` |
| MS4 Evidencias | **No levantado** (requiere `boto3`/S3 no disponibles en el venv local); ver §6 |

Usuarios de prueba (`backend/scripts/seed_usuarios_prueba.py`, ya sembrados en Neon):

| Rol | Correo | Resultado login vía `/api/auth/login` |
|---|---|---|
| Cliente | `cliente@pruebas.cl` | 200 OK → `roles: ["cliente"]` |
| Mecánico | `mecanico@pruebas.cl` | 200 OK → `roles: ["mecanico"]` |
| Administrador | `administrador@pruebas.cl` | 200 OK → `roles: ["administrador"]` |

## 2. Corrección previa requerida: migraciones de Neon

Al iniciar la ejecución, `GET /api/notificaciones?limite=15` respondía **500**. Diagnóstico:
la base Neon (entorno compartido) estaba detrás de `main` en sus tres bases.

| Servicio | Revisión Neon (antes) | Head repo | Migraciones aplicadas |
|---|---|---|---|
| MS1 | `0004_intentos_login_ms1` | `0008_contexto_avisos_ms1` | 0004_notificaciones → 0008 (5 migraciones, tablas de avisos) |
| MS2 | `0012_integracion_ms2` | `0014_solicitud_nueva_atencion_ms2` | 0013 (índice orden activa) y 0014 (solicitudes de nueva atención) |
| MS3 | `0010_ms3` | `0011_avisos_ms3` | 0011 (outbox de avisos) |

Con autorización explícita del integrante se ejecutó `alembic upgrade head` en MS1/MS2/MS3
(comandos desde `backend/`, p. ej. `alembic -c services/ms1_auth/alembic.ini upgrade head`).
Las migraciones son aditivas y `0013_orden_activa_por_vehiculo` validó que no había
duplicados antes de crear el índice. Tras aplicarlas, `/api/notificaciones` respondió
**200** en los tres roles y las vistas de nuevas atenciones dejaron de fallar.

> Registro: los tres `500` de `/api/notificaciones` visibles en los logs del gateway
> corresponden todos al periodo previo a las migraciones.

## 3. Flujo Cliente (`cliente@pruebas.cl`)

Convención: **OK** = funciona según lo esperado, **OBS** = funciona con observación.

| # | Paso | Ruta | Resultado | Observaciones |
|---|---|---|:---:|---|
| C-01 | Login desde `/login` | `/login` → `/client` | OK | Redirección al portal del rol; token persistido en `localStorage` |
| C-02 | Dashboard cliente | `/client` | OK | Saludo con nombre real, accesos rápidos (Mis Vehículos, Nuevas Atenciones) |
| C-03 | Mis Vehículos | `/client/vehiculos` | OK | 3 vehículos reales (Toyota Corolla, Hyundai Accent, nissan pathfinder) con patente/año/km |
| C-04 | Ficha de vehículo | `/client/vehiculos/1` | OK | Datos del vehículo + historial de órdenes (1 orden, estado Listo) |
| C-05 | Estado del Servicio | `/client/servicios` | OK | 2 servicios con filtro, tarjetas y accesos a detalle/evidencia |
| C-06 | Mis Órdenes | `/client/ordenes` | OK | Órdenes n°1 (Listo) y n°2 (Recibido) con filtro por estado |
| C-07 | Detalle de orden | `/client/ordenes/1` | OK | Ciclo de estados 1–8, historial de estados con fechas |
| C-08 | Presupuestos | `/client/presupuestos` | OK | Servicio n°1, Aprobado, versión 1, total $68.990 |
| C-09 | Nuevas Atenciones | `/client/nuevas-atenciones` | OK | Estado vacío correcto (sin solicitudes), filtro por situación |
| C-10 | Centro de avisos | `/client/notificaciones` | OK | “0 notificación(es), 0 sin leer”, filtros Todas/No leídas, estado vacío |
| C-11 | Campana de notificaciones | popover en TopBar | OK | Abre “Avisos — Sin avisos pendientes” con enlace “Ver centro de avisos” |
| C-12 | Cierre de sesión | botón en portal | OK | Vuelve a `/login` y limpia la sesión |

Errores de consola del rol cliente: **0** (tras las migraciones de §2).

## 4. Flujo Mecánico (`mecanico@pruebas.cl`)

| # | Paso | Ruta | Resultado | Observaciones |
|---|---|---|:---:|---|
| M-01 | Login | `/login` → `/mechanic` | OK | Redirección al portal mecánico |
| M-02 | Dashboard | `/mechanic` | OK | Órdenes asignadas: 1 · activas: 1 · vehículos: 1; resumen por estado |
| M-03 | Mis Órdenes | `/mechanic/ordenes` | OK | Orden n°1 asignada (Toyota Corolla · ABCD12) con filtro por estado |
| M-04 | Detalle de orden | `/mechanic/ordenes/1` | OK | Ficha completa + historial de estados; **OBS**: `502` en `/api/evidencias?orden_id=1` (MS4 detenido, esperado) |
| M-05 | Editor de presupuesto | `/mechanic/ordenes/1/presupuesto` | OK | Formulario de ítems Mano de obra/Repuesto con catálogo MS3 (16 repuestos), “Guardar borrador” |
| M-06 | Vehículos asignados | `/mechanic/vehiculos` | OK | Toyota Corolla con dueño (Cliente #1); OBS: muestra estado vacío un instante antes de llegar los datos |
| M-07 | Actualizar Estados | `/mechanic/estados` | OK | Orden n°1 en Listo sin avances disponibles para mecánico (correcto según estado) |
| M-08 | Centro de avisos | `/mechanic/notificaciones` | OK | Estado vacío con contadores en 0 |
| M-09 | Cierre de sesión | botón en sidebar | OK | Vuelve a `/login` |

Errores de consola del rol mecánico: solo el **502** de evidencias (MS4 detenido, §6).

## 5. Flujo Administrador (`administrador@pruebas.cl`)

| # | Paso | Ruta | Resultado | Observaciones |
|---|---|---|:---:|---|
| A-01 | Login | `/login` → `/admin` | OK | Redirección al panel de administración |
| A-02 | Panel de Control | `/admin` | OK | Indicadores reales: 3 órdenes totales/activas, 4 vehículos, 4 mecánicos, carga por mecánico |
| A-03 | Gestión de Órdenes | `/admin/ordenes` | OK | 3 órdenes (n°1, n°2, n°3) con filtro y “Registrar ingreso” |
| A-04 | Detalle de orden | `/admin/ordenes/1` | OK | Ficha + historial; mismo **OBS** 502 de evidencias (MS4 detenido) |
| A-05 | Clientes | `/admin/clientes` | OK | 5 clientes con correo y estado Activo |
| A-06 | Catálogo de Vehículos | `/admin/vehiculos` | OK | 4 vehículos con dueño y ficha técnica |
| A-07 | Inventario (MS3) | `/admin/inventario` | OK | 16 repuestos con stock, umbral y estado de stock (Normal/Crítico) |
| A-08 | Distribuidores (MS3) | `/admin/distribuidores` | OK | 7 proveedores con contacto, tipo y cantidad de repuestos |
| A-09 | Nuevas atenciones | `/admin/nuevas-atenciones` | OK | Estado vacío correcto, filtros por situación y n° de orden |
| A-10 | Centro de avisos | `/admin/notificaciones` | OK | Estado vacío con contadores en 0 |
| A-11 | Campana de notificaciones | popover en TopBar | OK | “Sin avisos pendientes” + enlace al centro de avisos |
| A-12 | Capacidad del taller | `/admin/configuracion` | OK | Límites vigentes (5 ingresos/jornada, 2 órdenes activas por mecánico) con último cambio registrado |
| A-13 | Cierre de sesión | botón en portal | OK | Vuelve a `/login` |

Errores de consola del rol administrador: solo el **502** de evidencias (MS4 detenido, §6).

## 6. Limitaciones del ambiente (conocidas y acotadas)

1. **MS4 (evidencias) no ejecutado en local:** el servicio requiere `boto3` y S3/MinIO.
   Consecuencia: `GET /api/evidencias?orden_id=...` responde **502** desde el gateway y las
   vistas de evidencias de las órdenes no pueden listar archivos. No afecta los flujos
   principales (auth, órdenes, vehículos, presupuestos, inventario, avisos).
2. **Caja de avisos vacía:** no hay eventos recientes en Neon para los usuarios de prueba,
   por lo que la campana y el centro muestran su estado vacío (correcto). El circuito
   completo evento → notificación → lectura requiere transacciones de negocio (ver §7).
3. **Sin escrituras de negocio:** no se crearon órdenes, presupuestos ni vehículos nuevos
   para no mutar el dataset compartido de Neon (producción). El recorrido validó lectura,
   navegación, guardas y estados.

## 7. Verificación de protección de rutas por rol (403)

| Origen | Destino intentado | Resultado |
|---|---|---|
| Sesión cliente | `/admin` | **OK** → `/acceso-denegado` (ERROR 403, mensaje con rol, botones “Ir a mi Panel”/“Cerrar Sesión”) |
| Sesión mecánico | `/client` | **OK** → `/acceso-denegado` (ERROR 403, mismo patrón) |

Sin errores de consola en ambos casos. `ProtectedRoute` + `AccessDeniedPage` funcionan
según lo implementado.

## 8. Suite automática complementaria

`npm run test` (Vitest + RTL): **127 archivos, 1097 pruebas, todas aprobadas** (~56 s),
incluyendo las pruebas de rutas protegidas y navegación por roles.

## 9. Resultado global

- **Estado:** Flujo completo ejecutado para los tres roles contra backend real (Neon).
- **Resultado:** **Aprobado**. Login, portales, vistas principales, campana y centro de
  avisos, guardas por rol y cierre de sesión funcionan; las únicas fallas son del ambiente
  (MS4 detenido) y quedaron documentadas.
- **Recomendaciones de seguimiento:**
  1. Ejecutar en un ambiente de pruebas (p. ej. `sgtm_pruebas`) una pasada con escrituras
     de negocio de punta a punta (ingreso → diagnóstico → presupuesto → aprobación →
     entrega) para validar el circuito de notificaciones con eventos reales.
  2. Coordinar con el equipo el estado de las migraciones de Neon (fue necesario aplicar
     `head` durante esta ejecución) y definir quién las aplica en cada integración a main.
  3. Levantar MS4 con `boto3` + MinIO cuando se requiera validar evidencias visuales.
- **Fecha de registro:** 2026-11-10
- **Responsable:** Gustavo Rosa (Frontend Web React)
