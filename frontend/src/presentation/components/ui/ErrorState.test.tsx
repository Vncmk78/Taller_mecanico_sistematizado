import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ErrorState } from './ErrorState';

describe('ErrorState', () => {
    it('muestra el título y el mensaje del error con role alert', () => {
        render(<ErrorState title="No se pudieron cargar los vehículos" message="El servidor tuvo un problema." />);

        const alert = screen.getByRole('alert');
        expect(alert).toHaveTextContent('No se pudieron cargar los vehículos');
        expect(alert).toHaveTextContent('El servidor tuvo un problema.');
    });

    it('permite reintentar', () => {
        const onRetry = vi.fn();
        render(<ErrorState title="No se pudo cargar" onRetry={onRetry} />);

        fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

        expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('acepta una etiqueta de reintento distinta y una acción secundaria', () => {
        render(
            <ErrorState
                title="No se pudo cargar"
                onRetry={vi.fn()}
                retryLabel="Volver a intentar"
                action={<a href="/admin/vehiculos">Volver al catálogo</a>}
            />
        );

        expect(screen.getByRole('button', { name: 'Volver a intentar' })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Volver al catálogo' })).toBeInTheDocument();
    });

    it('oculta el botón cuando no hay reintento', () => {
        render(<ErrorState title="No se pudo cargar" />);

        expect(screen.queryByRole('button')).toBeNull();
    });

    it('aplica la clase extra recibida', () => {
        const { container } = render(<ErrorState title="No se pudo cargar" className="p-10" />);

        expect(container.querySelector('[role="alert"]')).toHaveClass('p-10');
    });

    it('muestra la referencia de la petición para poder rastrear el fallo', () => {
        render(
            <ErrorState
                title="No se pudieron cargar los vehículos"
                message="Ocurrió un error inesperado en la Gateway."
                requestId="9f1c2b3a-4d5e-6f70-8192-a3b4c5d6e7f8"
            />
        );

        expect(screen.getByText('Referencia: 9f1c2b3a-4d5e-6f70-8192-a3b4c5d6e7f8')).toBeInTheDocument();
    });

    it('omite la referencia cuando el error no trae una', () => {
        render(
            <ErrorState
                title="No se pudieron cargar los vehículos"
                message="No fue posible consultar los vehículos"
                requestId={null}
            />
        );

        expect(screen.queryByText(/Referencia:/)).not.toBeInTheDocument();
    });
});
