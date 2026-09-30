import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Spinner } from '@/presentation/components/ui/Spinner';

describe('Spinner: componente de carga', () => {
  it('renderiza con rol de status y una etiqueta accesible', () => {
    render(<Spinner label="Cargando órdenes..." />);

    expect(screen.getByRole('status', { name: 'Cargando órdenes...' })).toBeInTheDocument();
  });

  it('usa la etiqueta por defecto cuando no se entrega una', () => {
    render(<Spinner />);

    expect(screen.getByRole('status', { name: 'Cargando...' })).toBeInTheDocument();
  });

  it('aplica clases personalizadas al ícono', () => {
    const { container } = render(<Spinner className="w-10 h-10 text-primary-blue" />);

    expect(container.querySelector('.animate-spin')).toHaveClass('w-10', 'h-10');
  });
});