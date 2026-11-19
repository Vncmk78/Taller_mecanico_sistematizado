import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DevolucionSinDatosError, orderService } from '@/infrastructure/api/OrderService';
import apiClient from '@/infrastructure/config/apiClient';
import {
  bitacoraEntradaReal,
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
    post: vi.fn(),
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

  it('getVehicleOrderHistory consulta el historial paginado por vehículo', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { items: [ordenApi], total: 1, limit: 20, offset: 0 },
    });

    const page = await orderService.getVehicleOrderHistory('7', { limit: 20, offset: 0 });

    expect(apiClient.get).toHaveBeenCalledWith('/ordenes/vehiculo/7/historial', {
      params: { limit: 20, offset: 0 },
    });
    expect(page).toMatchObject({ total: 1, limit: 20, offset: 0 });
    expect(page.items[0].id).toBe('3');
    expect(page.items[0].vehicleId).toBe('7');
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

  it('el detalle del Cliente exige propiedad aunque la cuenta tenga otros roles', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: ordenApi });
    await orderService.getOrderById('3', { soloPropietario: true });
    expect(apiClient.get).toHaveBeenCalledWith('/ordenes/3', { params: { solo_propietario: true } });
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

// Cuerpos literales de gateway/contratos/ordenes.py:214-233, los mismos que
// valida backend/tests/test_gateway_openapi.py contra los esquemas reales.
describe('OrderService: Bitácora de trabajo (contrato HTTP de MS2)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getOrderBitacora consulta GET /ordenes/{id}/bitacora y traduce la entrada', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [bitacoraEntradaReal] });

    const entries = await orderService.getOrderBitacora('31');

    expect(apiClient.get).toHaveBeenCalledWith('/ordenes/31/bitacora');
    expect(entries[0]).toEqual({
      id: '77',
      ordenId: '31',
      autorUsuarioId: '50',
      tipo: 'accion',
      descripcion: 'Se reemplazaron las pastillas delanteras',
      creadoEn: '2026-09-28T12:15:00-03:00',
      repuestos: [{ nombre: 'Pastillas de freno', cantidad: 2 }],
    });
  });

  it('registrarBitacora publica POST /ordenes/{id}/bitacora recortando espacios', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: bitacoraEntradaReal });

    const entry = await orderService.registrarBitacora('31', {
      tipo: 'accion',
      descripcion: '  Se reemplazaron las pastillas delanteras  ',
      repuestos: [{ nombre: '  Pastillas de freno ', cantidad: 2 }],
    });

    expect(apiClient.post).toHaveBeenCalledWith('/ordenes/31/bitacora', {
      tipo: 'accion',
      descripcion: 'Se reemplazaron las pastillas delanteras',
      repuestos: [{ nombre: 'Pastillas de freno', cantidad: 2 }],
    });
    expect(entry.id).toBe('77');
  });

  // El modelo de MS2 tiene extra="forbid" y repuestos por defecto []; enviarlo
  // vacío en una observación es válido.
  it('registrarBitacora normaliza los repuestos omitidos a una lista vacía', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { ...bitacoraEntradaReal, tipo: 'observacion', repuestos: [] },
    });

    const entry = await orderService.registrarBitacora('31', {
      tipo: 'observacion',
      descripcion: 'El cliente reporta ruido al frenar',
    });

    expect(entry.repuestos).toEqual([]);
    const cuerpo = vi.mocked(apiClient.post).mock.calls[0][1] as Record<string, unknown>;
    expect(cuerpo.repuestos).toEqual([]);
  });
});

