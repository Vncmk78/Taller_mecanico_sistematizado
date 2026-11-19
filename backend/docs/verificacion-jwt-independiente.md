# Verificación: Gateway y microservicios validan el JWT de forma independiente

**Semana 9 — Verificar que Gateway y microservicios validen el JWT de forma independiente.**

**Resultado: se cumple.** Las 88 operaciones protegidas de MS1–MS4 rechazan con
`401` los siete tipos de token inválido probados, llamando a cada
microservicio **directo, sin pasar por la Gateway**. La Gateway no tiene el
secreto, no decide la autenticación y reenvía el token sin tocarlo.

- Prueba automática: `tests/test_validacion_jwt_independiente.py` (110 casos)
- Decisión de diseño: [`contratos-api-gateway.md`](contratos-api-gateway.md), «Quién valida el token»
- Flujo completo: [`estudio-seguridad-transporte.md`](estudio-seguridad-transporte.md) §5

---

## 1. Qué significa «independiente» en este sistema

| Capa | Qué hace con el JWT | Por qué |
|---|---|---|
| Gateway | **No lo valida.** Reenvía `Authorization` intacta al microservicio | Sin el secreto, la Gateway no puede fabricar identidades; solo mueve bytes |
| MS1, MS2, MS3, MS4 | Cada uno lo valida en su dependencia `obtener_principal_actual` con `shared.auth.validar_token_acceso` | Un microservicio no confía en que la petición «ya pasó por la Gateway»: si alguien lo llama directo, igual rechaza |

Por eso la verificación no busca dos validaciones del mismo token. Busca que
ningún microservicio dependa de otro, ni de la Gateway, para rechazar un
token inválido.

## 2. Barrido de rutas por microservicio

Se recorren todas las operaciones del OpenAPI de cada servicio. Las que no
están en la lista explícita de públicas o internas deben responder `401` ante
cada token inválido.

| Servicio | Protegidas con JWT | Públicas | Internas (`X-Service-Token`) | Rechazo correcto |
|---|---:|---:|---:|---|
| MS1 · Autenticación | 13 | 4 (`/health`, `/health/db`, `register`, `login`) | 4 | 13 de 13 |
| MS2 · Vehículos y órdenes | 32 | 2 (`/health`, `/health/db`) | 1 | 32 de 32 |
| MS3 · Presupuestos e inventario | 39 | 2 (`/health`, `/health/db`) | 0 | 39 de 39 |
| MS4 · Evidencias | 4 | 3 (`/health`, `/health/db`, `/health/storage`) | 0 | 4 de 4 |
| **Total** | **88** | **11** | **5** | **88 de 88** |

Tokens inválidos usados en cada ruta:

| Caso | Qué simula |
|---|---|
| `sin_token` | Petición sin `Authorization` |
| `malformado` | Texto que no es un JWT |
| `firma_ajena` | JWT bien formado, firmado con otra clave |
| `expirado` | Firma correcta, `exp` en el pasado |
| `alg_none` | Ataque del algoritmo `none`, sin firma |
| `rol_inventado` | Firma correcta, rol que no existe (`superusuario`) |
| `sub_no_numerico` | Firma correcta, `sub` que no es un id de usuario |

Controles para que el barrido no dé falsos positivos:

- El mismo endpoint, con un token **válido** del servicio, ya no responde `401`.
- Si se desactiva la validación de MS2, la prueba detecta las 32 rutas como
  desprotegidas.
- Si alguien agrega una ruta sin protección, la prueba falla con su nombre. Si
  la ruta es pública a propósito, hay que agregarla a la lista `PUBLICAS`.
- Todo `401` trae `WWW-Authenticate: Bearer`.

## 3. Rutas internas

| Verificación | Resultado |
|---|---|
| Un JWT válido de Administrador **no abre** `POST /interno/eventos/ordenes/estado` (MS1) | `401` |
| Un JWT válido de Administrador **no abre** `GET /interno/notificaciones/ordenes/{id}/destinatario` (MS2) | `401` |
| La Gateway no publica ninguna de las 5 rutas `/interno/*` | `404` en las 5 |

Estas rutas solo aceptan el secreto de servicio (`X-Service-Token`), que es
distinto del secreto JWT.

## 4. Gateway

| Verificación | Resultado |
|---|---|
| La configuración de la Gateway no tiene ningún campo `JWT` ni `SECRET` | Sin secreto |
| Con un token forjado (`alg: none`), la Gateway consulta igual al microservicio | Consulta MS1, MS2, MS3 y MS4 |
| La cabecera `Authorization` llega al microservicio idéntica a la enviada | Idéntica en los 4 |
| El `401` que ve el cliente es el del microservicio, sin cambios | Igual al del servicio |

## 5. Observaciones

| ID | Severidad | Observación | Acción sugerida |
|---|---|---|---|
| J-01 | Media | MS1–MS4 comparten el mismo secreto HS256 en producción: quien lea el entorno de un servicio puede firmar tokens válidos para todos. Ya estaba registrado como T9 en `estudio-owasp-autenticacion-control-acceso.md` | Evaluar RS256: MS1 firma con la clave privada y MS2–MS4 validan con la pública. Decisión de equipo, fuera de esta tarea |
| J-02 | Baja | En las rutas internas de MS1 se valida el cuerpo antes que el secreto de servicio: una llamada sin credencial recibe `422`, no `401`, si el cuerpo es inválido | Mover la comprobación del secreto a una dependencia de FastAPI. Solo afecta rutas que la Gateway no publica |

No se encontraron rutas protegidas que acepten un token inválido.

## 6. Cómo ejecutar

```bash
cd backend
python -m pytest tests/test_validacion_jwt_independiente.py -v   # 110 passed
```
