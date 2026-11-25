# 08 — Pendientes y deuda técnica

Este documento es honesto sobre lo que **no** está terminado. Sirve para que el
equipo sepa qué falta, por qué se decidió así y qué riesgo implica.

Prioridad sugerida:

- **Alta:** afecta una función que el usuario final espera.
- **Media:** mejora operación o seguridad, no bloquea la demo.
- **Baja:** deuda de mantenimiento.

---

## 1. Funcionalidad incompleta

### 1.1 Correo electrónico desactivado — Prioridad alta

- **Qué falta:** no hay cuenta SMTP, así que
  `MS1_NOTIFICATION_WORKER_ENABLED=false`.
- **Efecto:** las notificaciones existen en la bandeja interna, pero **no se
  envían por correo**. Las entregas quedan `pendiente`.
- **Para cerrarlo:** contratar/configurar un SMTP y definir
  `MS1_SMTP_HOST`, `MS1_SMTP_PORT`, `MS1_SMTP_USUARIO`, `MS1_SMTP_CLAVE`,
  `MS1_SMTP_REMITENTE`, `MS1_SMTP_MODO`, y poner
  `MS1_NOTIFICATION_WORKER_ENABLED=true`.

### 1.2 Push FCM sin proyecto — Prioridad alta (para la app móvil)

- **Qué falta:** no hay proyecto Firebase/FCM ni credenciales de servidor.
- **Efecto:** la app puede registrar el token (`POST
  /api/notificaciones/dispositivos`) y la bandeja funciona, pero las entregas
  push quedan `sin_dispositivo` o `pendiente`.
- **Para cerrarlo:** crear el proyecto FCM, cargar las credenciales en MS1 y
  completar el envío en el worker de notificaciones.

### 1.3 Videos grandes — Prioridad media

- **Situación:** el servicio MS4 acepta videos de hasta 100 MiB, pero la Gateway
  corta el cuerpo en **12 MiB** (`GATEWAY_MAX_BODY_ARCHIVOS_BYTES=12582912`).
- **Efecto:** desde la web o la app, un video de más de 12 MiB falla con `413`.
- **Opciones:**
  1. Subir el límite de la Gateway (evaluar memoria y timeout).
  2. Subida por partes (multipart resumible).
  3. Comprimir/recortar en el cliente.
- **Recomendación:** definir con el equipo móvil el tamaño máximo real esperado
  antes de cambiar el límite.

---

## 2. Infraestructura y operación

### 2.1 DNS de evidencias — Prioridad media

- **Situación:** `evidencias-tallerconnect.inf.uct.cl` no existe en el DNS de la
  UCT y no se pudo crear.
- **Solución aplicada:** MinIO usa `ms4-tallerconnect.inf.uct.cl` y MS4 pasó a
  `ms4-interno-tallerconnect.inf.uct.cl`.
