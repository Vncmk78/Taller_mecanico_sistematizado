# 06 — Runbook de operación

Procedimientos para **operar** el ambiente desplegado en Kubero UCT. Está pensado
para alguien con acceso al panel y, opcionalmente, a `kubectl`.

- Panel: <https://kubero.inf.uct.cl>
- Pipeline: `tallerconnect` → fase `Production`
- Namespace de Kubernetes: lo deriva Kubero del pipeline y la fase
  (habitualmente `tallerconnect-production`; confirmar con `kubectl get ns`).

> Antes de cualquier cambio, anota qué versión está desplegada (tag de imagen) y
> verifica la salud con la sección 1. Así puedes volver atrás.

---

## 1. Verificación rápida de salud

```bash
curl -s https://api-tallerconnect.inf.uct.cl/api/health
curl -s https://api-tallerconnect.inf.uct.cl/api/health/servicios
curl -s -o /dev/null -w "web=%{http_code}\n" https://tallerconnect.inf.uct.cl/
curl -s -o /dev/null -w "healthz=%{http_code}\n" https://tallerconnect.inf.uct.cl/healthz
curl -s -o /dev/null -w "minio=%{http_code}\n" https://ms4-tallerconnect.inf.uct.cl/minio/health/live
```

Esperado:

```json
{
  "status": "ok",
  "gateway": "ok",
  "servicios": {
    "ms1_auth": { "estado": "ok", "latencia_ms": 19 },
    "ms2_taller": { "estado": "ok", "latencia_ms": 37 },
    "ms3_presupuestos": { "estado": "ok", "latencia_ms": 42 },
    "ms4_evidencias": { "estado": "ok", "latencia_ms": 42 }
  }
}
```

Si un servicio aparece caído, revisar sus logs (sección 3) antes de reiniciar
nada.

---

## 2. Reiniciar una aplicación

### Desde el panel (recomendado)

1. Entrar al pipeline `tallerconnect` → fase `Production`.
2. Abrir la app (`gateway`, `ms1`…`ms4`, `web`, `minio`).
3. Usar **Restart** / **Redeploy**.
4. Esperar a que el pod quede `Running` y el health check en verde.
5. Verificar la salud (sección 1).

> Reiniciar una app **no** borra datos: las bases y el volumen de MinIO son
> persistentes. Reiniciar `minio` deja MS4 sin almacenamiento unos segundos.

### Desde `kubectl` (si tienes acceso)

```bash
kubectl -n tallerconnect-production get pods
kubectl -n tallerconnect-production rollout restart deployment/ms1
kubectl -n tallerconnect-production rollout status deployment/ms1
```

Ajustar el nombre del deployment si Kubero lo generó distinto
(`kubectl get deploy`).

### Orden recomendado si hay que reiniciar todo

1. `minio`
2. `ms1`, `ms2`, `ms3`, `ms4`
3. `gateway`
4. `web`

Así los servicios encuentran sus dependencias disponibles al arrancar.

---

## 3. Ver logs

### Desde el panel

Cada app tiene una vista de **Logs** en vivo. Es lo primero que hay que mirar.

### Desde `kubectl`

```bash
kubectl -n tallerconnect-production get pods
kubectl -n tallerconnect-production logs deployment/gateway --tail=200
kubectl -n tallerconnect-production logs deployment/ms2 -f
kubectl -n tallerconnect-production logs deployment/ms2 --previous
```

`--previous` muestra los logs del contenedor que murió (útil para crashes).

### Qué buscar

| Síntoma en logs | Causa probable |
| --- | --- |
| `relation ... does not exist` | Faltan migraciones |
| `could not connect to server` | Addon PostgreSQL caído o DSN malo |
| `InvalidAccessKeyId` / `SignatureDoesNotMatch` | Credenciales S3 de MS4 incorrectas |
| `No se pudo conectar a MS1/MS2/MS3` | URL interna mal escrita o servicio caído |
| `401` repetidos en MS1 | JWT distinto entre servicios |
| `No hay trabajadores` / worker inactivo | `MS*_EVENT_WORKER_ENABLED` en `false` |

---

## 4. Actualizar la versión desplegada

### 4.1 Publicar la imagen

El workflow solo está en la rama `kubero-deploy`:

```bash
git checkout kubero-deploy
git merge main                 # traer lo que se quiera desplegar
git push origin kubero-deploy
```

Esperar **Actions → Docker Build** en GitHub. Al terminar, GHCR tiene:

