import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { proveedorService } from '@/infrastructure/api/ProveedorService';
import type { PaginaProveedores, Proveedor } from '@/domain/entities/Proveedor';
import { AdminDistributorsPage, LIMITE_PROVEEDORES } from './AdminDistributorsPage';

vi.mock('@/infrastructure/api/ProveedorService', () => ({
    proveedorService: {
        getProveedores: vi.fn(),
    },
}));

// Fallo de transporte: error Axios sin respuesta HTTP (isOfflineError -> true).
const axiosNetworkError = { isAxiosError: true };
// Error del servidor: llego respuesta con status 500 (isOfflineError -> false).
const axiosServerError = {
    isAxiosError: true,
    response: { status: 500, data: { detail: 'El servidor tuvo un problema. Intente m\u00e1s tarde.' } },
};

function proveedor(overrides: Partial<Proveedor> = {}): Proveedor {
    return {
        proveedorId: 1,
        nombre: 'Repuestos del Sur',
        contacto: 'ventas@delsur.cl',
        tipoDistribuidor: 'oficial',
        cantidadRepuestos: 12,
        ...overrides,
    };
}

function pagina(
    proveedores: Proveedor[],
    total = proveedores.length
): PaginaProveedores {
    return { total, desde: 0, limite: LIMITE_PROVEEDORES, proveedores };
}

const catalogo = [
    proveedor(),
    proveedor({
        proveedorId: 2,
        nombre: 'Frenos Chile',
        contacto: '+56 9 8765 4321',
        tipoDistribuidor: 'generico',
        cantidadRepuestos: 4,
    }),
];

