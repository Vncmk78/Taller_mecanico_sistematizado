# CONEXIONES — Integración TallerConnect y preparación de Kubero

## 1. Estado y límites de esta guía

Panel de administración: https://kubero.inf.uct.cl. **No es la URL de la API**.
La URL pública de la Gateway y la de la web aún deben asignarse y verificarse.
No se declara que las bases de Kubero estén creadas, migradas o sembradas.

El plan de integración del 29-10-2026 se refiere a `main` (`b05663d`). La rama
`MartinH` tiene otro historial de migraciones y otras funcionalidades. La versión
objetivo elegida para el despliegue es `origin/main` (`b05663d`); no se integra
el trabajo adicional de MartinH para esta publicación.
**No aplicar las migraciones de MartinH sobre las bases del despliegue de main
sin revisar esta diferencia.** Un ID de revisión igual tampoco garantiza que
su contenido coincida entre ramas. Los scripts comparan con el checkout actual;
no validan que todas las columnas e índices coincidan con los modelos.

La revisión del panel del 30-10-2026 mostró un pipeline `mamaderasgames`, sin
aplicaciones en producción. Se inspeccionó el formulario de aplicación sin
crear ni guardar recursos. Permite imagen/tag, puerto, comando, variables,
complementos y health checks. El catálogo ofrece
PostgreSQL como complemento (se inspeccionaron sus campos sin guardarlo).
Faltan las bases y sus DSN, el almacenamiento S3, el registro de imágenes y
los dominios definitivos para TallerConnect.

## 2. Arquitectura y contenedor backend

Se conservan la Gateway FastAPI y los cuatro microservicios independientes,
cada uno con su propia base PostgreSQL. MS4 guarda los archivos en MinIO/S3.
La web y la app móvil consumen exclusivamente `/api/*` de la Gateway.

El `Dockerfile` en la raíz empaqueta solo el backend. Crear cinco aplicaciones
independientes con la misma imagen y diferente `SGTM_SERVICIO`; cada proceso
escucha en `0.0.0.0:8000` por defecto (`PORT` configurable).

| Aplicación propuesta | SGTM_SERVICIO | Módulo | Health check |
| --- | --- | --- | --- |
| sgtm-gateway | gateway | gateway.main:app | /api/health |
| sgtm-ms1 | ms1 | services.ms1_auth.main:app | /health |
| sgtm-ms2 | ms2 | services.ms2_taller.main:app | /health |
| sgtm-ms3 | ms3 | services.ms3_presupuestos.main:app | /health |
| sgtm-ms4 | ms4 | services.ms4_evidencias.main:app | /health |

Construcción local desde la raíz (requiere Docker activo):

```bash
docker build --platform linux/amd64 -t tallerconnect-backend:local .
```

Los comandos deben ejecutarse sobre el código de main con estas herramientas
de preparación incorporadas. Construir desde la raíz de MartinH produciría
otra versión. Para la verificación se extrajo main con `git archive` en
`backend/salidas-integracion/main-b05663d/` y se agregaron únicamente las
herramientas de preparación; no se cambió de rama ni se realizó un merge.

El tag local **no está disponible automáticamente en Kubero**. Publicar la
imagen en un registro accesible al clúster, o utilizar un build autorizado del
panel si está disponible. Usar el mismo tag inmutable para las cinco instancias.
No incluir `.env` en la imagen, y no ejecutar migraciones al iniciar cada pod.

Kubero admite despliegue desde imágenes o Git; las opciones efectivas dependen
de su configuración: https://www.kubero.dev/docs/usermanual/deployment/.
En el panel universitario inspeccionado, el formulario ofrecía imagen/tag.

## 3. Variables y recursos por servicio

Configurar las variables en cada aplicación, con los nombres de
`backend/.env.example`. Los `localhost` de la plantilla son solo para desarrollo:
en Kubernetes apuntarían al propio pod, no a otro microservicio.

| Aplicación | Configuración necesaria |
| --- | --- |
| Gateway | GATEWAY_MS1_URL…GATEWAY_MS4_URL con URLs internas reales; GATEWAY_CORS_ORIGINS con el origen HTTPS de la web; GATEWAY_CORS_ORIGIN_REGEX vacío si no se autorizan previews Vercel |
| MS1 | MS1_DATABASE_URL, MS1_JWT_SECRET_KEY; MS1_EVENT_SHARED_SECRET si se habilitan los eventos de MartinH |
| MS2 | MS2_DATABASE_URL, MS2_JWT_SECRET_KEY, MS2_MS3_URL, MS2_TIMEZONE=America/Santiago; MS2_MS1_URL y secreto de eventos si corresponde a la versión desplegada |
| MS3 | MS3_DATABASE_URL, MS3_JWT_SECRET_KEY, MS3_MS2_URL |
| MS4 | MS4_DATABASE_URL, MS4_JWT_SECRET_KEY, MS4_MS2_URL y MS4_S3_* |