- **Riesgo:** los nombres no son intuitivos. Está documentado en
  [02 — Despliegue](02-despliegue-kubero.md#5-dominios).
- **Para cerrarlo:** solicitar el DNS a la UCT y migrar MinIO cuando exista.

### 2.2 Estrategia del workflow — Resuelta el 23-11-2026

- **Decisión:** `.github/workflows/docker-build.yml` queda en `main` con
  `branches: [main]`. El flujo es `Vicente → Develop → main`.
- **Estado:** la rama `kubero-deploy` se conserva fuera del flujo y su copia del
  workflow también quedó con `branches: [main]`; un push a esa rama ya no
  publica imágenes.
- **Deploy automático:** el mismo workflow fija el tag `sha-<commit>` en las 6
  apps Docker y redeploya. Requiere el secreto `KUBERO_TOKEN`.
- **Verificado el 24-11-2026:** run `45306353919` desde `main`, conclusión
  `success`, incluido el job `Actualizar Kubero al sha publicado`. Ver
  [07 — Pruebas realizadas](07-pruebas-realizadas.md#2-build-e-imágenes).

### 2.3 Sin respaldos automáticos — Prioridad alta

- **Situación:** los respaldos de PostgreSQL y MinIO son **manuales**
  (ver [06 — Runbook](06-runbook-operacion.md#6-respaldos)).
- **Riesgo:** un error humano o un borrado de addon sin respaldo reciente
  implica pérdida de datos.
- **Para cerrarlo:** programar un CronJob de `pg_dump` + `mc mirror` y definir
  retención. Probar una restauración completa al menos una vez.

### 2.4 Sin alta disponibilidad — Prioridad media

- **Situación:** una réplica por app. Si un pod cae, Kubero lo reinicia, pero hay
  una interrupción breve.
- **Riesgo:** una caída durante una demo o evaluación se nota.
- **Para cerrarlo:** subir réplicas de `gateway` y microservicios, y revisar que
  el arranque no dependa de estado local. Las migraciones ya están separadas del
  arranque, así que es viable.

### 2.5 Sin monitoreo ni alertas — Prioridad media

- **Situación:** la salud se consulta a mano. No hay panel de métricas ni
  alertas.
- **Para cerrarlo:** exponer `/api/health/servicios` a un monitor externo
  (Uptime Kuma, Prometheus, etc.) y alertar si un servicio deja de responder.

### 2.6 Consola de MinIO expuesta — Prioridad media

- **Situación:** la consola de MinIO responde en
  `https://ms4-tallerconnect.inf.uct.cl:36553`.
- **Riesgo:** superficie de ataque adicional. Está protegida por credenciales
  root, pero no debería ser pública en producción.
- **Para cerrarlo:** restringir el acceso por red/firewall o deshabilitar la
  consola si no se usa.

### 2.7 Etiqueta `latest` en producción — Resuelta el 24-11-2026

- **Situación:** las seis apps (gateway, ms1–ms4 y web) quedaron fijadas en
  `:sha-40106f5` por el run `45306353919`. `minio` conserva `latest` a propósito.
- **Riesgo:** si se vuelve a `latest`, un redeploy puede traer código distinto al
  probado.
- **Cierre:** el job de deploy mantiene las apps en `sha-<commit>` en cada push a
  `main`. No se confirmó el tag uno por uno en el panel, pero el job terminó en
  `success` y la salud pública respondió correctamente.

### 2.8 Secreto `KUBERO_TOKEN` — Creado, con expiración conocida

- **Situación:** el token con permisos `app:read` y `app:write` ya está guardado
  como secreto de GitHub Actions; el deploy automático funcionó con él.
- **Riesgo:** el usuario lo creó con expiración de ~2 meses. Al vencer, Kubero
  seguirá sirviendo la versión desplegada, pero fallarán los deploys futuros.
- **Para cerrarlo:** rotar el token antes de que expire, repitiendo
  **Perfil → API Tokens** de Kubero y **Settings → Secrets and variables →
  Actions** (runbook §4.2).

---

## 3. Código y repositorio

### 3.1 `auth-service/` sin versionar — Prioridad baja

- **Situación:** la carpeta `auth-service/` está en el disco pero **no** está
  versionada en Git.
- **Riesgo:** se pierde si se limpia el directorio; nadie sabe si es código vivo
  o un experimento.
- **Para cerrarlo:** decidir si se elimina o se incorpora al repo con un README
  que explique su relación con `backend/services/ms1_auth`.

### 3.2 `presupuestos-service/` legacy — Prioridad baja

- **Situación:** existe una carpeta `presupuestos-service/` que **no se
  despliega**. El servicio vigente es
  `backend/services/ms3_presupuestos`.
- **Riesgo:** confusión sobre cuál es el código real.
- **Para cerrarlo:** mover a una rama de archivo o eliminar, dejando una nota.

### 3.3 Tests no ejecutados en CI — Prioridad media

- **Situación:** el workflow solo construye y publica imágenes. No corre
  `backend/tests/` ni el build del frontend como verificación.
- **Riesgo:** una imagen puede publicarse con tests rojos.
- **Para cerrarlo:** agregar un job de tests antes del build, o un workflow
  separado en `pull_request`.

### 3.4 `README.md` raíz desactualizado — Prioridad baja

- **Situación:** el README describe el proyecto, pero el detalle operativo vive
  ahora en `docs/`. Se agregó un enlace, pero conviene revisar que no queden
  instrucciones de Vercel/Neon como si fueran el ambiente vigente.

### 3.5 Tabla de responsables incompleta — Prioridad baja

- **Situación:** [docs/README.md](README.md) tiene una tabla de responsables con
  campos `(completar)`.
- **Para cerrarlo:** llenarla antes de entregar el proyecto.

### 3.6 Hallazgo H-01 — Corregido (no es deuda pendiente)

- **Situación:** hasta esta revisión, las consultas de disponibilidad por orden,
  la reserva, los consumos y la liberación de stock de MS3 no comprobaban que el
  Mecánico tuviera asignada la orden.
- **Corrección aplicada:** las cinco operaciones usan
  `_exigir_orden_asignada_al_mecanico` en
  `backend/services/ms3_presupuestos/routers/inventario.py`, con el mismo
  verificador de MS2 que ya usaba `POST /inventario/movimientos`. Administrador
  queda exento; si MS2 no responde, la operación falla cerrada con `503` antes
  de leer o mover stock.
- **Cobertura:** `backend/tests/test_acceso_indebido_roles.py` y
  `backend/services/ms3_presupuestos/tests/test_disponibilidad_stock.py`.
- **Estado:** cerrado en `Vicente`; no queda trabajo pendiente. El detalle y la
  evidencia están en [07 — Pruebas realizadas](07-pruebas-realizadas.md#19).

### 3.7 Correcciones derivadas de la revisión de formularios — Cerradas

- **Situación:** la auditoría de `frontend/` encontró un reintento que generaba
  una nueva `clave_operacion` (posible doble movimiento de stock), un `404` de
  orden no asignada mostrado como «sin presupuesto», un refresco fallido tras un
  consumo confirmado que dejaba datos stale, un dashboard que podía decir
  «Sistema En línea» con KPIs en «—», errores de borrado silenciados, fallos de
  consulta de presupuesto confundidos con ausencia, notificaciones sin aviso de
  error y catálogos vacíos sin explicación.
- **Corrección aplicada:** se reutiliza la clave mientras el resultado sea
  incierto; el `404` se discrimina por `detail`; el refresco fallido bloquea un
  nuevo envío y ofrece recarga; las cargas fallidas se marcan como datos
  parciales; los `catch` de borrado/notificaciones muestran el motivo y el
  catálogo ofrece reintento. Además, el coordinador de reservas de MS3 usa el
  saldo cronológico canónico de `comprometido_por_ordenes` (un consumo libre
  previo no deja saldo negativo falso).
- **Cobertura:** pruebas nuevas en `AdminInventoryMovementsPage`,
  `ConsumoRepuestosPanel`, `AdminDashboardPage`, `AdminDistributorsPage`,
  `AdminInventoryPage`, `EvidenceUploadForm` (dos archivos), `NotificationsPage`,
  `MechanicBudgetPage` y `test_disponibilidad_repuestos.py`.
- **Estado:** cerrado en `Vicente`. El detalle y los comandos están en
  [07 — Pruebas realizadas](07-pruebas-realizadas.md#20).

---

## 4. Decisiones que se mantienen (no son deuda)

Estas no son tareas pendientes: son decisiones conscientes.

| Decisión | Motivo |
| --- | --- |
| **Vercel y Neon intactos** | El usuario pidió explícitamente no borrarlos ni modificarlos. Siguen existiendo como respaldo histórico, pero **no** son el ambiente vigente. |
| **Una sola imagen backend** | Menos mantenimiento y versiones consistentes entre las 5 apps. |
| **Una base por microservicio** | Aislamiento de datos, igual que el diseño original. |
| **Cuatro addons PostgreSQL separados** | Cada servicio es dueño de su esquema. |
| **MS1 no envía correo** | No hay SMTP disponible; la bandeja interna cubre la demo. |
| **Usuario MinIO limitado** | MS4 no necesita root; reduce el impacto de una filtración. |
| **Secretos fuera del repositorio** | El repositorio de GitHub es público. |

---

## 5. Riesgos residuales

| Riesgo | Impacto | Mitigación actual |
| --- | --- | --- |
| Pérdida de datos por borrar un addon | Alto | Procedimiento documentado; falta respaldo automático |
| Filtración de un secreto | Alto | Secretos solo en el panel; rotación documentada |
| Caída durante la demo | Medio | Health checks y reinicio manual |
| Video grande rechazado | Medio | Límite documentado; falta definir política |
| Confusión entre código legacy y vigente | Bajo | Documentado aquí |

---

## 6. Próximos pasos sugeridos (orden)

1. Configurar SMTP y habilitar el worker de correo.
2. Configurar FCM y completar el push (coordinar con app móvil).
3. Programar respaldos automáticos y ensayar una restauración.
4. Fijar `sha-<commit>` en las seis apps antes del primer merge a `main`.
5. Verificar el primer run del workflow publicando desde `main` y ajustar la
   copia del workflow en `kubero-deploy` sin borrar la rama.
6. Agregar tests al CI.
7. Resolver `auth-service/` y `presupuestos-service/`.
8. Completar la tabla de responsables.
9. Evaluar réplicas y monitoreo antes de una entrega formal.
