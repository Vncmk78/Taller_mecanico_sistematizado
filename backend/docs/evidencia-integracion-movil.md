# Evidencia de integración con el equipo móvil (Integra IV)

**Semana 9 — Registrar evidencia de integración con el equipo móvil.**

Registro de cada sesión de prueba entre la app de Integra IV y la Gateway. Sirve
de evidencia para el curso y como fuente de las correcciones del backend: toda
incompatibilidad que aparezca aquí se registra con un ID nuevo en
[`diferencias-contrato-consumo-real.md`](diferencias-contrato-consumo-real.md)
(D-04, …) o en [`contratos-integracion-iv.md`](contratos-integracion-iv.md)
(B-05, …), con su prueba de regresión.

- Operaciones que usa la app: [`contratos-integracion-iv.md`](contratos-integracion-iv.md) §2
- Configuración y reglas para la app: [`estudio-consumo-api-movil-redes-externas.md`](estudio-consumo-api-movil-redes-externas.md) §4

---

## 1. Estado

| | |
|---|---|
| Stack de la app | Sin confirmar (Flutter o React Native) |
| Build de la app disponible | No |
| Entorno acordado para las pruebas | Propuesto: `https://tallerconect.vercel.app` |
| Cuentas de prueba entregadas al equipo móvil | Pendiente |
| Sesiones de prueba realizadas | 1 (preparación, solo backend) |

## 2. Sesiones

### S-00 — Preparación del backend (2026-11-03)

| | |
|---|---|
| Participantes | Bastián Liempi (backend) |
| Entorno | Gateway local (`0.0.0.0:8000`) y producción en Vercel |
| Cliente | `curl` y pruebas automáticas; simulan un cliente nativo (sin `Origin`) y un build web (con `Origin`) |
| Objetivo | Dejar la Gateway lista para que la app la consuma desde fuera de la red del backend |

Resultado:

| Verificación | Resultado | Evidencia |
|---|---|---|
| Contratos de las 25 operaciones móviles | 179 comprobaciones ok | `pytest tests/test_contratos_integracion_iv.py` |
| Respuestas reales contra el contrato | 29 de 29 ok | `pytest tests/test_contrato_consumo_real.py` |
| Cabeceras para clientes móviles y externos | 4 de 4 ok (2 fallaban antes de corregir H-01) | `pytest tests/test_cabeceras_cliente_movil.py` |
| Regresión de incompatibilidades corregidas (B-01 a B-04, D-01, D-02, O-01) | 18 de 18 ok | `pytest tests/test_regresion_incompatibilidades.py` |
| Producción accesible desde red externa | `200` en `/api/health`; los 4 servicios `ok` tras el arranque en frío | Estudio §2.2 |
| Incompatibilidades corregidas | H-01 (`Retry-After` no expuesto por CORS) y O-01 (matriz de roles desactualizada) | Estudio §3 |
| Pendientes para el equipo móvil | Confirmar stack y si habrá build web (H-02); recibir cuentas de prueba | — |

### Plantilla para las próximas sesiones

Copiar este bloque por sesión (S-01, S-02, …):

```markdown
### S-0N — <tema> (<AAAA-MM-DD>)

| | |
|---|---|
| Participantes | <backend> / <equipo móvil> |
| Entorno | <Vercel / local + IP> |
| App | <Flutter / React Native>, build <versión o commit>, <emulador / teléfono, Android/iOS + versión> |
| Red | <Wi-Fi del campus / datos móviles / misma LAN> |
| Cuentas usadas | <cliente de prueba, mecánico de prueba> (nunca anotar contraseñas) |

| # | Flujo | Operación | Rol | Esperado | Obtenido | `X-Request-ID` | ¿OK? |
|---|---|---|---|---|---|---|---|
| 1 | Acceso | `POST /api/auth/login` | Cliente | `200` + token | | | |

Incompatibilidades encontradas: <ID nuevo (D-0N / B-0N) o «ninguna»>
Capturas: `docs/evidencias-movil/S-0N/` (pantalla de la app + respuesta)
Acuerdos y próximos pasos: <…>
```

## 3. Qué evidencia guardar en cada sesión

1. La tabla de operaciones con el estado HTTP y el `X-Request-ID` de cada
   llamada. Con el id se busca la petición en los logs de la Gateway y del
   microservicio.
2. Una captura de la app por flujo (pantalla del resultado o del error que ve el
   usuario).
3. Para cada fallo: método, ruta, body enviado (sin contraseñas ni tokens) y
   body recibido.
4. Versión del contrato contra la que se probó (`info.version` de
   `/openapi.json`).

## 4. Cobertura de flujos

Se marca al terminar cada sesión.

| Flujo | Operaciones | Cliente | Mecánico | Sesión |
|---|---:|:-:|:-:|---|
| Acceso | 3 | ☐ | ☐ | |
| Vehículos | 5 | ☐ | ☐ | |
| Órdenes | 4 | ☐ | ☐ | |
| Trabajo del mecánico | 3 | — | ☐ | |
| Evidencias | 4 | ☐ | ☐ | |
| Presupuestos | 6 | ☐ | — | |
