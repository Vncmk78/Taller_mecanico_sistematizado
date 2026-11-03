# Notas de traspaso: reglas y casos límite

Grupo 10 · Taller de Integración II · SCRUM-688 · 23-10-2026

Este resumen sirve para orientar la continuidad del backend y las pruebas. La
fuente funcional sigue siendo `Sistematizacion.docx`; ante dudas, contrastar
este resumen con esa sistematización y con el contrato vigente. No usar estas
notas para habilitar por sí solas una ruta bloqueada.

## Arquitectura y responsabilidades

- La solución conserva cuatro microservicios y una API Gateway. Web y móvil
  consumen la Gateway, nunca los servicios directamente.
- MS1 autentica y administra usuarios/roles; también aloja notificaciones.
- MS2 administra perfiles de cliente, vehículos, ingresos físicos, órdenes,
  asignaciones, estados, historiales y capacidades.
- MS3 administra presupuestos/versiones, repuestos, proveedores e inventario.
- MS4 administra metadatos y archivos de evidencias.
- Cada servicio mantiene su propia base PostgreSQL. Las referencias entre
  servicios son identificadores y contratos API, no claves foráneas cruzadas.
- Los roles son `cliente`, `mecanico` y `administrador`; una cuenta puede tener
  varios. El registro público solo concede `cliente`; roles internos requieren
  administración.

Referencias: [`contratos-api-gateway.md`](contratos-api-gateway.md),
[`matriz-autorizacion-roles.md`](matriz-autorizacion-roles.md) y
[`modelo-evidencias.md`](modelo-evidencias.md).

## Estados y reglas que deben preservarse

La orden tiene ocho estados oficiales:

| Código | Estado |
|---:|---|
| 1 | Recibido |
| 2 | Esperando diagnóstico |
| 3 | Esperando aprobación de presupuesto |
| 4 | Esperando repuestos |
| 5 | En reparación |
| 6 | Listo |
| 7 | Entregado |
| 8 | Cancelado |

La decisión de una versión de presupuesto y la revisión de una solicitud de
nueva atención son estados separados; no se agregan al catálogo de la orden.

Reglas de transición comprobadas/documentadas:

- La creación requiere que el Administrador confirme el ingreso físico; crea la
  orden en `Recibido` y su historial inicial en la misma transacción.
- La primera asignación válida del Administrador cambia `Recibido` a
  `Esperando diagnóstico`. La reasignación posterior conserva el estado y deja
  trazabilidad del responsable anterior, el nuevo y el Administrador.
- El envío del primer presupuesto lleva a `Esperando aprobación de presupuesto`.
  La primera aprobación se valida en MS3: una instantánea de stock insuficiente
  deriva a `Esperando repuestos`; una suficiente deriva a `En reparación`.
  Esa instantánea no reserva unidades ni verifica disponibilidad más adelante.
- Un rechazo inicial del Cliente antes de cualquier aprobación puede cancelar
  por el flujo específico de decisión, con motivo e historial. No equivale a la
  solicitud independiente de cancelación.
- Solo el Mecánico asignado puede declarar `Listo` mediante la operación actual;
  hoy no se verifica que toda la labor autorizada esté efectivamente terminada.
- `Entregado` y `Cancelado` son terminales. Una orden terminal no se reabre.
- Estado e historial se guardan atómicamente en MS2. Los rechazos no escriben
  una transición falsa ni una fila de historial.

## Límites de capacidad

- Son límites independientes el cupo de ingresos físicos por jornada y el
  máximo de órdenes activas por Mecánico. Ambos son configurables por un
  Administrador; la sistematización no fija valores universales.
- Solo un nuevo ingreso físico consume cupo diario. Reasignar, atender al día
  siguiente o cancelar no crea otro ingreso ni devuelve el cupo ya usado.
- Si el vehículo sigue dentro del taller, otra orden de atención debe reutilizar
  el ingreso abierto según la regla de la sistematización.