Los cuatro `MSn_JWT_SECRET_KEY` deben contener la misma clave aleatoria de al
menos 32 caracteres para HS256. El secreto de eventos MS1↔MS2 es independiente
del JWT y debe coincidir en ambos servicios. No dar las claves JWT o DSN a la
Gateway. No copiar el `.env` completo a cada aplicación.

Bases separadas: `taller_ms1`, `taller_ms2`, `taller_ms3`, `taller_ms4`.
Usar usuarios con acceso únicamente a su base y el modo TLS indicado por la UCT:

```text
postgresql+psycopg://USUARIO:PASSWORD@HOST:5432/taller_ms1
```

Agregar `?sslmode=require` si el servidor ofrece TLS. Mantener bases y servicios
internos restringidos al clúster; el punto público de negocio es la Gateway.
MS4 necesita un bucket privado, credenciales limitadas a ese bucket y
`MS4_S3_PUBLIC_ENDPOINT` con la URL HTTPS que abrirán web y móvil. Una URL
firmada contra un nombre interno de Kubernetes no será utilizable desde fuera.

Frontend React: `frontend/Dockerfile` construye con Node y sirve con Nginx.
Desde `frontend/` de la misma versión de main:

```bash
docker build --platform linux/amd64 -t tallerconnect-frontend:local .
```

Crear otra aplicación, puerto `80`, health check `/healthz`, con
`GATEWAY_UPSTREAM` igual al origen interno real de la Gateway, sin ruta ni barra
final (por ejemplo `http://NOMBRE_INTERNO:8000`, reemplazando el nombre). El
build fija `VITE_API_URL=/api`; Nginx reenvía `/api/*` conservando el prefijo,
y devuelve `index.html` en rutas SPA. El frontend consume su mismo origen;
la app móvil utiliza la URL pública de la Gateway. No incluir credenciales ni
DSN en el build de React.

## 4. Migraciones de las cuatro bases

Instalar `backend/requirements.txt` y configurar **explícitamente** los cuatro
`MSn_DATABASE_URL` en `backend/.env` o en el entorno del proceso. No se usan
DSN por defecto para verificar o migrar. Las variables del proceso prevalecen.

Consulta de solo lectura, desde la raíz:

```bash
python backend/scripts/verificar_migraciones.py
```

Informa cada revisión actual y cada head del código. Devuelve `0` si todas
coinciden, `1` si faltan migraciones y `2` ante una revisión desconocida, DSN
ausente o fallo de conexión. No crea `alembic_version` si falta.

Una vez revisadas la versión del código, las bases destino y la autorización
de producción, ejecutar **una sola vez por despliegue**:

```bash
python backend/scripts/migrar.py
```

En PowerShell también está `backend/scripts/migrar.ps1`;
`migrar_neon.ps1` se conserva solo como entrada de compatibilidad.

El migrador consulta primero las cuatro bases y no inicia escrituras si alguna
es incompatible o no se puede consultar. Luego ejecuta `alembic upgrade heads`
en MS1, MS2, MS3 **y MS4**, muestra `alembic current` y compara nuevamente las
cuatro bases. Falla si alguna no queda en los heads del checkout. Las bases son
independientes: si falla MS3, MS1/MS2 pueden haber migrado; no hay una transacción
global ni rollback automático. No se crean nuevas migraciones ni se usa `stamp`.

## 5. Preparación de datos y capacidad

Después de migrar, en un entorno de prueba autorizado se puede ejecutar desde
`backend/`:

```bash
python scripts/seed_usuarios_prueba.py
```

El seed de **main** crea o actualiza **siete** cuentas: tres de un solo rol
y cuatro combinaciones multirrol, más los perfiles Cliente correspondientes
en MS2. El seed de MartinH es distinto y solo contiene tres cuentas. También
restablece sus contraseñas; revisar el script antes de ejecutarlo sobre una
base con datos. No se ejecuta automáticamente. Se ejecutó en las bases temporales locales
de verificación; no se ha ejecutado en Kubero.

Como Administrador, configurar valores aprobados por el taller mediante:

- `PUT /api/ordenes/configuracion/capacidad/ingresos-diarios`, body
  `{"max_ingresos_diarios": ENTERO_POSITIVO}`.
- `PUT /api/ordenes/configuracion/capacidad/mecanicos`, body
  `{"max_ordenes_activas": ENTERO_POSITIVO}`.

No inventar esos límites. Sin configuración, crear un ingreso o asignar un
mecánico puede responder `409`. Preparar una orden visible para cada cuenta de
prueba en staging para comprobar detalle/historial sin insertar datos durante
la prueba de consultas. No copiar ni borrar datos de Neon como paso automático.

## 6. Verificación para la aplicación móvil

Completar en el `.env` local las variables `GATEWAY_URL` y
`APP_TEST_{CLIENTE,MECANICO,ADMINISTRADOR}_{EMAIL,PASSWORD}` con cuentas de
prueba de un solo rol. No usar las credenciales del panel Kubero.

```bash
python backend/scripts/prueba_integracion_app.py
python backend/scripts/prueba_integracion_app.py --salida backend/salidas-integracion/cubero-01
```

