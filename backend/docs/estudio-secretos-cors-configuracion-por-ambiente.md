# 🛡️ Estudio: secretos, CORS y configuración segura por ambiente

**Ámbito:** configuración de los cuatro microservicios (`backend/services/ms1_auth`
a `ms4_evidencias`), `backend/gateway/`, `backend/shared/`, las plantillas de
entorno (`backend/.env.example`, `backend/.env.pruebas.example`,
`backend/despliegue/env.despliegue.example`), los scripts de aprovisionamiento
(`backend/scripts/inicializar_bd.py`, `backend/scripts/ambiente_pruebas.py`) y el
despliegue en Vercel (`vercel.json`).

**Estado:** registro histórico del estudio. Las secciones que describen la
plataforma retirada conservan el análisis original; el código vigente usa Kubero
y `GATEWAY_CORS_ORIGIN_REGEX` queda vacío salvo configuración explícita.

**Documentos que complementa (no se repiten aquí):**

- `backend/docs/estudio-cors-y-exposicion-informacion.md`: análisis detallado de
  CORS y exposición en respuestas, con hallazgos H1–H5. En este documento solo
  se resume el impacto de CORS **por ambiente**.
- `backend/docs/estudio-seguridad-transporte.md`: CORS desde la óptica del
  transporte, esquemas de seguridad en OpenAPI y dependencias compartidas.
- `backend/docs/variables-entorno-y-direcciones.md`: mapa de qué variable
  configura qué y direcciones de red por ambiente.
- `backend/docs/ambiente-pruebas.md`: procedimiento del ambiente aislado
  `sgtm_pruebas`.

---

## 1. Por qué este estudio

La configuración es la frontera entre el código y el despliegue. Tres decisiones
concentran casi todo el riesgo:

1. **Secretos**: qué credenciales existen, cómo se generan, cómo se entregan a
   cada proceso y qué pasa cuando se rotan.
2. **Ambiente**: qué archivo o panel se lee en cada despliegue y qué validación
   impide que un ambiente use recursos o secretos de otro.
3. **CORS**: qué orígenes puede invocar la Gateway en cada ambiente (el detalle
   de cabeceras y cuerpos ya está en el estudio de CORS).

Revisarlos juntos permite responder, por ejemplo, si un token emitido en local
podría servir en pruebas (no: cada ambiente tiene su propia clave) o si subir la
regex de Vercel al `.env` local cambiaría el comportamiento (sí: el valor por
defecto del código y el de la plantilla son distintos).

---

## 2. Inventario de secretos

| Secreto | Variable(s) | Quién lo usa | Protección actual | Observación |
|---|---|---|---|---|
| JWT compartido | `MS1_JWT_SECRET_KEY` … `MS4_JWT_SECRET_KEY`; `SGTM_JWT_SECRET` en la plantilla de despliegue | MS1 emite; MS1–MS4 validan | `SecretStr` con `min_length=32` en los cuatro servicios; `shared/auth.py` exige HS256 y clave ≥ 32 | Una sola clave para todos; el payload lleva `sub`, `roles` y `exp`, sin `kid` ni versión. |
| Eventos MS1↔MS2 | `MS1_EVENT_SHARED_SECRET`, `MS2_EVENT_SHARED_SECRET` | Worker de notificaciones | `SecretStr \| None`, `min_length=32`; si falta, la ruta interna queda deshabilitada | Se rota en pareja. |
| Avisos MS3→MS1 | `MS1_MS3_EVENT_SHARED_SECRET`, `MS3_EVENT_SHARED_SECRET` | Contrato interno de avisos | `SecretStr \| None`, `min_length=32` | `ambiente_pruebas.py` los genera si faltan, sin mostrarlos. |
| Consulta de destinatarios | `MS1_MS2_NOTIFICATION_SECRET`, `MS2_NOTIFICATION_LOOKUP_SECRET` | Validación de asignaciones contra MS1 | `SecretStr \| None`, `min_length=32` | Mismo patrón que el par anterior. |
| Correo saliente | `MS1_SMTP_CLAVE` | MS1 | `SecretStr \| None`; `SMTP_MODO` restringido a `starttls`, `ssl` o `sin_tls_local` | `sin_tls_local` es solo para desarrollo. |
| Firebase | `MS1_FCM_CREDENTIALS_FILE` | MS1 | Ruta a una cuenta de servicio fuera de Git | La plantilla la deja comentada. |
| Bases de datos | `MS1_DATABASE_URL` … `MS4_DATABASE_URL` (DSN con contraseña), `DESPLIEGUE_PG_ADMIN_CLAVE`, `SGTM_MS1_BD_CLAVE` … `SGTM_MS4_BD_CLAVE`, `PRUEBAS_PG_CLAVE` | Servicios y scripts | `inicializar_bd.py` rechaza claves débiles y menores de 12 caracteres, y no las muestra en errores; `--exigir-tls` exige `sslmode` seguro | El DSN se declara como `str`, no como `SecretStr`. |
| MinIO raíz | `MINIO_ROOT_PASSWORD`, `PRUEBAS_MINIO_ROOT_CLAVE` | Contenedores de MinIO | Solo administración de MinIO | En plantillas aparecen valores de desarrollo; en pruebas se generan. |
| Almacenamiento de MS4 | `MS4_S3_ACCESS_KEY`, `MS4_S3_SECRET_KEY` | MS4 y el contenedor `minio_init` | **`str` con valores por defecto de desarrollo** (`ms4-evidencias`, `cambia-esta-clave-ms4`) | Ver hallazgo **S1**. |
| Secreto de plataforma | `VERCEL_AUTOMATION_BYPASS_SECRET` | MS2 → MS3 en Vercel | Se adjunta solo cuando el destino es el mismo host del despliegue | `test_despliegue_vercel.py` verifica que no se reenvía a dominios ajenos. |
| Credenciales de prueba de la app | `APP_TEST_CLIENTE_*`, `APP_TEST_MECANICO_*`, `APP_TEST_ADMINISTRADOR_*` | Pruebas de humo | Plantilla vacía; se completan solo en el `.env` local | No son credenciales del panel de despliegue. |

