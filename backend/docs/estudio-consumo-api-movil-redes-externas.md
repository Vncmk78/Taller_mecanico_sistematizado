# Estudio: diagnóstico de consumo de la API desde apps móviles y redes externas

**Semana 9 — Estudiar diagnóstico de consumo API desde aplicaciones móviles y redes externas.**

La app de Taller de Integración IV consume la misma Gateway que el frontend web,
pero desde otro lugar: un teléfono en Wi-Fi o datos móviles, fuera de la red
donde corren los servicios. Este estudio revisa qué cambia en ese escenario,
qué se midió y qué debe configurar cada lado.

- Contratos que usa la app: [`contratos-integracion-iv.md`](contratos-integracion-iv.md)
- Diferencias contrato vs consumo real: [`diferencias-contrato-consumo-real.md`](diferencias-contrato-consumo-real.md)
- CORS y transporte: [`estudio-seguridad-transporte.md`](estudio-seguridad-transporte.md)
- Direcciones y variables: [`variables-entorno-y-direcciones.md`](variables-entorno-y-direcciones.md)
- Regresión de esta tarea: `tests/test_cabeceras_cliente_movil.py`

---

## 1. Qué cambia respecto del frontend web

| Aspecto | Frontend web | App móvil nativa | Build web de la app (Expo Web, Ionic/Capacitor, WebView) |
|---|---|---|---|
| Envía `Origin` | Sí | **No** | Sí |
| Pasa por CORS | Sí | **No** | Sí |
| Puede leer cualquier cabecera de respuesta | Solo las expuestas | Sí, todas | Solo las expuestas |
| Red | Misma máquina o Vercel | Wi-Fi o datos móviles, NAT, latencia variable | Igual que la app |
| Acepta HTTP sin TLS | Sí en local | Android 9+ y iOS (ATS) lo **bloquean** por defecto | Depende del contenedor |

Integra IV todavía no define si la app será Flutter o React Native
(`estudio-pruebas-contrato-consumidores.md`). El estudio cubre ambos casos: lo
que importa es si la app corre **nativa** o como **build web**.

## 2. Diagnóstico realizado (2026-11-03)

### 2.1 Gateway local expuesta a la red

Gateway levantada con `uvicorn gateway.main:app --host 0.0.0.0 --port 8000` y
consultada desde otra interfaz (IP de red `172.16.10.3`), sin microservicios.

| Prueba | Resultado |
|---|---|
| `GET /api/health` sin `Origin` (cliente nativo) | `200` |
| Preflight desde `http://localhost:5173` (web) | `200`, origen permitido |
| Preflight desde `https://<preview>.vercel.app` | `200`, permitido por la regex |
| Preflight desde `http://localhost:8081` (Expo Web) | **`400`** |
| Preflight desde `http://localhost:19006` (Expo Web, versiones antiguas) | **`400`** |
| Preflight desde `capacitor://localhost` y `http://localhost` (Ionic/Capacitor) | **`400`** |
| `GET /api/ordenes` con el microservicio caído | `502` JSON con `request_id`, `Retry-After: 5` |
| `/openapi.json` | versión `2.1.0`, sin `servers` (la app debe configurar su URL base) |

### 2.2 Producción (`https://tallerconect.vercel.app`)

| Prueba | Resultado |
|---|---|
| `http://…/api/health` | `308` → HTTPS |
| `GET /api/health` (primera llamada tras inactividad) | `200` en **3,4 s** |
| `GET /api/health/servicios` (primera llamada) | **`503` degradado**: MS1 ok (1250 ms), MS2, MS3 y MS4 `tiempo_agotado` |
| `GET /api/health/servicios` (siguientes 3 llamadas) | `200`, los cuatro `ok` entre 99 y 146 ms; total 0,6–0,8 s |
| `GET /api/auth/me` sin token | `401`, `WWW-Authenticate: Bearer`, `X-Request-ID`, HSTS de 2 años |
| Preflight desde `http://localhost:8081` | **`400`** |
| `/openapi.json` | `200`, 489 KB |

## 3. Hallazgos

