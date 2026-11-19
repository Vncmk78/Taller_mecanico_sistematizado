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
| B1 | Workflow `docker-build.yml` en `kubero-deploy` | ✅ Run `43548759119`, conclusión `success` |
| B2 | Imagen backend publicada | ✅ `ghcr.io/vncmk78/tallerconnect-backend:latest` y `:sha-c855bab` |
| B3 | Imagen frontend publicada | ✅ `ghcr.io/vncmk78/tallerconnect-frontend:latest` y `:sha-c855bab` |

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