---

## 3. Cómo se carga la configuración por ambiente

### 3.1 Selección del archivo

`backend/shared/entorno.py` es la única fuente de verdad para elegir el archivo
de entorno: `SGTM_ENV_FILE` (por defecto `.env`). Cada servicio usa su prefijo
(`MS1_`, `MS2_`, `MS3_`, `MS4_`, `GATEWAY_`) con `pydantic-settings` y
`extra="ignore"`, de modo que un mismo archivo pueda contener la configuración
de los cuatro sin cruces accidentales.

| Ambiente | Fuente | Mecanismo de selección | Aislamiento observable |
|---|---|---|---|
| Desarrollo local | `backend/.env` (copia de `.env.example`) | Valor por defecto de `archivo_entorno()` | Bases en 5433–5436, MinIO en 9000/9001, Gateway en 8000. |
| Pruebas aisladas | `backend/.env.pruebas`, generado desde `.env.pruebas.example` | `SGTM_ENV_FILE=.env.pruebas` **y** variables exportadas al proceso hijo por `ambiente_pruebas.py` | `verificar_configuracion()` rechaza puertos, bases o bucket del ambiente local; exige JWT propio y regex CORS vacía. |
| Despliegue de base de datos | `backend/despliegue/.env.despliegue`, generado por `inicializar_bd.py configurar` | Script que sustituye `__GENERAR__` por `secrets.token_urlsafe(32)` | `chmod 600`; si el archivo ya existe, no se reemplaza porque sus claves pertenecen al volumen creado. |
| Vercel / Kubero | Variables del panel | Entorno del proceso (sin archivo versionado) | Bindings internos `GATEWAY_MSn_URL`; `VERCEL_*` solo existe en Vercel. |

### 3.2 Controles ya implementados

- **Secretos fuera de Git.** `.gitignore` excluye `.env`, `.env.pruebas`,
  `.env.*.local` y `backend/.pruebas/`. Las plantillas versionadas usan
  placeholders (`reemplaza-por-…`, `__GENERAR__`, `<generar>`, `<JWT>`), nunca
  claves reales.
- **Longitud y tipo.** Las claves JWT y los secretos de eventos son `SecretStr`
  con `min_length=32`. `shared/auth.py` valida además longitud ≥ 32 y algoritmo
  HS256 antes de firmar o verificar.
- **Calidad de claves de base.** `inicializar_bd.py` mantiene una lista de
  claves débiles (incluye `cambia-esta-clave`, `postgres`, `__generar__`), exige
  al menos 12 caracteres y rechaza los roles `postgres`/`taller` en el perfil de
  despliegue.
- **Aislamiento activo de pruebas.** `ambiente_pruebas.py verificar` comprueba
  puertos, nombres de base, bucket, CORS (solo puerto 5183, regex vacía), que
  las cuatro claves JWT sean iguales y ≥ 32, que los secretos de cada contrato
  interno coincidan y que los secretos no sean los del `.env` existente. Las
  comparaciones se hacen sin imprimir los valores.
