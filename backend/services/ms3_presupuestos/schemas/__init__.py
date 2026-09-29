"""Esquemas Pydantic (contratos de entrada/salida) del microservicio MS3.

Un módulo por recurso (presupuesto.py, repuesto.py, proveedor.py,
inventario.py). Convenciones del proyecto:

- Campos en español, iguales al MER (patente, marca... / numero, cantidad...).
- `model_config = ConfigDict(extra="forbid")` en las entradas: un campo que no
  corresponde (por ejemplo un id que decide el servidor) se rechaza con 422.
- Dinero y cantidades de ítems como Decimal (nunca float).
"""
