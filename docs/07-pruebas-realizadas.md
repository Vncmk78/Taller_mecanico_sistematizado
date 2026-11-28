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
| B6 | Deploy automático de `main` @ `ee84ed4` | ✅ Docker Build en `success` (4 jobs); Kubero en `:sha-ee84ed4` — ver sección 18 |

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

---

## 19. Corrección de H-01: asignación del mecánico antes de operar stock (24-11-2026)

### 19.1 Cambio

El checklist de seguridad (`backend/docs/checklist-revision-seguridad-rutas.md`)
marcaba como **H-01** que MS3 permitía a un Mecánico consultar disponibilidad,
reservar, consumir y liberar stock de una orden que no tenía asignada. Se agregó
`_exigir_orden_asignada_al_mecanico` en
`backend/services/ms3_presupuestos/routers/inventario.py` y se aplicó a las
cinco operaciones con `orden_id`:

- `POST /inventario/disponibilidad` (cuando el cuerpo lleva `orden_id`);
- `GET /inventario/ordenes/{orden_id}/disponibilidad`;
- `POST /inventario/ordenes/{orden_id}/reserva`;
- `POST /inventario/ordenes/{orden_id}/consumos`;
- `POST /inventario/ordenes/{orden_id}/liberacion`.

La comprobación reutiliza `VerificadorOrdenesHttp.verificar_creacion_presupuesto`
(contra MS2), igual que `POST /inventario/movimientos`. Administrador queda
exento; `OrdenNoVisible` se traduce a `404` con
`detail = "Orden <id> no existe"` y un fallo de MS2 propaga `503` **antes** de
leer o mover stock. También se documentaron esos códigos en las respuestas de
las rutas y se eliminaron los imports duplicados del módulo.

### 19.2 Casos cubiertos

`backend/tests/test_acceso_indebido_roles.py`:

- Mecánico no asignado: las cinco operaciones devuelven `404` y no alteran
  presupuestos ni movimientos.
- `Cliente + Mecánico` dueño de la orden pero sin asignación: también `404` (ser
  propietario no sustituye la asignación).
- Mecánico asignado: consulta y consumo de su orden siguen funcionando.
- Administrador sin asignación: permitido y sin llamada innecesaria a MS2.
- MS2 caído: `503` y ninguna escritura (fail-closed).

`backend/services/ms3_presupuestos/tests/test_disponibilidad_stock.py`:

- Override del verificador que simula orden no asignada para las cinco rutas,
  de modo que el fixture permisivo de la suite MS3 no oculte una regresión.

`backend/tests/test_integracion_presupuesto_stock.py`:

- El flujo del mecánico 77 ahora asigna la orden a ese mecánico.
- La comprobación de stock insuficiente para una orden ajena se hace como
  Administrador, coherente con el nuevo guard.

### 19.3 Ejecución

```
python -m pytest tests/test_acceso_indebido_roles.py tests/test_integracion_presupuesto_stock.py -q
59 passed, 11 skipped, 7 warnings

python -m pytest services/ms3_presupuestos/tests/test_disponibilidad_stock.py -q -rs
27 skipped, 1 warning

python -m pytest -q
1 failed, 2465 passed, 617 skipped, 55 warnings in 741.44s
```

Los `27 skipped` se deben a que el entorno local no tiene PostgreSQL de MS3 en
`localhost:5435`; esa suite usa SQLite en otros archivos y la cobertura
ejecutable de H-01 quedó demostrada en el primer comando. No se hicieron
mutaciones en producción: todas las pruebas usan bases descartables o `TestClient`.

### 19.4 Falla ajena al cambio

La suite backend completa previa al cambio terminó en
`1 failed, 2451 passed, 612 skipped, 55 warnings in 737.57s`; la ejecución final
de esta revisión dio `1 failed, 2465 passed, 617 skipped, 55 warnings in 741.44s`
(14 pruebas más y ninguna falla nueva). El único fallo fue siempre
`test_archivo_congelado_coincide_con_el_publicado`: el entorno tiene
`pydantic 2.14.1`, mientras `backend/requirements.txt` fija `pydantic>=2.12,<2.14`
porque 2.14 cambia la publicación de `pattern` en esquemas `Decimal`. Se
reprodujo el mismo fallo en un worktree limpio sobre `bb38caa`, antes de tocar
código, por lo que **no es una regresión de H-01**. No se reexportó el contrato
OpenAPI ni se subió su versión: la corrección congelada se debe hacer con el
rango de dependencias declarado.