- **Secretos de plataforma con destino acotado.** `cabeceras_para_ms3()` solo
  adjunta `VERCEL_AUTOMATION_BYPASS_SECRET` cuando la URL apunta al mismo host
  del despliegue; las pruebas cubren URLs ajenas y variantes engañosas.
- **Errores sin credenciales.** Los mensajes de validación de MS1 enmascaran los
  secretos (CWE-209) y los errores del script de base no incluyen DSN ni claves.

---

## 4. CORS por ambiente (resumen)

El análisis de cabeceras, orden de middlewares y sobreexposición pertenece a
`estudio-cors-y-exposicion-informacion.md`. Aquí solo se registra **qué valor
se aplica en cada ambiente**, porque esa diferencia es la que puede romper un
despliegue:

| Ambiente | `GATEWAY_CORS_ORIGINS` | `GATEWAY_CORS_ORIGIN_REGEX` | `allow_credentials` |
|---|---|---|---|
| Código (si no hay entorno) | `http://localhost:5173`, `http://localhost:8000` | `https://[a-z0-9-]+\.vercel\.app` | `true` |
| `.env.example` (local) | `http://localhost:5173`, `http://localhost:8000` | **vacío** (desactiva la regex) | `true` |
| `.env.pruebas.example` | `http://localhost:5183`, `http://127.0.0.1:5183` | **vacío, obligatorio** | `true` (valor por defecto) |
| Vercel | Lo que defina el panel | Lo que defina el panel; si se omite, queda la regex del código | `true` |

Dos consecuencias concretas:

1. La plantilla local es **más restrictiva** que el código: si se copia
   `.env.example` a `.env`, los previews `*.vercel.app` no se autorizan. Si se
   borra esa línea, vuelve la regex del código.
2. El dominio real del panel de Vercel **no es verificable desde el
   repositorio**. El hallazgo **H2** del estudio de CORS (la regex admite
   subdominios de `vercel.app` de terceros) sigue vigente y su evaluación no se
   repite aquí. Igualmente sigue vigente **H1** (documentación pública
   `/docs`, `/redoc`, `/openapi.json` en la Gateway).

---

## 5. Rotación y ciclo de vida

| Secreto | Efecto de rotarlo | Procedimiento seguro |
|---|---|---|
| JWT | Invalida **todos** los tokens vigentes de inmediato en MS1–MS4: HS256 usa una única clave y el payload no tiene `kid` ni versión. | Generar la nueva clave fuera de Git, actualizar las cuatro variables de forma coordinada y forzar re-login. Para rotar sin corte habría que añadir `kid`/doble clave (cambio de contrato, no implementado). |
| Secretos de eventos | Rompe el worker hasta que se actualicen **ambos** extremos del contrato. | Rotar el par `MS1_EVENT_SHARED_SECRET`/`MS2_EVENT_SHARED_SECRET` y los pares MS1↔MS3 y MS1↔MS2 en el mismo despliegue. |
| S3 / MinIO | MS4 deja de firmar o de acceder al bucket. | Actualizar la clave del usuario en MinIO y `MS4_S3_SECRET_KEY` en el servicio (en Docker, `minio_init` lee la misma variable). |
| Bases de datos | Los servicios dejan de conectar. | Cambiar la contraseña del rol y el DSN en cada servicio; el script no reemplaza un `.env.despliegue` existente porque la clave ya quedó en el volumen. |
| SMTP / FCM | Dejan de enviarse notificaciones; el login no se afecta. | Actualizar la variable en MS1 y reiniciar el worker. |

Regla transversal: **ningún script imprime secretos**. Tanto
`ambiente_pruebas.py configurar` como `inicializar_bd.py configurar` lo evitan y
existen pruebas que lo comprueban.

---

## 6. Hallazgos

### S1 — Credenciales S3 de MS4 con valores por defecto de desarrollo

**Qué ocurre:** en `backend/services/ms4_evidencias/config.py`, `S3_ACCESS_KEY`
y `S3_SECRET_KEY` son `str` con valores por defecto (`ms4-evidencias` y
`cambia-esta-clave-ms4`), sin `SecretStr` ni `min_length`. El
`backend/docker-compose.yml` replica esos valores como *fallback*
(`${MS4_S3_ACCESS_KEY:-ms4-evidencias}` y
`${MS4_S3_SECRET_KEY:-cambia-esta-clave-ms4}`).

**Riesgo:** si en un despliegue falta la variable, MS4 arranca con una
credencial conocida en lugar de fallar en la validación de configuración. El
acceso queda limitado por la política del bucket, pero la credencial es
predecible y el fallo pasa desapercibido.

