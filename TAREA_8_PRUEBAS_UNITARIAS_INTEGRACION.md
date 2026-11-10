# 🧪 TAREA 8: Pruebas Unitarias y de Integración

**Carácter:** registro de pruebas y de resultados de una ejecución anterior
**Framework:** pytest + FastAPI TestClient  
**Coverage:** Autenticación, Autorización, JWT, Gateway, Propiedad de Recursos

---

> Los conteos y resultados de este documento corresponden a la ejecución
> registrada originalmente; no acreditan el estado de una revisión posterior.
> El backend Node y su suite Jest se retiraron del árbol activo por no estar
> conectados con el sistema FastAPI. Sus fuentes anteriores permanecen en Git.
> Las pruebas actuales se ejecutan desde `backend/` con pytest y desde
> `frontend/` con Vitest.

---

## 📋 RESUMEN

La suite vigente cubre, con **1150 pruebas** en 55 archivos:

- ✅ Autenticación (registro, login, `/auth/me`, intentos fallidos, historial de roles)
- ✅ JWT: firma, expiración, claims obligatorios, formato de `sub` y `roles`, integridad del token
- ✅ Autorización por rol, incluidos multirol, `401` vs `403` y normalización
- ✅ Propiedad de recursos y acceso cruzado, con `404` indistinguible
- ✅ Acceso indebido entre roles y recursos ajenos del mismo rol
- ✅ Autenticación por canales web y móvil
- ✅ API Gateway: enrutamiento, formato de errores, OpenAPI, CORS, evidencias, health
- ✅ Integración real del JWT emitido por MS1 validado en MS2 a través de la Gateway
- ✅ Contratos de MS3 (presupuestos, aislamiento, persistencia) y MS4 (evidencias, ciclo de archivos, huérfanos)
- ✅ Decisiones de presupuesto (integración y migraciones)

**Total:** 1150 pruebas → **1095 pasan, 55 se omiten y 0 fallan**. No queda
ningún `xfail`: los dos huecos de seguridad que estaban registrados como
`xfail` estricto (§4.3 y §4.4 de la matriz de autorización) quedaron
corregidos y ahora hay pruebas que verifican el comportamiento correcto.
Las omitidas son las que requieren un servicio externo levantado (MinIO o
PostgreSQL descartable) y se habilitan siguiendo la sección «Cómo ejecutar».

Además de `pytest`, el repositorio tiene **dos suites más** que también se
ejecutan hoy:

| Suite | Comando | Resultado verificado |
|---|---|---|
| Frontend (vitest) | `cd frontend && npm test` | **175 pruebas en 37 archivos**, todas pasan |
| Humo Gateway → MS1 | `cd backend && python scripts/prueba_comunicacion_smoke.py` | **33 comprobaciones**, salida 0, con la Gateway y MS1 levantados |

La de frontend cubre los componentes de UI; la de humo comprueba sobre HTTP real
que la cadena de autenticación responde, con casos válidos y rechazados, y es el
equivalente ejecutable de la parte de autenticación de TAREA 7. Ninguna de las
dos sustituye a `pytest`.

---

## 📁 ESTRUCTURA DE PRUEBAS

### Suite vigente (pytest)