**Resolución:** el repositorio ya trae `backend/.venv` con `pydantic 2.13.5`,
dentro del rango declarado. Ejecutando con ese intérprete
(`.venv\Scripts\python.exe -m pytest tests/test_gateway_openapi_version_estable.py`)
la prueba pasa (`14 passed` junto con la suite nueva de imports). El fallo era
solo el intérprete global usado en la ejecución local, no un problema del código
ni del contrato: el job `backend` de `Verificación SGTM` sobre `sha-f9b8ee6`
terminó en `success`.

---

## 20. Revisión de formularios y coherencia de estados (24-11-2026)

Además de **H-01**, la revisión de los cambios de los compañeros encontró
comportamientos de frontend que podían duplicar stock, ocultar rechazos o dar
una señal operativa falsa. Se corrigieron con prueba de regresión en cada caso:

| Hallazgo | Corrección | Prueba |
| --- | --- | --- |
| `AdminInventoryMovementsPage` generaba una `claveOperacion` nueva en cada reintento; si el servidor aplicaba el movimiento y se perdía la respuesta, el reintento movía stock dos veces. | La clave se guarda en `useRef` con la firma de los datos; se conserva ante resultados inciertos (sin respuesta, 502/503/504 o 500 de Gateway) y solo se descarta tras éxito o rechazo definitivo. | `AdminInventoryMovementsPage.test.tsx`: el primer envío falla con 503 y el segundo reutiliza la misma clave. |
| `ConsumoRepuestosPanel` mostraba «sin presupuesto» ante cualquier `404`, incluido el `404` de orden inexistente/no asignada de **H-01**. | El aviso benigno exige que el `detail` contenga «no tiene presupuesto»; los demás `404` van a `ErrorState`. | `ConsumoRepuestosPanel.test.tsx`: `detail: 'Orden 999 no existe'` muestra error con reintento. |
| Tras un consumo correcto, si fallaba el refresco de disponibilidad se limpiaba la clave y quedaban cantidades viejas listas para reenviar. | El refresco fallido muestra advertencia con «Recargar disponibilidad», deshabilita «Registrar consumo» y conserva la clave hasta que la vista vuelve a estar fresca. | `ConsumoRepuestosPanel.test.tsx`: consumo resuelto + siguiente GET rechazado. |
| `AdminDashboardPage` podía decir «Sistema En línea» con KPIs en «—» si fallaba solo una de vehículos, usuarios u órdenes. | Esas tres fuentes se agregan a `fallos`, por lo que el estado pasa a «Datos parciales» o «Sin conexión». | `AdminDashboardPage.test.tsx`: falla solo `getAllVehicles`. |
| Al eliminar proveedor o repuesto, el `catch` cerraba el diálogo sin mostrar el `409` de MS3. | Se muestra el `detail` del servidor dentro de la confirmación y el diálogo permanece abierto. | Pruebas nuevas en `AdminDistributorsPage.test.tsx` y `AdminInventoryPage.test.tsx`. |
| `EvidenceUploadForm` grababa `id: null` si fallaba la consulta del presupuesto y afirmaba que la orden no tenía uno. | Estado de error separado de «ausente», con botón «Reintentar consulta»; el envío se bloquea con un mensaje distinto. | Pruebas en `EvidenceUploadForm.test.tsx` y ajuste de `EvidenceUploadForm.validacion.test.tsx`. |
| `NotificationsPage` silenciaba los fallos al marcar avisos como leídos, a diferencia de `NotificationBell`. | Ambos `catch` poblan el `error` ya existente y muestran el aviso con opción de reintento. | `NotificationsPage.test.tsx`: fallos de `markAsRead` y `markAllAsRead`. |
| Fallos al cargar el catálogo de repuestos en el editor de presupuesto dejaban un selector vacío sin explicación. | `catalogoError` con mensaje y botón «Reintentar catálogo», distinto de un catálogo legítimamente vacío. | `MechanicBudgetPage.test.tsx`: primer `getRepuestos` rechazado y reintento correcto. |