El directorio de salida debe ser nuevo. La prueba no sigue redirecciones y
exige HTTPS fuera de localhost. Hace únicamente GET y el POST de login;
este último puede registrar auditoría o actualizar contadores de acceso.
Comprueba health, OpenAPI, `401` sin token con desafío Bearer, login y `/me`
por rol, permisos de listados de vehículos y órdenes, y detalle, historial,
vehículo y evidencias de la primera orden visible para cada rol.

Salida: `0` si pasa todo, `1` si falla alguna comprobación, `2` si hay grupos
omitidos porque no existen órdenes visibles (o falta configuración de CLI).
No presenta una base vacía como prueba completa. No prueba escrituras,
propiedad entre cuentas distintas, concurrencia ni subidas/descargas S3.

Con `--salida` guarda `openapi.json` del despliegue y `muestras.json` con
respuestas observadas, estado de la prueba y omisiones. Las muestras omiten
JWT, correo, nombre, patente y observaciones; los listados se limitan al primer
elemento. Son respuestas anonimizadas, no datos ficticios ni evidencia de
consultas omitidas. `backend/salidas-integracion/` está excluido de Git.
Revisar esos archivos antes de compartirlos con el equipo móvil.

### Verificación local de la preparación (30-10-2026)

Se construyeron para `linux/amd64` las imágenes backend y frontend con código
de main `b05663d` y las herramientas de preparación. La selección de pruebas
`test_scripts_despliegue`, `test_gateway_openapi`, `test_gateway_openapi_ejemplos`,
`test_auth_api`, `test_ordenes_api` y `test_vehiculos_api` pasó en esa copia:
332 pruebas. También había pasado en MartinH: 283 pruebas. Hubo avisos de
deprecación de Starlette/httpx/AnyIO y de `HTTP_422_UNPROCESSABLE_ENTITY`.

El migrador elevó cuatro bases PostgreSQL locales vacías a los heads de main:
MS1 `0004_intentos_login_ms1`, MS2 `0011_ms2`, MS3 `0008_ms3`, MS4 `0001_ms4`.
Se sembraron las cuentas y se creó una orden ficticia asignada en ese entorno.
La prueba HTTP por Gateway terminó con cero fallos y cero grupos omitidos para
los tres roles. Se verificaron además `/healthz`, `/`, una ruta SPA y el proxy
`/api/health` de Nginx con `200`, y `/api/ordenes` sin token con `401`.
Se reprodujo además una base MS2 parcial en `0007_ms2` sin la columna
`historial_estado.envio_presupuesto_id`: el verificador informó ATRASADA y el
migrador la llevó a `0011_ms2`, tras lo cual la consulta de esa columna funcionó.
MS1/MS3/MS4, ya en head, admitieron la reejecución sin cambios de versión.
Estas comprobaciones son **locales**, no verificaciones de Kubero.

La construcción del frontend informó siete vulnerabilidades de dependencias
(dos moderadas y cinco altas) y un bundle JS mayor que 500 kB. La auditoría `npm audit --omit=dev --json` identificó dos vulnerabilidades
altas de producción: `follow-redirects` y `zod`, con correcciones disponibles.
No se aplicó
`npm audit fix` ni se cambiaron dependencias del producto como parte de la
preparación. Revisar estos avisos antes de publicar.

## 7. Contrato y entrega a Víctor

En todos los casos usar `Authorization: Bearer <token>`.
`POST /api/auth/login` recibe `email` y `password`; la respuesta vigente incluye
`access_token`, `token_type` y `user`. `GET /api/auth/me` devuelve el usuario.

| Consulta | Cliente | Mecánico | Administrador |
| --- | --- | --- | --- |
| GET /api/ordenes | Sus órdenes | Asignadas | Todas |
| GET /api/ordenes/{id} y /historial | Propias | Asignadas | Todas |
| GET /api/vehiculos | Propios | 403 | Todos |
| GET /api/vehiculos/asignados | 403 | Asignados | 403 |
| GET /api/vehiculos/{id} | Propios | Con orden asignada | Todos |
| POST /api/ordenes | 403 | 403 | 201 con precondiciones válidas |
| PUT /api/ordenes/{id}/mecanico | 403 | 403 | 200 con precondiciones válidas |
| POST /api/vehiculos | 201 con datos válidos | 403 | 403 |

Tabla de permisos implementados en el código; no certifica su funcionamiento
en Kubero hasta ejecutar las pruebas. Las cuentas multirrol combinan alcances;
la prueba exige cuentas de un solo rol para que sus resultados sean inequívocos.
Las órdenes fuera de alcance se ocultan con `404`. Sin token, las rutas
protegidas responden `401` con `WWW-Authenticate: Bearer`. Los errores de
autenticación/autorización normalizados usan `{"detail":"No autenticado"}`
y `{"detail":"No tienes permiso para realizar esta operación"}`.
`PATCH /api/ordenes/{id}/estado` está limitado a la finalización 5→6 por el
mecánico asignado; otras transiciones utilizan sus endpoints específicos.