- La capacidad del Mecánico cuenta órdenes asignadas que no estén `Entregado` ni
  `Cancelado`. Una orden `Recibido` sin responsable no ocupa capacidad. La
  reasignación libera carga del responsable anterior y carga al nuevo.
- Una reducción por debajo del uso actual no cancela ni desasigna órdenes; se
  informa la situación y se rechazan aumentos que excedan el nuevo límite.
- La configuración local que se observó para ingresos diarios fue 4. Es un
  valor del entorno de desarrollo; no convertirlo en requisito de negocio ni
  asumir que está aplicado en otros entornos.

## Autorización y privacidad

- Cada microservicio valida el JWT y autoriza por rol y recurso; la Gateway enruta
  y no reemplaza esos controles.
- Cliente: solo ve órdenes de sus vehículos. Mecánico: solo órdenes asignadas a
  su usuario. Administrador: alcance global sobre órdenes.
- Para proteger la existencia de recursos ajenos, una consulta de orden fuera
  del alcance del Cliente/Mecánico responde `404`, igual que una orden inexistente.
- Un usuario multirrol acumula alcances; no se intersectan.
- Un motivo no sustituye la autorización, la solicitud formal o una precondición
  de negocio. No permitir que un PATCH genérico evada una operación específica.

## Flujos deliberadamente incompletos

El PATCH genérico debe seguir rechazando estos casos hasta implementar su
operación de dominio y contrato, con actor, precondiciones, idempotencia e
historial definidos:

- `Esperando repuestos` → `En reparación`: falta un evento verificado entre MS3
  y MS2; hay que definir actor y cómo se consideran unidades comprometidas o
  reservadas. La aprobación inicial no cubre esta transición posterior.
- `Listo` → `Entregado`: falta registrar la entrega física, Administrador,
  fecha/hora y estado/historial juntos. Devolver un vehículo cancelado no lo
  convierte en `Entregado`.
- Cancelación independiente solicitada por el Cliente y confirmada por el
  Administrador: falta verificar ausencia de aprobación previa en MS3 y guardar
  la confirmación e historial. El rechazo inicial de presupuesto sí usa otro
  flujo específico.
- Finalización del trabajo: la ruta actual permite al Mecánico asignado marcar
  `Listo`, pero falta acordar cómo probar que se completó el alcance autorizado.
- Notificaciones y eventos: la sistematización ubica notificaciones en MS1 y
  exige destinatarios autorizados, persistencia y resultado por canal. El
  contrato, autenticación servicio-a-servicio, catálogo de eventos y política de
  reintentos aún requieren acuerdo. No introducir broker, payload ni endpoint
  por inferencia.

La máquina de estados documenta evidencia, endpoints y rechazos exactos en
[`maquina-estados-ordenes.md`](maquina-estados-ordenes.md). Para notificaciones,
ver [`estudio-eventos-notificaciones.md`](estudio-eventos-notificaciones.md).

## Verificación y entorno local

- Regresión de vehículos, órdenes, asignaciones e historial ejecutada el
  2026-10-23: 214 pruebas pasaron; hubo 9 advertencias deprecadas de
  Starlette/httpx y de la constante HTTP 422.
- La integración local ha tenido Gateway, MS1, MS2 y MS3 disponibles; MS4 y
  MinIO no estaban activos en la última comprobación. Para una prueba que
  requiera evidencias multimedia, levantar y verificar también MS4 y MinIO.
- Las pruebas de MS3 con PostgreSQL usan transacciones revertidas. No limpiar
  datos persistentes de una base compartida sin identificar su origen.

## Siguiente paso para trabajo pendiente

Antes de habilitar una transición incompleta, contrastar el requisito con la
sistematización, acordar actor y precondiciones con el equipo, definir el
contrato entre servicios, y agregar pruebas de autorización, concurrencia,
idempotencia, atomicidad y ausencia de escrituras en rechazos. Mantener el
backend alineado con la API Gateway y no cambiar la arquitectura de cuatro
microservicios.
