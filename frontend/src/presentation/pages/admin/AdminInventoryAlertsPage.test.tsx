import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import { AdminInventoryAlertsPage } from './AdminInventoryAlertsPage';

vi.mock('@/infrastructure/api/InventarioService', () => ({
    inventarioService: { listAlertas: vi.fn() },
}));

describe('AdminInventoryAlertsPage', () => {
    beforeEach(() => vi.clearAllMocks());

    it('muestra alertas de stock', async () => {
        vi.mocked(inventarioService.listAlertas).mockResolvedValue({
            umbralGeneral: 5,
            total: 1,
            alertas: [
                { repuestoId: 1, nombre: 'Filtro', proveedorNombre: 'Prov', stock: 2, umbralEfectivo: 5, faltan: 3 },
            ],
        });
        render(<AdminInventoryAlertsPage />);
        expect(await screen.findByText('Filtro')).toBeInTheDocument();
        expect(screen.getByText('3')).toBeInTheDocument();
    });

    it('muestra vacío cuando no hay alertas', async () => {
        vi.mocked(inventarioService.listAlertas).mockResolvedValue({
            umbralGeneral: 5,
            total: 0,
            alertas: [],
        });
        render(<AdminInventoryAlertsPage />);
        expect(await screen.findByText('No hay alertas de stock')).toBeInTheDocument();
    });
});