Las respuestas de órdenes conservan identificadores como `vehiculo_id`,
`estado_codigo` y `mecanico_actual_id`. Obtener el vehículo con
`GET /api/vehiculos/{vehiculo_id}`. Los ocho estados son: 1 Recibido,
2 Esperando diagnóstico, 3 Esperando aprobación de presupuesto,
4 Esperando repuestos, 5 En reparación, 6 Listo, 7 Entregado, 8 Cancelado.
No se agregaron objetos anidados ni nombres de usuarios. Confirmar con Víctor
si necesita otro contrato antes de implementar una ampliación.

La entrega final debe incluir la URL pública **verificada**, `/docs`,
`openapi.json`, muestras revisadas, permisos por rol y cambios correspondientes
a la versión realmente desplegada. No afirmar que los endpoints exclusivos de
main están incluidos en MartinH sin integrar y comprobar esa versión.

---

# Historial anterior: Vercel/Neon

Las secciones siguientes se conservan como registro de verificaciones anteriores.
Sus URLs, resultados y cifras no describen un despliegue actual en Kubero.

## 8. Última verificación de producción (2026-09-24)

Resultados probados contra `https://tallerconect.vercel.app`:

| Prueba | Resultado |
| --- | --- |
| `GET /api/health` | 200 `{"status":"ok","servicio":"gateway"}` |
| `GET /` (frontend) | 200 |
| `GET /ms1/docs` … `/ms4/docs` | 200 (los 4 Swagger cargan) |
| `GET /ms1/health` + `/ms2/health` + `/ms3/health` + `/ms4/health` | 200 |
| `GET /ms2/health/db` + `/ms3/health/db` | 200 (`database:"ok"`) |
| `POST /api/auth/login` (cliente, mecánico, admin) | 200 + JWT |
| `POST /api/auth/login` (contraseña incorrecta) | 401 |
| `GET /api/auth/me` (con token) | 200 usuario con roles |
| `GET /api/vehiculos` (token cliente) | 200 `[]` |
| `GET /api/vehiculos` (token admin) | 200 (el Administrador ya ve todos los vehículos; antes respondía 403) |

---

## 9. Verificación de pruebas funcionales de los primeros flujos web (2026-09-30)

Pruebas automatizadas (robots) ejecutadas tras sincronizar `Vicente` con el
`main` actual (FF a `6690a87`, que incluye el trabajo del gateway de Basti):

| Suite | Comando | Resultado |
| --- | --- | --- |
| Backend | `.\\.venv\\Scripts\\python.exe -m pytest -q` (desde `backend/`) | 427 passed, 61 skipped (saltan JWT/PostgreSQL) |
| Lint frontend | `npm run lint` | 0 warnings / 0 errors |
| Tests frontend | `npm test` | 209 passed / 43 archivos |
| Build frontend | `npm run build` (tsc -b && vite build) | OK |

Flujos cubiertos: auth (register/login/me), vehículos (listado por rol,
`/api/vehiculos/asignados`, detalle, alta, PATCH) y órdenes (listado, filtro,
paginación, detalle, historial, `PATCH .../estado` con 409/422/403/404/401,
asignación de mecánico). Ver plan detallado en
`.opencode/plans/r32x-pruebas-funcionales-primeros-flujos-web.md`.

Ajustes post-merge: los dos tests de `test_gateway_openapi_ejemplos.py` de Basti
asumían 11 operaciones de negocio; pasan a validar las **14 operaciones**
vigentes (set explícito) y se agregó el ejemplo 200 `lista_asignados` de
`GET /api/vehiculos/asignados` en `gateway/openapi_ejemplos.py`. Dependencia
nueva del venv: `openapi-spec-validator` (de `requirements-dev.txt`).

## 10. Reemplazo de datos simulados por respuestas reales de la Gateway (2026-09-30)

Las 14 operaciones de negocio existen y el frontend ya las consumía; lo que
quedaba eran datos de demostración en producción (seeds de stores, nombres de
dueño/mecánico y filtros por identidades de ejemplo). Ahora ninguna vista depende
de datos simulados.

| Suite | Comando | Resultado |
| --- | --- | --- |
| Backend | `.\.venv\Scripts\python.exe -m pytest -q` (desde `backend/`) | 427 passed, 61 skipped |
| Lint frontend | `npm run lint` | 0 warnings / 0 errors (150 archivos) |
| Tests frontend | `npm test` | 286 passed / 51 archivos |
| Build frontend | `npm run build` (tsc -b && vite build) | OK |

**Backend**: `VehiculoRespuesta` expone ahora `cliente_id` (schema de MS2,
contrato de la Gateway y ejemplos del OpenAPI), que es el dato que la interfaz
muestra como propietario real.

**Frontend**:
- Los 3 stores (`useVehicleStore`, `useOrderStore`, `useOrderHistoryStore`)
  arrancan vacíos: la caché solo contiene respuestas de la Gateway.
- `VehicleService` mapea `cliente_id` a `Vehicle.clientId`. En el portal Cliente
  manda el `id` de la sesión (`usuario_id` de MS1) para resolver pertenencia;
  en Administrador y Mecánico queda el `cliente_id` real de MS2.
