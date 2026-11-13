import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { SolicitudCancelacion } from '@/domain/entities/SolicitudCancelacion';
import { orderService } from '@/infrastructure/api/OrderService';
import { errorAxios } from '@/infrastructure/mocks/payloads.reales';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { AdminCancelacionesPage } from './AdminCancelacionesPage';

vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: {
        getCancelacionesPendientes: vi.fn(),
        confirmarCancelacion: vi.fn(),
    },
}));

const solicitud: SolicitudCancelacion = {
    id: '12',
    ordenId: '31',
    clienteUsuarioId: '42',
    estadoAlSolicitar: 3,
    motivo: 'El cliente no continuará con el servicio',
    estado: 'pendiente',
    solicitadaEn: '2026-10-23T10:30:00-03:00',
    administradorId: null,
    confirmadaEn: null,
};

function renderPage() {
    return render(
        <MemoryRouter>
            <ToastProvider>
                <AdminCancelacionesPage />
            </ToastProvider>
        </MemoryRouter>
    );
}

describe('AdminCancelacionesPage: bandeja de solicitudes pendientes', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(orderService.getCancelacionesPendientes).mockResolvedValue([solicitud]);
    });

    it('lista las solicitudes con su motivo y enlaza a la orden', async () => {
        renderPage();

        expect(await screen.findByText('Orden n° 31')).toHaveAttribute(
            'href',
            '/admin/ordenes/31'
        );
        expect(screen.getByText('El cliente no continuará con el servicio')).toBeInTheDocument();
        expect(screen.getByText('Cliente #42')).toBeInTheDocument();
        expect(screen.getByText('Esperando aprobación de presupuesto')).toBeInTheDocument();
        expect(orderService.getCancelacionesPendientes).toHaveBeenCalledTimes(1);
    });

    it('muestra un estado vacío cuando no hay solicitudes', async () => {
        vi.mocked(orderService.getCancelacionesPendientes).mockResolvedValue([]);

        renderPage();

        expect(await screen.findByText('No hay cancelaciones pendientes')).toBeInTheDocument();
    });

    it('confirma la cancelación solo después del diálogo y la quita de la bandeja', async () => {
        vi.mocked(orderService.confirmarCancelacion).mockResolvedValue({
            id: '31',
            vehicleId: '1',
            ingresoId: 1,
            estadoCodigo: 8,
            mecanicoActualId: null,
            creadoPorId: '1',
            creadoEn: '2026-10-20T10:00:00Z',
            actualizadoEn: '2026-10-23T10:40:00Z',
        });

        renderPage();

        fireEvent.click(await screen.findByRole('button', { name: 'Confirmar cancelación' }));
        const dialog = await screen.findByRole('dialog', { name: '¿Confirmar la cancelación?' });
        expect(screen.getByText(/Motivo del cliente: El cliente no continuará/)).toBeInTheDocument();
        expect(orderService.confirmarCancelacion).not.toHaveBeenCalled();

        fireEvent.click(within(dialog).getByRole('button', { name: 'Confirmar cancelación' }));

        await waitFor(() => expect(orderService.confirmarCancelacion).toHaveBeenCalledWith('31'));
        expect(await screen.findByText('Orden n° 31 cancelada.')).toBeInTheDocument();
        await waitFor(() => expect(screen.queryByText('Orden n° 31')).not.toBeInTheDocument());
    });

    it('muestra el rechazo del backend sin quitar la solicitud', async () => {
        vi.mocked(orderService.confirmarCancelacion).mockRejectedValue(
            errorAxios(409, { detail: 'No existe una solicitud pendiente para la orden' })
        );

        renderPage();

        fireEvent.click(await screen.findByRole('button', { name: 'Confirmar cancelación' }));
        fireEvent.click(
            within(await screen.findByRole('dialog')).getByRole('button', {
                name: 'Confirmar cancelación',
            })
        );

        expect(
            await screen.findByText('No existe una solicitud pendiente para la orden')
        ).toBeInTheDocument();
        expect(screen.getByText('Orden n° 31')).toBeInTheDocument();
    });

    it('permite reintentar cuando falla la carga inicial', async () => {
        vi.mocked(orderService.getCancelacionesPendientes)
            .mockRejectedValueOnce(errorAxios(500, { detail: 'Servicio no disponible' }))
            .mockResolvedValueOnce([solicitud]);

        renderPage();

        expect(
            await screen.findByText('No se pudieron cargar las cancelaciones pendientes')
        ).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

        expect(await screen.findByText('Orden n° 31')).toBeInTheDocument();
    });
});
