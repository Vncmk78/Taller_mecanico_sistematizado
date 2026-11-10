import { beforeEach, expect, it, vi } from 'vitest';
import apiClient from '@/infrastructure/config/apiClient';
import { notificationService } from './NotificationService';
vi.mock('@/infrastructure/config/apiClient', () => ({ default: { get: vi.fn(), patch: vi.fn(), post: vi.fn() } }));
beforeEach(() => vi.clearAllMocks());
it('lee la fecha y el límite del contrato real y conserva el estado de lectura', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [{ notificacion_id: 1, tipo: 'orden.estado_cambiado', titulo: 'Orden', mensaje: 'Aviso', leida: true, creado_en: '2026-11-07T10:00:00Z' }] });
    const result = await notificationService.getMyNotifications({ limit: 30, soloNoLeidas: true });
    expect(apiClient.get).toHaveBeenCalledWith('/notificaciones', { params: { limite: 30, solo_no_leidas: true } });
    expect(result.items[0]).toMatchObject({ leida: true, creadaEn: '2026-11-07T10:00:00Z' });
    expect(result.noLeidas).toBe(0);
});
it.each([404, 405, 501, 503])('no presenta como éxito ni bandeja vacía un HTTP %s', async (status) => {
    const error = { response: { status } };
    vi.mocked(apiClient.get).mockRejectedValue(error);
    vi.mocked(apiClient.patch).mockRejectedValue(error);
    await expect(notificationService.getMyNotifications()).rejects.toBe(error);
    await expect(notificationService.markAsRead('1')).rejects.toBe(error);
    await expect(notificationService.markAllAsRead()).rejects.toBe(error);
});

it('el contador usa los totales del servidor y no solo los 15 avisos de la campana', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [], headers: { 'x-notificaciones-total': '45', 'x-notificaciones-no-leidas': '28' } });
    expect(await notificationService.getMyNotifications({ limit: 15 })).toMatchObject({ total: 45, noLeidas: 28 });
});

it('consulta y reintenta solo los canales del aviso indicado', async () => {
  const api = { entrega_id: 3, canal: 'correo', estado: 'pendiente', intentos: 0, aceptada_en: null, ultimo_error: null, intentos_registrados: [] };
  vi.mocked(apiClient.get).mockResolvedValue({ data: [api] });
  vi.mocked(apiClient.post).mockResolvedValue({ data: [api] });
  expect((await notificationService.getDeliveries('8'))[0]).toMatchObject({ id: '3', estado: 'pendiente' });
  await notificationService.retryDeliveries('8');
  expect(apiClient.get).toHaveBeenCalledWith('/notificaciones/8/entregas');
  expect(apiClient.post).toHaveBeenCalledWith('/notificaciones/8/reintentos');
});

it('acepta alertas sin orden y conserva referencias a solicitudes, presupuestos y repuestos', async () => {
  vi.mocked(apiClient.get).mockResolvedValue({ data: [{ notificacion_id: 4, tipo: 'stock.alerta', titulo: 'Stock', mensaje: 'Aviso', leida: false, orden_id: null, repuesto_id: 8, solicitud_id: null, presupuesto_id: null }] });
  const { items } = await notificationService.getMyNotifications();
  expect(items[0]).toMatchObject({ ordenId: null, repuestoId: '8', solicitudId: null, presupuestoId: null });
});
