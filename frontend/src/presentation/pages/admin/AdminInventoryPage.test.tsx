import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { repuestoService } from '@/infrastructure/api/RepuestoService';
import type { PaginaRepuestos, Repuesto } from '@/domain/entities/Repuesto';
import { AdminInventoryPage, LIMITE_REPUESTOS } from './AdminInventoryPage';

vi.mock('@/infrastructure/api/RepuestoService', () => ({
    repuestoService: {
        getRepuestos: vi.fn(),
        getRepuestoById: vi.fn(),
    },
}));

// Fallo de transporte: error Axios sin respuesta HTTP (isOfflineError -> true).
const axiosNetworkError = { isAxiosError: true };
// Error del servidor: llego respuesta con status 500 (isOfflineError -> false).
const axiosServerError = {
    isAxiosError: true,
    response: { status: 500, data: { detail: 'El servidor tuvo un problema. Intente m\u00e1s tarde.' } },
};

function repuesto(overrides: Partial<Repuesto> = {}): Repuesto {
    return {
        repuestoId: 1,
        nombre: 'Filtro de aceite',
        proveedorId: 1,
        proveedorNombre: 'Repuestos del Sur',
        proveedorTipoDistribuidor: 'oficial',
        stock: 10,
        umbralParticular: null,
        umbralEfectivo: 5,
        bajoUmbral: false,
        ...overrides,
    };
}

function pagina(repuestos: Repuesto[], total = repuestos.length): PaginaRepuestos {
    return { total, desde: 0, limite: LIMITE_REPUESTOS, umbralGeneral: 5, repuestos };
}

const catalogo = [
    repuesto({ repuestoId: 1, nombre: 'Filtro de aceite', stock: 10, umbralEfectivo: 5 }),
    repuesto({
        repuestoId: 2,
        nombre: 'Pastillas de freno',
        proveedorNombre: 'Frenos Chile',
        stock: 2,
        umbralEfectivo: 10,
        bajoUmbral: true,
    }),
    repuesto({
        repuestoId: 3,
        nombre: 'Bujías',
        proveedorNombre: 'Ignición SpA',
        stock: 0,
        umbralEfectivo: 8,
        bajoUmbral: true,
    }),
];