- `ghcr.io/vncmk78/tallerconnect-backend:sha-<commit>`
- `ghcr.io/vncmk78/tallerconnect-frontend:sha-<commit>`
- y las etiquetas `latest` actualizadas.

### 4.2 Desplegar en Kubero

1. En cada app backend (`gateway`, `ms1`–`ms4`), cambiar el tag de la imagen de
   `latest` a `sha-<commit>`.
2. En `web`, cambiar el tag de `tallerconnect-frontend`.
3. Redeploy de las apps afectadas.
4. Verificar salud y, si hay migraciones nuevas, ejecutarlas (sección 5).

> **Recomendación:** fijar `sha-<commit>` en producción. `latest` cambia sin
> aviso y un redeploy puede traer código distinto al probado.

### 4.3 Volver atrás (rollback)

1. Cambiar el tag de la imagen al `sha-<commit>` anterior.
2. Redeploy.
3. Si la versión nueva aplicó migraciones incompatibles, restaurar el respaldo
   (sección 6) **antes** de volver a arrancar el código viejo.

---

## 5. Aplicar migraciones

Las migraciones **no** corren al iniciar los pods. Se ejecutan una vez con una
app temporal.

1. Crear una app temporal `migraciones` en el pipeline, con la imagen del
   backend que se va a desplegar.
2. Variables:
   - `SGTM_SERVICIO=migraciones`
   - `MS1_DATABASE_URL`, `MS2_DATABASE_URL`, `MS3_DATABASE_URL`,
     `MS4_DATABASE_URL`
3. Esperar a que el pod termine.
4. Revisar los logs: debe ejecutar `alembic upgrade heads` en MS1 → MS4 y
   verificar que las cuatro quedan en el head del código.
5. **Eliminar la app temporal.**

Heads vigentes al 15-11-2026:

| Servicio | Revisión |
| --- | --- |
| MS1 | `0008_contexto_avisos_ms1` |
| MS2 | `0014_nueva_atencion_ms2` |
| MS3 | `0011_avisos_ms3` |
| MS4 | `0001_ms4` |

Si el pod falla:

- `relation ... already exists` → la base ya tenía esa migración aplicada sin
  registro; revisar `alembic_version` antes de hacer `stamp`.
- `connection refused` → el addon aún no está listo; reintentar.

> Nunca ejecutes `alembic stamp head` a ciegas: puede marcar como aplicadas
> migraciones que no corrieron y romper el esquema.

---

## 6. Respaldos

### 6.1 PostgreSQL

Las bases **no** están expuestas a Internet, así que el respaldo se ejecuta
**dentro** del clúster. La imagen del backend **no** trae `pg_dump`; usa el
contenedor del addon PostgreSQL o una imagen `postgres:16-alpine`.

**Opción A — `kubectl` (recomendada)**

El pod del addon sí tiene `pg_dump`. Redirigir la salida a un archivo local:

```bash
NS=tallerconnect-production

kubectl -n $NS get pods | grep postgres        # ubicar el pod de cada addon

kubectl -n $NS exec <pod-postgres-ms1> -- \
  pg_dump "postgresql://postgres:<PASSWORD>@localhost:5432/taller_ms1" \
  -Fc > taller_ms1.dump
```

Repetir para `ms2`, `ms3` y `ms4` cambiando el pod y la base.

**Opción B — solo panel de Kubero**

1. Crear una app temporal con imagen `postgres:16-alpine` y comando
   `sleep infinity`.
2. Abrir su terminal desde Kubero.
3. Ejecutar el respaldo contra el host interno:

```bash
pg_dump "postgresql://postgres:<PASSWORD>@ms1-postgres:5432/taller_ms1" \
  -Fc -f /tmp/taller_ms1.dump
```

4. Como la terminal del panel **no descarga archivos**, subir el respaldo a
   MinIO: descargar `mc` dentro del contenedor y ejecutar

```bash
mc alias set tctaller https://ms4-tallerconnect.inf.uct.cl <ROOT_USER> <ROOT_PASSWORD>
mc cp /tmp/taller_ms1.dump tctaller/evidencias/respaldos/taller_ms1.dump
```

5. Descargar el archivo desde la consola de MinIO.
6. Eliminar la app temporal y el objeto de MinIO si no debe quedar allí.

Restaurar (con el pod de PostgreSQL o una app temporal):

```bash
pg_restore --clean --if-exists \
  -d "postgresql://postgres:<PASSWORD>@ms1-postgres:5432/taller_ms1" \
  taller_ms1.dump
```

