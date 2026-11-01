# Smoke tests de todos los prefijos de la Gateway

Semana 7 · Bastián Liempi · Taller de Integración II (Grupo 10)

Un *smoke test* responde una sola pregunta: **¿cada prefijo de la Gateway
llega a su microservicio y vuelve con el formato esperado?** No prueba reglas
de negocio (eso lo cubre la suite de pytest); prueba que el cableado completo
—Gateway, enrutamiento, JWT y los cuatro servicios— responde.

## Qué se ejecuta

El mismo código sirve para los dos modos:

| Modo | Cómo | Cuándo |
|---|---|---|
| En proceso (CI) | `tests/test_gateway_smoke_prefijos.py` | En cada `pytest`: Gateway real + MS1..MS4 reales en memoria (SQLite), sin red ni Docker |
| Contra un entorno levantado | `scripts/smoke_prefijos_gateway.py --gateway <url>` | Después de levantar todo en local o de desplegar en Vercel |

Los prefijos salen del catálogo `gateway/rutas.py` (`MICROSERVICIOS`), así que
un prefijo nuevo entra al smoke sin tocar el script (la prueba
`test_representativos_cubren_todos_los_prefijos_publicados` obliga a definir su
endpoint representativo).

| # | Comprobación | Esperado |
|---|---|---|
| 1 | `GET /api/health` | `200` |
| 2 | `GET /api/health/servicios` | `200` y los cuatro en `ok` |
| 3 | `GET /api/health/servicios/{servicio}` (×4) | `200` con `estado: ok` (OMITIDO si la Gateway desplegada es anterior a la Semana 7) |
| 4 | Endpoint protegido de cada prefijo publicado, sin token (×8) | `401` **del microservicio** (`{"detail": ...}`), nunca un error de la Gateway |
| 5 | Cada alias heredado (×6) | `404` del microservicio |
| 6 | `GET /api/prefijo-inexistente` | `404 RUTA_NO_ENCONTRADA` de la Gateway |
| 7 | Todas | Devuelven el mismo `X-Request-ID` enviado |
| 8 | Opcional, con `--email/--password`: login y cada prefijo con token (×8) | `200/403/404/422` del microservicio, nunca `502/503/504` |

Endpoints representativos (solo `GET`, sin efectos): `auth` → `/auth/me`,
`vehiculos` → `/vehiculos`, `ordenes` → `/ordenes`, `presupuestos` →
`/presupuestos`, `repuestos` → `/repuestos`, `proveedores` → `/proveedores`,
`inventario` → `/inventario/alertas`, `evidencias` → `/evidencias?orden_id=1`.

Un resultado se considera generado por la Gateway (y no por el microservicio)
cuando el cuerpo trae `error.codigo` del catálogo de la Gateway
(`RUTA_NO_ENCONTRADA`, `MICROSERVICIO_INALCANZABLE`, `TIEMPO_AGOTADO`,
`GATEWAY_SATURADA`, ...).

## Cómo ejecutarlos

Desde `backend/`:

```bash
# En proceso (también corre con toda la suite)
python -m pytest tests/test_gateway_smoke_prefijos.py -v

# Contra el entorno local (Gateway en :8000 y MS1..MS4 en :8001..:8004)
python scripts/smoke_prefijos_gateway.py

# Contra producción, con login de un usuario de prueba y resultados en JSON
python scripts/smoke_prefijos_gateway.py --gateway https://tallerconect.vercel.app \
    --email cliente@pruebas.cl --password '<clave>' --json smoke.json
```

El script sale con código `0` si todo lo aplicable pasa y `1` si algo falla.

## Resultados

### En proceso (suite de pytest)

`tests/test_gateway_smoke_prefijos.py`: **4/4 pruebas pasan**.

- Sin token: 21 comprobaciones, 21 pasan (incluido el diagnóstico de los
  cuatro servicios).
- Con token (cliente registrado vía Gateway): 30 comprobaciones, 30 pasan.
  `GET /api/auth/me` → `200`; `GET /api/repuestos` → `403` de MS3 (un Cliente
  no administra el catálogo).
- Con MS3 apagado, el smoke reporta como FALLA exactamente lo que depende de
  MS3: `502 MICROSERVICIO_INALCANZABLE` en sus prefijos y `503` en la salud
  agregada y en su diagnóstico.

### Producción (`https://tallerconect.vercel.app`, 31-10-2026)

Despliegue anterior a la Semana 7 (sin el diagnóstico por servicio).

| Ejecución | Pasan | Fallan | Omitidos | Observación |
|---|---|---|---|---|
| 1 (22:59 hora de Chile) | 16 | 1 | 4 | `GET /api/health/servicios` → `503`: arranque en frío |
| 2 (23:01 hora de Chile) | 17 | 0 | 4 | Todo responde |

Detalle de la ejecución 2: `/api/health` `200`; `/api/health/servicios` `200`
con los cuatro en `ok`; los ocho prefijos publicados sin token → `401` del
microservicio; los seis alias → `404` del microservicio; prefijo inexistente →
`404 RUTA_NO_ENCONTRADA`; `X-Request-ID` devuelto en todas. Los cuatro
diagnósticos quedaron OMITIDOS porque ese despliegue todavía no los tiene.

## Hallazgos

1. **Arranque en frío vs. timeout del health check.** La primera llamada a
   `/api/health/servicios` en producción respondió `503`; un minuto después,
   `200` con latencias de 80–130 ms. Las funciones de Vercel y las bases de
   Neon se suspenden sin tráfico y la primera consulta supera el timeout de 2 s
   (`GATEWAY_HEALTH_TIMEOUT_SECONDS`). Recomendación: en Vercel, definir
   `GATEWAY_HEALTH_TIMEOUT_SECONDS=5` y no alertar por un único `503` del
   health check.
2. **Almacenamiento de MS4 en producción.** `GET /ms4/health/storage` responde
   `503` ("El almacenamiento de evidencias no está disponible"): el despliegue
   no tiene MinIO/S3 configurado. Cuando la Gateway de la Semana 7 se
   despliegue, `GET /api/health/servicios/ms4_evidencias` lo mostrará como
   `degradado` (proceso y base `ok`, almacenamiento `error`), que es justo lo
   que el diagnóstico debe hacer visible. La subida de evidencias en producción
   depende de configurar `MS4_S3_*`.
3. **Alias heredados.** Los seis alias (`vehiculo`, `orden`, `clientes`,
   `mecanicos`, `presupuesto`, `evidencia`) llegan a su servicio pero ninguno
   publica rutas bajo ellos (responden `404` del microservicio). Siguen como
   deuda registrada en `docs/contratos-api-gateway.md`.