```
backend/
├── tests/
│   ├── conftest.py                    Fixtures: SQLite en memoria, .env de pruebas
│   ├── test_acceso_indebido_roles.py               (18)  Acceso indebido entre roles (§4.3 y §4.4 corregidos)
│   ├── test_acceso_recursos_ajenos_mismo_rol.py    (8)  Recursos ajenos del mismo rol
│   ├── test_asignacion_ordenes_api.py              (24)  Asignación, reasignación, idempotencia
│   ├── test_autenticacion_canales.py               (10)  Autenticación por canales web/móvil
│   ├── test_auth_api.py                            (8)  Registro, login, /auth/me
│   ├── test_autorizacion.py                        (6)  401 vs 403, multirol
│   ├── test_decisiones_presupuesto_integracion.py  (28)  Decisiones de presupuesto
│   ├── test_decisiones_presupuesto_postgresql.py   (45)  Decisiones en PostgreSQL (se omiten sin PG)
│   ├── test_gateway_errores_proxy.py               (28)  Errores del proxy
│   ├── test_gateway_estructura.py                  (6)  Estructura de la Gateway
│   ├── test_gateway_evidencias.py                  (14)  Límites de la ruta de evidencias
│   ├── test_gateway_formato.py                     (15)  Formato común de errores
│   ├── test_gateway_health_servicios.py            (10)  Health de servicios
│   ├── test_gateway_openapi.py                     (42)  Swagger y esquemas
│   ├── test_gateway_openapi_ejemplos.py            (20)  Ejemplos del OpenAPI
│   ├── test_gateway_openapi_evidencias.py          (4)  OpenAPI de evidencias
│   ├── test_gateway_rechazos_evidencias.py         (25)  Rechazos de evidencias
│   ├── test_gateway_rutas.py                       (43)  Enrutamiento y reenvío
│   ├── test_historial_roles.py                     (6)  Historial de roles
│   ├── test_integracion_jwt_gateway_ms2.py         (5)  JWT real MS1→Gateway→MS2
│   ├── test_integracion_prefijos.py                (21)  Prefijos de enrutamiento
│   ├── test_integridad_token_jwt.py                (12)  Integridad del token JWT
│   ├── test_jwt.py                                 (11)  Claims, firma, expiración
│   ├── test_login_intentos_fallidos.py             (2)  Intentos fallidos de login
│   ├── test_migraciones_decisiones.py              (2)  Migraciones de decisiones
│   ├── test_ms2_integracion_ms3.py                 (12)  Integración MS2 → MS3
│   ├── test_ms3_aislamiento.py                     (20)  Aislamiento de MS3
│   ├── test_ms3_estructura.py                      (12)  Estructura de MS3
│   ├── test_ms3_integracion_ms2.py                 (17)  Integración MS3 → MS2
│   ├── test_ms3_persistencia_base.py               (15)  Persistencia de MS3
│   ├── test_ms3_presupuestos_contratos.py          (15)  Contratos de presupuestos
│   ├── test_ms4_api_evidencias.py                  (20)  API de evidencias
│   ├── test_ms4_asociacion_ordenes.py              (38)  Asociación de evidencias con órdenes
│   ├── test_ms4_autorizacion_evidencias.py         (24)  Autorización de evidencias
│   ├── test_ms4_ciclo_archivos.py                  (12)  Ciclo de archivos (6 se omiten sin MinIO)
│   ├── test_ms4_config.py                          (2)  Configuración de MS4
│   ├── test_ms4_convencion_metadatos.py            (19)  Convención de metadatos
│   ├── test_ms4_errores_carga.py                   (12)  Errores de carga
│   ├── test_ms4_estructura.py                      (6)  Estructura de MS4
│   ├── test_ms4_huerfanos.py                       (23)  Evidencias huérfanas (1 se omite sin MinIO)
│   ├── test_ms4_limites_archivos.py                (49)  Límites de tamaño y cantidad
│   ├── test_ms4_logs.py                            (23)  Logs de evidencias
│   ├── test_ms4_minio_integracion.py               (2)  Integración MinIO (se omite sin MinIO)
│   ├── test_ms4_modelo_evidencia.py                (17)  Modelo de evidencia
│   ├── test_ms4_recepcion.py                       (18)  Recepción de evidencias
│   ├── test_ms4_recepcion_minio.py                 (1)  Recepción MinIO (se omite sin MinIO)
│   ├── test_ms4_url_firmada.py                     (17)  URLs firmadas
│   ├── test_ms4_validacion_contenido.py            (43)  Validación de contenido
│   ├── test_normalizacion_401_403.py               (14)  Normalización de 401 vs 403
│   ├── test_ordenes_api.py                         (142)  Visibilidad y creación de órdenes
│   ├── test_seguridad_autenticacion.py             (12)  Seguridad de autenticación
│   ├── test_usuarios_roles.py                      (43)  Usuarios y roles
│   ├── test_validadores_orden.py                   (22)  Validadores de dominio
│   └── test_vehiculos_api.py                       (58)  Propiedad y CRUD de vehículos
│
├── requirements-dev.txt               pytest, httpx, respx
└── verificar_conexion.py              Conexiones a las 4 bases de datos
```

`tests/conftest.py` fija las variables `MS*_JWT_SECRET_KEY` y `MS*_DATABASE_URL`
por defecto, así que la suite corre sin `.env` y sin PostgreSQL. 55 pruebas se
omiten si no hay servicios externos: 10 de MinIO
(`docker compose up -d minio minio_init`) y 45 de PostgreSQL descartable; ver
la sección «Casos pendientes».

## 🚀 CÓMO EJECUTAR LAS PRUEBAS

### Instalar dependencias

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

En Linux/macOS: `python3 -m venv .venv && ./.venv/bin/pip install -r requirements-dev.txt`

