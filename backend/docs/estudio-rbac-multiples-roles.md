# Estudio: RBAC con usuarios de múltiples roles

Documento de estudio sobre cómo el sistema aplica **Control de Acceso Basado en
Roles (RBAC)** cuando una misma cuenta posee **más de un rol a la vez**.

Describe el diseño existente y reporta hallazgos. **No implementa cambios**: no
crea endpoints, no modifica permisos ni altera el contrato del token.

Fuentes de verdad del comportamiento:

- [`matriz-autorizacion-roles.md`](matriz-autorizacion-roles.md) — qué puede hacer
  cada rol en cada recurso. Manda sobre **quién** puede ver o hacer algo.
- [`contratos-api-gateway.md`](contratos-api-gateway.md) — rutas, cuerpos y
  errores. Manda sobre el contrato HTTP.
- [`estudio-seguridad-transporte.md`](estudio-seguridad-transporte.md) — el flujo
  completo de autenticación y los guards reutilizables de FastAPI.

## 1. Por qué este estudio

RBAC se resuelve bien cuando cada usuario tiene exactamente un rol. La pregunta
interesante aparece cuando **las identidades se superponen**: un mecánico que
también es cliente de su propio vehículo, o un administrador que además atiende
órdenes.

El sistema ya implementa RBAC completo sobre cuatro microservicios. Este estudio
aisla la dimensión **multirol** para responder tres preguntas:

1. ¿Cómo se acumulan los roles: por unión o por intersección?
2. ¿En qué capa se decide, y contra qué se compara?
3. ¿Qué tan frescos están los permisos que el token declara?

## 2. Cómo se modela RBAC aquí

| Concepto RBAC | Equivalente en el sistema |
|---|---|
| Sujeto | La identidad del JWT: `usuario_id` + `roles` |
| Rol | `NombreRol`: `cliente`, `mecanico`, `administrador` |
| Permiso | La fila de la matriz de autorización para ese rol y recurso |
| Asignación | La tabla intermedia `usuario_rol` (relación M:N) |
| Sesión | El Bearer JWT, con vigencia de 60 minutos |

El permiso **no se asigna al usuario**: se asigna al rol. El usuario adquiere
permisos de forma indirecta al poseer roles. Un usuario multirol adquiere, por
definición, la **suma** de los permisos de todos sus roles.

Los tres roles viven en `backend/shared/auth.py` (`NombreRol`, línea 18). No hay
permisos granulares ni roles custom: la matriz de autorización es el catálogo
útil de permisos.

## 3. Fuentes de verdad

| Qué define | Dónde vive |
|---|---|
| Los tres roles y su enumeración | `backend/shared/auth.py` → `NombreRol` |
| Emisión y validación del JWT | `backend/shared/auth.py` → `crear_token_acceso`, `validar_token_acceso` |
| Persistencia de la asignación | `services/ms1_auth/models/usuario.py` → relación `roles` (M:N) |
| Lectura y validación de roles desde BD | `services/ms1_auth/services/autenticacion.py:229` → `roles_del_usuario` |
| Guard de rol por endpoint | `services/ms1_auth/dependencies.py:63` y `services/ms3_presupuestos/dependencies.py:56` → `requerir_roles` |
| Guard de recurso local | `services/ms2_taller/dependencies.py:43` → `resolver_cliente_actual` |
| Visibilidad de órdenes por rol | `services/ms2_taller/services/ordenes.py:295` → `_filtro_visibilidad` |
| Qué puede hacer cada rol | `docs/matriz-autorizacion-roles.md` |

### 3.1 El contrato del token

`shared/auth.py` es la **única fuente de verdad** de identidad y roles. Ningún
servicio reimplementa su validación. El claim tiene exactamente tres claves:
`sub`, `roles`, `exp`.

Propiedades del claim `roles`, verificadas:

| Propiedad | Emisor `crear_token_acceso` | Validador `validar_token_acceso` |
|---|---|---|
| Lista no vacía | rechaza con `ValueError` | rechaza con `TokenInvalidoError` |
| Sin duplicados | rechaza con `ValueError` | rechaza con `TokenInvalidoError` |
| Solo roles conocidos | rechaza con `ValueError` | rechaza con `TokenInvalidoError` |
| Elementos de tipo texto | — | rechaza con `TokenInvalidoError` |
| Orden determinista | sí, ordena por `.value` | no exige orden |

El validador **no consulta la base de datos**: los roles del token se aceptan
como válidos mientras la firma y la expiración lo estén. Esta es la propiedad
que sostiene el rendimiento de los guards y también la causa del hallazgo 8.1.

