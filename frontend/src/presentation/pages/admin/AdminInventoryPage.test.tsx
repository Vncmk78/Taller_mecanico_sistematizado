import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { repuestoService } from '@/infrastructure/api/RepuestoService';
import type { PaginaRepuestos, Repuesto } from '@/domain/entities/Repuesto';
import { AdminInventoryPage, LIMITE_REPUESTOS } from './AdminInventoryPage';

vi.mock('@/infrastructure/api/RepuestoService', () => ({
    repuestoService: {
        getRepuestos: vi.fn(),
        getRepuestoById: vi.fn(),
    },
}));

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
            .mockRejectedValueOnce(new Error('500'))
            .mockResolvedValueOnce(pagina(catalogo));

        render(<AdminInventoryPage />);

        expect(
            await screen.findByText('No se pudieron cargar los repuestos del inventario.')
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
});
