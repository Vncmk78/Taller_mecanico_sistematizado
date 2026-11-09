# Datos de demostración: cargar, reiniciar y limpiar

Procedimiento con `scripts/datos_demo.py` para dejar las bases con datos
**controlados** (siempre los mismos) para pruebas integrales y demostraciones.
Funciona sobre el ambiente de despliegue (`despliegue-base-datos.md`) y también
sobre los ambientes de pruebas y demo final, porque reconoce sus marcas.

## Qué datos se cargan

| Paso | Origen | Resultado |
|---|---|---|
| 1 | `seed_usuarios_prueba.py` | 7 cuentas (`*@pruebas.cl`): cada rol y cada combinación; 4 perfiles Cliente en MS2 |
| 2 | `seed_datos_ms3.py` | 2 proveedores, 4 repuestos con stock (uno bajo umbral), umbral general 5 |
| 3 | `sembrar_demo_pruebas.py` (solo con `--gateway`) | vehículos `DEMO01..09` y órdenes 1–8 en cada estado, creados **por la API** |

| Patente | Estado final | Patente | Estado final |
|---|---|---|---|
| DEMO01 | 1 Recibido | DEMO06 | 7 Entregado |
| DEMO02 | 2 Asignado | DEMO07 | 8 Cancelado (Cliente) |
| DEMO03 | 3 Esperando aprobación | DEMO08 | 8 Cancelado (rechazo) |
| DEMO04 | 5 En reparación | DEMO09 | sin orden |
| DEMO05 | 6 Listo | | |

Cuentas (claves en `seed_usuarios_prueba.py`), por ejemplo
`administrador@pruebas.cl` / `AdminPrueba123!`, `cliente@pruebas.cl` /
`ClientePrueba123!`, `mecanico@pruebas.cl` / `MecanicoPrueba123!`.

Sobre bases recién limpias, los identificadores también se repiten (órdenes
1–8 con las mismas patentes): los casos de prueba pueden referirse a ellos.

## Protección

`datos_demo.py` **no escribe** si alguna de las cuatro bases no tiene en su
comentario una de estas marcas: `sgtm-despliegue-demo`, `sgtm-ambiente-pruebas`
o `sgtm-ambiente-demo-final`. Producción se crea con `sgtm-despliegue`, por lo
que ahí nunca se cargan cuentas con claves públicas ni se borra nada.
Además, `limpiar` y `reiniciar` exigen `--confirmar LIMPIAR-DEMO`.

Marcar una base existente como demostración (con su dueño o un administrador),
solo si se está seguro de que sus datos se pueden perder:

```sql
COMMENT ON DATABASE sgtm_ms1 IS 'sgtm-despliegue-demo';   -- repetir para ms2..ms4
```

## Procedimiento

Desde `backend/`, con la configuración del ambiente elegida:

```bash
export SGTM_ENV_FILE=despliegue/.env.despliegue     # PowerShell: $env:SGTM_ENV_FILE = "..."
python scripts/inicializar_bd.py                     # bases en heads (requisito)
```

### Cargar

```bash
python scripts/datos_demo.py cargar                                  # pasos 1 y 2 (solo bases)
python scripts/datos_demo.py cargar --gateway http://127.0.0.1:8000  # + escenarios DEMO (servicios levantados)
```

Es idempotente: si los datos ya están, no los duplica. Si existen solo algunos
escenarios DEMO, se detiene y pide reiniciar. Al terminar verifica y muestra
conteos.

### Ver el estado y verificar

```bash
python scripts/datos_demo.py estado                 # marca y conteos de cada base
python scripts/datos_demo.py verificar              # cuentas, perfiles, catálogo
python scripts/datos_demo.py verificar --escenarios # + DEMO01..09 en su estado esperado
```

`verificar` termina con 0 si todo está, 1 si falta algo (y lo lista).

### Limpiar

```bash
python scripts/datos_demo.py limpiar --confirmar LIMPIAR-DEMO
```

Elimina tablas, vistas, secuencias, tipos y funciones de la aplicación en las
cuatro bases (MS4 → MS1) y vuelve a aplicar las migraciones (MS1 → MS4). Quedan
solo el esquema y los datos de referencia que crean las migraciones (roles,
estados de orden, etc.). Conserva las extensiones `pg_trgm` y `unaccent`. No
borra las bases, los roles ni el volumen; cada base se limpia dentro de una
transacción (si algo falla, esa base queda como estaba).

Los archivos de evidencias en MinIO/S3 no se tocan; tras limpiar quedan sin
fila en MS4. Para borrarlos:

```bash
python scripts/limpiar_huerfanos_ms4.py --antiguedad-minutos 1 --eliminar
```

### Reiniciar (lo habitual antes de una demostración)

```bash
python scripts/datos_demo.py reiniciar --confirmar LIMPIAR-DEMO --gateway http://127.0.0.1:8000
```

Equivale a `limpiar` + `cargar` + `verificar`. Los servicios pueden seguir
levantados: no hace falta reiniciarlos.

## Cuándo usar qué

| Situación | Acción |
|---|---|
| Antes de una demostración o prueba integral | `reiniciar` |
| Después de probar a mano y querer volver al punto de partida | `reiniciar` |
| Dejar la base vacía para probar el registro desde cero | `limpiar` |
| Comprobar que la base de la demo está bien sin tocarla | `verificar --escenarios` |
| Destruir todo, incluso roles y volumen | `docker compose ... down --volumes` (ver `despliegue-base-datos.md`) |

## Códigos de salida

0 correcto · 1 datos incompletos (`verificar`) · 2 error, falta confirmación o
protección activa (no se escribió nada).
