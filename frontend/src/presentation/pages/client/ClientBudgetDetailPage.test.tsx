import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { useBudgetStore } from '@/infrastructure/stores/useBudgetStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { mockPresupuestoPendiente } from '@/infrastructure/mocks/budgets.mock';
import { ClientBudgetDetailPage } from './ClientBudgetDetailPage';

vi.mock('@/infrastructure/api/PresupuestoService', () => ({
    presupuestoService: {
        getByOrder: vi.fn(),
        getById: vi.fn(),
        decidir: vi.fn(),
    },
}));

const axiosNetworkError = { isAxiosError: true };
const axios500 = { isAxiosError: true, response: { status: 500, data: {} } };

const versionAprobada = {
    ...mockPresupuestoPendiente.versiones[0],
    estado: 'aprobada' as const,
    decision: { id: '77', decision: 'aprobado' as const, fecha: '2026-09-03T10:00:00-03:00' },
};

function renderPage() {
    return render(
        <MemoryRouter initialEntries={['/client/presupuestos/101']}>
            <Routes>
                <Route path="/client/presupuestos/:ordenId" element={<ClientBudgetDetailPage />} />
            </Routes>
        </MemoryRouter>
    );
}

function withPendingSources() {
    vi.mocked(presupuestoService.getByOrder).mockResolvedValue({
        ...mockPresupuestoPendiente,
        versiones: [],
    });
    vi.mocked(presupuestoService.getById).mockResolvedValue(mockPresupuestoPendiente);
}

describe('ClientBudgetDetailPage: aprobación y rechazo del presupuesto', () => {
    beforeEach(() => {
        useBudgetStore.setState({ presupuestos: [], status: 'idle', error: null, isOffline: false, requestId: null });
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false, requestId: null });
        vi.clearAllMocks();
    });

    it('muestra las partidas, el total y los botones de decisión del presupuesto pendiente', async () => {
        withPendingSources();

        renderPage();

        expect(await screen.findByText('Servicio n° 101')).toBeInTheDocument();
        expect(screen.getByText('Kit Pastillas Freno Delanteras')).toBeInTheDocument();
        expect(screen.getByText('Mano de obra (Mantención general)')).toBeInTheDocument();
        expect(screen.getByText('$108.000')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Aprobar Presupuesto' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Rechazar' })).toBeInTheDocument();
    });

    it('aprueba el presupuesto tras confirmar y avisa el resultado', async () => {
        withPendingSources();
        vi.mocked(presupuestoService.decidir).mockResolvedValue({
            presupuesto: {
                ...mockPresupuestoPendiente,
                estadoUltimaVersion: 'aprobada',
                versionVigente: 1,
                versiones: [versionAprobada],
                totalUltimaVersion: 108000,
            },
            efectoEnOrden: 'en_reparacion',
            decisionId: '77',
            aplicacionConfirmada: true,
        });

        renderPage();

        fireEvent.click(await screen.findByRole('button', { name: 'Aprobar Presupuesto' }));
        fireEvent.click(screen.getByRole('button', { name: 'Aprobar' }));

        expect(await screen.findByText(/Presupuesto aprobado/)).toBeInTheDocument();
        expect(presupuestoService.decidir).toHaveBeenCalledWith('501', 1, 'aprobado', undefined, undefined);
    });

    it('rechaza exigiendo motivo y, antes de aprobar, confirmación de cancelación', async () => {
        withPendingSources();
        vi.mocked(presupuestoService.decidir).mockResolvedValue({
            presupuesto: {
                ...mockPresupuestoPendiente,
                estadoUltimaVersion: 'rechazada',
                versiones: [{ ...mockPresupuestoPendiente.versiones[0], estado: 'rechazada' }],
            },
            efectoEnOrden: 'cancelado',
            decisionId: '88',
            aplicacionConfirmada: true,
        });

        renderPage();

        fireEvent.click(await screen.findByRole('button', { name: 'Rechazar' }));
        const confirmar = screen.getByRole('button', { name: 'Rechazar presupuesto' });

        // Sin motivo el diálogo valida antes de llamar a la API.
        fireEvent.click(confirmar);
        expect(await screen.findByText('Indique el motivo del rechazo.')).toBeInTheDocument();
        expect(presupuestoService.decidir).not.toHaveBeenCalled();

        // Con motivo pero sin confirmar la cancelación sigue bloqueado.
        fireEvent.change(screen.getByLabelText('Motivo del rechazo'), {
            target: { value: 'Costo elevado' },
        });
        fireEvent.click(confirmar);
        expect(
            await screen.findByText('Debe confirmar que desea cancelar el servicio.')
        ).toBeInTheDocument();

        fireEvent.click(
            screen.getByLabelText(/Entiendo que, al rechazar antes de aprobar/)
        );
        fireEvent.click(confirmar);

        expect(await screen.findByText(/Presupuesto rechazado/)).toBeInTheDocument();
        expect(presupuestoService.decidir).toHaveBeenCalledWith('501', 1, 'rechazado', 'Costo elevado', true);
    });

    it('una orden sin presupuesto enviado muestra el estado vacío', async () => {
        vi.mocked(presupuestoService.getByOrder).mockResolvedValue(null);

        renderPage();

        expect(await screen.findByText('Presupuesto no encontrado.')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Volver a mis presupuestos' })).toHaveAttribute(
            'href',
            '/client/presupuestos'
        );
    });

    it('un error del servidor no lo disfraza de presupuesto inexistente', async () => {
        vi.mocked(presupuestoService.getByOrder).mockRejectedValue(axios500);

        renderPage();

        expect(await screen.findByText('No se pudo cargar el presupuesto')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
        expect(screen.queryByText('Presupuesto no encontrado.')).not.toBeInTheDocument();
    });

    it('sin conexión conserva el presupuesto desde la caché', async () => {
        useBudgetStore.setState({
            presupuestos: [mockPresupuestoPendiente],
            status: 'idle',
            error: null,
            isOffline: false,
        });
        vi.mocked(presupuestoService.getByOrder).mockRejectedValue(axiosNetworkError);
        vi.mocked(presupuestoService.getById).mockRejectedValue(axiosNetworkError);

        renderPage();

        expect(await screen.findByText('Servicio n° 101')).toBeInTheDocument();
        expect(await screen.findByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();
        expect(screen.getByText('Kit Pastillas Freno Delanteras')).toBeInTheDocument();
    });
});
