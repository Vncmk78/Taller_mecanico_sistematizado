# 07 — Pruebas realizadas

Registro de las verificaciones ejecutadas contra el ambiente real de Kubero el
**15 de noviembre de 2026**. No son pruebas unitarias: son comprobaciones de
extremo a extremo por HTTP contra los dominios públicos.

> Las pruebas automatizadas del repositorio (`backend/tests/`) son otra cosa y se
> ejecutan en desarrollo. Este documento responde a "¿funciona lo desplegado?".

---

## 1. Resumen

| Área | Pruebas | Resultado |
| --- | --- | --- |
| Build e imágenes | 3 | ✅ |
| Infraestructura y salud | 9 | ✅ |
| Base de datos y migraciones | 5 | ✅ |
| Autenticación y roles | 6 | ✅ |
| Vehículos y órdenes | 8 | ✅ |
| Presupuestos | 7 | ✅ |
| Inventario | 6 | ✅ |
| Evidencias y MinIO | 6 | ✅ |
| Notificaciones | 8 | ✅ |
| Nueva atención | 4 | ✅ |
| Frontend y dominios | 8 | ✅ |
| Seguridad (CORS, errores, secretos) | 6 | ✅ |

**Total: 76 comprobaciones, todas con el resultado esperado.**

---

## 2. Build e imágenes

| # | Prueba | Resultado |
| --- | --- | --- |
| B1 | Workflow `docker-build.yml` (histórico en `kubero-deploy`) | ✅ Run `43548759119`, conclusión `success` |
| B2 | Imagen backend publicada | ✅ `ghcr.io/vncmk78/tallerconnect-backend:latest` y `:sha-c855bab` |
| B3 | Imagen frontend publicada | ✅ `ghcr.io/vncmk78/tallerconnect-frontend:latest` y `:sha-c855bab` |
| B4 | Workflow en `main` con `branches: [main]` | ✅ Run `45306353919` desde `main`, conclusión `success` |
| B5 | Job de deploy automático (tags `sha-<commit>` + redeploy + salud) | ✅ Job `Actualizar Kubero al sha publicado` en `success`; imágenes `:sha-40106f5` |

---

## 3. Infraestructura y salud

| # | Prueba | Resultado |
| --- | --- | --- |
| I1 | Pipeline `tallerconnect` con 7 apps | ✅ `gateway`, `ms1`–`ms4`, `web`, `minio` |
| I2 | `GET /api/health` | ✅ `200 {"status":"ok","servicio":"gateway"}` |
| I3 | `GET /api/health/servicios` | ✅ 4 servicios `ok` (latencia 19–42 ms) |
| I4 | `GET /health` de MS1 | ✅ `200` |
| I5 | `GET /health` de MS2 | ✅ `200` |
| I6 | `GET /health` de MS3 | ✅ `200` |
| I7 | `GET /health` de MS4 | ✅ `200` |
| I8 | `GET /minio/health/live` | ✅ `200` |
| I9 | PVC de MinIO | ✅ `minio-data-cephfs` montado, storage class `csi-cephfs-sc` |

---

## 4. Base de datos y migraciones

| # | Prueba | Resultado |
| --- | --- | --- |
| D1 | 4 addons PostgreSQL | ✅ `ms1-postgres` … `ms4-postgres` |
| D2 | Migración MS1 | ✅ `0008_contexto_avisos_ms1` |
| D3 | Migración MS2 | ✅ `0014_nueva_atencion_ms2` |
| D4 | Migración MS3 | ✅ `0011_avisos_ms3` |
| D5 | Migración MS4 | ✅ `0001_ms4` |

La app temporal `migraciones` terminó correctamente y fue eliminada.

---

## 5. Autenticación y roles

| # | Prueba | Resultado |
| --- | --- | --- |
| A1 | Seed de usuarios | ✅ 8 cuentas creadas/actualizadas |
| A2 | Login cliente | ✅ `200` con `access_token` y `user.roles=["cliente"]` |
| A3 | Login mecánico | ✅ `200` |
| A4 | Login administrador | ✅ `200` |
| A5 | `GET /api/auth/me` | ✅ Devuelve el usuario del token |
| A6 | Sin token | ✅ `401 {"detail":"No autenticado"}` |

---

## 6. Vehículos y órdenes