### 3.2 Dónde viven los roles en la base de datos

Los roles son una relación M:N entre `Usuario` y `Rol`. `roles_del_usuario`
(`autenticacion.py:229`) los normaliza a `frozenset[NombreRol]` y **lanza
`ConfiguracionRolesError` si la lista está vacía**, además de si encuentra un rol
desconocido. Esa validación corre en `login` y en `/auth/me`, no en los guards
(hallazgo 8.4).

El token se arma **una sola vez**, en `POST /auth/login`
(`routers/auth.py:76`), combinando `roles_del_usuario` con `crear_token_acceso`.

## 4. Los dos mecanismos de autorización

RBAC se decide en dos momentos distintos, con semántica de unión en ambos.

### 4.1 Guard de rol: ¿puede entrar a este endpoint?

```python
def requerir_roles(*roles_permitidos: NombreRol):        # ms1/dependencies.py:63
    permitidos = frozenset(roles_permitidos)
    def dependencia(principal=Depends(obtener_principal_actual)):
        if principal.roles.isdisjoint(permitidos):       # vacío -> 403
            raise HTTPException(status_code=403, ...)
        return principal
    return dependencia
```

La prueba es de **intersección vacía**: si el usuario tiene *al menos uno* de los
roles permitidos, entra. Es decir, la **unión** de los roles manda. Un usuario
`administrador + mecanico` satisface cualquier guard que pida uno de los dos.

Se aplica de dos formas:

```python
# 1. Solo proteger, sin necesitar la identidad
@router.get("", dependencies=[Depends(requerir_roles(NombreRol.ADMINISTRADOR))])

# 2. Proteger y además usar quién llama
def endpoint(principal: PrincipalAutenticado = Depends(requerir_roles(...)))
```

`requerir_roles` existe en **dos microservicios** (MS1 y MS3) con la misma
semántica. La diferencia de comportamiento cuando se invoca sin argumentos está
documentada en [`estudio-seguridad-transporte.md`](estudio-seguridad-transporte.md)
§7.2 y no se repite aquí.

### 4.2 Visibilidad por recurso: ¿qué ve dentro del endpoint?

Superado el guard, `_filtro_visibilidad` (`ordenes.py:295`) traduce los roles en
un filtro SQL:

| Roles del principal | Filtro devuelto | Efecto |
|---|---|---|
| incluye `administrador` | `None` | sin `WHERE` → acceso global |
| incluye `cliente` | `EXISTS (...vehiculo, cliente...)` | órdenes de sus vehículos |
| incluye `mecanico` | `mecanico_actual_id = :id` | órdenes asignadas a él |
| incluye `cliente` **y** `mecanico` | `or_(ambos)` | **unión** de ambos alcances |

Se usa en `listar_ordenes` (`ordenes.py:256`) y en `obtener_orden_visible`
(`ordenes.py:273`), con la misma regla. Un recurso fuera del alcance responde
`404`, no `403`, para no revelar su existencia.

### 4.3 Por qué unión y nunca intersección

La regla está en `matriz-autorizacion-roles.md` §3.1 y §6.2:

> Nunca se debe intersectar alcances: un usuario con dos roles **no** debe ver
> menos que uno que tenga solo uno de ellos.

Con intersección, un usuario `cliente + mecanico` solo vería las órdenes que son
simultáneamente suyas **y** asignadas a él — casi siempre el conjunto vacío.
Tener más roles jamás puede ser un perjuicio.

## 5. Comportamiento verificado de un usuario multirol

Verificado contra la aplicación real (no por lectura de código). Los siete
subconjuntos no vacíos de los tres roles, aplicados a `_filtro_visibilidad`:

| Subconjunto | Filtro resultante |
|---|---|
| `cliente` | `EXISTS (SELECT 1 FROM vehiculo, orden_trabajo ...)` |
| `mecanico` | `orden_trabajo.mecanico_actual_id = :id` |
| `administrador` | `NULL` → sin filtro, acceso global |
| `cliente + mecanico` | `or_` de ambos alcances |
| `cliente + administrador` | `NULL` → acceso global |
| `mecanico + administrador` | `NULL` → acceso global |
| `cliente + mecanico + administrador` | `NULL` → acceso global |

Y sobre el guard de rol (`GET /auth/usuarios`, exige `administrador`):

| Roles del token | Resultado |
|---|---|
| `administrador` | `200` |
| `administrador + mecanico` | `200` — la unión permite entrar |
| `cliente + mecanico` | `403` |
| `cliente` | `403` |