describe('AdminInventoryPage: filtros y estado de stock', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('pide como máximo el límite que acepta el backend', async () => {
        vi.mocked(repuestoService.getRepuestos).mockResolvedValue(pagina(catalogo));

        render(<AdminInventoryPage />);

        await screen.findByText('Filtro de aceite');
        expect(repuestoService.getRepuestos).toHaveBeenCalledWith({ limite: 200 });
    });

    it('muestra el indicador de carga mientras espera la respuesta', () => {
        vi.mocked(repuestoService.getRepuestos).mockImplementation(
            () => new Promise<PaginaRepuestos>(() => {})
        );

        render(<AdminInventoryPage />);

        expect(screen.getByText('Cargando inventario...')).toBeInTheDocument();
    });

    it('lista los repuestos con su estado de stock y el contador total', async () => {
        vi.mocked(repuestoService.getRepuestos).mockResolvedValue(pagina(catalogo));

        render(<AdminInventoryPage />);

        expect(await screen.findByText('Filtro de aceite')).toBeInTheDocument();
        expect(screen.getByText('Pastillas de freno')).toBeInTheDocument();
        expect(screen.getByText('Bujías')).toBeInTheDocument();
        expect(screen.getByText(/3 de 3 repuestos/)).toBeInTheDocument();
        expect(screen.getByLabelText('Estado de stock: Normal')).toBeInTheDocument();
        expect(screen.getByLabelText('Estado de stock: Crítico')).toBeInTheDocument();
        expect(screen.getByLabelText('Estado de stock: Sin stock')).toBeInTheDocument();
    });

    it('filtra por texto sobre nombre, proveedor y código', async () => {
        vi.mocked(repuestoService.getRepuestos).mockResolvedValue(pagina(catalogo));

        render(<AdminInventoryPage />);
        await screen.findByText('Filtro de aceite');

        fireEvent.change(screen.getByRole('searchbox', { name: 'Buscar repuestos' }), {
            target: { value: 'frenos chile' },
        });

        expect(screen.getByText('Pastillas de freno')).toBeInTheDocument();
        expect(screen.queryByText('Filtro de aceite')).not.toBeInTheDocument();
        expect(screen.queryByText('Bujías')).not.toBeInTheDocument();
        expect(screen.getByText(/1 de 3 repuestos/)).toBeInTheDocument();
    });

    it('filtra por estado de stock', async () => {
        vi.mocked(repuestoService.getRepuestos).mockResolvedValue(pagina(catalogo));

        render(<AdminInventoryPage />);
        await screen.findByText('Filtro de aceite');

        fireEvent.change(screen.getByRole('combobox', { name: 'Filtrar por estado de stock' }), {
            target: { value: 'sin_stock' },
        });

        expect(screen.getByText('Bujías')).toBeInTheDocument();
        expect(screen.queryByText('Filtro de aceite')).not.toBeInTheDocument();
        expect(screen.queryByText('Pastillas de freno')).not.toBeInTheDocument();
    });

    it('limpia los filtros y recupera el listado completo', async () => {
        vi.mocked(repuestoService.getRepuestos).mockResolvedValue(pagina(catalogo));

        render(<AdminInventoryPage />);
        await screen.findByText('Filtro de aceite');

        const buscador = screen.getByRole('searchbox', { name: 'Buscar repuestos' });
        fireEvent.change(buscador, { target: { value: 'bujías' } });
        expect(screen.queryByText('Filtro de aceite')).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: /limpiar filtros/i }));

        expect(buscador).toHaveValue('');
        expect(screen.getByText('Filtro de aceite')).toBeInTheDocument();
        expect(screen.getByText('Bujías')).toBeInTheDocument();
    });

    it('muestra el estado vacío del catálogo cuando no hay repuestos', async () => {
        vi.mocked(repuestoService.getRepuestos).mockResolvedValue(pagina([]));

        render(<AdminInventoryPage />);

        expect(await screen.findByText('No hay repuestos registrados')).toBeInTheDocument();
    });

    it('explica que no hay coincidencias cuando los filtros no devuelven nada', async () => {
        vi.mocked(repuestoService.getRepuestos).mockResolvedValue(pagina(catalogo));

        render(<AdminInventoryPage />);
        await screen.findByText('Filtro de aceite');

        fireEvent.change(screen.getByRole('searchbox', { name: 'Buscar repuestos' }), {
            target: { value: 'inexistente' },
        });

        expect(
            screen.getByText('No se encontraron repuestos con los filtros aplicados')
        ).toBeInTheDocument();
    });

    it('muestra el error y permite reintentar la carga', async () => {
        vi.mocked(repuestoService.getRepuestos)
            .mockRejectedValueOnce(axiosServerError)
            .mockResolvedValueOnce(pagina(catalogo));

        render(<AdminInventoryPage />);

        expect(
            await screen.findByText('No se pudieron cargar los repuestos del inventario')
        ).toBeInTheDocument();
        expect(
            screen.getByText('El servidor tuvo un problema. Intente m\u00e1s tarde.')
        ).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: /reintentar/i }));

        expect(await screen.findByText('Filtro de aceite')).toBeInTheDocument();
        expect(repuestoService.getRepuestos).toHaveBeenCalledTimes(2);
    });

    it('avisa cuando el catálogo supera lo que se carga en una página', async () => {
        vi.mocked(repuestoService.getRepuestos).mockResolvedValue(pagina(catalogo, 512));

        render(<AdminInventoryPage />);

        expect(
            await screen.findByText(/El catálogo tiene 512 repuestos/)
        ).toBeInTheDocument();
    });

    it('consulta el servicio una sola vez al montar', async () => {
        vi.mocked(repuestoService.getRepuestos).mockResolvedValue(pagina(catalogo));

        render(<AdminInventoryPage />);

        await screen.findByText('Filtro de aceite');
        expect(repuestoService.getRepuestos).toHaveBeenCalledTimes(1);
        expect(repuestoService.getRepuestos).toHaveBeenCalledWith({ limite: 200 });
    });

    it('combina la búsqueda de texto con el filtro de estado de stock', async () => {
        vi.mocked(repuestoService.getRepuestos).mockResolvedValue(pagina(catalogo));

        render(<AdminInventoryPage />);
        await screen.findByText('Filtro de aceite');

        fireEvent.change(screen.getByRole('searchbox', { name: 'Buscar repuestos' }), {
            target: { value: 'pastillas' },
        });
        fireEvent.change(screen.getByRole('combobox', { name: 'Filtrar por estado de stock' }), {
            target: { value: 'critico' },
        });

        expect(screen.getByText('Pastillas de freno')).toBeInTheDocument();
        expect(screen.queryByText('Filtro de aceite')).not.toBeInTheDocument();
        expect(screen.queryByText('Bujías')).not.toBeInTheDocument();
        expect(screen.getByText(/1 de 3 repuestos/)).toBeInTheDocument();
    });

    it('permite limpiar los filtros desde el estado vacío', async () => {
        vi.mocked(repuestoService.getRepuestos).mockResolvedValue(pagina(catalogo));

        render(<AdminInventoryPage />);
        await screen.findByText('Filtro de aceite');

        fireEvent.change(screen.getByRole('searchbox', { name: 'Buscar repuestos' }), {
            target: { value: 'inexistente' },
        });

        expect(
            screen.getByText('No se encontraron repuestos con los filtros aplicados')
        ).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: /limpiar filtros/i }));

        expect(screen.getByRole('searchbox', { name: 'Buscar repuestos' })).toHaveValue('');
        expect(screen.getByText('Filtro de aceite')).toBeInTheDocument();
        expect(screen.getByText('Bujías')).toBeInTheDocument();
    });

    it('muestra un guion cuando el repuesto no tiene umbral efectivo', async () => {
        vi.mocked(repuestoService.getRepuestos).mockResolvedValue(
            pagina([repuesto({ repuestoId: 9, nombre: 'Sin umbral', umbralEfectivo: null, umbralParticular: null })])
        );

        render(<AdminInventoryPage />);

        expect(await screen.findByText('Sin umbral')).toBeInTheDocument();
        expect(screen.getByText('-')).toBeInTheDocument();
    });

    it('muestra el banner offline cuando no hay respuesta del servidor', async () => {
        vi.mocked(repuestoService.getRepuestos).mockRejectedValue(axiosNetworkError);

        render(<AdminInventoryPage />);

        expect(await screen.findByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();
        expect(screen.queryByText('No se pudieron cargar los repuestos del inventario')).not.toBeInTheDocument();
    });

    it('muestra el requestId cuando la Gateway lo env\u00eda en un error sin cach\u00e9', async () => {
        const errorConReferencia = {
            isAxiosError: true,
            response: {
                status: 500,
                data: { detail: 'El servidor tuvo un problema. Intente m\u00e1s tarde.', error: { request_id: 'req-inventario-1' } },
                headers: { 'x-request-id': 'req-inventario-1' },
            },
        };
        vi.mocked(repuestoService.getRepuestos).mockRejectedValue(errorConReferencia);

        render(<AdminInventoryPage />);

        expect(await screen.findByText('No se pudieron cargar los repuestos del inventario')).toBeInTheDocument();
        expect(screen.getByText('Referencia: req-inventario-1')).toBeInTheDocument();
    });
});

describe('AdminInventoryPage: modo mecánico', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    function renderMechanic() {
        return render(
            <MemoryRouter>
                <AdminInventoryPage mode="mechanic" />
            </MemoryRouter>
        );
    }

    it('oculta las acciones de administración y ofrece consultar el stock', async () => {
        vi.mocked(repuestoService.getRepuestos).mockResolvedValue(pagina(catalogo));

        renderMechanic();

        expect(await screen.findByText('Filtro de aceite')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Nuevo repuesto' })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Editar' })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Eliminar' })).not.toBeInTheDocument();

        const enlacesStock = screen.getAllByRole('link', { name: 'Ver stock' });
        expect(enlacesStock).toHaveLength(catalogo.length);
        expect(enlacesStock[0]).toHaveAttribute('href', '/mechanic/inventario/stock/1');
    });

    it('muestra el subtítulo de consulta sin acciones de escritura', async () => {
        vi.mocked(repuestoService.getRepuestos).mockResolvedValue(pagina(catalogo));

        renderMechanic();

        expect(
            await screen.findByText('Consulta de repuestos y disponibilidad del taller')
        ).toBeInTheDocument();
    });
});
