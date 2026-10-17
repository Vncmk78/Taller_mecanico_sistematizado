import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Car } from 'lucide-react';
import { EmptyState } from './EmptyState';

describe('EmptyState', () => {
    it('muestra el título del estado vacío', () => {
        render(<EmptyState title="Aún no hay vehículos registrados en el taller." />);

        expect(screen.getByText('Aún no hay vehículos registrados en el taller.')).toBeInTheDocument();
    });

    it('muestra la descripción solo cuando se entrega', () => {
        const { rerender } = render(<EmptyState title="Sin datos" />);

        expect(screen.queryByText(/Pruebe con otra patente/)).not.toBeInTheDocument();

        rerender(<EmptyState title="Sin datos" description="Pruebe con otra patente." />);

        expect(screen.getByText('Pruebe con otra patente.')).toBeInTheDocument();
    });

    it('permite una acción opcional que se puede pulsar', () => {
        const onClick = vi.fn();
        render(
            <EmptyState
                title="Sin datos"
                action={
                    <button type="button" onClick={onClick}>
                        Limpiar filtros
                    </button>
                }
            />
        );

        expect(screen.queryByRole('button')).not.toBeNull();
        screen.getByRole('button', { name: 'Limpiar filtros' }).click();
        expect(onClick).toHaveBeenCalledTimes(1);
    });

    it('acepta un ícono propio y ocupa todo el grid del listado', () => {
        const { container } = render(<EmptyState title="Sin datos" icon={Car} />);

        expect(container.querySelector('.lucide-car')).not.toBeNull();
        expect(container.querySelector('.col-span-full')).not.toBeNull();
    });
});
