import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { SolicitudNuevaAtencion } from '@/domain/entities/SolicitudNuevaAtencion';
import type { User, UserRole } from '@/domain/entities/User';
import { nuevaAtencionService } from '@/infrastructure/api/NuevaAtencionService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { ClientNuevasAtencionesPage } from './ClientNuevasAtencionesPage';

// Simulaciones del contrato acordado (Entrega B); el backend B está pendiente.
vi.mock('@/infrastructure/api/NuevaAtencionService', () => ({
    nuevaAtencionService: { solicitar: vi.fn(), listar: vi.fn(), obtener: vi.fn() },
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

function iniciar(roles: UserRole[]) {
    const user: User = { id: '10', email: 'c@taller.cl', full_name: 'Cliente', role: roles[0], roles, is_active: true };
    useAuthStore.setState({ user, token: 't', isAuthenticated: true });
}

const renderPage = () =>
    render(
        <MemoryRouter>
            <ClientNuevasAtencionesPage />
        </MemoryRouter>
    );

beforeEach(() => {
    vi.clearAllMocks();
    iniciar(['cliente']);
});

describe('ClientNuevasAtencionesPage', () => {
    it('lista vacía: lo indica y orienta a las órdenes canceladas', async () => {
        vi.mocked(nuevaAtencionService.listar).mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });

        renderPage();

        expect(await screen.findByText('Aún no hay solicitudes de nueva atención.')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Ir a mis órdenes' })).toHaveAttribute('href', '/client/ordenes');
        expect(screen.getByRole('heading', { name: /Mis solicitudes de nueva atención/ })).toBeInTheDocument();
        expect(nuevaAtencionService.listar).toHaveBeenCalledWith({}, { limit: 20, offset: 0 });
    });

    it('muestra situación y orden generada tal como las informa el servidor', async () => {
        vi.mocked(nuevaAtencionService.listar).mockResolvedValue({
            items: [
                solicitud(5, { situacion: 'aceptada', ordenGeneradaId: '30' }),
                solicitud(4, { situacion: 'rechazada' }),
            ],
            total: 2, limit: 20, offset: 0,
        });

        renderPage();

        const lista = await screen.findByRole('list', { name: 'Solicitudes de nueva atención' });
        const items = within(lista).getAllByRole('listitem');
        expect(items[0]).toHaveTextContent('Aceptada');
        expect(items[0]).toHaveTextContent('generó la orden n° 30');
        expect(items[1]).toHaveTextContent('Rechazada');
        expect(within(items[0]).getByRole('link')).toHaveAttribute('href', '/client/nuevas-atenciones/5');
    });

    it('pagina en el servidor con limit 20 y offset', async () => {
        vi.mocked(nuevaAtencionService.listar)
            .mockResolvedValueOnce({ items: Array.from({ length: 20 }, (_, i) => solicitud(25 - i)), total: 25, limit: 20, offset: 0 })
            .mockResolvedValueOnce({ items: [1, 2, 3, 4, 5].map((n) => solicitud(n)), total: 25, limit: 20, offset: 20 });

        renderPage();

        expect(await screen.findByText('1–20 de 25')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Anterior' })).toBeDisabled();
        fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }));

        expect(await screen.findByText('21–25 de 25')).toBeInTheDocument();
        expect(nuevaAtencionService.listar).toHaveBeenLastCalledWith({}, { limit: 20, offset: 20 });
        expect(screen.getByRole('button', { name: 'Siguiente' })).toBeDisabled();
    });

    it('filtra por situación en el servidor y vuelve a la primera página', async () => {
        vi.mocked(nuevaAtencionService.listar).mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });

        renderPage();
        await screen.findByText('Aún no hay solicitudes de nueva atención.');
        fireEvent.change(screen.getByLabelText('Situación'), { target: { value: 'rechazada' } });

        await waitFor(() =>
            expect(nuevaAtencionService.listar).toHaveBeenLastCalledWith({ situacion: 'rechazada' }, { limit: 20, offset: 0 })
        );
        expect(await screen.findByText('No hay solicitudes con esa situación.')).toBeInTheDocument();
    });

    it('una cuenta que incluye Administrador ve el alcance administrativo', async () => {
        iniciar(['cliente', 'administrador']);
        vi.mocked(nuevaAtencionService.listar).mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });

        renderPage();

        expect(await screen.findByRole('heading', { name: 'Solicitudes de nueva atención' })).toBeInTheDocument();
        expect(screen.getByText(/se muestran las solicitudes de todos los clientes/)).toBeInTheDocument();
    });

    it('un error del servidor se muestra con reintento', async () => {
        vi.mocked(nuevaAtencionService.listar)
            .mockRejectedValueOnce({ isAxiosError: true, response: { status: 403, data: { detail: 'Se requiere el rol Cliente o Administrador' } } })
            .mockResolvedValueOnce({ items: [], total: 0, limit: 20, offset: 0 });

        renderPage();

        expect(await screen.findByText('Se requiere el rol Cliente o Administrador')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: /Reintentar/ }));
        expect(await screen.findByText('Aún no hay solicitudes de nueva atención.')).toBeInTheDocument();
    });
});