### 5.1 El rol que manda: administrador

`administrador` es **absorbente** en la visibilidad: cualquier subconjunto que lo
contenga devuelve filtro `None`. Un administrador que además es cliente o
mecánico no pierde nada, pero **tampoco gana la capacidad de verse a sí mismo de
forma restringida**: no hay forma de pedir "muéstrame solo lo mío".

### 5.2 Vehículos: donde el multirol no basta por sí solo

Los endpoints de vehículos no usan `requerir_roles`, sino `resolver_cliente_actual`
(`ms2/dependencies.py:43`), que encadena dos condiciones:

1. `cliente` debe estar en `principal.roles` → si no, `403`.
2. Debe existir un perfil `Cliente` localmente → si no, `404`.

Por eso en la matriz §4.2 el Administrador aparece con ⚠️: **el rol
`administrador` por sí solo no da acceso a vehículos**. Solo lo da si la cuenta
*además* tiene `cliente` y existe su perfil local. Es el único punto del sistema
donde un rol administrativo no es suficiente.

## 6. Vigencia de los roles: el token congela los permisos

Este es el hallazgo más relevante del estudio multirol.

### 6.1 Qué se observa

Secuencia verificada con la aplicación real:

| Paso | Acción | Resultado |
|---|---|---|
| 1 | `ana` inicia sesión | token **T1** con `roles: ["cliente"]` |
| 2 | un administrador le otorga `administrador` | `200`, la BD ya lo refleja |
| 3 | **T1** llama a `GET /auth/usuarios` (solo admin) | **`403`** — T1 no conoce el rol nuevo |
| 4 | **T1** llama a `GET /auth/me` | **`200`** con `["administrador", "cliente"]` |
| 5 | `ana` vuelve a iniciar sesión | token **T2** con `["administrador", "cliente"]` |
| 6 | **T2** llama a `GET /auth/usuarios` | `200` |

Y en el sentido inverso:

| Paso | Acción | Resultado |
|---|---|---|
| 1 | se emite **T3** con `administrador` | — |
| 2 | un administrador le retira `administrador` | `200`, la BD ya lo refleja |
| 3 | **T3** llama a `GET /auth/usuarios` | **`200`** — el privilegio sigue vigente |
| 4 | `ana` vuelve a iniciar sesión | sin `administrador` |
| 5 | token nuevo llama a `GET /auth/usuarios` | `403` |

### 6.2 Por qué ocurre

Los roles entran al token en el instante de `POST /auth/login` y **no se vuelven
a leer**. `requerir_roles` y `_filtro_visibilidad` trabajan exclusivamente sobre
`principal.roles`, proveniente del claim. `obtener_principal_actual` valida firma
y expiración sin tocar la base de MS1.

`GET /auth/me` sí consulta la base (`obtener_usuario_actual` →
`buscar_usuario_activo_por_id`), por eso responde con los roles **actuales**
mientras los guards responden con los roles **emitidos**.

### 6.3 Ventana de revocación

- **Revocación:** hasta que el token expire. `JWT_EXPIRE_MINUTES` es `60`
  (`ms1_auth/config.py:32`). Asignar o retirar roles **no invalida** tokens ya
  emitidos: el privilegio retirado sigue siendo usable hasta 60 minutos después.
- **Asignación:** el permiso nuevo no es usable hasta que el usuario vuelva a
  iniciar sesión. No existe endpoint de refresco de token.

## 7. Cobertura de pruebas

| Archivo | Prueba | Qué cubre |
|---|---|---|
| `test_autorizacion.py` | `test_multirol_incluyendo_cliente_es_permitido` | unión en el guard de rol |
| `test_autorizacion.py` | `test_mecanico_sin_cliente_recibe_403` | rol insuficiente |
| `test_autorizacion.py` | `test_token_ausente_devuelve_401` / `..._invalido...` | `401` vs `403` |
| `test_ordenes_api.py` | `test_get_multirol_une_alcances_sin_duplicados` | unión de alcances sin duplicados |
| `test_ordenes_api.py` | `test_get_administrador_multirol_mantiene_acceso_global` | `administrador` absorbente |
| `test_ordenes_api.py` | `test_post_multirol_con_administrador_puede_crear` | creación con multirol |
| `test_vehiculos_api.py` | `test_usuario_multirol_con_cliente_es_permitido` | `resolver_cliente_actual` con multirol |
| `test_vehiculos_api.py` | `test_usuario_sin_rol_cliente_recibe_403` | `administrador` no basta |
| `test_asignacion_ordenes_api.py` | `test_multirol_con_administrador_puede_asignar...` | asignación con multirol |
| `test_ms3_estructura.py` | `test_guard_rol_permitido_responde_200...` | guard de MS3 |