- Se retiraron `CURRENT_CLIENT_ID`, `CURRENT_MECHANIC_ID`, `mockOwners`,
  `mockMechanics` y `mockAssignedVehicleIds` de producción, junto con el archivo
  `infrastructure/mocks/orders.mock.ts`. Los mocks que quedan son fixtures
  exclusivos de los tests.
- Los filtros offline por identidad se eliminaron: la Gateway ya devuelve solo
  lo que corresponde al rol, así que la caché se muestra tal cual. El alcance de
  un vehículo para el rol Mecánico lo aplica el backend (404 si no está
  asignado).
- `VehicleInfoPanel` recibe `ownerLabel` (p. ej. `Cliente #7`) en vez de un
  objeto con nombre, correo y teléfono simulados; las órdenes muestran
  `Mecánico <id>` o `Sin asignar`.

Pendiente de coordinar con backend: exponer nombres reales requiere que MS2
resuelva MS1 (o un endpoint de clientes/mecánicos), fuera del alcance de esta
misión. Ver `frontend/docs/contratos-openapi.md` y el plan en
`.opencode/plans/r32x-reemplazar-mocks-gateway.md`.

## Estados de carga, vacío y error en la interfaz

Los 3 portales (Administrador, Mecánico y Cliente) comparten los mismos estados en
los listados, detalles e historial de vehículos y órdenes, con el texto
acomodado a cada portal.

**`isOffline` ya no significa "cualquier error"**: `isOfflineError`
(`frontend/src/infrastructure/api/errors.ts`) solo marca `true` cuando el fallo
es de transporte —error no Axios, Axios sin `response`, o `502/503/504`—. Un
`500` u otro `5xx` con respuesta llega como error del servidor, porque el
problema no es la conexión del usuario. Un `404` en un detalle se traduce a
"no encontrado" en vez de a un error.

| Estado | Comportamiento |
| --- | --- |
| Cargando | `LoadingState` o skeleton según la vista |
| Vacío | `EmptyState` con el texto del portal y, si aplica, la acción para crear el primer registro |
| Sin conexión | `OfflineBanner` + los últimos datos de la caché, con `RetryButton` |
| Error del servidor con caché | Se conservan los datos y se avisa en un `Alert` con reintento |
| Error del servidor sin caché | `ErrorState` a pantalla completa con mensaje y botón de reintento |
| Detalle inexistente | `EmptyState` "no encontrado" con el link de regreso del portal |

Detalles del comportamiento:

- `fetchCollection` limpia `status`, `error` e `isOffline` al iniciar cada
  intento, para que un reintento no herede el error anterior.
- Ante un fallo nunca se borra la caché: primero se avisa, después se muestran
  los últimos datos conocidos.
- Un detalle distingue `notFound` (el `404` real) de `failed` (el fetch falló sin
  copia local), de modo que un error de red no se presenta como "no encontrado".
- El historial de la orden usa su propio aviso: "No fue posible mostrar el
  historial de estados de esta orden." en vez del vacío "Aún no hay registros".
- Componentes nuevos reutilizables: `EmptyState`, `ErrorState` y `RetryButton`;
  `OfflineBanner` quedó delegando el reintento en `RetryButton`.

La tabla completa por código de respuesta está en
`frontend/docs/contratos-openapi.md`, sección "Estados de carga, vacío y error".

## Mapeo y errores probados con payloads reales del backend (2026-09-30)

Los tests de mapeo y de errores ya no usan cuerpos inventados: se prueban contra
los literales que devuelve el backend, copiados a
`frontend/src/infrastructure/mocks/payloads.reales.ts` con la referencia al
archivo del backend del que salió cada uno.

Qué se verificó:

- **Éxitos**: vehículo `AB1234`/Toyota/Corolla/2018/45000 km, orden con
  `mecanico_actual_id: null` y fechas `-03:00`, historial de usuario y de sistema
  (con `estado_anterior`, `actor_usuario_id` y `observacion` en `null`), y el
  token de login con el usuario anidado.
- **Errores de la Gateway**: los 7 códigos de su catálogo (`RUTA_NO_ENCONTRADA`,
  `METODO_NO_PERMITIDO`, `ERROR_INTERNO`, `ERROR_MICROSERVICIO`,
  `MICROSERVICIO_INALCANZABLE`, `GATEWAY_SATURADA`, `TIEMPO_AGOTADO`), con su
  `detail`, `request_id` y código.
- **Errores de los microservicios**: 409 de patente y de correo, 401 de
  credenciales y de token, 403, y los 422 en sus tres formas (lista de FastAPI y
  dos strings).

Cambios que salieron de esta prueba:

