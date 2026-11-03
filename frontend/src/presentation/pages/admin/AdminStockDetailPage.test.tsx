import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import { AdminStockDetailPage } from './AdminStockDetailPage';

vi.mock('@/infrastructure/api/InventarioService', () => ({
    inventarioService: { getStock: vi.fn() },
}));

describe('AdminStockDetailPage', () => {
    beforeEach(() => vi.clearAllMocks());

    it('muestra stock del repuesto', async () => {
        vi.mocked(inventarioService.getStock).mockResolvedValue({
            repuestoId: 7,
            nombre: 'Filtro',
            proveedorNombre: 'Prov',
            stock: 10,
            comprometido: 2,
            disponible: 8,
            umbralEfectivo: 5,
            bajoUmbral: false,
            compromisos: [],
        });
        render(
            <MemoryRouter initialEntries={['/admin/inventario/stock/7']}>
                <Routes>
                    <Route path="/admin/inventario/stock/:repuestoId" element={<AdminStockDetailPage />} />
                </Routes>
            </MemoryRouter>
        );
        expect(await screen.findByText('Filtro')).toBeInTheDocument();
        expect(screen.getByText('8')).toBeInTheDocument();
    });
});
