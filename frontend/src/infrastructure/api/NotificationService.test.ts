import { beforeEach, expect, it, vi } from 'vitest';
import apiClient from '@/infrastructure/config/apiClient';
import { notificationService } from './NotificationService';
vi.mock('@/infrastructure/config/apiClient', () => ({ default: { get: vi.fn(), patch: vi.fn() } }));
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