- `502/503/504` se siguen marcando como fallo de servicio, pero ahora la
  interfaz muestra el mensaje que escribió el backend ("La Gateway está
  ocupada. Intente más tarde.") en vez de un texto genérico. Antes ya se
  respetaba el `detail`; ahora está fijado con pruebas para que no se pierda.
- Se expone el `request_id` de la Gateway como `Referencia: <id>` en los estados
  de error, en el banner de servicio caído y en el formulario de registro, para
  poder rastrear el fallo en los logs. `getApiErrorRequestId` lo lee del bloque
  `error` y, si no está, de la cabecera `X-Request-ID`.
- El `409` de patente duplicada muestra el literal del servidor ("La patente ya
  está registrada") en el campo Patente, en vez de un texto propio del frontend.
- `anio` y `kilometraje` son opcionales en el contrato y llegan en `null` para un
  vehículo sin esos datos: `vehicleDisplay.ts` muestra "Sin especificar" en vez
  de "Año: 0". Limitación asumida: un vehículo con 0 km reales queda
  indistinguible de uno sin dato.
- Con `roles` múltiple en la respuesta de MS1 gana el primero (`roles[0]`), que
  es el que define el portal de ingreso. Queda documentado y fijado con un test.
- Vitest corre con `TZ: America/Santiago`, así que las pruebas de fechas con
  offset `-03:00` no dependen de la zona horaria de la máquina.

Desajuste detectado, sin modificar: el formulario exige una patente con formato
`ABCD-12`, pero el backend solo pide `min_length=1` y su test afirma que el
contrato no define patrón. La UI es más restrictiva que el servidor. Es una
decisión de producto, así que queda anotada en
`frontend/docs/contratos-openapi.md` ("Desajuste detectado: formato de patente")
para resolverla con el equipo.

| Verificación | Resultado |
| --- | --- |
| `npx tsc --noEmit -p tsconfig.json` | Sin errores |
| `npm run lint` | 0 errores, 0 warnings |
| `npx vitest run` | 341 tests en 54 archivos, todos verdes (antes 286 en 51) |
| `npm run build` | Compila; queda el aviso preexistente de chunk > 500 kB |

## Discrepancias entre el frontend y el contrato de la API (2026-09-30)

Se auditó una por una las suposiciones del frontend contra la Gateway, los
contratos de `backend/gateway/contratos/` y los esquemas reales de MS1 y MS2.
El registro completo, con la evidencia de cada archivo del backend, quedó en
`frontend/docs/contratos-openapi.md`, sección "Registro de discrepancias entre el
frontend y el contrato de la API".

| # | Discrepancia | Impacto | Estado |
| --- | --- | --- | --- |
| D1 | El formulario exigía patente `ABCD-12`; el contrato solo pide `min_length=1`, sin patrón | La UI rechazaba el ejemplo del propio backend (`AB1234`) | Resuelta |
| D2 | El formulario no ponía tope a marca y modelo; el contrato exige `max_length=60` | La UI aceptaba texto largo y el backend respondía `422` | Resuelta |
| D3 | El formulario exigía año y kilometraje con rangos inventados; el contrato los declara `int \| None` sin cotas | No se podía registrar un vehículo sin esos datos, y valores válidos (año 1995, 1.500.000 km) quedaban fuera | Resuelta |
| D4 | Este repo afirmaba que `backend/docs/contratos-api-gateway.md` estaba desactualizado | Ya no lo estaba: la dependencia de backend lo había actualizado | Resuelta |

Cambios:

- La patente se valida con `min(1)` y su `placeholder` es `AB1234`, alineado con
  el contrato, que es la autoridad.
- `marca` y `modelo` tienen ahora `.max(60)`, como el backend. El `422` real que
  recibía el usuario por texto largo quedó como fixture
  (`textoVehiculoDemasiadoLargo`) y como prueba en `errors.test.ts`.
- Año y kilometraje son opcionales en el formulario y viajan como `null`
  explícito, el valor que el contrato declara. Se eliminaron los topes que el
  contrato nunca declaró, pero se conserva el rechazo de un valor no numérico o
  negativo.
- Se corrigió la sección que reportaba como deuda un documento del backend que
  ya estaba al día.

Queda anotado para el equipo de backend, sin tocarlo desde el frontend: el
contrato no acota `anio` ni `kilometraje` (debería declarar `ge`/`le`), y el
`origen` del historial es un `str` abierto cuando el dominio solo admite
`usuario` o `sistema`.

| Verificación | Resultado |
| --- | --- |
| `npx tsc --noEmit -p tsconfig.json` | Sin errores |
| `npm run lint` | 0 errores, 0 warnings |
| `npx vitest run` | 347 tests en 54 archivos, todos verdes (antes 341) |
| `npm run build` | Compila; queda el aviso preexistente de chunk > 500 kB |

## Vista web del mecánico y sus órdenes asignadas (2026-10-04)

El portal `/mechanic` ya tenía las vistas de órdenes, detalle y avance de estado,
pero la misión pedía cerrar los huecos que quedaban. Se auditing cada vista contra
los endpoints reales de MS2 antes de tocar nada.

### Bugs encontrados

- **Los vehículos nunca se cargaban** en `/mechanic/ordenes` ni en
  `/mechanic/estados`: ambas páginas leían `useVehicleStore` pero ninguna llamaba
  `fetchVehicles`. Como la caché es solo en memoria, entrar directo a la ruta o
  refrescar dejaba la lista siempre en el fallback `Vehículo N°<id>`, sin patente ni
  modelo. El backend sí entregaba todo lo necesario:
  `listar_vehiculos_para_mecanico` (`services/vehiculos.py`) filtra por
  `mecanico_actual_id` **sin filtro de estado**, así que un solo
  `GET /vehiculos/asignados` etiqueta el 100% de las órdenes del mecánico.
- **La búsqueda por estado no funcionaba** en `/mechanic/ordenes`: el texto
  buscable armaba el hash sin `ordenStatusLabel`, que `AdminOrdersPage` y
  `ClientOrdersPage` sí incluyen.
- **Fuga de datos entre sesiones**: `logout()` y `clearSession()` solo limpiaban la
  sesión de auth, no las cachés de órdenes y vehículos, que son compartidas entre
  los tres portales y usan `mergeById`. Como `MechanicVehiclesPage` filtraba la
  lista completa de `vehicles` solo por texto de búsqueda, un mecánico que
  entrara en el mismo navegador tras una sesión de admin vería los vehículos
  cacheados del admin. Los comentarios del código afirmaban lo contrario.

### Cambios

- Las cuatro vistas del portal cargan sus vehículos asignados y reutilizan los
  helpers `orderVehicleLabel`/`orderPatente`.
- `/mechanic/estados` suma búsqueda, filtro por estado y paginación (reusando
  `useOrderListFilters`, `OrderListToolbar` y `OrderPagination`), y separa en un
  bloque **Órdenes cerradas** las que no tienen ningún avance del mecánico, en vez
  de mostrarles un selector sin opciones.
- El avance de estado pide confirmación con `ConfirmDialog` (componente que
  existía sin uso) y confirma el éxito con un toast.
- Nuevo sistema de toast (`ToastProvider` + `Toast`) montado en `App.tsx`, para
  los tres portales.
- `/mechanic` pasa de un texto que decía "se implementará en una próxima misión" a
  un panel con cuatro indicadores (órdenes asignadas, activas, esperan tu avance y
  vehículos asignados) más el desglose por estado. Se calculan en el cliente porque
  `GET /api/ordenes` devuelve la colección completa sin filtros ni paginación.
- Doble barrera de alcance: además de la Gateway, las vistas comparan contra
  `user.id`. Es válido porque `mecanicoActualId` y `user.id` son ambos el
  `usuario_id` de MS1 (lo usa `_filtro_visibilidad` en MS2). La lógica quedó en
  `mechanicScope.ts`. Y `logout`/`clearSession` ahora purgan las cachés
  compartidas.
- Se eliminaron `/mechanic/historial` (con su enlace de menú) y las páginas
  `MechanicHistoryPage.tsx` y `MechanicPortalPage.tsx`, que eran código muerto.
  No hay endpoint de historial por mecánico: MS2 solo expone
  `GET /api/ordenes/{id}/historial`, y el historial ya se consulta completo en
  `/mechanic/ordenes/:id`.

Se ajustaron los tests que fijaban el comportamiento anterior ("no filtrar por
identidad") y se añadieron los del panel, del toast, del alcance por mecánico y de
la purga de cachés.

| Verificación | Resultado |
| --- | --- |
| `npx tsc --noEmit -p tsconfig.json` | Sin errores |
| `npm run lint` | 0 errores, 0 warnings |
| `npx vitest run` | 380 tests en 133 archivos, todos verdes (antes 347) |
| `npm run build` | Compila; queda el aviso preexistente de chunk > 500 kB |

## Cambios de estado desde la vista del mecánico: matriz y verificación real (2026-10-07)

La vista `/mechanic/estados` ya probaba solo el avance `5 -> 6`. Esta ronda cierra
el resto de la matriz con pruebas de frontend y confirma el ciclo contra
PostgreSQL real y los tres procesos (MS1 + MS2 + Gateway).

### Frontend (tests nuevos)

- `Order.test.ts` amarra `AVANCES_MECANICO` a los 10 pares que acepta
  `backend/services/ms2_taller/domain/transiciones_orden.py:70-111`: si se
  agrega un par que MS2 rechaza, el test falla (no lo descubre el 409 en
  pantalla). Además exige que los 4 estados sin avance del mecánico (3, 6, 7, 8)
  queden explícitos y que todo destino ofrecido tenga etiqueta.
- `MechanicStatusPage.test.tsx` sube a 30 casos: matriz de los 8 estados
  (qué opciones ofrece cada uno y cuáles caen a "Órdenes cerradas"), los 4
  avances del mecánico con observación, errores literales del backend
  (403 reasignación, 409 transición, 409 terminal, 404, 422 listado de
  FastAPI), reintento sin recargar, ausencia de doble envío con el botón en
  "Cargando...", actualización visual de la caché y alcance por `user.id`.
- `OrderService.test.ts` verifica la forma del body (`estado_destino` +
  `observacion`, sin campos extra porque el modelo usa `extra="forbid"`) y que la
  observación de solo espacios se omite (`min_length=1` con strip en MS2).

| Verificación frontend | Resultado |
| --- | --- |
| `npx tsc --noEmit -p tsconfig.json` | Sin errores |
| `npm run lint` | 0 errores, 0 warnings (163 archivos) |
| `npx vitest run` | 417 tests en 141 suites, todos verdes (antes 387) |
| `npm run build` (tsc -b && vite build) | OK; aviso preexistente de chunk > 500 kB |

### PostgreSQL local (en vez de Docker)

Docker Desktop/WSL no estaban disponibles; se usó el PostgreSQL 18 local
(127.0.0.1:5432) que ya corría. Quedó así en `backend/.env` (gitignored, no se
sube):

- Rol `taller` (password `taller`) y bases `taller_ms1`, `taller_ms2`,
  `taller_ms3` (no existían; se crearon solo si faltaban).
- `alembic upgrade head` para MS1, MS2 y MS3, y `scripts/seed_usuarios_prueba.py`
  (idempotente) que crea cliente/mecánico/admin y el perfil Cliente en MS2.

### B1: suite pytest contra PostgreSQL real

Docker no se usa; se apuntan las suites de migración/ORM a la instancia local:

```
$env:MS2_MIGRATION_TEST_DATABASE_URL="postgresql+psycopg://taller:taller@localhost:5432/taller_ms2"
$env:MS3_ORM_TEST_DATABASE_URL="postgresql+psycopg://taller:taller@localhost:5432/taller_ms3"
.\.venv\Scripts\python.exe -m pytest -q
```

Resultado: **488 passed, 0 skipped** (54 s). Incluye MinIO; antes de tenerlo eran
486/2 y con la suite original 427/61 (por tiempos de conexión a 5434/5435).

### MinIO (MS4) con Docker Desktop

El `docker-compose` de MS4 usa `cgr.dev/chainguard/minio` (servidor) y
`quay.io/minio/mc` (cliente `minio_init`); este último ahora responde **401
UNAUTHORIZED** en los pulls (el repo/tag ya no se sirve sin auth). Workaround
verificado (2026-10-07):

```
docker volume create minio_data
docker run -d --name sgtm_minio `
  -e MINIO_ROOT_USER=admin-local -e MINIO_ROOT_PASSWORD=cambia-esta-clave-local `
  -p 9000:9000 -p 9001:9001 `
  -v minio_data:/data -v "$PWD\minio:/config:ro" `
  cgr.dev/chainguard/minio@sha256:999718c09ef5d2ac888aa97ffd628a67ba8be2d64d6eea9e719d1f58cd59e204 `
  server /data --console-address ":9001"
```

El binario `mc` viene incluido en la imagen de Chainguard (lo usa su healthcheck),
así que el setup de `minio_init` se replica con `docker exec sgtm_minio mc
--config-dir /tmp/mc-live ...`: alias `sgtm`, bucket `evidencias` privado, usuario
`ms4-evidencias`, y la política `politica-ms4` desde `/config/politica-ms4.json`
(montada en ro). Verificado con `mc admin user info` (PolicyName: politica-ms4) y
con la suite: `test_ms4_minio_integracion` y `test_ms4_recepcion_minio` en verde.

### B2: ciclo completo contra el stack real (Gateway 8000, MS1 8001, MS2 8002)

Script temporal (borrado al terminar); cada paso se ejecutó con el token real de
MS1 a través de `PATCH /api/ordenes/{id}/estado`. Resultado: **20/20 PASS**.

- Login de admin, cliente y mecánico (3 JWTs), alta de vehículo (cliente)
  y de orden (admin).
- Ciclo de la orden asignada: asignar mecánico mueve `1 -> 2` automáticamente;
  luego mecánico `2 -> 3`, admin `3 -> 5`, mecánico `5 -> 6`, admin `6 -> 7`.
- El historial registra 6 entradas con el actor correcto (mecánico en 2->3 y 5->6;
  admin en las demás) y `origen="usuario"`.
- Rechazos verificados con el literal exacto del backend:
  - terminal: 409 `El estado Entregado es terminal y no admite transiciones`
  - transición inválida: 409 `Transición no permitida: Recibido -> En reparación`
  - no autorizado: 403 `No tienes permiso para cambiar el estado de esta orden`
  - inexistente: 404 `Orden no encontrada`
  - destino desconocido: 422 `Estado de destino desconocido: 999`
  - esquema: 422 con `detail` list (p. ej. `estado_destino: 0`)
- Tras los rechazos la orden sigue en estado 1 (rollback correcto).

Los literales 403/409/404/422 coinciden con los fixtures de
`frontend/src/infrastructure/mocks/payloads.reales.ts` que usan los tests de la
vista, así que los tests de UI y la verificación real validan el mismo contrato.

Nota: al correr desde una consola de Python en Windows, el keep-alive de httpx
contra uvicorn se cae al reutilizar el socket (WinError 10054); el script usó
`httpx.Limits(max_keepalive_connections=1, keepalive_expiry=0)`. Correr pytest
solo también exige que el puerto 5432 esté libre y las 3 bases migradas.