describe('OrderService: solicitud y confirmación de cancelación', () => {
  beforeEach(() => vi.clearAllMocks());

  it('después de solicitar consulta la orden sin interpretar la solicitud como estado Cancelado', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { solicitud_id: 5, orden_id: 3, estado: 'pendiente', motivo: 'No continuar' },
    });
    vi.mocked(apiClient.get).mockResolvedValue({ data: { ...ordenApi, estado_codigo: 3 } });

    const resultado = await orderService.cancelarComoCliente('3', ' No continuar ');

    expect(apiClient.post).toHaveBeenCalledWith('/ordenes/3/cancelacion', { motivo: 'No continuar' });
    expect(apiClient.get).toHaveBeenCalledWith('/ordenes/3');
    expect(resultado.id).toBe('3');
    expect(resultado.estadoCodigo).toBe(3);
    expect(resultado.vehicleId).toBe(String(ordenApi.vehiculo_id));
  });

  it('lista las solicitudes pendientes y traduce el contrato de cancelación', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: [
        {
          solicitud_id: 12,
          orden_id: 31,
          cliente_usuario_id: 42,
          estado_al_solicitar: 3,
          motivo: 'El cliente no continuará',
          estado: 'pendiente',
          solicitada_en: '2026-10-23T10:30:00-03:00',
          administrador_id: null,
          confirmada_en: null,
        },
      ],
    });

    const pendientes = await orderService.getCancelacionesPendientes();

    expect(apiClient.get).toHaveBeenCalledWith('/ordenes/cancelaciones/pendientes');
    expect(pendientes[0]).toEqual({
      id: '12',
      ordenId: '31',
      clienteUsuarioId: '42',
      estadoAlSolicitar: 3,
      motivo: 'El cliente no continuará',
      estado: 'pendiente',
      solicitadaEn: '2026-10-23T10:30:00-03:00',
      administradorId: null,
      confirmadaEn: null,
    });
  });

  it('el administrador usa la confirmación específica y recibe la orden cancelada', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { ...ordenApi, estado_codigo: 8 } });

    const resultado = await orderService.confirmarCancelacion('3');

    expect(apiClient.post).toHaveBeenCalledWith('/ordenes/3/cancelacion/confirmacion');
    expect(apiClient.patch).not.toHaveBeenCalled();
    expect(resultado.id).toBe('3');
    expect(resultado.estadoCodigo).toBe(8);
  });
});

describe('OrderService: devolución del vehículo de una orden cancelada', () => {
  // Fixture del acuerdo web/backend (contrato-web-bloques-3-4.md, Entrega A).
  const devolucionApi = {
    orden_id: 25,
    vehiculo_id: 9,
    ingreso_id: 12,
    estado_codigo: 8,
    mecanico_actual_id: null,
    creado_por_id: 3,
    creado_en: '2026-11-08T12:00:00Z',
    actualizado_en: '2026-11-08T13:00:00Z',
    devuelto_en: '2026-11-08T13:00:00Z',
    devuelto_por_id: 3,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('publica POST /ordenes/{id}/devolucion con body vacío y conserva el estado Cancelado', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: devolucionApi });

    const orden = await orderService.registrarDevolucion('25');

    expect(apiClient.post).toHaveBeenCalledWith('/ordenes/25/devolucion', {});
    expect(orden).toMatchObject({
      id: '25',
      estadoCodigo: 8,
      ingresoId: 12,
      devueltoEn: '2026-11-08T13:00:00Z',
      devueltoPorId: '3',
    });
  });

  it('una respuesta 200 sin fecha o responsable no se muestra como devolución registrada', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { ...devolucionApi, devuelto_en: null, devuelto_por_id: null },
    });

    await expect(orderService.registrarDevolucion('25')).rejects.toBeInstanceOf(DevolucionSinDatosError);
  });

  it('el detalle mapea la devolución informada, la ausencia (null) y la falta del campo (undefined)', async () => {
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({ data: devolucionApi })
      .mockResolvedValueOnce({ data: { ...devolucionApi, devuelto_en: null, devuelto_por_id: null } })
      .mockResolvedValueOnce({ data: ordenApi });

    const devuelta = await orderService.getOrderById('25');
    const pendiente = await orderService.getOrderById('25');
    const sinCampos = await orderService.getOrderById('3');

    expect([devuelta.devueltoEn, devuelta.devueltoPorId]).toEqual(['2026-11-08T13:00:00Z', '3']);
    expect([pendiente.devueltoEn, pendiente.devueltoPorId]).toEqual([null, null]);
    expect(sinCampos.devueltoEn).toBeUndefined();
    expect(sinCampos.devueltoPorId).toBeUndefined();
  });

  it('el listado y el historial por vehículo también traen los datos de devolución', async () => {
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({ data: [devolucionApi] })
      .mockResolvedValueOnce({ data: { items: [devolucionApi], total: 1, limit: 20, offset: 0 } });

    const [listada] = await orderService.getOrders();
    const pagina = await orderService.getVehicleOrderHistory('9', { limit: 20, offset: 0 });

    expect(listada.devueltoEn).toBe('2026-11-08T13:00:00Z');
    expect(pagina.items[0].devueltoPorId).toBe('3');
  });
});
