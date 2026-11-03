import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { Repuesto } from '@/domain/entities/Repuesto';
import { StockStatusBadge } from './StockStatusBadge';

function repuesto(overrides: Partial<Repuesto> = {}): Repuesto {
    return {
        repuestoId: 1,
        nombre: 'Pastillas de freno',
        proveedorId: 2,
        proveedorNombre: 'Frenos Chile',
        proveedorTipoDistribuidor: 'oficial',
        stock: 3,
        umbralParticular: null,
        umbralEfectivo: 10,
        bajoUmbral: true,
        ...overrides,
    };
}

describe('StockStatusBadge: visualización del estado de stock', () => {
    it('muestra la etiqueta del estado calculado', () => {
        render(<StockStatusBadge repuesto={repuesto({ stock: 0 })} />);

        expect(screen.getByText('Sin stock')).toBeInTheDocument();
    });

    it('expone el estado de forma accesible con aria-label y title', () => {
        render(<StockStatusBadge repuesto={repuesto()} />);

        const badge = screen.getByLabelText('Estado de stock: Crítico');
        expect(badge).toHaveAttribute('title', 'Estado de stock: Crítico');
        expect(badge).toHaveTextContent('Crítico');
    });

    it('aplica el color del estado y respeta className extra', () => {
        render(<StockStatusBadge repuesto={repuesto({ stock: 50 })} className="ml-2" />);

        const badge = screen.getByLabelText('Estado de stock: Normal');
        expect(badge).toHaveClass('text-status-green');
        expect(badge).toHaveClass('ml-2');
    });
});
