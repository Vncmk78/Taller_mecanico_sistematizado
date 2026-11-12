# Expiración de sesión durante el uso de la aplicación

**Tarea (Semana 10):** Implementar manejo de expiración de sesión durante el uso de la aplicación
**Alcance:** Frontend Web (React) — cierre proactivo de la sesión a partir del `exp` del JWT, aviso previo al usuario y coordinación con el manejo reactivo del `401`.
**Base:** rama `Gustavo` sincronizada con `Develop` (commit base `d26e226`).

## 1. Problema detectado

La sesión ya se cerraba cuando la API respondía `401`, pero la detección dependía de que
existiera una petición. Una pantalla sin tráfico (un formulario abierto, una tabla ya
cargada, una pestaña en segundo plano) podía seguir mostrando datos de una sesión vencida
hasta que el usuario intentara una acción y recibiera el error.

Además, el cierre era silencioso: el usuario volvía al login sin saber por qué había perdido
la sesión ni cuánto le quedaba.

| # | Síntoma | Causa |
|---|---|---|
| 1 | Pantalla sin peticiones sigue usando una sesión muerta | El cierre solo se disparaba con la respuesta `401` |
| 2 | Pérdida de contexto al volver al login | La redirección no conservaba la ruta pedida |
| 3 | El usuario no sabía que su sesión estaba por vencer | No existía aviso previo |
| 4 | Abrir la app con un token vencido mostraba "sesión expirada" | No se distinguía una sesión activa de un token ya vencido al arrancar |

## 2. Contrato del token asumido

Se usa el contrato que ya emite MS1 (`backend/shared/auth.py`), sin inventar endpoints:

| Claim | Uso en el cliente |
|---|---|
| `sub` | Identificador del usuario (no se usa para decidir la expiración) |
| `roles` | Se mantiene la autorización existente por roles |
| `exp` | Segundos epoch; fuente única para el aviso y el cierre proactivo |

- La vida del token por defecto es de **60 minutos** (`MS1_JWT_EXPIRE_MINUTES`).
- **No existe refresh ni revocación**: al vencer, la única salida es iniciar sesión de nuevo.
  Por eso el aviso no ofrece "renovar" ni "extender".
- El cliente **decodifica el payload sin verificar la firma**. No puede verificarla (no tiene
  la clave) y no debe intentarlo: la autorización real la sigue validando cada microservicio.
  Un token manipulado con un `exp` futuro no gana permisos, solo retrasa el cierre local
  hasta el `401`, que se maneja igual.

## 3. Comportamiento implementado

### 3.1 Ventana de aviso (`SESSION_WARNING_MS = 5 min`)

- Al entrar en los últimos 5 minutos, aparece un `Alert` de tono `warning` fijo abajo a la
  izquierda (`SessionExpiryBanner`).
- Mientras queden más de 60 segundos muestra la cuenta: «Tu sesión expirará en N minutos…».
- Con un minuto o menos no muestra cifra: «Tu sesión está por expirar…».
- El contador se recalcula cada 30 segundos (`SESSION_TICK_MS`); no se actualiza cada
  segundo porque no aporta precisión útil y encarece los renders.
- El banner no es descartable: es un aviso persistente mientras dure la ventana.

### 3.2 Cierre exacto al vencer

- Un temporizador programado con el tiempo restante cierra la sesión **en el instante del
  `exp`**, sin esperar al `401`.
- `AuthProvider` centraliza el cierre en `cerrarPorExpiracion(anunciarExpiracion)`:
  - guard `sesionCerrada` para que el temporizador y el interceptor `401` no naveguen dos veces;
  - navega a `/login` con la ruta de origen (incluido el query string) antes de limpiar;
  - marca el motivo en el store (`sesionExpirada`) y también en el state del router.

### 3.3 Token ya vencido al abrir la aplicación

- `restoreSession` lee el `exp` antes de llamar a `/auth/me`: si ya venció, descarta el token
  y finaliza la inicialización sin gastar la petición.
- El cierre se anuncia como `false`: no hubo una sesión en uso que expirara, así que el login
  no muestra el mensaje de expiración.

### 3.4 Pestañas en segundo plano

- Los navegadores frenan los temporizadores en pestañas inactivas. Al volver a primer plano
  (`visibilitychange`) se recalcula el tiempo restante; si el vencimiento ya pasó, se cierra
  la sesión de inmediato.

### 3.5 Por qué el motivo vive en el store