**Evaluación: observación, no corregida.** Convertirlas en `SecretStr` con
longitud mínima y quitar los *fallbacks* fuera de local implica tocar la
configuración de MS4, el Compose y las plantillas a la vez. Es un cambio de
código, no de estudio; se propone como pendiente.

### S2 — La rotación del JWT no es gradual

**Qué ocurre:** `shared/auth.py` firma y valida con una sola clave HS256; el
payload no incluye `kid`, `iss` ni versión del secreto.

**Riesgo:** no existe una ventana de solapamiento. Rotar en un servicio antes
que en los otros produce `401` intermitentes; rotar en los cuatro a la vez cierra
las sesiones activas.

**Evaluación: decisión de diseño, no corregida.** Añadir `kid` y mantener dos
claves temporalmente cambia el contrato compartido y la forma de validar en los
cuatro servicios. No entra en una revisión de configuración.

### S3 — La regex CORS depende de una variable que no está en la plantilla local

**Qué ocurre:** el valor por defecto del código autoriza `*.vercel.app`, pero
`backend/.env.example` y `.env.pruebas.example` lo dejan vacío. En Vercel, si el
panel no define la variable, rige el valor del código.

**Riesgo:** el comportamiento de CORS no es el mismo en todos los ambientes y no
se puede confirmar el dominio real desde el repositorio. El riesgo de la regex
en sí (H2) ya está evaluado en el estudio de CORS.

**Evaluación: observación.** No se modifica: hacerlo sin las coordenadas del
panel de Vercel puede bloquear previews legítimos.

### S4 — Las plantillas mezclan placeholders con valores de desarrollo

**Qué ocurre:** `.env.example` y `docker-compose.yml` incluyen valores como
`taller:taller`, `cambia-esta-clave-local` y `admin-local` para que el entorno
local arranque sin pasos extra.

**Riesgo:** copiar la plantilla a producción sin reemplazarlos deja credenciales
predecibles. Los scripts de despliegue sí generan claves propias, pero la
plantilla de la Gateway no tiene una validación equivalente.

**Evaluación: observación.** Sustituir todos los valores por placeholders
rompería el arranque local documentado; se recomienda un *checklist* de
despliegue que verifique que no queden valores de ejemplo.

### S5 — El DSN es `str`, no `SecretStr`

**Qué ocurre:** `DATABASE_URL` se declara como `str` en la configuración base y
en cada servicio, aunque contiene usuario y contraseña.

**Riesgo:** una futura línea de log que imprima la configuración completa
podría revelarlo. Actualmente no ocurre: los errores del script de base y del
proxy se construyen sin incluir el DSN, y hay pruebas que lo verifican.

**Evaluación: riesgo bajo, no corregido.** Cambiar el tipo del DSN afecta a los
cuatro servicios y a los scripts que lo lean; se registra para una revisión
futura, no para esta tarea.

---

## 7. Verificación ejecutada

Se ejecutaron desde `backend/` las pruebas que cubren los controles descritos:

```powershell
$env:PYTHONPATH=(Get-Location).Path
.\.venv\Scripts\python.exe -m pytest tests/test_ambiente_pruebas.py tests/test_inicializar_bd.py tests/test_gateway_estructura.py tests/test_direccion_ms3.py tests/test_direccion_notificaciones.py tests/test_exposicion_indebida_datos.py tests/test_credenciales_vacias_y_multirol.py tests/test_proveedores_notificaciones.py tests/test_ms4_logs.py -q
```

Resultado: **134 passed, 10 warnings** (advertencias de deprecación de
Starlette, ajenas a esta revisión). Las pruebas no fueron modificadas.

---

## 8. Conclusión

El manejo de secretos y el aislamiento por ambiente están **bien cubiertos en
el camino principal**: claves JWT obligatorias y validadas, generación
aleatoria en los scripts, exclusión de archivos de entorno en Git, verificación
estricta del ambiente de pruebas y secreto de plataforma con destino acotado.
CORS está documentado en detalle en otro estudio y aquí solo se registra su
variación por ambiente.

Los cinco hallazgos son observaciones o decisiones pendientes, no defectos que
puedan corregirse de forma mínima dentro de una revisión. El orden recomendado
para decidirlos es: **S2** (rotación del JWT, porque afecta a disponibilidad),
**S1** (credenciales S3 con valores por defecto), **S3/H2** (CORS, cuando se
confirme el dominio real de Vercel) y, por último, **S4** y **S5**.
