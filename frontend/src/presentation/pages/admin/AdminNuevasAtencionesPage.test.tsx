import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { SolicitudNuevaAtencion } from '@/domain/entities/SolicitudNuevaAtencion';
import { nuevaAtencionService } from '@/infrastructure/api/NuevaAtencionService';
import { AdminNuevasAtencionesPage } from './AdminNuevasAtencionesPage';

// Simulaciones del contrato acordado; la integración real la hace Codex.
vi.mock('@/infrastructure/api/NuevaAtencionService', () => ({
    nuevaAtencionService: { solicitar: vi.fn(), listar: vi.fn(), obtener: vi.fn(), revisar: vi.fn(), generarOrden: vi.fn() },
}));

const solicitud = (id: number, overrides: Partial<SolicitudNuevaAtencion> = {}): SolicitudNuevaAtencion => ({
    id: String(id),
    ordenCanceladaId: '25',
    vehiculoId: '9',
    clienteUsuarioId: '10',
    descripcion: `Descripción ${id}`,
    solicitadaEn: '2026-11-08T14:00:00-03:00',
    situacion: 'pendiente',
    respuesta: null,
    revisorId: null,
    revisadaEn: null,
    ordenGeneradaId: null,
    ...overrides,
});

const vacia = { items: [], total: 0, limit: 20, offset: 0 };

const renderPage = () =>
    render(
        <MemoryRouter>
            <AdminNuevasAtencionesPage />
        </MemoryRouter>
    );

beforeEach(() => vi.clearAllMocks());

describe('AdminNuevasAtencionesPage', () => {
    it('lista vacía sin filtros', async () => {
        vi.mocked(nuevaAtencionService.listar).mockResolvedValue(vacia);

        renderPage();

        expect(await screen.findByText('Aún no hay solicitudes de nueva atención.')).toBeInTheDocument();
        expect(nuevaAtencionService.listar).toHaveBeenCalledWith({}, { limit: 20, offset: 0 });
    });

    it('muestra el cliente de cada solicitud y enlaza al detalle administrativo', async () => {
        vi.mocked(nuevaAtencionService.listar).mockResolvedValue({
            items: [solicitud(5, { clienteUsuarioId: '12', situacion: 'aceptada', ordenGeneradaId: '30' })],
            total: 1, limit: 20, offset: 0,
        });

        renderPage();

        const lista = await screen.findByRole('list', { name: 'Solicitudes de nueva atención' });
        const item = within(lista).getByRole('listitem');
        expect(item).toHaveTextContent('cliente (usuario) n° 12');
        expect(item).toHaveTextContent('generó la orden n° 30');
        expect(within(item).getByRole('link')).toHaveAttribute('href', '/admin/nuevas-atenciones/5');
    });

    it('filtra por situación, orden cancelada y orden generada en el servidor', async () => {
        vi.mocked(nuevaAtencionService.listar).mockResolvedValue(vacia);
        renderPage();
        await screen.findByText('Aún no hay solicitudes de nueva atención.');

        fireEvent.change(screen.getByLabelText('Situación'), { target: { value: 'aceptada' } });
        await waitFor(() =>
            expect(nuevaAtencionService.listar).toHaveBeenLastCalledWith({ situacion: 'aceptada' }, { limit: 20, offset: 0 })
        );

        fireEvent.change(screen.getByLabelText('Orden cancelada n°'), { target: { value: '25' } });
        fireEvent.change(screen.getByLabelText('Orden generada n°'), { target: { value: '30' } });
        fireEvent.click(screen.getByRole('button', { name: 'Filtrar' }));

        await waitFor(() =>
            expect(nuevaAtencionService.listar).toHaveBeenLastCalledWith(
                { situacion: 'aceptada', ordenCanceladaId: '25', ordenGeneradaId: '30' },
                { limit: 20, offset: 0 }
            )
        );
        expect(await screen.findByText('No hay solicitudes con esos filtros.')).toBeInTheDocument();
    });

    it('rechaza números de orden inválidos sin consultar', async () => {
        vi.mocked(nuevaAtencionService.listar).mockResolvedValue(vacia);
        renderPage();
        await screen.findByText('Aún no hay solicitudes de nueva atención.');

        fireEvent.change(screen.getByLabelText('Orden cancelada n°'), { target: { value: '-3' } });
        fireEvent.click(screen.getByRole('button', { name: 'Filtrar' }));

        expect(await screen.findByText('Los números de orden deben ser enteros positivos.')).toBeInTheDocument();
        expect(nuevaAtencionService.listar).toHaveBeenCalledTimes(1);
    });

    it('pagina en el servidor', async () => {
        vi.mocked(nuevaAtencionService.listar)
            .mockResolvedValueOnce({ items: Array.from({ length: 20 }, (_, i) => solicitud(41 - i)), total: 41, limit: 20, offset: 0 })
            .mockResolvedValueOnce({ items: [solicitud(21)], total: 41, limit: 20, offset: 20 });

        renderPage();

        expect(await screen.findByText('1–20 de 41')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }));
        expect(await screen.findByText('21–40 de 41')).toBeInTheDocument();
        expect(nuevaAtencionService.listar).toHaveBeenLastCalledWith({}, { limit: 20, offset: 20 });
    });

    it('un error se muestra con reintento', async () => {
        vi.mocked(nuevaAtencionService.listar)
            .mockRejectedValueOnce({ isAxiosError: true, response: { status: 404, data: { detail: 'Not Found' } } })
            .mockResolvedValueOnce(vacia);

        renderPage();

        expect(await screen.findByText('Not Found')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: /Reintentar/ }));
        expect(await screen.findByText('Aún no hay solicitudes de nueva atención.')).toBeInTheDocument();
    });
});