describe('AdminDistributorsPage: listado y estados', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('pide como máximo el límite que acepta el backend y lista los distribuidores', async () => {
        vi.mocked(proveedorService.getProveedores).mockResolvedValue(pagina(catalogo));

        render(<AdminDistributorsPage />);

        expect(await screen.findByText('Repuestos del Sur')).toBeInTheDocument();
        expect(proveedorService.getProveedores).toHaveBeenCalledWith({ limite: 200 });
        expect(screen.getByText('Frenos Chile')).toBeInTheDocument();
        expect(screen.getByText('Oficial')).toBeInTheDocument();
        expect(screen.getByText('Genérico')).toBeInTheDocument();
        expect(screen.getByText('12')).toBeInTheDocument();
        expect(screen.getByText(/2 de 2 distribuidores/)).toBeInTheDocument();
    });

    it('muestra el indicador de carga mientras espera la respuesta', () => {
        vi.mocked(proveedorService.getProveedores).mockImplementation(
            () => new Promise<PaginaProveedores>(() => {})
        );

        render(<AdminDistributorsPage />);

        expect(screen.getByText('Cargando distribuidores...')).toBeInTheDocument();
    });

    it('muestra el error y permite reintentar la carga', async () => {
        vi.mocked(proveedorService.getProveedores)
            .mockRejectedValueOnce(axiosServerError)
            .mockResolvedValueOnce(pagina(catalogo));

        render(<AdminDistributorsPage />);

        expect(
            await screen.findByText('No se pudieron cargar los distribuidores')
        ).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: /reintentar/i }));

        expect(await screen.findByText('Repuestos del Sur')).toBeInTheDocument();
        expect(proveedorService.getProveedores).toHaveBeenCalledTimes(2);
    });

    it('muestra el estado vacío cuando no hay distribuidores', async () => {
        vi.mocked(proveedorService.getProveedores).mockResolvedValue(pagina([]));

        render(<AdminDistributorsPage />);

        expect(await screen.findByText('No hay distribuidores registrados')).toBeInTheDocument();
    });

    it('en modo mecánico lista los distribuidores sin acciones de escritura', async () => {
        vi.mocked(proveedorService.getProveedores).mockResolvedValue(pagina(catalogo));

        render(<AdminDistributorsPage mode="mechanic" />);

        expect(await screen.findByText('Repuestos del Sur')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Nuevo proveedor' })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Editar' })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Eliminar' })).not.toBeInTheDocument();
        expect(screen.queryByRole('columnheader', { name: 'Acciones' })).not.toBeInTheDocument();
    });

    it('distingue el vacío por búsqueda y permite limpiar los filtros', async () => {
        vi.mocked(proveedorService.getProveedores).mockResolvedValue(pagina(catalogo));

        render(<AdminDistributorsPage />);
        await screen.findByText('Repuestos del Sur');

        const buscador = screen.getByRole('searchbox', { name: 'Buscar distribuidores' });
        fireEvent.change(buscador, { target: { value: 'inexistente' } });

        expect(
            screen.getByText('No se encontraron distribuidores para "inexistente".')
        ).toBeInTheDocument();
        expect(screen.queryByText('Repuestos del Sur')).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: /limpiar filtros/i }));

        expect(buscador).toHaveValue('');
        expect(screen.getByText('Repuestos del Sur')).toBeInTheDocument();
        expect(screen.getByText('Frenos Chile')).toBeInTheDocument();
    });

    it('filtra por nombre y por contacto', async () => {
        vi.mocked(proveedorService.getProveedores).mockResolvedValue(pagina(catalogo));

        render(<AdminDistributorsPage />);
        await screen.findByText('Repuestos del Sur');

        fireEvent.change(screen.getByRole('searchbox', { name: 'Buscar distribuidores' }), {
            target: { value: '8765' },
        });

        expect(screen.getByText('Frenos Chile')).toBeInTheDocument();
        expect(screen.queryByText('Repuestos del Sur')).not.toBeInTheDocument();
        expect(screen.getByText(/1 de 2 distribuidores/)).toBeInTheDocument();
    });

    it('avisa cuando el catálogo supera lo que se carga en una página', async () => {
        vi.mocked(proveedorService.getProveedores).mockResolvedValue(pagina(catalogo, 512));

        render(<AdminDistributorsPage />);

        expect(await screen.findByText(/El catálogo tiene 512 distribuidores/)).toBeInTheDocument();
    });

    it('consulta el servicio una sola vez al montar', async () => {
        vi.mocked(proveedorService.getProveedores).mockResolvedValue(pagina(catalogo));

        render(<AdminDistributorsPage />);

        await screen.findByText('Repuestos del Sur');
        expect(proveedorService.getProveedores).toHaveBeenCalledTimes(1);
        expect(proveedorService.getProveedores).toHaveBeenCalledWith({ limite: 200 });
    });

    it('muestra el contacto de cada distribuidor y su tipo', async () => {
        vi.mocked(proveedorService.getProveedores).mockResolvedValue(pagina(catalogo));

        render(<AdminDistributorsPage />);

        expect(await screen.findByText('ventas@delsur.cl')).toBeInTheDocument();
        expect(screen.getByText('+56 9 8765 4321')).toBeInTheDocument();
    });

    it('muestra el banner offline cuando no hay respuesta del servidor', async () => {
        vi.mocked(proveedorService.getProveedores).mockRejectedValue(axiosNetworkError);

        render(<AdminDistributorsPage />);

        expect(await screen.findByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();
        expect(screen.queryByText('No se pudieron cargar los distribuidores')).not.toBeInTheDocument();
    });

    it('muestra el requestId cuando la Gateway lo env\u00eda en un error sin cach\u00e9', async () => {
        const errorConReferencia = {
            isAxiosError: true,
            response: {
                status: 500,
                data: { detail: 'El servidor tuvo un problema. Intente m\u00e1s tarde.', error: { request_id: 'req-dist-1' } },
                headers: { 'x-request-id': 'req-dist-1' },
            },
        };
        vi.mocked(proveedorService.getProveedores).mockRejectedValue(errorConReferencia);

        render(<AdminDistributorsPage />);

        expect(await screen.findByText('No se pudieron cargar los distribuidores')).toBeInTheDocument();
        expect(screen.getByText('Referencia: req-dist-1')).toBeInTheDocument();
    });
});