> `--clean` borra los objetos existentes. Úsalo solo con un respaldo verificado y
> con la app detenida.

### 6.2 MinIO (evidencias)

```bash
mc alias set tctaller https://ms4-tallerconnect.inf.uct.cl <ROOT_USER> <ROOT_PASSWORD>
mc mirror tctaller/evidencias ./respaldo-evidencias
```

Restaurar:

```bash
mc mirror ./respaldo-evidencias tctaller/evidencias
```

Los metadatos de las evidencias están en PostgreSQL (MS4); los archivos, en
MinIO. **Hay que respaldar ambos** para poder recuperar una evidencia completa.

### 6.3 Frecuencia sugerida

| Qué | Cuándo |
| --- | --- |
| PostgreSQL | Antes de cada migración y al menos semanal |
| MinIO | Al menos semanal |
| Secretos | Al cambiar cualquiera (guardar en gestor de contraseñas) |

---

## 7. Problemas frecuentes

### La web carga pero todas las llamadas fallan

1. Revisar `GATEWAY_UPSTREAM` en `web` (`http://gateway-kuberoapp`).
2. Revisar la salud de `gateway`.
3. Revisar que `gateway` tenga las cuatro `GATEWAY_MSn_URL`.
4. Abrir la consola del navegador: un error CORS indica un origen distinto al
   autorizado.

### `502` o `504` en `/api/*`

- `502`: la Gateway no alcanza al microservicio. Revisar el nombre del Service
  (`msN-kuberoapp`) y que el pod esté `Running`.
- `504`: el microservicio tardó más que el timeout de la Gateway. Revisar logs
  del servicio; si es una subida, recordar el límite de 60 s para archivos.

### `401` en todas las peticiones

- El JWT no coincide entre servicios: comparar `MSn_JWT_SECRET_KEY`.
- Token vencido (60 min): volver a hacer login.

### `403` al subir evidencia

- El usuario es cliente. Solo mecánico y administrador suben evidencias.

### `409` al cancelar una orden

- La orden ya tiene una aprobación inicial de presupuesto. Es una regla de
  negocio, no un error.

### `503` al subir evidencia

- MS4 no alcanza MinIO. Verificar `minio` y las variables `MS4_S3_*`.
- MS4 no alcanza MS2/MS3 para validar la orden.

### Las notificaciones no aparecen

1. Confirmar `MS2_EVENT_WORKER_ENABLED=true` y `MS3_EVENT_WORKER_ENABLED=true`.
2. Revisar logs de MS2/MS3: ¿hay errores de outbox?
3. Confirmar que los secretos de eventos coinciden entre MS1 y el emisor.
4. Recordar que el correo está desactivado; la bandeja interna sí debe funcionar.

### MinIO responde `307` en la raíz

Es normal: redirige a la consola en el puerto `36553`. El endpoint S3 es la raíz
sin seguir el redirect (`/evidencias/...`).

### El pod de una app queda en `CrashLoopBackOff`

```bash
kubectl -n tallerconnect-production logs deployment/ms1 --previous --tail=200
```

Causas típicas: variable obligatoria faltante, DSN inválido, secreto de menos de
32 caracteres, o migración pendiente.

---

## 8. Rotación de secretos

Si se filtra un secreto:

1. Generar uno nuevo (mínimo 32 caracteres).
2. Cambiarlo en **todas** las apps que lo comparten:
   - JWT → MS1, MS2, MS3, MS4.
   - Eventos de orden → MS1 y MS2.
   - Avisos MS3 → MS1 y MS3.
   - Lookup de destinatarios → MS1 y MS2.
   - Contraseña de una base → el addon y la app correspondiente.
   - Credenciales de MS4 en MinIO → MinIO y `ms4`.
3. Reiniciar las apps afectadas.
4. Verificar salud y un flujo de login + notificación.
5. Guardar el nuevo valor en el gestor de contraseñas.

> Cambiar el JWT invalida todos los tokens emitidos: los usuarios deberán volver
> a iniciar sesión.

---

## 9. Checklist antes de una demostración

- [ ] `GET /api/health/servicios` → los 4 en `ok`.
- [ ] Web responde `200` y el login funciona con las cuentas de prueba.
- [ ] Hay al menos una orden en estado `2` o `5` para mostrar el flujo.
- [ ] MinIO health `200` y una descarga de evidencia funciona.
- [ ] Las notificaciones del administrador y del cliente cargan.
- [ ] El equipo conoce las cuentas de [04 — Datos de prueba](04-datos-de-prueba.md).