### Ejecutar todas las pruebas
```bash
python -m pytest tests -q
```

### Resultado verificado
```
1095 passed, 55 skipped, 51 warnings in 292.09s (0:04:52)
```

De las 1150 pruebas, **55 se omiten** por depender de un servicio externo no
levantado y **0 fallan**. El desglose se revisó después de corregir los dos
huecos de seguridad `xfail` que antes registraba este documento (§4.3 y §4.4
de la matriz de autorización). El detalle completo está en la sección
[«Casos pendientes»](#-casos-pendientes).

Las omitidas se describen solas con `-rs` y son de dos grupos:

```
SKIPPED tests/test_ms4_ciclo_archivos.py:389: MinIO no está disponible
        (docker compose up -d minio minio_init)      ← 10 omitidas de MinIO (una de test_ms4_huerfanos.py)
SKIPPED tests/test_decisiones_presupuesto_postgresql.py:92:
        Se requieren dos PostgreSQL locales descartables para SCRUM-397/438
                                                      ← 45 omitidas de PostgreSQL
```

Para incluirlas:
```bash
docker compose up -d minio minio_init        # habilita las 10 de MinIO
python -m pytest tests -q
```

Las 45 de PostgreSQL necesitan además dos bases descartables levantadas; ver
`test_decisiones_presupuesto_postgresql.py`.

### Ejecutar un subconjunto
```bash
python -m pytest tests/test_autorizacion.py -v
python -m pytest tests -k "gateway or jwt" -q
```

### Comprobar las conexiones a las bases de datos
```bash
python verificar_conexion.py     # requiere los 4 servicios de DB levantados
```

---

## 📊 COBERTURA

**Módulos del sistema en ejecución con cobertura directa:**

| Módulo | Archivo(s) de pruebas | Pruebas |
|---|---|---|
| `shared/auth.py` — emisión y validación de JWT | `test_jwt.py` (11), `test_integridad_token_jwt.py` (12) | 23 |
| `services/ms1_auth` — registro, login, `/auth/me`, roles, seguridad, canales web/móvil | `test_auth_api.py` (8), `test_autorizacion.py` (6), `test_usuarios_roles.py` (43), `test_historial_roles.py` (6), `test_login_intentos_fallidos.py` (2), `test_autenticacion_canales.py` (10), `test_normalizacion_401_403.py` (14), `test_seguridad_autenticacion.py` (12) | 101 |
| `services/ms2_taller` — vehículos | `test_vehiculos_api.py` | 58 |
| `services/ms2_taller` — órdenes y asignación de mecánico | `test_ordenes_api.py` (142), `test_asignacion_ordenes_api.py` (24) | 166 |
| `services/ms2_taller` — validadores de dominio | `test_validadores_orden.py` | 22 |
| `gateway` — rutas, formato de errores, OpenAPI, CORS, evidencias, health | `test_gateway_rutas.py` (43), `test_gateway_errores_proxy.py` (28), `test_gateway_openapi.py` (42), `test_gateway_openapi_ejemplos.py` (20), `test_gateway_openapi_evidencias.py` (4), `test_gateway_formato.py` (15), `test_gateway_rechazos_evidencias.py` (25), `test_gateway_evidencias.py` (14), `test_gateway_health_servicios.py` (10), `test_gateway_estructura.py` (6) | 207 |
| Integración MS1 → Gateway → MS2 y prefijos | `test_integracion_jwt_gateway_ms2.py` (5), `test_integracion_prefijos.py` (21) | 26 |
| `services/ms3_presupuestos` | `test_ms3_aislamiento.py` (20), `test_ms3_integracion_ms2.py` (17), `test_ms3_presupuestos_contratos.py` (15), `test_ms3_persistencia_base.py` (15), `test_ms3_estructura.py` (12), `test_ms2_integracion_ms3.py` (12) | 91 |
| `services/ms3_presupuestos` — decisiones de presupuesto | `test_decisiones_presupuesto_integracion.py` (28), `test_decisiones_presupuesto_postgresql.py` (45, se omiten sin PostgreSQL), `test_migraciones_decisiones.py` (2) | 75 |
| `services/ms4_evidencias` | `test_ms4_validacion_contenido.py` (43), `test_ms4_limites_archivos.py` (49), `test_ms4_asociacion_ordenes.py` (38), `test_ms4_autorizacion_evidencias.py` (24), `test_ms4_huerfanos.py` (23, 1 se omite sin MinIO), `test_ms4_logs.py` (23), `test_ms4_api_evidencias.py` (20), `test_ms4_convencion_metadatos.py` (19), `test_ms4_recepcion.py` (18), `test_ms4_modelo_evidencia.py` (17), `test_ms4_url_firmada.py` (17), `test_ms4_ciclo_archivos.py` (12, 6 se omiten sin MinIO), `test_ms4_errores_carga.py` (12), `test_ms4_estructura.py` (6), `test_ms4_config.py` (2), `test_ms4_minio_integracion.py` (2, se omiten sin MinIO), `test_ms4_recepcion_minio.py` (1, se omite sin MinIO) | 326 |
| Seguridad transversal — acceso indebido entre roles y recursos ajenos del mismo rol | `test_acceso_indebido_roles.py` (18, incluye §4.3/§4.4 corregidos), `test_acceso_recursos_ajenos_mismo_rol.py` (8) | 26 |
| **Total** | **55 archivos** | **1150** |

**Total de la suite: 1150 pruebas** → 1095 pasan, 55 se omiten (10 de MinIO y
45 de PostgreSQL descartable) y **0 fallan**; ya no queda ningún `xfail`
estricto: los huecos §4.3 y §4.4 de la matriz de autorización están corregidos
y cuentan como pruebas que pasan.

**Cobertura transversal de seguridad**, presente en varios archivos:

- `401` vs `403`: token ausente, inválido, expirado y `sub` no entero devuelven
  `401`; el rol insuficiente devuelve `403`.
- `404` indistinguible: un recurso ajeno y uno inexistente responden igual, tanto
  en órdenes como en vehículos.
- Campos controlados por el servidor: el body no puede fijar propietario,
  estado, responsable ni fechas.
- Rollback: los fallos de persistencia no dejan escrituras parciales.
- Idempotencia: repetir la misma asignación no crea historial duplicado.

No se publica un porcentaje de cobertura de líneas: la suite no se ejecuta con
`--cov`, así que cualquier cifra en este documento estaría sin respaldo. Para
obtenerla:

```bash
python -m pip install pytest-cov
python -m pytest tests --cov=services --cov=gateway --cov=shared
```

## 🔍 EJEMPLOS DE PRUEBAS (suite vigente)

### Ejemplo 1: contrato de claims del JWT
```python
def test_claims_obligatorios_y_formato(sin_exp, sin_sub, sub_uuid):
    """El token exige sub entero positivo y roles no vacía."""
```

### Ejemplo 2: el rol insuficiente no es lo mismo que un token inválido
```python
def test_mecanico_sin_cliente_recibe_403(...):
    """Token válido pero rol insuficiente -> 403, no 401."""
```

### Ejemplo 3: un recurso ajeno es indistinguible de uno inexistente
```python
def test_get_detalle_cliente_ajeno_recibe_404(...):
    """No se revela la existencia de órdenes de otro cliente."""
```

---

## ✅ RESULTADOS ESPERADOS

### Suite vigente — resultado verificado

```
1095 passed, 55 skipped, 51 warnings in 292.09s (0:04:52)
```

Reproducir con `cd backend && python -m pytest tests -q`. De las 1150 pruebas,
55 se omiten por depender de servicios externos (10 de MinIO y 45 de PostgreSQL
descartable) y **0 fallan**; ya no queda ningún `xfail`: los huecos de seguridad
§4.3 y §4.4 están corregidos (detalle en la sección «Casos pendientes»).

## ⏳ CASOS PENDIENTES

De las 1150 pruebas de la suite vigente, **1095 pasan**. Las restantes **55 no
son fallos**: se omiten por depender de un servicio externo no levantado.
Antes había además 4 `xfail` estrictos que registraban huecos de seguridad
abiertos (§4.3 y §4.4 de la matriz de autorización): **ya están corregidos**,
las marcas se retiraron y sus casos quedaron como pruebas de regresión con
código de rechazo exacto (3 casos nuevos y las 4 antiguas convertidas, más
las de versiones/inventario de §4.4 → 25 en
`test_acceso_indebido_roles.py`). Este documento mantiene todos los estados
identificados; ninguno se esconde ni se «bendice».

### 1. Omitidas por servicio externo (55)

Se habilitan levantando el servicio correspondiente y volviendo a correr la
suite. Con todos los servicios levantadas no debería quedar ninguna omitida.

| Grupo | Pruebas | Servicio requerido | Cómo habilitarla |
|---|---|---|---|
| `test_ms4_ciclo_archivos.py` | 6 | MinIO | `docker compose up -d minio minio_init` |
| `test_ms4_minio_integracion.py` | 2 | MinIO | ídem |
| `test_ms4_recepcion_minio.py` | 1 | MinIO | ídem |
| `test_ms4_huerfanos.py` | 1 | MinIO | ídem (reutiliza el fixture `cliente_minio` de `test_ms4_recepcion_minio.py`) |
| `test_decisiones_presupuesto_postgresql.py` | 45 | Dos PostgreSQL locales descartables | Ver el propio archivo (casos SCRUM-397/438) |
| **Total** | **55** | **MinIO (10) + PostgreSQL (45)** | |

### 2. Casos corregidos de seguridad — registro con evidencia (2026-11)

Cada déficit de seguridad corregido en la rama `DerisA` queda registrado aquí
con su defecto, su corrección y la prueba reproducible que lo demuestra
(`cd backend && python -m pytest tests/<archivo>.py -q`).

#### 2.1 Credenciales vacías o de espacios en el login (MS1)

- **Defecto:** `LoginSolicitud` no imponía longitud mínima a `password`
  (`services/ms1_auth/schemas/auth.py`), así que una contraseña vacía o de
  espacios llegaba al caso de uso como si fuera un intento real.
- **Corrección:** `password: str = Field(min_length=1)` (commit `0e3aaa5`);
  el rechazo ocurre en la capa de schemas (`422`), sin tocar la base ni sumar
  intentos fallidos, por lo que tampoco puede bloquear una cuenta.
- **Evidencia:** `tests/test_credenciales_vacias_y_multirol.py` —
  `test_login_con_credenciales_vacias_o_invalidas_devuelve_422`,
  `test_password_vacia_no_cuenta_como_intento_fallido`,
  `test_password_incorrecta_no_vacia_si_cuenta_como_intento`,
  `test_registro_con_datos_vacios_o_invalidos_devuelve_422_y_no_crea_cuenta`.

El mismo archivo registra las reglas de **cuentas multirol**, que no era un
déficit sino verificación reforzada (commit `ef62dc4`): el token lleva todos
los roles sin duplicados y las reglas de credenciales (mensaje genérico,
bloqueo, cuenta inactiva, acceso administrativo) se aplican igual que a una
cuenta de un solo rol — entre otras,
`test_token_de_cuenta_multirol_lleva_todos_los_roles_sin_duplicados`,
`test_cuenta_multirol_se_bloquea_igual_que_una_de_un_rol`,
`test_cuenta_multirol_inactiva_recibe_401_generico`,
`test_multirol_sin_administrador_no_accede_a_gestion_de_usuarios` y
`test_multirol_con_administrador_accede_con_token_de_login`.

#### 2.2 Huecos de autorización §4.3 y §4.4 de la matriz de roles

Los 4 `xfail` estrictos que registraban los huecos de
`test_acceso_indebido_roles.py` se retiraron tras implementar la corrección:

| Antiguo `xfail` | Estado actual |
|---|---|
| `test_administrador_no_asigna_a_un_usuario_inexistente` | Pasa: `mecanico_id` se valida contra MS1 y el usuario inexistente responde `404` |
| `test_administrador_no_asigna_a_un_usuario_sin_rol_mecanico` | Pasa: el usuario activo sin rol `mecanico` responde `409` |
| `test_mecanico_no_asignado_no_crea_presupuesto_de_orden_ajena` | Pasa: MS3 consulta la visibilidad en MS2 y la orden ajena responde `404` |
| `test_mecanico_no_crea_presupuesto_de_orden_inexistente` | Pasa: la orden inexistente responde `404` |

- **§4.3 (commit `12de38d`):** asignación de mecánico validada fail-closed
  contra MS1 (`services/ms2_taller/integracion_ms1.py`: `404` usuario
  inexistente, `409` usuario inactivo o sin rol `mecanico`, `503` con MS1 no
  disponible y la orden intacta) y creación de presupuesto en MS3 sujeta a la
  visibilidad que MS2 confirma.
- **§4.4 (commit `a98046c`):** el mismo alcance del mecánico se aplicó a las
  versiones y a los movimientos de stock con `orden_id` de MS3
  (`presupuestos.py` y `inventario.py::registrar`): orden ajena o inexistente
  `404` indistinguible, MS2 caído `503`, todo fail-closed antes de escribir.
- **Casos nuevos de evidencia (§4.3):** en `test_acceso_indebido_roles.py`,
  `test_ms1_caido_no_modifica_reasignacion_ni_historial` (falla cerrada `503`
  de MS1 con la orden intacta) y `test_mecanico_asignado_crea_presupuesto_con_su_identidad`
  (mecánico asignado que SÍ presupuesta su orden, `201`); la validación del
  destino inactivo o sin rol `mecanico` queda expuesta en
  `test_validacion_referencias_personal.py` (`test_ms1_destino_invalido_se_rechaza`).
- **Casos nuevos de evidencia (§4.4):**
  `test_mecanico_no_asignado_no_versiona_ni_edita_presupuesto_ajeno`,
  `test_mecanico_asignado_versiona_presupuesto_de_su_orden`,
  `test_mecanico_no_asignado_no_registra_compromiso_de_stock_ajeno`,
  `test_mecanico_asignado_registra_compromiso_de_su_orden` y
  `test_compromiso_sin_ms2_no_se_aplica_responde_503`.

#### 2.3 Auditoría de propiedad de vehículos y órdenes (§4.2)

- **Resultado:** no se halló hueco de propiedad: el cliente solo opera sus
  vehículos/órdenes, el mecánico solo las asignadas (con `404`
  indistinguible) y la lectura administrativa del parque es intencional y
  tiene pruebas que la exigen.
- **Cobertura añadida (commit `c6f9a63`):** `tests/test_vehiculos_api.py` —
  `test_post_administrador_puro_recibe_403` y
  `test_patch_administrador_puro_recibe_403`: la escritura exige rol
  `cliente` y el Administrador puro recibe `403` sin dejar cambios en la fila.
- **Matriz alineada:** la §4.2 de
  [`docs/matriz-autorizacion-roles.md`](backend/docs/matriz-autorizacion-roles.md)
  quedó con el comportamiento real (listado y detalle administrativos del
  parque completo con pruebas, `GET /api/vehiculos/asignados` solo mecánico,
  `POST`/`PATCH` solo Cliente).

Referencia completa de huecos y decisiones pendientes:
[`docs/matriz-autorizacion-roles.md`](backend/docs/matriz-autorizacion-roles.md).

### 3. No automatizado en esta suite

- **Frontend (vitest):** se corre aparte (`cd frontend && npm test`), 175 pruebas
  en 37 archivos. No la sustituye `pytest`.
- **Humo sobre HTTP real:** `scripts/prueba_comunicacion_smoke.py`, 33
  comprobaciones, requiere la Gateway y MS1 levantadas. No corre dentro de
  `pytest`.

### 4. Suite histórica (Jest) no ejecutable
`__tests__/`, `jest.config.js` y `package.json` de la raíz no cargan ninguna
suite y `backend/src/` está incompleto (`models/User` ausente). Queda **pendiente
de decisión del equipo** retirarla; ver la sección «Conclusión». No se ha tocado
ningún archivo de esa suite en este registro.

---


## 🛠️ CONFIGURACIÓN

### Suite vigente

No requiere archivo de configuración: `pytest` descubre `tests/` por convención
y `tests/conftest.py` fija las variables de entorno de pruebas. Las dependencias
de prueba se instalan con `requirements-dev.txt` (`pytest`, `httpx`, `respx`).

## 📈 BENEFICIOS

✅ **Confianza:** Sabe que el código funciona  
✅ **Refactoring seguro:** Puede cambiar código sin miedo  
✅ **Documentación viva:** Las pruebas documentan el comportamiento  
✅ **Catch bugs:** Previene regressions  
✅ **Quality:** 1150 pruebas de uso cubiertas, incluidas las de seguridad

---

## 🎯 CONCLUSIÓN

**Pruebas completas y verificadas sobre el sistema en ejecución:**
- 1150 pruebas: 1095 pasan, 55 se omiten por servicios externos (10 MinIO y 45 PostgreSQL descartable), 0 fallos y 0 `xfail` (los huecos §4.3/§4.4 ya están corregidos)
- Autenticación verificada
- Autorización verificada, con `401` y `403` diferenciados
- Propiedad de recursos y acceso cruzado verificados, con `404` indistinguible
- Contrato de claims del JWT verificado contra `shared/auth.py`
- Gateway verificada: enrutamiento, reenvío de `Authorization`, errores, OpenAPI
- Integración real JWT de MS1 → Gateway → MS2 verificada

El código Node y su suite Jest fueron retirados. Esta retirada no elimina
pruebas de `backend/tests/` ni de `frontend/src/`, que verifican el sistema
vigente. Los ejemplos de endpoints del monolito no son contratos disponibles.

**TAREA 8: COMPLETADA** ✅

