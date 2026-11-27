"""Las notificaciones internas usan URL configurable y secreto de servicio."""

import pytest

from shared.direccion_notificaciones import (
    cabeceras_notificaciones,
    url_notificaciones_por_defecto,
)


@pytest.mark.parametrize("ms", [1, 2])
def test_valor_local_y_cabecera_de_servicio(ms):
    assert url_notificaciones_por_defecto(ms) == f"http://localhost:800{ms}"
    destino = f"http://ms{ms}-interno:8000"
    assert cabeceras_notificaciones(destino, ms, "servicio") == {
        "X-Service-Token": "servicio"
    }