| ID | Severidad | Hallazgo | Afecta a | Estado |
|---|---|---|---|---|
| **H-01** | Media | CORS solo exponía `X-Request-ID`. La Gateway envía `Retry-After` en el `429` del login y en sus `502/503/504`, pero `fetch()` en navegador la ocultaba | Frontend web y build web de la app | **Corregido**: `expose_headers=["X-Request-ID", "Retry-After"]` en `gateway/main.py` |
| **H-02** | Media | Los orígenes de un build web de la app (`localhost:8081`, `localhost:19006`, `capacitor://localhost`, `http://localhost`) reciben `400` en el preflight | Solo si la app corre como build web o WebView | Configuración: agregar el origen en `GATEWAY_CORS_ORIGINS` cuando el equipo móvil confirme cuál usa. **No** usar `*`: con `allow_credentials=True` no está permitido |
| **H-03** | Media | Arranque en frío en Vercel: la primera llamada tras inactividad tarda segundos y MS2–MS4 no responden dentro de 2 s | App en datos móviles, primera pantalla | Lado app: mostrar «cargando», reintentar solo operaciones idempotentes ante `502/503/504` respetando `Retry-After` |
| **H-04** | Alta si no se configura | Las URLs de descarga de evidencias se firman con `MS4_S3_PUBLIC_ENDPOINT`; si está vacío se firma con `S3_ENDPOINT` (`http://localhost:9000`), que un teléfono no alcanza. La firma incluye el Host, así que no se puede reescribir en la app | Ver y descargar evidencias | Configuración: en cualquier entorno probado desde un teléfono, `MS4_S3_PUBLIC_ENDPOINT` debe ser una URL alcanzable desde fuera (HTTPS en producción). Pendiente de confirmar en Vercel |
| **H-05** | Media | En local, `uvicorn` sin `--host` escucha solo en `127.0.0.1`: un teléfono en la misma Wi-Fi no llega. Además Android 9+ e iOS bloquean HTTP sin TLS | Pruebas locales con teléfono físico | Ver §4 |
| **H-06** | Baja | El JWT dura 60 min (`MS1_JWT_EXPIRE_MINUTES`) y no hay refresh token | Sesiones largas en la app | Lado app: ante `401` borrar el token y volver al login (O-03 de `contratos-integracion-iv.md`). Un refresh token es decisión de producto |
| **H-07** | Baja | `/openapi.json` pesa 489 KB y no declara `servers` | Generación de cliente | Generar el cliente en tiempo de build, nunca descargarlo en el teléfono; la URL base va en la configuración de la app |

Sin hallazgos en: redirección HTTP→HTTPS, HSTS, `WWW-Authenticate` en el `401`,
`X-Request-ID` en todas las respuestas, formato JSON de los errores propios
(`detail` + `error.codigo/estado/ruta/request_id`) y acceso de un cliente sin
`Origin`.

## 4. Configuración para probar con el equipo móvil

| Escenario | URL base de la app | Qué hacer en el backend |
|---|---|---|
| Emulador Android | `http://10.0.2.2:8000` | Gateway local normal. Permitir HTTP solo en el build de depuración (`usesCleartextTraffic` / `network_security_config`) |
| Simulador iOS | `http://localhost:8000` | Excepción ATS solo para depuración |
| Teléfono físico, misma Wi-Fi | `http://<IP-LAN-del-PC>:8000` | `uvicorn gateway.main:app --host 0.0.0.0 --port 8000`, abrir el puerto 8000 en el firewall de Windows y `MS4_S3_PUBLIC_ENDPOINT=http://<IP-LAN>:9000` |
| Teléfono en datos móviles o red externa | `https://tallerconect.vercel.app` | Nada nuevo. Es la opción recomendada para las pruebas reales: HTTPS, sin excepciones de TLS |
| Build web de la app | La que corresponda | Agregar su origen a `GATEWAY_CORS_ORIGINS` (H-02) |

Reglas para la app, derivadas del contrato:

1. Enviar `Authorization: Bearer <token>` en todo menos `register` y `login`.
2. Ante `401`: borrar el token y volver al login.
3. Ante `429` (login) y `502/503/504`: esperar lo que diga `Retry-After`.
   Reintentar automáticamente solo `GET`. Los `POST` y `PATCH` no se repiten
   solos, salvo la aplicación de una decisión de presupuesto
   (`503` con `decision_registrada=true`, ver `contratos-integracion-iv.md`).
4. Mostrar `detail` al usuario y guardar `X-Request-ID` (o `error.request_id`)
   en el log de la app. Con ese id el backend encuentra la petición en sus logs
   (`estudio-correlacion-logs.md`). La app puede enviar su propio
   `X-Request-ID` si cumple `^[A-Za-z0-9-]{1,128}$`.
5. Evidencias: comprimir la foto antes de subirla. La Gateway corta en 12 MiB
   (`413`) y el timeout de subida es 60 s, poco margen en datos móviles.
6. No guardar la URL de descarga: vence a los 300 s (`expira_en`). Pedir una
   nueva cada vez que se va a mostrar el archivo.

## 5. Qué no se pudo verificar

| Punto | Motivo |
|---|---|
| Consumo desde la app real | El equipo de Integra IV todavía no entrega build ni código |
| Datos móviles reales (latencia, NAT de operador) | Requiere el teléfono del equipo móvil; se mide en las pruebas reales de integración |
| `MS4_S3_PUBLIC_ENDPOINT` en Vercel | Requiere acceso a las variables del proyecto; confirmarlo antes de probar evidencias (H-04) |
| Flujos autenticados en producción | Requiere cuentas de prueba acordadas con el equipo móvil |

Lo que se mida en esas pruebas se registra en
[`evidencia-integracion-movil.md`](evidencia-integracion-movil.md).

## 6. Cómo reproducir

```bash
# Regresión de cabeceras para clientes móviles y externos
cd backend
python -m pytest tests/test_cabeceras_cliente_movil.py -v   # 4 passed

# Gateway local accesible desde la red
uvicorn gateway.main:app --host 0.0.0.0 --port 8000
curl -i http://<IP>:8000/api/health
curl -i -X OPTIONS http://<IP>:8000/api/ordenes \
  -H "Origin: http://localhost:8081" -H "Access-Control-Request-Method: GET"

# Producción
curl -i https://tallerconect.vercel.app/api/health/servicios
```