El `<Navigate>` de `ProtectedRoute` puede ejecutarse después de la redirección del provider y
sobrescribir el `state` del router (React Router 7 procesa las navegaciones como
transiciones). Para que el aviso no se pierda según quién redirija:

- `useAuthStore` expone `sesionExpirada` y `marcarSesionExpirada()`;
- `LoginPage` muestra el `Alert` si el state del router **o** el store lo indican;
- `login` y `logout` reinician el indicador.

También se conserva el query string en el `from` de `ProtectedRoute`.

## 4. Flujo resumido

```
Login correcto
  └─ login() guarda token y resetea sesionExpirada
       └─ useSessionExpiry lee exp
            ├─ faltan > 5 min ──────────────── sin aviso
            ├─ faltan <= 5 min ─────────────── banner con cuenta regresiva
            └─ restante = 0 ────────────────── cerrarPorExpiracion(true)
                                                 └─ /login?… con aviso

App abierta con token vencido
  └─ restoreSession descarta sin /auth/me
       └─ cerrarPorExpiracion(false) ──────── /login sin aviso

Cualquier petición con token inválido
  └─ interceptor 401 ─────────────────────── cerrarPorExpiracion(true)
```

## 5. Pruebas

| Archivo | Qué cubre |
|---|---|
| `src/infrastructure/config/sessionExpiry.test.ts` | Decodificación base64url, payload no válido, `exp` ausente/ inválido, estados y mensajes |
| `src/presentation/components/auth/useSessionExpiry.test.tsx` | Aviso a los 5 min, cuenta regresiva, cierre exacto, token vencido al montar, cambio de token, desmontaje y `visibilitychange` |
| `src/presentation/components/auth/SessionExpiryBanner.test.tsx` | Sin render fuera de la ventana, mensaje con minutos y mensaje sin cifra |
| `src/presentation/components/auth/AuthProvider.test.tsx` | Expiración durante el uso con `ProtectedRoute` (aviso, cierre, `from` con query) y JWT vencido al abrir |
| `src/infrastructure/stores/useAuthStore.test.ts` | `restoreSession` con JWT vigente consulta el perfil; con JWT vencido no lo consulta y limpia la sesión |

- **Resultado:** 132 archivos / 1148 pruebas en verde.
- **Build:** `tsc -b && vite build` correcto (sin errores de tipos).
- Las pruebas usan `vi.useFakeTimers()` + `vi.setSystemTime` para controlar el reloj y
  `src/test/jwt.ts` para fabricar tokens decodificables con `sub`, `roles` y `exp`.

## 6. Limitaciones y decisiones

1. **Sin renovación automática:** el backend no tiene refresh ni endpoint de extensión; el
   aviso solo ayuda a guardar el trabajo y volver a entrar.
2. **El reloj del cliente manda:** si el equipo tiene la hora muy desfasada, el cierre local
   puede adelantarse o atrasarse. El `401` sigue siendo la red de seguridad.
3. **Tokens opacos:** si un token no es un JWT de tres partes (por ejemplo, en pruebas o
   integraciones futuras), `decodeJwtPayload` devuelve `null` y se mantiene únicamente el
   manejo reactivo del `401`.
4. **No se valida la firma en el cliente:** sería imposible sin la clave y no aporta
   seguridad; la validación real ocurre en cada servicio.
5. **No se agregó un "cerrar sesión ahora"** al banner: no forma parte del alcance y el menú
   de usuario ya permite cerrar sesión.

## 7. Archivos principales

| Archivo | Cambio |
|---|---|
| `src/infrastructure/config/sessionExpiry.ts` | Nuevo: decodificación de JWT, `exp`, estados, minutos y mensajes |
| `src/presentation/components/auth/useSessionExpiry.ts` | Nuevo: temporizadores de aviso y cierre, `visibilitychange` |
| `src/presentation/components/auth/SessionExpiryBanner.tsx` | Nuevo: banner de advertencia |
| `src/presentation/components/auth/AuthProvider.tsx` | Cierre coordinado 401/temporizador, guard y montaje del banner |
| `src/infrastructure/stores/useAuthStore.ts` | `restoreSession` descarta JWT vencido; `sesionExpirada` en el store |
| `src/presentation/pages/auth/LoginPage.tsx` | Aviso de sesión expirada también desde el store |
| `src/presentation/components/auth/ProtectedRoute.tsx` | Conserva el query string en `from` |
| `src/test/jwt.ts` | Nuevo helper de pruebas para fabricar JWTs |

- **Fecha de registro:** 2026-11-12
- **Responsable:** Gustavo Rosa (Frontend Web React)
