import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import { AdminThresholdPage } from './AdminThresholdPage';

vi.mock('@/infrastructure/api/InventarioService', () => ({
    inventarioService: {
        getUmbralGeneral: vi.fn(),
        getHistorialUmbral: vi.fn(),
        cambiarUmbralGeneral: vi.fn(),
    },
}));

describe('AdminThresholdPage', () => {
    beforeEach(() => vi.clearAllMocks());

    it('muestra umbral general', async () => {
        vi.mocked(inventarioService.getUmbralGeneral).mockResolvedValue({
            umbralGeneral: 5,
            vigenteDesde: null,
            actualizadoPorId: null,
        });
        vi.mocked(inventarioService.getHistorialUmbral).mockResolvedValue([]);
        render(<AdminThresholdPage />);
        expect(await screen.findByText('5')).toBeInTheDocument();
    });
});
