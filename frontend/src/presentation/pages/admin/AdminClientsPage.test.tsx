import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { authService } from '@/infrastructure/api/AuthService';
import type { UsuarioListado } from '@/domain/entities/User';
import { AdminClientsPage } from './AdminClientsPage';

vi.mock('@/infrastructure/api/AuthService', () => ({
    authService: {
        listarUsuarios: vi.fn(),
    },
}));

// Fallo de transporte: error Axios sin respuesta HTTP (isOfflineError -> true).
const axiosNetworkError = { isAxiosError: true };
// Error del servidor: llego respuesta con status 500 (isOfflineError -> false).
const axiosServerError = {
    isAxiosError: true,
    response: { status: 500, data: { detail: 'El servidor tuvo un problema. Intente m\u00e1s tarde.' } },
};

function usuario(overrides: Partial<UsuarioListado> = {}): UsuarioListado {
    return {
        id: '1',
        email: 'ana@correo.cl',
        full_name: 'Ana Pérez',
        roles: ['cliente'],
        is_active: true,
        ...overrides,
    };
}

const usuariosDelSistema = [
    usuario(),
    usuario({
        id: '2',
        email: 'bruno@correo.cl',
        full_name: 'Bruno Díaz',
        is_active: false,
    }),
    usuario({
        id: '3',
        email: 'mecanico@correo.cl',
        full_name: 'Martín Herrera',
        roles: ['mecanico'],
    }),
    usuario({
        id: '4',
        email: 'admin@correo.cl',
        full_name: 'Administradora General',
        roles: ['administrador'],
    }),
];

describe('AdminClientsPage: listado y estados', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('lista solo las cuentas con rol cliente y muestra su estado', async () => {
        vi.mocked(authService.listarUsuarios).mockResolvedValue(usuariosDelSistema);

        render(<AdminClientsPage />);

        expect(await screen.findByText('Ana Pérez')).toBeInTheDocument();
        expect(screen.getByText('Bruno Díaz')).toBeInTheDocument();
        expect(screen.getByText('ana@correo.cl')).toBeInTheDocument();
        expect(screen.getByText('Activo')).toBeInTheDocument();
        expect(screen.getByText('Inactivo')).toBeInTheDocument();
        expect(screen.getByText(/2 de 2 clientes/)).toBeInTheDocument();
        expect(screen.queryByText('Martín Herrera')).not.toBeInTheDocument();
        expect(screen.queryByText('Administradora General')).not.toBeInTheDocument();
    });

    it('consulta GET /auth/usuarios una sola vez al montar', async () => {
        vi.mocked(authService.listarUsuarios).mockResolvedValue(usuariosDelSistema);

        render(<AdminClientsPage />);

        await screen.findByText('Ana Pérez');
        expect(authService.listarUsuarios).toHaveBeenCalledTimes(1);
    });

    it('muestra el indicador de carga mientras espera la respuesta', () => {
        vi.mocked(authService.listarUsuarios).mockImplementation(
            () => new Promise<UsuarioListado[]>(() => {})
        );

        render(<AdminClientsPage />);

        expect(screen.getByText('Cargando clientes...')).toBeInTheDocument();
    });

    it('muestra el error y permite reintentar la carga', async () => {
        vi.mocked(authService.listarUsuarios)
            .mockRejectedValueOnce(axiosServerError)
            .mockResolvedValueOnce(usuariosDelSistema);

        render(<AdminClientsPage />);

        expect(await screen.findByText('No se pudieron cargar los clientes')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: /reintentar/i }));

        expect(await screen.findByText('Ana Pérez')).toBeInTheDocument();
        expect(authService.listarUsuarios).toHaveBeenCalledTimes(2);
    });

    it('muestra el estado vacío cuando no hay cuentas con rol cliente', async () => {
        vi.mocked(authService.listarUsuarios).mockResolvedValue([
            usuario({ id: '3', email: 'mecanico@correo.cl', roles: ['mecanico'] }),
        ]);

        render(<AdminClientsPage />);

        expect(await screen.findByText('No hay clientes registrados')).toBeInTheDocument();
    });

    it('distingue el vacío por búsqueda y permite limpiar los filtros', async () => {
        vi.mocked(authService.listarUsuarios).mockResolvedValue(usuariosDelSistema);

        render(<AdminClientsPage />);
        await screen.findByText('Ana Pérez');

        const buscador = screen.getByRole('searchbox', { name: 'Buscar clientes' });
        fireEvent.change(buscador, { target: { value: 'inexistente' } });

        expect(
            await screen.findByText('No se encontraron clientes para "inexistente".')
        ).toBeInTheDocument();
        expect(screen.queryByText('Ana Pérez')).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: /limpiar filtros/i }));

        expect(buscador).toHaveValue('');
        await waitFor(() => {
            expect(screen.getByText('Ana Pérez')).toBeInTheDocument();
        });
        expect(screen.getByText('Bruno Díaz')).toBeInTheDocument();
    });

    it('filtra por nombre y por correo electrónico', async () => {
        vi.mocked(authService.listarUsuarios).mockResolvedValue(usuariosDelSistema);

        render(<AdminClientsPage />);
        await screen.findByText('Ana Pérez');

        fireEvent.change(screen.getByRole('searchbox', { name: 'Buscar clientes' }), {
            target: { value: 'bruno@' },
        });

        await waitFor(() => {
            expect(screen.queryByText('Ana Pérez')).not.toBeInTheDocument();
        });
        expect(screen.getByText('Bruno Díaz')).toBeInTheDocument();
        expect(screen.getByText(/1 de 2 clientes/)).toBeInTheDocument();
    });

    it('muestra el banner offline cuando no hay respuesta del servidor', async () => {
        vi.mocked(authService.listarUsuarios).mockRejectedValue(axiosNetworkError);

        render(<AdminClientsPage />);

        expect(await screen.findByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();
        expect(screen.queryByText('No se pudieron cargar los clientes')).not.toBeInTheDocument();
    });

    it('muestra el requestId cuando la Gateway lo env\u00eda en un error sin cach\u00e9', async () => {
        const errorConReferencia = {
            isAxiosError: true,
            response: {
                status: 500,
                data: { detail: 'El servidor tuvo un problema. Intente m\u00e1s tarde.', error: { request_id: 'req-clientes-1' } },
                headers: { 'x-request-id': 'req-clientes-1' },
            },
        };
        vi.mocked(authService.listarUsuarios).mockRejectedValue(errorConReferencia);

        render(<AdminClientsPage />);

        expect(await screen.findByText('No se pudieron cargar los clientes')).toBeInTheDocument();
        expect(screen.getByText('Referencia: req-clientes-1')).toBeInTheDocument();
    });
});
