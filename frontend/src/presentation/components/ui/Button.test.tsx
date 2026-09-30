import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { Button } from '@/presentation/components/ui/Button';

describe('Button: botón reutilizable accesible', () => {
  it('usa type="button" por defecto', () => {
    render(<Button>Guardar</Button>);

    expect(screen.getByRole('button', { name: 'Guardar' })).toHaveAttribute('type', 'button');
  });

  it('respeta un type explícito como submit', () => {
    render(<Button type="submit">Enviar</Button>);

    expect(screen.getByRole('button', { name: 'Enviar' })).toHaveAttribute('type', 'submit');
  });

  it('deshabilita el botón y anuncia Cargando... cuando isLoading', () => {
    render(<Button isLoading>Guardar</Button>);

    const boton = screen.getByRole('button', { name: 'Cargando...' });
    expect(boton).toBeDisabled();
  });

  it('llama onClick al presionar', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Aceptar</Button>);

    fireEvent.click(screen.getByRole('button', { name: 'Aceptar' }));

    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});