| # | Prueba | Resultado |
| --- | --- | --- |
| O1 | Crear vehículo | ✅ `201` |
| O2 | Crear orden | ✅ `201`, estado `1` |
| O3 | Asignar mecánico | ✅ Transición `1 → 2` |
| O4 | Capacidad diaria | ✅ Consulta y configuración |
| O5 | Capacidad por mecánico | ✅ Consulta y configuración |
| O6 | Transiciones `2 → 3 → 5 → 6 → 7` | ✅ Todas aplicadas |
| O7 | Bitácora | ✅ Registro y consulta de observaciones/acciones |
| O8 | Entrega de orden | ✅ Transición `6 → 7` |

---

## 7. Presupuestos

| # | Prueba | Resultado |
| --- | --- | --- |
| P1 | Crear presupuesto | ✅ `201`, versión 1 en `borrador` |
| P2 | Enviar presupuesto | ✅ Orden `2 → 3`, versión congelada |
| P3 | Aprobar | ✅ Orden `3 → 5`, `efecto_en_orden="en_reparacion"` |
| P4 | Rechazar | ✅ Orden `3 → 8`, reservas liberadas |
| P5 | Presupuesto versionado | ✅ Nueva versión sin sobrescribir la anterior |
| P6 | Ítems de repuesto y mano de obra | ✅ Totales correctos (ej. `23990.00`) |
| P7 | Orden con aprobación inicial | ✅ `GET .../primera-aprobacion` |

---

## 8. Inventario

| # | Prueba | Resultado |
| --- | --- | --- |
| N1 | Crear proveedor | ✅ `201` |
| N2 | Crear repuesto | ✅ `201`, umbral general 3 |
| N3 | Movimiento de ingreso | ✅ Stock actualizado |
| N4 | Reserva por orden | ✅ Comprometido 1, disponible 1 |
| N5 | Consumo | ✅ Descuento aplicado |
| N6 | Alerta de stock bajo | ✅ `alerta.nueva=true` al cruzar el umbral |

---

## 9. Evidencias y MinIO

| # | Prueba | Resultado |
| --- | --- | --- |
| E1 | Bucket `evidencias` | ✅ Creado (privado) |
| E2 | Usuario limitado `ms4-evidencias` | ✅ Solo ve `evidencias`; otro bucket → `403` |
| E3 | MS4 firma como `ms4-evidencias` | ✅ Confirmado con `mc admin trace` |
| E4 | Subida real de evidencia | ✅ `201`, 70 bytes |
| E5 | Descarga prefirmada | ✅ `200`, 70 bytes |
| E6 | URL de descarga | ✅ `expira_en=300`, firma S3v4 |

---

## 10. Notificaciones

| # | Prueba | Resultado |
| --- | --- | --- |
| T1 | `orden.estado_cambiado` | ✅ Aviso al cliente al cambiar estado |
| T2 | `presupuesto.enviado` | ✅ Cliente, orden 6 / presupuesto 4 |
| T3 | `presupuesto.decidido` | ✅ Administradores, orden 6 / presupuesto 4 |
| T4 | `stock.alerta` | ✅ Administradores, repuesto 1 (stock 2 < umbral 3) |
| T5 | `nueva_atencion.solicitada` | ✅ Administradores |
| T6 | `nueva_atencion.revisada` | ✅ Cliente solicitante |
| T7 | `GET /api/notificaciones` | ✅ Cabeceras `X-Notificaciones-Total` y `X-Notificaciones-No-Leidas` |
| T8 | Leer / leer todas / dispositivo | ✅ `PATCH .../leer` `204`, `leer-todas` `204`, dispositivo `201`/`200`/`204` |

Además:

- Marcar como leída una notificación ajena → `404`.
- El registro de entregas mostró `canal=correo, estado=pendiente` y
  `canal=push, estado=sin_dispositivo` (esperado: no hay SMTP ni FCM
  configurados).

---

## 11. Nueva atención

| # | Prueba | Resultado |
| --- | --- | --- |
| U1 | Cliente solicita nueva atención sobre orden cancelada | ✅ `201`, situación `pendiente` |
| U2 | Administrador lista solicitudes | ✅ Visible con `total` |
| U3 | Administrador acepta | ✅ Situación `aceptada` |
| U4 | Generar orden nueva | ✅ Orden 7 en estado `1` |

---

## 12. Frontend y dominios

