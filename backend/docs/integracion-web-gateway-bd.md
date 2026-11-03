# Integración Web → Gateway → Microservicios → ORM/BD

**Semana 8 — Ejecutar integración Web → Gateway → Microservicios → ORM/BD.**

Ejecución de la cadena completa del SGTM con piezas reales en cada capa: el
frontend en un navegador, la Gateway, los cuatro microservicios y sus bases
PostgreSQL en Neon. Cada capa se comprueba contra la siguiente.

| Pieza | Herramienta |
|---|---|
| Capas 1 a 5 (BD, MS, Gateway, Web por HTTP, persistencia) | `backend/scripts/integracion_capas.py` |
| Capa Web en navegador real (login y vistas por rol) | `frontend/scripts/integracion-web.mjs` (Playwright) |
| Flujos de negocio completos sobre esta misma pila | `docs/flujos-e2e-gateway.md` |

---

## 1. Entorno de la ejecución (3 de noviembre de 2026)

| Capa | Qué se usó |
|---|---|
| Web | `frontend/` con `vite` (puerto 5173, proxy `/api` → Gateway) y Chromium headless |
| Gateway | `gateway.main:app` con Uvicorn (puerto 8000), contrato **2.0.1** |
| Microservicios | MS1 a MS4 con Uvicorn (puertos 8001 a 8004), código de la rama `Bastian` |
| ORM/BD | Neon, proyecto `taller-mecanico`, rama **`preview/Bastian`** (copia propia de `production`), bases `taller_ms1` a `taller_ms4`, PostgreSQL 18 |
| Archivos de MS4 | S3 simulado (`moto_server`, bucket `evidencias`) en lugar de MinIO |

**No se tocó la rama `production` de Neon.** El plan gratuito no permite más
ramas, así que se usó la rama de vista previa de Bastian, que estaba archivada y
atrasada. Antes de la ejecución:

1. `python scripts/migrar.py` llevó las cuatro bases a los heads del checkout:
   MS1 `0003` → `0005_integracion_ms1`, MS2 `0007` → `0012_integracion_ms2`,
   MS3 `0006` → `0008_ms3` y MS4 sin versión → `0001_ms4`.
2. `python scripts/seed_usuarios_prueba.py` creó las 7 cuentas de prueba y sus perfiles Cliente.
3. `python scripts/seed_datos_ms3.py` cargó el catálogo mínimo de MS3.

## 2. Resultado por capas — `integracion_capas.py`

**30/30 comprobaciones OK.**

| Capa | Comprobación | Resultado | Detalle |
|---|---|---|---|
| BD | Migraciones MS1 / MS2 / MS3 / MS4 | OK ×4 | Las cuatro bases en los heads del checkout |
| MS | `/health` de MS1 a MS4 | OK ×4 | 13–14 ms |
| MS | `/health/db` de MS1 a MS4 (ORM → Neon) | OK ×4 | 468–513 ms |
| Gateway | Ve a `ms1_auth`, `ms2_taller`, `ms3_presupuestos`, `ms4_evidencias` | OK ×4 | 461–1348 ms |
| Gateway | Publica un contrato congelado | OK | versión 2.0.1 |
| Web | Sirve la aplicación | OK | 200 |
| Web | Su `/api` llega a la Gateway | OK | 200 |
| Web | La Gateway acepta el CORS del origen web | OK | `Allow-Origin: http://localhost:5173` |
| Persistencia | MS1: el usuario del token existe en `taller_ms1.usuario` | OK | |
| Persistencia | Gateway → MS2: crear vehículo / está en `taller_ms2.vehiculo` con los mismos datos | OK ×2 | |
| Persistencia | Gateway → MS2: crear orden | OK | |
| Persistencia | Gateway → MS2 → MS1: asignar mecánico (MS2 valida el rol en MS1, contrato 2.0.0) | OK | |
| Persistencia | MS2: `orden_trabajo` queda en estado 2 con el mecánico; `historial_estado` registra 1 → 2 | OK ×2 | |
| Persistencia | Gateway → MS4 → MS2: subir evidencia | OK | |
| Persistencia | MS4: metadato en `taller_ms4.evidencia` y archivo en S3 con el mismo tamaño | OK ×2 | 534 bytes |

Las lecturas de comprobación en la base se hacen con `SET TRANSACTION READ ONLY`.

## 3. Resultado de la capa Web en navegador — `integracion-web.mjs`

**3/3 roles OK.** Login desde `/login`, redirección al portal del rol, clic en el
menú y carga de la vista con datos reales de la API:

| Rol | Login | Portal | Vista con datos | Llamadas `/api` | Resultado |
|---|---|---|---|---:|---|
| cliente | 200 | `/client` | `GET /api/vehiculos` 200 | 2 | OK |
| mecanico | 200 | `/mechanic` | `GET /api/ordenes` 200 | 3 | OK |
| administrador | 200 | `/admin` | `GET /api/ordenes` 200 | 4 | OK |

Todas las llamadas que hizo el navegador a `/api` respondieron 2xx.

## 4. Hallazgos

- **H-01 — Fechas con zona horaria en PostgreSQL.** Contra Neon, `creado_en` y
  `fecha_hora` llegan como `2026-09-26T22:04:51.572957Z` (UTC con `Z`). Esto
  cierra la observación O-01 de `diferencias-contrato-consumo-real.md`: la falta
  de zona horaria solo ocurre con SQLite en las pruebas.
- **H-02 — Latencia de la base remota.** La primera conexión de cada servicio a
  Neon tarda entre 3,4 y 4,9 s; después, `/health/db` tarda alrededor de 0,5 s.
  Influye en las coordinaciones entre servicios (ver H-01 de `flujos-e2e-gateway.md`).
- **H-03 — Recargar `/client/vehiculos` no es una prueba válida del portal
  Cliente.** Abrirla con navegación completa (recarga) no llegó a pedir
  `/api/vehiculos`; navegando por el menú, como lo hace el usuario, sí. El script
  navega por el menú. Si se quiere que esa URL funcione al recargarla, hay que
  revisarlo en el frontend.
- **H-04 — Rama de Neon.** La rama `preview/Bastian` quedó migrada y con datos de
  prueba (vehículos `INT…` y `E2E…`, órdenes y evidencias). Las imágenes de prueba
  quedaron en el S3 simulado y no en MinIO, así que una descarga real de esas
  evidencias fallará fuera de esta ejecución.

## 5. Cómo repetirla

Desde `backend/`, con las variables `MS1..MS4_DATABASE_URL` apuntando a una base
de **desarrollo o integración** (nunca producción) y la misma
`MS1..MS4_JWT_SECRET_KEY` en los cuatro servicios:

```bash
python scripts/migrar.py
python scripts/seed_usuarios_prueba.py
python scripts/seed_datos_ms3.py
# levantar MS1..MS4 (8001-8004), la Gateway (8000), MinIO o un S3 compatible,
# y el frontend: cd ../frontend && npm run dev
python scripts/integracion_capas.py --salida integracion.md

cd ../frontend
npm i --no-save playwright && npx playwright install chromium
WEB_URL=http://localhost:5173 node scripts/integracion-web.mjs capturas/
```

Las dos herramientas salen con código 0 si todo pasa. Crean datos nuevos en
cada corrida.