## 8. Hallazgos

Ninguno está corregido por este estudio: se documentan para su decisión.

### 8.1 Los roles del token caducan con él, no con la base

Verificado en §6. Consecuencias:

- **Revocación tardía:** tras retirar un rol, el usuario conserva ese privilegio
  hasta 60 minutos. Si el motivo del retiro era de seguridad, la ventana es
  relevante.
- **Asignación tardía:** tras conceder un rol, el usuario no puede usarlo hasta
  re-login. Puede confundirse con un fallo del guard.
- **Divergencia `/auth/me` vs guards:** la misma identidad con el mismo token
  reporta unos roles y es autorizada con otros (paso 4 vs paso 3 de §6.1).

Es una decisión de diseño clásica del estado sin sesión del JWT: no se consulta
la base por petición. Corregirlo exigiría un mecanismo de revocación (lista de
bloqueo, versión de rol embebida en el token o revalidación por petición), lo
cual cambia el contrato y el rendimiento — fuera del alcance de este estudio.

### 8.2 La rama `false()` de `_filtro_visibilidad` es inalcanzable

`_filtro_visibilidad` termina en `return or_(*alcances) if alcances else false()`.
La rama `false()` significaría "sin roles visibles → no ve nada", pero es
inalcanzable en ejecución: `crear_token_acceso` rechaza listas vacías y
`validar_token_acceso` rechaza un claim `roles` vacío, desconocido o con
duplicados. Por tanto `principal.roles` es siempre un subconjunto **no vacío y
conocido** de los tres roles, y los siete casos de §5 generan siempre un filtro
distinto de `false()`.

Es código defensivo legítimo, no un defecto. Se documenta para que nadie lo
interprete como una rama con comportamiento propio que deba probarse.

### 8.3 Las cuentas sin roles responden `500` en `login` y `/auth/me`

Defecto conocido y **pendiente de decisión**: `roles_del_usuario` lanza
`ConfiguracionRolesError` con una lista vacía y ambos endpoints lo traducen en
`500`. Los endpoints de consulta (`GET /auth/usuarios`, `GET /auth/usuarios/{id}`)
y el `DELETE` de roles **sí** toleran `roles: []`.

No se corrigió aquí por estar fuera del alcance de este estudio.

### 8.4 `matriz-autorizacion-roles.md` §4.1 está desactualizada

La sección 4.1 todavía dice «Ver datos de **otros** usuarios | — | — | —» y
«No existe ningún endpoint de administración de usuarios», pero ya existen
`GET /auth/usuarios`, `GET /auth/usuarios/{id}`, `POST` y `DELETE` de roles,
todos exclusivos de Administrador. §8 de esa matriz exige actualizarla cuando
cambia un endpoint.

Pendiente de decisión; no se modificó en este estudio.

### 8.5 `requerir_roles` está duplicado en MS1 y MS3

Dos implementaciones con la misma semántica de unión. Ya está tratado en
[`estudio-seguridad-transporte.md`](estudio-seguridad-transporte.md) §7.1 y §7.2;
se menciona aquí solo para no perderlo del mapa multirol.

## 9. Qué no cubre este estudio

- **No modifica código.** Todo lo reportado está sin corregir.
- **No crea ni propone roles ni permisos nuevos.** Los tres de `NombreRol` son
  los únicos válidos.
- **No cambia el contrato del JWT.**
- **No cubre `frontend/`**: la ocultación de acciones por rol en la interfaz es
  experiencia de usuario, no seguridad (matriz §6.1).
- **No cubre MS4**: tiene `obtener_principal_actual` sin endpoints que la usen.
- **No sustituye** la matriz de autorización ni el contrato de la API.

## 10. Referencias

- [`matriz-autorizacion-roles.md`](matriz-autorizacion-roles.md) — §3.1 regla
  multirol, §4 matriz maestra, §5 semántica de errores, §6.2 evidencias.
- [`contratos-api-gateway.md`](contratos-api-gateway.md) — rutas y errores.
- [`estudio-seguridad-transporte.md`](estudio-seguridad-transporte.md) — flujo de
  autorización completo, guards reutilizables, hallazgos 7.1 y 7.2.
- [`maquina-estados-ordenes.md`](maquina-estados-ordenes.md) — estados de la orden.
- `backend/shared/auth.py` — contrato único de identidad y roles.