En backend se alineó además el cálculo de saldos del coordinador de reservas
(`services/ms3_presupuestos/services/disponibilidad_repuestos.py`) con la regla
canónica de `RepositorioMovimientos.comprometido_por_ordenes`: saldo
`max(0, saldo − cantidad)` en orden cronológico. Antes, sumar/restar sin ordenar
podía dejar un saldo negativo falso tras un consumo libre previo y provocar un
`409`/`500` al reservar o al revertir una reserva rechazada. La prueba
`test_coordinador_usa_saldo_cronologico_tras_consumo_libre` cubre reserva y
reversa.

### 20.1 Ejecución

```
npx vitest run src/presentation/pages/admin/AdminInventoryMovementsPage.test.tsx
16 passed (16)

npx vitest run src/presentation/components/orders/ConsumoRepuestosPanel.test.tsx
20 passed (20)

npx vitest run src/presentation/pages/admin/AdminDashboardPage.test.tsx
10 passed (10)

npx vitest run src/presentation/pages/admin/AdminDistributorsPage.test.tsx
15 passed (15)

npx vitest run src/presentation/pages/admin/AdminInventoryPage.test.tsx
22 passed (22)

npx vitest run src/presentation/components/evidence/EvidenceUploadForm.test.tsx
8 passed (8)

npx vitest run src/presentation/components/evidence/EvidenceUploadForm.validacion.test.tsx
24 passed (24)

npx vitest run src/presentation/pages/shared/NotificationsPage.test.tsx
6 passed (6)

npx vitest run src/presentation/pages/mechanic/MechanicBudgetPage.test.tsx
10 passed (10)

npm test
143 files passed, 1288 tests passed

npm run lint
2 warnings preexistentes de react(set-state-in-effect) en NotificationBell y NotificationsPage

npm run build
TS + Vite correctos; único aviso: chunk >500 kB

python -m pytest tests/test_disponibilidad_repuestos.py -q
6 passed, 1 warning

python -m pytest services/ms3_presupuestos/tests/test_reglas_reserva_stock.py tests/test_disponibilidad_repuestos.py tests/test_integracion_presupuesto_stock.py tests/test_acceso_indebido_roles.py -q
65 passed, 28 skipped

python -m pytest tests/test_gateway_openapi_version_estable.py -q
1 failed, 9 passed, 7 warnings  # único fallo, preexistente (ver §19.4)

python -m pytest -q
1 failed, 2465 passed, 617 skipped, 55 warnings in 741.44s
```

No se hicieron mutaciones en producción: todas las pruebas usan `TestClient`,
bases descartables o mocks. El desajuste de límites de video entre Gateway y MS4
sigue documentado como deuda en `docs/08-pendientes-y-deuda.md` §1.3; no se
cambió.

---

## 21. Despliegue automático `sha-ee84ed4` (24-11-2026)

Despliegue de la Gateway y de los servicios en el ambiente público tras el merge
de `Develop` en `main` (commit `ee84ed4`, "panel operativo del administrador").

### 21.1 Pipeline

| # | Paso | Resultado |
| --- | --- | --- |
| D1 | Trigger | ✅ `push` a `main`, commit `ee84ed4` |
| D2 | Job `Solo ejecutable desde main` | ✅ `success` (3 s) |
| D3 | Job `Backend (Gateway + MS1-MS4)` | ✅ `success` (48 s) → `ghcr.io/vncmk78/tallerconnect-backend:sha-ee84ed4` |
| D4 | Job `Frontend (React + Nginx)` | ✅ `success` (1 min 7 s) → `ghcr.io/vncmk78/tallerconnect-frontend:sha-ee84ed4` |
| D5 | Job `Actualizar Kubero al sha publicado` | ✅ `success` (30 s): `gateway`, `ms1`–`ms4` y `web` en `sha-ee84ed4`; `minio` sin cambios |
| D6 | Salud verificada por el propio job | ✅ `/api/health/servicios` y `/healthz` en `ok` |
| D7 | Migraciones | ✅ No aplica: el commit no trae migraciones nuevas (el job las detecta y omite el deploy si existen) |
| D8 | Workflow `Verificación SGTM` del mismo merge | ✅ `success` (backend 4 min 20 s, frontend 1 min 51 s) |

Duración total del Docker Build: 1 min 47 s.

### 21.2 Verificación posterior (24-11-2026 15:51 UTC)

Ejecutada desde fuera del clúster con `backend/scripts/verificar_salud.py`:

