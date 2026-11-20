import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import type { Notification, NotificationListResponse } from '@/domain/entities/Notification';
import { notificationService } from '@/infrastructure/api/NotificationService';
import { NotificationsPage } from './NotificationsPage';

vi.mock('@/infrastructure/api/NotificationService', () => ({
    notificationService: {
        getMyNotifications: vi.fn(),
        markAsRead: vi.fn(),
        markAllAsRead: vi.fn(),
        getDeliveries: vi.fn(),
        retryDeliveries: vi.fn(),
    },
}));

const aviso: Notification = {
    id: '8',
    userId: '3',
    tipo: 'orden_actualizada',
    titulo: 'Su orden cambió de estado',
    mensaje: 'El vehículo está en revisión.',
    leida: false,
    creadaEn: '2026-11-18T10:00:00Z',
};

function respuesta(items: Notification[], total = items.length): NotificationListResponse {
    return { items, total, noLeidas: items.filter((n) => !n.leida).length };
}

describe('NotificationsPage: estados de carga, error y lista vacía', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(notificationService.getMyNotifications).mockResolvedValue(respuesta([aviso]));
    });

    it('muestra el estado de carga mientras espera los avisos', () => {
        vi.mocked(notificationService.getMyNotifications).mockImplementation(
            () => new Promise<NotificationListResponse>(() => {})
        );

        render(<NotificationsPage />);

        expect(screen.getByText('Cargando notificaciones...')).toBeInTheDocument();
        expect(screen.getAllByRole('status').length).toBeGreaterThan(0);
    });

    it('lista los avisos recibidos', async () => {
        render(<NotificationsPage />);

        expect(await screen.findByText('Su orden cambió de estado')).toBeInTheDocument();
        expect(screen.getByText('El vehículo está en revisión.')).toBeInTheDocument();
        expect(screen.getByText('orden actualizada')).toBeInTheDocument();
        expect(
            screen.queryByRole('navigation', { name: 'Paginación de notificaciones' })
        ).not.toBeInTheDocument();
    });

    it('muestra el error con reintento cuando falla la carga', async () => {
        vi.mocked(notificationService.getMyNotifications)
            .mockRejectedValueOnce(new Error('No disponible'))
            .mockResolvedValueOnce(respuesta([aviso]));

        render(<NotificationsPage />);

        expect(await screen.findByText('No se pudieron cargar los avisos')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

        expect(await screen.findByText('Su orden cambió de estado')).toBeInTheDocument();
        expect(notificationService.getMyNotifications).toHaveBeenCalledTimes(2);
    });

    it('muestra el estado vacío y oculta la paginación cuando no hay avisos', async () => {
        vi.mocked(notificationService.getMyNotifications).mockResolvedValue(respuesta([]));

        render(<NotificationsPage />);

        expect(await screen.findByText('No hay notificaciones')).toBeInTheDocument();
        expect(
            screen.queryByRole('navigation', { name: 'Paginación de notificaciones' })
        ).not.toBeInTheDocument();
    });
});