| # | Prueba | Resultado |
| --- | --- | --- |
| F1 | `GET https://tallerconnect.inf.uct.cl/` | ✅ `200`, HTML de la SPA |
| F2 | Assets JS/CSS | ✅ `200` |
| F3 | Ruta SPA `/login` | ✅ `200` |
| F4 | `/healthz` | ✅ `200 ok` |
| F5 | `api-tallerconnect` `/api/health` | ✅ `200` |
| F6 | Swagger `/docs` | ✅ `200` |
| F7 | OpenAPI `/openapi.json` | ✅ `200`, 94 operaciones en 75 rutas |
| F8 | Dominios MS1–MS3 y MS4 interno | ✅ `/health` `200`; MinIO raíz `307` a consola |

---

## 13. Seguridad

| # | Prueba | Resultado |
| --- | --- | --- |
| S1 | CORS desde `https://tallerconnect.inf.uct.cl` | ✅ `200` con `Access-Control-Allow-Origin` correcto |
| S2 | CORS desde `https://ejemplo.cl` | ✅ `400` (no autorizado) |
| S3 | Cliente intenta crear orden | ✅ `403 "No tienes permiso..."` |
| S4 | Sin token en ruta protegida | ✅ `401 "No autenticado"` |
| S5 | MS4 usa usuario limitado, no root | ✅ Verificado |
| S6 | Documentación sin secretos | ✅ Revisada: solo cuentas de demostración |

---

## 14. Lo que **no** se probó (y por qué)

| Tema | Motivo |
| --- | --- |
| Envío real de correo | No hay cuenta SMTP; `MS1_NOTIFICATION_WORKER_ENABLED=false` |
| Push real a un dispositivo | No hay proyecto FCM configurado |
| Video de más de 12 MiB | La Gateway corta en 12 MiB; el límite de 100 MiB del servicio no es alcanzable desde fuera |
| Carga y concurrencia | No se hizo prueba de estrés |
| Recuperación ante desastre | No se ensayó una restauración completa de respaldo |
| Rotación de secretos en caliente | Procedimiento documentado, no ejecutado |
| Navegadores/dispositivos reales | Verificación por HTTP, no matriz de dispositivos |

Estos puntos están en [08 — Pendientes](08-pendientes-y-deuda.md).

---

## 15. Cómo reproducir la verificación

```bash
BASE=https://api-tallerconnect.inf.uct.cl

# 1. Salud
curl -s $BASE/api/health/servicios

# 2. Login
TOKEN=$(curl -s -X POST $BASE/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"administrador@pruebas.cl","password":"AdminPrueba123!"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 3. Órdenes y notificaciones
curl -s $BASE/api/ordenes -H "Authorization: Bearer $TOKEN"
curl -si "$BASE/api/notificaciones?limite=5" -H "Authorization: Bearer $TOKEN" | head -20

# 4. Evidencias de la orden 1
curl -s "$BASE/api/evidencias?orden_id=1" -H "Authorization: Bearer $TOKEN"
```