```
[ OK ] gateway              HTTP 200          ok
[ OK ] servicios (bases)    HTTP 200          ok
[ OK ] ms1_auth             HTTP 200          proceso=ok (11 ms), base=ok (23 ms)
[ OK ] ms2_taller           HTTP 200          proceso=ok (11 ms), base=ok (23 ms)
[ OK ] ms3_presupuestos     HTTP 200          proceso=ok (10 ms), base=ok (20 ms)
[ OK ] ms4_evidencias       HTTP 200          proceso=ok (16 ms), base=ok (67 ms), almacenamiento=ok (141 ms)
6/6 comprobaciones OK
```

| # | Comprobación | Resultado |
| --- | --- | --- |
| V1 | `GET https://api-tallerconnect.inf.uct.cl/openapi.json` → `info.version` | ✅ `3.1.0` (contrato vigente) |
| V2 | `GET https://api-tallerconnect.inf.uct.cl/api/health` | ✅ `200`, con cabecera `X-Request-ID` |
| V3 | `GET https://api-tallerconnect.inf.uct.cl/docs` | ✅ `200` |
| V4 | `GET https://tallerconnect.inf.uct.cl/` | ✅ `200` |
| V5 | `GET https://tallerconnect.inf.uct.cl/healthz` | ✅ `200` |
| V6 | `GET https://ms4-tallerconnect.inf.uct.cl/minio/health/live` | ✅ `200` |

### 21.3 Reproducir

```bash
cd backend
python scripts/verificar_salud.py --base https://api-tallerconnect.inf.uct.cl --json salidas-integracion/salud-despliegue.json
```

### 21.4 Rollback

Volver las 6 apps al tag anterior en Kubero y redeploy (runbook §4.3). Como
esta versión no trae migraciones, no hace falta restaurar la base.

---

## 22. Integración web, base de datos y app móvil (24-11-2026)

Verificación de que los clientes (web de Integra II y app móvil de Integra IV)
llegan a la Gateway y, a través de ella, a las cuatro bases y a MinIO, con la
versión desplegada `sha-ee84ed4`. Solo lectura: no se crearon datos en producción.

```
Web (tallerconnect.inf.uct.cl)            ─┐
App móvil (frontend-movil.inf.uct.cl)     ─┼─► Gateway ─► MS1–MS4 ─► PostgreSQL ×4 + MinIO
App móvil (tallerconnect-frontend…)       ─┘
```

### 22.1 Web de Integra II ↔ Gateway ↔ bases

Recorrida manual como Administrador en `https://tallerconnect.inf.uct.cl`, con
DevTools → Network (Fetch/XHR). Todas las llamadas salen del bundle
`index-BaVgsO8G.js` (versión desplegada).

| # | Llamada (`/api/...`) | Microservicio / base | Resultado |
| --- | --- | --- | --- |
| W1 | `usuarios?limite=100`, `notificaciones?limite=15` | MS1 | ✅ 200 |
| W2 | `ordenes?limite=100`, detalle `ordenes/{4,6,7}`, `historial` | MS2 | ✅ 200 |
| W3 | `presupuestos?orden_id={6,7}` | MS3 | ✅ 200 |
| W4 | `repuestos`, `proveedores`, `inventario/movimientos`, `inventario/alertas`, `umbral-general`, `historial-umbral` | MS3 | ✅ 200 |
| W5 | `inventario/ordenes/{4,6}/disponibilidad` | MS3 | ✅ 200 |
| W6 | `evidencias?orden_id={6,7}` | MS4 | ✅ 200 |
| W7 | `inventario/ordenes/7/disponibilidad` | MS3 | ⚠️ 404 — ver hallazgo H1 |

### 22.2 App móvil de Integra IV ↔ Gateway ↔ bases

Las dos builds web de la app Expo usan como `API_URL` su propio dominio + `/api`
y su servidor reenvía a la Gateway (mismo origen: sin CORS).

| # | Comprobación | `frontend-movil.inf.uct.cl` | `tallerconnect-frontend.inf.uct.cl` |
| --- | --- | --- | --- |
| M1 | `GET /login` | ✅ 200 | ✅ 200 |
| M2 | `GET /api/health` (vía su proxy) | ✅ `{"status":"ok","servicio":"gateway"}` | ✅ igual |
| M3 | `GET /api/health/servicios` | ✅ 4 servicios `ok` | ✅ igual |
| M4 | `POST /api/auth/login` con credenciales inválidas | ✅ 401 de MS1 | ✅ 401 de MS1 |
| M5 | Login como Cliente + `GET /api/ordenes` | — | ✅ `200 OK`, `x-total-count: 7`, `x-request-id` de la Gateway, HSTS |
| M6 | `verificar_salud.py --base https://frontend-movil.inf.uct.cl` (todo el diagnóstico a través del proxy de la app) | ✅ 6/6 OK (MS4: base 190 ms, almacenamiento 444 ms) | — |

