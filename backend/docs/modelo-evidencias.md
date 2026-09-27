# Modelo de metadatos de evidencias — MS4

Semana 3 · Bastián Liempi · Taller de Integración II (Grupo 10)

Define el modelo `Evidencia` (metadatos) de fotos y videos de orden. **Aquí no
hay endpoints ni migraciones**: solo el modelo, sus enums y las reglas de
visibilidad que usarán las consultas futuras.

El archivo vive en MinIO/S3; en PostgreSQL solo van los **metadatos**. Fuentes:
lámina 04-mer-erd (recuadro "BD MS4"), Sistematización final §4.3, §4.4, §8, y
la tarea *Estudiar MinIO/S3, multipart y SDK*.

## Referencias lógicas a otros servicios (§8)

En MS4 no existen claves foráneas físicas hacia otras bases. Las PKs de los
tres servicios son **enteros seriales** (verificado contra los modelos):

| Columna | Referencia | PK origen |
|---|---|---|
| `orden_id` | Orden de Trabajo (MS2) | `orden_trabajo.orden_id` → `Integer` |
| `presupuesto_id` | Presupuesto (MS3) | `presupuesto.presupuesto_id` → `Integer` |
| `autor_usuario_id` | Usuario (MS1) | `usuario.usuario_id` → `Integer` |
| `eliminada_por_usuario_id` | Usuario (MS1) | `usuario.usuario_id` → `Integer` |

Se guardan como enteros sueltos (marcados REF en el MER) y la integridad se
resuelve por contrato de API, nunca con `ForeignKey`.

## Tabla `evidencia`

| Campo | Tipo | Nulo | Origen | Nota |
|---|---|---|---|---|
| `evidencia_id` | UUID PK | no | MER | Se genera en la app (`uuid4`) |
| `orden_id` | Integer | no | MER | Referencia lógica a MS2, sin FK |
| `presupuesto_id` | Integer | sí | estudio | Solo si contexto = presupuesto |
| `autor_usuario_id` | Integer | no | MER | Referencia lógica a MS1 |
| `contexto` | `str(20)` | no | MER | `diagnostico` / `presupuesto` / `reparacion` / `resultado_final` |
| `tipo_archivo` | `str(10)` | no | MER | `foto` / `video` |
| `visible_cliente` | Boolean | no | MER | Valor por defecto según contexto (ver reglas) |
| `estado` | `str(12)` | no | estudio | `pendiente` / `confirmada` / `anulada` (flujo C) |
| `clave_objeto` | `str(512)` UNIQUE | no | MER | Clave del objeto en MinIO |
| `nombre_original` | `str(255)` | no | estudio | Solo para mostrarlo, nunca para rutas |
| `content_type` | `str(100)` | no | estudio | |
| `tamano_bytes` | `BigInteger` | no | estudio | |
| `sha256` | `CHAR(64)` | sí | estudio | Se llena al confirmar |
| `request_id` | `str(64)` | sí | estudio | Trazabilidad con el Gateway |
| `creada_en` | `timestamptz` | no | MER | `server_default = now()` |
| `confirmada_en` | `timestamptz` | sí | estudio | |
| `eliminada_en` | `timestamptz` | sí | MER | Eliminación lógica |
| `eliminada_por_usuario_id` | Integer | sí | nuevo | Auditoría |

Los enums viven como `StrEnum` en `models/evidencia.py`
(`ContextoEvidencia`, `TipoArchivo`, `EstadoEvidencia`) y se guardan como
strings validados con CHECK, igual que las restricciones por catálogo de MS2.

## Constraints (implementadas como CHECK en `__table_args__`)

1. `contexto` dentro de los 4 valores permitidos.
2. `tipo_archivo` es foto o video.
3. `estado` dentro de los 3 valores permitidos.
4. `tamano_bytes > 0`.
5. `sha256 IS NULL OR length(sha256) = 64`.
6. Si contexto = presupuesto, entonces `presupuesto_id` no es nulo, y al revés.
7. Si contexto = presupuesto, entonces `visible_cliente = true`.
8. Si estado = confirmada, entonces `confirmada_en` y `sha256` no son nulos.
9. `eliminada_en` y `eliminada_por_usuario_id` son los dos nulos o los dos llenos.
10. *Consistencia de estilo MS2*: las referencias lógicas a MS1/MS2/MS3 son
    ids positivos.