Para un flujo completo, seguir el guion de
[04 — Datos de prueba](04-datos-de-prueba.md#10-guion-mínimo-de-demostración).

---

## 16. Permisos, roles y datos visibles (24-11-2026)

Verificación específica de que **acciones y datos visibles** respetan los roles.
Se hizo en el ambiente real (`api-tallerconnect.inf.uct.cl` y
`tallerconnect.inf.uct.cl`) con las 8 cuentas demo de
[04 — Datos de prueba](04-datos-de-prueba.md).

### 16.1 Criterio de no mutación

Solo se usaron `GET`, login y navegación. Los únicos `POST` fueron rechazos
controlados contra identificadores inexistentes, para comprobar el guard sin
crear nada: crear orden como cliente → `403`, subir evidencia como cliente →
`403`, subir evidencia como mecánico a orden `999999` → `404`. No se marcaron
notificaciones como leídas ni se cambió ninguna orden, presupuesto o evidencia.

### 16.2 Pruebas automatizadas locales

| Conjunto | Resultado |
| --- | --- |
| `backend/tests/test_autorizacion.py` | ✅ 6 passed |
| `test_acceso_indebido_roles`, `test_acceso_recursos_ajenos_mismo_rol`, `test_exposicion_indebida_datos`, `test_ms4_autorizacion_evidencias`, `test_credenciales_vacias_y_multirol` | ✅ 103 passed |
| Usuarios/roles, órdenes, vehículos, perfil, notificaciones, evidencias, JWT, seguridad y MS3 | ✅ 411 passed, 112 skipped |
| `OrderActions`, `OrderActionsPanel`, `RoleLayout` (Vitest) | ✅ 54 passed |
| `ProtectedRoute` (Vitest) | ✅ 7 passed |

**Total local: 581 passed, 112 skipped.** Los skips son casos ya cubiertos o
no aplicables al ambiente de pruebas; ningún fallo.

### 16.3 API real: 73/73 comprobaciones

| Área | Verificaciones | Resultado |
| --- | --- | --- |
| Login y `/auth/me` de las 8 cuentas, anónimo y token inválido | 18 | ✅ `200` con roles correctos; sin token y token inválido → `401` |
| Órdenes: listado por cuenta, detalle, `solo_propietario` y ajenas | 21 | ✅ Cliente ve 1–7; mecánico ve 1,2,3,5,6; administrador y multirroles con administrador ven 1–7; cliente 8 y multirol sin propiedad ven `[]`; orden no asignada/ajena → `404` |
| Presupuestos y catálogos | 12 | ✅ Cliente ve solo versión enviada de su orden; ajeno → `404`; cliente no crea/envía ni ve repuestos/inventario → `403`; mecánico y administrador sí ven catálogo |
| Evidencias | 15 | ✅ Cliente ve 2 visibles y no la interna; mecánico y administrador ven 3; detalle interno para cliente → `404`; ajeno y orden no asignada → `404`; subida rechazada según rol |
| Notificaciones | 7 | ✅ Cada cuenta ve solo su bandeja; intersecciones vacías entre cliente/mecánico/administrador |

Detalles destacados:

- `solo_propietario=true` devuelve `200` al dueño, `404` a mecánico,
  administrador y multirol que no es dueño: **no filtra, oculta**.
- Multirol = unión de roles para **alcance**, pero no para **datos**: la cuenta
  4 (`cliente+mecánico`) no ve órdenes porque no tiene vehículo ni asignación.
- Las bandejas reales devolvieron 28 notificaciones al cliente 1, 0 al
  mecánico 2, 7 al administrador 3 y 0 al cliente 8, sin solapamiento.

### 16.4 Web real: portales, menús y acciones

| Cuenta | `/client` | `/mechanic` | `/admin` | Resultado |
| --- | --- | --- | --- | --- |
| 1 `cliente` | ✅ | 🔒 `cliente` | 🔒 `cliente` | Menú sin inventario, usuarios ni reasignación |
| 2 `mecánico` | 🔒 `mecanico` | ✅ | 🔒 `mecanico` | Orden 4 no asignada → “Orden no encontrada”; orden 5 asignada con presupuesto, bitácora y evidencias |
| 3 `administrador` | 🔒 `administrador` | 🔒 `administrador` | ✅ | Orden 5 con reasignación de mecánico y subida de evidencia |
| 4 `cliente+mecánico` | ✅ | ✅ | 🔒 `cliente, mecanico` | Sin escalada: no ve órdenes ajenas |
| 5 `cliente+administrador` | ✅ | 🔒 `administrador, cliente` | ✅ | Redirige al portal admin al entrar |
| 6 `mecanico+administrador` | 🔒 `administrador, mecanico` | ✅ | ✅ | Redirige al portal admin al entrar |
| 7 los tres roles | ✅ | ✅ | ✅ | Redirige al portal admin al entrar |

Comprobaciones adicionales en la UI:

- Sin sesión, las tres rutas protegidas redirigen a `/login` y `localStorage`
  queda sin `token`.
- El cliente ve en `/client/ordenes/1/evidencias` exactamente **2** imágenes
  (`Presupuesto`, `Reparación`), sin control de subida y sin la evidencia
  interna de `Diagnóstico`. El mecánico ve el formulario “Subir evidencia” en
  la misma orden.
- En `/client/presupuestos` solo aparecen los presupuestos propios con estado
  `Aprobado`/`Rechazado`; como todos los de demo ya están decididos, no se
  muestran botones de aprobar/rechazar. Ese comportamiento por estado está
  cubierto por los 54 tests de `OrderActions`/`OrderActionsPanel`.
- El texto de denegación usa la unión de roles de `getUserRoles()`, por ejemplo
  `Tu rol (cliente, mecanico) no tiene permisos para acceder a esta sección.`

**Resultado global de esta verificación: 73/73 en API, 581 passed en local y
todas las comprobaciones visuales acordes al rol. No se encontraron brechas de
permisos.**

---

## 17. Panel operativo del administrador (24-11-2026)

Cambios verificados en `Vicente` y ya visibles en la web desplegada: el dashboard
dejó de mostrar valores de relleno y ahora consulta datos reales con
`Promise.allSettled`.

### 17.1 Verificación local

| Comando | Resultado |
| --- | --- |
| `npm test -- --run src/presentation/pages/admin/AdminDashboardPage.test.tsx src/infrastructure/api/PresupuestoService.test.ts` | ✅ 22 passed |
| `npm test` (suite completa de `frontend/`) | ✅ **1277 passed**, 143 archivos, 0 fallos |
| `npm run lint` | ✅ sin errores; solo 2 warnings preexistentes en notificaciones |
| `npm run build` (`tsc -b && vite build`) | ✅ build correcto (aviso no bloqueante: chunk > 500 kB) |

Casos cubiertos por las pruebas nuevas:

- KPIs desde la API, sin `'—'` permanente ni sección “Actividad Reciente”.
- Cola activa: excluye estados 7 y 8, enlaza al detalle y muestra patente,
  vehículo, estado y mecánico.
- KPI “Presupuestos por Revisar” cuenta solo `estadoUltimaVersion === 'enviada'`
  y llama a `GET /presupuestos` con `limite: 200`.
- Panel de inventario/proveedores: alertas, repuestos, bajo umbral,
  distribuidores, últimos movimientos y accesos rápidos con sus `href`.
- Degradación parcial: si falla solo presupuestos, el resto del panel sigue y
  aparece “Datos parciales”; si fallan las tres fuentes básicas aparece
  `ErrorState` y el botón “Reintentar” recupera los datos.
- Carga de mecánicos paginada (5 por página).

### 17.2 Verificación de ambiente (solo lectura)

Inicialmente `POST /api/auth/login` devolvió `504` y `/api/health/servicios`
devolvió `503` con `ms1_auth` y `ms4_evidencias` en `tiempo_agotado`. La
incidencia fue transitoria: en la validación de la tarea siguiente el login de
las tres cuentas demo respondió `200` y todos los flujos cargaron.

Comprobación real cerrada con la cuenta de administrador:

```
GET /api/presupuestos?limite=200  → 200
{ total: 4, devueltos: 4, enviadas: 0 }
```

Coincide con el KPI “Presupuestos por Revisar” mostrado por el dashboard real
(`0`). El contrato también se confirmó leyendo
`backend/services/ms3_presupuestos/routers/presupuestos.py`: sin `orden_id` aplica
para personal, `limite` acepta hasta 200 y el cliente solo ve versiones enviadas
de su propia orden. No se hicieron `POST/PATCH/DELETE` de datos de negocio.

---

## 18. Validación funcional de los principales flujos web (24-11-2026)

Validación **en la web desplegada** (`tallerconnect.inf.uct.cl`) con el
navegador integrado y las cuentas demo de
[04 — Datos de prueba](04-datos-de-prueba.md). No se usaron credenciales
versionadas ni se alteraron datos de negocio.

### 18.1 Criterio

- Solo navegación `GET`; los únicos `POST` fueron `auth/login` y el cierre de
  sesión.
- No se aprobaron/rechazaron presupuestos, no se confirmaron cancelaciones, no
  se crearon órdenes/repuestos/proveedores, no se subió evidencia, no se
  registraron movimientos ni se marcaron notificaciones como leídas.
- Se tomaron como fallo los textos “No se pudo…”, “Sin conexión” o errores de
  consola. El único `4xx` esperado fue el `404` de una orden no asignada.

### 18.2 Flujos públicos y de sesión

| Flujo | Resultado |
| --- | --- |
| Landing `/` | ✅ “El taller del futuro, hoy.” y accesos a ingresar/registro |
| `/admin`, `/client`, `/mechanic` sin sesión | ✅ los tres redirigen a `/login` |
| Login administrador / cliente / mecánico | ✅ `200`, redirección a `/admin`, `/client` y `/mechanic` según rol |
| Cierre de sesión | ✅ vuelve a `/login` y `localStorage.token` queda nulo |
| Tras logout, `/admin` | ✅ vuelve a `/login` |

### 18.3 Administrador

| Ruta | Comprobación | Resultado |
| --- | --- | --- |
| `/admin` | KPIs 7 órdenes / 4 activas / 6 vehículos / 4 mecánicos / 0 presupuestos por revisar; cola con órdenes 7, 5, 1 y 6; alertas, movimientos y accesos rápidos | ✅ |
| Cola activa → detalle | Enlace `Orden #7` abre `/admin/ordenes/7` | ✅ |
| Alerta de stock → detalle | Enlace del dashboard abre `/admin/inventario/stock/1` y muestra stock 2 / comprometido 1 / disponible 1 | ✅ |
| `/admin/ordenes` | Listado con 6 órdenes y filtros de estado | ✅ |
| `/admin/ordenes/1` | Ciclo, historial, presupuesto, consumo, disponibilidad y evidencias | ✅ |
| `/admin/nuevas-atenciones`, `/admin/cancelaciones` | Bandejas con estados vacíos/ocupados según datos demo | ✅ |
| `/admin/usuarios`, `/admin/clientes`, `/admin/vehiculos` | 9 usuarios, 6 clientes y catálogo de 6 vehículos | ✅ |
| `/admin/configuracion` | Capacidad del taller e historial | ✅ |
| `/admin/inventario` y `/alertas`, `/movimientos`, `/umbral`, `/stock/1`, `/distribuidores` | Catálogo, 1 alerta, 7 movimientos, umbral 3 y distribuidores | ✅ |
| `/admin/notificaciones` | 7 notificaciones, 6 sin leer | ✅ |

### 18.4 Cliente

| Ruta | Comprobación | Resultado |
| --- | --- | --- |
| `/client` | Portal con accesos a vehículos y nuevas atenciones | ✅ |
| `/client/vehiculos` | 6 vehículos propios con ficha técnica | ✅ |
| `/client/ordenes`, `/ordenes/1` | 7 órdenes propias y detalle de la orden 1 | ✅ |
| `/client/presupuestos` | 4 presupuestos propios en estados Aprobado/Rechazado; sin botones de decisión | ✅ |
| `/client/ordenes/1/evidencias` | Exactamente **2** evidencias visibles (Presupuesto y Reparación) y **sin** control de subida | ✅ |
| `/client/servicios` | 4 servicios en proceso y 3 finalizados | ✅ |
| `/client/nuevas-atenciones`, `/notificaciones` | Solicitud n° 1 y 28 notificaciones, 10 sin leer | ✅ |
| `/admin` y `/mechanic` | Redirección a `/acceso-denegado` con `403` y rol `cliente` | ✅ |

### 18.5 Mecánico

| Ruta | Comprobación | Resultado |
| --- | --- | --- |
| `/mechanic` | 5 asignadas, 3 activas, 2 con avance pendiente | ✅ |
| `/mechanic/ordenes`, `/ordenes/1` | 5 órdenes asignadas; detalle con ciclo, disponibilidad y presupuesto | ✅ |
| `/mechanic/ordenes/1/presupuesto` | Versión 1 aprobada; el texto indica que el Administrador revisa precios | ✅ |
| `/mechanic/ordenes/1/evidencias` | Control “Subir evidencia” presente | ✅ |
| `/mechanic/estados`, `/vehiculos` | 2 órdenes con avance y 5 vehículos asignados | ✅ |
| `/mechanic/inventario*`, `/umbral` y `/distribuidores` | Catálogo, 1 alerta, 7 movimientos, umbral y distribuidores; sin botones “Nuevo repuesto”, “Nuevo proveedor” ni “Guardar” umbral | ✅ |
| `/mechanic/notificaciones` | Bandeja vacía acorde a la cuenta | ✅ |
| `/mechanic/ordenes/4` (no asignada) | Texto “Orden no encontrada” y `GET /api/ordenes/4` → `404` | ✅ |
| `/admin` y `/client` | Redirección a `/acceso-denegado` con `403` y rol `mecanico` | ✅ |

### 18.6 Resultado

- **Todos los flujos principales cargaron sin errores de consola.**
- El único `4xx` de red fue el `404` esperado de la orden no asignada al
  mecánico.
- `/api/health/servicios` había marcado `ms1_auth`/`ms4_evidencias` como
  `tiempo_agotado` al inicio, pero los login y las evidencias funcionaron
  después: se trata de una señal transitoria del healthcheck, no de un fallo de
  los flujos validados.
- No se detectaron brechas de rol: el cliente y el mecánico quedan fuera de
  `/admin`, y el mecánico no ve acciones administrativas de inventario.

**Conclusión: validación funcional satisfactoria de los flujos web principales
en los tres portales.**
