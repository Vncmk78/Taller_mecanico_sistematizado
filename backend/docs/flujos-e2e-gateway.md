# Flujos end-to-end representativos a través de la Gateway

**Semana 8 — Ejecutar flujos end-to-end representativos a través de Gateway.**

Ejecución de los flujos de negocio que usan los clientes web y móvil, de
principio a fin, sobre la pila real de `integracion-web-gateway-bd.md`: Gateway
y cuatro microservicios con PostgreSQL en Neon (rama `preview/Bastian`) y S3
simulado. Cada paso se valida contra el contrato congelado **2.0.1**.

Script: `backend/scripts/flujos_e2e_gateway.py`.

---

## 1. Flujos

| Flujo | Qué recorre |
|---|---|
| F1 Acceso | Registro de un cliente nuevo, correo repetido (409), contraseña incorrecta (401), login y `me` de los tres roles |
| F0 Configuración | El Administrador consulta el cupo diario de ingresos y el máximo de órdenes por mecánico, y los fija si faltan |
| F2 Orden completa | Vehículo → orden → asignación → bitácora → evidencia de diagnóstico → presupuesto con repuesto → envío → el Cliente ve la orden, la evidencia (URL de descarga) y el presupuesto → aprueba → En reparación → bitácora con repuestos → Listo → entrega → historial `[1, 2, 3, 5, 6, 7]`, bitácora e historial del vehículo |
| F3 Rechazo | Presupuesto enviado y rechazado por el Cliente con motivo → la orden queda Cancelada (8) |
| F4 Cancelación | El Cliente solicita la cancelación (201), la repite (200), el Administrador la ve pendiente y la confirma → Cancelada (8) |
| F5 Seguridad | Sin token (401), token inválido (401), orden ajena para otro cliente y para un mecánico no asignado (404), Cliente cambiando estado (403), Mecánico creando orden (403), Cliente listando usuarios (403), body inválido (422) |

En cada paso se comprueban el estado HTTP esperado, el estado de la orden cuando
corresponde y que el cuerpo cumpla el esquema publicado para ese estado.

## 2. Resultado (3 de noviembre de 2026)

**74/74 pasos OK** en dos corridas, una con F2 y otra con F3, F4 y F5 (cada
corrida repite F1 y F0). Ninguna respuesta se apartó del contrato 2.0.1.

| Flujo | Pasos | Tiempo |
|---|---:|---:|
| F1 Acceso (×2) | 16/16 | 20,7 s |
| F0 Configuración (×2) | 4/4 | 4,3 s |
| F2 Orden completa | 27/27 | 62,6 s |
| F3 Rechazo | 11/11 | 33,1 s |
| F4 Cancelación | 6/6 | 13,7 s |
| F5 Seguridad | 10/10 | 7,7 s |

## 3. Hallazgos

### H-01 — Las coordinaciones MS3 → MS2 superan el timeout de 3 s contra Neon

Con los timeouts por defecto (`MS3_MS2_TIMEOUT_SEGUNDOS=3`,
`MS2_MS3_TIMEOUT_SEGUNDOS=3`), **3 de las 4 coordinaciones** respondieron `503`:

| Operación | Respuesta | Tiempo | Reintento indicado por el contrato |
|---|---|---:|---|
| Envío del presupuesto (F2) | 503 | 6,4 s | `POST /api/presupuestos/{id}/envio-inicial/aplicacion` → 200 (2,7 s) |
| Aprobación del Cliente (F2) | 503 | 10,0 s | `POST /api/presupuestos/decisiones/{id}/aplicacion` → 200 (2,5 s) |
| Envío del presupuesto (F3) | 200 | 6,5 s | — |
| Rechazo del Cliente (F3) | 503 | 8,5 s | `POST /api/presupuestos/decisiones/{id}/aplicacion` → 200 (3,0 s) |

La coordinación es una cadena (MS3 → MS2 → MS3 de vuelta, cada uno con varias
consultas a una base remota) y no alcanza a terminar en 3 s. **El diseño
resistió:** la decisión y el envío quedaron guardados, el reintento idempotente
los aplicó una sola vez y la orden terminó en el estado correcto (el historial
de F2 no tiene transiciones duplicadas).

Prueba de control: con los timeouts en 10 s, F2 pasó **35/35 sin ningún
reintento**. Ese envío tardó 6,9 s y la aprobación 10,3 s.

Implicancias:

- **Web e Integración IV** tienen que implementar el reintento ante el `503`
  de envío y decisión, como indica el contrato. No es un caso raro: con la base
  remota ocurre en la mayoría de los intentos.
- **Backend:** conviene medir estos tiempos en el despliegue real. Si se
  repiten, hay que subir `MS3_MS2_TIMEOUT_SEGUNDOS` y `MS2_MS3_TIMEOUT_SEGUNDOS`
  o reducir las consultas de la cadena. Ojo con el margen: la Gateway corta la
  lectura a los 15 s (`GATEWAY_TIMEOUT_READ_SECONDS`) y la aprobación ya tardó
  10,3 s con timeouts de 10 s. Bajar la latencia (base y servicios en la misma
  región, menos consultas por coordinación) es mejor que subir timeouts.

### H-02 — Configuración inicial obligatoria del taller

En una base recién migrada, `POST /api/ordenes` responde `409` («Configura el
máximo diario de ingresos físicos antes de recibir vehículos») hasta que un
Administrador fija `max_ingresos_diarios` y `max_ordenes_activas`. Es el
comportamiento esperado, pero tiene que formar parte de la puesta en marcha de
cada ambiente. F0 lo resuelve en las pruebas.

### H-03 — Cuentas multirol en pruebas de acceso

`cliente-administrador@pruebas.cl` ve todas las órdenes por su rol
Administrador. Para probar que un cliente no ve órdenes ajenas, F5 usa el
cliente recién registrado en F1, que solo tiene el rol Cliente.

## 4. Cómo repetirlo

Con la pila levantada como en `integracion-web-gateway-bd.md` §5:

```bash
cd backend
python scripts/flujos_e2e_gateway.py --salida e2e.md            # todos los flujos
python scripts/flujos_e2e_gateway.py --flujos F2 --salida f2.md  # uno solo
```

Sale con 0 si todos los pasos pasan. El reporte muestra cada paso con su
estado esperado, el obtenido, el tiempo y la cantidad de reintentos de
coordinación. Crea datos nuevos en cada corrida: usar solo contra bases de
desarrollo o integración.
