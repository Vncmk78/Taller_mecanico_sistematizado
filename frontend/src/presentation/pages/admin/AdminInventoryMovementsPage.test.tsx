import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import { AdminInventoryMovementsPage } from './AdminInventoryMovementsPage';

vi.mock('@/infrastructure/api/InventarioService', () => ({
    inventarioService: { listMovimientos: vi.fn(), registrarMovimiento: vi.fn() },
}));

describe('AdminInventoryMovementsPage', () => {
    beforeEach(() => vi.clearAllMocks());

    it('lista movimientos', async () => {
        vi.mocked(inventarioService.listMovimientos).mockResolvedValue({
            total: 1,
            desde: 0,
            limite: 50,
            movimientos: [
                {
                    movimientoId: 1,
                    claveOperacion: 'k',
                    repuestoId: 2,
                    tipo: 'ingreso',
                    cantidad: 5,
                    ordenId: null,
                    proveedorId: null,
                    fechaHora: '2026-01-01T00:00:00Z',
                    registradoPorId: 1,
                },
            ],
        });
        render(<AdminInventoryMovementsPage />);
        expect(await screen.findByText('ingreso')).toBeInTheDocument();
    });

    it('muestra vacío cuando no hay movimientos', async () => {
        vi.mocked(inventarioService.listMovimientos).mockResolvedValue({
            total: 0,
            desde: 0,
            limite: 50,
            movimientos: [],
        });
        render(<AdminInventoryMovementsPage />);
        expect(await screen.findByText('No hay movimientos')).toBeInTheDocument();
    });
});
