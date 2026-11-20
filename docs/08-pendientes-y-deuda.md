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

### 2.2 Workflow solo en `kubero-deploy` — Prioridad media

- **Situación:** `.github/workflows/docker-build.yml` existe solo en la rama
  `kubero-deploy`. `main` no compila imágenes.
- **Riesgo:** si se fusiona `kubero-deploy` en `main`, el workflow también se
  ejecutará en `main` (así está declarado en `on.push.branches`). Eso puede
  publicar imágenes desde una rama que no está probada para despliegue.
- **Para cerrarlo:** decidir la estrategia definitiva:
  - dejar el workflow solo en `kubero-deploy`, o
  - moverlo a `main` y quitar `main` de `on.push.branches`, o
  - usar solo `workflow_dispatch` + tags.

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

### 2.7 Etiqueta `latest` en producción — Prioridad media

- **Situación:** las apps pueden desplegar `latest`.
- **Riesgo:** un redeploy trae una imagen distinta a la probada.
- **Para cerrarlo:** fijar `sha-<commit>` en todas las apps (ya está
  recomendado en el runbook).

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
4. Fijar `sha-<commit>` en todas las apps.
5. Definir la estrategia del workflow (`main` vs `kubero-deploy`).
6. Agregar tests al CI.
7. Resolver `auth-service/` y `presupuestos-service/`.
8. Completar la tabla de responsables.
9. Evaluar réplicas y monitoreo antes de una entrega formal.
