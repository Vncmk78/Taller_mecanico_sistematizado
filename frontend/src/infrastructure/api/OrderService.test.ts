import { beforeEach, describe, expect, it, vi } from 'vitest';
import { orderService } from '@/infrastructure/api/OrderService';
import apiClient from '@/infrastructure/config/apiClient';
import {
  historialEstadoDeCreacion,
  historialEstadoReal,
  ordenRespuestaConMecanico,
  ordenRespuestaReal,
} from '@/infrastructure/mocks/payloads.reales';

// Fija el contrato HTTP de MS2 consumido por el frontend (ver
// docs/contratos-openapi.md). Cualquier cambio de ruta o de mapeo debe
// coordinarse con el backend y reflejarse aquí.
vi.mock('@/infrastructure/config/apiClient', () => ({
  default: {
    get: vi.fn(),
    patch: vi.fn(),
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

  it('getOrderHistory consulta GET /ordenes/{id}/historial', async () => {
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

  it('cambiarEstado publica PATCH /ordenes/{id}/estado y traduce la orden actualizada', async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({
      data: { ...ordenApi, estado_codigo: 6 },
    });

    const order = await orderService.cambiarEstado('3', 6, 'Trabajo terminado');

    expect(apiClient.patch).toHaveBeenCalledWith('/ordenes/3/estado', {
      estado_destino: 6,
      observacion: 'Trabajo terminado',
    });
    expect(order.estadoCodigo).toBe(6);
    expect(order.mecanicoActualId).toBe('40');
  });

  it('cambiarEstado omite la observación vacía en el cuerpo', async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({ data: ordenApi });

    await orderService.cambiarEstado('3', 2);

    expect(apiClient.patch).toHaveBeenCalledWith('/ordenes/3/estado', {
      estado_destino: 2,
      observacion: undefined,
    });
  });

  it('cambiarEstado trata la observación de solo espacios como ausente', async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({ data: ordenApi });

    await orderService.cambiarEstado('3', 2, '   ');

    // CambioEstadoSolicitud declara min_length=1 con str_strip_whitespace, así que
    // mandar "   " llegaría al backend como "" y respondería 422. Omitirla lo evita.
    expect(apiClient.patch).toHaveBeenCalledWith('/ordenes/3/estado', {
      estado_destino: 2,
      observacion: undefined,
    });
  });

  it('cambiarEstado envía solo estado_destino y observacion, sin campos extra', async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({ data: ordenApi });

    await orderService.cambiarEstado('3', 6, 'Listo');

    // El modelo de MS2 tiene extra="forbid": mandar orden_id o actor_usuario_id
    // desde el cliente lo haría rechazar con 422. El rol y el id del mecánico los
    // saca MS2 del JWT.
    const cuerpo = vi.mocked(apiClient.patch).mock.calls[0][1] as Record<string, unknown>;
    expect(Object.keys(cuerpo).sort()).toEqual(['estado_destino', 'observacion']);
    expect(cuerpo.estado_destino).toBe(6);
    expect(typeof cuerpo.estado_destino).toBe('number');
  });
});

// Cuerpos literales de gateway/contratos/ordenes.py, los mismos que valida
// backend/tests/test_gateway_openapi.py contra los esquemas reales.
describe('OrderService: mapeo contra el payload real de la Gateway', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('traduce el ejemplo real del contrato, con el mecánico sin asignar', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [ordenRespuestaReal] });

    const orders = await orderService.getOrders();

    expect(orders[0]).toEqual({
      id: '31',
      vehicleId: '12',
      ingresoId: 18,
      estadoCodigo: 1,
      mecanicoActualId: null,
      creadoPorId: '99',
      creadoEn: '2026-09-28T10:30:00-03:00',
      actualizadoEn: '2026-09-28T10:30:00-03:00',
    });
  });

  it('conserva la fecha tal cual llega, con su offset -03:00', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [ordenRespuestaReal] });

    const [order] = await orderService.getOrders();

    // El mapeo no debe normalizar ni recortar la fecha: se guarda el string
    // exacto que envió el backend.
    expect(order.creadoEn).toBe('2026-09-28T10:30:00-03:00');
    // Y ese string representa el instante correcto: 10:30 en Chile son las
    // 13:30 UTC. La aserción es independiente de la zona horaria del runner.
    expect(new Date(order.creadoEn).toISOString()).toBe('2026-09-28T13:30:00.000Z');
  });

  it('traduce el mecánico asignado como id de texto del dominio', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [ordenRespuestaConMecanico] });

    const [order] = await orderService.getOrders();

    expect(order.mecanicoActualId).toBe('50');
    expect(order.estadoCodigo).toBe(5);
  });

  it('traduce el ejemplo real del historial con su observación', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [historialEstadoReal] });

    const entries = await orderService.getOrderHistory('31');

    expect(entries[0]).toEqual({
      id: '41',
      ordenId: '31',
      estadoAnteriorCodigo: 1,
      estadoNuevoCodigo: 2,
      actorUsuarioId: 50,
      origen: 'usuario',
      fecha: '2026-09-28T11:00:00-03:00',
      observacion: 'Inicia evaluación técnica',
    });
  });

  it('traduce el registro de creación del historial: sistema, sin estado anterior ni actor', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [historialEstadoDeCreacion] });

    const entries = await orderService.getOrderHistory('31');

    expect(entries[0]).toEqual({
      id: '40',
      ordenId: '31',
      estadoAnteriorCodigo: null,
      estadoNuevoCodigo: 1,
      actorUsuarioId: null,
      origen: 'sistema',
      fecha: '2026-09-28T10:30:00-03:00',
      // La observación llega en null y el dominio la deja como undefined para
      // que la línea de tiempo no invente un texto.
      observacion: undefined,
    });
  });

  it('respeta la coherencia del historial real: sistema implica actor nulo', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [historialEstadoDeCreacion] });

    const [entry] = await orderService.getOrderHistory('31');

    // La base lo garantiza (ms2_taller/models/historial_estado.py:64-68); el
    // mapeo no debe inventar un actor para poder pintar la línea de tiempo.
    expect(entry.origen).toBe('sistema');
    expect(entry.actorUsuarioId).toBeNull();
  });
});
