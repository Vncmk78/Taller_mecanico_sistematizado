import { beforeEach, describe, expect, it, vi } from 'vitest';
import { orderService } from '@/infrastructure/api/OrderService';
import apiClient from '@/infrastructure/config/apiClient';

// Fija el contrato HTTP de MS2 consumido por el frontend (ver
// docs/contratos-openapi.md). Cualquier cambio de ruta o de mapeo debe
// coordinarse con el backend y reflejarse aquí.
vi.mock('@/infrastructure/config/apiClient', () => ({
  default: {
    get: vi.fn(),
  },
}));

const ordenApi = {
  orden_id: 3,
  vehiculo_id: 7,
  ingreso_id: 1,
  estado_codigo: 5,
  mecanico_actual_id: 40,
  creado_por_id: 99,
  creado_en: '2026-09-01T10:00:00Z',
  actualizado_en: '2026-09-02T15:30:00Z',
};

const historialApi = {
  historial_id: 2,
  orden_id: 9,
  estado_anterior: 2,
  estado_nuevo: 5,
  actor_usuario_id: 40,
  origen: 'usuario' as const,
  fecha_hora: '2026-09-02T15:30:00Z',
  observacion: 'Avanza a reparación',
};

describe('OrderService: contrato HTTP de MS2 (órdenes)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getOrders consulta GET /ordenes y traduce OrdenRespuesta al dominio', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [ordenApi] });

    const orders = await orderService.getOrders();

    expect(apiClient.get).toHaveBeenCalledWith('/ordenes');
    expect(orders[0]).toEqual({
      id: '3',
      vehicleId: '7',
      ingresoId: 1,
      estadoCodigo: 5,
      mecanicoActualId: '40',
      creadoPorId: '99',
      creadoEn: '2026-09-01T10:00:00Z',
      actualizadoEn: '2026-09-02T15:30:00Z',
    });
  });

  it('getOrderById interpola el id en GET /ordenes/{id}', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: ordenApi });

    const order = await orderService.getOrderById('3');

    expect(apiClient.get).toHaveBeenCalledWith('/ordenes/3');
    expect(order.id).toBe('3');
  });

  it('mantiene mecánico nulo cuando el servidor no asignó responsable', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { ...ordenApi, mecanico_actual_id: null },
    });

    const order = await orderService.getOrderById('3');

    expect(order.mecanicoActualId).toBeNull();
  });

  it('getOrderHistory consulta GET /ordenes/{id}/historial (endpoint pendiente de MS2)', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [historialApi] });

    const entries = await orderService.getOrderHistory('9');

    expect(apiClient.get).toHaveBeenCalledWith('/ordenes/9/historial');
    expect(entries[0]).toEqual({
      id: '2',
      ordenId: '9',
      estadoAnteriorCodigo: 2,
      estadoNuevoCodigo: 5,
      actorUsuarioId: 40,
      origen: 'usuario',
      fecha: '2026-09-02T15:30:00Z',
      observacion: 'Avanza a reparación',
    });
  });
});