La lista de `content_type` permitidos (`image/jpeg`, `image/png`, `image/webp`,
`video/mp4`…) se valida en la aplicación (checklist 1.1 y 1.2), no en la base.

## Índices

- `ix_evidencia_orden_contexto` sobre (`orden_id`, `contexto`): la consulta
  principal de la recepción/carga es "evidencias de la orden X por contexto".
- `ix_evidencia_presupuesto` sobre `presupuesto_id`: soporta RF18 y la regla
  de negocio "todo presupuesto incluye al menos una evidencia".
- `UNIQUE` sobre `clave_objeto` (ya vía `unique=True`).

## Reglas de visibilidad

| Rol | Qué ve | Qué puede hacer |
|---|---|---|
| Cliente | Evidencias de **sus** órdenes (se verifica contra MS2) con `visible_cliente = true`, `estado = confirmada` y `eliminada_en IS NULL` | Solo lectura |
| Mecánico | Todas las confirmadas y no eliminadas de las órdenes que atiende | Subir, cambiar `visible_cliente` (salvo contexto presupuesto), eliminar las propias |
| Administrador | Todo, incluidas las eliminadas (auditoría) | Todo |

**Valor por defecto de `visible_cliente` según contexto:**

| Contexto | `visible_cliente` por defecto |
|---|---|
| `diagnostico` | `false` (trabajo interno del taller) |
| `reparacion` | `false` |
| `presupuesto` | `true` y no se puede cambiar (regla 7) |
| `resultado_final` | `true` (entrega de la orden) |

**Reglas de negocio**

- Cancelar una orden no borra ni mueve sus evidencias (MER §4.4).
- Una evidencia eliminada lógicamente no cuenta para la regla "todo presupuesto
  debe tener al menos una evidencia".
- Las evidencias anuladas o pendientes nunca se le muestran al cliente.

## Ciclo de estados (flujo C)

```text
             ┌─────────── confirmar ───────────┐
             │                                 ▼
   pendiente ──►  confirmada  ──►  eliminación lógica
             │                                  
             └─────────── anular ──►  anulada
```

- `pendiente` → `confirmada`: exige `confirmada_en` y `sha256` (regla 8); es
  el momento en que el archivo ya está íntegro y se guarda su hash (control 2.4).
- `pendiente` → `anulada`: la evidencia no sirvió (p. ej. foto borrosa) y no se
  muestra al cliente.
- `confirmada`/`anulada` → `eliminada_en`: baja lógica con responsable
  (`eliminada_por_usuario_id`), para auditoría. No borra el archivo de MinIO
  automáticamente: eso lo define la tarea de recepción (checklist 5.3).

## Relación con los requisitos funcionales

- **RF18** — *Crear presupuestos con monto y evidencia fotográfica o en
  video*, junto a la regla de negocio *todo presupuesto debe incluir al menos
  una foto o video como evidencia*. Se apoya en `ix_evidencia_presupuesto`: al validar el
  presupuesto se consulta si existe una evidencia `presupuesto_id = X` en estado
  `confirmada` y no eliminada.
- **RF29** — *Adjuntar archivos multimedia (fotografías o video) como evidencia
  en presupuestos y reparaciones.* Se apoya en los contextos `presupuesto` y
  `reparacion`, y en que la evidencia de presupuesto siempre es visible para
  el cliente que lo aprueba (regla 7).

## Pruebas

`tests/test_ms4_modelo_evidencia.py` (SQLite en memoria con `create_all`):

- inserción de una evidencia válida y sus valores por defecto;
- `IntegrityError` para las reglas 1–9 (contexto inválido, tipo inválido,
  tamaño 0, estado inválido, sha256 corto, pareja presupuesto-id incoherente
  en ambas direcciones, presupuesto oculto, confirmada sin sha256, eliminación
  sin responsable, `clave_objeto` duplicada);
- `visible_cliente` por defecto según contexto (4 casos).
