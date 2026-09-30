import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LoadingState } from './LoadingState';

describe('LoadingState', () => {
    it('muestra el mensaje y un spinner accesible', () => {
        render(<LoadingState message="Cargando detalle de la orden..." className="p-10" />);

        expect(screen.getByText('Cargando detalle de la orden...')).toBeInTheDocument();
        expect(
            screen.getByRole('status', { name: 'Cargando detalle de la orden...' })
        ).toBeInTheDocument();
    });

    it('aplica la clase extra recibida', () => {
        render(<LoadingState message="Cargando..." className="p-10" />);

        expect(screen.getByText('Cargando...').parentElement).toHaveClass('p-10');
    });
});