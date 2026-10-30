import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProgressBar } from '@/presentation/components/ui/ProgressBar';

describe('ProgressBar: barra de progreso accesible', () => {
    it('expone el porcentaje con role progressbar', () => {
        render(<ProgressBar value={42} />);

        const barra = screen.getByRole('progressbar');
        expect(barra).toHaveAttribute('aria-valuenow', '42');
        expect(barra).toHaveAttribute('aria-valuemin', '0');
        expect(barra).toHaveAttribute('aria-valuemax', '100');
    });

    it('recorta el valor al rango 0-100', () => {
        const { rerender } = render(<ProgressBar value={-5} />);
        expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0');

        rerender(<ProgressBar value={150} />);
        expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100');
    });

    it('permite un nombre accesible propio', () => {
        render(<ProgressBar value={10} />);
        expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuemax', '100');
    });
});