M5 (captura en DevTools): `Request URL https://tallerconnect-frontend.inf.uct.cl/api/ordenes`,
`Status 200`, cabeceras `x-total-count` y `x-request-id` emitidas por la Gateway,
lo que prueba el recorrido app móvil → proxy → Gateway → MS2 → base.

### 22.3 Hallazgos

| # | Hallazgo | Responsable | Gravedad |
| --- | --- | --- | --- |
| H1 | La web trata el **404** de `GET /api/inventario/ordenes/{id}/disponibilidad` como error. MS3 responde 404 cuando la orden **aún no tiene presupuesto** (contrato), pero `ConsumoRepuestosPanel.tsx` solo reconoce el 409 como "sin presupuesto" y muestra *"No se pudo cargar la disponibilidad de repuestos"* en órdenes nuevas. Arreglo: tratar 404 igual que 409 y agregar la prueba. | Frontend Integra II | Baja (UX) |
| H2 | La build desplegada de `frontend-movil` define el servicio de `/notificaciones` pero ninguna pantalla lo usa: la app no muestra notificaciones. El endpoint funciona (la web lo consume con 200). | Integra IV | Media |
| H3 | El código de la app móvil conserva `https://tallerconect.vercel.app/api` como URL por defecto (`INTEGRATION`/`PRODUCTION`). Ese despliegue ya no existe (`404 DEPLOYMENT_NOT_FOUND`). La build web no lo usa, pero una build nativa (Expo Go/APK) sin `EXPO_PUBLIC_API_URL` caería ahí. Debe usar `https://api-tallerconnect.inf.uct.cl/api`. | Integra IV | Media |
| H4 | Las apps `frontend-movil` y `frontend` de Integra IV no estaban documentadas; se agregaron a [02 — Despliegue](02-despliegue-kubero.md#3-pipeline-y-aplicaciones). | Integra II | — |

### 22.4 Reproducir

```bash
cd backend
python scripts/verificar_salud.py --base https://api-tallerconnect.inf.uct.cl
python scripts/verificar_salud.py --base https://frontend-movil.inf.uct.cl   # a través del proxy de la app móvil
```

En el navegador: login con las cuentas de [04 — Datos de prueba](04-datos-de-prueba.md),
DevTools → Network → Fetch/XHR, filtrar por `ordenes`, `evidencias`, `presupuestos`.

---

## 23. Diagnóstico de Kubero tras `sha-181e65d` (27-11-2026)

Inspección **solo de lectura** en `https://kubero.inf.uct.cl` (sin editar,
reiniciar ni borrar nada). Se revisaron los dos pipelines, las etiquetas de las
apps y los registros/eventos de MS1, MS2 y MS3.

### 23.1 Evidencia observada

| Elemento | Resultado leído |
| --- | --- |
| Pipeline `tallerconnect` (Producción) | `frontend-movil`, `gateway`, `minio`, `ms1`, `ms2`, `ms3`, `ms4`, `web`. Backend y `web` en `sha-1f96253`; `frontend-movil` en `73948df…`. |
| Pipeline `tallerconnect-scrum641` (Test) | 12 apps `demo732-*` y `qa641-*`, todas en `sha-181e65d`. Es el pipeline inesperado; **no se tocó**. |
| MS1 / MS2 / MS3 | Un pod sano (iniciado ayer, `GET /health` → 200) y un pod en `CrashLoopBackOff` (iniciado hace 4 h, 52–55 reinicios). Eventos: `Pulling image "…:sha-1f96253"` y `Back-off restarting failed container`. |
| Registros de los pods caídos | `Traceback` → `services/__init__.py` → `services/ms4_evidencias/__init__.py` → `services/ms4_evidencias/config.py` → `pydantic_core.ValidationError: 1 validation error for Settings: JWT_SECRET_KEY, Field required`. Idéntico en MS1, MS2 y MS3. |
| Variables de entorno de MS1 en Kubero | `SGTM_SERVICIO=ms1`, `MS1_DATABASE_URL`, `MS1_JWT_SECRET_KEY`, … No existe `MS4_JWT_SECRET_KEY`. |

### 23.2 Causa raíz

El commit `0ab861f` (25-11-2026) convirtió `backend/services/__init__.py` en una
copia de la app de MS4: importa `services.ms4_evidencias.config` y crea `app`.
Como Python ejecuta `__init__.py` del paquete antes que cualquier submódulo,
arrancar `services.ms1_auth.main`, `services.ms2_taller.main` o
`services.ms3_presupuestos.main` instancia también `Settings` de MS4. Ese modelo
exige `MS4_JWT_SECRET_KEY` (mostrado como campo `JWT_SECRET_KEY` en el error).
Los pods nuevos con `sha-181e65d`/`sha-1f96253` no reciben esa variable y mueren
al arrancar; los pods anteriores seguían sirviendo con la imagen antigua.

### 23.3 Corrección y prueba

- `backend/services/__init__.py` vuelve a ser un initializer inerte: no importa
  configuración ni expone `app`. La app de MS4 sigue en
  `backend/services/ms4_evidencias/main.py`.
- `backend/tests/test_import_paquete_servicios.py` reproduce el entorno de los
  pods (sin `MS4_*` y sin `.env`) y comprueba que importan `services`,
  `services.ms1_auth.main`, `services.ms2_taller.main` y
  `services.ms3_presupuestos.main`. Antes del cambio falla con el mismo
  `ValidationError`; después pasan las 4 pruebas.
- Suite de no regresión: `165 passed` en
  `test_gateway_smoke_prefijos.py`, `test_integracion_prefijos.py`,
  `test_gateway_evidencias.py` y `test_gateway_openapi.py`.
- Suite completa del backend: `2497 passed, 617 skipped, 1 failed` ejecutada con
  el Python global (`pydantic 2.14.1`). El único fallo fue
  `test_archivo_congelado_coincide_con_el_publicado`; con el `backend/.venv`
  (`pydantic 2.13.5`, rango declarado) esa prueba pasa, y el job `backend` de
  `Verificación SGTM` sobre `sha-f9b8ee6` terminó en `success`. Ver §19.4.

### 23.4 El «x» de GitHub Actions

La otra check suite del mismo SHA pertenece a `Verificación SGTM`
(`.github/workflows/verificacion.yml`). Al primer chequeo, el job `backend`
estaba `in_progress` y la anotación visible era «Process completed with exit
code 1» del paso «Suite completa, con PostgreSQL y S3 reales». La ejecución
terminó después en **`success`** para `frontend` y `backend` (sin anotaciones),
al igual que los seis jobs de `docker-build.yml`, incluido «Actualizar Kubero al
sha publicado». El fallo transitorio procedía de la ejecución local con
`pydantic 2.14.1` (§19.4) y **no** fue la causa del CrashLoopBackOff: el
contenedor moría antes de iniciar por un `ValidationError`, sin ejecutar pruebas.

---

## 24. Retiro de la plataforma anterior del repositorio (27-11-2026)

El usuario autorizó borrar el código muerto de Vercel/Neon que quedaba en el
repo. Se eliminaron `vercel.json`, `backend/scripts/migrar_neon.ps1`,
`backend/tests/test_despliegue_vercel.py` y el directorio local `.vercel/` con
sus identificadores de proyecto. El *shim* `migrar_neon.ps1` sólo redirigía a
`migrar.ps1`; los tests borrados sólo validaban el contrato de despliegue
retirado.

Las utilidades todavía usadas por MS1/MS2/MS3
(`services/ms2_taller/direccion_ms3.py` y `shared/direccion_notificaciones.py`)
se simplificaron: ya no leen `VERCEL_*`, conservan el valor local por defecto y
el JWT/la cabecera de servicio. `GATEWAY_CORS_ORIGIN_REGEX` ahora es `None` por
defecto, así que no se autorizan dominios de la plataforma retirada sin
configuración explícita. La detección de claves `npg_` del escáner de secretos
se conservó con otro nombre: sigue siendo útil para encontrar credenciales
antiguas filtradas. Los estudios y evidencias históricos se conservan como
registro; `docs/README.md` los marca como tal.

### 24.1 Verificación

- Pruebas focales: `109 passed` (URLs internas, cabeceras, CORS, ambiente de
  pruebas, importación de paquetes y contrato OpenAPI).
- Suite completa con `backend/.venv` (`pydantic 2.13.5`):
  `2469 passed, 617 skipped, 1 warning in 877.15s`. No hay fallos; los 617
  saltos siguen siendo las pruebas que requieren PostgreSQL/MinIO aislados (§19).
- No se tocó Vercel ni Neon externamente: el alcance fue únicamente el
  repositorio. No se hizo merge a `Develop`/`main` ni redeploy.

## 25. UAT en producción con cuentas demo (28-11-2026)

El usuario autorizó la UAT más completa posible en el ambiente de producción,
usando las cuentas demo de `docs/04-datos-de-prueba.md` y **datos nuevos** marcados
`UAT`. No se borraron ni modificaron datos de negocio existentes. Se priorizó el
recorrido de UI y los `GET`; las mutaciones quedaron limitadas al guion de la
orden de prueba. Las contraseñas demo no se repiten aquí: están en el documento
de datos de prueba.

### 25.1 Estado inicial y publicaciones

- Salud inicial: primer intento `5/6` por un `503` transitorio de
  `ms4_evidencias` (`base=tiempo_agotado`); repetición inmediata `6/6 OK`. No
  fue una incidencia de código.
- Antes de esta UAT, producción servía el bundle `index-BPsOgBAY.js` (cookies).
  Durante la prueba se detectó y corrigió una incidencia real de subida de
  evidencias (§25.4), con tres publicaciones sucesivas:
  - `Vicente`: `2577bc6` → `0cbd93d` → `4ba5d9d`.
  - `Develop`: `5b7d488` → `3639e0a` → `86dc56a`.
  - `main`: `44bccc9` → `44282d1` → `153afb4`.
- CI final de `153afb4`: `Verificación SGTM` #158 y `Docker Build` #44 en
  `success`; jobs `frontend`, `backend` y `Actualizar Kubero al sha publicado`
  correctos. Producción sirve `index-B0Uso6qX.js`.
- No se repitió ningún deploy manual: el último job automático publicó el sha.

### 25.2 Recorrido de UI por roles

Sin errores de consola en los recorridos:

- **Cliente** (`cliente@pruebas.cl`, ID 1): 9 pantallas (portal, vehículos,
  estado del servicio, órdenes, detalle, presupuestos, nuevas atenciones,
  avisos, política de cookies). La lista de presupuestos tarda ~6 s por llamadas
  secuenciales, pero carga correctamente.
- **Mecánico** (`mecanico@pruebas.cl`, ID 2): 14 pantallas, además del editor de
  orden (5 estados del formulario).
- **Administrador** (`administrador@pruebas.cl`, ID 3): 19 pantallas.
- **Cuentas multi-rol** (IDs 4–7): 4 cuentas; el redirect por rol llevó a
  `/client` en la cuenta 4 y a `/admin` en las cuentas 5–7.

### 25.3 Flujo E2E completo (datos nuevos)

Secuencia ejecutada en producción, con verificación en UI y en red:

1. **Vehículo**: patente `UAT001`, ID `8`, `Toyota UAT Corolla`, año `2024`,
   `100 km`.
2. **Orden n° 9** (ingreso `8`): creada en `Recibido`; asignada a `Mecánico 2`
   y avanzada a `Esperando diagnóstico` (2).
3. **Presupuesto n° 5**, versión 1, `borrador`, total `$35.000`:
   - Repuesto: `Filtro de aceite Toyota`, 1 × `$15.000`.
   - Mano de obra: 1 × `$20.000`.
   - `POST /api/presupuestos` → `201`.
4. El administrador envió el presupuesto: orden → `Esperando aprobación de
   presupuesto` (3). Notificaciones cliente IDs `58`–`62`, incluidas
   `presupuesto.enviado` y `orden.estado_cambiado`.
5. El cliente aprobó marcando la casilla de confirmación:
   `POST /api/presupuestos/5/versiones/1/decision`; mensaje *«Aprobación
   registrada. Estado del servicio: En reparación»*; orden → `En reparación`
   (5). Antes de aprobar, `/api/inventario/stock/1` mostraba `stock=2`,
   `comprometido=1` (orden 6), `disponible=1`, `bajo_umbral=true`: la reserva
   ocurre al aprobar, no al enviar. Los `404`/`409` previos de
   `/api/inventario/ordenes/9/disponibilidad` y el `403` con token de cliente
   son respuestas esperadas por estado y permisos.
6. **Evidencia multimedia**: `uat-evidencia.png` (70 B), contexto
   `Reparación`, `Visible para el cliente` activo. UI mostró *«Evidencia subida
   correctamente»* y el archivo `Confirmada`. Respuesta HTTP: ID
   `f7b8f11e-db5c-4f57-8e4f-15513d865c63`, `visible_cliente=true`,
   `estado=confirmada`, `content_type=image/png`. El portal cliente
   (`/client/ordenes/9/evidencias`) mostró la misma evidencia sin errores.
7. **Consumo de stock**: `1 × Filtro de aceite Toyota` registrado por el
   mecánico. UI: *«Consumo registrado para 1 repuesto. No quedan repuestos
   pendientes de consumir del presupuesto aprobado»*. `POST
   /api/inventario/ordenes/9/consumos`. Stock final `stock=1`,
   `comprometido=1` (solo orden 6), `disponible=0`, `bajo_umbral=true`.
   Movimientos: `8` = `compromiso` de la orden 9 y `9` = `consumo` de la
   orden 9, con la misma clave de operación lógica.
8. **Bitácora**: entrada tipo `Acción`, descripción *«UAT: se cambia filtro de
   aceite y se verifican frenos. Evidencia fotográfica adjunta»*; visible con
   fecha y `Usuario 2`. `POST /api/ordenes/9/bitacora`.
9. **Avance a `Listo` (6)**: `PATCH /api/ordenes/9/estado`, previa confirmación
   en modal; observación *«UAT: reparación finalizada y evidencia adjunta»*.
   Notificaciones cliente IDs `67` (*Vehículo listo para retirar*) y `68`
   (`orden.estado_cambiado`).
10. **Entrega (7)**: el administrador confirmó *«Registrar entrega»*;
    `POST /api/ordenes/9/entrega`. La orden quedó en `Entregado`; el historial
    mostró `Recibido → Esperando diagnóstico → Esperando aprobación de
    presupuesto → En reparación → Listo → Entregado`. Notificación de admin ID
    `63` (`presupuesto.decidido`). El rol mecánico no recibió notificaciones de
    esta orden, comportamiento observado también en el diseño actual.

### 25.4 Incidencia detectada y corregida: subida de evidencias

- **Síntoma**: `POST /api/evidencias` devolvía `422` con `Field required` para
  `archivo`, `orden_id` y `contexto`. La petición salía con
  `Content-Type: application/json` y cuerpo `{"archivo":{}, ...}`.
- **Causa**: `apiClient` fijaba `application/json` globalmente; axios 1.20
  serializaba el `FormData` como `{}`. Al retirar el header, el adaptador
  `fetch` de axios añadía `x-www-form-urlencoded` o fallaba con
  `ERR_DNS_NO_MATCHING_SUPPORTED_ALPN` / `ERR_ALPN_NEGOTIATION_FAILED` al
  enviar `FormData` en este entorno.
- **Corrección**: `apiClient` ya no fija `Content-Type` para `FormData`, y
  `EvidenciaService.crear` usa `fetch` nativo, que genera el boundary
  `multipart/form-data` correcto y conserva el token Bearer. Se conserva el
  mensaje *«Sin conexión: no se pudo subir la evidencia…»* y se reporta
  progreso al completar.
- **Regresión**: pruebas focales `21/21`; suite frontend completa
  `1309/1309` (148 archivos); `npm run lint` y `npm run build` limpios
  (bundle `index-B0Uso6qX.js`). CI verde en `main` #158/#44.
- **Verificación en producción**: la subida por UI pasó de `422` a `201`, con
  evidencia visible para el cliente y sin errores de consola.

### 25.5 Verificación final

- Salud en producción con `backend/.venv` y
  `python backend/scripts/verificar_salud.py --base https://tallerconnect.inf.uct.cl`:
  **6/6 OK** (gateway, bases de MS1–MS4, procesos y almacenamiento de MS4).
- Recorridos posteriores al deploy: sin errores de consola; el bundle activo
  es `index-B0Uso6qX.js`.
- Nota operativa: al cambiar el bundle, el navegador puede conservar en caché
  un `index.html` antiguo que referencia un JS ya no publicado; se resolvió
  recargando con un parámetro de consulta único. No afecta a los usuarios que
  cargan el documento fresco.
